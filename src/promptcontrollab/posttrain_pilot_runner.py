"""Guarded execution support for the three-stage local LoRA pilot."""

from __future__ import annotations

import contextlib
import importlib
import inspect
import json
import os
import subprocess
import time
from collections import defaultdict
from collections.abc import Iterator
from itertools import groupby
from pathlib import Path
from typing import Any

from promptcontrollab.files import JsonDict, ensure_dir, stable_digest, write_json
from promptcontrollab.posttrain_pilot import (
    PilotInputs,
    build_sft_pilot_plan,
    canonical_answer_exact_match,
    paired_checkpoint_statistics,
    token_trajectory_drift,
    training_strategy_argument,
    validate_resource_approval,
)


def execute_sft_pilot(
    inputs: PilotInputs,
    *,
    approval_path: Path,
    gpu: int,
    lock_file: Path,
) -> None:
    """Execute the pilot only after explicit queue, GPU, and lock checks pass."""

    validate_resource_approval(approval_path, gpu=gpu)
    _assert_gpu_idle(gpu)
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu)
    with _exclusive_lock(lock_file):
        _run_pilot(inputs)


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


def _assert_gpu_idle(index: int) -> None:
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
    active = [line for line in process_query.stdout.splitlines() if line.startswith(selected_uuid)]
    if active:
        raise RuntimeError(f"GPU {index} has active compute processes")
    if selected_memory > 1024:
        raise RuntimeError(f"GPU {index} has {selected_memory} MiB allocated; refusing to start")


def _run_pilot(inputs: PilotInputs) -> None:
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
        trainer.train()
        final_adapter = adapter_root / "final"
        trainer.model.save_pretrained(final_adapter)
        mid_adapter = training_root / f"checkpoint-{mid_step}"
        del trainer, model, base
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        stage_scores: dict[str, list[float]] = {}
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
            stage_scores[stage] = _evaluate_checkpoint(
                model=evaluation_model,
                tokenizer=tokenizer,
                rows=eval_rows,
                out_dir=seed_root / f"checkpoint-{stage}",
                checkpoint_id=f"seed-{seed}-{stage}",
                seed=seed,
                model_id=str(inputs.model_path.resolve()),
                split_hash=split_hash,
                sample_hash=sample_hash,
                torch_module=torch,
            )
            del evaluation_model
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        baseline_scores = stage_scores["initial"]
        for stage in ("initial", "mid", "final"):
            write_json(
                seed_root / f"checkpoint-{stage}" / "stats.json",
                paired_checkpoint_statistics(
                    baseline_scores,
                    stage_scores[stage],
                    seed=seed,
                    baseline_checkpoint=f"seed-{seed}-initial",
                    candidate_checkpoint=f"seed-{seed}-{stage}",
                    baseline_split_hash=split_hash,
                    candidate_split_hash=split_hash,
                    baseline_sample_hash=sample_hash,
                    candidate_sample_hash=sample_hash,
                ),
            )


def _evaluate_checkpoint(
    *,
    model: Any,
    tokenizer: Any,
    rows: list[JsonDict],
    out_dir: Path,
    checkpoint_id: str,
    seed: int,
    model_id: str,
    split_hash: str,
    sample_hash: str,
    torch_module: Any,
) -> list[float]:
    scores: list[float] = []
    confidences: list[float] = []
    teacher_matches: list[float] = []
    drifts: list[float] = []
    generated_lengths: list[float] = []
    latencies_ms: list[float] = []
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
            score = canonical_answer_exact_match(output, expected)
            scores.append(score)
            by_slice[str(row.get("slice", "default"))].append(score)
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
                    device,
                    torch_module,
                )
            )
            hidden = model(**encoded, output_hidden_states=True, return_dict=True).hidden_states
            final_layer = hidden[-1][0].float().detach().cpu().tolist()
            drifts.append(token_trajectory_drift(final_layer))

    mean_score = _mean(scores)
    teacher_score = _mean(teacher_matches)
    ensure_dir(out_dir / "diagnostics")
    write_json(
        out_dir / "manifest.json",
        {
            "checkpoint": {
                "id": checkpoint_id,
                "training_method": "sft_lora",
                "provider": "huggingface-local",
                "model_id": model_id,
                "split_hash": split_hash,
                "seed": seed,
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
    return scores


def _teacher_forced_canonical_exact_match(
    model: Any,
    tokenizer: Any,
    prompt: str,
    expected: str,
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
    return canonical_answer_exact_match(predicted_text, target_text)


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
