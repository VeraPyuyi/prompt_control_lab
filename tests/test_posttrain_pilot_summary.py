from __future__ import annotations

import json
from pathlib import Path

from promptcontrollab.posttrain_pilot_summary import write_pilot_summary


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_gate(root: Path, seed: int, stage: str, decision: str, delta: float) -> None:
    gate_dir = root / f"seed-{seed}" / "gates" / f"initial-to-{stage}"
    _write_json(
        gate_dir / "posttrain_gate.json",
        {
            "decision": decision,
            "capability_profile": "full-open-model",
            "plain_summary": f"{stage} is {decision}",
        },
    )
    _write_json(
        gate_dir / "checkpoint_comparison.json",
        {"score_delta": delta, "slice_deltas": {"gsm8k": delta}},
    )
    _write_json(
        gate_dir / "decision_trace.json",
        {
            "checks": [
                {
                    "check": "task_score",
                    "status": "passed" if decision == "pass" else "triggered",
                    "impact": decision,
                }
            ]
        },
    )


def _write_checkpoint(root: Path, seed: int, stage: str, score: float) -> None:
    checkpoint = root / f"seed-{seed}" / f"checkpoint-{stage}"
    _write_json(checkpoint / "manifest.json", {"checkpoint": {"id": f"{seed}-{stage}"}})
    _write_json(
        checkpoint / "metrics.json",
        {
            "mean_score": score,
            "mean_tokens": 20 + seed,
            "mean_latency_ms": 100 + seed,
            "generation_saturation_rate": 0.0,
        },
    )
    diagnostics = checkpoint / "diagnostics"
    _write_json(diagnostics / "trajectory.json", {"mean_step_drift": 0.1 + seed * 0.01})
    _write_json(diagnostics / "generation_mismatch.json", {"gap": 0.05})
    _write_json(diagnostics / "selective_risk.json", {"observed_aurc": 0.2})
    _write_json(
        diagnostics / "prompt_reachability.json",
        {"representation_shift_l2_normalized": 0.03},
    )
    _write_json(diagnostics / "readout_alignment.json", {"alignment_gap": 0.05})
    _write_json(diagnostics / "prompt_routing.json", {"evidence_status": "insufficient_evidence"})
    _write_json(diagnostics / "prompt_projection.json", {"applicability": "not_applicable"})
    _write_json(diagnostics / "prompt_stability.json", {"mean_step_drift": 0.1})


def test_pilot_summary_aggregates_all_seed_gates_conservatively(tmp_path: Path) -> None:
    for seed in (0, 1, 2):
        for stage, score in (("initial", 0.5), ("mid", 0.6), ("final", 0.7)):
            _write_checkpoint(tmp_path, seed, stage, score + seed * 0.01)
        _write_gate(tmp_path, seed, "mid", "pass", 0.05 + seed * 0.01)
        _write_gate(
            tmp_path,
            seed,
            "final",
            "needs_review" if seed == 2 else "pass",
            0.1 + seed * 0.01,
        )

    payload = write_pilot_summary(tmp_path, seeds=(0, 1, 2))

    assert payload["decision"] == "needs_review"
    assert payload["stage_decisions"] == {"mid": "pass", "final": "needs_review"}
    assert payload["gate_count"] == 6
    assert payload["checkpoint_run_count"] == 9
    assert payload["planned_checkpoint_run_count"] == 9
    assert payload["score_delta_by_stage"]["final"]["mean"] == 0.11
    assert payload["checkpoint_metrics_by_stage"]["final"]["mean_score"]["mean"] == 0.71
    assert payload["checkpoint_metrics_by_stage"]["final"]["routing_status_counts"] == {
        "insufficient_evidence": 3
    }
    assert all(not Path(row["gate_path"]).is_absolute() for row in payload["gates"])
    assert (tmp_path / "pilot_summary.html").is_file()
    trace = json.loads((tmp_path / "decision_trace.json").read_text(encoding="utf-8"))
    assert len(trace["gate_traces"]) == 6


def test_pilot_summary_marks_missing_seed_gate_as_insufficient(tmp_path: Path) -> None:
    _write_gate(tmp_path, 0, "mid", "pass", 0.1)

    payload = write_pilot_summary(tmp_path, seeds=(0, 1, 2))

    assert payload["decision"] == "insufficient_evidence"
    assert payload["missing_gates"]
