from __future__ import annotations

import csv
import hashlib
import json
import statistics
from pathlib import Path

import pytest

from promptcontrollab.cli import main
from promptcontrollab.files import read_json
from promptcontrollab.posttrain_export import export_posttrain_pilot

ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_complete_run(root: Path) -> None:
    stages = ("initial", "mid", "final")
    for stage_index, stage in enumerate(stages):
        checkpoint = root / "seed-0" / f"checkpoint-{stage}"
        _write_json(
            checkpoint / "manifest.json",
            {
                "checkpoint": {
                    "id": f"seed-0-{stage}",
                    "model_id": "Qwen/Qwen2.5-0.5B-Instruct",
                    "model_revision": "pinned-revision",
                    "model_snapshot_sha256": "sha256:" + "a" * 64,
                    "split_hash": "sha256:" + "b" * 64,
                    "seed": 0,
                    "provider": "huggingface-local",
                    "training_method": "sft_lora",
                }
            },
        )
        _write_json(
            checkpoint / "metrics.json",
            {
                "mean_score": 0.1 + stage_index * 0.1,
                "by_slice": {"gsm8k": 0.2 + stage_index * 0.1, "format_following": 0.0},
                "mean_tokens": 120 - stage_index * 10,
                "mean_latency_ms": 9000 - stage_index * 1000,
                "generation_saturation_rate": 0.9 - stage_index * 0.2,
            },
        )
        _write_json(
            checkpoint / "stats.json",
            {
                "comparisons": [
                    {
                        "mean_delta": stage_index * 0.1,
                        "bootstrap_ci": [stage_index * 0.05, stage_index * 0.15],
                        "permutation_p_value": 1.0 if stage == "initial" else 0.01,
                        "holm_adjusted_p_value": 1.0 if stage == "initial" else 0.02,
                    }
                ]
            },
        )
        diagnostics = checkpoint / "diagnostics"
        _write_json(diagnostics / "trajectory.json", {"mean_step_drift": 1.0 + stage_index})
        _write_json(diagnostics / "generation_mismatch.json", {"gap": 0.5 - 0.1 * stage_index})
        _write_json(diagnostics / "selective_risk.json", {"observed_aurc": 0.8 - 0.1 * stage_index})
        _write_json(
            diagnostics / "prompt_reachability.json",
            {"representation_shift_l2_normalized": float(stage_index)},
        )
        _write_json(diagnostics / "readout_alignment.json", {"alignment_gap": 0.5})
        _write_json(diagnostics / "prompt_stability.json", {"mean_step_drift": 1.0})
        _write_json(
            diagnostics / "prompt_routing.json",
            {"evidence_status": "insufficient_evidence"},
        )
        _write_json(
            diagnostics / "prompt_projection.json",
            {"applicability": "not_applicable"},
        )
    for stage in ("mid", "final"):
        gate = root / "seed-0" / "gates" / f"initial-to-{stage}"
        _write_json(
            gate / "posttrain_gate.json",
            {
                "decision": "hold",
                "baseline": str((root / "seed-0/checkpoint-initial").resolve()),
                "candidate": str((root / f"seed-0/checkpoint-{stage}").resolve()),
                "missing_artifacts": [],
                "invalid_evidence": ["candidate:generation_saturation_rate"],
                "checks": {
                    "task_score": {"passed": True, "severity": "info", "observed": 0.1},
                    "trajectory_stability": {
                        "passed": False,
                        "severity": "fail",
                        "increase": 0.2,
                        "threshold": 0.05,
                        "message": "Trajectory drift increased.",
                    },
                },
                "claim_boundary": "Observed checkpoint association, not a causal proof.",
            },
        )
        _write_json(
            gate / "checkpoint_comparison.json",
            {
                "baseline_checkpoint": "seed-0-initial",
                "candidate_checkpoint": f"seed-0-{stage}",
                "score_delta": 0.1 if stage == "mid" else 0.2,
            },
        )
        _write_json(
            gate / "decision_trace.json",
            {
                "decision": "hold",
                "checks": [
                    {
                        "check": "trajectory_stability",
                        "status": "triggered",
                        "impact": "hold",
                        "observed": 0.2,
                        "threshold": 0.05,
                    }
                ]
            },
        )
    _write_json(
        root / "pilot_summary.json",
        {
            "schema": "prompt_control_lab.posttrain_sft_pilot_summary.v1",
            "decision": "hold",
            "seeds": [0],
            "planned_checkpoint_run_count": 3,
            "checkpoint_run_count": 3,
            "gate_count": 2,
            "stage_decisions": {"mid": "hold", "final": "hold"},
            "score_delta_by_stage": {
                "mid": {"count": 1, "mean": 0.1, "min": 0.1, "max": 0.1},
                "final": {"count": 1, "mean": 0.2, "min": 0.2, "max": 0.2},
            },
            "checkpoint_metrics_by_stage": {},
            "gates": [],
            "missing_gates": [],
            "missing_checkpoints": [],
            "claim_boundary": "Observed checkpoint evidence, not a causal proof.",
        },
    )
    _write_json(
        root / "parallel_execution_manifest.json",
        {
            "execution_source_commit": "1" * 40,
            "gate_reporting_source_commit": "2" * 40,
            "execution_wheel": {"sha256": "sha256:" + "c" * 64},
            "gate_reporting_wheel": {"sha256": "sha256:" + "d" * 64},
            "model": {
                "id": "Qwen/Qwen2.5-0.5B-Instruct",
                "revision": "pinned-revision",
                "snapshot_sha256": "sha256:" + "a" * 64,
                "cache_path": "/mnt/private/model-cache",
            },
            "split_sha256": "sha256:" + "b" * 64,
            "runtime_versions": {"torch": "2.4.1", "promptcontrollab": "0.2.0a1"},
            "shards": [{"seed": 0, "gpu": 1, "source_dir": str(root.resolve())}],
            "preserved_attempts": [{"path": "/root/private/attempt", "reason": "oom"}],
            "claim_boundary": "Execution provenance only.",
        },
    )


