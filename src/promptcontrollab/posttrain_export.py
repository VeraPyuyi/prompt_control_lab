"""Portable, aggregate-only export for a completed post-training pilot."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from promptcontrollab.core.files import JsonDict, ensure_dir, stable_digest

_STAGES = ("initial", "mid", "final")
_GATE_STAGES = ("mid", "final")
_ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\[^\\\s]+\\|file://|(?:^|[\s\"'(=])/(?!/)[^\s\"']+)",
    re.MULTILINE,
)
_SECRET_PATTERN = re.compile(
    r"(?i)(?:api[_-]?key|password|private[_-]?key|bearer\s+|"
    r"sk[-_][A-Za-z0-9][A-Za-z0-9._-]{14,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    r"xox[baprs]-[A-Za-z0-9-]{10,}|(?:AKIA|ASIA)[A-Z0-9]{16}|"
    r"AIza[A-Za-z0-9_-]{20,}|"
    r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})"
)
_HASH_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")
_COMMIT_PATTERN = re.compile(r"[0-9a-f]{7,64}\Z")
_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/+:-]{0,159}\Z")
_VERSION_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+_-]{0,79}\Z")
_PUBLIC_CHECKS = frozenset(
    {
        "artifact_completeness",
        "evidence_validity",
        "provenance",
        "task_score",
        "paired_uncertainty",
        "slice_regression",
        "resource_cost",
        "trajectory_stability",
        "soft_hard_deployment",
        "generation_mismatch",
        "selective_risk",
        "prompt_reachability",
        "readout_alignment",
        "prompt_routing",
        "prompt_projection",
        "prompt_stability",
    }
)
_PUBLIC_ATTEMPT_REASONS = frozenset(
    {
        "accelerate_dependency_mismatch",
        "operator_authorized_parallel_relaunch",
        "transient_cuda_oom_root_cause_not_proven",
        "pre_classification_fix_gate_reports",
        "oom",
    }
)
_DECISION_PRIORITY = {"pass": 0, "needs_review": 1, "insufficient_evidence": 2, "hold": 3}


@dataclass
class _SourceSnapshot:
    root: Path
    payloads: dict[Path, JsonDict] = field(default_factory=dict)
    hashes: dict[Path, str] = field(default_factory=dict)

    def read(self, path: Path) -> JsonDict:
        resolved = path.resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError(f"Post-training artifact escapes the source run: {path}")
        if resolved in self.payloads:
            return self.payloads[resolved]
        if not resolved.is_file():
            raise ValueError(f"Required post-training artifact is missing: {path}")
        data = resolved.read_bytes()
        try:
            value = json.loads(data.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid JSON artifact: {path}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"Expected JSON object in {path}")
        self.payloads[resolved] = value
        self.hashes[resolved] = _sha256_bytes(data)
        return value


def export_posttrain_pilot(*, run_dir: Path, out_dir: Path) -> JsonDict:
    """Export only aggregate checkpoint evidence and path-free provenance."""

    run = run_dir.expanduser().resolve()
    out = out_dir.expanduser().resolve()
    if not run.is_dir():
        raise ValueError(f"Post-training pilot run is missing: {run_dir}")
    if out.exists():
        raise ValueError(f"Post-training export output already exists: {out_dir}")
    if out == run or out.is_relative_to(run):
        raise ValueError("Post-training export output must be outside the source run")

    source = _SourceSnapshot(run)
    summary_path = run / "pilot_summary.json"
    summary = source.read(summary_path)
    seeds = _validated_seeds(summary)
    _validate_complete_summary(summary, seeds=seeds)
    provenance = _portable_provenance(source, seeds=seeds)
    checkpoint_rows = _checkpoint_rows(
        run,
        seeds=seeds,
        source=source,
        provenance=provenance,
    )
    gate_rows = _gate_rows(
        run,
        seeds=seeds,
        source=source,
        checkpoint_rows=checkpoint_rows,
    )
    public_summary = _public_summary(
        summary,
        seeds=seeds,
        checkpoint_rows=checkpoint_rows,
        gate_rows=gate_rows,
    )
    provenance["source_snapshot_sha256"] = _source_snapshot(source)
    gate_payload: JsonDict = {
        "schema": "prompt_control_lab.public_posttrain_gate_decisions.v1",
        "decision": public_summary["decision"],
        "gate_count": len(gate_rows),
        "gates": gate_rows,
        "claim_boundary": (
            "These rows preserve configured gate observations and decisions. They do not prove "
            "a hidden causal training mechanism or universal checkpoint quality."
        ),
    }
    report = _render_report(public_summary, checkpoint_rows, gate_rows)

    _assert_portable(public_summary, source_root=run)
    _assert_portable(provenance, source_root=run)
    _assert_portable(gate_payload, source_root=run)
    _assert_portable(checkpoint_rows, source_root=run)
    _assert_portable(report, source_root=run)

    artifact_manifest = _publish_export(
        out,
        public_summary=public_summary,
        provenance=provenance,
        gate_payload=gate_payload,
        checkpoint_rows=checkpoint_rows,
        report=report,
    )
    return {
        "schema": "prompt_control_lab.posttrain_pilot_export_result.v1",
        "decision": public_summary["decision"],
        "checkpoint_rows": len(checkpoint_rows),
        "gate_rows": len(gate_rows),
        "output_dir": str(out),
        "source_snapshot_sha256": provenance["source_snapshot_sha256"],
        "artifact_count": artifact_manifest["artifact_count"],
    }


def _validated_seeds(summary: JsonDict) -> tuple[int, ...]:
    raw = summary.get("seeds")
    if (
        not isinstance(raw, list)
        or not raw
        or any(not isinstance(seed, int) or isinstance(seed, bool) for seed in raw)
        or len(set(raw)) != len(raw)
    ):
        raise ValueError("Pilot summary must contain unique integer seeds")
    return tuple(raw)


def _validate_complete_summary(summary: JsonDict, *, seeds: tuple[int, ...]) -> None:
    missing_gates = summary.get("missing_gates")
    missing_checkpoints = summary.get("missing_checkpoints")
    if missing_gates or missing_checkpoints:
        raise ValueError("Pilot summary is incomplete; missing checkpoint or gate evidence remains")
    expected_checkpoints = len(seeds) * len(_STAGES)
    expected_gates = len(seeds) * len(_GATE_STAGES)
    if summary.get("checkpoint_run_count") != expected_checkpoints:
        raise ValueError("Pilot summary checkpoint count does not match its seed set")
    if summary.get("gate_count") != expected_gates:
        raise ValueError("Pilot summary gate count does not match its seed set")


def _checkpoint_rows(
    run: Path,
    *,
    seeds: tuple[int, ...],
    source: _SourceSnapshot,
    provenance: JsonDict,
) -> list[JsonDict]:
    rows: list[JsonDict] = []
    checkpoint_ids: set[str] = set()
    for seed in seeds:
        for stage in _STAGES:
            checkpoint = run / f"seed-{seed}" / f"checkpoint-{stage}"
            manifest = source.read(checkpoint / "manifest.json")
            metrics = source.read(checkpoint / "metrics.json")
            stats = _first_comparison(source.read(checkpoint / "stats.json"))
            checkpoint_identity = _mapping(manifest.get("checkpoint"))
            checkpoint_id = _validate_checkpoint_identity(
                checkpoint_identity,
                seed=seed,
                stage=stage,
                provenance=provenance,
            )
            if checkpoint_id in checkpoint_ids:
                raise ValueError(f"Duplicate checkpoint id: {checkpoint_id}")
            checkpoint_ids.add(checkpoint_id)
            slices = _mapping(metrics.get("by_slice"))
            diagnostics = checkpoint / "diagnostics"
            row: JsonDict = {
                "seed": seed,
                "stage": stage,
                "checkpoint_id": checkpoint_id,
                "mean_score": _required_number(metrics.get("mean_score"), "mean_score"),
                "gsm8k_score": _required_number(slices.get("gsm8k"), "by_slice.gsm8k"),
                "format_following_score": _required_number(
                    slices.get("format_following"), "by_slice.format_following"
                ),
                "mean_tokens": _required_number(metrics.get("mean_tokens"), "mean_tokens"),
                "mean_latency_ms": _required_number(
                    metrics.get("mean_latency_ms"), "mean_latency_ms"
                ),
                "generation_saturation_rate": _required_number(
                    metrics.get("generation_saturation_rate"), "generation_saturation_rate"
                ),
                "mean_delta": _required_number(stats.get("mean_delta"), "stats.mean_delta"),
                "ci_lower": _required_interval_value(stats.get("bootstrap_ci"), 0),
                "ci_upper": _required_interval_value(stats.get("bootstrap_ci"), 1),
                "permutation_p_value": _required_number(
                    stats.get("permutation_p_value"), "stats.permutation_p_value"
                ),
                "holm_adjusted_p_value": _required_number(
                    stats.get("holm_adjusted_p_value"), "stats.holm_adjusted_p_value"
                ),
                "trajectory_drift": _diagnostic_number(
                    diagnostics / "trajectory.json", "mean_step_drift", source
                ),
                "generation_mismatch": _diagnostic_number(
                    diagnostics / "generation_mismatch.json", "gap", source
                ),
                "selective_aurc": _diagnostic_number(
                    diagnostics / "selective_risk.json", "observed_aurc", source
                ),
                "reachability_shift": _diagnostic_number(
                    diagnostics / "prompt_reachability.json",
                    "representation_shift_l2_normalized",
                    source,
                ),
                "readout_alignment_gap": _diagnostic_number(
                    diagnostics / "readout_alignment.json", "alignment_gap", source
                ),
                "prompt_stability_drift": _diagnostic_number(
                    diagnostics / "prompt_stability.json", "mean_step_drift", source
                ),
                "routing_status": _diagnostic_text(
                    diagnostics / "prompt_routing.json",
                    "evidence_status",
                    source,
                    allowed={"insufficient_evidence", "observed"},
                ),
                "projection_status": _diagnostic_text(
                    diagnostics / "prompt_projection.json",
                    "applicability",
                    source,
                    allowed={"not_applicable", "applicable"},
                ),
            }
            rows.append(row)
    return rows


def _gate_rows(
    run: Path,
    *,
    seeds: tuple[int, ...],
    source: _SourceSnapshot,
    checkpoint_rows: list[JsonDict],
) -> list[JsonDict]:
    rows: list[JsonDict] = []
    checkpoint_index = {
        (int(row["seed"]), str(row["stage"])): row for row in checkpoint_rows
    }
    for seed in seeds:
        for stage in _GATE_STAGES:
            gate_dir = run / f"seed-{seed}" / "gates" / f"initial-to-{stage}"
            gate = source.read(gate_dir / "posttrain_gate.json")
            comparison = source.read(gate_dir / "checkpoint_comparison.json")
            trace = source.read(gate_dir / "decision_trace.json")
            baseline = checkpoint_index[(seed, "initial")]
            candidate = checkpoint_index[(seed, stage)]
            decision = _decision(gate.get("decision"), "gate decision")
            trace_decision = _decision(trace.get("decision"), "trace decision")
            if trace_decision != decision:
                raise ValueError(f"Gate and decision trace disagree for seed {seed} {stage}")
            _require_equal(
                comparison.get("baseline_checkpoint"),
                baseline["checkpoint_id"],
                f"seed {seed} {stage} baseline checkpoint",
            )
            _require_equal(
                comparison.get("candidate_checkpoint"),
                candidate["checkpoint_id"],
                f"seed {seed} {stage} candidate checkpoint",
            )
            score_delta = _required_number(comparison.get("score_delta"), "score_delta")
            expected_delta = float(candidate["mean_score"]) - float(baseline["mean_score"])
            if not math.isclose(score_delta, expected_delta, abs_tol=1e-9):
                raise ValueError(
                    f"Gate score_delta disagrees with checkpoint metrics for seed {seed}"
                )
            triggered: list[JsonDict] = []
            raw_checks = trace.get("checks")
            if not isinstance(raw_checks, list):
                raise ValueError("decision trace checks must be a list")
            for raw in raw_checks:
                if not isinstance(raw, dict):
                    raise ValueError("decision trace check entries must be objects")
                check = str(raw.get("check", ""))
                if check not in _PUBLIC_CHECKS:
                    raise ValueError(f"Unsupported public gate check: {check}")
                status = str(raw.get("status", ""))
                if status not in {"triggered", "passed", "not_applicable"}:
                    raise ValueError(f"Unsupported decision trace check status: {status}")
                if status != "triggered":
                    continue
                triggered.append(
                    {
                        "check": check,
                        "status": "triggered",
                        "impact": _impact(raw.get("impact")),
                        "observed": _bounded_observation(raw.get("observed")),
                        "threshold": _bounded_observation(raw.get("threshold")),
                    }
                )
            if decision == "hold" and not any(
                item["impact"] == "hold" for item in triggered
            ):
                raise ValueError("hold decision requires a triggered hold-impact check")
            rows.append(
                {
                    "seed": seed,
                    "stage": stage,
                    "decision": decision,
                    "score_delta": score_delta,
                    "missing_artifact_count": _list_length(gate.get("missing_artifacts")),
                    "invalid_evidence_count": _list_length(gate.get("invalid_evidence")),
                    "triggered_checks": triggered,
                }
            )
    return rows


def _portable_provenance(
    source: _SourceSnapshot,
    *,
    seeds: tuple[int, ...],
) -> JsonDict:
    manifest = source.read(source.root / "parallel_execution_manifest.json")
    assignments: list[JsonDict] = []
    shards = manifest.get("shards")
    if isinstance(shards, list):
        for raw in shards:
            if not isinstance(raw, dict):
                continue
            seed = raw.get("seed")
            gpu = raw.get("gpu")
            if seed in seeds and isinstance(gpu, int) and not isinstance(gpu, bool):
                assignments.append({"seed": seed, "gpu": gpu})
    assignments.sort(key=lambda item: int(item["seed"]))
    if [item["seed"] for item in assignments] != list(seeds):
        raise ValueError("Execution manifest does not contain one GPU assignment per seed")
    attempts: list[JsonDict] = []
    raw_attempts = manifest.get("preserved_attempts")
    if isinstance(raw_attempts, list):
        for raw in raw_attempts:
            if not isinstance(raw, dict):
                raise ValueError("Execution attempt provenance must contain objects")
            reason = str(raw.get("reason", ""))
            if reason not in _PUBLIC_ATTEMPT_REASONS:
                raise ValueError(f"Unsupported public attempt reason: {reason}")
            attempts.append({"reason": reason})
    telemetry = _mapping(manifest.get("seed_2_gpu_telemetry"))
    raw_model = _mapping(manifest.get("model"))
    model: JsonDict = {
        "id": _safe_identifier(raw_model.get("id"), "model.id"),
        "revision": _safe_identifier(raw_model.get("revision"), "model.revision"),
        "snapshot_sha256": _required_hash(
            raw_model.get("snapshot_sha256"), "model.snapshot_sha256"
        ),
    }
    runtime_versions = _public_runtime_versions(manifest.get("runtime_versions"))
    return {
        "schema": "prompt_control_lab.public_posttrain_provenance.v1",
        "execution_source_commit": _required_commit(
            manifest.get("execution_source_commit"), "execution_source_commit"
        ),
        "gate_reporting_source_commit": _required_commit(
            manifest.get("gate_reporting_source_commit"), "gate_reporting_source_commit"
        ),
        "execution_wheel_sha256": _required_hash(
            _mapping(manifest.get("execution_wheel")).get("sha256"),
            "execution_wheel.sha256",
        ),
        "gate_reporting_wheel_sha256": _required_hash(
            _mapping(manifest.get("gate_reporting_wheel")).get("sha256"),
            "gate_reporting_wheel.sha256",
        ),
        "model": model,
        "split_sha256": _required_hash(manifest.get("split_sha256"), "split_sha256"),
        "runtime_versions": runtime_versions,
        "seed_gpu_assignments": assignments,
        "preserved_attempts": attempts,
        "seed_2_gpu_telemetry": _public_telemetry(telemetry),
        "claim_boundary": (
            "Recorded execution provenance does not establish a causal model mechanism."
        ),
    }


def _public_summary(
    summary: JsonDict,
    *,
    seeds: tuple[int, ...],
    checkpoint_rows: list[JsonDict],
    gate_rows: list[JsonDict],
) -> JsonDict:
    decision = _aggregate_decisions([str(row["decision"]) for row in gate_rows])
    if summary.get("decision") != decision:
        raise ValueError("Pilot summary decision disagrees with the conservative gate aggregation")
    stage_decisions = {
        stage: _aggregate_decisions(
            [str(row["decision"]) for row in gate_rows if row["stage"] == stage]
        )
        for stage in _GATE_STAGES
    }
    if _mapping(summary.get("stage_decisions")) != stage_decisions:
        raise ValueError("Pilot summary stage decisions disagree with gate artifacts")
    metric_keys = (
        "mean_score",
        "mean_tokens",
        "mean_latency_ms",
        "generation_saturation_rate",
        "trajectory_drift",
        "generation_mismatch",
        "selective_aurc",
        "reachability_shift",
        "readout_alignment_gap",
        "prompt_stability_drift",
    )
    metrics_by_stage: JsonDict = {}
    for stage in _STAGES:
        stage_rows = [row for row in checkpoint_rows if row["stage"] == stage]
        metrics_by_stage[stage] = {
            key: _aggregate_numbers([float(row[key]) for row in stage_rows])
            for key in metric_keys
        }
        metrics_by_stage[stage]["routing_status_counts"] = _count_values(
            [str(row["routing_status"]) for row in stage_rows]
        )
        metrics_by_stage[stage]["projection_status_counts"] = _count_values(
            [str(row["projection_status"]) for row in stage_rows]
        )
    score_delta_by_stage = {
        stage: _aggregate_numbers(
            [float(row["score_delta"]) for row in gate_rows if row["stage"] == stage]
        )
        for stage in _GATE_STAGES
    }
    return {
        "schema": "prompt_control_lab.public_posttrain_pilot_summary.v1",
        "decision": decision,
        "seeds": list(seeds),
        "planned_checkpoint_run_count": len(seeds) * len(_STAGES),
        "checkpoint_run_count": len(checkpoint_rows),
        "gate_count": len(gate_rows),
        "stage_decisions": stage_decisions,
        "score_delta_by_stage": score_delta_by_stage,
        "checkpoint_metrics_by_stage": metrics_by_stage,
        "missing_gates": [],
        "missing_checkpoints": [],
        "claim_boundary": (
            "This summary conservatively aggregates observed checkpoint evidence across seeds. "
            "It does not establish a causal training mechanism."
        ),
    }


def _source_snapshot(source: _SourceSnapshot) -> str:
    rows = []
    for path in sorted(source.hashes, key=lambda item: item.as_posix()):
        rows.append(
            {
                "path": path.relative_to(source.root).as_posix(),
                "sha256": source.hashes[path],
            }
        )
    return f"sha256:{stable_digest(rows)}"


def _write_checkpoint_csv(path: Path, rows: list[JsonDict]) -> None:
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_artifact_manifest(out: Path) -> JsonDict:
    artifacts = []
    for path in sorted(item for item in out.iterdir() if item.is_file()):
        artifacts.append(
            {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    payload: JsonDict = {
        "schema": "prompt_control_lab.public_posttrain_artifact_manifest.v1",
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "excluded": [
            "raw prompts",
            "predictions.jsonl",
            "dataset records",
            "model weights",
            "LoRA adapters",
            "trainer state",
            "absolute source paths",
        ],
    }
    _write_lf_json(out / "artifact_manifest.json", payload)
    return payload


def _publish_export(
    out: Path,
    *,
    public_summary: JsonDict,
    provenance: JsonDict,
    gate_payload: JsonDict,
    checkpoint_rows: list[JsonDict],
    report: str,
) -> JsonDict:
    ensure_dir(out.parent)
    temporary = Path(tempfile.mkdtemp(prefix=f".{out.name}.tmp-", dir=out.parent))
    try:
        _write_lf_json(temporary / "pilot_summary.json", public_summary)
        _write_lf_json(temporary / "provenance.json", provenance)
        _write_lf_json(temporary / "gate_decisions.json", gate_payload)
        _write_checkpoint_csv(temporary / "checkpoint_metrics.csv", checkpoint_rows)
        (temporary / "report.md").write_bytes(report.encode("utf-8"))
        artifact_manifest = _write_artifact_manifest(temporary)
        temporary.replace(out)
        return artifact_manifest
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _write_lf_json(path: Path, value: JsonDict) -> None:
    payload = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path.write_bytes(payload.encode("utf-8"))


def _render_report(
    summary: JsonDict,
    checkpoint_rows: list[JsonDict],
    gate_rows: list[JsonDict],
) -> str:
    lines = [
        "# Controlled SFT checkpoint pilot",
        "",
        f"- Conservative decision: `{summary.get('decision')}`",
        f"- Seeds: `{summary.get('seeds')}`",
        f"- Checkpoint runs: `{summary.get('checkpoint_run_count')}`",
        f"- Gates: `{summary.get('gate_count')}`",
        "",
        "| Seed | Stage | Score | GSM8K | Format | Mean tokens | Saturation |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for row in checkpoint_rows:
        lines.append(
            f"| {row['seed']} | {row['stage']} | {_display(row['mean_score'])} | "
            f"{_display(row['gsm8k_score'])} | {_display(row['format_following_score'])} | "
            f"{_display(row['mean_tokens'])} | {_display(row['generation_saturation_rate'])} |"
        )
    lines.extend(
        [
            "",
            "## Gate decisions",
            "",
            "| Seed | Stage | Decision | Score delta | Triggered checks |",
            "|---:|---|---|---:|---|",
        ]
    )
    for row in gate_rows:
        names = ", ".join(
            str(check.get("check"))
            for check in row["triggered_checks"]
            if isinstance(check, dict)
        )
        lines.append(
            f"| {row['seed']} | {row['stage']} | {row['decision']} | "
            f"{_display(row['score_delta'])} | {names} |"
        )
    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            str(summary.get("claim_boundary")),
            "",
            "This export contains aggregate evidence only. It excludes raw prompts, per-example "
            "predictions, dataset records, weights, adapters, trainer state, and absolute paths.",
            "",
        ]
    )
    return "\n".join(lines)


def _validate_checkpoint_identity(
    identity: JsonDict,
    *,
    seed: int,
    stage: str,
    provenance: JsonDict,
) -> str:
    checkpoint_id = _safe_identifier(identity.get("id"), "checkpoint.id")
    _require_equal(checkpoint_id, f"seed-{seed}-{stage}", "checkpoint.id")
    _require_equal(identity.get("seed"), seed, "checkpoint.seed")
    model = _mapping(provenance.get("model"))
    _require_equal(identity.get("model_id"), model.get("id"), "checkpoint.model_id")
    _require_equal(
        identity.get("model_revision"), model.get("revision"), "checkpoint.model_revision"
    )
    _require_equal(
        identity.get("model_snapshot_sha256"),
        model.get("snapshot_sha256"),
        "checkpoint.model_snapshot_sha256",
    )
    _require_equal(identity.get("split_hash"), provenance.get("split_sha256"), "split_hash")
    _require_equal(identity.get("provider"), "huggingface-local", "checkpoint.provider")
    _require_equal(identity.get("training_method"), "sft_lora", "checkpoint.training_method")
    return checkpoint_id


def _diagnostic_number(path: Path, key: str, source: _SourceSnapshot) -> float:
    return _required_number(source.read(path).get(key), f"{path.name}.{key}")


def _diagnostic_text(
    path: Path,
    key: str,
    source: _SourceSnapshot,
    *,
    allowed: set[str],
) -> str:
    value = str(source.read(path).get(key, ""))
    if value not in allowed:
        raise ValueError(f"Unsupported {path.name}.{key}: {value}")
    return value


def _first_comparison(stats: JsonDict) -> JsonDict:
    comparisons = stats.get("comparisons")
    if isinstance(comparisons, list) and comparisons and isinstance(comparisons[0], dict):
        return comparisons[0]
    return stats


def _required_interval_value(value: object, index: int) -> float:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("stats.bootstrap_ci must contain exactly two finite numbers")
    return _required_number(value[index], "stats.bootstrap_ci")


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Public post-training evidence must contain finite numbers")
    return number


def _required_number(value: object, field_name: str) -> float:
    number = _number(value)
    if number is None:
        raise ValueError(f"{field_name} must be a finite number")
    return number


def _mapping(value: object) -> JsonDict:
    return value if isinstance(value, dict) else {}


def _list_length(value: object) -> int:
    if not isinstance(value, list):
        raise ValueError("Expected an artifact list in the post-training gate")
    return len(value)


def _decision(value: object, field_name: str) -> str:
    text = str(value)
    if text not in _DECISION_PRIORITY:
        raise ValueError(f"Unsupported {field_name}: {text}")
    return text


def _impact(value: object) -> str:
    text = str(value)
    if text not in {"none", "needs_review", "insufficient_evidence", "hold"}:
        raise ValueError(f"Unsupported public gate impact: {text}")
    return text


def _bounded_observation(value: object) -> object:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return _required_number(value, "gate observation")
    if isinstance(value, list | dict):
        return {"item_count": len(value)}
    text = str(value)
    aliases = {
        "not_applicable": "not_applicable",
        "insufficient_evidence": "insufficient_evidence",
        "observed intervention evidence": "observed_intervention_required",
    }
    if text not in aliases:
        raise ValueError("Unsupported free text in an allowlisted gate observation")
    return aliases[text]


def _aggregate_decisions(decisions: list[str]) -> str:
    if not decisions:
        raise ValueError("Cannot aggregate an empty set of checkpoint decisions")
    return max(decisions, key=lambda item: _DECISION_PRIORITY[_decision(item, "decision")])


def _aggregate_numbers(values: list[float]) -> JsonDict:
    if not values:
        raise ValueError("Cannot aggregate an empty numeric checkpoint series")
    return {
        "count": len(values),
        "mean": round(sum(values) / len(values), 12),
        "min": min(values),
        "max": max(values),
    }


def _count_values(values: list[str]) -> JsonDict:
    return {value: values.count(value) for value in sorted(set(values))}


def _safe_identifier(value: object, field_name: str) -> str:
    text = str(value or "")
    if (
        not _IDENTIFIER_PATTERN.fullmatch(text)
        or _ABSOLUTE_PATH_PATTERN.search(text)
        or _SECRET_PATTERN.search(text)
    ):
        raise ValueError(f"{field_name} contains an unsafe public value")
    return text


def _required_hash(value: object, field_name: str) -> str:
    text = str(value or "")
    if not _HASH_PATTERN.fullmatch(text):
        raise ValueError(f"{field_name} must be a SHA-256 value")
    return text


def _required_commit(value: object, field_name: str) -> str:
    text = str(value or "")
    if not _COMMIT_PATTERN.fullmatch(text):
        raise ValueError(f"{field_name} must be a hexadecimal commit id")
    return text


def _public_runtime_versions(value: object) -> JsonDict:
    raw = _mapping(value)
    allowed = {
        "accelerate",
        "datasets",
        "numpy",
        "peft",
        "promptcontrollab",
        "python",
        "scipy",
        "torch",
        "transformers",
    }
    output: JsonDict = {}
    for key in sorted(raw):
        if key not in allowed:
            continue
        version = str(raw[key])
        if not _VERSION_PATTERN.fullmatch(version) or _SECRET_PATTERN.search(version):
            raise ValueError(f"runtime_versions.{key} contains an unsafe public value")
        output[key] = version
    return output


def _public_telemetry(telemetry: JsonDict) -> JsonDict:
    output: JsonDict = {}
    for key in ("sample_count", "peak_memory_used_mib", "mean_utilization_percent"):
        if key in telemetry:
            output[key] = _required_number(telemetry[key], f"seed_2_gpu_telemetry.{key}")
    for key in ("first_observed_at", "last_observed_at"):
        if key in telemetry:
            output[key] = _safe_identifier(telemetry[key], f"seed_2_gpu_telemetry.{key}")
    return output


def _require_equal(observed: object, expected: object, field_name: str) -> None:
    if observed != expected:
        raise ValueError(f"{field_name} is inconsistent across the controlled pilot")


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _sha256_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _assert_portable(value: object, *, source_root: Path) -> None:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    if (
        str(source_root) in text
        or source_root.as_posix() in text
        or _ABSOLUTE_PATH_PATTERN.search(text)
        or _SECRET_PATTERN.search(text)
    ):
        raise ValueError("Post-training public export contains an absolute source path")


def _display(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    return "" if value is None else str(value)
