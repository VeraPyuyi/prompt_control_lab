"""Fail-closed protocol helpers for a controlled LoRA checkpoint pilot."""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
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
    model_provenance_path: Path | None = None
    runtime_root: Path = Path("/root/prompt_control_lab_runtime")
    seeds: tuple[int, ...] = (0, 1, 2)
    max_steps: int = 60


_MODEL_PROVENANCE_FILE = "model_provenance.json"
_PINNED_REVISION_PATTERN = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
_QUEUE_SNAPSHOT_MAX_AGE_SECONDS = 90.0


def write_model_provenance(
    model_path: Path,
    *,
    model_id: str,
    revision: str,
    manifest_path: Path | None = None,
) -> JsonDict:
    """Hash a local model snapshot and bind it to a pinned provider revision."""

    if not model_path.is_dir():
        raise ValueError(f"Cached model directory is missing: {model_path}")
    if not model_id.strip():
        raise ValueError("Model provenance requires model_id")
    normalized_revision = revision.strip().lower()
    if _PINNED_REVISION_PATTERN.fullmatch(normalized_revision) is None:
        raise ValueError("Model provenance revision must be a pinned 40/64-character commit hash")
    files = _model_file_records(model_path)
    if not files:
        raise ValueError("Model provenance requires at least one model file")
    payload: JsonDict = {
        "schema": "prompt_control_lab.model_snapshot_provenance.v1",
        "model_id": model_id.strip(),
        "revision": normalized_revision,
        "files": files,
        "combined_sha256": f"sha256:{stable_digest(files)}",
    }
    write_json(manifest_path or model_provenance_path(model_path), payload)
    return payload


def model_provenance_path(model_path: Path) -> Path:
    """Return the external provenance path without mutating a shared model cache."""

    return model_path.with_name(f"{model_path.name}.{_MODEL_PROVENANCE_FILE}")


def validate_model_provenance(
    model_path: Path,
    *,
    manifest_path: Path | None = None,
) -> JsonDict:
    """Verify the pinned identity and every file hash before GPU execution."""

    provenance_path = manifest_path or model_provenance_path(model_path)
    if not provenance_path.is_file():
        raise ValueError(f"Model provenance manifest is missing: {provenance_path}")
    payload = read_json(provenance_path)
    if not str(payload.get("model_id", "")).strip():
        raise ValueError("Model provenance is missing model_id")
    revision = str(payload.get("revision", "")).strip().lower()
    if _PINNED_REVISION_PATTERN.fullmatch(revision) is None:
        raise ValueError("Model provenance revision is not a pinned commit hash")
    recorded_files = payload.get("files")
    if not isinstance(recorded_files, list) or not recorded_files:
        raise ValueError("Model provenance files must be a non-empty list")
    current_files = _model_file_records(model_path)
    if recorded_files != current_files:
        raise ValueError("Model provenance file hash mismatch or snapshot contents changed")
    combined = f"sha256:{stable_digest(current_files)}"
    if payload.get("combined_sha256") != combined:
        raise ValueError("Model provenance combined hash mismatch")
    return payload