def _replace_model_id(root: Path, model_id: str) -> None:
    execution = read_json(root / "parallel_execution_manifest.json")
    execution["model"]["id"] = model_id
    _write_json(root / "parallel_execution_manifest.json", execution)
    for stage in ("initial", "mid", "final"):
        path = root / "seed-0" / f"checkpoint-{stage}" / "manifest.json"
        manifest = read_json(path)
        manifest["checkpoint"]["model_id"] = model_id
        _write_json(path, manifest)


def test_export_posttrain_pilot_writes_portable_aggregate_only(tmp_path: Path) -> None:
    run = tmp_path / "private-run"
    _write_complete_run(run)
    out = tmp_path / "public-case"

    payload = export_posttrain_pilot(run_dir=run, out_dir=out)

    assert payload["decision"] == "hold"
    assert payload["checkpoint_rows"] == 3
    assert payload["gate_rows"] == 2
    rows = list(csv.DictReader((out / "checkpoint_metrics.csv").open(encoding="utf-8")))
    assert [row["stage"] for row in rows] == ["initial", "mid", "final"]
    decisions = read_json(out / "gate_decisions.json")
    assert decisions["gates"][0]["triggered_checks"][0]["check"] == "trajectory_stability"
    assert all(
        "next_action" not in check
        for gate in decisions["gates"]
        for check in gate["triggered_checks"]
    )
    provenance = read_json(out / "provenance.json")
    assert provenance["model"]["revision"] == "pinned-revision"
    assert "cache_path" not in provenance["model"]
    assert provenance["seed_gpu_assignments"] == [{"gpu": 1, "seed": 0}]
    persisted = "\n".join(
        path.read_text(encoding="utf-8")
        for path in out.iterdir()
        if path.suffix in {".json", ".csv", ".md"}
    )
    assert str(run.resolve()) not in persisted
    assert "/root/" not in persisted
    assert "private/attempt" not in persisted
    assert not list(out.rglob("predictions.jsonl"))
    manifest = read_json(out / "artifact_manifest.json")
    for row in manifest["artifacts"]:
        path = out / row["path"]
        assert row["sha256"] == f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"
        assert b"\r\n" not in path.read_bytes()


def test_posttrain_pilot_export_cli_and_incomplete_run_failure(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _write_complete_run(run)
    out = tmp_path / "out"

    assert main(["posttrain-pilot-export", "--run", str(run), "--out", str(out)]) == 0
    summary = read_json(run / "pilot_summary.json")
    summary["missing_gates"] = ["seed-0/gates/initial-to-final"]
    _write_json(run / "pilot_summary.json", summary)

    assert (
        main(
            [
                "posttrain-pilot-export",
                "--run",
                str(run),
                "--out",
                str(tmp_path / "incomplete"),
            ]
        )
        == 2
    )
    assert not (tmp_path / "incomplete").exists()


@pytest.mark.parametrize(
    "unsafe_model_id",
    [
        r"\\private-server\models\qwen",
        "file:///private/model",
        "sk-secret-model-token",
        "ghp_" + "a" * 36,
        "github_pat_" + "a" * 30,
        "AKIA" + "A" * 16,
        "AIza" + "a" * 30,
        "xoxb-" + "a" * 24,
    ],
)
def test_export_rejects_unsafe_allowlisted_provenance(
    tmp_path: Path,
    unsafe_model_id: str,
) -> None:
    run = tmp_path / "run"
    _write_complete_run(run)
    _replace_model_id(run, unsafe_model_id)
    out = tmp_path / "out"

    with pytest.raises(ValueError, match="unsafe public value"):
        export_posttrain_pilot(run_dir=run, out_dir=out)

    assert not out.exists()


def test_export_rejects_mixed_split_summary_conflict_and_non_finite_metrics(
    tmp_path: Path,
) -> None:
    mixed = tmp_path / "mixed"
    _write_complete_run(mixed)
    manifest_path = mixed / "seed-0/checkpoint-final/manifest.json"
    manifest = read_json(manifest_path)
    manifest["checkpoint"]["split_hash"] = "sha256:" + "e" * 64
    _write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="split_hash"):
        export_posttrain_pilot(run_dir=mixed, out_dir=tmp_path / "mixed-out")

    conflict = tmp_path / "conflict"
    _write_complete_run(conflict)
    summary_path = conflict / "pilot_summary.json"
    summary = read_json(summary_path)
    summary["decision"] = "pass"
    _write_json(summary_path, summary)
    with pytest.raises(ValueError, match="summary decision"):
        export_posttrain_pilot(run_dir=conflict, out_dir=tmp_path / "conflict-out")

    non_finite = tmp_path / "non-finite"
    _write_complete_run(non_finite)
    metrics_path = non_finite / "seed-0/checkpoint-final/metrics.json"
    metrics = read_json(metrics_path)
    metrics["mean_score"] = float("nan")
    _write_json(metrics_path, metrics)
    with pytest.raises(ValueError, match="finite"):
        export_posttrain_pilot(run_dir=non_finite, out_dir=tmp_path / "non-finite-out")


