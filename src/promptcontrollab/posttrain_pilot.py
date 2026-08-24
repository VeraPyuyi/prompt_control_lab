"""Fail-closed protocol helpers for a controlled LoRA checkpoint pilot."""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from promptcontrollab.files import JsonDict, read_json, stable_digest, write_json


@dataclass(frozen=True)
class PilotInputs:
    """Local-only inputs for the fixed SFT checkpoint protocol."""

    model_path: Path
    train_path: Path
    validation_path: Path
    withheld_path: Path
    format_fixture_path: Path
    out_dir: Path
    seeds: tuple[int, ...] = (0, 1, 2)
    max_steps: int = 60


def build_sft_pilot_plan(inputs: PilotInputs) -> JsonDict:
    """Build a deterministic plan without importing ML libraries or using a GPU."""

    if not inputs.seeds:
        raise ValueError("SFT pilot requires at least one seed")
    if inputs.max_steps < 2:
        raise ValueError("SFT pilot max_steps must be at least 2")
    split_paths = {
        "train": inputs.train_path.resolve(),
        "validation": inputs.validation_path.resolve(),
        "withheld": inputs.withheld_path.resolve(),
        "format_fixture": inputs.format_fixture_path.resolve(),
    }
    split_rows: JsonDict = {}
    split_identities: dict[str, tuple[set[str], set[str]]] = {}
    for name, path in split_paths.items():
        if not path.is_file():
            raise ValueError(f"SFT pilot input is missing: {path}")
        row_ids, content_hashes = _split_identities(path)
        split_identities[name] = (row_ids, content_hashes)
        split_rows[name] = {
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
            "row_count": len(content_hashes),
            "id_set_sha256": f"sha256:{stable_digest(sorted(row_ids))}",
            "content_set_sha256": f"sha256:{stable_digest(sorted(content_hashes))}",
        }
    _validate_split_disjointness(split_identities)
    split_identity = {
        name: row["sha256"] for name, row in sorted(split_rows.items()) if isinstance(row, dict)
    }
    stages = ("initial", "mid", "final")
    evaluations = [
        {
            "seed": seed,
            "stage": stage,
            "run_dir": str((inputs.out_dir / f"seed-{seed}" / f"checkpoint-{stage}").resolve()),
            "diagnostics": [
                "task_score",
                "trajectory_stability",
                "generation_mismatch",
                "selective_risk",
            ],
            "soft_hard_applicability": "not_applicable",
        }
        for seed in inputs.seeds
        for stage in stages
    ]
    return {
        "schema": "prompt_control_lab.posttrain_sft_pilot.v1",
        "execution_status": "plan_only",
        "training_method": "sft_lora",
        "model_path": str(inputs.model_path.resolve()),
        "out_dir": str(inputs.out_dir.resolve()),
        "seeds": list(inputs.seeds),
        "checkpoint_stages": list(stages),
        "max_steps": inputs.max_steps,
        "mid_step": max(1, inputs.max_steps // 2),
        "task_families": ["gsm8k", "format_following"],
        "split_provenance": {
            "files": split_rows,
            "combined_sha256": f"sha256:{stable_digest(split_identity)}",
        },
        "planned_evaluations": evaluations,
        "resource_gate": {
            "approval_record_required": True,
            "queue_clear_required": True,
            "exclusive_lock_required": True,
            "gpu_process_check_required": True,
        },
        "claim_boundary": (
            "This plan defines a controlled checkpoint comparison. It records association and "
            "diagnostic evidence; it does not by itself establish a hidden causal mechanism."
        ),
    }


def write_sft_pilot_plan(inputs: PilotInputs, path: Path) -> JsonDict:
    """Build and persist a plan-only pilot protocol."""

    payload = build_sft_pilot_plan(inputs)
    write_json(path, payload)
    return payload


def validate_resource_approval(
    path: Path,
    *,
    gpu: int,
    now: datetime | None = None,
) -> JsonDict:
    """Validate an explicit, expiring server-operator resource approval record."""

    if not path.is_file():
        raise ValueError(f"Resource approval record is missing: {path}")
    payload = read_json(path)
    if payload.get("approved") is not True:
        raise ValueError("Resource approval record is not approved")
    if payload.get("queue_clear") is not True:
        raise ValueError("Resource approval record does not confirm the server queue is clear")
    recorded_gpu = payload.get("gpu")
    if not isinstance(recorded_gpu, int) or isinstance(recorded_gpu, bool) or recorded_gpu != gpu:
        raise ValueError(f"Resource approval GPU does not match requested GPU {gpu}")
    if not str(payload.get("approved_by", "")).strip():
        raise ValueError("Resource approval record is missing approved_by")

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    checked_at = _parse_timestamp(payload.get("checked_at"), field="checked_at")
    expires_at = _parse_timestamp(payload.get("expires_at"), field="expires_at")
    if checked_at > current:
        raise ValueError("Resource approval checked_at is in the future")
    if expires_at <= current:
        raise ValueError("Resource approval record has expired")
    if expires_at <= checked_at:
        raise ValueError("Resource approval expires_at must be after checked_at")
    return payload


def paired_checkpoint_statistics(
    baseline_scores: list[float],
    candidate_scores: list[float],
    *,
    seed: int,
    samples: int = 2000,
    baseline_checkpoint: str,
    candidate_checkpoint: str,
    baseline_split_hash: str,
    candidate_split_hash: str,
    baseline_sample_hash: str,
    candidate_sample_hash: str,
) -> JsonDict:
    """Compute deterministic paired bootstrap and sign-permutation evidence."""

    if len(baseline_scores) != len(candidate_scores) or not baseline_scores:
        raise ValueError("Paired checkpoint scores must be non-empty and have matched lengths")
    if samples < 100:
        raise ValueError("Paired checkpoint statistics require at least 100 samples")
    if not all(_finite_score(value) for value in [*baseline_scores, *candidate_scores]):
        raise ValueError("Paired checkpoint scores must be finite")
    for name, value in (
        ("baseline_checkpoint", baseline_checkpoint),
        ("candidate_checkpoint", candidate_checkpoint),
        ("baseline_split_hash", baseline_split_hash),
        ("candidate_split_hash", candidate_split_hash),
        ("baseline_sample_hash", baseline_sample_hash),
        ("candidate_sample_hash", candidate_sample_hash),
    ):
        if not value.strip():
            raise ValueError(f"Paired checkpoint statistics require {name}")
    deltas = [
        float(candidate) - float(baseline)
        for baseline, candidate in zip(baseline_scores, candidate_scores, strict=True)
    ]
    observed = sum(deltas) / len(deltas)
    bootstrap_rng = random.Random(seed)
    bootstrap = sorted(
        sum(deltas[bootstrap_rng.randrange(len(deltas))] for _ in deltas) / len(deltas)
        for _ in range(samples)
    )
    permutation_rng = random.Random(seed + 1_000_003)
    extreme = 0
    for _ in range(samples):
        permuted = sum(
            delta if permutation_rng.random() < 0.5 else -delta for delta in deltas
        ) / len(deltas)
        if abs(permuted) >= abs(observed) - 1e-15:
            extreme += 1
    p_value = (extreme + 1) / (samples + 1)
    comparison: JsonDict = {
        "baseline_checkpoint": baseline_checkpoint,
        "candidate_checkpoint": candidate_checkpoint,
        "baseline_split_hash": baseline_split_hash,
        "candidate_split_hash": candidate_split_hash,
        "baseline_sample_hash": baseline_sample_hash,
        "candidate_sample_hash": candidate_sample_hash,
        "mean_delta": round(observed, 12),
        "bootstrap_ci": [
            round(_quantile(bootstrap, 0.025), 12),
            round(_quantile(bootstrap, 0.975), 12),
        ],
        "permutation_p_value": round(p_value, 12),
        "holm_adjusted_p_value": round(p_value, 12),
        "n_pairs": len(deltas),
        "seed": seed,
        "samples": samples,
    }
    return {
        "schema": "prompt_control_lab.paired_checkpoint_statistics.v1",
        "comparisons": [comparison],
        "holm_family_size": 1,
    }


def training_strategy_argument(parameters: set[str]) -> dict[str, str]:
    """Return the transformers-version-compatible evaluation strategy keyword."""

    if "eval_strategy" in parameters:
        return {"eval_strategy": "steps"}
    if "evaluation_strategy" in parameters:
        return {"evaluation_strategy": "steps"}
    raise ValueError("Installed transformers TrainingArguments has no evaluation strategy field")


def sequence_exact_match(predictions: list[int], targets: list[int]) -> float:
    """Return a binary sequence-level match in the same units as generated exact match."""

    if not targets or len(predictions) != len(targets):
        return 0.0
    return float(predictions == targets)


def canonical_answer_exact_match(prediction: str, target: str) -> float:
    """Compare generated and teacher-forced answers with one canonical text rule."""

    return float(_canonical_answer(prediction) == _canonical_answer(target))


def token_trajectory_drift(vectors: list[list[float]]) -> float:
    """Measure normalized drift between adjacent token states in one hidden layer."""

    if len(vectors) < 2:
        return 0.0
    width = len(vectors[0])
    if width == 0 or any(len(vector) != width for vector in vectors):
        raise ValueError("Token trajectory vectors must have one non-empty shared width")
    distances = [
        math.dist(vectors[index], vectors[index + 1]) / math.sqrt(width)
        for index in range(len(vectors) - 1)
    ]
    return sum(distances) / len(distances)


def _split_identities(path: Path) -> tuple[set[str], set[str]]:
    row_ids: set[str] = set()
    content_hashes: set[str] = set()
    row_count = 0
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid pilot JSON at {path}:{line_number}") from exc
        if not isinstance(value, dict) or not all(key in value for key in ("prompt", "answer")):
            raise ValueError(f"Invalid pilot row at {path}:{line_number}")
        row_count += 1
        row_id = str(value.get("id", "")).strip()
        if row_id:
            if row_id in row_ids:
                raise ValueError(f"Duplicate pilot row id in {path}: {row_id}")
            row_ids.add(row_id)
        content_hash = stable_digest(
            {
                "prompt": _canonical_text(str(value["prompt"])),
                "answer": _canonical_answer(str(value["answer"])),
            }
        )
        if content_hash in content_hashes:
            raise ValueError(f"Duplicate pilot row content in {path}:{line_number}")
        content_hashes.add(content_hash)
    if row_count == 0:
        raise ValueError(f"Pilot split is empty: {path}")
    return row_ids, content_hashes


def _validate_split_disjointness(
    identities: dict[str, tuple[set[str], set[str]]],
) -> None:
    names = ("train", "validation", "withheld", "format_fixture")
    for index, first in enumerate(names):
        first_ids, first_content = identities[first]
        for second in names[index + 1 :]:
            second_ids, second_content = identities[second]
            id_overlap = first_ids & second_ids
            content_overlap = first_content & second_content
            if id_overlap or content_overlap:
                raise ValueError(
                    f"Pilot split overlap between {first} and {second}: "
                    f"{len(id_overlap)} ids, {len(content_overlap)} normalized rows"
                )


def _canonical_text(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


def _canonical_answer(value: str) -> str:
    cleaned = " ".join(value.strip().split())
    if "####" in cleaned:
        cleaned = cleaned.rsplit("####", 1)[-1].strip()
    return cleaned.casefold()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _parse_timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"Resource approval {field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Resource approval {field} is invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"Resource approval {field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _finite_score(value: float) -> bool:
    return math.isfinite(float(value))


def _quantile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("Cannot compute a quantile of an empty sample")
    position = (len(values) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower
    return values[lower] * (1.0 - weight) + values[upper] * weight
