"""Failure-boundary and numerical tests for the versioned research contracts."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from promptcontrollab.diagnostics.research_tools import analyze_research
from promptcontrollab.diagnostics.research_tools.common import digest
from promptcontrollab.diagnostics.research_tools.v2_readout import parse_answer


def base(schema: str) -> dict[str, Any]:
    return {
        "schema_version": f"pcl.{schema}/v2",
        "synthetic": True,
        "representation": "raw_records",
        "provenance": {"description": "Synthetic unit-test evidence only", "source": "synthetic"},
    }


def readout() -> dict[str, Any]:
    doc = base("readout-sensitivity")
    samples: list[dict[str, Any]] = [
        {
            "item_id": f"q{i}",
            "gold_answer": str(i),
            "initial_answers": {"source": str(i + 1), "target": str(i)},
            "source": {"text": str(i + 1)},
            "target": {"text": str(i)},
            "scores": {"loss": i, "primary": 3 - i},
        }
        for i in range(4)
    ]
    samples[1]["target"]["text"] = "Answer: 1"
    samples[2]["target"]["text"] = ""
    doc["conditions"] = [
        {
            "condition_id": rule,
            "parser": {"rule": rule, "version": "numeric/v2", "posthoc": False},
            "budget_tokens": 32,
            "generation_mode": "saved_full",
            "decoding": {"method": "greedy"},
            "batch_size": 2,
            "stopping": "eos",
            "precision": "float32",
            "template_id": "synthetic-template/v1",
            "samples": copy.deepcopy(samples),
        }
        for rule in ("strict", "leading", "terminal")
    ]
    return doc


def response() -> dict[str, Any]:
    doc = base("response-profile")
    doc["metadata"] = {
        "readout_definition": "First coordinate",
        "calibration_source": "Synthetic calibration",
        "label_usage": {"calibration": "fit", "measurement": "none", "evaluation": "score"},
        "calibration_ids": ["calibration-q"],
        "measurement_ids": ["measurement-q"],
        "evaluation_ids": [f"q{i}" for i in range(10)],
    }
    doc["records"] = [
        {
            "record_id": "local",
            "loss_before": 1,
            "loss_after": 0.5,
            "control_before": [0],
            "control_after": [1],
            "response_before": [0, 0],
            "response_after": [2, 0],
            "readout_gradient": [1, 0],
            "linear_response_matrix": [[2], [0]],
        }
    ]
    doc["readouts"] = [
        {
            "readout_id": "fixed",
            "mode": "fixed_coefficients",
            "original_coefficients": [1, 0],
            "coefficients": [1, 0],
        }
    ]
    doc["selection_records"] = [
        {
            "question_id": f"q{2 * fold + label}",
            "pair_id": pair,
            "fold": fold,
            "label": label,
            "scores": {
                "loss": 1 - label,
                "primary": 100 * fold + label,
                "activation": label,
                "logit": 1 - label,
            },
        }
        for fold in range(5)
        for pair in ("pair-a", "pair-b")
        for label in (0, 1)
    ]
    doc["calibration_curves"] = [
        {
            "readout_id": "fixed",
            "source": "saved_summary",
            "bins": [
                {"count": 4, "mean_prediction": 0.25, "observed_rate": 0.5},
                {"count": 4, "mean_prediction": 0.75, "observed_rate": 0.75},
            ],
        }
    ]
    return doc


def measurement() -> dict[str, Any]:
    doc = base("measurement-value")
    costs = dict.fromkeys(
        ("load", "probe", "score", "sort", "transfer", "serialization", "failed"), 0
    )
    doc["cases"] = [
        {
            "case_id": "case",
            "model": "synthetic-model",
            "pair_id": "pair",
            "item_ids": ["q0", "q1", "q2", "q3"],
            "labels": [1, 1, 0, 0],
            "budget_seconds": 4,
            "policies": [
                {
                    "strategy": strategy,
                    "actual_batch_size": 2,
                    "costs": copy.deepcopy(costs),
                    "timing_scope": "measured_full_policy",
                    "run_id": f"synthetic-{strategy}",
                    "batches": [
                        {
                            "batch_id": "b0",
                            "item_ids": ids[:2],
                            "elapsed_seconds": 2,
                            "completed": True,
                        },
                        {
                            "batch_id": "b1",
                            "item_ids": ids[2:],
                            "elapsed_seconds": 2,
                            "completed": True,
                        },
                    ],
                }
                for strategy, ids in (
                    ("direct", ["q2", "q3", "q0", "q1"]),
                    ("primary", ["q0", "q1", "q2", "q3"]),
                )
            ],
        }
    ]
    return doc


def transfer() -> dict[str, Any]:
    doc = base("control-transfer")
    doc["calibration_question_ids"] = ["old-q"]
    doc["calibration_prompt_ids"] = ["old-a", "old-b"]
    doc["panels"] = [
        {
            "panel_id": "both-new",
            "model": "synthetic-model",
            "axes": {"questions": "new_questions", "prompts": "unseen_prompts"},
            "pairs": [
                {
                    "pair_id": f"pair-{i}",
                    "prompt_ids": [f"p{i}", f"p{i + 1}"],
                    "question_ids": ["q0", "q1", "q2", "q3"],
                    "labels": [0, 1, 0, 1],
                    "scores": {"loss": [0, 1, 2, 3], "primary": [0, 3, 1, 2]},
                    "predictions": {
                        "primary": {"full": 0.2, "cheap": 0.1, "group_mean": 0.25, "zero": 0}
                    },
                }
                for i in range(2)
            ],
        }
    ]
    return doc


def replay() -> dict[str, Any]:
    doc = base("research-replay")
    item = response()
    doc.update(
        files={"response.json": {"json": item, "sha256": digest(item)}},
        checks=[{"kind": "response", "input_file": "response.json"}],
    )
    return doc


@pytest.mark.parametrize(
    "kind,factory",
    [
        ("readout", readout),
        ("response", response),
        ("measurement-value", measurement),
        ("transfer", transfer),
        ("replay", replay),
    ],
)
def test_v2_dispatch_reports_are_deterministic(
    kind: str,
    factory: Any,
    tmp_path: Path,
) -> None:
    result = analyze_research(kind, factory(), tmp_path / "a")
    repeated = analyze_research(kind, factory(), tmp_path / "b")
    assert result == repeated and result["schema_version"].endswith("/v2")
    for suffix in ("json", "en.html", "zh.html", "en.md", "zh.md"):
        assert (tmp_path / "a" / f"report.{suffix}").read_bytes() == (
            tmp_path / "b" / f"report.{suffix}"
        ).read_bytes()
    assert "合成" in (tmp_path / "a/report.zh.html").read_text(encoding="utf-8")


def test_readout_changed_scores_and_answers_fail_the_premise_but_keep_observations(
    tmp_path: Path,
) -> None:
    doc = readout()
    doc["conditions"][1]["samples"][0]["scores"]["primary"] = -1
    result = analyze_research("readout", doc, tmp_path)
    assert result["fixed_score_initial_answer_preserving_claim"] == "failed"
    assert result["fixed_scores_preserved"] is False
    assert result["fixed_score_ranks_preserved"] is False
    assert result["conditions"][1]["rank_sensitivity"]["primary"]["spearman"] < 1
    doc = readout()
    doc["conditions"][1]["samples"][0]["initial_answers"]["source"] = "changed"
    result = analyze_research("readout", doc, tmp_path)
    assert result["initial_answers_preserved"] is False
    assert result["fixed_score_initial_answer_preserving_claim"] == "failed"
    assert result["conditions"][1]["comparison_class"] == "inference_perturbation"


def test_readout_parse_answer_correctness_and_rank_are_distinct(tmp_path: Path) -> None:
    result = analyze_research("readout", readout(), tmp_path)
    strict, leading, terminal = result["conditions"]
    assert strict["samples"][1]["parse_switch"] == 1
    assert terminal["samples"][1]["parse_switch"] == 0
    assert terminal["samples"][1]["correctness_change"] == 1
    assert terminal["samples"][1]["answer_changed"] is True
    assert leading["samples"][1]["parsed"]["target"] is None
    assert result["fixed_score_ranks_preserved"] is True
    assert terminal["comparison_axes"]["batch_size"] == 2


def test_readout_prefix_requires_consistency_receipt_and_distinguishes_real_short(
    tmp_path: Path,
) -> None:
    doc = readout()
    condition = doc["conditions"][0]
    condition["generation_mode"] = "stored_prefix"
    for sample in condition["samples"]:
        for key in ("source", "target"):
            endpoint = sample[key]
            pieces = list(endpoint["text"])
            endpoint.update(
                token_ids=list(range(len(pieces))),
                token_texts=pieces,
                prefix_tokens=len(pieces),
                tokenizer_id="synthetic/v1",
            )
    with pytest.raises(ValueError, match=r"token.consistency"):
        analyze_research("readout", doc, tmp_path)
    for sample in condition["samples"]:
        for key in ("source", "target"):
            endpoint = sample[key]
            endpoint["token_consistency"] = {
                "token_ids_sha256": digest(endpoint["token_ids"]),
                "decoded_text_sha256": digest(endpoint["text"]),
                "decoder": "synthetic decoder v1",
                "verified": True,
            }
    result = analyze_research("readout", doc, tmp_path)
    assert result["conditions"][0]["generation_mode"] == "stored_prefix"
    condition["generation_mode"] = "real_short_generation"
    with pytest.raises(ValueError, match="prefix"):
        analyze_research("readout", doc, tmp_path)


def test_response_equal_pair_fold_auc_never_pools_crossfold_scores(tmp_path: Path) -> None:
    result = analyze_research("response", response(), tmp_path)
    selection = result["selection_statistics"]
    assert selection["fold_count"] == 5
    assert selection["aggregation"] == "equal_pair_then_equal_fold"
    assert selection["mean_auc"]["primary"] == 1.0
    assert selection["mean_auc"]["loss"] == 0.0
    assert selection["pooled_crossfold_auc"] is None
    assert result["calibration_curves"][0]["computation"] == "saved_summary_only"
    assert result["calibration_curves"][0]["ece_from_saved_bins"] == 0.125


def test_response_rejects_question_leakage_and_disguised_refit(tmp_path: Path) -> None:
    doc = response()
    doc["selection_records"][4]["question_id"] = "q0"
    with pytest.raises(ValueError, match=r"question.*fold"):
        analyze_research("response", doc, tmp_path)
    doc = response()
    doc["readouts"][0]["coefficients"] = [2, 0]
    with pytest.raises(ValueError, match=r"fixed.coefficient"):
        analyze_research("response", doc, tmp_path)
    doc = response()
    doc["metadata"]["calibration_ids"] = ["q0"]
    with pytest.raises(ValueError, match="disjoint"):
        analyze_research("response", doc, tmp_path)


def test_measurement_budget_boundary_atomic_batches_and_unknown_cost(tmp_path: Path) -> None:
    doc = measurement()
    doc["cases"][0]["budget_seconds"] = 3.99
    result = analyze_research("measurement-value", doc, tmp_path)
    direct, primary = result["cases"][0]["policies"]
    assert direct["K"] == 2 and primary["K"] == 2
    assert primary["delta_Y"] == 2
    assert primary["gain_status"] == "measured_full_policy"
    doc["cases"][0]["policies"][1]["batches"][0]["completed"] = False
    result = analyze_research("measurement-value", doc, tmp_path)
    assert result["cases"][0]["policies"][1]["K"] == 0
    doc["cases"][0]["policies"][1]["costs"]["transfer"] = None
    result = analyze_research("measurement-value", doc, tmp_path)
    assert result["cases"][0]["policies"][1]["K"] is None
    assert result["cases"][0]["policies"][1]["delta_Y"] is None
    assert result["cases"][0]["policies"][1]["observed_spend_within_cutoff_seconds"] is None
    assert result["cases"][0]["policies"][1]["measured_overrun_seconds"] is None


def test_primitive_timing_does_not_become_control_gain(tmp_path: Path) -> None:
    doc = measurement()
    doc["cases"][0]["policies"][1]["timing_scope"] = "primitive_operations"
    result = analyze_research("measurement-value", doc, tmp_path)
    row = result["cases"][0]["policies"][1]
    assert row["gain_status"] == "not_measured_full_policy"
    assert row["delta_Y"] is None
    assert result["scale_extrapolation"] == "not_supported"


def test_transfer_axes_and_prediction_are_not_confirmation(tmp_path: Path) -> None:
    result = analyze_research("transfer", transfer(), tmp_path)
    panel = result["panels"][0]
    assert panel["axes"] == {"questions": "new_questions", "prompts": "unseen_prompts"}
    assert panel["summaries"][0]["group_mean_gain"] == 0.25
    assert panel["summaries"][0]["pair_prediction_mae"]["full"] == pytest.approx(0.05)
    assert panel["additional_control_value"]["status"] == "not_evaluated"
    assert result["evidence"]["temporal_independence_verified"] is False
    doc = transfer()
    doc["panels"][0]["pairs"][0]["prompt_ids"][0] = "old-a"
    with pytest.raises(ValueError, match="unseen_prompts"):
        analyze_research("transfer", doc, tmp_path)


def test_summary_only_is_labeled_and_never_raw_recomputed(tmp_path: Path) -> None:
    for kind, schema in (("response", "response-profile"), ("transfer", "control-transfer")):
        doc = base(schema)
        doc.update(representation="saved_summary", summaries=[{"metric": "mae", "value": 0.1}])
        result = analyze_research(kind, doc, tmp_path / kind)
        assert result["computation"] == "saved_summary_only"
        assert result["raw_recomputation"] is False
        assert result["evidence"]["declared"] == "historical_observation"
        doc["evidence_status"] = "independent_confirmation"
        with pytest.raises(ValueError, match="independent_confirmation"):
            analyze_research(kind, doc, tmp_path / kind)


def test_replay_four_statuses_and_hashes_do_not_prove_lock(tmp_path: Path) -> None:
    doc = replay()
    result = analyze_research("replay", doc, tmp_path)
    assert result["integrity"]["status"] == "passed"
    assert result["numerical_replay"]["status"] == "not_supplied"
    assert result["protocol"]["chronological_prediction_lock"] == "not_verified"
    assert result["theoretical_checks"]["model_global_claim"] is False
    doc["files"]["response.json"]["sha256"] = "0" * 64
    result = analyze_research("replay", doc, tmp_path)
    assert result["integrity"]["status"] == "failed"
    assert result["protocol"]["chronological_prediction_lock"] == "not_verified"


def test_public_a2_examples_are_synthetic_and_replayable(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1] / "examples/research/a2"
    for kind in ("readout", "response", "measurement-value", "transfer", "replay"):
        doc = json.loads((root / f"{kind}.json").read_text(encoding="utf-8"))
        assert doc["synthetic"] is True
        result = analyze_research(kind, doc, tmp_path / kind)
        assert result["synthetic"] is True
        if kind == "replay":
            assert result["integrity"]["status"] == "passed"
            assert result["numerical_replay"]["status"] == "passed"
            assert result["protocol"]["status"] == "passed"


def test_response_undefined_fold_is_not_dropped_from_mean(tmp_path: Path) -> None:
    doc = response()
    for row in doc["selection_records"]:
        if row["fold"] == 0:
            row["label"] = 0
    stats = analyze_research("response", doc, tmp_path)["selection_statistics"]
    assert stats["folds"][0]["undefined_pairs"] == 2
    assert stats["mean_auc"]["primary"] is None


def test_response_equal_pair_weighting_with_unequal_question_counts(tmp_path: Path) -> None:
    doc = response()
    for row in doc["selection_records"]:
        if row["pair_id"] == "pair-b":
            row["scores"]["primary"] = 1 - row["label"]
    for fold in range(5):
        for extra in range(4):
            question = f"extra-{fold}-{extra}"
            doc["metadata"]["evaluation_ids"].append(question)
            doc["selection_records"].append(
                {
                    "question_id": question,
                    "pair_id": "pair-a",
                    "fold": fold,
                    "label": 0,
                    "scores": {"loss": 1, "primary": 100 * fold, "activation": 0, "logit": 1},
                }
            )
    stats = analyze_research("response", doc, tmp_path)["selection_statistics"]
    assert stats["mean_auc"]["primary"] == 0.5


def test_response_refit_and_fold_training_leakage_rejected(tmp_path: Path) -> None:
    doc = response()
    doc["readouts"][0].update(mode="refit", fit_question_ids=["q0"], fit_run_id="fit")
    with pytest.raises(ValueError, match="disjoint"):
        analyze_research("response", doc, tmp_path)
    doc = response()
    doc["training_question_ids_by_fold"] = {str(fold): ["q0"] for fold in range(5)}
    with pytest.raises(ValueError, match="disjoint"):
        analyze_research("response", doc, tmp_path)


def test_measurement_exact_decimal_cutoff_and_missing_component(tmp_path: Path) -> None:
    doc = measurement()
    case = doc["cases"][0]
    case["budget_seconds"] = 0.3
    for policy in case["policies"]:
        policy["batches"][0]["elapsed_seconds"] = 0.1
        policy["batches"][1]["elapsed_seconds"] = 0.2
    result = analyze_research("measurement-value", doc, tmp_path)
    assert all(row["K"] == 4 for row in result["cases"][0]["policies"])
    del case["policies"][1]["costs"]["serialization"]
    row = analyze_research("measurement-value", doc, tmp_path)["cases"][0]["policies"][1]
    assert row["K"] is None
    assert row["unknown_cost_components"] == ["serialization"]


def test_failed_batch_cost_paid_but_items_only_counted_on_completed_retry(tmp_path: Path) -> None:
    doc = measurement()
    policy = doc["cases"][0]["policies"][1]
    failed = copy.deepcopy(policy["batches"][0])
    failed.update(batch_id="failed-attempt", elapsed_seconds=0.5, completed=False)
    policy["batches"].insert(0, failed)
    result = analyze_research("measurement-value", doc, tmp_path)
    row = result["cases"][0]["policies"][1]
    assert row["K"] == 2 and row["Y"] == 2
    assert row["observed_spend_within_cutoff_seconds"] == 4
    assert row["measured_overrun_seconds"] == 0.5
    assert row["excluded_batches"][0]["reason"] == "incomplete_batch"


@pytest.mark.parametrize("field,value", [("elapsed_seconds", -1), ("completed", 1)])
def test_batch_rejects_invalid_timing_or_completion(
    field: str,
    value: Any,
    tmp_path: Path,
) -> None:
    doc = measurement()
    doc["cases"][0]["policies"][0]["batches"][0][field] = value
    with pytest.raises(ValueError):
        analyze_research("measurement-value", doc, tmp_path)


def test_transfer_control_value_requires_same_case_panel(tmp_path: Path) -> None:
    doc = transfer()
    doc["panels"][0]["measurement_document"] = measurement()
    with pytest.raises(ValueError, match="panel"):
        analyze_research("transfer", doc, tmp_path)
    doc["panels"][0]["measurement_document"]["cases"][0]["pair_id"] = "pair-0"
    doc["panels"][0]["measurement_document"]["cases"][0]["labels"] = [0, 1, 0, 1]
    result = analyze_research("transfer", doc, tmp_path)
    assert result["panels"][0]["additional_control_value"]["status"] == "measured_full_policy"


def test_crossed_axes_reject_changed_question_panel(tmp_path: Path) -> None:
    doc = transfer()
    panel = copy.deepcopy(doc["panels"][0])
    panel["panel_id"] = "seen-new"
    panel["axes"]["prompts"] = "seen_prompts"
    for pair in panel["pairs"]:
        pair["prompt_ids"] = ["old-a", "old-b"]
        pair["question_ids"] = ["different0", "different1", "different2", "different3"]
    doc["panels"].append(panel)
    with pytest.raises(ValueError, match="crossed question axis"):
        analyze_research("transfer", doc, tmp_path)


def test_replay_protocol_failure_is_distinct_from_integrity(tmp_path: Path) -> None:
    item = readout()
    item["conditions"][1]["samples"][0]["scores"]["primary"] = -1
    doc = base("research-replay")
    doc.update(
        files={"input.json": {"json": item, "sha256": digest(item)}},
        checks=[{"kind": "readout", "input_file": "input.json"}],
    )
    result = analyze_research("replay", doc, tmp_path)
    assert result["integrity"]["status"] == "passed"
    assert result["protocol"]["status"] == "failed"
    assert result["numerical_replay"]["status"] == "not_supplied"


def test_replay_rejects_external_commands_and_paths(tmp_path: Path) -> None:
    doc = replay()
    doc["command"] = "python uploaded.py"
    with pytest.raises(ValueError, match="commands"):
        analyze_research("replay", doc, tmp_path)
    doc = replay()
    doc["files"]["../outside.json"] = doc["files"].pop("response.json")
    with pytest.raises(ValueError, match="safe relative"):
        analyze_research("replay", doc, tmp_path)


def test_numeric_parser_does_not_round_distinct_long_answers() -> None:
    left = "1234567890123456789012345678901"
    right = "1234567890123456789012345678902"
    assert parse_answer(left, "strict", "numeric/v2") != parse_answer(right, "strict", "numeric/v2")
    assert parse_answer("1,000.00", "strict", "numeric/v2") == parse_answer(
        "1e3", "strict", "numeric/v2"
    )


def test_readout_score_preservation_does_not_collapse_large_integer_scores(tmp_path: Path) -> None:
    doc = readout()
    for condition in doc["conditions"]:
        condition["samples"][0]["scores"]["primary"] = 2**53
    doc["conditions"][1]["samples"][0]["scores"]["primary"] += 1
    result = analyze_research("readout", doc, tmp_path)
    assert result["fixed_scores_preserved"] is False


def test_transfer_ranking_retains_large_integer_order(tmp_path: Path) -> None:
    doc = transfer()
    for pair in doc["panels"][0]["pairs"]:
        pair["labels"] = [0, 1, 0, 1]
        pair["scores"]["primary"] = [2**53, 2**53 + 1, 2**53 + 4, 2**53 + 5]
    result = analyze_research("transfer", doc, tmp_path)
    assert result["panels"][0]["pairs"][0]["auc"]["primary"] == 0.75


@pytest.mark.parametrize(
    "value,rule,expected",
    [
        ("B", "strict", "B"),
        ("B. Because", "strict", None),
        ("B. Because", "leading", "B"),
        ("Because", "leading", None),
        ("Answer: (B).", "terminal", "B"),
        ("CAD", "terminal", None),
        ("b", "strict", None),
        ("F", "strict", None),
        ("2", "strict", None),
    ],
)
def test_choice_parser_has_explicit_domain_and_token_boundaries(
    value: str,
    rule: str,
    expected: str | None,
) -> None:
    assert parse_answer(value, rule, "choice/v2") == expected


def test_choice_readout_runs_raw_paired_analysis(tmp_path: Path) -> None:
    doc = readout()
    for condition in doc["conditions"]:
        condition["parser"]["version"] = "choice/v2"
        for index, sample in enumerate(condition["samples"]):
            sample["gold_answer"] = "ABCD"[index]
            sample["source"]["text"] = "BCDE"[index]
            sample["target"]["text"] = "ABCD"[index]
            if index == 1:
                sample["target"]["text"] = "Answer: B"
    result = analyze_research("readout", doc, tmp_path)
    assert result["raw_recomputation"] is True
    assert result["conditions"][0]["samples"][1]["correctness_change"] == 0
    assert result["conditions"][2]["samples"][1]["correctness_change"] == 1


def with_linked_receipts(
    document: dict[str, Any],
    *,
    calibration_ids: list[str],
    evaluation_ids: list[str],
    payload_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build internally linked synthetic receipts for the original document bytes."""
    doc = copy.deepcopy(document)
    doc["evidence_status"] = "independent_confirmation"
    payload = {
        "description": "Synthetic lock only",
        "calibration_ids_sha256": digest(calibration_ids),
    }
    payload.update(payload_fields or {})
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
            "evaluation_ids_sha256": digest(evaluation_ids),
        },
        "cohorts": {"calibration_ids": calibration_ids, "evaluation_ids": evaluation_ids},
    }
    return doc


