"""Local response, readout replacement, and question-grouped selection diagnostics."""

from __future__ import annotations

import math

from .common import JsonDict, number, text
from .response import analyze_document as local_response
from .transfer_prediction import binary_auc
from .v2_common import (
    average,
    header,
    identifiers,
    integer,
    mapping,
    numeric_vector,
    records,
    saved_summary,
    score_number,
)


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        for index in order[start:end]:
            ranks[index] = (start + end - 1) / 2
        start = end
    return ranks


def rank_correlation(left: list[float], right: list[float]) -> float | None:
    """Spearman rank correlation with average ties and undefined constant vectors."""
    if not left or len(left) != len(right):
        raise ValueError("Rank sensitivity requires aligned nonempty score vectors")
    a, b = _ranks(left), _ranks(right)
    center = (len(a) - 1) / 2
    x, y = [v - center for v in a], [v - center for v in b]
    denominator = math.hypot(*x) * math.hypot(*y)
    return (
        math.fsum(u * v for u, v in zip(x, y, strict=True)) / denominator if denominator else None
    )


def selection_statistics(document: JsonDict) -> JsonDict:
    """Evaluate grouped calibration by averaging within-fold and within-pair AUCs."""
    supplied = document.get("selection_records")
    if supplied is None:
        return {"status": "not_supplied", "pooled_crossfold_auc": None}
    rows = records(supplied, "selection_records")
    questions: dict[str, int] = {}
    coordinates: set[tuple[str, str]] = set()
    groups: dict[tuple[int, str], list[JsonDict]] = {}
    names: set[str] | None = None
    for row in rows:
        question = text(row.get("question_id"), "question_id")
        pair = text(row.get("pair_id"), "pair_id")
        fold = integer(row.get("fold"), "fold")
        if fold > 4:
            raise ValueError("Question-group selection uses exactly five folds numbered 0..4")
        if question in questions and questions[question] != fold:
            raise ValueError("A question must belong to only one fold across every pair")
        questions[question] = fold
        if (question, pair) in coordinates:
            raise ValueError("Duplicate question/pair coordinate")
        coordinates.add((question, pair))
        label = integer(row.get("label"), "label")
        if label not in (0, 1):
            raise ValueError("selection label must be binary")
        scores = mapping(row.get("scores"), "scores")
        if not {"loss", "primary", "activation", "logit"} <= set(scores):
            raise ValueError("Selection requires loss, primary, activation and logit baselines")
        checked = {key: score_number(value, f"scores.{key}") for key, value in scores.items()}
        if names is None:
            names = set(checked)
        elif names != set(checked):
            raise ValueError("Selection score names must align across folds and pairs")
        groups.setdefault((fold, pair), []).append(
            {"question_id": question, "label": label, "scores": checked}
        )
    if set(questions.values()) != set(range(5)):
        raise ValueError("Question-group selection requires all five folds")
    pair_sets = [{pair for fold_id, pair in groups if fold_id == fold} for fold in range(5)]
    if any(pairs != pair_sets[0] for pairs in pair_sets):
        raise ValueError("Equal-pair selection requires the same pair cohort in every fold")
    training = document.get("training_question_ids_by_fold")
    training_status = "not_supplied"
    if training is not None:
        training = mapping(training, "training_question_ids_by_fold")
        if set(training) != {str(fold) for fold in range(5)}:
            raise ValueError("Training identities must be supplied for all five folds")
        for fold in range(5):
            train_ids = identifiers(training[str(fold)], "training_question_ids")
            heldout = {question for question, group in questions.items() if group == fold}
            if set(train_ids) & heldout:
                raise ValueError("Training and held-out question identities must be disjoint")
        training_status = "identity_disjointness_verified"
    folds: list[JsonDict] = []
    for fold in range(5):
        pair_rows: list[JsonDict] = []
        for pair in sorted(pair_sets[fold]):
            panel = groups[(fold, pair)]
            auc = {
                name: binary_auc(
                    [row["scores"][name] for row in panel], [row["label"] for row in panel]
                )
                for name in sorted(names or [])
            }
            pair_rows.append({"pair_id": pair, "item_count": len(panel), "auc": auc})
        common = [
            row for row in pair_rows if all(value is not None for value in row["auc"].values())
        ]
        folds.append(
            {
                "fold": fold,
                "pairs": pair_rows,
                "common_valid_pairs": len(common),
                "undefined_pairs": len(pair_rows) - len(common),
                "auc": {
                    name: average([row["auc"][name] for row in common])
                    for name in sorted(names or [])
                },
            }
        )
    means = {
        name: average([fold["auc"][name] for fold in folds])
        if all(fold["auc"][name] is not None for fold in folds)
        else None
        for name in sorted(names or [])
    }
    rank_rows = []
    for (fold, pair), panel in sorted(groups.items()):
        for name in sorted((names or set()) - {"primary"}):
            rank_rows.append(
                {
                    "fold": fold,
                    "pair_id": pair,
                    "baseline": name,
                    "spearman": rank_correlation(
                        [row["scores"]["primary"] for row in panel],
                        [row["scores"][name] for row in panel],
                    ),
                }
            )
    return {
        "status": "computed",
        "fold_count": 5,
        "question_count": len(questions),
        "aggregation": "equal_pair_then_equal_fold",
        "folds": folds,
        "mean_auc": means,
        "auc_gaps": {
            name: value - means["loss"] if value is not None and means["loss"] is not None else None
            for name, value in means.items()
            if name != "loss"
        },
        "pooled_crossfold_auc": None,
        "rank_sensitivity": rank_rows,
        "training_separation": training_status,
        "scope": (
            "Within-fold per-pair AUC only; "
            "fold-specific scores are never pooled for selection AUC."
        ),
    }


