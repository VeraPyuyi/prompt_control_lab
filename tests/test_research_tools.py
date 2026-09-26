"""Behavioral invariants and failure boundaries of the portable research tools."""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any

import pytest

from promptcontrollab.diagnostics.research_tools import analyze_research
from promptcontrollab.diagnostics.research_tools.common import digest, evidence
from promptcontrollab.diagnostics.research_tools.measurement_value import (
    analyze_document as measurement,
)
from promptcontrollab.diagnostics.research_tools.replay import compare_values

ROOT = Path(__file__).resolve().parents[1]


def fixture(kind: str) -> dict[str, Any]:
    value = json.loads(
        (ROOT / "examples/research-tools" / f"{kind}.json").read_text(encoding="utf-8")
    )
    assert isinstance(value, dict)
    return value


@pytest.mark.parametrize("kind", ["readout", "response", "measurement-value", "transfer", "replay"])
def test_all_tools_write_deterministic_bilingual_reports(kind: Any, tmp_path: Path) -> None:
    result = analyze_research(kind, fixture(kind), tmp_path / "first")
    repeated = analyze_research(kind, fixture(kind), tmp_path / "second")
    assert result == repeated
    for name in (
        "report.json",
        "metrics.csv",
        "report.en.md",
        "report.zh.md",
        "report.en.html",
        "report.zh.html",
    ):
        assert (tmp_path / "first" / name).read_bytes() == (tmp_path / "second" / name).read_bytes()
    assert "SYNTHETIC" in (tmp_path / "first/report.en.html").read_text(encoding="utf-8")
    assert "合成" in (tmp_path / "first/report.zh.html").read_text(encoding="utf-8")


def test_readout_preserves_parser_version_posthoc_and_distinct_targets(tmp_path: Path) -> None:
    result = analyze_research("readout", fixture("readout"), tmp_path)
    exact, numeric = result["conditions"]
    assert exact["samples"][0]["correctness_change"] == 0
    assert numeric["samples"][0]["correctness_change"] == 1
    assert numeric["samples"][0]["parse_switch"] == 0
    assert numeric["parser"] == {
        "rule": "last_number",
        "version": "last-number/v1",
        "posthoc": True,
    }
    assert (
        numeric["auc_gaps"]["correctness_change"]["primary"]
        != exact["auc_gaps"]["correctness_change"]["primary"]
    )


def test_readout_requires_token_evidence_for_derived_prefix(tmp_path: Path) -> None:
    doc = fixture("readout")
    endpoint = doc["conditions"][0]["samples"][0]["target"]
    endpoint["prefix_tokens"] = 1
    with pytest.raises(ValueError, match="token_ids"):
        analyze_research("readout", doc, tmp_path)
    endpoint.update(token_ids=[10, 20], token_texts=["Answer: ", "2"], tokenizer_id="synthetic/v1")
    result = analyze_research("readout", doc, tmp_path)
    assert "not a rerun" in result["conditions"][0]["samples"][0]["output_evidence"]["target"]
    endpoint["token_texts"] = ["A", "2"]
    with pytest.raises(ValueError, match="reconstruct"):
        analyze_research("readout", doc, tmp_path)


def test_response_recomputes_and_keeps_zero_distinct_from_null(tmp_path: Path) -> None:
    doc = fixture("response")
    row = analyze_research("response", doc, tmp_path)["rows"][0]
    assert row["loss_delta"] == -0.5
    assert row["response_gain"] == 2
    assert row["readout_alignment"] == 1
    assert row["subspace_fraction"] == 1
    assert row["approximation_residual"] == 0
    doc["records"][0]["control_after"] = [0, 0]
    doc["records"][0]["response_after"] = [0, 0]
    row = analyze_research("response", doc, tmp_path)["rows"][0]
    assert row["response_gain"] is None and row["readout_alignment"] is None
    assert row["subspace_fraction"] is None and row["approximation_residual"] == 0


@pytest.mark.parametrize("invalid", [True, float("nan"), float("inf"), "1"])
def test_response_rejects_nonfinite_boolean_and_coerced_inputs(
    invalid: Any, tmp_path: Path
) -> None:
    doc = fixture("response")
    doc["records"][0]["control_after"][0] = invalid
    with pytest.raises(ValueError):
        analyze_research("response", doc, tmp_path)