def test_response_receipts_bind_original_document_before_geometry_projection(
    tmp_path: Path,
) -> None:
    original = response()
    doc = with_linked_receipts(
        original,
        calibration_ids=original["metadata"]["calibration_ids"],
        evaluation_ids=original["metadata"]["evaluation_ids"],
    )
    before = copy.deepcopy(doc)
    result = analyze_research("response", doc, tmp_path)
    assert doc == before
    assert result["rows"][0]["response_gain"] == 2
    assert result["evidence"]["linked_receipts_verified"] is True
    assert result["evidence"]["temporal_independence_verified"] is False
    assert result["input_canonical_sha256"] == digest(doc)
    doc["records"][0]["loss_after"] = 0.4
    with pytest.raises(ValueError, match="analyzed document"):
        analyze_research("response", doc, tmp_path)


def measurement_receipt_document() -> dict[str, Any]:
    """Freeze the v2 policy trace projection and its exact model/pair cohort."""
    doc = measurement()
    locked = [
        {
            key: case[key]
            for key in (
                "case_id",
                "model",
                "pair_id",
                "item_ids",
                "budget_seconds",
                "policies",
            )
        }
        for case in doc["cases"]
    ]
    return with_linked_receipts(
        doc,
        calibration_ids=["synthetic-model:calibration-pair"],
        evaluation_ids=["synthetic-model:pair"],
        payload_fields={"policies_sha256": digest(locked)},
    )


