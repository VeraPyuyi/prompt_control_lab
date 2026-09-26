"""Operational comparison metrics preserve paired scope, unknowns, and zero values."""

from __future__ import annotations

import json
from typing import Any

import pytest

from promptcontrollab.evaluation.experiments.assessment import assess
from promptcontrollab.evaluation.experiments.models import ExperimentSpec


def _spec(count: int = 2) -> dict[str, Any]:
    return ExperimentSpec.from_json(
        {
            "data": [
                {"id": str(index), "input": f"task {index}", "expected": "yes"}
                for index in range(count)
            ],
            "baseline": {"provider": "openai", "model": "test", "prompt": "baseline"},
            "candidate": {"provider": "openai", "model": "test", "prompt": "candidate"},
            "budget": {"input_cost_per_million": 2, "output_cost_per_million": 3},
        }
    ).to_json()


def _row(item: int, score: float, **extra: Any) -> dict[str, Any]:
    return {
        "id": str(item),
        "status": "completed",
        "score": score,
        "output_status": "scored",
        **extra,
    }


def _assess(
    spec: dict[str, Any],
    baseline: list[dict[str, Any]],
    candidate: list[dict[str, Any]],
    scope: str = "evaluation",
) -> dict[str, Any]:
    return assess(
        spec,
        baseline,
        candidate,
        expected_ids=[task["id"] for task in spec["data"]],
        scope=scope,
        budget={"unknown_cost_calls": 0},
    )


def test_matched_resources_keep_zero_and_compute_only_complete_deltas() -> None:
    baseline = [
        _row(0, 0, latency_ms=0, usage={"input_tokens": 0, "output_tokens": 0}, actual_cost=0),
        _row(1, 1, latency_ms=20, usage={"input_tokens": 2, "output_tokens": 4}),
    ]
    candidate = [
        _row(0, 1, latency_ms=10, usage={"input_tokens": 0, "output_tokens": 0}, actual_cost=0),
        _row(1, 1, latency_ms=30, usage={"input_tokens": 4, "output_tokens": 8}),
    ]
    result = _assess(_spec(), baseline, candidate)
    practical = result["practical"]
    assert practical["baseline"]["score_mean"] == 0.5
    assert practical["candidate"]["score_mean"] == 1
    assert practical["baseline"]["latency_known_count"] == 2
    assert practical["baseline"]["mean_latency_ms"] == 10
    assert practical["baseline"]["mean_input_tokens"] == 1
    assert practical["baseline"]["mean_output_tokens"] == 2
    assert practical["baseline"]["cost_known_count"] == 2
    assert practical["baseline"]["known_cost"] == pytest.approx(0.000016)
    assert practical["delta"]["mean_latency_ms"] == 10
    assert practical["delta"]["mean_input_tokens"] == 1
    assert practical["delta"]["mean_output_tokens"] == 2
    assert practical["delta"]["cost"] == pytest.approx(0.000016)
    assert result["next_action"] == practical["next_action"]
    assert result["evidence_range"] == practical["evidence_range"]


def test_unknown_and_nonfinite_measurements_never_become_zero_or_delta() -> None:
    spec = _spec(1)
    spec["budget"].pop("input_cost_per_million")
    baseline = [
        _row(
            0,
            0,
            latency_ms=float("nan"),
            actual_cost=float("inf"),
            usage={"input_tokens": True, "output_tokens": -1},
        )
    ]
    candidate = [
        _row(0, 1, latency_ms=0, actual_cost=0, usage={"input_tokens": 0, "output_tokens": 0})
    ]
    practical = _assess(spec, baseline, candidate)["practical"]
    assert practical["baseline"]["mean_latency_ms"] is None
    assert practical["baseline"]["known_input_tokens"] is None
    assert practical["baseline"]["input_tokens_known_count"] == 0
    assert practical["candidate"]["mean_latency_ms"] == 0
    assert practical["candidate"]["known_input_tokens"] == 0
    assert practical["candidate"]["known_cost"] is None
    assert practical["candidate"]["cost_status"] == "unknown"
    assert practical["delta"]["cost"] is None
    assert practical["delta"]["mean_latency_ms"] is None
    assert practical["delta"]["mean_input_tokens"] is None
    json.dumps(practical, allow_nan=False)


def test_quality_counts_include_unmatched_completed_outputs_with_explicit_denominator() -> None:
    baseline = [
        _row(0, 0, output_status="parse_error"),
        {"id": "1", "status": "service_error", "score": None},
    ]
    candidate = [_row(0, 1), _row(1, 0, output_status="empty_output")]
    result = _assess(_spec(), baseline, candidate)
    base, cand = result["practical"]["baseline"], result["practical"]["candidate"]
    assert base["matched_count"] == cand["matched_count"] == 1
    assert base["parse_error_count"] == 1
    assert base["unavailable_count"] == 1
    assert cand["quality_observed_count"] == 2
    assert cand["empty_output_count"] == cand["format_error_count"] == 1
    assert cand["score_mean"] == 1
    assert result["next_action"]["code"] == "complete_coverage"


def test_no_matched_observations_have_null_means_and_bilingual_evidence() -> None:
    result = _assess(_spec(1), [], [])
    practical = result["practical"]
    assert practical["baseline"]["score_mean"] is None
    assert practical["baseline"]["known_cost"] is None
    assert practical["baseline"]["mean_input_tokens"] is None
    assert practical["delta"]["score_mean"] is None
    assert practical["evidence_range"]["matched"] == 0
    assert "0 matched" in practical["evidence_range"]["en"]
    assert "完整输出" in practical["evidence_range"]["zh"]
    assert result["next_action"]["en"] and result["next_action"]["zh"]


def test_format_metric_keeps_lower_is_better_and_demo_action_is_explicit() -> None:
    spec = _spec(1)
    spec.update(metric="format_error", synthetic=True)
    result = _assess(spec, [_row(0, 1, output_status="empty_output")], [_row(0, 0)])
    assert result["practical"]["baseline"]["format_error_count"] == 1
    assert result["practical"]["delta"]["score_mean"] == -1
    assert result["practical"]["score_direction"] == "lower_is_better"
    assert result["next_action"]["code"] == "run_real_evaluation"


def test_finite_cost_aggregate_overflow_remains_unknown() -> None:
    rows = [_row(index, 1, actual_cost=1e308, latency_ms=1e308) for index in range(2)]
    practical = _assess(_spec(), rows, rows)["practical"]
    assert practical["baseline"]["mean_latency_ms"] == 1e308
    assert practical["baseline"]["known_cost"] is None
    assert practical["baseline"]["cost_status"] == "unknown"
    assert practical["delta"]["cost"] is None
    json.dumps(practical, allow_nan=False)
