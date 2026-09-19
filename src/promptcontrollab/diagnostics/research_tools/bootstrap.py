"""Shared panel and endpoint-component bootstrap for frozen forecast comparisons."""

from __future__ import annotations

import math
import random

from .common import JsonDict, number
from .transfer_prediction import PREDICTORS, SCORES, binary_auc


def _labels(pair: JsonDict) -> list[int]:
    behavior = pair["behavior"]
    if "risk_change" in behavior:
        return [int(value) for value in behavior["risk_change"]]
    return [
        abs(a - b) for a, b in zip(behavior["risk_source"], behavior["risk_target"], strict=True)
    ]


def _components(pairs: list[JsonDict]) -> list[list[int]]:
    remaining, groups = set(range(len(pairs))), []
    while remaining:
        component = [min(remaining)]
        remaining.remove(component[0])
        endpoints = {pairs[component[0]]["left_seed"], pairs[component[0]]["right_seed"]}
        changed = True
        while changed:
            changed = False
            for index in sorted(remaining):
                if endpoints & {pairs[index]["left_seed"], pairs[index]["right_seed"]}:
                    component.append(index)
                    endpoints.update((pairs[index]["left_seed"], pairs[index]["right_seed"]))
                    remaining.remove(index)
                    changed = True
        groups.append(component)
    return groups


def analyze_bootstrap(document: JsonDict, result: JsonDict) -> JsonDict:
    """Compute shared endpoint-aware bootstrap comparisons for frozen transfer forecasts."""
    settings = document.get("bootstrap", {})
    if not isinstance(settings, dict):
        raise ValueError("bootstrap must be an object")
    repetitions, seed = settings.get("repetitions", 199), settings.get("seed", 1729)
    confidence = number(settings.get("confidence", 0.95), "bootstrap.confidence")
    if type(repetitions) is not int or not 20 <= repetitions <= 2000:
        raise ValueError("bootstrap.repetitions must be an integer from 20 to 2000")
    if type(seed) is not int or not 0 < confidence < 1:
        raise ValueError(
            "bootstrap seed must be integer and confidence must be between zero and one"
        )
    if document["evidence_status"] == "locked_prediction":
        return {"status": "awaiting_behavior", "intervals": None}
    rng, models = random.Random(seed), []
    for model in sorted({pair["model"] for pair in document["pairs"]}):
        all_pairs = [pair for pair in document["pairs"] if pair["model"] == model]
        valid_ids = {
            row["pair_id"]
            for row in result["pairs"]
            if row["model"] == model and row["status"] == "defined"
        }
        # Validate actual shared endpoint observations before reducing to valid AUC pairs.
        endpoint_labels: dict[int, list[int]] = {}
        for pair in all_pairs:
            if "risk_source" not in pair["behavior"]:
                continue
            for endpoint, name in (("left_seed", "risk_source"), ("right_seed", "risk_target")):
                labels = pair["behavior"][name]
                if pair[endpoint] in endpoint_labels and endpoint_labels[pair[endpoint]] != labels:
                    raise ValueError("Shared endpoint behavioral labels disagree across pairs")
                endpoint_labels[pair[endpoint]] = labels
        pairs = [pair for pair in all_pairs if pair["pair_id"] in valid_ids]
        if not pairs:
            models.append(
                {
                    "model": model,
                    "status": "undefined_auc",
                    "intervals": None,
                    "valid_repetitions": 0,
                }
            )
            continue
        groups = _components(all_pairs)
        valid_map = {pair["pair_id"]: index for index, pair in enumerate(pairs)}
        # Preserve dependencies mediated by an otherwise undefined pair.
        groups = [
            [
                valid_map[all_pairs[index]["pair_id"]]
                for index in group
                if all_pairs[index]["pair_id"] in valid_map
            ]
            for group in groups
        ]
        groups = [group for group in groups if group]
        size = len(pairs[0]["item_ids"])
        panel_labels = [_labels(pair) for pair in pairs]
        family = [
            (score, predictor)
            for score in SCORES
            for predictor in PREDICTORS
            if predictor != "full"
        ]
        observed = {}
        for score, predictor in family:
            summary = next(
                row
                for row in result["summaries"]
                if row["model"] == model and row["score"] == score
            )
            observed[(score, predictor)] = summary["mae_improvement"][predictor]
        draws = []
        for _ in range(repetitions):
            # The same item indices and component multiplicities feed every score/predictor.
            indices = [rng.randrange(size) for _ in range(size)]
            chosen = [index for _ in groups for index in groups[rng.randrange(len(groups))]]
            errors = {}
            for index in set(chosen):
                pair, labels = pairs[index], [panel_labels[index][j] for j in indices]
                auc: JsonDict = {
                    name: binary_auc([pair["scores"][name][j] for j in indices], labels)
                    for name in ("loss", *SCORES)
                }
                if any(value is None for value in auc.values()):
                    break
                errors[index] = {
                    (score, predictor): abs(
                        pair["predictions"][score][predictor] - (auc[score] - auc["loss"])
                    )
                    for score in SCORES
                    for predictor in PREDICTORS
                }
            else:
                draws.append(
                    {
                        key: math.fsum(
                            errors[index][key] - errors[index][(key[0], "full")] for index in chosen
                        )
                        / len(chosen)
                        for key in family
                    }
                )
        intervals = None
        if len(draws) >= 20:
            # Shared maximum deviation gives a simultaneous descriptive bootstrap band
            # over the six comparisons within this model, not an across-model guarantee.
            maxima = sorted(max(abs(draw[key] - observed[key]) for key in family) for draw in draws)
            radius = maxima[min(len(maxima) - 1, math.ceil(confidence * len(maxima)) - 1)]
            intervals = [
                {
                    "score": score,
                    "baseline": predictor,
                    "mae_improvement": observed[(score, predictor)],
                    "lower": observed[(score, predictor)] - radius,
                    "upper": observed[(score, predictor)] + radius,
                }
                for score, predictor in family
            ]
        models.append(
            {
                "model": model,
                "status": "computed" if intervals is not None else "insufficient_valid_repetitions",
                "endpoint_component_count": len(groups),
                "endpoint_components": [
                    [pairs[index]["pair_id"] for index in group] for group in groups
                ],
                "endpoint_uncertainty": "conditional_on_one_connected_component"
                if len(groups) == 1
                else "resampled_connected_components",
                "shared_endpoint_labels": "checked_where_supplied"
                if endpoint_labels
                else "not_supplied",
                "common_valid_pairs": len(pairs),
                "undefined_pairs_excluded": len(all_pairs) - len(pairs),
                "valid_repetitions": len(draws),
                "undefined_repetitions": repetitions - len(draws),
                "intervals": intervals,
            }
        )
    return {
        "status": "computed",
        "method": (
            "shared-item and connected-endpoint-component bootstrap; "
            "within-model simultaneous maximum-deviation bands"
        ),
        "repetitions": repetitions,
        "seed": seed,
        "confidence": confidence,
        "models": models,
        "undefined_policy": (
            "No one-class AUC is imputed. Undefined observed pairs "
            "and undefined resamples are reported separately."
        ),
        "claim_scope": (
            "Frozen supplied forecasts only; descriptive uncertainty "
            "conditional on the supplied endpoint dependency graph."
        ),
    }
