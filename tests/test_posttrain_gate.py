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
    seed: int = 0,
    training_method: str = "sft",
    model_revision: str = "a" * 40,
    model_snapshot_sha256: str = "sha256:" + "b" * 64,
    include_prompt_diagnostics: bool = True,
) -> None:
    _write_json(
        root / "manifest.json",
        {
            "checkpoint": {
                "id": checkpoint_id,
                "training_method": training_method,
                "provider": "huggingface",
                "model_id": model_id,
                "model_revision": model_revision,
                "model_snapshot_sha256": model_snapshot_sha256,
                "split_hash": split_hash,
                "seed": seed,
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
    if include_prompt_diagnostics:
        _write_prompt_diagnostics(root, routing_status="observed")


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
                "max_prompt_reachability_shift: 0.5",
                "max_readout_alignment_gap: 0.1",
                "max_prompt_stability_drift_increase: 0.05",
                "require_prompt_routing_evidence: false",
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
    trace = read_json(tmp_path / "gate/decision_trace.json")
    assert trace["capability_profile"] == "full-open-model"
    assert trace["checks"]
    assert all(
        {"check", "observed", "threshold", "status", "impact", "evidence", "next_action"}
        <= set(row)
        for row in trace["checks"]
    )


def _write_prompt_diagnostics(
    root: Path,
    *,
    reachability_shift: float = 0.2,
    alignment_gap: float = 0.04,
    stability_drift: float = 0.2,
    routing_status: str = "insufficient_evidence",
) -> None:
    _write_json(
        root / "diagnostics/prompt_reachability.json",
        {"representation_shift_l2_normalized": reachability_shift},
    )
    _write_json(
        root / "diagnostics/readout_alignment.json",
        {"alignment_gap": alignment_gap},
    )
    _write_json(
        root / "diagnostics/prompt_routing.json",
        {"evidence_status": routing_status},
    )
    _write_json(
        root / "diagnostics/prompt_projection.json",
        {
            "applicability": "not_applicable",
            "reason": "Standard LoRA does not deploy a learned soft prompt.",
        },
    )
    _write_json(
        root / "diagnostics/prompt_stability.json",
        {"mean_step_drift": stability_drift},
    )


def test_posttrain_gate_uses_prompt_reach_diagnostics_when_available(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "checkpoint-000"
    candidate = tmp_path / "checkpoint-500"
    _write_checkpoint(baseline, checkpoint_id="000", score=0.6)
    _write_checkpoint(candidate, checkpoint_id="500", score=0.7)
    _write_prompt_diagnostics(
        baseline,
        reachability_shift=0.0,
        alignment_gap=0.03,
        stability_drift=0.2,
    )
    _write_prompt_diagnostics(
        candidate,
        reachability_shift=0.2,
        alignment_gap=0.04,
        stability_drift=0.22,
    )
    policy = tmp_path / "posttrain.policy.yaml"
    _write_policy(policy)

    payload = run_posttrain_gate(
        baseline_dir=baseline,
        candidate_dir=candidate,
        policy_path=policy,
        out_dir=tmp_path / "gate",
        capability="full-open-model",
    )

    assert payload["decision"] == "insufficient_evidence"
    assert payload["checks"]["prompt_reachability"]["observed"] == 0.2
    assert payload["checks"]["readout_alignment"]["observed"] == 0.04
    assert payload["checks"]["prompt_routing"]["applicable"] is True
    assert payload["checks"]["prompt_routing"]["passed"] is False
    assert payload["checks"]["prompt_routing"]["evidence_status"] == (
        "insufficient_evidence"
    )
    assert payload["checks"]["prompt_routing"]["severity"] == "insufficient"
    assert payload["checks"]["prompt_projection"]["applicable"] is False
    assert payload["checks"]["prompt_stability"]["increase"] == pytest.approx(0.02)
    trace = read_json(tmp_path / "gate/decision_trace.json")
    trace_rows = {row["check"]: row for row in trace["checks"]}
    assert trace_rows["prompt_reachability"]["evidence"] == [
        "diagnostics/prompt_reachability.json"
    ]
    assert trace_rows["readout_alignment"]["evidence"] == [
        "diagnostics/readout_alignment.json"
    ]


@pytest.mark.parametrize(
    ("diagnostic", "candidate_value", "expected_decision"),
    [
        ("prompt_reachability", 0.8, "needs_review"),
        ("readout_alignment", 0.3, "hold"),
        ("prompt_stability", 0.4, "hold"),
    ],
)
def test_posttrain_gate_promotes_prompt_diagnostic_thresholds_to_decisions(
    tmp_path: Path,
    diagnostic: str,
    candidate_value: float,
    expected_decision: str,
) -> None:
    baseline = tmp_path / "checkpoint-000"
    candidate = tmp_path / "checkpoint-500"
    _write_checkpoint(baseline, checkpoint_id="000", score=0.6)
    _write_checkpoint(candidate, checkpoint_id="500", score=0.7)
    _write_prompt_diagnostics(
        baseline,
        stability_drift=0.2,
        routing_status="intervention_observed",
    )
    if diagnostic == "prompt_reachability":
        _write_prompt_diagnostics(
            candidate,
            reachability_shift=candidate_value,
            stability_drift=0.22,
            routing_status="intervention_observed",
        )
    elif diagnostic == "readout_alignment":
        _write_prompt_diagnostics(
            candidate,
            alignment_gap=candidate_value,
            stability_drift=0.22,
            routing_status="intervention_observed",
        )
    else:
        _write_prompt_diagnostics(
            candidate,
            stability_drift=candidate_value,
            routing_status="intervention_observed",
        )
    policy = tmp_path / "posttrain.policy.yaml"
    _write_policy(policy)

    payload = run_posttrain_gate(
        baseline_dir=baseline,
        candidate_dir=candidate,
        policy_path=policy,
        out_dir=tmp_path / "gate",
        capability="full-open-model",
    )

    assert payload["decision"] == expected_decision
    assert payload["checks"][diagnostic]["passed"] is False


def test_posttrain_gate_black_box_does_not_fail_on_inapplicable_open_model_evidence(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "checkpoint-000"
    candidate = tmp_path / "checkpoint-500"
    _write_checkpoint(baseline, checkpoint_id="000", score=0.6)
    _write_checkpoint(candidate, checkpoint_id="500", score=0.7)
    for root in (baseline, candidate):
        manifest = read_json(root / "manifest.json")
        manifest["checkpoint"]["provider"] = "openai"
        manifest["checkpoint"]["capabilities"] = {"hidden_states": False}
        _write_json(root / "manifest.json", manifest)
        (root / "diagnostics/trajectory.json").unlink()
        (root / "diagnostics/soft_hard.json").unlink()
        (root / "diagnostics/generation_mismatch.json").unlink()
    policy = tmp_path / "posttrain.policy.yaml"
    _write_policy(policy)

    payload = run_posttrain_gate(
        baseline_dir=baseline,
        candidate_dir=candidate,
        policy_path=policy,
        out_dir=tmp_path / "gate",
        capability="auto",
    )

    assert payload["capability_profile"] == "black-box"
    assert payload["decision"] == "pass"
    assert payload["checks"]["trajectory_stability"]["applicable"] is False
    assert payload["checks"]["generation_mismatch"]["applicable"] is False


def test_posttrain_gate_explicit_open_model_profile_fails_closed_without_hidden_evidence(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "checkpoint-000"
    candidate = tmp_path / "checkpoint-500"
    _write_checkpoint(baseline, checkpoint_id="000", score=0.6)
    _write_checkpoint(candidate, checkpoint_id="500", score=0.7)
    (candidate / "diagnostics/trajectory.json").unlink()
    policy = tmp_path / "posttrain.policy.yaml"
    _write_policy(policy)

    payload = run_posttrain_gate(
        baseline_dir=baseline,
        candidate_dir=candidate,
        policy_path=policy,
        out_dir=tmp_path / "gate",
        capability="full-open-model",
    )

    assert payload["capability_profile"] == "full-open-model"
    assert payload["decision"] == "insufficient_evidence"


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
    assert check["passed"] is None
    assert check["severity"] == "info"


def test_posttrain_gate_holds_before_reporting_other_missing_evidence(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "checkpoint-000"
    candidate = tmp_path / "checkpoint-500"
    _write_checkpoint(baseline, checkpoint_id="000", score=0.6)
    _write_checkpoint(candidate, checkpoint_id="500", score=0.7)
    readout = read_json(candidate / "diagnostics/readout_alignment.json")
    readout["alignment_gap"] = 0.5
    _write_json(candidate / "diagnostics/readout_alignment.json", readout)
    (candidate / "diagnostics/prompt_routing.json").unlink()
    policy = tmp_path / "posttrain.policy.yaml"
    _write_policy(policy)

    payload = run_posttrain_gate(
        baseline_dir=baseline,
        candidate_dir=candidate,
        policy_path=policy,
        out_dir=tmp_path / "gate",
        capability="full-open-model",
    )

    assert payload["missing_artifacts"]
    assert payload["checks"]["readout_alignment"]["passed"] is False
    assert payload["decision"] == "hold"


@pytest.mark.parametrize(
    ("changed_field", "changed_value", "violation"),
    [
        ("model_revision", "c" * 40, "model_mismatch"),
        ("model_snapshot_sha256", "sha256:" + "d" * 64, "model_mismatch"),
        ("seed", 1, "seed_mismatch"),
        ("training_method", "dpo", "training_method_mismatch"),
    ],
)
def test_posttrain_gate_binds_checkpoint_provenance_beyond_model_alias(
    tmp_path: Path,
    changed_field: str,
    changed_value: object,
    violation: str,
) -> None:
    baseline = tmp_path / "checkpoint-000"
    candidate = tmp_path / "checkpoint-500"
    _write_checkpoint(baseline, checkpoint_id="000", score=0.6)
    _write_checkpoint(candidate, checkpoint_id="500", score=0.7)
    manifest = read_json(candidate / "manifest.json")
    manifest["checkpoint"][changed_field] = changed_value
    _write_json(candidate / "manifest.json", manifest)
    policy = tmp_path / "posttrain.policy.yaml"
    _write_policy(policy)

    payload = run_posttrain_gate(
        baseline_dir=baseline,
        candidate_dir=candidate,
        policy_path=policy,
        out_dir=tmp_path / "gate",
    )

    assert payload["decision"] == "hold"
    assert violation in payload["checks"]["provenance"]["violations"]


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


def test_posttrain_gate_marks_generation_saturation_as_insufficient_evidence(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "checkpoint-000"
    candidate = tmp_path / "checkpoint-500"
    _write_checkpoint(baseline, checkpoint_id="000", score=0.6)
    _write_checkpoint(candidate, checkpoint_id="500", score=0.7)
    mismatch_path = candidate / "diagnostics/generation_mismatch.json"
    mismatch = read_json(mismatch_path)
    mismatch["generation_saturation_rate"] = 0.1
    _write_json(mismatch_path, mismatch)
    policy = tmp_path / "posttrain.policy.yaml"
    _write_policy(policy)

    payload = run_posttrain_gate(
        baseline_dir=baseline,
        candidate_dir=candidate,
        policy_path=policy,
        out_dir=tmp_path / "gate",
    )

    assert payload["decision"] == "insufficient_evidence"
    assert "candidate:diagnostics.generation_mismatch.generation_saturation_rate" in payload[
        "invalid_evidence"
    ]


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