def _calibration_curves(document: JsonDict) -> list[JsonDict]:
    result = []
    for curve in records(document.get("calibration_curves", []), "calibration_curves", empty=True):
        readout_id = text(curve.get("readout_id"), "readout_id")
        if curve.get("source") != "saved_summary":
            raise ValueError("Calibration curves require explicit saved_summary provenance")
        bins = []
        for item in records(curve.get("bins"), "calibration bins"):
            count = integer(item.get("count"), "bin.count", minimum=1)
            prediction = number(item.get("mean_prediction"), "mean_prediction")
            observed = number(item.get("observed_rate"), "observed_rate")
            if not 0 <= prediction <= 1 or not 0 <= observed <= 1:
                raise ValueError("Calibration bin rates must lie in [0,1]")
            bins.append({"count": count, "mean_prediction": prediction, "observed_rate": observed})
        total = sum(item["count"] for item in bins)
        ece = math.fsum(
            item["count"] / total * abs(item["mean_prediction"] - item["observed_rate"])
            for item in bins
        )
        result.append(
            {
                "readout_id": readout_id,
                "bins": bins,
                "count": total,
                "computation": "saved_summary_only",
                "ece_from_saved_bins": ece,
                "raw_calibration_recomputed": False,
            }
        )
    return result


def _readouts(document: JsonDict, evaluation_ids: list[str]) -> list[JsonDict]:
    """Compare fixed-coefficient readout replacement separately from recalibration."""
    result, seen = [], set()
    response_records = records(document.get("records"), "records")
    for readout in records(document.get("readouts", []), "readouts", empty=True):
        rid = text(readout.get("readout_id"), "readout_id")
        if rid in seen:
            raise ValueError("readout_id must be unique")
        seen.add(rid)
        original = numeric_vector(readout.get("original_coefficients"), "original_coefficients")
        coefficients = numeric_vector(readout.get("coefficients"), "coefficients", len(original))
        mode = readout.get("mode")
        if mode == "fixed_coefficients":
            if original != coefficients:
                raise ValueError("fixed-coefficient readout replacement must preserve coefficients")
            fit_status = "coefficients_preserved"
        elif mode == "refit":
            fit_ids = identifiers(readout.get("fit_question_ids"), "fit_question_ids")
            if set(fit_ids) & set(evaluation_ids):
                raise ValueError("Readout refit and evaluation identities must be disjoint")
            text(readout.get("fit_run_id"), "fit_run_id")
            fit_status = "declared_refit_disjoint_identities"
        else:
            raise ValueError("readout mode must distinguish fixed_coefficients from refit")
        deltas = []
        for record in response_records:
            before = numeric_vector(
                record.get("response_before"), "response_before", len(coefficients)
            )
            after = numeric_vector(
                record.get("response_after"), "response_after", len(coefficients)
            )
            displacement = [b - a for a, b in zip(before, after, strict=True)]
            deltas.append(
                {
                    "record_id": record["record_id"],
                    "readout_delta": number(
                        math.fsum(c * d for c, d in zip(coefficients, displacement, strict=True)),
                        "readout_delta",
                    ),
                    "original_readout_delta": number(
                        math.fsum(c * d for c, d in zip(original, displacement, strict=True)),
                        "original_readout_delta",
                    ),
                }
            )
        result.append(
            {
                "readout_id": rid,
                "mode": mode,
                "fit_status": fit_status,
                "coefficients": coefficients,
                "deltas": deltas,
                "rank_correlation_to_original": rank_correlation(
                    [row["readout_delta"] for row in deltas],
                    [row["original_readout_delta"] for row in deltas],
                ),
            }
        )
    return result


