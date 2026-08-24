from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

import pytest

from promptcontrollab.cli import main
from promptcontrollab.files import read_json
from promptcontrollab.posttrain_gate import run_posttrain_gate

_SAMPLE_HASH = "sha256:" + "a" * 64


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_checkpoint(
    root: Path,
    *,
    checkpoint_id: str,
    score: float,
    split_hash: str = "sha256:split",
    model_id: str = "Qwen/Qwen2.5-0.5B",
    drift: float = 0.2,
    soft_hard_risk: str = "low",
    generation_gap: float = 0.04,
    aurc: float = 0.3,
    mean_tokens: float = 100.0,
    mean_latency_ms: float = 200.0,
    paired_ci: tuple[float, float] = (0.01, 0.2),
    paired_baseline_id: str = "000",
    paired_baseline_split_hash: str | None = None,
    paired_mean_delta: float | None = None,
    sample_hash: str = _SAMPLE_HASH,
    n: int = 2,
) -> None:
    _write_json(
        root / "manifest.json",
        {
            "checkpoint": {
                "id": checkpoint_id,
                "training_method": "sft",
                "provider": "huggingface",
                "model_id": model_id,
                "split_hash": split_hash,
                "seed": 0,
            }
        },
    )
    _write_json(
        root / "metrics.json",
        {
            "mean_score": score,
            "n": n,
            "sample_hash": sample_hash,
            "mean_tokens": mean_tokens,
            "mean_latency_ms": mean_latency_ms,
            "by_slice": {"format": score, "reasoning": score - 0.1},
        },
    )
    _write_json(
        root / "stats.json",
        {
            "comparisons": [
                {
                    "baseline_checkpoint": paired_baseline_id,
                    "candidate_checkpoint": checkpoint_id,
                    "baseline_split_hash": paired_baseline_split_hash or split_hash,
                    "candidate_split_hash": split_hash,
                    "mean_delta": (
                        paired_mean_delta if paired_mean_delta is not None else score - 0.6
                    ),
                    "bootstrap_ci": list(paired_ci),
                    "permutation_p_value": 0.02,
                    "holm_adjusted_p_value": 0.02,
                    "n_pairs": n,
                    "baseline_sample_hash": sample_hash,
                    "candidate_sample_hash": sample_hash,
                }
            ]
        },
    )
    _write_json(
        root / "diagnostics/trajectory.json",
        {"mean_step_drift": drift, "log_decay_slope": -0.02, "decay_r2": 0.7},
    )
    _write_json(
        root / "diagnostics/soft_hard.json",
        {"risk": soft_hard_risk, "mean_projection_distance": 0.2},
    )
    _write_json(
        root / "diagnostics/generation_mismatch.json",
        {"gap": generation_gap, "teacher_forced_score": score + generation_gap},
    )
    _write_json(root / "diagnostics/selective_risk.json", {"observed_aurc": aurc})


