"""Independent compact AUC replay and immutable forecast-input boundaries."""

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from promptcontrollab.transfer_prediction import analyze_document, binary_auc, fixed_predictions


@pytest.fixture
def example() -> dict[str, Any]:
    pair = {
        "model": "synthetic-model",
        "pair_id": "one",
        "left_seed": 1,
        "right_seed": 2,
        "pairing_type": "adjacent_seed",
        "item_ids": ["a", "b", "c", "d"],
        "scores": {"loss": [1, 2, 3, 4], "primary": [3, 4, 1, 2], "norm": [2, 2, 1, 1]},
        "behavior": {"risk_source": [0, 0, 0, 1], "risk_target": [1, 1, 0, 1]},
        "predictions": {
            score: {"full": 0.8, "cheap": 0.6, "uniform_mean": 0.5, "zero": 0}
            for score in ("primary", "norm")
        },
    }
    return {
        "schema_version": "control-transfer/v1",
        "synthetic": True,
        "evidence_status": "historical_observation",
        "endpoint_policy": "disjoint",
        "prediction_lock_sha256": "a" * 64,
        "pairs": [pair],
    }


def test_midrank_auc_and_fixed_errors(example: Any) -> None:
    assert binary_auc([1, 1, 2, 2], [1, 0, 1, 0]) == 0.5
    assert binary_auc([1, 2], [1, 1]) is None
    result = analyze_document(example)
    pair = result["pairs"][0]
    assert pair["auc"] == {"loss": 0.0, "primary": 1.0, "norm": 1.0}
    assert pair["gains"] == {"primary": 1.0, "norm": 1.0}
    assert pair["errors"]["primary"]["full"]["absolute"] == pytest.approx(0.2)
    assert result["summaries"][0]["mae_improvement"]["zero"] == pytest.approx(0.8)


def test_distinct_large_integer_scores_are_not_rounded_into_ties(example: Any) -> None:
    assert binary_auc([2**53, 2**53 + 1], [0, 1]) == 1.0
    example["pairs"][0]["scores"]["loss"] = [2**53, 2**53 + 1, 0, 0]
    example["pairs"][0]["behavior"] = {"risk_change": [0, 1, 0, 0]}
    assert analyze_document(example)["pairs"][0]["auc"]["loss"] == 1.0


def test_predictions_are_label_score_independent_and_not_mutated(example: Any) -> None:
    before = deepcopy(example)
    expected = fixed_predictions(example)
    example["pairs"][0]["behavior"] = {"malformed": "ignored by prediction reader"}
    example["pairs"][0]["scores"] = None
    assert fixed_predictions(example) == expected
    assert before["pairs"][0]["predictions"] == example["pairs"][0]["predictions"]


def test_pending_forecast_record_rejects_labels(example: Any) -> None:
    example["evidence_status"] = "locked_prediction"
    with pytest.raises(ValueError, match="omit behavior"):
        analyze_document(example)
    example["pairs"][0].pop("behavior")
    result = analyze_document(example)
    assert result["pairs"][0]["status"] == "awaiting_behavior"
    assert result["summaries"][0]["mae"]["full"] is None


def test_undefined_retained_not_half_or_zero(example: Any) -> None:
    example["pairs"][0]["behavior"]["risk_target"] = [0, 0, 0, 1]
    result = analyze_document(example)
    assert result["pairs"][0]["status"] == "undefined_auc"
    assert result["pairs"][0]["gains"]["primary"] is None
    assert result["summaries"][0]["common_valid_pairs"] == 0


def test_explicit_change_labels_do_not_invent_endpoint_direction(example: Any) -> None:
    paired = analyze_document(example)
    example["pairs"][0]["behavior"] = {"risk_change": [1, 1, 0, 0]}
    compact = analyze_document(example)
    assert compact["summaries"] == paired["summaries"]
    assert compact["pairs"][0]["risk_increases"] is None
    assert compact["pairs"][0]["risk_decreases"] is None


def test_shared_endpoints_and_inconsistent_mean_rejected(example: Any) -> None:
    second = deepcopy(example["pairs"][0])
    second["pair_id"] = "two"
    example["pairs"].append(second)
    with pytest.raises(ValueError, match="Shared endpoint"):
        analyze_document(example)
    second.update(left_seed=3, right_seed=4)
    second["predictions"]["norm"]["uniform_mean"] = 0.25
    with pytest.raises(ValueError, match="common to the model"):
        analyze_document(example)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "1"])
def test_invalid_scores_rejected(example: Any, value: Any) -> None:
    example["pairs"][0]["scores"]["loss"][0] = value
    with pytest.raises(ValueError):
        analyze_document(example)


def test_script_runs_without_site_dependencies_and_labels_synthetic(
    tmp_path: Path, example: Any
) -> None:
    root = Path(__file__).resolve().parents[1]
    inp = tmp_path / "fixture.json"
    inp.write_text(json.dumps(example), encoding="utf-8")
    out = tmp_path / "report"
    result = subprocess.run(
        [
            sys.executable,
            "-S",
            str(root / "scripts/run_transfer_prediction_case.py"),
            "--input",
            str(inp),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "SYNTHETIC TEST DATA" in (out / "report.md").read_text(encoding="utf-8")
    assert "合成测试数据" in (out / "report.zh.md").read_text(encoding="utf-8")
    assert len((out / "pairs.csv").read_text().splitlines()) == 9