def build_sft_pilot_plan(inputs: PilotInputs) -> JsonDict:
    """Build a deterministic plan without importing ML libraries or using a GPU."""

    if not inputs.seeds:
        raise ValueError("SFT pilot requires at least one seed")
    if len(set(inputs.seeds)) != len(inputs.seeds):
        raise ValueError("SFT pilot seeds must be unique")
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
                "prompt_reachability",
                "readout_alignment",
                "prompt_routing",
                "prompt_projection",
                "prompt_stability",
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
        "model_provenance_path": str(
            (inputs.model_provenance_path or model_provenance_path(inputs.model_path)).resolve()
        ),
        "out_dir": str(inputs.out_dir.resolve()),
        "runtime_root": str(inputs.runtime_root.resolve()),
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
            "default_resource_scope": "global_queue",
            "resource_scopes": ["global_queue", "selected_gpu"],
            "queue_clear_required_by_default": True,
            "selected_gpu_assignment_requires_explicit_authorization": True,
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
    runtime_root: Path | None = None,
) -> JsonDict:
    """Validate an expiring approval and its exact, fresh queue snapshot."""

    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Resource approval record is missing: {path}")
    payload = read_json(path)
    if payload.get("approved") is not True:
        raise ValueError("Resource approval record is not approved")
    resource_scope = str(payload.get("resource_scope", "global_queue")).strip()
    if resource_scope not in {"global_queue", "selected_gpu"}:
        raise ValueError(f"Resource approval has unsupported resource_scope: {resource_scope}")
    pending_jobs = payload.get("queue_pending_jobs")
    if not _nonnegative_int(pending_jobs):
        raise ValueError("Resource approval record must report non-negative pending jobs")
    running_jobs = payload.get("queue_running_jobs")
    if not _nonnegative_int(running_jobs):
        raise ValueError("Resource approval record must report non-negative running jobs")
    if resource_scope == "global_queue":
        if payload.get("queue_clear") is not True:
            raise ValueError("Resource approval record does not confirm the server queue is clear")
        if pending_jobs != 0:
            raise ValueError("Resource approval record must report zero pending jobs")
        if running_jobs != 0:
            raise ValueError("Resource approval record must report zero running jobs")
    else:
        _validate_selected_gpu_approval(payload, gpu=gpu)
    if not str(payload.get("queue_source", "")).strip():
        raise ValueError("Resource approval record is missing queue_source")
    if not _valid_sha256(payload.get("queue_snapshot_sha256")):
        raise ValueError("Resource approval queue_snapshot_sha256 must be a SHA-256 digest")
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
    age_seconds = (current - checked_at).total_seconds()
    if age_seconds > _QUEUE_SNAPSHOT_MAX_AGE_SECONDS:
        raise ValueError(
            "Resource approval queue snapshot is stale; refresh it immediately before launch"
        )

    queue_snapshot = _validate_queue_snapshot(
        payload,
        approval_path=path,
        approval_checked_at=checked_at,
        runtime_root=runtime_root,
    )
    payload["queue_snapshot_validation"] = queue_snapshot
    return payload


def _validate_selected_gpu_approval(payload: JsonDict, *, gpu: int) -> None:
    if payload.get("selected_gpu_reserved") is not True:
        raise ValueError("Selected-GPU approval must confirm the GPU is reserved")
    if payload.get("authorization_type") != "explicit_user_gpu_assignment":
        raise ValueError("Selected-GPU approval requires explicit user GPU assignment")
    if not str(payload.get("authorization_reason", "")).strip():
        raise ValueError("Selected-GPU approval is missing an authorization reason")
    if payload.get("external_scheduler_process_isolation_verified") is not True:
        raise ValueError("Selected-GPU approval must verify external scheduler process isolation")
    if not _valid_sha256(payload.get("external_scheduler_policy_sha256")):
        raise ValueError("Selected-GPU approval requires a scheduler policy SHA-256 digest")
    max_idle_memory = payload.get("max_idle_memory_mib")
    if (
        not isinstance(max_idle_memory, int)
        or isinstance(max_idle_memory, bool)
        or not 0 <= max_idle_memory <= 4096
    ):
        raise ValueError("Selected-GPU approval memory ceiling must be between 0 and 4096 MiB")
    selected_gpu = payload.get("selected_gpu")
    if not isinstance(selected_gpu, int) or isinstance(selected_gpu, bool) or selected_gpu != gpu:
        raise ValueError(f"Selected-GPU approval does not reserve requested GPU {gpu}")
    assigned_gpus = payload.get("assigned_gpus")
    if (
        not isinstance(assigned_gpus, list)
        or not assigned_gpus
        or any(not isinstance(value, int) or isinstance(value, bool) for value in assigned_gpus)
        or len(set(assigned_gpus)) != len(assigned_gpus)
        or gpu not in assigned_gpus
    ):
        raise ValueError("Selected-GPU approval must list unique assigned GPUs including the GPU")
    if not isinstance(payload.get("queue_clear"), bool):
        raise ValueError("Selected-GPU approval queue_clear must be a boolean observation")


