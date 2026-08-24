"""Guarded execution support for the three-stage local LoRA pilot."""

from __future__ import annotations

import contextlib
import importlib
import inspect
import json
import math
import os
import subprocess
import time
from collections import defaultdict
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path
from typing import Any

from promptcontrollab.files import JsonDict, ensure_dir, stable_digest, write_json
from promptcontrollab.posttrain_gate import run_posttrain_gate
from promptcontrollab.posttrain_pilot import (
    PilotInputs,
    build_sft_pilot_plan,
    paired_checkpoint_statistics,
    score_pilot_output,
    token_trajectory_drift,
    training_strategy_argument,
    validate_gpu_idle_snapshots,
    validate_model_provenance,
    validate_resource_approval,
)
from promptcontrollab.posttrain_pilot_summary import write_pilot_summary


@dataclass(frozen=True)
class CheckpointEvaluation:
    """In-memory checkpoint evidence needed for matched stage comparisons."""

    scores: list[float]
    representation_centroid: list[float]
    mean_score: float
    teacher_forced_score: float


def execute_sft_pilot(
    inputs: PilotInputs,
    *,
    approval_path: Path,
    gpu: int,
    lock_file: Path,
) -> None:
    """Execute the pilot only after explicit queue, GPU, and lock checks pass."""

    model_provenance = validate_model_provenance(inputs.model_path)
    approval = validate_resource_approval(approval_path, gpu=gpu)
    gpu_gate = _assert_gpu_idle_twice(gpu)
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu)
    with _exclusive_lock(lock_file):
        ensure_dir(inputs.out_dir)
        write_json(
            inputs.out_dir / "resource_gate.json",
            {
                "schema": "prompt_control_lab.resource_gate.v1",
                "approval": approval,
                "gpu_gate": gpu_gate,
                "lock_file": str(lock_file.resolve()),
                "model_provenance": {
                    "model_id": model_provenance.get("model_id"),
                    "revision": model_provenance.get("revision"),
                    "combined_sha256": model_provenance.get("combined_sha256"),
                },
            },
        )
        _run_pilot(inputs, model_provenance=model_provenance)


@contextlib.contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    if os.name == "nt":
        raise RuntimeError("The GPU pilot lock requires a POSIX server")
    fcntl = importlib.import_module("fcntl")

    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f"Another pilot owns the lock: {path}") from exc
        stream.write(str(os.getpid()))
        stream.flush()
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _assert_gpu_idle_twice(
    index: int,
    *,
    interval_seconds: float = 15.0,
    sleep: Callable[[float], None] = time.sleep,
) -> JsonDict:
    """Require two consecutive observations before allocating the selected GPU."""

    first = _gpu_idle_snapshot(index)
    sleep(interval_seconds)
    second = _gpu_idle_snapshot(index)
    return validate_gpu_idle_snapshots(first, second, gpu=index)


def _assert_gpu_idle(index: int) -> None:
    """Backward-compatible single-check wrapper used by older callers."""

    validate_gpu_idle_snapshots(
        _gpu_idle_snapshot(index),
        _gpu_idle_snapshot(index),
        gpu=index,
    )


