"""Crossed prompt/question transfer, with separate association and policy claims."""

from __future__ import annotations

from .common import JsonDict, number, text
from .transfer_prediction import binary_auc
from .v2_common import (
    average,
    binary_vector,
    header,
    identifiers,
    mapping,
    records,
    saved_summary,
    score_vector,
)


def _additional_control(panel: JsonDict) -> JsonDict:
    if "measurement_document" not in panel:
        return {
            "status": "not_evaluated",
            "delta_Y": None,
            "scope": "Pair prediction accuracy does not establish additional paid control value.",
        }
    from .v2_measurement import analyze_document as measure

    measurement_document = mapping(panel["measurement_document"], "measurement_document")
    measured = measure(measurement_document)
    if not measured["raw_recomputation"]:
        return {"status": "saved_summary_only", "delta_Y": None, "measurement": measured}
    pairs = {row["pair_id"]: row for row in panel["pairs"]}
    for case in measurement_document["cases"]:
        pair = pairs.get(case["pair_id"])
        if (
            case["model"] != panel["model"]
            or pair is None
            or case["item_ids"] != pair["question_ids"]
            or case["labels"] != pair["labels"]
        ):
            raise ValueError(
                "Additional control value must use the same model, pair, questions and labels "
                "as the transfer panel"
            )
    rows = [
        policy
        for case in measured["cases"]
        for policy in case["policies"]
        if policy["strategy"] != "direct"
    ]
    return {
        "status": "measured_full_policy"
        if rows and all(row["gain_status"] == "measured_full_policy" for row in rows)
        else "incomplete_cost_evidence",
        "delta_Y": None,
        "policies": rows,
        "scope": (
            "Each supplied measured policy versus its direct comparator; policies are not pooled."
        ),
    }