def test_measurement_v2_receipt_binds_new_policy_shape_and_exact_cohort(tmp_path: Path) -> None:
    doc = measurement_receipt_document()
    result = analyze_research("measurement-value", doc, tmp_path)
    assert result["evidence"]["linked_receipts_verified"] is True
    assert result["evidence"]["temporal_independence_verified"] is False
    assert result["cases"][0]["policies"][0]["K"] == 4
    doc["cases"][0]["policies"][0]["costs"]["probe"] = 0.1
    doc["evidence_receipts"]["evaluation"]["document_sha256"] = digest(
        {key: value for key, value in doc.items() if key != "evidence_receipts"}
    )
    with pytest.raises(ValueError, match="freeze"):
        analyze_research("measurement-value", doc, tmp_path)


def test_measurement_v2_receipt_rejects_wrong_evaluation_cohort(tmp_path: Path) -> None:
    doc = measurement_receipt_document()
    doc["evidence_receipts"]["cohorts"]["evaluation_ids"] = ["synthetic-model:wrong-pair"]
    doc["evidence_receipts"]["evaluation"]["evaluation_ids_sha256"] = digest(
        ["synthetic-model:wrong-pair"]
    )
    with pytest.raises(ValueError, match="actual analyzed cases"):
        analyze_research("measurement-value", doc, tmp_path)