def _gpu_idle_snapshot(index: int) -> JsonDict:
    gpu_query = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=index,uuid,memory.used",
            "--format=csv,noheader,nounits",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    selected_uuid = ""
    selected_memory = 0
    for line in gpu_query.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) == 3 and parts[0] == str(index):
            selected_uuid = parts[1]
            selected_memory = int(parts[2])
            break
    if not selected_uuid:
        raise RuntimeError(f"GPU {index} was not reported by nvidia-smi")

    process_query = subprocess.run(
        [
            "nvidia-smi",
            "--query-compute-apps=gpu_uuid,pid",
            "--format=csv,noheader,nounits",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    active: list[int] = []
    for line in process_query.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 2 or parts[0] != selected_uuid:
            continue
        try:
            active.append(int(parts[1]))
        except ValueError:
            continue
    return {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "gpu": index,
        "uuid": selected_uuid,
        "memory_used_mib": selected_memory,
        "active_compute_pids": active,
    }


def _run_pilot(inputs: PilotInputs, *, model_provenance: JsonDict) -> None:
    try:
        torch = importlib.import_module("torch")
        peft = importlib.import_module("peft")
        transformers = importlib.import_module("transformers")
    except ImportError as exc:
        raise RuntimeError(
            "Execution requires torch, transformers, peft, and accelerate in the server env"
        ) from exc

    if not inputs.model_path.is_dir():
        raise ValueError(f"Cached model directory is missing: {inputs.model_path}")
    train_rows = _read_rows(inputs.train_path)
    validation_rows = _read_rows(inputs.validation_path)
    eval_rows = _read_rows(inputs.withheld_path) + _read_rows(inputs.format_fixture_path)
    if not train_rows or not validation_rows or not eval_rows:
        raise ValueError("Pilot train, validation, and evaluation inputs must be non-empty")

    tokenizer = transformers.AutoTokenizer.from_pretrained(
        str(inputs.model_path), local_files_only=True, trust_remote_code=False
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    class SftDataset:
        def __init__(self, rows: list[JsonDict]) -> None:
            self.examples = [
                tokenizer(
                    _training_text(row),
                    truncation=True,
                    max_length=512,
                    return_tensors="pt",
                )
                for row in rows
            ]

        def __len__(self) -> int:
            return len(self.examples)

        def __getitem__(self, index: int) -> JsonDict:
            return {key: value.squeeze(0) for key, value in self.examples[index].items()}

    split_hash = str(build_sft_pilot_plan(inputs)["split_provenance"]["combined_sha256"])
    sample_hash = _evaluation_sample_hash(eval_rows)
    for seed in inputs.seeds:
        transformers.set_seed(seed)
        seed_root = inputs.out_dir / f"seed-{seed}"
        adapter_root = seed_root / "adapters"
        ensure_dir(adapter_root)
        base = transformers.AutoModelForCausalLM.from_pretrained(
            str(inputs.model_path),
            local_files_only=True,
            trust_remote_code=False,
            torch_dtype="auto",
        )
        model = peft.get_peft_model(
            base,
            peft.LoraConfig(
                task_type="CAUSAL_LM",
                r=8,
                lora_alpha=16,
                lora_dropout=0.05,
                target_modules="all-linear",
            ),
        )
        initial_adapter = adapter_root / "initial"
        model.save_pretrained(initial_adapter)
        mid_step = max(1, inputs.max_steps // 2)
        training_root = seed_root / "trainer"
        strategy = training_strategy_argument(
            set(inspect.signature(transformers.TrainingArguments.__init__).parameters)
        )
        trainer = transformers.Trainer(
            model=model,
            args=transformers.TrainingArguments(
                output_dir=str(training_root),
                max_steps=inputs.max_steps,
                per_device_train_batch_size=2,
                gradient_accumulation_steps=4,
                learning_rate=2e-4,
                logging_steps=max(1, mid_step // 3),
                save_steps=mid_step,
                eval_steps=mid_step,
                save_total_limit=3,
                report_to=[],
                remove_unused_columns=False,
                bf16=bool(torch.cuda.is_available() and torch.cuda.is_bf16_supported()),
                seed=seed,
                data_seed=seed,
                **strategy,
            ),
            train_dataset=SftDataset(train_rows),
            eval_dataset=SftDataset(validation_rows),
            data_collator=transformers.DataCollatorForLanguageModeling(
                tokenizer=tokenizer,
                mlm=False,
            ),
        )
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
        training_started = time.perf_counter()
        train_result = trainer.train()
        measured_runtime = time.perf_counter() - training_started
        peak_memory_mib = (
            float(torch.cuda.max_memory_allocated()) / (1024.0 * 1024.0)
            if torch.cuda.is_available()
            else 0.0
        )
        raw_train_metrics = getattr(train_result, "metrics", {})
        train_metrics = {
            str(key): value
            for key, value in raw_train_metrics.items()
            if isinstance(value, str | int | float | bool) or value is None
        }
        write_json(
            seed_root / "training_resources.json",
            {
                "schema": "prompt_control_lab.sft_training_resources.v1",
                "seed": seed,
                "max_steps": inputs.max_steps,
                "measured_runtime_seconds": measured_runtime,
                "peak_memory_mib": peak_memory_mib,
                "trainer_metrics": train_metrics,
                "lora": {"r": 8, "alpha": 16, "dropout": 0.05},
                "optimizer": {"learning_rate": 0.0002},
            },
        )
        final_adapter = adapter_root / "final"
        trainer.model.save_pretrained(final_adapter)
        mid_adapter = training_root / f"checkpoint-{mid_step}"
        del trainer, model, base
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        stage_evaluations: dict[str, CheckpointEvaluation] = {}
        for stage, adapter_path in (
            ("initial", initial_adapter),
            ("mid", mid_adapter),
            ("final", final_adapter),
        ):
            if not adapter_path.is_dir():
                raise RuntimeError(f"Expected adapter checkpoint is missing: {adapter_path}")
            evaluation_model = peft.AutoPeftModelForCausalLM.from_pretrained(
                str(adapter_path),
                local_files_only=True,
                trust_remote_code=False,
                torch_dtype="auto",
            )
            evaluation_model.eval()
            if torch.cuda.is_available():
                evaluation_model.cuda()
            stage_evaluations[stage] = _evaluate_checkpoint(
                model=evaluation_model,
                tokenizer=tokenizer,
                rows=eval_rows,
                out_dir=seed_root / f"checkpoint-{stage}",
                checkpoint_id=f"seed-{seed}-{stage}",
                seed=seed,
                model_id=str(model_provenance["model_id"]),
                model_revision=str(model_provenance["revision"]),
                model_snapshot_sha256=str(model_provenance["combined_sha256"]),
                split_hash=split_hash,
                sample_hash=sample_hash,
                torch_module=torch,
            )
            del evaluation_model
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        baseline_evaluation = stage_evaluations["initial"]
        baseline_scores = baseline_evaluation.scores
        for stage in ("initial", "mid", "final"):
            evaluation = stage_evaluations[stage]
            _write_relative_prompt_diagnostics(
                seed_root / f"checkpoint-{stage}",
                baseline=baseline_evaluation,
                candidate=evaluation,
                stage=stage,
            )
            write_json(
                seed_root / f"checkpoint-{stage}" / "stats.json",
                paired_checkpoint_statistics(
                    baseline_scores,
                    evaluation.scores,
                    seed=seed,
                    baseline_checkpoint=f"seed-{seed}-initial",
                    candidate_checkpoint=f"seed-{seed}-{stage}",
                    baseline_split_hash=split_hash,
                    candidate_split_hash=split_hash,
                    baseline_sample_hash=sample_hash,
                    candidate_sample_hash=sample_hash,
                ),
            )
        for stage in ("mid", "final"):
            run_posttrain_gate(
                baseline_dir=seed_root / "checkpoint-initial",
                candidate_dir=seed_root / f"checkpoint-{stage}",
                policy_path=None,
                out_dir=seed_root / "gates" / f"initial-to-{stage}",
                capability="full-open-model",
            )
    write_pilot_summary(inputs.out_dir, seeds=inputs.seeds)


def _evaluate_checkpoint(
    *,
    model: Any,
    tokenizer: Any,
    rows: list[JsonDict],
    out_dir: Path,
    checkpoint_id: str,
    seed: int,
    model_id: str,
    model_revision: str,
    model_snapshot_sha256: str,
    split_hash: str,
    sample_hash: str,
    torch_module: Any,
) -> CheckpointEvaluation:
    scores: list[float] = []
    confidences: list[float] = []
    teacher_matches: list[float] = []
    drifts: list[float] = []
    generated_lengths: list[float] = []
    latencies_ms: list[float] = []
    representation_sum: list[float] | None = None
    by_slice: dict[str, list[float]] = defaultdict(list)
    device = next(model.parameters()).device
    with torch_module.no_grad():
        for row in rows:
            prompt = f"{str(row['prompt']).strip()}\nAnswer:"
            encoded = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=448)
            encoded = {key: value.to(device) for key, value in encoded.items()}
            started = time.perf_counter()
            generated = model.generate(
                **encoded,
                max_new_tokens=48,
                do_sample=False,
                return_dict_in_generate=True,
                output_scores=True,
                pad_token_id=tokenizer.pad_token_id,
            )
            latencies_ms.append((time.perf_counter() - started) * 1000.0)
            prompt_length = encoded["input_ids"].shape[1]
            new_tokens = generated.sequences[0, prompt_length:]
            generated_lengths.append(float(new_tokens.numel()))
            output = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
            expected = str(row["answer"]).strip()
            task_slice = str(row.get("slice", "default"))
            score = score_pilot_output(output, expected, task_slice)
            scores.append(score)
            by_slice[task_slice].append(score)
            probabilities = [
                float(logits[0].softmax(dim=-1).max().item()) for logits in generated.scores
            ]
            confidences.append(sum(probabilities) / len(probabilities) if probabilities else 0.0)
            teacher_matches.append(
                _teacher_forced_canonical_exact_match(
                    model,
                    tokenizer,
                    prompt,
                    expected,
                    task_slice,
                    device,
                    torch_module,
                )
            )
            hidden = model(**encoded, output_hidden_states=True, return_dict=True).hidden_states
            final_tensor = hidden[-1][0].float().detach().cpu()
            final_layer = final_tensor.tolist()
            drifts.append(token_trajectory_drift(final_layer))
            representation = final_tensor.mean(dim=0).tolist()
            if representation_sum is None:
                representation_sum = [float(value) for value in representation]
            else:
                representation_sum = [
                    current + float(value)
                    for current, value in zip(
                        representation_sum,
                        representation,
                        strict=True,
                    )
                ]

    mean_score = _mean(scores)
    teacher_score = _mean(teacher_matches)
    representation_centroid = [
        value / len(rows) for value in (representation_sum or [])
    ]
    ensure_dir(out_dir / "diagnostics")
    write_json(
        out_dir / "manifest.json",
        {
            "checkpoint": {
                "id": checkpoint_id,
                "training_method": "sft_lora",
                "provider": "huggingface-local",
                "model_id": model_id,
                "model_revision": model_revision,
                "model_snapshot_sha256": model_snapshot_sha256,
                "split_hash": split_hash,
                "seed": seed,
                "capabilities": {
                    "hidden_states": True,
                    "output_head": True,
                    "repeated_runs": True,
                    "interventions": False,
                },
            }
        },
    )
    write_json(
        out_dir / "metrics.json",
        {
            "mean_score": mean_score,
            "mean_tokens": _mean(generated_lengths),
            "mean_latency_ms": _mean(latencies_ms),
            "n": len(scores),
            "sample_hash": sample_hash,
            "by_slice": {name: _mean(values) for name, values in sorted(by_slice.items())},
        },
    )
    write_json(
        out_dir / "diagnostics/trajectory.json",
        {
            "mean_step_drift": _mean(drifts),
            "definition": (
                "Mean normalized distance between adjacent prompt-token states in the final "
                "hidden layer."
            ),
        },
    )
    write_json(
        out_dir / "diagnostics/soft_hard.json",
        {
            "applicability": "not_applicable",
            "reason": "This SFT LoRA checkpoint does not deploy a learned soft prompt.",
        },
    )
    write_json(
        out_dir / "diagnostics/generation_mismatch.json",
        {
            "gap": abs(teacher_score - mean_score),
            "teacher_forced_canonical_exact_match": teacher_score,
            "free_generation_canonical_exact_match": mean_score,
            "definition": (
                "Absolute difference between teacher-forced and free-generation answers "
                "under one canonical text exact-match rule."
            ),
        },
    )
    write_json(
        out_dir / "diagnostics/selective_risk.json",
        {
            "observed_aurc": _aurc(scores, confidences),
            "confidence_definition": "Mean maximum token probability over generated answer tokens.",
        },
    )
    write_json(
        out_dir / "diagnostics/readout_alignment.json",
        {
            "schema": "prompt_control_lab.readout_alignment.v1",
            "teacher_forced_score": teacher_score,
            "free_generation_score": mean_score,
            "alignment_gap": abs(teacher_score - mean_score),
            "interpretation_role": "mechanism",
            "claim_boundary": (
                "This score-level alignment proxy does not identify a unique hidden mechanism."
            ),
        },
    )
    write_json(
        out_dir / "diagnostics/prompt_routing.json",
        {
            "schema": "prompt_control_lab.prompt_routing.v1",
            "evidence_status": "insufficient_evidence",
            "reason": "The SFT pilot does not intervene on a prompt-routing mechanism.",
            "interpretation_role": "boundary",
        },
    )
    write_json(
        out_dir / "diagnostics/prompt_projection.json",
        {
            "schema": "prompt_control_lab.prompt_projection.v1",
            "applicability": "not_applicable",
            "reason": "A standard LoRA checkpoint does not require soft-to-hard prompt rounding.",
            "interpretation_role": "boundary",
        },
    )
    write_json(
        out_dir / "diagnostics/prompt_stability.json",
        {
            "schema": "prompt_control_lab.prompt_stability.v1",
            "mean_step_drift": _mean(drifts),
            "interpretation_role": "stability",
            "claim_boundary": (
                "Observed trajectory consistency is a diagnostic association, not a stability "
                "guarantee."
            ),
        },
    )
    return CheckpointEvaluation(
        scores=scores,
        representation_centroid=representation_centroid,
        mean_score=mean_score,
        teacher_forced_score=teacher_score,
    )


def _write_relative_prompt_diagnostics(
    out_dir: Path,
    *,
    baseline: CheckpointEvaluation,
    candidate: CheckpointEvaluation,
    stage: str,
) -> None:
    shift = _representation_shift(
        baseline.representation_centroid,
        candidate.representation_centroid,
    )
    write_json(
        out_dir / "diagnostics/prompt_reachability.json",
        {
            "schema": "prompt_control_lab.prompt_reachability.v1",
            "baseline_stage": "initial",
            "candidate_stage": stage,
            "representation_shift_l2_normalized": shift,
            "score_delta": candidate.mean_score - baseline.mean_score,
            "baseline_centroid_sha256": _centroid_digest(baseline.representation_centroid),
            "candidate_centroid_sha256": _centroid_digest(candidate.representation_centroid),
            "interpretation_role": "mechanism",
            "claim_boundary": (
                "The measured checkpoint-to-checkpoint representation shift is associated with "
                "training stage; it does not prove a unique causal path."
            ),
        },
    )


def _representation_shift(baseline: list[float], candidate: list[float]) -> float | None:
    if not baseline or len(baseline) != len(candidate):
        return None
    return math.dist(baseline, candidate) / math.sqrt(len(baseline))


def _centroid_digest(values: list[float]) -> str:
    return f"sha256:{stable_digest([round(value, 8) for value in values])}"


def _teacher_forced_canonical_exact_match(
    model: Any,
    tokenizer: Any,
    prompt: str,
    expected: str,
    task_slice: str,
    device: Any,
    torch_module: Any,
) -> float:
    prefix = tokenizer(prompt, return_tensors="pt")["input_ids"].to(device)
    answer = tokenizer(expected, add_special_tokens=False, return_tensors="pt")["input_ids"].to(
        device
    )
    if answer.shape[1] == 0:
        return 0.0
    full = torch_module.cat([prefix, answer], dim=1)
    with torch_module.no_grad():
        logits = model(input_ids=full, return_dict=True).logits
    start = prefix.shape[1]
    predictions = logits[0, start - 1 : -1].argmax(dim=-1).tolist()
    targets = answer[0].tolist()
    predicted_text = tokenizer.decode(predictions, skip_special_tokens=True)
    target_text = tokenizer.decode(targets, skip_special_tokens=True)
    return score_pilot_output(predicted_text, target_text, task_slice)


def _read_rows(path: Path) -> list[JsonDict]:
    rows: list[JsonDict] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict) or not all(key in value for key in ("prompt", "answer")):
            raise ValueError(f"Invalid pilot row at {path}:{line_number}")
        rows.append(value)
    return rows


def _training_text(row: JsonDict) -> str:
    return f"{str(row['prompt']).strip()}\nAnswer:{str(row['answer']).strip()}"


def _evaluation_sample_hash(rows: list[JsonDict]) -> str:
    identities = [
        {
            "id": str(row.get("id", "")),
            "prompt": str(row["prompt"]),
            "answer": str(row["answer"]),
            "slice": str(row.get("slice", "default")),
        }
        for row in rows
    ]
    return f"sha256:{stable_digest(identities)}"


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _aurc(scores: list[float], confidences: list[float]) -> float:
    ranked = sorted(
        zip(confidences, scores, strict=True),
        key=lambda pair: pair[0],
        reverse=True,
    )
    risks: list[float] = []
    accepted = 0
    accepted_score = 0.0
    for _, tied_rows in groupby(ranked, key=lambda pair: pair[0]):
        group = list(tied_rows)
        group_mean = _mean([score for _, score in group])
        for offset in range(1, len(group) + 1):
            expected_score = accepted_score + group_mean * offset
            risks.append(1.0 - expected_score / (accepted + offset))
        accepted += len(group)
        accepted_score += sum(score for _, score in group)
    return _mean(risks)