@pytest.mark.parametrize(
    "field,value",
    [("control_after", [1]), ("linear_response_matrix", [[1, 2]]), ("subspace_basis", [[2, 0]])],
)
def test_response_dimension_and_projection_checks(field: Any, value: Any, tmp_path: Path) -> None:
    doc = fixture("response")
    doc["records"][0][field] = value
    with pytest.raises(ValueError):
        analyze_research("response", doc, tmp_path)


def test_transmission_cost_counts_at_exact_budget_boundary() -> None:
    doc = fixture("measurement-value")
    costs = doc["cases"][0]["costs"]
    costs.update(
        generation_pair_seconds=[0.1] * 4,
        transmission_pair_seconds=[0.2] * 4,
        transmission_seconds=0.1,
        budget_seconds=0.4,
    )
    direct = next(row for row in measurement(doc)["rows"] if row["strategy"] == "direct")
    assert direct["K"] == 1 and direct["required_seconds"] == 0.4
    assert direct["unspent_seconds"] == 0
    costs["transmission_seconds"] = 0.5
    direct = next(row for row in measurement(doc)["rows"] if row["strategy"] == "direct")
    assert direct["K"] == 0 and direct["p"] is None and direct["overhead_exceeds_budget"]


def test_shared_endpoint_bootstrap_preserves_components_and_predictions(tmp_path: Path) -> None:
    doc = fixture("transfer")
    doc["endpoint_policy"] = "shared_fixed_cases"
    second = copy.deepcopy(doc["pairs"][0])
    second.update(pair_id="second", left_seed=2, right_seed=3)
    second["behavior"] = {"risk_change": [0, 1, 1, 0]}
    doc["pairs"].append(second)
    doc["pairs"][0]["behavior"] = {"risk_change": [1, 1, 0, 0]}
    before = copy.deepcopy(doc)
    result = analyze_research("transfer", doc, tmp_path)
    assert doc == before
    boot = result["bootstrap"]["models"][0]
    assert boot["endpoint_component_count"] == 1
    assert boot["endpoint_uncertainty"] == "conditional_on_one_connected_component"
    assert sorted(boot["endpoint_components"][0]) == sorted([doc["pairs"][0]["pair_id"], "second"])
    assert len(boot["intervals"]) == 6
    for source, row in zip(doc["pairs"], result["pairs"], strict=True):
        assert source["predictions"] == row["predictions"]


def test_shared_endpoint_conflicting_observations_rejected(tmp_path: Path) -> None:
    doc = fixture("transfer")
    doc["endpoint_policy"] = "shared_fixed_cases"
    second = copy.deepcopy(doc["pairs"][0])
    second.update(pair_id="conflicting", left_seed=2, right_seed=3)
    second["behavior"] = {"risk_source": [0, 0, 0, 0], "risk_target": [1, 1, 0, 0]}
    doc["pairs"].append(second)
    with pytest.raises(ValueError, match="Shared endpoint behavioral"):
        analyze_research("transfer", doc, tmp_path)


def test_undefined_auc_bootstrap_remains_null(tmp_path: Path) -> None:
    doc = fixture("transfer")
    doc["pairs"][0]["behavior"] = {"risk_change": [0, 0, 0, 0]}
    result = analyze_research("transfer", doc, tmp_path)
    assert result["pairs"][0]["auc"]["loss"] is None
    assert result["bootstrap"]["models"][0]["intervals"] is None


@pytest.mark.parametrize("kind", ["measurement-value", "transfer"])
def test_independent_confirmation_requires_actual_receipts(kind: Any, tmp_path: Path) -> None:
    doc = fixture(kind)
    doc["evidence_status"] = "independent_confirmation"
    doc["prediction_lock_sha256"] = "a" * 64
    with pytest.raises(ValueError, match="actual linked"):
        analyze_research(kind, doc, tmp_path)


def test_linked_receipts_are_not_authenticated_temporal_proof() -> None:
    doc: dict[str, Any] = {"evidence_status": "independent_confirmation", "synthetic": True}
    train, test = ["calibration/a"], ["evaluation/b"]
    payload = {"protocol": "synthetic", "calibration_ids_sha256": digest(train)}
    lock = {
        "payload": payload,
        "payload_sha256": digest(payload),
        "frozen_at": "2026-01-01T00:00:00Z",
    }
    doc["evidence_receipts"] = {
        "lock": lock,
        "evaluation": {
            "lock_sha256": digest(lock),
            "document_sha256": digest(doc),
            "started_at": "2026-01-02T00:00:00Z",
            "evaluation_ids_sha256": digest(test),
        },
        "cohorts": {"calibration_ids": train, "evaluation_ids": test},
    }
    result = evidence(doc)
    assert result["linked_receipts_verified"] is True
    assert result["temporal_independence_verified"] is False
    doc["evidence_receipts"]["lock"]["payload"]["protocol"] = "tampered"
    with pytest.raises(ValueError, match="hash mismatch"):
        evidence(doc)