def test_export_rejects_malformed_decision_trace_checks(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _write_complete_run(run)
    trace_path = run / "seed-0/gates/initial-to-final/decision_trace.json"
    trace = read_json(trace_path)
    trace["checks"] = {"trajectory_stability": "triggered"}
    _write_json(trace_path, trace)

    with pytest.raises(ValueError, match="decision trace checks must be a list"):
        export_posttrain_pilot(run_dir=run, out_dir=tmp_path / "out")


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("missing_decision", "trace decision"),
        ("non_object_check", "check entries must be objects"),
        ("unknown_status", "check status"),
        ("hold_without_hold_impact", "hold-impact check"),
    ],
)
def test_export_rejects_incomplete_decision_explanations(
    tmp_path: Path,
    mutation: str,
    error: str,
) -> None:
    run = tmp_path / mutation
    _write_complete_run(run)
    trace_path = run / "seed-0/gates/initial-to-final/decision_trace.json"
    trace = read_json(trace_path)
    if mutation == "missing_decision":
        trace.pop("decision")
    elif mutation == "non_object_check":
        trace["checks"] = ["trajectory_stability"]
    elif mutation == "unknown_status":
        trace["checks"][0]["status"] = "trigered"
    else:
        trace["checks"][0]["impact"] = "needs_review"
    _write_json(trace_path, trace)

    with pytest.raises(ValueError, match=error):
        export_posttrain_pilot(run_dir=run, out_dir=tmp_path / f"{mutation}-out")


def test_committed_checkpoint_case_is_complete_bounded_and_path_free() -> None:
    case = ROOT / "docs/case_studies/sft_checkpoint_pilot"
    rows = list(csv.DictReader((case / "checkpoint_metrics.csv").open(encoding="utf-8")))
    summary = read_json(case / "pilot_summary.json")
    gates = read_json(case / "gate_decisions.json")
    provenance = read_json(case / "provenance.json")
    manifest = read_json(case / "artifact_manifest.json")

    assert len(rows) == 9
    assert summary["decision"] == "hold"
    assert summary["checkpoint_run_count"] == 9
    assert gates["gate_count"] == 6
    assert all(row["decision"] == "hold" for row in gates["gates"])
    initial = [float(row["mean_score"]) for row in rows if row["stage"] == "initial"]
    final = [float(row["mean_score"]) for row in rows if row["stage"] == "final"]
    assert statistics.fmean(initial) == pytest.approx(0.088541666667)
    assert statistics.fmean(final) == pytest.approx(0.194444444444)
    assert all(float(row["format_following_score"]) == 0.0 for row in rows)
    assert provenance["model"]["revision"] == "7ae557604adf67be50417f59c2c2f167def9a775"
    assert provenance["source_snapshot_sha256"].startswith("sha256:")
    assert (case / "README.md").is_file()
    assert (case / "README.zh.md").is_file()
    assert (case / "checkpoint_decision.svg").is_file()
    assert (case / "checkpoint_decision.zh.svg").is_file()

    persisted = "\n".join(
        path.read_text(encoding="utf-8")
        for path in case.iterdir()
        if path.suffix in {".json", ".csv", ".md", ".svg"}
    )
    assert "/root/" not in persisted
    assert "sft-pilot-safe-extract" not in persisted
    assert "D:\\" not in persisted
    assert not list(case.rglob("predictions.jsonl"))
    assert not list(case.rglob("*.pt"))
    assert not list(case.rglob("*.safetensors"))
    for row in manifest["artifacts"]:
        path = case / row["path"]
        assert row["sha256"] == f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"

    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "docs/case_studies/sft_checkpoint_pilot/*.json text eol=lf" in attributes
    assert "docs/case_studies/sft_checkpoint_pilot/*.csv text eol=lf" in attributes
