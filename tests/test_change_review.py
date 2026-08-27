from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import TypedDict

import pytest

from promptcontrollab.cli import main
from promptcontrollab.evaluation.change_review import review_changes
from promptcontrollab.evaluation.report_model import ReportModel
from promptcontrollab.integrations.ui.data import load_run_detail


class _RunOptions(TypedDict, total=False):
    prompt_hash: str
    model: str
    provider: str
    agent: str
    checkpoint: str


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _run(
    root: Path,
    name: str,
    *,
    prompt_hash: str,
    model: str = "model-20260801",
    provider: str = "openai",
    agent: str | None = None,
    checkpoint: str | None = None,
    score: float = 0.5,
) -> Path:
    run = root / name
    manifest: dict[str, object] = {
        "metric": "exact_match",
        "split_hash": "split-fixed",
        "prompt": {"prompt_hash": prompt_hash},
        "model": {"provider": provider, "model_id": model},
    }
    if agent:
        manifest["agent"] = agent
    if checkpoint:
        manifest["checkpoint"] = {"checkpoint_id": checkpoint, "stage": name}
    _write_json(run / "manifest.json", manifest)
    _write_json(run / "metrics.json", {"mean_score": score, "by_slice": {"core": score}})
    return run


def test_review_changes_writes_complete_shadow_artifact_set(tmp_path: Path) -> None:
    baseline = _run(tmp_path, "baseline", prompt_hash="sha256:raw", score=0.4)
    candidate = _run(tmp_path, "candidate", prompt_hash="sha256:guarded", score=0.6)
    out = tmp_path / "review"

    payload = review_changes(
        baseline_dir=baseline,
        candidate_dir=candidate,
        out_dir=out,
        kind="auto",
        mode="shadow",
    )

    assert payload["schema"] == "prompt_control_lab.change_review.v1"
    assert payload["change_kind"] == "prompt_change"
    assert payload["mode"] == "shadow"
    assert payload["enforcement"] == "observe_only"
    assert payload["decision"] in {"pass", "needs_review", "hold", "insufficient_evidence"}
    for name in [
        "change_review.json",
        "comparison_validity.json",
        "attribution.json",
        "stability.json",
        "decision_trace.json",
        "human_feedback.json",
        "report.md",
        "report.html",
    ]:
        assert (out / name).is_file(), name

    feedback = json.loads((out / "human_feedback.json").read_text(encoding="utf-8"))
    assert feedback["questions"] == [
        "What changed?",
        "What was observed?",
        "What most likely explains the difference?",
        "How reliable is the evidence?",
        "What cannot be concluded?",
        "What should happen next?",
    ]


def test_review_changes_records_secondary_execution_metric_deltas(tmp_path: Path) -> None:
    baseline = _run(tmp_path, "baseline", prompt_hash="sha256:raw", score=1.0)
    candidate = _run(tmp_path, "candidate", prompt_hash="sha256:guarded", score=1.0)
    _write_json(
        baseline / "metrics.json",
        {
            "mean_score": 1.0,
            "mean_total_tokens": 1200.0,
            "mean_tool_calls": 8.0,
            "mean_touched_files": 3.0,
        },
    )
    _write_json(
        candidate / "metrics.json",
        {
            "mean_score": 1.0,
            "mean_total_tokens": 900.0,
            "mean_tool_calls": 6.0,
            "mean_touched_files": 2.0,
        },
    )

    payload = review_changes(
        baseline_dir=baseline,
        candidate_dir=candidate,
        out_dir=tmp_path / "review",
        kind="auto",
        mode="shadow",
    )

    deltas = payload["observations"]["metric_deltas"]
    assert deltas["mean_total_tokens"] == {
        "baseline": 1200.0,
        "candidate": 900.0,
        "delta": -300.0,
        "direction": "decrease",
    }
    assert deltas["mean_tool_calls"]["delta"] == -2.0
    feedback = json.loads(
        (tmp_path / "review" / "human_feedback.json").read_text(encoding="utf-8")
    )
    assert "mean_total_tokens decreased" in feedback["answers"]["What was observed?"]


@pytest.mark.parametrize(
    ("baseline_kwargs", "candidate_kwargs", "expected"),
    [
        (
            {"prompt_hash": "sha256:p", "model": "model-a"},
            {"prompt_hash": "sha256:p", "model": "model-b"},
            "model_change",
        ),
        (
            {"prompt_hash": "sha256:p", "agent": "codex"},
            {"prompt_hash": "sha256:p", "agent": "deepseek-harness"},
            "agent_change",
        ),
        (
            {"prompt_hash": "sha256:p", "checkpoint": "step-0"},
            {"prompt_hash": "sha256:p", "checkpoint": "step-60"},
            "checkpoint_change",
        ),
    ],
)
def test_review_changes_detects_primary_change_kind(
    tmp_path: Path,
    baseline_kwargs: _RunOptions,
    candidate_kwargs: _RunOptions,
    expected: str,
) -> None:
    baseline = _run(tmp_path, "baseline", **baseline_kwargs)
    candidate = _run(tmp_path, "candidate", **candidate_kwargs)

    payload = review_changes(
        baseline_dir=baseline,
        candidate_dir=candidate,
        out_dir=tmp_path / f"review-{expected}",
        kind="auto",
        mode="shadow",
    )

    assert payload["change_kind"] == expected


def test_review_changes_rejects_unknown_kind_and_mode(tmp_path: Path) -> None:
    baseline = _run(tmp_path, "baseline", prompt_hash="sha256:a")
    candidate = _run(tmp_path, "candidate", prompt_hash="sha256:b")

    with pytest.raises(ValueError, match="change kind"):
        review_changes(
            baseline_dir=baseline,
            candidate_dir=candidate,
            out_dir=tmp_path / "bad-kind",
            kind="mixed",
            mode="shadow",
        )
    with pytest.raises(ValueError, match="review mode"):
        review_changes(
            baseline_dir=baseline,
            candidate_dir=candidate,
            out_dir=tmp_path / "bad-mode",
            kind="auto",
            mode="block",
        )