@pytest.mark.parametrize("completed", [True, False])
def test_crossing_batch_consumes_remaining_budget_without_discovery_credit(
    completed: bool,
    tmp_path: Path,
) -> None:
    doc = measurement()
    doc["cases"][0]["budget_seconds"] = 3
    doc["cases"][0]["policies"][1]["batches"][1]["completed"] = completed
    row = analyze_research("measurement-value", doc, tmp_path)["cases"][0]["policies"][1]
    assert row["K"] == 2 and row["Y"] == 2
    assert row["observed_spend_within_cutoff_seconds"] == 3
    assert row["observed_elapsed_through_cutoff_batch_seconds"] == 4
    assert row["measured_overrun_seconds"] == 1


def test_upfront_overrun_is_capped_and_no_later_batch_is_started(tmp_path: Path) -> None:
    doc = measurement()
    doc["cases"][0]["budget_seconds"] = 1
    doc["cases"][0]["policies"][1]["costs"]["load"] = 2
    row = analyze_research("measurement-value", doc, tmp_path)["cases"][0]["policies"][1]
    assert row["K"] == 0 and row["Y"] == 0
    assert row["observed_spend_within_cutoff_seconds"] == 1
    assert row["observed_elapsed_through_cutoff_batch_seconds"] == 2
    assert row["measured_overrun_seconds"] == 1