def test_replay_numeric_tolerance_separate_from_integrity(tmp_path: Path) -> None:
    source = fixture("response")
    expected = analyze_research("response", source, tmp_path / "baseline")
    expected["rows"][0]["response_gain"] += 1e-10
    manifest: dict[str, Any] = {
        "schema_version": "research-replay/v1",
        "synthetic": True,
        "files": {
            "input.json": {"json": source, "sha256": "0" * 64},
            "expected.json": {"json": expected},
        },
        "checks": [
            {"kind": "response", "input_file": "input.json", "expected_file": "expected.json"}
        ],
        "tolerances": {"atol": 1e-8, "rtol": 0},
    }
    result = analyze_research("replay", manifest, tmp_path / "replay")
    assert result["integrity"]["status"] == "failed"
    assert result["numerical_replay"]["checks"][0]["status"] == "passed"
    manifest["tolerances"]["atol"] = 1e-12
    assert (
        analyze_research("replay", manifest, tmp_path / "strict")["numerical_replay"]["checks"][0][
            "status"
        ]
        == "failed"
    )
    assert compare_values(None, 0, atol=1, rtol=1)
    assert compare_values(True, 1, atol=1, rtol=1)


@pytest.mark.parametrize(
    "bad", ["../escape.json", "C:/absolute.json", "/absolute.json", "a\\b.json"]
)
def test_replay_rejects_external_and_escaping_names(bad: Any, tmp_path: Path) -> None:
    doc = fixture("replay")
    doc["files"][bad] = {"json": {}}
    with pytest.raises(ValueError, match="safe relative"):
        analyze_research("replay", doc, tmp_path)


def test_replay_rejects_commands_and_recursion(tmp_path: Path) -> None:
    doc = fixture("replay")
    doc["command"] = "echo never executed"
    with pytest.raises(ValueError, match="commands"):
        analyze_research("replay", doc, tmp_path)
    del doc["command"]
    doc["checks"][0]["kind"] = "replay"
    with pytest.raises(ValueError, match="recursive"):
        analyze_research("replay", doc, tmp_path)


def test_replay_reuses_local_posterior_certificate(tmp_path: Path) -> None:
    posterior = {
        "residual_norm_upper": 0.01,
        "jacobian_inverse_norm_upper": 1,
        "jacobian_lipschitz_upper": 1,
        "neighborhood_radius": 0.1,
    }
    doc = {
        "schema_version": "research-replay/v1",
        "synthetic": True,
        "files": {"local.json": {"json": posterior, "sha256": digest(posterior)}},
        "checks": [{"kind": "posterior-certificate", "input_file": "local.json"}],
    }
    result = analyze_research("replay", doc, tmp_path)
    row = result["theoretical_checks"]["checks"][0]
    assert row["status"] == "passed"
    assert row["result"]["h"] == 0.01
    assert row["certificate_level"] == "insufficient_evidence"
    assert "no entire-LLM proof" in row["claim_scope"]


