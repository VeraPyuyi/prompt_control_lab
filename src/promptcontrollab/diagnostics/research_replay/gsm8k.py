# Adapted for PromptControlLab: generic identities and typed data-only entrypoints.
# Numerical ordering, seeds, corrections and missingness policies are retained.
"""Fixed-forecast AUC-gain statistics with shared pair/item resampling.

No fitting, prompt generation, or data preparation occurs in this module.
Undefined AUCs remain undefined; all inferential comparisons use one common
set of valid original pairs and one shared valid-bootstrap-draw mask.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

FAMILIES = ("primary", "norm")
BASELINES = ("cheap", "uniform_mean", "zero")
PREDICTORS = ("full", *BASELINES)
PAIR_TYPES = ("adjacent_seed", "selection_loss")


def _auc_plan(labels: np.ndarray[Any, Any], scores: np.ndarray[Any, Any]) -> tuple[Any, ...] | None:
    labels, scores = np.asarray(labels, dtype=float), np.asarray(scores, dtype=float)
    if labels.ndim != 1 or scores.shape != labels.shape:
        raise ValueError("AUC labels and scores must be aligned one-dimensional arrays")
    finite_labels = np.isfinite(labels)
    if np.any(finite_labels & (labels != 0.0) & (labels != 1.0)):
        raise ValueError("AUC labels must be binary 0/1")
    if not len(labels) or not finite_labels.all() or not np.isfinite(scores).all():
        return None
    order = np.argsort(scores, kind="stable")
    ordered_scores = scores[order]
    starts = np.r_[0, np.flatnonzero(ordered_scores[1:] != ordered_scores[:-1]) + 1]
    return order, starts, labels[order]


def _auc_draws(plan: tuple[Any, ...] | None, weights: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    """Exact tie-group weighted Mann-Whitney statistic for many draws."""
    result = np.full(len(weights), np.nan, dtype=float)
    if plan is None:
        return result
    order, starts, positive = plan
    ordered_weights = weights[:, order]
    positive_mass = np.add.reduceat(ordered_weights * positive, starts, axis=1)
    negative_mass = np.add.reduceat(ordered_weights * (1.0 - positive), starts, axis=1)
    negative_before = np.cumsum(negative_mass, axis=1) - negative_mass
    numerator = np.sum(positive_mass * (negative_before + 0.5 * negative_mass), axis=1)
    denominator = positive_mass.sum(axis=1) * negative_mass.sum(axis=1)
    np.divide(numerator, denominator, out=result, where=denominator > 0.0)
    return result


def weighted_binary_auc(
    labels: Sequence[float] | np.ndarray[Any, Any],
    scores: Sequence[float],
    weights: Sequence[float] | None = None,
) -> float | None:
    """Weighted binary AUC, awarding each exact score tie half a win.

    This computes the full weighted positive/negative comparison statistic,
    with no bins or tie jitter. Missing scores/labels or zero positive/negative
    mass return None. Nonbinary labels and malformed weights raise ValueError.
    """
    label_array, score_array = np.asarray(labels, dtype=float), np.asarray(scores, dtype=float)
    plan = _auc_plan(label_array, score_array)
    w = (
        np.ones(len(label_array), dtype=float)
        if weights is None
        else np.asarray(weights, dtype=float)
    )
    if w.shape != label_array.shape or not np.isfinite(w).all() or np.any(w < 0.0):
        raise ValueError("AUC weights must be aligned, finite, and nonnegative")
    if not len(w) or w.max() == 0.0:
        return None
    # AUC is scale-invariant; normalization prevents large-weight overflow.
    value = _auc_draws(plan, (w / w.max())[None, :])[0]
    return float(value) if np.isfinite(value) else None


weighted_auc = weighted_binary_auc


def _json_numbers(array: np.ndarray[Any, Any]) -> list[Any]:
    array = np.asarray(array, dtype=float)
    if array.ndim == 1:
        return [float(value) if np.isfinite(value) else None for value in array]
    return [_json_numbers(row) for row in array]


def _point(
    gains: np.ndarray[Any, Any], predictions: np.ndarray[Any, Any], indices: Sequence[int]
) -> dict[str, Any]:
    """Equal weight per common-valid original pair; no refitting."""
    result = {}
    indices = list(indices)
    for family_index, family in enumerate(FAMILIES):
        comparisons: dict[str, Any] = {}
        if indices:
            target = gains[indices, family_index]
            errors = np.abs(predictions[indices, family_index, :] - target[:, None])
            full_mae = float(errors[:, 0].mean())
        else:
            errors, full_mae = None, None
        for baseline_index, baseline in enumerate(BASELINES, start=1):
            comparisons[baseline] = {
                "full_mae": full_mae,
                "baseline_mae": float(errors[:, baseline_index].mean()) if indices else None,
                "mae_improvement": float((errors[:, baseline_index] - errors[:, 0]).mean())
                if indices
                else None,
            }
        result[family] = comparisons
    return result


def forecast_mae_statistics(
    score_arrays: Mapping[str, np.ndarray[Any, Any]],
    risk_change_labels: np.ndarray[Any, Any] | Mapping[str, np.ndarray[Any, Any]],
    pair_ids: Sequence[str],
    pairing_types: Sequence[str],
    fixed_predictions: Mapping[str, Mapping[str, np.ndarray[Any, Any]]],
    *,
    n_bootstrap: int = 20000,
    seed: int = 20260911,
    family_size: int = 22,
    family_alpha: float = 0.05,
    minimum_valid_pairs: int = 12,
    minimum_per_type: int = 6,
    minimum_valid_draw_fraction: float = 0.95,
    chunk_size: int = 256,
    return_bootstrap_draws: bool = False,
) -> dict[str, Any]:
    """Bootstrap MAE improvement of fixed full forecasts over three baselines.

    Score arrays primary/norm/loss are pair-by-item. Labels may be one shared
    pair-by-item array or a primary/norm mapping. Predictions are
    ``{family: {full, cheap, uniform_mean, zero}}`` with one value per pair.
    The target for each family is AUC(state score) - AUC(loss score).

    Each draw resamples the same item coordinates for every pair and family,
    then draws pairs within construction strata, preserving the observed
    common-valid stratum counts. Forecasts remain fixed. A draw is valid only
    when every sampled pair has defined AUCs in both families. Undefined AUCs
    on zero-weight pairs do not enter that draw. Separate RNG streams make the
    draw sequence and receipts independent of chunk_size.
    """
    pair_ids, pairing_types = list(pair_ids), list(pairing_types)
    pair_count = len(pair_ids)
    if (
        not pair_count
        or len(set(pair_ids)) != pair_count
        or any(not isinstance(p, str) or not p for p in pair_ids)
    ):
        raise ValueError("pair_ids must be nonempty, unique strings")
    if len(pairing_types) != pair_count or any(t not in PAIR_TYPES for t in pairing_types):
        raise ValueError("Pairing types must be aligned adjacent_seed/selection_loss values")
    for name, value, lower in (
        ("n_bootstrap", n_bootstrap, 1),
        ("chunk_size", chunk_size, 1),
        ("family_size", family_size, len(FAMILIES) * len(BASELINES)),
        ("minimum_valid_pairs", minimum_valid_pairs, 1),
        ("minimum_per_type", minimum_per_type, 1),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < lower:
            raise ValueError(f"{name} must be an integer >= {lower}")
    if not 0.0 < family_alpha < 1.0 or not 0.0 < minimum_valid_draw_fraction <= 1.0:
        raise ValueError("Invalid family alpha or valid-draw threshold")
    scores = {name: np.asarray(score_arrays[name], dtype=float) for name in (*FAMILIES, "loss")}
    shape = scores["loss"].shape
    if len(shape) != 2 or shape[0] != pair_count or shape[1] < 1:
        raise ValueError("Scores must be nonempty pair-by-item arrays")
    if any(array.shape != shape for array in scores.values()):
        raise ValueError("All score arrays must have the same pair/item coordinates")
    item_count = shape[1]
    labels = {
        family: np.asarray(
            risk_change_labels[family]
            if isinstance(risk_change_labels, Mapping)
            else risk_change_labels,
            dtype=float,
        )
        for family in FAMILIES
    }
    if any(array.shape != shape for array in labels.values()):
        raise ValueError("Risk-change labels must match the score array shape")
    prediction_array = np.empty((pair_count, len(FAMILIES), len(PREDICTORS)), dtype=float)
    for f, family in enumerate(FAMILIES):
        for p, predictor in enumerate(PREDICTORS):
            values = np.asarray(fixed_predictions[family][predictor], dtype=float)
            if values.shape != (pair_count,):
                raise ValueError("Fixed forecasts require one aligned prediction per pair")
            prediction_array[:, f, p] = values
    prediction_projection = {
        family: {
            predictor: _json_numbers(prediction_array[:, f, p])
            for p, predictor in enumerate(PREDICTORS)
        }
        for f, family in enumerate(FAMILIES)
    }
    prediction_sha256 = hashlib.sha256(
        json.dumps(
            prediction_projection, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    gains = np.full((pair_count, len(FAMILIES)), np.nan, dtype=float)
    state_auc = np.full_like(gains, np.nan)
    reference_auc = np.full_like(gains, np.nan)
    plans = {}
    unit_weights = np.ones((1, item_count), dtype=float)
    for f, family in enumerate(FAMILIES):
        for i in range(pair_count):
            state_plan = _auc_plan(labels[family][i], scores[family][i])
            loss_plan = _auc_plan(labels[family][i], scores["loss"][i])
            plans[(i, f)] = state_plan, loss_plan
            state_auc[i, f] = _auc_draws(state_plan, unit_weights)[0]
            reference_auc[i, f] = _auc_draws(loss_plan, unit_weights)[0]
            if np.isfinite(state_auc[i, f]) and np.isfinite(reference_auc[i, f]):
                gains[i, f] = state_auc[i, f] - reference_auc[i, f]
    common_valid = np.isfinite(gains).all(axis=1) & np.isfinite(prediction_array).all(axis=(1, 2))
    # Canonical pair order makes the RNG-to-pair mapping explicit and stable.
    valid_indices = sorted(np.flatnonzero(common_valid).tolist(), key=lambda i: pair_ids[i])
    valid_pair_ids = [pair_ids[i] for i in valid_indices]
    strata = {
        kind: [j for j, i in enumerate(valid_indices) if pairing_types[i] == kind]
        for kind in PAIR_TYPES
    }
    type_counts = {kind: len(indices) for kind, indices in strata.items()}
    point = _point(gains, prediction_array, valid_indices)
    gate_reasons = []
    if len(valid_indices) < minimum_valid_pairs:
        gate_reasons.append("insufficient_common_valid_original_pairs")
    if any(number < minimum_per_type for number in type_counts.values()):
        gate_reasons.append("insufficient_common_valid_pairs_per_type")
    pair_table = []
    for i, pair_id in enumerate(pair_ids):
        family_values, exclusion_reasons = {}, []
        for f, family in enumerate(FAMILIES):
            if not np.isfinite(state_auc[i, f]):
                exclusion_reasons.append(f"{family}:undefined_state_auc")
            if not np.isfinite(reference_auc[i, f]):
                exclusion_reasons.append(f"{family}:undefined_loss_auc")
            if not np.isfinite(prediction_array[i, f]).all():
                exclusion_reasons.append(f"{family}:nonfinite_fixed_prediction")
            family_values[family] = {
                "state_auc": float(state_auc[i, f]) if np.isfinite(state_auc[i, f]) else None,
                "loss_auc": float(reference_auc[i, f])
                if np.isfinite(reference_auc[i, f])
                else None,
                "gain": float(gains[i, f]) if np.isfinite(gains[i, f]) else None,
                "predictions": dict(
                    zip(PREDICTORS, _json_numbers(prediction_array[i, f]), strict=False)
                ),
                "mae_improvements": {
                    baseline: (
                        float(
                            abs(prediction_array[i, f, b] - gains[i, f])
                            - abs(prediction_array[i, f, 0] - gains[i, f])
                        )
                        if np.isfinite(gains[i, f])
                        and np.isfinite(prediction_array[i, f, [0, b]]).all()
                        else None
                    )
                    for b, baseline in enumerate(BASELINES, start=1)
                },
            }
        pair_table.append(
            {
                "pair_id": pair_id,
                "pairing_type": pairing_types[i],
                "common_valid": bool(common_valid[i]),
                "exclusion_reasons": exclusion_reasons,
                "families": family_values,
            }
        )
    delete_one = []
    for i, pair_id in enumerate(pair_ids):
        remaining = [j for j in valid_indices if j != i]
        counts = Counter(pairing_types[j] for j in remaining)
        delete_one.append(
            {
                "deleted_pair_id": pair_id,
                "deleted_common_valid_pair": bool(common_valid[i]),
                "remaining_common_valid_pairs": len(remaining),
                "remaining_pairs_per_type": {kind: counts[kind] for kind in PAIR_TYPES},
                "meets_original_pair_count_gate": len(remaining) >= minimum_valid_pairs
                and all(counts[kind] >= minimum_per_type for kind in PAIR_TYPES),
                "estimates": _point(gains, prediction_array, remaining),
            }
        )
    bootstrap_values = np.full((n_bootstrap, len(FAMILIES), len(BASELINES)), np.nan, dtype=float)
    valid_draw_mask = np.zeros(n_bootstrap, dtype=bool)
    item_digest, pair_digest = hashlib.sha256(), hashlib.sha256()
    attempted = 0
    if valid_indices:
        streams = np.random.SeedSequence(seed).spawn(1 + len(PAIR_TYPES))
        item_rng = np.random.default_rng(streams[0])
        pair_rngs = {
            kind: np.random.default_rng(streams[k + 1]) for k, kind in enumerate(PAIR_TYPES)
        }
        probabilities = np.full(item_count, 1.0 / item_count)
        valid_predictions = prediction_array[valid_indices]
        for start in range(0, n_bootstrap, chunk_size):
            stop = min(start + chunk_size, n_bootstrap)
            batch = stop - start
            item_counts = item_rng.multinomial(item_count, probabilities, size=batch)
            pair_counts = np.zeros((batch, len(valid_indices)), dtype=np.int64)
            for kind, indices in strata.items():
                if indices:
                    count = len(indices)
                    pair_counts[:, indices] = pair_rngs[kind].multinomial(
                        count, np.full(count, 1.0 / count), size=batch
                    )
            item_digest.update(item_counts.astype("<u4", copy=False).tobytes())
            pair_digest.update(pair_counts.astype("<u4", copy=False).tobytes())
            weights = item_counts.astype(float)
            draw_gains = np.full((batch, len(valid_indices), len(FAMILIES)), np.nan, dtype=float)
            for j, original_index in enumerate(valid_indices):
                for f in range(len(FAMILIES)):
                    state_plan, loss_plan = plans[(original_index, f)]
                    draw_gains[:, j, f] = _auc_draws(state_plan, weights) - _auc_draws(
                        loss_plan, weights
                    )
            selected = pair_counts > 0
            valid_draws = ~np.any(selected & ~np.isfinite(draw_gains).all(axis=2), axis=1)
            full_errors = np.abs(valid_predictions[None, :, :, 0] - draw_gains)
            base_errors = np.abs(valid_predictions[None, :, :, 1:] - draw_gains[:, :, :, None])
            differences = base_errors - full_errors[:, :, :, None]
            # Zero-weight pairs are absent, not imputed. Undefined selected
            # pairs keep NaN and invalidate this shared draw for all contrasts.
            contributions = np.where(selected[:, :, None, None], differences, 0.0)
            values = np.sum(contributions * pair_counts[:, :, None, None], axis=1) / len(
                valid_indices
            )
            bootstrap_values[start:stop][valid_draws] = values[valid_draws]
            valid_draw_mask[start:stop] = valid_draws
            attempted += batch
    valid_draws = int(valid_draw_mask.sum())
    valid_fraction = valid_draws / attempted if attempted else None
    if valid_fraction is None or valid_fraction < minimum_valid_draw_fraction:
        gate_reasons.append("insufficient_shared_valid_bootstrap_draw_fraction")
    inferential = not gate_reasons
    comparison_alpha = family_alpha / family_size
    quantile_levels = [comparison_alpha / 2.0, 1.0 - comparison_alpha / 2.0]
    comparisons: dict[str, Any] = {}
    for f, family in enumerate(FAMILIES):
        comparisons[family] = {}
        for b, baseline in enumerate(BASELINES):
            interval = (
                np.quantile(bootstrap_values[valid_draw_mask, f, b], quantile_levels).tolist()
                if inferential
                else None
            )
            comparisons[family][baseline] = {
                **point[family][baseline],
                "interval": interval,
                "confidence_level": 1.0 - comparison_alpha if inferential else None,
                "valid_bootstrap_draws": valid_draws,
                "positive_improvement": "baseline_mae_minus_full_mae",
            }
    result = {
        "schema": "diagnostic.gsm8k-transfer.fixed-forecast-statistics.v1",
        "status": "inferential" if inferential else "descriptive",
        "gate_reasons": gate_reasons,
        "pair_count": pair_count,
        "item_count": item_count,
        "common_valid_original_pairs": len(valid_indices),
        "common_valid_pair_ids": valid_pair_ids,
        "common_valid_pairs_per_type": type_counts,
        "minimum_valid_pairs": minimum_valid_pairs,
        "minimum_per_type": minimum_per_type,
        "minimum_valid_draw_fraction": minimum_valid_draw_fraction,
        "requested_bootstrap_draws": n_bootstrap,
        "attempted_bootstrap_draws": attempted,
        "valid_bootstrap_draws": valid_draws,
        "valid_bootstrap_fraction": valid_fraction,
        "seed": int(seed),
        "bonferroni_family_size": family_size,
        "family_alpha": family_alpha,
        "comparison_alpha": comparison_alpha,
        "quantile_levels": quantile_levels,
        "comparisons": comparisons,
        "pair_table": pair_table,
        "delete_one_pair": delete_one,
        "fixed_predictions_sha256": prediction_sha256,
        "forecasts_refit": False,
        "resampling": {
            "scheme": "shared_item_multinomial_and_stratified_pair_multinomial",
            "pair_count_unit": "common_valid_pair",
            "pair_order": valid_pair_ids,
            "item_count_sha256": item_digest.hexdigest() if attempted else None,
            "pair_count_sha256": pair_digest.hexdigest() if attempted else None,
            "shared_across_families_and_baselines": True,
            "common_valid_draw_mask": True,
            "weighting": "equal_pair_weights_preserving_observed_valid_stratum_counts",
        },
    }
    if return_bootstrap_draws:
        result["bootstrap_improvement_draws"] = _json_numbers(bootstrap_values)
        result["bootstrap_valid_mask"] = valid_draw_mask.tolist()
    return result


bootstrap_mae_improvement = forecast_mae_statistics