def test_exact_budget_completion_does_not_start_the_next_positive_duration_batch(
    tmp_path: Path,
) -> None:
    doc = measurement()
    doc["cases"][0]["budget_seconds"] = 2
    row = analyze_research("measurement-value", doc, tmp_path)["cases"][0]["policies"][1]
    assert row["K"] == 2 and row["Y"] == 2
    assert row["observed_spend_within_cutoff_seconds"] == 2
    assert row["observed_elapsed_through_cutoff_batch_seconds"] == 2
    assert row["measured_overrun_seconds"] == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("batch_size", 99),
        ("precision", "changed"),
        ("template_id", "changed"),
        ("decoding", {"method": "different"}),
        ("stopping", "changed"),
    ],
)
def test_readout_execution_changes_are_not_readout_only(
    field: str,
    value: Any,
    tmp_path: Path,
) -> None:
    doc = readout()
    doc["conditions"][1][field] = value
    row = analyze_research("readout", doc, tmp_path)["conditions"][1]
    assert row["fixed_score_initial_answer_preserving_claim"] == "passed"
    assert row["comparison_class"] == "inference_perturbation"
    assert row["execution_conditions_preserved"] is False


def test_changed_raw_output_is_not_hidden_by_preserved_initial_answer_claim(tmp_path: Path) -> None:
    doc = readout()
    doc["conditions"][1]["samples"][0]["source"]["text"] = "999"
    row = analyze_research("readout", doc, tmp_path)["conditions"][1]
    assert row["fixed_score_initial_answer_preserving_claim"] == "passed"
    assert row["source_records_preserved"] is False
    assert row["comparison_class"] == "inference_perturbation"


