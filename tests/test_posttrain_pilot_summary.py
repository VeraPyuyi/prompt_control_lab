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


def test_pilot_summary_aggregates_all_seed_gates_conservatively(tmp_path: Path) -> None:
    for seed in (0, 1, 2):
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
    assert payload["score_delta_by_stage"]["final"]["mean"] == 0.11
    assert (tmp_path / "pilot_summary.html").is_file()
    trace = json.loads((tmp_path / "decision_trace.json").read_text(encoding="utf-8"))
    assert len(trace["gate_traces"]) == 6


def test_pilot_summary_marks_missing_seed_gate_as_insufficient(tmp_path: Path) -> None:
    _write_gate(tmp_path, 0, "mid", "pass", 0.1)

    payload = write_pilot_summary(tmp_path, seeds=(0, 1, 2))

    assert payload["decision"] == "insufficient_evidence"
    assert payload["missing_gates"]