def test_html_escapes_untrusted_record_metadata(tmp_path: Path) -> None:
    doc = fixture("response")
    doc["metadata"]["readout_definition"] = "<script>alert(1)</script>"
    analyze_research("response", doc, tmp_path)
    assert "<script>" not in (tmp_path / "report.en.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("kind", ["green-certificate", "terminal-sensitivity"])
def test_replay_reuses_other_local_certificate_modules(kind: Any, tmp_path: Path) -> None:
    pytest.importorskip("numpy")
    pytest.importorskip("scipy")
    if kind == "green-certificate":
        source = {
            "arrays": {"M": [[0.5, 0], [0, 2]], "B0": [[1, 0], [0, 0]], "BN": [[0, 0], [0, 1]]},
            "horizons": [8, 16, 32],
        }
    else:
        source = {
            "records": [
                {
                    "intervention_kind": "terminal_objective",
                    "horizon": horizon,
                    "early_step": 0,
                    "perturbation_norm": 1,
                    "control_delta_norm": math.exp(-0.1 * horizon),
                    "seed": seed,
                }
                for seed in (0, 1)
                for horizon in (8, 16, 32, 64)
            ]
        }
    doc = {
        "schema_version": "research-replay/v1",
        "synthetic": True,
        "files": {"input.json": {"json": source}},
        "checks": [{"kind": kind, "input_file": "input.json"}],
    }
    result = analyze_research("replay", doc, tmp_path)
    check = result["theoretical_checks"]["checks"][0]
    assert check["status"] == "passed"
    assert check["certificate_level"] in {"surrogate_consistent", "empirical_only"}
    assert str(tmp_path) not in json.dumps(result)


def test_readout_rejects_condition_specific_gold_changes(tmp_path: Path) -> None:
    doc = fixture("readout")
    doc["conditions"][1]["samples"][0]["gold_answer"] = "999"
    with pytest.raises(ValueError, match="same gold answers"):
        analyze_research("readout", doc, tmp_path)


def test_valid_linked_transfer_receipt_freezes_forecasts_and_actual_cohort(tmp_path: Path) -> None:
    doc = fixture("transfer")
    doc["evidence_status"] = "independent_confirmation"
    train = ["synthetic-model:99"]
    test = sorted(
        {
            f"{pair['model']}:{pair[key]}"
            for pair in doc["pairs"]
            for key in ("left_seed", "right_seed")
        }
    )
    forecasts = [
        {
            key: pair[key]
            for key in (
                "model",
                "pair_id",
                "left_seed",
                "right_seed",
                "pairing_type",
                "predictions",
            )
        }
        for pair in doc["pairs"]
    ]
    payload = {"forecasts_sha256": digest(forecasts), "calibration_ids_sha256": digest(train)}
    lock = {
        "payload": payload,
        "payload_sha256": digest(payload),
        "frozen_at": "2026-01-01T00:00:00Z",
    }
    doc["prediction_lock_sha256"] = digest(lock)
    evaluation = {
        "lock_sha256": digest(lock),
        "document_sha256": digest(doc),
        "started_at": "2026-01-02T00:00:00Z",
        "evaluation_ids_sha256": digest(test),
    }
    doc["evidence_receipts"] = {
        "lock": lock,
        "evaluation": evaluation,
        "cohorts": {"calibration_ids": train, "evaluation_ids": test},
    }
    result = analyze_research("transfer", doc, tmp_path)
    assert result["evidence"]["linked_receipts_verified"]
    assert not result["evidence"]["temporal_independence_verified"]
    doc["evidence_receipts"]["cohorts"]["evaluation_ids"] = ["unrelated:1"]
    with pytest.raises(ValueError, match="actual analyzed"):
        analyze_research("transfer", doc, tmp_path)


def test_replay_hash_fields_do_not_override_numerical_agreement(tmp_path: Path) -> None:
    source = fixture("transfer")
    expected = analyze_research("transfer", source, tmp_path / "expected")
    expected["input_canonical_sha256"] = "a" * 64
    doc = {
        "schema_version": "research-replay/v1",
        "synthetic": True,
        "files": {"input.json": {"json": source}, "expected.json": {"json": expected}},
        "checks": [
            {"kind": "transfer", "input_file": "input.json", "expected_file": "expected.json"}
        ],
    }
    result = analyze_research("replay", doc, tmp_path / "replay")
    assert result["numerical_replay"]["checks"][0]["status"] == "passed"
    assert result["integrity"]["recomputed_result_hashes"][0]["status"] == "failed"


def test_measurement_budget_curves_and_cost_breakdown_match_final_observations(
    tmp_path: Path,
) -> None:
    result = analyze_research("measurement-value", fixture("measurement-value"), tmp_path)
    for curve in result["budget_profiles"]["curves"]:
        rows = [
            row
            for row in result["rows"]
            if (row["model"], row["strategy"]) == (curve["model"], curve["strategy"])
        ]
        assert curve["points"][-1]["delta_Y"] == sum(row["delta_Y"] for row in rows)
        assert curve["points"][-1]["K"] == sum(row["K"] for row in rows)
    for cost in result["budget_profiles"]["cost_breakdown"]:
        required = sum(
            row["required_seconds"]
            for row in result["rows"]
            if (row["model"], row["strategy"]) == (cost["model"], cost["strategy"])
        )
        assert sum(cost["seconds"].values()) == pytest.approx(required)
    report = (tmp_path / "report.en.html").read_text(encoding="utf-8")
    assert "<svg" in report and "<details>" in report
    assert "Net discoveries" in report and "Transmit s" in report