def test_shadow_review_never_claims_it_blocked_downstream_execution(tmp_path: Path) -> None:
    baseline = _run(tmp_path, "baseline", prompt_hash="sha256:a", score=0.8)
    candidate = _run(tmp_path, "candidate", prompt_hash="sha256:b", score=0.1)

    payload = review_changes(
        baseline_dir=baseline,
        candidate_dir=candidate,
        out_dir=tmp_path / "review",
        kind="prompt_change",
        mode="shadow",
    )

    assert payload["enforcement"] == "observe_only"
    assert payload["downstream_modified"] is False
    assert "blocked downstream" not in json.dumps(payload).lower()


def test_report_model_and_ui_load_the_same_change_review_artifacts(tmp_path: Path) -> None:
    baseline = _run(tmp_path, "baseline", prompt_hash="sha256:a", score=0.5)
    candidate = _run(tmp_path, "candidate", prompt_hash="sha256:b", score=0.7)
    out = tmp_path / "review"
    review_changes(
        baseline_dir=baseline,
        candidate_dir=candidate,
        out_dir=out,
        kind="auto",
        mode="shadow",
    )

    model = ReportModel.from_run(out)
    detail = load_run_detail(out)

    assert model.change_review["change_kind"] == "prompt_change"
    assert model.human_feedback["schema"] == "prompt_control_lab.human_feedback.v1"
    assert model.attribution == detail["attribution"]
    assert model.stability == detail["stability"]
    assert model.change_review == detail["change_review"]
    assert model.human_feedback == detail["human_feedback"]


def test_report_model_additive_change_review_fields_are_optional() -> None:
    signature = inspect.signature(ReportModel)

    for name in (
        "change_review",
        "attribution",
        "stability",
        "decision_trace",
        "human_feedback",
        "trace_import",
    ):
        assert signature.parameters[name].default is not inspect.Parameter.empty


def test_cli_review_writes_shadow_review(tmp_path: Path) -> None:
    baseline = _run(tmp_path, "baseline", prompt_hash="sha256:a", score=0.3)
    candidate = _run(tmp_path, "candidate", prompt_hash="sha256:b", score=0.4)
    out = tmp_path / "review"

    assert (
        main(
            [
                "review",
                "--baseline",
                str(baseline),
                "--candidate",
                str(candidate),
                "--kind",
                "auto",
                "--mode",
                "shadow",
                "--out",
                str(out),
            ]
        )
        == 0
    )
    payload = json.loads((out / "change_review.json").read_text(encoding="utf-8"))
    assert payload["mode"] == "shadow"
    assert payload["downstream_modified"] is False


def test_checkpoint_review_preserves_posttrain_hold_decision(tmp_path: Path) -> None:
    baseline = _run(
        tmp_path,
        "baseline",
        prompt_hash="sha256:p",
        checkpoint="step-0",
        score=0.1,
    )
    candidate = _run(
        tmp_path,
        "candidate",
        prompt_hash="sha256:p",
        checkpoint="step-60",
        score=0.2,
    )
    _write_json(
        candidate / "posttrain_gate.json",
        {
            "decision": "hold",
            "plain_summary": "Score improved, but generation mismatch exceeded the policy.",
        },
    )

    payload = review_changes(
        baseline_dir=baseline,
        candidate_dir=candidate,
        out_dir=tmp_path / "review",
        kind="auto",
        mode="shadow",
    )

    assert payload["change_kind"] == "checkpoint_change"
    assert payload["decision"] == "hold"
    assert payload["observations"]["candidate_gate"] == "hold"
    assert any("post-training gate" in reason.lower() for reason in payload["reasons"])


@pytest.mark.parametrize(
    ("gate_decision", "expected"),
    [("needs_review", "needs_review"), ("insufficient_evidence", "insufficient_evidence")],
)
def test_review_changes_conservatively_propagates_candidate_gate_status(
    tmp_path: Path,
    gate_decision: str,
    expected: str,
) -> None:
    baseline = _run(tmp_path, "baseline", prompt_hash="sha256:a", score=0.4)
    candidate = _run(tmp_path, "candidate", prompt_hash="sha256:b", score=0.8)
    _write_json(candidate / "posttrain_gate.json", {"decision": gate_decision})

    payload = review_changes(
        baseline_dir=baseline,
        candidate_dir=candidate,
        out_dir=tmp_path / "review",
        kind="prompt_change",
        mode="shadow",
    )

    assert payload["decision"] == expected
    trace = json.loads(
        (tmp_path / "review" / "decision_trace.json").read_text(encoding="utf-8")
    )
    gate_check = next(item for item in trace["checks"] if item["check"] == "candidate_gate")
    assert gate_check["status"] == "triggered"


def test_review_changes_treats_nonfinite_scores_as_invalid_evidence(tmp_path: Path) -> None:
    baseline = _run(tmp_path, "baseline", prompt_hash="sha256:a", score=0.4)
    candidate = _run(tmp_path, "candidate", prompt_hash="sha256:b", score=0.8)
    _write_json(candidate / "metrics.json", {"mean_score": float("nan")})

    payload = review_changes(
        baseline_dir=baseline,
        candidate_dir=candidate,
        out_dir=tmp_path / "review",
        kind="prompt_change",
        mode="shadow",
    )

    assert payload["decision"] == "insufficient_evidence"
    serialized = (tmp_path / "review" / "change_review.json").read_text(encoding="utf-8")
    assert "NaN" not in serialized
