# Adapted for PromptControlLab: generic identities and typed data-only entrypoints.
# Numerical ordering, seeds, corrections and missingness policies are retained.
"""Reviewed complete-panel statistics with shared items and within-model pair draws."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from numbers import Real
from typing import Any, cast

import numpy as np

PARSERS = ("strict", "leading", "terminal")
BUDGETS = (1, 2, 4, 8, 16, 32)
CONDITIONS = tuple((parser, budget) for parser in PARSERS for budget in BUDGETS)
SCORES = ("primary", "norm", "loss")
STATE_FAMILIES = ("primary", "norm")
CHANNELS = ("overall", "parse", "correctness")
METRICS = (*SCORES, "primary_gap", "norm_gap")
BOOTSTRAP_DRAWS = 20_000
BOOTSTRAP_SEED = 20260908
MIN_PAIRS = 12
MIN_VALID_FRACTION = 0.95
ALPHA = 0.05
COMPARISONS = 18
_REQUIRED = frozenset(
    {
        "model",
        "pair",
        "item_id",
        "item_index",
        "parser",
        "budget",
        "risk_source",
        "risk_target",
        "parse_source",
        "parse_target",
        "correct_source",
        "correct_target",
        "y",
        "channel",
        "primary",
        "norm",
        "loss",
        "first_legal_source",
        "first_legal_target",
    }
)


def _binary(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value not in (0, 1):
        raise ValueError(f"{name} must be integer zero or one")
    return int(value)


def _boolean(value: Any, name: str) -> bool:
    if not isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{name} must be a boolean")
    return bool(value)


def derive_channel(
    risk_source: int, risk_target: int, parse_source: bool, parse_target: bool
) -> str:
    """Classify risk switches; silent parseability switches remain stable negatives."""
    source = _binary(risk_source, "risk_source")
    target = _binary(risk_target, "risk_target")
    source_parse = _boolean(parse_source, "parse_source")
    target_parse = _boolean(parse_target, "parse_target")
    if (source == 0 and not source_parse) or (target == 0 and not target_parse):
        raise ValueError("An unparseable answer cannot have zero risk")
    if source == target:
        return "stable"
    return "parse" if source_parse != target_parse else "correctness"


@dataclass(frozen=True)
class ModelRows:
    """Arrays use condition, pair, item axes; scores use pair, item, score."""

    pairs: tuple[Any, ...]
    scores: np.ndarray[Any, Any]
    y: np.ndarray[Any, Any]
    channel: np.ndarray[Any, Any]
    parse_source: np.ndarray[Any, Any]
    parse_target: np.ndarray[Any, Any]
    risk_source: np.ndarray[Any, Any]
    risk_target: np.ndarray[Any, Any]
    first_legal_source: np.ndarray[Any, Any]
    first_legal_target: np.ndarray[Any, Any]


@dataclass(frozen=True)
class ValidatedRows:
    """Hold validated observations and their aligned prompt-pair coordinates."""
    models: dict[str, ModelRows]
    item_ids: tuple[Any, ...]
    row_count: int
    strict_contract: bool


def _identity(value: Any, name: str) -> Any:
    if isinstance(value, bool) or not isinstance(value, (str, int)) or value == "":
        raise ValueError(f"{name} must be a nonempty string or integer identity")
    return value


def _identity_sort(value: Any) -> tuple[str, Any]:
    return type(value).__name__, value


def validate_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    strict_contract: bool = True,
    model_keys: tuple[str, ...] | None = None,
) -> ValidatedRows:
    """Reject partial cells, duplicates, invalid risks, and any score/identity drift."""
    by_key: dict[tuple[Any, ...], Mapping[str, Any]] = {}
    baselines: dict[tuple[Any, ...], tuple[Any, ...]] = {}
    pairs_by_model: dict[str, set[Any]] = {}
    items_by_index: dict[int, Any] = {}
    indices_by_item: dict[Any, int] = {}
    for number, row in enumerate(rows, start=1):
        if not isinstance(row, Mapping):
            raise ValueError(f"Row {number} must be a dictionary")
        missing = _REQUIRED - row.keys()
        if missing:
            raise ValueError(f"Row {number} missing required fields: {sorted(missing)}")
        model = row["model"]
        if not isinstance(model, str) or not model:
            raise ValueError(f"Row {number} has an invalid model identity")
        pair = _identity(row["pair"], "pair")
        item = _identity(row["item_id"], "item_id")
        index = row["item_index"]
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise ValueError("item_index must be a nonnegative integer")
        if items_by_index.get(index, item) != item or indices_by_item.get(item, index) != index:
            raise ValueError("Shared item identity/index mismatch")
        items_by_index[index] = item
        indices_by_item[item] = index
        parser, budget = row["parser"], row["budget"]
        if (
            isinstance(budget, bool)
            or not isinstance(budget, int)
            or (parser, budget) not in CONDITIONS
        ):
            raise ValueError(f"Unknown parser/budget condition: {(parser, budget)!r}")
        key = (model, pair, item, parser, budget)
        if key in by_key:
            raise ValueError(f"Duplicate row key: {key!r}")
        source_risk = _binary(row["risk_source"], "risk_source")
        target_risk = _binary(row["risk_target"], "risk_target")
        source_parse = _boolean(row["parse_source"], "parse_source")
        target_parse = _boolean(row["parse_target"], "parse_target")
        for side, risk, parse in (
            ("source", source_risk, source_parse),
            ("target", target_risk, target_parse),
        ):
            correct = row[f"correct_{side}"]
            if parse:
                if not isinstance(correct, bool) or risk != int(not correct):
                    raise ValueError(f"Inconsistent parseable {side} correctness/risk")
            elif correct is not None or risk != 1:
                raise ValueError(f"Unparseable {side} requires null correctness and risk one")
        expected_channel = derive_channel(source_risk, target_risk, source_parse, target_parse)
        if _binary(row["y"], "y") != int(source_risk != target_risk):
            raise ValueError("y must equal the indicator of differing endpoint risks")
        if row["channel"] != expected_channel:
            raise ValueError("Channel is inconsistent with risk and parseability")
        row_scores = []
        for name in SCORES:
            score = row[name]
            if isinstance(score, bool) or not isinstance(score, Real) or not math.isfinite(score):
                raise ValueError(f"{name} must be a finite numerical score")
            row_scores.append(float(score))
        first_source_flag = _boolean(row["first_legal_source"], "first_legal_source")
        first_target_flag = _boolean(row["first_legal_target"], "first_legal_target")
        baseline = (*row_scores, first_source_flag, first_target_flag, index)
        base_key = (model, pair, item)
        if baselines.get(base_key, baseline) != baseline:
            raise ValueError("Fixed scores, first-token legality, or item index drift across cells")
        baselines[base_key] = baseline
        pairs_by_model.setdefault(model, set()).add(pair)
        by_key[key] = row
    if not by_key:
        raise ValueError("No rows; production contract requires a complete matrix")
    item_count = len(indices_by_item)
    if strict_contract and (
        (
            len(pairs_by_model) != 3
            or (model_keys is not None and set(pairs_by_model) != set(model_keys))
        )
        or item_count != 400
        or any(len(pairs) != 16 for pairs in pairs_by_model.values())
    ):
        raise ValueError(
            "The production contract requires 3 named models, 16 pairs each, 400 items"
        )
    if set(items_by_index) != set(range(item_count)):
        raise ValueError("Shared item indices must be contiguous from zero")
    items = tuple(items_by_index[index] for index in range(item_count))
    model_names = tuple(model for model in (model_keys or ()) if model in pairs_by_model)
    model_names += tuple(sorted(set(pairs_by_model) - set(model_names)))
    output: dict[str, ModelRows] = {}
    for model in model_names:
        pairs = tuple(sorted(pairs_by_model[model], key=_identity_sort))
        shape = (len(CONDITIONS), len(pairs), item_count)
        arrays = {
            name: np.zeros(shape, dtype=np.uint8)
            for name in (
                "y",
                "channel",
                "parse_source",
                "parse_target",
                "risk_source",
                "risk_target",
            )
        }
        scores = np.empty((len(pairs), item_count, len(SCORES)), dtype=np.float64)
        first_source = np.empty((len(pairs), item_count), dtype=bool)
        first_target = np.empty_like(first_source)
        for pair_index, pair in enumerate(pairs):
            for item_index, item in enumerate(items):
                base = baselines.get((model, pair, item))
                if base is None:
                    raise ValueError(
                        f"Missing shared model/pair/item identity: {(model, pair, item)}"
                    )
                scores[pair_index, item_index] = base[:3]
                first_source[pair_index, item_index] = base[3]
                first_target[pair_index, item_index] = base[4]
                for cell, (parser, budget) in enumerate(CONDITIONS):
                    cell_row = by_key.get((model, pair, item, parser, budget))
                    if cell_row is None:
                        raise ValueError(f"Missing row/cell: {(model, pair, item, parser, budget)}")
                    for name, array in arrays.items():
                        value = cell_row[name]
                        array[cell, pair_index, item_index] = (
                            ("stable", "parse", "correctness").index(value)
                            if name == "channel"
                            else value
                        )
        output[model] = ModelRows(
            pairs,
            scores,
            arrays["y"],
            arrays["channel"],
            arrays["parse_source"],
            arrays["parse_target"],
            arrays["risk_source"],
            arrays["risk_target"],
            first_source,
            first_target,
        )
    return ValidatedRows(output, items, len(by_key), strict_contract)


@dataclass(frozen=True)
class BootstrapWeights:
    """Hold shared pair and item resampling weights with reproducibility metadata."""
    item_weights: np.ndarray[Any, Any]
    pair_weights: dict[str, np.ndarray[Any, Any]]


def make_bootstrap_weights(
    item_count: int, pair_counts: Mapping[str, int], *, draws: int, seed: int
) -> BootstrapWeights:
    """One shared item stream and an independent pair stream for each sorted model.

    A row represents one crossed draw, never an independently sampled pair-item
    row. Separate SeedSequence children make generation independent of chunking.
    """
    if item_count < 1 or draws < 1 or any(count < 1 for count in pair_counts.values()):
        raise ValueError("Positive item/pair/draw counts are required")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("bootstrap_seed must be a nonnegative integer")
    models = sorted(pair_counts)
    streams = np.random.SeedSequence(seed).spawn(len(models) + 1)

    def sample(count: int, stream: np.random.SeedSequence) -> np.ndarray[Any, Any]:
        dtype = np.uint16 if count <= np.iinfo(np.uint16).max else np.uint32
        return (
            np.random.default_rng(stream)
            .multinomial(count, np.full(count, 1.0 / count), size=draws)
            .astype(dtype)
        )

    item_weights = sample(item_count, streams[0])
    pair_weights = {
        model: sample(pair_counts[model], stream)
        for model, stream in zip(models, streams[1:], strict=True)
    }
    return BootstrapWeights(item_weights, pair_weights)


@dataclass(frozen=True)
class _ScoreOrder:
    order: np.ndarray[Any, Any]
    group_starts: np.ndarray[Any, Any]

    @classmethod
    def build(cls, scores: np.ndarray[Any, Any]) -> _ScoreOrder:
        order = np.argsort(scores, kind="stable")
        ordered_scores = scores[order]
        starts = np.r_[0, np.flatnonzero(ordered_scores[1:] != ordered_scores[:-1]) + 1]
        return cls(order, starts)

    def grouped(self, values: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
        return np.add.reduceat(values, self.group_starts, axis=1)


def _divide(
    numerator: np.ndarray[Any, Any], denominator: np.ndarray[Any, Any]
) -> np.ndarray[Any, Any]:
    result = np.full(np.broadcast_shapes(numerator.shape, denominator.shape), np.nan)
    np.divide(numerator, denominator, out=result, where=denominator > 0)
    return result


def weighted_auc(
    y: Iterable[int], scores: Iterable[float], weights: Iterable[float] | None = None
) -> float | None:
    """Tie-aware weighted P(score_positive > score_negative), plus half ties."""
    labels = np.asarray(list(y))
    values = np.asarray(list(scores), dtype=float)
    mass = np.ones_like(values) if weights is None else np.asarray(list(weights), dtype=float)
    if (
        labels.ndim != 1
        or values.shape != labels.shape
        or mass.shape != labels.shape
        or not np.all(np.isin(labels, (0, 1)))
        or not np.all(np.isfinite(values))
        or not np.all(np.isfinite(mass))
        or np.any(mass < 0)
    ):
        raise ValueError("AUC requires aligned binary labels, finite scores, nonnegative weights")
    if len(labels) == 0:
        return None
    order = _ScoreOrder.build(values)
    sorted_mass = mass[order.order][None, :]
    positive = order.grouped(sorted_mass * labels[order.order])
    negative = order.grouped(sorted_mass * (1 - labels[order.order]))
    numerator = np.sum(positive * (np.cumsum(negative, axis=1) - 0.5 * negative), axis=1)
    denominator = positive.sum(axis=1) * negative.sum(axis=1)
    value = _divide(numerator, denominator)[0]
    return float(value) if np.isfinite(value) else None


def _auc_channels(
    orders: tuple[_ScoreOrder, ...],
    y: np.ndarray[Any, Any],
    channels: np.ndarray[Any, Any],
    item_weights: np.ndarray[Any, Any],
    chunk_size: int,
) -> tuple[np.ndarray[Any, Any], float]:
    """All positives and each positive channel share exactly the y=0 negatives.

    Sort scores once per original pair. Vectorize across draws; reduce tied score
    groups once per chunk. The same sorted negative cumulative sums serve all
    positive channels. No row resampling or per-draw sorting is performed.
    """
    draws = len(item_weights)
    output = np.full((draws, len(CHANNELS), len(SCORES)), np.nan)
    max_mixture_error = 0.0
    if not np.any(y == 0) or not np.any(y == 1):
        return output, max_mixture_error
    for start in range(0, draws, chunk_size):
        stop = min(draws, start + chunk_size)
        weights = item_weights[start:stop]
        for score, order in enumerate(orders):
            sorted_weights = weights[:, order.order].astype(np.float64, order="C")
            all_mass = order.grouped(sorted_weights)
            negative = order.grouped(sorted_weights * (y[order.order] == 0))
            parse = order.grouped(sorted_weights * (channels[order.order] == 1))
            overall = all_mass - negative
            correctness = overall - parse
            below = np.cumsum(negative, axis=1) - 0.5 * negative
            negative_count = negative.sum(axis=1)
            positive_count = overall.sum(axis=1)
            parse_count = parse.sum(axis=1)
            correct_count = correctness.sum(axis=1)
            overall_auc = _divide((overall * below).sum(axis=1), positive_count * negative_count)
            parse_auc = _divide((parse * below).sum(axis=1), parse_count * negative_count)
            correct_auc = _divide((correctness * below).sum(axis=1), correct_count * negative_count)
            output[start:stop, 0, score] = overall_auc
            output[start:stop, 1, score] = parse_auc
            output[start:stop, 2, score] = correct_auc
            reconstructed = _divide(
                np.nan_to_num(parse_auc) * parse_count + np.nan_to_num(correct_auc) * correct_count,
                positive_count,
            )
            finite = np.isfinite(overall_auc)
            if finite.any():
                max_mixture_error = max(
                    max_mixture_error,
                    float(np.max(np.abs(overall_auc[finite] - reconstructed[finite]))),
                )
    return output, max_mixture_error


def _metrics(aucs: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    return np.concatenate((aucs, aucs[..., :2] - aucs[..., 2:3]), axis=-1)


def _number(value: Any) -> float | None:
    return float(value) if np.isfinite(value) else None


def _mean(values: np.ndarray[Any, Any]) -> float | None:
    return float(np.mean(values)) if len(values) else None


def _direction(value: float | None) -> str:
    if value is None:
        return "undefined"
    return "positive" if value > 0 else "negative" if value < 0 else "zero"


def _interval_side(interval: list[float] | None) -> str:
    if interval is None:
        return "undefined"
    if interval[0] > 0:
        return "positive"
    return "negative" if interval[1] < 0 else "includes_zero"


def _summarize(
    values: np.ndarray[Any, Any],
    point: float | None,
    quantiles: tuple[float, float],
    pair_count: int,
    *,
    exploratory: bool,
) -> dict[str, Any]:
    finite = values[np.isfinite(values)]
    interval = np.quantile(finite, quantiles, method="linear").tolist() if len(finite) else None
    return {
        "point": point,
        "point_direction": _direction(point),
        "interval": interval,
        "interval_side": _interval_side(interval),
        "estimable_pairs": pair_count,
        "valid_draws": len(finite),
        "undefined_draws": len(values) - len(finite),
        "valid_fraction": len(finite) / len(values),
        "exploratory": exploratory,
    }


class _CellMeans:
    """Fixed original pair masks; a zero-weight undefined pair does not spoil a draw."""

    def __init__(self, draws: int) -> None:
        shape = (len(CONDITIONS), len(CHANNELS), draws)
        self.sums = np.zeros((*shape, len(METRICS)), dtype=np.float64)
        self.denominators = np.zeros(shape, dtype=np.float64)
        self.invalid = np.zeros(shape, dtype=bool)

    def add(
        self,
        cell: int,
        point: np.ndarray[Any, Any],
        draws: np.ndarray[Any, Any],
        weights: np.ndarray[Any, Any],
    ) -> None:
        for channel in range(len(CHANNELS)):
            if not np.isfinite(point[channel, 0]):
                continue
            values = _metrics(draws[:, channel])
            self.sums[cell, channel] += np.nan_to_num(values) * weights[:, None]
            self.denominators[cell, channel] += weights
            self.invalid[cell, channel] |= (weights > 0) & ~np.isfinite(values[:, 0])

    def values(self, cell: int, channel: int) -> np.ndarray[Any, Any]:
        values = _divide(self.sums[cell, channel], self.denominators[cell, channel, :, None])
        values[self.invalid[cell, channel]] = np.nan
        return values


def _primary_summary(
    data: ModelRows,
    point_aucs: np.ndarray[Any, Any],
    common: np.ndarray[Any, Any],
    sums: np.ndarray[Any, Any],
    denominator: np.ndarray[Any, Any],
    invalid: np.ndarray[Any, Any],
) -> dict[str, Any]:
    """Summarize primary contrasts using the original correction family and coverage rules."""
    native = CONDITIONS.index(("strict", 8))
    stopped = CONDITIONS.index(("strict", 1))
    counts = int(common.sum())
    pair_indices = np.flatnonzero(common)
    endpoint_points = np.stack((point_aucs[native, :, 0], point_aucs[stopped, :, 0]), axis=1)
    pair_gaps = endpoint_points[..., :2] - endpoint_points[..., 2:3]
    endpoint_draws = _divide(sums, denominator[:, None, None])
    endpoint_draws[invalid] = np.nan
    quantiles = (ALPHA / (2 * COMPARISONS), 1 - ALPHA / (2 * COMPARISONS))
    families = {}
    for family_index, family in enumerate(STATE_FAMILIES):
        gaps = pair_gaps[common, :, family_index]
        points = [_mean(gaps[:, condition]) for condition in range(2)]
        points.append(cast(float, points[1]) - cast(float, points[0]) if counts else None)
        draws = endpoint_draws[:, :, family_index]
        draw_columns = (draws[:, 0], draws[:, 1], draws[:, 1] - draws[:, 0])
        names = ("native_gap", "stopped_gap", "gap_change")
        estimands = {
            name: _summarize(values, point, quantiles, counts, exploratory=False)
            for name, values, point in zip(names, draw_columns, points, strict=True)
        }
        reasons = []
        if counts < MIN_PAIRS:
            reasons.append("fewer_than_12_common_pairs")
        if any(item["valid_fraction"] < MIN_VALID_FRACTION for item in estimands.values()):
            reasons.append("valid_draw_fraction_below_0.95")
        inferential = not reasons
        shift = inferential and estimands["gap_change"]["interval_side"] in ("positive", "negative")
        native_side = estimands["native_gap"]["interval_side"]
        stopped_side = estimands["stopped_gap"]["interval_side"]
        reversal = shift and {native_side, stopped_side} == {"positive", "negative"}
        direction = "unsupported"
        if reversal:
            direction = "loss_to_state" if stopped_side == "positive" else "state_to_loss"
        elif shift:
            direction = (
                "toward_state"
                if estimands["gap_change"]["interval_side"] == "positive"
                else "toward_loss"
            )
        sensitivity = []
        sign_changes = []
        for local_index, pair_index in enumerate(pair_indices):
            remaining = np.delete(gaps, local_index, axis=0)
            omitted_points = [_mean(remaining[:, condition]) for condition in range(2)]
            omitted_points.append(
                cast(float, omitted_points[1]) - cast(float, omitted_points[0])
                if len(remaining)
                else None
            )
            changed = [
                name
                for name, before, after in zip(names, points, omitted_points, strict=True)
                if before is not None
                and after is not None
                and _direction(before) != _direction(after)
            ]
            pair = data.pairs[pair_index]
            sensitivity.append(
                {
                    "omitted_pair": pair,
                    "remaining_pairs": len(remaining),
                    "points": dict(zip(names, omitted_points, strict=True)),
                    "directions": {
                        name: _direction(value)
                        for name, value in zip(names, omitted_points, strict=True)
                    },
                    "sign_changes": changed,
                }
            )
            if changed:
                sign_changes.append(pair)
        families[family] = {
            "estimands": estimands,
            "inferential": inferential,
            "ineligibility_reasons": reasons,
            "shift_supported": bool(shift),
            "reversal_supported": bool(reversal),
            "direction": direction,
            "leave_one_pair_out": sensitivity,
            "sign_change_omissions": sign_changes,
        }
    return {
        "all_pairs": list(data.pairs),
        "common_pairs": [data.pairs[index] for index in pair_indices],
        "common_pair_count": counts,
        "excluded_pairs": [
            {
                "pair": pair,
                "native_defined": bool(np.isfinite(point_aucs[native, index, 0, 0])),
                "stopped_defined": bool(np.isfinite(point_aucs[stopped, index, 0, 0])),
            }
            for index, pair in enumerate(data.pairs)
            if not common[index]
        ],
        "families": families,
    }


def _pair_secondary(
    data: ModelRows,
    point_aucs: np.ndarray[Any, Any],
    cell: int,
    pair: int,
) -> dict[str, Any]:
    """Compute descriptive secondary statistics for one prompt pair."""
    labels = data.y[cell, pair]
    channel_labels = data.channel[cell, pair]
    n_positive = int(labels.sum())
    n_negative = len(labels) - n_positive
    channels: dict[str, Any] = {}
    positive_counts = (
        n_positive,
        int((channel_labels == 1).sum()),
        int((channel_labels == 2).sum()),
    )
    for channel_index, channel in enumerate(CHANNELS):
        metrics = _metrics(point_aucs[cell, pair, channel_index])
        channels[channel] = {
            "positive_count": positive_counts[channel_index],
            "negative_count": n_negative,
            "auc": {name: _number(metrics[index]) for index, name in enumerate(SCORES)},
            "gaps": {
                name: _number(metrics[3 + index]) for index, name in enumerate(STATE_FAMILIES)
            },
        }
    mixture_weights = [count / n_positive if n_positive else None for count in positive_counts[1:]]
    reconstruction = {}
    errors = []
    for score in SCORES:
        overall = channels["overall"]["auc"][score]
        value = None
        if overall is not None:
            value = sum(
                weight * channels[channel]["auc"][score]
                for channel, weight in zip(CHANNELS[1:], mixture_weights, strict=True)
                if weight is not None and weight > 0
            )
            errors.append(abs(value - overall))
        reconstruction[score] = value
    parse_source = data.parse_source[cell, pair].astype(bool)
    parse_target = data.parse_target[cell, pair].astype(bool)
    return {
        "pair": data.pairs[pair],
        "counts": {
            "items": len(labels),
            "positive": n_positive,
            "negative": n_negative,
            "parse_positive": positive_counts[1],
            "correctness_positive": positive_counts[2],
            "parseable_source": int(parse_source.sum()),
            "parseable_target": int(parse_target.sum()),
            "correct_source": int((data.risk_source[cell, pair] == 0).sum()),
            "correct_target": int((data.risk_target[cell, pair] == 0).sum()),
            "silent_parse_switches": int(((labels == 0) & (parse_source != parse_target)).sum()),
            "first_legal_source": int(data.first_legal_source[pair].sum()),
            "first_legal_target": int(data.first_legal_target[pair].sum()),
        },
        "channels": channels,
        "mixture_check": {
            "estimable": bool(errors),
            "positive_weights": dict(zip(CHANNELS[1:], mixture_weights, strict=True)),
            "reconstructed_auc": reconstruction,
            "max_abs_error": max(errors) if errors else None,
        },
    }


def _secondary_summary(
    data: ModelRows,
    point_aucs: np.ndarray[Any, Any],
    means: _CellMeans,
    mixture_errors: np.ndarray[Any, Any],
) -> list[dict[str, Any]]:
    """Aggregate secondary statistics under the frozen resampling protocol."""
    cells = []
    for cell_index, (parser, budget) in enumerate(CONDITIONS):
        pairs = [
            _pair_secondary(data, point_aucs, cell_index, pair) for pair in range(len(data.pairs))
        ]
        summaries: dict[str, Any] = {}
        for channel_index, channel in enumerate(CHANNELS):
            mask = np.isfinite(point_aucs[cell_index, :, channel_index, 0])
            points = _metrics(point_aucs[cell_index, mask, channel_index])
            draws = means.values(cell_index, channel_index)
            summary = {
                name: _summarize(
                    draws[:, metric],
                    _mean(points[:, metric]),
                    (0.025, 0.975),
                    int(mask.sum()),
                    exploratory=True,
                )
                for metric, name in enumerate(METRICS)
            }
            summaries[channel] = {
                "estimable_pairs": [data.pairs[index] for index in np.flatnonzero(mask)],
                "estimable_pair_count": int(mask.sum()),
                "auc": {name: summary[name] for name in SCORES},
                "gaps": {name: summary[f"{name}_gap"] for name in STATE_FAMILIES},
            }
        checked = [pair for pair in pairs if pair["mixture_check"]["estimable"]]
        reconstructed = {
            score: (
                float(
                    np.mean([pair["mixture_check"]["reconstructed_auc"][score] for pair in checked])
                )
                if checked
                else None
            )
            for score in SCORES
        }
        cells.append(
            {
                "parser": parser,
                "budget": budget,
                "exploratory": True,
                "total_pairs": len(data.pairs),
                "pairs": pairs,
                "equal_pair_means": summaries,
                "mixture_check": {
                    "identity": (
                        "Per-pair positive-channel mixture with all y=0 rows as shared negatives"
                    ),
                    "pairs_checked": len(checked),
                    "max_abs_error": max(
                        (pair["mixture_check"]["max_abs_error"] for pair in checked), default=None
                    ),
                    "bootstrap_max_abs_error": float(mixture_errors[cell_index].max())
                    if checked
                    else None,
                    "equal_pair_reconstructed_auc": reconstructed,
                    "equal_pair_overall_auc": {
                        score: summaries["overall"]["auc"][score]["point"] for score in SCORES
                    },
                },
            }
        )
    return cells


def _analyze_model(
    data: ModelRows,
    item_weights: np.ndarray[Any, Any],
    pair_weights: np.ndarray[Any, Any],
    chunk_size: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, int]]:
    """Evaluate all frozen primary and secondary contrasts for one model."""
    draws = len(item_weights)
    point_aucs = np.full((len(CONDITIONS), len(data.pairs), len(CHANNELS), len(SCORES)), np.nan)
    mixture_errors = np.zeros((len(CONDITIONS), len(data.pairs)))
    means = _CellMeans(draws)
    native = CONDITIONS.index(("strict", 8))
    stopped = CONDITIONS.index(("strict", 1))
    positive_counts = data.y.sum(axis=2)
    defined = (positive_counts > 0) & (positive_counts < data.y.shape[2])
    common = defined[native] & defined[stopped]
    primary_sums = np.zeros((draws, 2, 2))
    primary_denominator = np.zeros(draws)
    primary_invalid = np.zeros((draws, 2), dtype=bool)
    augmented_weights = np.concatenate(
        (np.ones((1, data.y.shape[2]), dtype=item_weights.dtype), item_weights), axis=0
    )
    cache_hits = 0
    configurations = 0
    for pair in range(len(data.pairs)):
        orders = tuple(
            _ScoreOrder.build(data.scores[pair, :, index]) for index in range(len(SCORES))
        )
        cache: dict[tuple[bytes, bytes], tuple[np.ndarray[Any, Any], float]] = {}
        weights = pair_weights[:, pair].astype(float)
        if common[pair]:
            primary_denominator += weights
        for cell in range(len(CONDITIONS)):
            labels, channels = data.y[cell, pair], data.channel[cell, pair]
            key = labels.tobytes(), channels.tobytes()
            if key not in cache:
                cache[key] = _auc_channels(orders, labels, channels, augmented_weights, chunk_size)
                configurations += 1
            else:
                cache_hits += 1
            all_aucs, mixture_error = cache[key]
            point, sampled = all_aucs[0], all_aucs[1:]
            point_aucs[cell, pair] = point
            mixture_errors[cell, pair] = mixture_error
            means.add(cell, point, sampled, weights)
            if common[pair] and cell in (native, stopped):
                condition = 0 if cell == native else 1
                gaps = sampled[:, 0, :2] - sampled[:, 0, 2:3]
                primary_sums[:, condition] += np.nan_to_num(gaps) * weights[:, None]
                primary_invalid[:, condition] |= (weights > 0) & ~np.isfinite(gaps[:, 0])
    return (
        _primary_summary(
            data, point_aucs, common, primary_sums, primary_denominator, primary_invalid
        ),
        _secondary_summary(data, point_aucs, means, mixture_errors),
        {
            "unique_pair_label_channel_configurations": configurations,
            "reused_configurations": cache_hits,
        },
    )


def analyze_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    bootstrap_draws: int = BOOTSTRAP_DRAWS,
    bootstrap_seed: int = BOOTSTRAP_SEED,
    strict_contract: bool = True,
    bootstrap_chunk_size: int = 512,
    model_keys: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Analyze a complete frozen matrix with equal-pair crossed-bootstrap means.

    Only primary coverage gates (12 original common pairs, 95% valid draws) can
    authorize primary decisions. The 18-cell secondary matrix is exploratory.
    Non-default draws/seeds or small fixtures are explicitly marked non-production.
    Endpoint intervals use their own valid draws on the same original common
    pair set; the gap-change interval uses the intersection of endpoint-valid
    draws. Undefined positive-weight pairs invalidate a draw, rather than being
    dropped and renormalized after resampling.
    """
    for value, name in (
        (bootstrap_draws, "bootstrap_draws"),
        (bootstrap_chunk_size, "bootstrap_chunk_size"),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    data = validate_rows(rows, strict_contract=strict_contract, model_keys=model_keys)
    weights = make_bootstrap_weights(
        len(data.item_ids),
        {model: len(value.pairs) for model, value in data.models.items()},
        draws=bootstrap_draws,
        seed=bootstrap_seed,
    )
    primary_models = {}
    secondary_models = {}
    cache_stats = {}
    for model, model_rows in data.models.items():
        primary_models[model], secondary_models[model], cache_stats[model] = _analyze_model(
            model_rows, weights.item_weights, weights.pair_weights[model], bootstrap_chunk_size
        )
    return {
        "schema": "diagnostic.independent_prompt_validation.analysis.v1",
        "production_analysis": (
            strict_contract
            and bootstrap_draws == BOOTSTRAP_DRAWS
            and bootstrap_seed == BOOTSTRAP_SEED
        ),
        "validation": {
            "strict_contract": strict_contract,
            "rows": data.row_count,
            "models": list(data.models),
            "items": len(data.item_ids),
            "item_ids_in_index_order": list(data.item_ids),
            "pair_counts": {model: len(value.pairs) for model, value in data.models.items()},
            "all_18_cells_complete": True,
            "scores_exactly_invariant": True,
            "shared_item_identities_verified": True,
            "first_legal_flags_invariant": True,
        },
        "bootstrap": {
            "draws": bootstrap_draws,
            "seed": bootstrap_seed,
            "required_production_draws": BOOTSTRAP_DRAWS,
            "scheme": "shared-item and independent within-model pair multinomial weights",
            "random_streams": (
                "NumPy SeedSequence children: shared items, then lexically sorted models"
            ),
            "pair_order": {model: list(value.pairs) for model, value in data.models.items()},
            "item_weight_sha256": hashlib.sha256(weights.item_weights.tobytes()).hexdigest(),
            "pair_weight_sha256": {
                model: hashlib.sha256(value.tobytes()).hexdigest()
                for model, value in weights.pair_weights.items()
            },
            "numpy_version": np.__version__,
            "undefined_draw_policy": (
                "Invalidate if any included positive-weight pair is undefined, "
                "or all included pair weights are zero; never impute chance"
            ),
            "cache": cache_stats,
        },
        "primary": {
            "parser": "strict",
            "native_budget": 8,
            "stopped_budget": 1,
            "gap_definition": "AUC(state)-AUC(loss)",
            "change_definition": "stopped_gap-native_gap",
            "fixed_score_direction": "larger predicts risk switch; no sign flips",
            "family_comparisons": COMPARISONS,
            "interval_quantiles": [ALPHA / (2 * COMPARISONS), 1 - ALPHA / (2 * COMPARISONS)],
            "interval_method": "Bonferroni percentile; linear quantile interpolation",
            "min_estimable_pairs": MIN_PAIRS,
            "min_valid_draw_fraction": MIN_VALID_FRACTION,
            "group_coverage_rule": "All three estimands must meet the valid-draw threshold",
            "models": primary_models,
        },
        "secondary": {
            "exploratory": True,
            "interval_quantiles": [0.025, 0.975],
            "interval_method": "Pointwise percentile crossed bootstrap; exploratory",
            "models": secondary_models,
        },
    }