def analyze_document(document: JsonDict) -> JsonDict:
    """Evaluate crossed transfer panels and distinguish mean, pairwise and incremental value."""
    result = header(document, "transfer")
    summary = saved_summary(document, result)
    if summary is not None:
        return summary
    calibration_questions = set(
        identifiers(document.get("calibration_question_ids"), "calibration_question_ids")
    )
    calibration_prompts = set(
        identifiers(document.get("calibration_prompt_ids"), "calibration_prompt_ids")
    )
    panels: list[JsonDict] = []
    panel_ids: set[str] = set()
    question_cohorts: dict[tuple[str, str], list[str]] = {}
    prompt_cohorts: dict[tuple[str, str], dict[str, list[str]]] = {}
    for panel in records(document.get("panels"), "panels"):
        pid = text(panel.get("panel_id"), "panel_id")
        if pid in panel_ids:
            raise ValueError("panel_id must be unique")
        panel_ids.add(pid)
        model = text(panel.get("model"), "model")
        axes = mapping(panel.get("axes"), "axes")
        if set(axes) != {"questions", "prompts"}:
            raise ValueError("Crossed panel axes must separately specify questions and prompts")
        if axes["questions"] not in ("calibration_questions", "new_questions"):
            raise ValueError("Question axis must be calibration_questions or new_questions")
        if axes["prompts"] not in ("seen_prompts", "unseen_prompts"):
            raise ValueError("Prompt axis must be seen_prompts or unseen_prompts")
        pair_rows: list[JsonDict] = []
        pair_ids: set[str] = set()
        common_questions: list[str] | None = None
        common_scores: set[str] | None = None
        endpoint_map: dict[str, list[str]] = {}
        for pair in records(panel.get("pairs"), "pairs"):
            pair_id = text(pair.get("pair_id"), "pair_id")
            if pair_id in pair_ids:
                raise ValueError("pair_id must be unique within a panel")
            pair_ids.add(pair_id)
            prompts = identifiers(pair.get("prompt_ids"), "prompt_ids")
            if len(prompts) != 2:
                raise ValueError("A prompt pair requires two distinct prompt identities")
            endpoint_map[pair_id] = prompts
            if axes["prompts"] == "unseen_prompts" and set(prompts) & calibration_prompts:
                raise ValueError(
                    "unseen_prompts must be disjoint from calibration prompt identities"
                )
            if axes["prompts"] == "seen_prompts" and set(prompts) - calibration_prompts:
                raise ValueError("seen_prompts must belong to calibration prompt identities")
            questions = identifiers(pair.get("question_ids"), "question_ids")
            if axes["questions"] == "new_questions" and set(questions) & calibration_questions:
                raise ValueError(
                    "new_questions must be disjoint from calibration question identities"
                )
            if (
                axes["questions"] == "calibration_questions"
                and set(questions) - calibration_questions
            ):
                raise ValueError("calibration_questions must belong to the calibration cohort")
            if common_questions is None:
                common_questions = questions
            elif common_questions != questions:
                raise ValueError("Prompt pairs must share the same ordered question panel")
            scores = mapping(pair.get("scores"), "scores")
            if "loss" not in scores or len(scores) < 2:
                raise ValueError("Transfer scores require loss and diagnostic scores")
            if common_scores is None:
                common_scores = set(scores)
            elif common_scores != set(scores):
                raise ValueError("Diagnostic score names must align across pairs")
            labels = binary_vector(pair.get("labels"), "labels", len(questions))
            auc = {
                key: binary_auc(score_vector(values, f"scores.{key}", len(questions)), labels)
                for key, values in scores.items()
            }
            gains = {
                key: value - auc["loss"] if value is not None and auc["loss"] is not None else None
                for key, value in auc.items()
                if key != "loss"
            }
            forecasts = mapping(pair.get("predictions"), "predictions")
            if set(forecasts) != set(gains):
                raise ValueError("Predictions must cover every diagnostic gain")
            predictions, errors = {}, {}
            for score, gain in gains.items():
                supplied = mapping(forecasts[score], f"predictions.{score}")
                if set(supplied) != {"full", "cheap", "group_mean", "zero"}:
                    raise ValueError(
                        "Transfer requires full, cheap, group_mean and zero predictions"
                    )
                values = {
                    key: number(value, f"predictions.{score}.{key}")
                    for key, value in supplied.items()
                }
                if values["zero"] != 0:
                    raise ValueError("Zero prediction baseline must be exactly zero")
                predictions[score] = values
                errors[score] = {
                    key: abs(value - gain) if gain is not None else None
                    for key, value in values.items()
                }
            pair_rows.append(
                {
                    "pair_id": pair_id,
                    "prompt_ids": prompts,
                    "question_count": len(questions),
                    "auc": auc,
                    "gains": gains,
                    "predictions": predictions,
                    "absolute_errors": errors,
                    "status": "defined"
                    if all(value is not None for value in gains.values())
                    else "undefined_auc",
                }
            )
        assert common_questions is not None
        qkey, pkey = (model, axes["questions"]), (model, axes["prompts"])
        if qkey in question_cohorts and question_cohorts[qkey] != common_questions:
            raise ValueError("A crossed question axis must retain the same ordered question cohort")
        if pkey in prompt_cohorts and prompt_cohorts[pkey] != endpoint_map:
            raise ValueError(
                "A crossed prompt axis must retain the same prompt pairs and orientation"
            )
        question_cohorts[qkey], prompt_cohorts[pkey] = common_questions, endpoint_map
        summaries = []
        valid = [row for row in pair_rows if row["status"] == "defined"]
        for score in sorted((common_scores or set()) - {"loss"}):
            if len({row["predictions"][score]["group_mean"] for row in pair_rows}) != 1:
                raise ValueError(
                    "Group-mean prediction must be fixed across a panel, not fit per pair"
                )
            maes = {
                key: average([row["absolute_errors"][score][key] for row in valid])
                for key in ("full", "cheap", "group_mean", "zero")
            }
            observed_mean = average([row["gains"][score] for row in valid])
            summaries.append(
                {
                    "score": score,
                    "pair_count": len(pair_rows),
                    "common_valid_pairs": len(valid),
                    "undefined_pairs": len(pair_rows) - len(valid),
                    "group_mean_gain": observed_mean,
                    "group_mean_prediction": pair_rows[0]["predictions"][score]["group_mean"],
                    "pair_prediction_mae": maes,
                    "mae_improvement_vs_group_mean": maes["group_mean"] - maes["full"]
                    if maes["group_mean"] is not None and maes["full"] is not None
                    else None,
                    "inference": (
                        "Descriptive equal-pair estimates; "
                        "no significance claim or cross-cell pooling."
                    ),
                }
            )
        panels.append(
            {
                "panel_id": pid,
                "model": model,
                "axes": axes,
                "question_count": len(common_questions),
                "pairs": pair_rows,
                "summaries": summaries,
                "additional_control_value": _additional_control(panel),
            }
        )
    cells = [
        (panel["model"], panel["axes"]["questions"], panel["axes"]["prompts"]) for panel in panels
    ]
    if len(set(cells)) != len(cells):
        raise ValueError("Crossed panel model/axis cells must be unique")
    result.update(
        panels=panels,
        crossed_panel={
            "axes": {
                "questions": ["calibration_questions", "new_questions"],
                "prompts": ["seen_prompts", "unseen_prompts"],
            },
            "observed_cells": [list(cell) for cell in cells],
            "missing_cells": [
                [model, questions, prompts]
                for model in sorted({cell[0] for cell in cells})
                for questions in ("calibration_questions", "new_questions")
                for prompts in ("seen_prompts", "unseen_prompts")
                if (model, questions, prompts) not in cells
            ],
        },
        inference_status=(
            "descriptive; use the separately frozen crossed bootstrap engine for intervals"
        ),
        success_claim=(
            "Group mean, pair prediction, and additional measured control value "
            "are separate targets."
        ),
    )
    return result