def _write_policy(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "min_score_delta: 0.0",
                "max_slice_regression: 0.05",
                "max_trajectory_drift_increase: 0.05",
                "max_generation_mismatch: 0.1",
                "max_selective_aurc: 0.4",
                "max_soft_hard_risk: medium",
                "min_paired_ci_lower: 0.0",
                "max_token_increase_ratio: 0.2",
                "max_latency_increase_ratio: 0.2",
                "require_split_hash_match: true",
                "require_model_match: true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_posttrain_gate_passes_matched_checkpoint_improvement(tmp_path: Path) -> None:
    baseline = tmp_path / "checkpoint-000"
    candidate = tmp_path / "checkpoint-500"
    _write_checkpoint(baseline, checkpoint_id="000", score=0.6, drift=0.2)
    _write_checkpoint(candidate, checkpoint_id="500", score=0.7, drift=0.22)
    policy = tmp_path / "posttrain.policy.yaml"
    _write_policy(policy)

    payload = run_posttrain_gate(
        baseline_dir=baseline,
        candidate_dir=candidate,
        policy_path=policy,
        out_dir=tmp_path / "gate",
    )

    assert payload["decision"] == "pass"
    assert payload["checks"]["task_score"]["passed"] is True
    assert payload["checks"]["provenance"]["passed"] is True
    comparison = read_json(tmp_path / "gate/checkpoint_comparison.json")
    assert comparison["score_delta"] == 0.1
    assert comparison["slice_deltas"]["format"] == 0.1
    attribution = read_json(tmp_path / "gate/mechanism_attribution.json")
    assert attribution["findings"]
    assert (tmp_path / "gate/report.html").is_file()


def test_posttrain_gate_holds_score_gain_with_stability_or_deployment_regression(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "checkpoint-000"
    candidate = tmp_path / "checkpoint-500"
    _write_checkpoint(baseline, checkpoint_id="000", score=0.6, drift=0.2)
    _write_checkpoint(
        candidate,
        checkpoint_id="500",
        score=0.75,
        drift=0.5,
        soft_hard_risk="high",
    )
    policy = tmp_path / "posttrain.policy.yaml"
    _write_policy(policy)

    payload = run_posttrain_gate(
        baseline_dir=baseline,
        candidate_dir=candidate,
        policy_path=policy,
        out_dir=tmp_path / "gate",
    )

    assert payload["decision"] == "hold"
    assert payload["checks"]["task_score"]["passed"] is True
    assert payload["checks"]["trajectory_stability"]["passed"] is False
    assert payload["checks"]["soft_hard_deployment"]["passed"] is False
    assert "score improvement" in payload["plain_summary"].lower()


def test_posttrain_gate_accepts_explicitly_not_applicable_soft_hard_diagnostic(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "checkpoint-000"
    candidate = tmp_path / "checkpoint-500"
    _write_checkpoint(baseline, checkpoint_id="000", score=0.6)
    _write_checkpoint(candidate, checkpoint_id="500", score=0.7)
    _write_json(
        candidate / "diagnostics/soft_hard.json",
        {
            "applicability": "not_applicable",
            "reason": "This SFT checkpoint does not deploy a learned soft prompt.",
        },
    )
    policy = tmp_path / "posttrain.policy.yaml"
    _write_policy(policy)

    payload = run_posttrain_gate(
        baseline_dir=baseline,
        candidate_dir=candidate,
        policy_path=policy,
        out_dir=tmp_path / "gate",
    )

    check = payload["checks"]["soft_hard_deployment"]
    assert payload["decision"] == "pass"
    assert check["applicable"] is False
    assert check["passed"] is True
    assert check["severity"] == "info"


def test_posttrain_gate_marks_missing_required_evidence_insufficient(tmp_path: Path) -> None:
    baseline = tmp_path / "checkpoint-000"
    candidate = tmp_path / "checkpoint-500"
    _write_checkpoint(baseline, checkpoint_id="000", score=0.6)
    _write_checkpoint(candidate, checkpoint_id="500", score=0.7)
    (candidate / "diagnostics/generation_mismatch.json").unlink()
    policy = tmp_path / "posttrain.policy.yaml"
    _write_policy(policy)

    payload = run_posttrain_gate(
        baseline_dir=baseline,
        candidate_dir=candidate,
        policy_path=policy,
        out_dir=tmp_path / "gate",
    )

    assert payload["decision"] == "insufficient_evidence"
    assert "candidate:diagnostics/generation_mismatch.json" in payload["missing_artifacts"]


def test_posttrain_gate_marks_non_finite_required_metric_insufficient(tmp_path: Path) -> None:
    baseline = tmp_path / "checkpoint-000"
    candidate = tmp_path / "checkpoint-500"
    _write_checkpoint(baseline, checkpoint_id="000", score=0.6)
    _write_checkpoint(candidate, checkpoint_id="500", score=0.7)
    metrics = read_json(candidate / "metrics.json")
    metrics["mean_score"] = float("nan")
    _write_json(candidate / "metrics.json", metrics)
    policy = tmp_path / "posttrain.policy.yaml"
    _write_policy(policy)

    payload = run_posttrain_gate(
        baseline_dir=baseline,
        candidate_dir=candidate,
        policy_path=policy,
        out_dir=tmp_path / "gate",
    )

    assert payload["decision"] == "insufficient_evidence"
    assert "candidate:metrics.mean_score" in payload["invalid_evidence"]
    report_text = (tmp_path / "gate/checkpoint_comparison.json").read_text(encoding="utf-8")
    assert "NaN" not in report_text


def test_posttrain_gate_needs_review_for_slice_regression(tmp_path: Path) -> None:
    baseline = tmp_path / "checkpoint-000"
    candidate = tmp_path / "checkpoint-500"
    _write_checkpoint(baseline, checkpoint_id="000", score=0.6)
    _write_checkpoint(candidate, checkpoint_id="500", score=0.65)
    metrics = read_json(candidate / "metrics.json")
    metrics["by_slice"]["reasoning"] = 0.3
    _write_json(candidate / "metrics.json", metrics)
    policy = tmp_path / "posttrain.policy.yaml"
    _write_policy(policy)

    payload = run_posttrain_gate(
        baseline_dir=baseline,
        candidate_dir=candidate,
        policy_path=policy,
        out_dir=tmp_path / "gate",
    )

    assert payload["decision"] == "needs_review"
    assert payload["checks"]["slice_regression"]["severity"] == "review"


def test_posttrain_gate_marks_missing_candidate_slice_insufficient(tmp_path: Path) -> None:
    baseline = tmp_path / "checkpoint-000"
    candidate = tmp_path / "checkpoint-500"
    _write_checkpoint(baseline, checkpoint_id="000", score=0.6)
    _write_checkpoint(candidate, checkpoint_id="500", score=0.7)
    metrics = read_json(candidate / "metrics.json")
    metrics["by_slice"].pop("reasoning")
    _write_json(candidate / "metrics.json", metrics)
    policy = tmp_path / "posttrain.policy.yaml"
    _write_policy(policy)

    payload = run_posttrain_gate(
        baseline_dir=baseline,
        candidate_dir=candidate,
        policy_path=policy,
        out_dir=tmp_path / "gate",
    )

    assert payload["decision"] == "insufficient_evidence"
    assert "candidate:metrics.by_slice.reasoning" in payload["invalid_evidence"]


def test_posttrain_gate_rejects_statistics_for_a_different_baseline(tmp_path: Path) -> None:
    baseline = tmp_path / "checkpoint-mid"
    candidate = tmp_path / "checkpoint-final"
    _write_checkpoint(baseline, checkpoint_id="mid", score=0.65)
    _write_checkpoint(
        candidate,
        checkpoint_id="final",
        score=0.7,
        paired_baseline_id="initial",
    )
    policy = tmp_path / "posttrain.policy.yaml"
    _write_policy(policy)

    payload = run_posttrain_gate(
        baseline_dir=baseline,
        candidate_dir=candidate,
        policy_path=policy,
        out_dir=tmp_path / "gate",
    )

    assert payload["decision"] == "insufficient_evidence"
    assert "candidate:stats.baseline_checkpoint" in payload["invalid_evidence"]


def test_posttrain_gate_rejects_unknown_soft_hard_policy_level(tmp_path: Path) -> None:
    baseline = tmp_path / "checkpoint-000"
    candidate = tmp_path / "checkpoint-500"
    _write_checkpoint(baseline, checkpoint_id="000", score=0.6)
    _write_checkpoint(candidate, checkpoint_id="500", score=0.7)
    policy = tmp_path / "posttrain.policy.yaml"
    _write_policy(policy)
    policy.write_text(
        policy.read_text(encoding="utf-8").replace(
            "max_soft_hard_risk: medium", "max_soft_hard_risk: typo"
        ),
        encoding="utf-8",
    )

    try:
        run_posttrain_gate(
            baseline_dir=baseline,
            candidate_dir=candidate,
            policy_path=policy,
            out_dir=tmp_path / "gate",
        )
    except ValueError as exc:
        assert "max_soft_hard_risk" in str(exc)
    else:
        raise AssertionError("Expected invalid soft-hard risk policy to fail closed")


def test_posttrain_gate_rejects_invalid_boolean_policy_value(tmp_path: Path) -> None:
    baseline = tmp_path / "checkpoint-000"
    candidate = tmp_path / "checkpoint-500"
    _write_checkpoint(baseline, checkpoint_id="000", score=0.6)
    _write_checkpoint(candidate, checkpoint_id="500", score=0.7)
    policy = tmp_path / "posttrain.policy.yaml"
    _write_policy(policy)
    policy.write_text(
        policy.read_text(encoding="utf-8").replace(
            "require_model_match: true", "require_model_match: typo"
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="require_model_match"):
        run_posttrain_gate(
            baseline_dir=baseline,
            candidate_dir=candidate,
            policy_path=policy,
            out_dir=tmp_path / "gate",
        )


def test_posttrain_gate_rejects_statistics_not_bound_to_metrics(tmp_path: Path) -> None:
    baseline = tmp_path / "checkpoint-000"
    candidate = tmp_path / "checkpoint-500"
    _write_checkpoint(baseline, checkpoint_id="000", score=0.6)
    _write_checkpoint(
        candidate,
        checkpoint_id="500",
        score=0.7,
        paired_mean_delta=99.0,
    )
    stats = read_json(candidate / "stats.json")
    stats["comparisons"][0]["n_pairs"] = 999
    stats["comparisons"][0]["candidate_sample_hash"] = "sha256:other"
    _write_json(candidate / "stats.json", stats)
    policy = tmp_path / "posttrain.policy.yaml"
    _write_policy(policy)

    payload = run_posttrain_gate(
        baseline_dir=baseline,
        candidate_dir=candidate,
        policy_path=policy,
        out_dir=tmp_path / "gate",
    )

    assert payload["decision"] == "insufficient_evidence"
    assert "candidate:stats.mean_delta" in payload["invalid_evidence"]
    assert "candidate:stats.n_pairs" in payload["invalid_evidence"]
    assert "candidate:stats.candidate_sample_hash" in payload["invalid_evidence"]


def test_posttrain_gate_rejects_reversed_confidence_interval(tmp_path: Path) -> None:
    baseline = tmp_path / "checkpoint-000"
    candidate = tmp_path / "checkpoint-500"
    _write_checkpoint(baseline, checkpoint_id="000", score=0.6)
    _write_checkpoint(candidate, checkpoint_id="500", score=0.7, paired_ci=(1.0, -1.0))
    policy = tmp_path / "posttrain.policy.yaml"
    _write_policy(policy)

    payload = run_posttrain_gate(
        baseline_dir=baseline,
        candidate_dir=candidate,
        policy_path=policy,
        out_dir=tmp_path / "gate",
    )

    assert payload["decision"] == "insufficient_evidence"
    assert "candidate:stats.bootstrap_ci" in payload["invalid_evidence"]


def test_posttrain_gate_rejects_non_finite_candidate_slice(tmp_path: Path) -> None:
    baseline = tmp_path / "checkpoint-000"
    candidate = tmp_path / "checkpoint-500"
    _write_checkpoint(baseline, checkpoint_id="000", score=0.6)
    _write_checkpoint(candidate, checkpoint_id="500", score=0.7)
    metrics = read_json(candidate / "metrics.json")
    metrics["by_slice"]["reasoning"] = float("nan")
    _write_json(candidate / "metrics.json", metrics)
    policy = tmp_path / "posttrain.policy.yaml"
    _write_policy(policy)

    payload = run_posttrain_gate(
        baseline_dir=baseline,
        candidate_dir=candidate,
        policy_path=policy,
        out_dir=tmp_path / "gate",
    )

    assert payload["decision"] == "insufficient_evidence"
    assert "candidate:metrics.by_slice.reasoning" in payload["invalid_evidence"]


def test_posttrain_gate_requires_nonempty_checkpoint_identity(tmp_path: Path) -> None:
    baseline = tmp_path / "checkpoint-000"
    candidate = tmp_path / "checkpoint-500"
    _write_checkpoint(baseline, checkpoint_id="000", score=0.6)
    _write_checkpoint(candidate, checkpoint_id="500", score=0.7)
    manifest = read_json(candidate / "manifest.json")
    manifest["checkpoint"].pop("id")
    _write_json(candidate / "manifest.json", manifest)
    stats = read_json(candidate / "stats.json")
    stats["comparisons"][0]["candidate_checkpoint"] = ""
    _write_json(candidate / "stats.json", stats)
    policy = tmp_path / "posttrain.policy.yaml"
    _write_policy(policy)

    payload = run_posttrain_gate(
        baseline_dir=baseline,
        candidate_dir=candidate,
        policy_path=policy,
        out_dir=tmp_path / "gate",
    )

    assert payload["decision"] == "insufficient_evidence"
    assert "candidate:manifest.checkpoint.id" in payload["invalid_evidence"]


def test_posttrain_gate_rejects_impossible_p_values(tmp_path: Path) -> None:
    baseline = tmp_path / "checkpoint-000"
    candidate = tmp_path / "checkpoint-500"
    _write_checkpoint(baseline, checkpoint_id="000", score=0.6)
    _write_checkpoint(candidate, checkpoint_id="500", score=0.7)
    stats = read_json(candidate / "stats.json")
    stats["comparisons"][0]["permutation_p_value"] = 2.0
    stats["comparisons"][0]["holm_adjusted_p_value"] = -1.0
    _write_json(candidate / "stats.json", stats)
    policy = tmp_path / "posttrain.policy.yaml"
    _write_policy(policy)

    payload = run_posttrain_gate(
        baseline_dir=baseline,
        candidate_dir=candidate,
        policy_path=policy,
        out_dir=tmp_path / "gate",
    )

    assert payload["decision"] == "insufficient_evidence"
    assert "candidate:stats.permutation_p_value" in payload["invalid_evidence"]
    assert "candidate:stats.holm_adjusted_p_value" in payload["invalid_evidence"]


def test_posttrain_gate_needs_review_when_paired_ci_crosses_zero(tmp_path: Path) -> None:
    baseline = tmp_path / "checkpoint-000"
    candidate = tmp_path / "checkpoint-500"
    _write_checkpoint(baseline, checkpoint_id="000", score=0.6)
    _write_checkpoint(
        candidate,
        checkpoint_id="500",
        score=0.7,
        paired_ci=(-0.02, 0.15),
    )
    policy = tmp_path / "posttrain.policy.yaml"
    _write_policy(policy)

    payload = run_posttrain_gate(
        baseline_dir=baseline,
        candidate_dir=candidate,
        policy_path=policy,
        out_dir=tmp_path / "gate",
    )

    assert payload["decision"] == "needs_review"
    assert payload["checks"]["paired_uncertainty"]["passed"] is False
    comparison = read_json(tmp_path / "gate/checkpoint_comparison.json")
    assert comparison["paired_statistics"]["bootstrap_ci"] == [-0.02, 0.15]


def test_posttrain_gate_reviews_token_or_latency_regression(tmp_path: Path) -> None:
    baseline = tmp_path / "checkpoint-000"
    candidate = tmp_path / "checkpoint-500"
    _write_checkpoint(baseline, checkpoint_id="000", score=0.6)
    _write_checkpoint(
        candidate,
        checkpoint_id="500",
        score=0.7,
        mean_tokens=140.0,
        mean_latency_ms=260.0,
    )
    policy = tmp_path / "posttrain.policy.yaml"
    _write_policy(policy)

    payload = run_posttrain_gate(
        baseline_dir=baseline,
        candidate_dir=candidate,
        policy_path=policy,
        out_dir=tmp_path / "gate",
    )

    assert payload["decision"] == "needs_review"
    assert payload["checks"]["resource_cost"]["passed"] is False


def test_posttrain_gate_cli_writes_all_artifacts(tmp_path: Path) -> None:
    baseline = tmp_path / "checkpoint-000"
    candidate = tmp_path / "checkpoint-500"
    _write_checkpoint(baseline, checkpoint_id="000", score=0.6)
    _write_checkpoint(candidate, checkpoint_id="500", score=0.7)
    policy = tmp_path / "posttrain.policy.yaml"
    _write_policy(policy)
    out_dir = tmp_path / "gate"

    assert (
        main(
            [
                "posttrain-gate",
                "--baseline",
                str(baseline),
                "--candidate",
                str(candidate),
                "--policy",
                str(policy),
                "--out",
                str(out_dir),
            ]
        )
        == 0
    )
    assert {
        "posttrain_gate.json",
        "checkpoint_comparison.json",
        "mechanism_attribution.json",
        "report.md",
        "report.html",
    } <= {path.name for path in out_dir.iterdir()}


def test_posttrain_gate_cli_uses_packaged_default_policy(tmp_path: Path) -> None:
    baseline = tmp_path / "checkpoint-000"
    candidate = tmp_path / "checkpoint-500"
    _write_checkpoint(baseline, checkpoint_id="000", score=0.6)
    _write_checkpoint(candidate, checkpoint_id="500", score=0.7)
    out_dir = tmp_path / "gate"

    assert main(
        [
            "posttrain-gate",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--out",
            str(out_dir),
        ]
    ) == 0
    payload = read_json(out_dir / "posttrain_gate.json")
    assert payload["policy_path"] == "packaged-default"
    assert (
        resources.files("promptcontrollab.template_data")
        .joinpath("policies")
        .joinpath("posttrain.policy.yaml")
        .is_file()
    )
