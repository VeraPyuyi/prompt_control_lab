"""Replay fixed control-diagnostic forecasts without fitting on behavior labels.

The compact case reproduces AUC gaps and prediction errors. It does not certify
chronological independence, reconstruct hidden states, or replace the research
bundle's crossed bootstrap. All functions use the Python standard library.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping
from typing import Any

from .common import evidence

SCORES = ("primary", "norm")
PREDICTORS = ("full", "cheap", "uniform_mean", "zero")
EVIDENCE = ("historical_observation", "locked_prediction", "independent_confirmation")
PAIR_TYPES = ("adjacent_seed", "selection_loss")


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")
    return value


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Scores and forecasts must be finite numbers")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError("Number exceeds finite range") from error
    if not math.isfinite(result):
        raise ValueError("Scores and forecasts must be finite numbers")
    return result


def _vector(
    value: Any, length: int, *, binary: bool = False, preserve_ordering: bool = False
) -> list[float]:
    if not isinstance(value, list) or len(value) != length:
        raise ValueError("Item arrays must be aligned")
    if binary and any(type(v) is not int or v not in (0, 1) for v in value):
        raise ValueError("Behavior risks must be integer zero or one")
    converted = [_number(v) for v in value]
    return list(value) if preserve_ordering else converted


def binary_auc(scores: list[float], labels: list[int]) -> float | None:
    """Exact midrank tie handling; one-class panels remain undefined."""
    values = _vector(scores, len(labels), preserve_ordering=True)
    labels = [int(label) for label in _vector(labels, len(labels), binary=True)]
    positives = int(sum(labels))
    negatives = len(labels) - positives
    if not positives or not negatives:
        return None
    ordered = sorted(zip(values, labels, strict=True))
    credit, negatives_before, begin = 0.0, 0, 0
    while begin < len(ordered):
        end = begin + 1
        while end < len(ordered) and ordered[end][0] == ordered[begin][0]:
            end += 1
        positive_ties = sum(int(row[1]) for row in ordered[begin:end])
        negative_ties = end - begin - positive_ties
        credit += positive_ties * (negatives_before + 0.5 * negative_ties)
        negatives_before += negative_ties
        begin = end
    return credit / (positives * negatives)


def fixed_predictions(document: Mapping[str, Any]) -> dict[str, Any]:
    """Validate/copy only forecast metadata; never access behavior or scores."""
    if document.get("schema_version") != "control-transfer/v1":
        raise ValueError("schema_version must be control-transfer/v1")
    if (
        document.get("evidence_status") not in EVIDENCE
        or type(document.get("synthetic")) is not bool
    ):
        raise ValueError("Explicit evidence status and synthetic Boolean are required")
    policy = document.get("endpoint_policy")
    if policy not in ("disjoint", "shared_fixed_cases"):
        raise ValueError("An explicit endpoint policy is required")
    if document["evidence_status"] == "independent_confirmation" and policy != "disjoint":
        raise ValueError("Independent prompt confirmation requires disjoint endpoints")
    if document["evidence_status"] == "independent_confirmation" or "evidence_receipts" in document:
        evidence(dict(document))
    lock = document.get("prediction_lock_sha256")
    if (
        not isinstance(lock, str)
        or len(lock) != 64
        or any(c not in "0123456789abcdef" for c in lock)
    ):
        raise ValueError("An explicit external prediction-lock SHA256 is required")
    pairs = document.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("At least one prompt pair is required")
    seen, result = set(), []
    endpoints: set[tuple[str, int]] = set()
    for pair in pairs:
        if not isinstance(pair, Mapping):
            raise ValueError("Each pair must be an object")
        model, pair_id = _text(pair.get("model"), "model"), _text(pair.get("pair_id"), "pair_id")
        key = (model, pair_id)
        if key in seen:
            raise ValueError("Duplicate model/pair coordinate")
        seen.add(key)
        seeds: list[Any] = [pair.get(name) for name in ("left_seed", "right_seed")]
        if any(type(seed) is not int for seed in seeds) or seeds[0] >= seeds[1]:
            raise ValueError("Integer endpoints must have canonical increasing orientation")
        if policy == "disjoint" and any((model, seed) in endpoints for seed in seeds):
            raise ValueError("Shared endpoint in a disjoint cohort")
        endpoints.update((model, seed) for seed in seeds)
        kind = pair.get("pairing_type")
        if kind not in PAIR_TYPES:
            raise ValueError("Unknown pairing type")
        forecasts = pair.get("predictions")
        if not isinstance(forecasts, Mapping) or set(forecasts) != set(SCORES):
            raise ValueError("Both fixed state-score forecasts are required")
        clean = {}
        for score in SCORES:
            row = forecasts[score]
            if not isinstance(row, Mapping) or set(row) != set(PREDICTORS):
                raise ValueError("Full, cheap, uniform-mean and zero forecasts are required")
            clean[score] = {name: _number(row[name]) for name in PREDICTORS}
            if clean[score]["zero"] != 0:
                raise ValueError("Zero baseline must be exactly zero")
        result.append(
            {
                "model": model,
                "pair_id": pair_id,
                "left_seed": seeds[0],
                "right_seed": seeds[1],
                "pairing_type": kind,
                "predictions": clean,
            }
        )
    for model in {row["model"] for row in result}:
        for score in SCORES:
            if (
                len(
                    {
                        row["predictions"][score]["uniform_mean"]
                        for row in result
                        if row["model"] == model
                    }
                )
                != 1
            ):
                raise ValueError("The fixed mean baseline must be common to the model cohort")
    return {"prediction_lock_sha256": lock, "pairs": result}


def analyze_document(document: Mapping[str, Any]) -> dict[str, Any]:
    """Assess frozen transfer forecasts without fitting to evaluation labels."""
    forecasts = fixed_predictions(document)
    pending = document["evidence_status"] == "locked_prediction"
    observed_rows = []
    panel_by_model: dict[str, list[str]] = {}
    for pair, forecast in zip(document["pairs"], forecasts["pairs"], strict=True):
        if pending:
            if "behavior" in pair:
                raise ValueError("A locked-prediction-only record must omit behavior labels")
            observed_rows.append(
                {
                    **forecast,
                    "status": "awaiting_behavior",
                    "auc": None,
                    "gains": None,
                    "errors": None,
                }
            )
            continue
        ids = pair.get("item_ids")
        if (
            not isinstance(ids, list)
            or not ids
            or any(not isinstance(v, str) or not v for v in ids)
            or len(set(ids)) != len(ids)
        ):
            raise ValueError("Unique nonempty item identifiers are required")
        model = forecast["model"]
        if model in panel_by_model and ids != panel_by_model[model]:
            raise ValueError("Pairs within a model must use the same ordered panel")
        panel_by_model[model] = ids
        size = len(ids)
        scores, behavior = pair.get("scores"), pair.get("behavior")
        if (
            not isinstance(scores, Mapping)
            or set(scores) != {"loss", *SCORES}
            or not isinstance(behavior, Mapping)
        ):
            raise ValueError("Fixed scores and paired behavioral risks are required")
        if set(behavior) == {"risk_change"}:
            labels = [int(value) for value in _vector(behavior["risk_change"], size, binary=True)]
            increases, decreases = None, None
        elif set(behavior) == {"risk_source", "risk_target"}:
            left = _vector(behavior["risk_source"], size, binary=True)
            right = _vector(behavior["risk_target"], size, binary=True)
            labels = [int(abs(b - a)) for a, b in zip(left, right, strict=True)]
            increases = sum(b > a for a, b in zip(left, right, strict=True))
            decreases = sum(b < a for a, b in zip(left, right, strict=True))
        else:
            raise ValueError("Supply paired endpoint risks or explicit risk_change labels")
        auc: dict[str, Any] = {
            name: binary_auc(_vector(scores[name], size, preserve_ordering=True), labels)
            for name in ("loss", *SCORES)
        }
        gains: dict[str, Any] = {
            name: auc[name] - auc["loss"]
            if auc["loss"] is not None and auc[name] is not None
            else None
            for name in SCORES
        }
        errors = {
            name: {
                key: {
                    "signed": _number(value - gains[name]),
                    "absolute": abs(_number(value - gains[name])),
                }
                for key, value in forecast["predictions"][name].items()
            }
            if gains[name] is not None
            else None
            for name in SCORES
        }
        observed_rows.append(
            {
                **forecast,
                "status": "defined"
                if all(v is not None for v in gains.values())
                else "undefined_auc",
                "item_count": size,
                "risk_changes": sum(labels),
                "risk_increases": increases,
                "risk_decreases": decreases,
                "auc": auc,
                "gains": gains,
                "errors": errors,
            }
        )
    summaries = []
    for model in sorted({row["model"] for row in observed_rows}):
        rows = [row for row in observed_rows if row["model"] == model]
        common = [row for row in rows if row["status"] == "defined"]
        counts = Counter(row["pairing_type"] for row in common)
        for score in SCORES:
            maes: dict[str, Any] = {
                name: math.fsum(
                    row["errors"][score][name]["absolute"] / len(common) for row in common
                )
                if common
                else None
                for name in PREDICTORS
            }
            summaries.append(
                {
                    "model": model,
                    "score": score,
                    "pair_count": len(rows),
                    "common_valid_pairs": len(common),
                    "pairing_type_counts": dict(counts),
                    "mae": maes,
                    "mae_improvement": {
                        name: maes[name] - maes["full"] if common else None
                        for name in PREDICTORS
                        if name != "full"
                    },
                    "inference_status": (
                        "point_estimates_only; use separately verified crossed bootstrap intervals"
                    ),
                }
            )
    raw = json.dumps(
        document, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return {
        "schema_version": "control-transfer-result/v1",
        "evidence_status": document["evidence_status"],
        "synthetic": document["synthetic"],
        "input_canonical_sha256": hashlib.sha256(raw).hexdigest(),
        "prediction_lock_sha256": forecasts["prediction_lock_sha256"],
        "pairs": observed_rows,
        "summaries": summaries,
        "evidence_status_source": (
            "declared by input; this compact replay does not certify prospective isolation"
        ),
        "success_claim": (
            "none; point estimates do not establish independent prediction or efficiency gains"
        ),
    }