def analyze_document(document: JsonDict) -> JsonDict:
    """Recompute supported response measurements and disclose stage-specific label use."""
    result = header(document, "response")
    summary = saved_summary(document, result)
    if summary is not None:
        return summary
    metadata = mapping(document.get("metadata"), "metadata")
    usage = mapping(metadata.get("label_usage"), "metadata.label_usage")
    if set(usage) != {"calibration", "measurement", "evaluation"}:
        raise ValueError("label_usage must separately declare calibration, measurement, evaluation")
    for role, use in usage.items():
        text(use, f"label_usage.{role}")
    cohorts = {
        role: identifiers(metadata.get(f"{role}_ids"), f"metadata.{role}_ids", empty=True)
        for role in ("calibration", "measurement", "evaluation")
    }
    if set(cohorts["calibration"]) & set(cohorts["evaluation"]):
        raise ValueError("Calibration and evaluation identities must be disjoint")
    legacy = dict(
        schema_version="response-profile/v1",
        synthetic=document["synthetic"],
        records=document.get("records"),
        metadata={
            "readout_definition": text(metadata.get("readout_definition"), "readout_definition"),
            "gold_label_usage": str(usage),
            "calibration_source": text(metadata.get("calibration_source"), "calibration_source"),
            "calibration_disjoint": True,
        },
    )
    # The original v2 document's receipts were verified by header(). The geometry
    # adapter is a new projection, not the document to which those receipts refer.
    local = local_response(legacy)
    selection = selection_statistics(document)
    if document.get("selection_records"):
        actual = {row["question_id"] for row in document["selection_records"]}
        if actual != set(cohorts["evaluation"]):
            raise ValueError("Selection question identities must match the evaluation cohort")
    result.update(
        metadata=metadata,
        rows=local["rows"],
        formulae=local["formulae"],
        readouts=_readouts(document, cohorts["evaluation"]),
        calibration_curves=_calibration_curves(document),
        selection_statistics=selection,
        label_usage=usage,
        local_properties={
            "status": "evaluated_saved_finite_dimensions",
            "model_global_claim": False,
            "record_count": len(local["rows"]),
            "scope": (
                "Response displacement, gain, alignment and approximation residual "
                "of supplied local records only."
            ),
        },
    )
    return result
