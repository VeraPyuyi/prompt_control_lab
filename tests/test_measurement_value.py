"""Budget accounting and label separation for the bounded public research case."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from promptcontrollab.measurement_value import analyze_document, fixed_order, locked_decision


def case() -> dict[str, Any]:
    """Synthetic test values, never empirical evidence."""
    return {
        "model": "synthetic-model",
        "pair": "synthetic-pair",
        "item_ids": ["a", "b", "c", "d"],
        "scores": {"loss": [4, 3, 2, 1], "primary": [4, 4, 2, 1], "norm": [1, 2, 3, 4]},
        "behavior": {"risk_source": [0, 1, 0, 1], "risk_target": [1, 0, 0, 1]},
        "costs": {
            "generation_pair_seconds": [1, 1, 1, 1],
            "budget_seconds": 4,
            "direct_sort_seconds": 0,
            "scan_seconds": {"loss": 1, "primary": 2, "norm": 0},
            "sort_seconds": {"loss": 0, "primary": 0, "norm": 0},
            "probe_seconds": 1.5,
            "selection_seconds": 0.5,
        },
    }


def document(value: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema_version": "measurement-value/v1",
        "evidence_status": "historical_observation",
        "synthetic": True,
        "provenance": {"description": "SYNTHETIC TEST ONLY"},
        "cases": [case() if value is None else value],
    }


def rows(value: dict[str, Any] | None = None) -> dict[str, Any]:
    return {row["strategy"]: row for row in analyze_document(document(value))["rows"]}


def decision() -> dict[str, Any]:
    context = {"model": "m", "pair": "p", "decode_cap": 8, "budget_seconds": 100}
    return {
        "schema_version": "measurement-value-decision/v1",
        "phase": "before_probe",
        "evidence_status": "locked_prediction",
        "context": context,
        "forecast": {
            "freeze_id": "synthetic-locked-test",
            "frozen": True,
            "basis": "full_cost_net_discoveries",
            "validity_scope": dict(context),
            "uniform_action": "loss",
            "baseline_discoveries": {"direct": 10, "loss": 9, "uniform": 9},
            "paid_discoveries": {"direct": 8, "loss": 7, "primary": 10.5, "norm": 9},
        },
    }


def post_probe_decision() -> dict[str, Any]:
    value = decision()
    value["phase"] = "after_probe"
    value["incurred_costs"] = {"probe_seconds": 1.5, "selection_seconds": 0.5}
    value["control_diagnostics"] = {
        "status": "valid",
        "validity_scope": dict(value["context"]),
        "features": {"x6": 0.2},
    }
    return value


def test_costs_reduce_complete_audits_even_with_higher_precision() -> None:
    result = rows()
    assert set(result) == {
        "direct",
        "loss",
        "primary",
        "norm",
        "paid_direct",
        "paid_loss",
        "paid_primary",
        "paid_norm",
    }
    assert (result["direct"]["K"], result["direct"]["Y"]) == (4, 2)
    primary = result["primary"]
    assert (primary["K"], primary["Y"], primary["p"], primary["delta_Y"]) == (2, 2, 1, 0)
    assert primary["decomposition"] == {
        "status": "defined",
        "precision_gain": "1",
        "capacity_loss": "1",
        "difference": 0,
    }
    assert result["paid_direct"]["K"] == 2
    assert result["paid_direct"]["upfront_seconds"] == 2
    assert result["paid_loss"]["precision_threshold"] == 2
    assert result["paid_loss"]["precision_threshold_gt_one"] is True


def test_both_risk_directions_count_and_sum_to_discoveries() -> None:
    for row in rows().values():
        assert row["Y"] == row["risk_increases"] + row["risk_decreases"]
    direct = rows()["direct"]
    assert direct["risk_increases"] == direct["risk_decreases"] == 1


def test_fixed_orders_are_descending_with_sha256_ties() -> None:
    value = case()
    assert fixed_order(value, "loss") == ["a", "b", "c", "d"]
    assert fixed_order(value, "primary") == ["b", "a", "c", "d"]
    assert fixed_order(value, "direct") == ["d", "c", "b", "a"]
    value["behavior"] = {"risk_source": [1] * 4, "risk_target": [0] * 4}
    value["costs"]["generation_pair_seconds"] = [100, 0, 0, 0]
    assert fixed_order(value, "primary") == ["b", "a", "c", "d"]


def test_cannot_skip_expensive_item_to_complete_later_cheap_audits() -> None:
    value = case()
    value["costs"].update({"budget_seconds": 3, "generation_pair_seconds": [2.5, 100, 0.1, 0.1]})
    value["costs"]["scan_seconds"]["loss"] = 0
    loss = rows(value)["loss"]
    assert loss["completed_item_ids"] == ["a"]
    assert loss["audit_seconds"] == 2.5
    assert loss["unspent_seconds"] == 0.5


def test_decimal_budget_boundary_includes_only_complete_pairs() -> None:
    value = case()
    value["costs"].update(
        {
            "budget_seconds": 0.3,
            "direct_sort_seconds": 0.1,
            "generation_pair_seconds": [0.1] * 4,
        }
    )
    direct = rows(value)["direct"]
    assert direct["K"] == 2
    assert direct["required_seconds"] == 0.3
    assert direct["unspent_seconds"] == 0


def test_zero_audits_preserve_counts_and_undefined_precision() -> None:
    zero = rows()["paid_primary"]
    assert (zero["K"], zero["Y"], zero["p"], zero["delta_Y"]) == (0, 0, None, -2)
    assert zero["precision_threshold"] is None
    assert zero["precision_threshold_gt_one"] is None
    assert zero["decomposition"] == {
        "status": "count_extension",
        "precision_gain": "0",
        "capacity_loss": "2",
        "difference": -2,
    }
    value = case()
    value["costs"]["direct_sort_seconds"] = 5
    result = rows(value)
    assert result["direct"]["overhead_exceeds_budget"] is True
    assert result["loss"]["delta_Y"] == 2
    assert result["loss"]["decomposition"] == {
        "status": "undefined_baseline_precision",
        "precision_gain": None,
        "capacity_loss": None,
        "difference": 2,
    }


def test_exact_fractional_decomposition_allows_more_audits_than_direct() -> None:
    value = case()
    value["costs"]["direct_sort_seconds"] = 1
    value["costs"]["scan_seconds"]["loss"] = 0
    loss = rows(value)["loss"]
    assert (loss["K_0"], loss["Y_0"], loss["K"], loss["Y"]) == (3, 1, 4, 2)
    assert loss["decomposition"] == {
        "status": "defined",
        "precision_gain": "2/3",
        "capacity_loss": "-1/3",
        "difference": 1,
    }


def test_missing_paid_costs_are_not_assumed_to_be_free() -> None:
    value = case()
    del value["costs"]["probe_seconds"]
    del value["costs"]["selection_seconds"]
    result = analyze_document(document(value))
    assert len(result["rows"]) == 4
    assert result["cases"][0]["paid_cost_status"] == "not_supplied"
    value["costs"]["probe_seconds"] = 0
    with pytest.raises(ValueError, match="together"):
        analyze_document(document(value))


@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf"), True, "1"])
def test_invalid_costs_are_rejected(bad: Any) -> None:
    value = case()
    value["costs"]["generation_pair_seconds"][0] = bad
    with pytest.raises(ValueError, match="generation_pair_seconds"):
        analyze_document(document(value))


@pytest.mark.parametrize("change", ["ids", "length", "score", "labels", "coordinate"])
def test_malformed_or_ambiguous_source_coordinates_are_rejected(change: str) -> None:
    value = document()
    sample = value["cases"][0]
    if change == "ids":
        sample["item_ids"][0] = sample["item_ids"][1]
    elif change == "length":
        sample["scores"]["loss"].pop()
    elif change == "score":
        sample["scores"]["norm"][0] = float("nan")
    elif change == "labels":
        sample["behavior"]["risk_source"][0] = 0.2
    else:
        value["cases"].append(copy.deepcopy(sample))
    with pytest.raises(ValueError):
        analyze_document(value)


def test_evidence_status_is_explicit_and_never_inferred_from_data() -> None:
    value = document()
    for status in ("historical_observation", "locked_prediction"):
        value["evidence_status"] = status
        assert analyze_document(value)["evidence_status"] == status
    value["evidence_status"] = "independent_confirmation"
    with pytest.raises(ValueError, match="actual linked"):
        analyze_document(value)
    del value["evidence_status"]
    with pytest.raises(ValueError, match="evidence_status"):
        analyze_document(value)


def test_label_changes_cannot_change_queues_or_completed_prefix() -> None:
    first = analyze_document(document())
    value = case()
    value["behavior"] = {"risk_source": [1] * 4, "risk_target": [1] * 4}
    second = analyze_document(document(value))
    assert first["cases"][0]["orders"] == second["cases"][0]["orders"]
    for left, right in zip(first["rows"], second["rows"], strict=True):
        assert left["completed_item_ids"] == right["completed_item_ids"]
        assert left["K"] == right["K"]
    assert any(
        left["Y"] != right["Y"] for left, right in zip(first["rows"], second["rows"], strict=True)
    )


def test_locked_decision_uses_paid_net_forecast_at_five_percent_boundary() -> None:
    result = locked_decision(decision())
    assert result["selected_strategy"] == "paid_primary"
    assert result["best_baseline_discoveries"] == 10
    assert result["required_paid_discoveries"] == 10.5
    assert result["evidence_status"] == "locked_prediction"


def test_uniform_is_a_frozen_action_baseline_and_best_baseline_must_be_beaten() -> None:
    value = decision()
    value["forecast"]["baseline_discoveries"]["uniform"] = 11
    result = locked_decision(value)
    assert result["selected_strategy"] == "direct"
    assert result["best_baseline_discoveries"] == 11
    assert result["uniform_action"] == "loss"


def test_paid_tie_falls_back_to_direct() -> None:
    value = decision()
    value["forecast"]["paid_discoveries"]["norm"] = 10.5
    assert locked_decision(value)["selected_strategy"] == "direct"


def test_zero_baseline_requires_one_full_predicted_discovery() -> None:
    value = decision()
    value["forecast"]["baseline_discoveries"] = dict.fromkeys(("direct", "loss", "uniform"), 0)
    value["forecast"]["paid_discoveries"] = {"direct": 0, "loss": 0, "primary": 0.99, "norm": 0}
    assert locked_decision(value)["selected_strategy"] == "direct"
    value["forecast"]["paid_discoveries"]["primary"] = 1
    assert locked_decision(value)["selected_strategy"] == "paid_primary"


@pytest.mark.parametrize("failure", ["unfrozen", "scope", "basis", "status", "missing"])
def test_unusable_forecast_is_explicit_insufficient_evidence(failure: str) -> None:
    value = decision()
    if failure == "unfrozen":
        value["forecast"]["frozen"] = False
    elif failure == "scope":
        value["forecast"]["validity_scope"]["decode_cap"] = 64
    elif failure == "basis":
        value["forecast"]["basis"] = "gross_before_costs"
    elif failure == "status":
        value["forecast"]["status"] = "failed"
    else:
        del value["forecast"]["baseline_discoveries"]["uniform"]
    result = locked_decision(value)
    assert result["decision"] == "insufficient_evidence"
    assert result["selected_strategy"] == "direct"


def test_pre_probe_rejects_expensive_controls_and_after_probe_is_distinct() -> None:
    value = decision()
    value["control_diagnostics"] = {"primary": [1], "certificate": "computed"}
    with pytest.raises(ValueError, match="before_probe"):
        locked_decision(value)
    assert locked_decision(post_probe_decision())["selected_strategy"] == "paid_primary"
    del value["control_diagnostics"]
    value["scores"] = {"primary": [1]}
    with pytest.raises(ValueError, match="before_probe"):
        locked_decision(value)


@pytest.mark.parametrize(
    "failure",
    [
        "tie",
        "gain",
        "missing_forecast",
        "unfrozen",
        "scope",
        "basis",
        "failed_forecast",
        "missing_counts",
        "invalid_counts",
        "missing_freeze_id",
        "invalid_uniform",
        "evidence_status",
    ],
)
def test_all_post_probe_direct_fallbacks_retain_paid_identity_and_costs(failure: str) -> None:
    value = post_probe_decision()
    if failure == "tie":
        value["forecast"]["paid_discoveries"]["norm"] = 10.5
    elif failure == "gain":
        value["forecast"]["paid_discoveries"]["primary"] = 10.4
    elif failure == "missing_forecast":
        del value["forecast"]
    elif failure == "unfrozen":
        value["forecast"]["frozen"] = False
    elif failure == "scope":
        value["forecast"]["validity_scope"]["decode_cap"] = 64
    elif failure == "basis":
        value["forecast"]["basis"] = "gross"
    elif failure == "failed_forecast":
        value["forecast"]["status"] = "failed"
    elif failure == "missing_counts":
        del value["forecast"]["baseline_discoveries"]["uniform"]
    elif failure == "invalid_counts":
        value["forecast"]["paid_discoveries"]["primary"] = float("nan")
    elif failure == "missing_freeze_id":
        del value["forecast"]["freeze_id"]
    elif failure == "invalid_uniform":
        value["forecast"]["uniform_action"] = "random"
    else:
        value["evidence_status"] = "historical_observation"
    result = locked_decision(value)
    assert result["selected_strategy"] == "paid_direct"
    assert result["incurred_costs"] == {"probe_seconds": 1.5, "selection_seconds": 0.5}
    assert result["incurred_seconds"] == 2


@pytest.mark.parametrize(
    "failure",
    [
        "missing",
        "null",
        "failed_status",
        "empty_features",
        "nan",
        "infinity",
        "boolean",
        "string",
        "array",
        "scope",
        "certificate_failed",
    ],
)
def test_unusable_post_probe_controls_fall_back_to_paid_source_uniform(failure: str) -> None:
    value = post_probe_decision()
    if failure == "missing":
        del value["control_diagnostics"]
    elif failure == "null":
        value["control_diagnostics"] = None
    elif failure == "failed_status":
        value["control_diagnostics"]["status"] = "failed"
    elif failure == "empty_features":
        value["control_diagnostics"]["features"] = {}
    elif failure in {"nan", "infinity", "boolean", "string", "array"}:
        invalid = {
            "nan": float("nan"),
            "infinity": float("inf"),
            "boolean": True,
            "string": "0.2",
            "array": [0.2],
        }
        value["control_diagnostics"]["features"]["x6"] = invalid[failure]
    elif failure == "scope":
        value["control_diagnostics"]["validity_scope"]["pair"] = "another-pair"
    else:
        value["control_diagnostics"] = {
            "primary": float("nan"),
            "certificate": "failed",
            "status": "failed",
        }
    result = locked_decision(value)
    assert result["selected_strategy"] == "paid_loss"
    assert result["decision"] == "fallback_uniform"
    assert result["control_diagnostics_status"] == "invalid"
    assert result["incurred_costs"] == value["incurred_costs"]
    assert result["incurred_seconds"] == 2


@pytest.mark.parametrize("failure", ["missing", "invalid", "scope", "unfrozen", "freeze_id"])
def test_invalid_controls_without_valid_source_uniform_keep_paid_direct(failure: str) -> None:
    value = post_probe_decision()
    value["control_diagnostics"] = None
    if failure == "missing":
        del value["forecast"]["uniform_action"]
    elif failure == "invalid":
        value["forecast"]["uniform_action"] = "random"
    elif failure == "scope":
        value["forecast"]["validity_scope"]["decode_cap"] = 64
    elif failure == "unfrozen":
        value["forecast"]["frozen"] = False
    else:
        del value["forecast"]["freeze_id"]
    result = locked_decision(value)
    assert result["selected_strategy"] == "paid_direct"
    assert result["decision"] == "insufficient_evidence"
    assert result["incurred_costs"] == value["incurred_costs"]
    assert result["incurred_seconds"] == 2


def test_post_probe_forecast_can_explicitly_declare_no_control_dependency() -> None:
    value = post_probe_decision()
    value["forecast"]["requires_control_diagnostics"] = False
    del value["control_diagnostics"]
    result = locked_decision(value)
    assert result["selected_strategy"] == "paid_primary"
    assert result["incurred_seconds"] == 2
    assert result["required_paid_discoveries"] == 10.5
    assert result["best_paid_discoveries"] == 10.5
    value["control_diagnostics"] = None
    assert locked_decision(value)["selected_strategy"] == "paid_loss"


def test_valid_post_probe_controls_and_labels_do_not_reestimate_forecasts() -> None:
    value = post_probe_decision()
    expected = locked_decision(value)
    value["control_diagnostics"]["features"]["x6"] = 1000
    value["behavior"] = {"risk_source": [0, 0], "risk_target": [1, 1]}
    assert locked_decision(value) == expected
    assert expected["selected_strategy"] == "paid_primary"
    assert expected["best_paid_discoveries"] == 10.5
    assert expected["incurred_seconds"] == 2


@pytest.mark.parametrize(
    "invalid",
    [
        None,
        {},
        {"probe_seconds": 1.5},
        {"probe_seconds": float("nan"), "selection_seconds": 0},
        {"probe_seconds": -1, "selection_seconds": 0},
    ],
)
def test_post_probe_requires_an_actual_finite_cost_ledger(invalid: Any) -> None:
    value = post_probe_decision()
    value["incurred_costs"] = invalid
    with pytest.raises(ValueError, match="incurred_costs"):
        locked_decision(value)


def test_before_probe_rejects_an_incurred_probe_cost_ledger() -> None:
    value = decision()
    value["incurred_costs"] = {"probe_seconds": 1.5, "selection_seconds": 0.5}
    with pytest.raises(ValueError, match="before_probe"):
        locked_decision(value)


@pytest.mark.parametrize(
    "probe, selection, budget, balance, status",
    [
        (101, 0, 100, -1, "exceeded"),
        (99, 2, 100, -1, "exceeded"),
        (100, 0, 100, 0, "exhausted"),
        (0.1, 0.2, 0.3, 0, "exhausted"),
        (0, 0, 0, 0, "exhausted"),
    ],
)
@pytest.mark.parametrize("controls", ["valid", "invalid", "not_required"])
def test_exhausted_actual_budget_stops_before_every_control_or_forecast_path(
    probe: float,
    selection: float,
    budget: float,
    balance: float,
    status: str,
    controls: str,
) -> None:
    value = post_probe_decision()
    value["context"]["budget_seconds"] = budget
    value["forecast"]["validity_scope"]["budget_seconds"] = budget
    value["control_diagnostics"]["validity_scope"]["budget_seconds"] = budget
    value["incurred_costs"] = {"probe_seconds": probe, "selection_seconds": selection}
    if controls == "invalid":
        value["control_diagnostics"] = None
    elif controls == "not_required":
        value["forecast"]["requires_control_diagnostics"] = False
        del value["control_diagnostics"]
    result = locked_decision(value)
    assert result["decision"] == "insufficient_evidence"
    assert result["selected_strategy"] == "paid_direct"
    assert result["incurred_costs"] == value["incurred_costs"]
    assert result["incurred_seconds"] == pytest.approx(probe + selection)
    assert result["remaining_budget_seconds"] == balance
    assert result["budget_status"] == status
    assert result["further_evaluation_allowed"] is False
    assert "best_paid_discoveries" not in result


def test_positive_actual_budget_preserves_external_net_forecast() -> None:
    result = locked_decision(post_probe_decision())
    assert result["remaining_budget_seconds"] == 98
    assert result["budget_status"] == "available"
    assert result["further_evaluation_allowed"] is True
    assert result["selected_strategy"] == "paid_primary"
    assert result["best_paid_discoveries"] == 10.5


def test_finite_scan_and_sort_with_unrepresentable_total_raise_validation_error() -> None:
    value = case()
    value["costs"]["scan_seconds"]["loss"] = 1e308
    value["costs"]["sort_seconds"]["loss"] = 1e308
    with pytest.raises(ValueError, match=r"upfront_seconds.*finite"):
        analyze_document(document(value))


def test_unrepresentable_incurred_total_raises_validation_error() -> None:
    value = post_probe_decision()
    value["incurred_costs"] = {"probe_seconds": 1e308, "selection_seconds": 1e308}
    with pytest.raises(ValueError, match=r"incurred_seconds.*finite"):
        locked_decision(value)


def test_decision_ignores_behavior_labels_entirely() -> None:
    value = decision()
    expected = locked_decision(value)
    value["behavior"] = {"risk_source": [0, 1], "risk_target": [1, 0]}
    assert locked_decision(value) == expected
    value["behavior"] = {"anything": "not inspected"}
    assert locked_decision(value) == expected


def test_script_runs_without_installed_package_and_writes_deterministic_artifacts(
    tmp_path: Path,
) -> None:
    source = tmp_path / "input.json"
    source.write_text(json.dumps(document()), encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_measurement_value_case.py"
    for destination in (tmp_path / "first", tmp_path / "second"):
        completed = subprocess.run(
            [sys.executable, "-S", str(script), "--input", str(source), "--out", str(destination)],
            check=False,
            capture_output=True,
            text=True,
            cwd=tmp_path,
        )
        assert completed.returncode == 0, completed.stderr
    names = {"results.json", "strategies.csv", "report.md", "report.zh.md"}
    assert {path.name for path in (tmp_path / "first").iterdir()} == names
    for name in names:
        first = (tmp_path / "first" / name).read_bytes()
        assert first == (tmp_path / "second" / name).read_bytes()
    output = json.loads((tmp_path / "first" / "results.json").read_text(encoding="utf-8"))
    assert output["input_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert "SYNTHETIC" in (tmp_path / "first" / "report.md").read_text(encoding="utf-8")
    assert "合成" in (tmp_path / "first" / "report.zh.md").read_text(encoding="utf-8")


def test_script_refuses_to_overwrite_its_input_fixture(tmp_path: Path) -> None:
    source = tmp_path / "results.json"
    original = json.dumps(document()).encode("utf-8")
    source.write_bytes(original)
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_measurement_value_case.py"
    completed = subprocess.run(
        [sys.executable, "-S", str(script), "--input", str(source), "--out", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert source.read_bytes() == original
    assert "overwrite" in completed.stderr


def test_published_historical_bytes_reproduce_the_supplied_baseline_receipt() -> None:
    directory = Path(__file__).resolve().parents[1] / "docs" / "case_studies" / "measurement_value"
    source_bytes = (directory / "source_records.json").read_bytes()
    source = json.loads(source_bytes)
    result = analyze_document(source)
    assert result["evidence_status"] == "historical_observation"
    assert result["synthetic"] is False
    assert len(result["cases"]) == 54
    assert all(len(value["item_ids"]) == 400 for value in source["cases"])
    expected = {
        ("ministral", "direct"): (19, 1144),
        ("ministral", "loss"): (19, 706),
        ("granite", "direct"): (19, 1286),
        ("granite", "loss"): (19, 626),
        ("qwen35", "direct"): (16, 690),
        ("qwen35", "loss"): (16, 516),
    }
    for (model, strategy), (pairs, discoveries) in expected.items():
        selected = [
            row for row in result["rows"] if row["model"] == model and row["strategy"] == strategy
        ]
        assert len(selected) == pairs
        assert sum(row["Y"] for row in selected) == discoveries
    result["input_sha256"] = hashlib.sha256(source_bytes).hexdigest()
    packaged = json.loads((directory / "historical_replay" / "results.json").read_bytes())
    assert result == packaged