def _validate_queue_snapshot(
    approval: JsonDict,
    *,
    approval_path: Path,
    approval_checked_at: datetime,
    runtime_root: Path | None,
) -> JsonDict:
    source_value = str(approval["queue_source"]).strip()
    source = Path(source_value).expanduser()
    if not source.is_absolute():
        source = approval_path.parent / source
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"Resource approval queue_source is not a real file: {source}")
    resolved = source.resolve()
    if runtime_root is not None:
        root = runtime_root.expanduser().resolve()
        if resolved == root or not resolved.is_relative_to(root):
            raise ValueError(
                f"Resource approval queue_source is outside the pilot runtime {root}: {resolved}"
            )

    observed_sha256 = _sha256(resolved)
    expected_sha256 = str(approval["queue_snapshot_sha256"])
    if observed_sha256 != expected_sha256:
        raise ValueError("Resource approval queue snapshot hash does not match queue_source")
    snapshot = read_json(resolved)
    snapshot_checked_at = _parse_timestamp(
        snapshot.get("checked_at"), field="queue snapshot checked_at"
    )
    if snapshot_checked_at != approval_checked_at:
        raise ValueError("Resource approval checked_at does not match the queue snapshot")
    resource_scope = str(approval.get("resource_scope", "global_queue")).strip()
    if str(snapshot.get("resource_scope", "global_queue")).strip() != resource_scope:
        raise ValueError("Queue snapshot resource_scope does not match the approval")
    for key in ("queue_pending_jobs", "queue_running_jobs"):
        value = snapshot.get(key)
        if not _nonnegative_int(value):
            raise ValueError(f"Current queue snapshot must report non-negative {key}")
        if value != approval.get(key):
            raise ValueError(f"Resource approval {key} does not match the queue snapshot")
    queue_clear = snapshot.get("queue_clear")
    if not isinstance(queue_clear, bool) or queue_clear != approval.get("queue_clear"):
        raise ValueError("Queue snapshot queue_clear does not match the approval")
    validation: JsonDict = {
        "path": str(resolved),
        "sha256": observed_sha256,
        "checked_at": snapshot_checked_at.isoformat(),
        "resource_scope": resource_scope,
        "queue_clear": queue_clear,
        "queue_pending_jobs": snapshot["queue_pending_jobs"],
        "queue_running_jobs": snapshot["queue_running_jobs"],
        "verified_inside_execution_lock": True,
    }
    if resource_scope == "global_queue":
        if queue_clear is not True:
            raise ValueError("Current queue snapshot does not report queue_clear=true")
        if snapshot["queue_pending_jobs"] != 0 or snapshot["queue_running_jobs"] != 0:
            raise ValueError("Current global queue snapshot must report zero pending/running jobs")
        return validation

    selected_fields = (
        "selected_gpu",
        "assigned_gpus",
        "selected_gpu_reserved",
        "authorization_type",
        "external_scheduler_process_isolation_verified",
        "external_scheduler_policy_sha256",
        "max_idle_memory_mib",
    )
    for key in selected_fields:
        if snapshot.get(key) != approval.get(key):
            raise ValueError(f"Selected-GPU queue snapshot {key} does not match the approval")
    _validate_selected_gpu_snapshot(snapshot, gpu=int(approval["gpu"]))
    validation.update(
        {
            "selected_gpu": snapshot["selected_gpu"],
            "assigned_gpus": snapshot["assigned_gpus"],
            "external_scheduler_policy_sha256": snapshot[
                "external_scheduler_policy_sha256"
            ],
        }
    )
    return validation


def _validate_selected_gpu_snapshot(snapshot: JsonDict, *, gpu: int) -> None:
    if snapshot.get("selected_gpu_reserved") is not True:
        raise ValueError("Selected-GPU queue snapshot does not confirm the GPU is reserved")
    if snapshot.get("authorization_type") != "explicit_user_gpu_assignment":
        raise ValueError("Selected-GPU queue snapshot lacks explicit assignment authorization")
    if snapshot.get("external_scheduler_process_isolation_verified") is not True:
        raise ValueError("Selected-GPU queue snapshot lacks scheduler process isolation evidence")
    if not _valid_sha256(snapshot.get("external_scheduler_policy_sha256")):
        raise ValueError("Selected-GPU queue snapshot requires a scheduler policy SHA-256")
    max_idle_memory = snapshot.get("max_idle_memory_mib")
    if (
        not isinstance(max_idle_memory, int)
        or isinstance(max_idle_memory, bool)
        or not 0 <= max_idle_memory <= 4096
    ):
        raise ValueError("Selected-GPU queue snapshot has an invalid memory ceiling")
    if snapshot.get("selected_gpu") != gpu:
        raise ValueError(f"Selected-GPU queue snapshot does not identify GPU {gpu}")
    assigned_gpus = snapshot.get("assigned_gpus")
    if not isinstance(assigned_gpus, list) or gpu not in assigned_gpus:
        raise ValueError("Selected-GPU queue snapshot does not include the requested GPU")