def transfer_receipt_document() -> dict[str, Any]:
    """Bind actual crossed cohorts and every nested forecast to its supplied receipt."""
    from promptcontrollab.diagnostics.research_tools.common import transfer_v2_receipt_projection

    doc = transfer()
    doc["evidence_status"] = "independent_confirmation"
    forecasts, calibration, panels = transfer_v2_receipt_projection(doc)
    payload = {
        "forecasts_sha256": digest(forecasts),
        "calibration_cohorts_sha256": digest(calibration),
    }
    lock = {
        "frozen_at": "2026-01-01T00:00:00Z",
        "payload": payload,
        "payload_sha256": digest(payload),
    }
    doc["evidence_receipts"] = {
        "lock": lock,
        "evaluation": {
            "started_at": "2026-01-02T00:00:00Z",
            "lock_sha256": digest(lock),
            "document_sha256": digest(doc),
            "evaluation_panels_sha256": digest(panels),
        },
        "cohorts": {"calibration": calibration, "evaluation_panels": panels},
    }
    return doc


def test_transfer_v2_lock_binds_nested_forecasts_and_actual_cohorts(tmp_path: Path) -> None:
    doc = transfer_receipt_document()
    result = analyze_research("transfer", doc, tmp_path)
    assert result["evidence"]["linked_receipts_verified"] is True
    assert result["evidence"]["temporal_independence_verified"] is False
    doc["panels"][0]["pairs"][0]["predictions"]["primary"]["full"] = 0.9
    doc["evidence_receipts"]["evaluation"]["document_sha256"] = digest(
        {key: value for key, value in doc.items() if key != "evidence_receipts"}
    )
    with pytest.raises(ValueError, match=r"freeze.*forecasts"):
        analyze_research("transfer", doc, tmp_path)


def test_transfer_v2_rejects_unrelated_but_internally_hashed_cohorts(tmp_path: Path) -> None:
    doc = transfer_receipt_document()
    unrelated = {"question_ids": ["unrelated"], "prompt_ids": ["unrelated"]}
    receipts = doc["evidence_receipts"]
    receipts["cohorts"]["calibration"] = unrelated
    receipts["lock"]["payload"]["calibration_cohorts_sha256"] = digest(unrelated)
    receipts["lock"]["payload_sha256"] = digest(receipts["lock"]["payload"])
    receipts["evaluation"]["lock_sha256"] = digest(receipts["lock"])
    with pytest.raises(ValueError, match="actual crossed panels"):
        analyze_research("transfer", doc, tmp_path)