def _nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


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


def score_pilot_output(prediction: str, target: str, task_slice: str) -> float:
    """Score one pilot answer using the declared task family's contract."""

    normalized_slice = task_slice.strip().casefold().replace("-", "_")
    if normalized_slice in {"gsm8k", "math", "arithmetic"}:
        predicted_number = _final_numeric_answer(prediction)
        target_number = _final_numeric_answer(target)
        if predicted_number is None or target_number is None:
            return 0.0
        return float(predicted_number == target_number)
    return float(prediction == target)


def validate_gpu_idle_snapshots(
    first: JsonDict,
    second: JsonDict,
    *,
    gpu: int,
    max_memory_mib: int = 1024,
) -> JsonDict:
    """Validate two consecutive observations of the same idle GPU."""

    snapshots = (first, second)
    uuids: list[str] = []
    for index, snapshot in enumerate(snapshots, 1):
        if snapshot.get("gpu") != gpu:
            raise ValueError(f"GPU idle snapshot {index} does not describe GPU {gpu}")
        uuid = str(snapshot.get("uuid", "")).strip()
        if not uuid:
            raise ValueError(f"GPU idle snapshot {index} is missing the GPU UUID")
        uuids.append(uuid)
        processes = snapshot.get("active_compute_pids")
        if not isinstance(processes, list):
            raise ValueError(f"GPU idle snapshot {index} has invalid active compute process data")
        if processes:
            raise ValueError(f"GPU {gpu} has active compute processes")
        memory = snapshot.get("memory_used_mib")
        if not isinstance(memory, int | float) or isinstance(memory, bool):
            raise ValueError(f"GPU idle snapshot {index} has invalid memory usage")
        if float(memory) > max_memory_mib:
            raise ValueError(
                f"GPU {gpu} has {memory} MiB allocated; refusing to start"
            )
    if uuids[0] != uuids[1]:
        raise ValueError("GPU identity changed between consecutive idle checks")
    return {
        "gpu": gpu,
        "gpu_uuid": uuids[0],
        "consecutive_idle_checks": 2,
        "snapshots": [first, second],
    }


def aggregate_pilot_decisions(decisions: list[str]) -> str:
    """Conservatively combine per-checkpoint gate decisions across seeds."""

    if not decisions:
        return "insufficient_evidence"
    allowed = {"pass", "needs_review", "hold", "insufficient_evidence"}
    unknown = sorted(set(decisions) - allowed)
    if unknown:
        raise ValueError(f"Unknown pilot gate decisions: {', '.join(unknown)}")
    for decision in ("hold", "insufficient_evidence", "needs_review", "pass"):
        if decision in decisions:
            return decision
    return "insufficient_evidence"


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


def _model_file_records(model_path: Path) -> list[JsonDict]:
    records: list[JsonDict] = []
    for path in sorted(model_path.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(model_path)
        if (
            not path.is_file()
            or path.name == _MODEL_PROVENANCE_FILE
            or ".cache" in relative.parts
        ):
            continue
        records.append(
            {
                "path": relative.as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return records


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


_NUMBER_PATTERN = re.compile(r"[-+]?(?:\d[\d,]*)(?:\.\d+)?")


def _final_numeric_answer(value: str) -> Decimal | None:
    cleaned = value.rsplit("####", 1)[-1] if "####" in value else value
    matches = _NUMBER_PATTERN.findall(cleaned)
    if not matches:
        return None
    try:
        return Decimal(matches[-1].replace(",", ""))
    except InvalidOperation:
        return None


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


def _valid_sha256(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        return False
    digest = value.removeprefix("sha256:")
    return len(digest) == 64 and all(character in "0123456789abcdef" for character in digest)


def _quantile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("Cannot compute a quantile of an empty sample")
    position = (len(values) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower
    return values[lower] * (1.0 - weight) + values[upper] * weight
