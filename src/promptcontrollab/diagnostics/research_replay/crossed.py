# Adapted for PromptControlLab: generic identities and typed data-only entrypoints.
# Numerical ordering, seeds, corrections and missingness policies are retained.
"""Frozen source-cross decomposition and independent fresh-item confirmation.

``Panel.scores`` has axes (primary/norm/loss, pair, item); ``Panel.labels`` has
axes (parser-major/budget-minor condition, pair, item). Larger scores always
predict a risk switch. Scores must be finite and labels binary. Input arrays
may have different orders: all resampling is aligned by canonical identities.

The old cohort contains three fixed cases, even when their endpoints overlap.
Only items are resampled for these references. A single new-pair multinomial
draw is reused across models, scores, conditions, and splits, mapping columns
to each model's sorted pair IDs. Independent item streams serve the disjoint
old/new/fresh splits; each stream is shared across every pair and model.

Source calls deliberately never access fresh panels. Confirmation accesses
only fresh panels and frozen predictions, including the source-frozen mean
prediction baseline. Undefined AUCs are never replaced by chance. A draw is
invalid if any included positive-weight new pair, or any old reference, is
undefined. The original eligible pair set never changes within bootstrap draws.

Descriptive omission checks retain every original new-pair identity, marking
excluded or undefined cases explicitly. Separate old-reference case omissions
rebuild the point contrasts using the remaining two references. They never
change primary estimates, bootstrap reference weights, or frozen forecasts.

The module does not write files. The caller must lock source provenance and
prediction bytes before obtaining fresh labels, and validate prompt endpoints
and the experimental sampling frame externally.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any, cast

import numpy as np

from .independent import _divide, _ScoreOrder

COHORTS = ("old", "new")
SPLITS = ("old", "new", "fresh")
PARSERS = ("strict", "leading", "terminal")
BUDGETS = (1, 2, 4, 8, 16, 32)
CONDITIONS = tuple((parser, budget) for parser in PARSERS for budget in BUDGETS)
SCORES = ("primary", "norm", "loss")
STATE_FAMILIES = SCORES[:2]
MAIN_CONDITION = CONDITIONS.index(("strict", 8))
BOOTSTRAP_DRAWS = 20_000
BOOTSTRAP_SEED = 20260908
FAMILY_COMPARISONS = 24
MIN_PAIRS = 12
MIN_VALID_FRACTION = 0.95
MAIN_QUANTILES = (0.05 / (2 * FAMILY_COMPARISONS), 1 - 0.05 / (2 * FAMILY_COMPARISONS))
DESCRIPTIVE_QUANTILES = (0.025, 0.975)
SOURCE_ESTIMANDS = ("P", "Q", "H")
FRESH_METRICS = (
    "mean_T",
    "mean_bias",
    "mae_pred",
    "mae_zero",
    "mae_constant",
    "improvement_over_zero",
    "improvement_over_constant",
)
FRESH_MAIN = ("mean_T", "improvement_over_zero", "improvement_over_constant")
PREDICTION_SCHEMA = "diagnostic.crossed_control.predictions.v1"


@dataclass(frozen=True)
class Panel:
    """Hold aligned prompt-pair and item coordinates for a crossed evaluation panel."""
    pair_ids: tuple[str, ...]
    item_ids: tuple[str, ...]
    scores: np.ndarray[Any, Any]
    labels: np.ndarray[Any, Any]


@dataclass(frozen=True)
class BootstrapWeights:
    """Retain shared bootstrap weights and their reproducibility metadata."""
    item_weights: dict[str, np.ndarray[Any, Any]]
    pair_weights: np.ndarray[Any, Any]


@dataclass(frozen=True)
class _Validated:
    panels: dict[str, dict[str, dict[str, Panel]]]
    item_ids: dict[str, tuple[str, ...]]
    new_pair_count: int

    def production_layout(self) -> bool:
        return (
            len(self.panels) == 2
            and self.new_pair_count == 16
            and all(
                len(ids) == {"old": 200, "new": 400, "fresh": 200}[split]
                for split, ids in self.item_ids.items()
            )
        )

    def metadata(self) -> dict[str, Any]:
        return {
            "models": list(self.panels),
            "item_ids_by_split": {split: list(ids) for split, ids in self.item_ids.items()},
            "pair_ids_by_model": {
                model: {
                    cohort: list(next(iter(splits.values())).pair_ids)
                    for cohort, splits in cohorts.items()
                }
                for model, cohorts in self.panels.items()
            },
            "shared_item_identities_verified": True,
            "split_item_sets_disjoint": True,
            "old_reference_count": 3,
            "new_pair_count": self.new_pair_count,
        }


def _ids(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError(f"{name} must contain nonempty string identities")
    if any(not isinstance(x, str) or not x for x in value) or len(set(value)) != len(value):
        raise ValueError(f"{name} must contain unique nonempty string identities")
    return tuple(value)


def _validate(panels: Mapping[str, Any], splits: tuple[str, ...]) -> _Validated:
    """Validate panel identities, labels, scores and shared endpoint constraints."""
    if (
        not isinstance(panels, Mapping)
        or not panels
        or any(not isinstance(model, str) or not model for model in panels)
    ):
        raise ValueError("Panels require nonempty model identities")
    output: dict[str, dict[str, dict[str, Panel]]] = {}
    shared_items: dict[str, tuple[str, ...]] = {}
    new_count = None
    for model in sorted(panels):
        output[model] = {}
        for cohort in COHORTS:
            output[model][cohort] = {}
            shared_pairs = None
            for split in splits:
                try:
                    panel = panels[model][cohort][split]
                except (KeyError, TypeError) as error:
                    raise ValueError(f"Missing panel: {model}/{cohort}/{split}") from error
                if not isinstance(panel, Panel):
                    raise ValueError(f"Expected Panel at {model}/{cohort}/{split}")
                pairs = _ids(panel.pair_ids, "pair_ids")
                items = _ids(panel.item_ids, "item_ids")
                if cohort == "old" and len(pairs) != 3:
                    raise ValueError("The old cohort requires exactly three fixed references")
                ordered_pairs, ordered_items = tuple(sorted(pairs)), tuple(sorted(items))
                if shared_pairs is not None and ordered_pairs != shared_pairs:
                    raise ValueError(f"Mismatched pair identities for {model}/{cohort}")
                shared_pairs = ordered_pairs
                if split in shared_items and shared_items[split] != ordered_items:
                    raise ValueError(f"Mismatched item identities for split {split}")
                shared_items[split] = ordered_items
                if cohort == "new":
                    if new_count is not None and len(pairs) != new_count:
                        raise ValueError(
                            "Shared pair draws require equal new-pair counts across models"
                        )
                    new_count = len(pairs)
                scores, labels = np.asarray(panel.scores), np.asarray(panel.labels)
                if (
                    scores.shape != (3, len(pairs), len(items))
                    or scores.dtype.kind not in "iuf"
                    or not np.isfinite(scores).all()
                ):
                    raise ValueError(
                        "scores must be finite numeric values with shape (3, pair, item)"
                    )
                if (
                    labels.shape != (18, len(pairs), len(items))
                    or labels.dtype.kind not in "biuf"
                    or not np.isin(labels, (0, 1)).all()
                ):
                    raise ValueError("labels must be binary with shape (18, pair, item)")
                if scores.dtype.kind in "iu" and any(
                    int(original) != int(converted)
                    for original, converted in zip(
                        scores.ravel(), scores.astype(np.float64).ravel(), strict=True
                    )
                ):
                    raise ValueError("Integer scores cannot be represented exactly as float64")
                pair_index = {pair: i for i, pair in enumerate(pairs)}
                item_index = {item: i for i, item in enumerate(items)}
                pi = [pair_index[pair] for pair in ordered_pairs]
                ii = [item_index[item] for item in ordered_items]
                output[model][cohort][split] = Panel(
                    ordered_pairs,
                    ordered_items,
                    scores[:, pi][:, :, ii].astype(np.float64),
                    labels[:, pi][:, :, ii].astype(np.uint8),
                )
    for index, split in enumerate(splits):
        for other in splits[index + 1 :]:
            if set(shared_items[split]) & set(shared_items[other]):
                raise ValueError("Old, new, and fresh item identity sets must be disjoint")
    assert new_count is not None
    return _Validated(output, shared_items, new_count)


def make_bootstrap_weights(
    item_counts: Mapping[str, int], pair_count: int, *, draws: int, seed: int
) -> BootstrapWeights:
    """Stable independent split streams and one shared new-pair stream.

    The four SeedSequence children always mean old items, new items, fresh
    items, and new pairs, even when only a subset of splits is requested.
    """
    if not item_counts or set(item_counts) - set(SPLITS):
        raise ValueError("Bootstrap item counts require known split names")
    for name, value in (("draws", draws), ("pair_count", pair_count), *item_counts.items()):
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    streams = np.random.SeedSequence(seed).spawn(4)

    def sample(count: int, stream: np.random.SeedSequence) -> np.ndarray[Any, Any]:
        dtype = np.uint16 if count <= np.iinfo(np.uint16).max else np.uint32
        return (
            np.random.default_rng(stream)
            .multinomial(count, np.full(count, 1 / count), size=draws)
            .astype(dtype)
        )

    return BootstrapWeights(
        {
            split: sample(item_counts[split], streams[index])
            for index, split in enumerate(SPLITS)
            if split in item_counts
        },
        sample(pair_count, streams[3]),
    )


def _auc_draws(
    orders: tuple[_ScoreOrder, ...],
    labels: np.ndarray[Any, Any],
    weights: np.ndarray[Any, Any],
    chunk_size: int = 512,
) -> np.ndarray[Any, Any]:
    """Tie-aware AUC in sorted score groups, vectorized over item-weight draws."""
    output = np.full((len(weights), len(orders)), np.nan)
    if not np.any(labels == 1) or not np.any(labels == 0):
        return output
    for start in range(0, len(weights), chunk_size):
        stop = min(len(weights), start + chunk_size)
        for score, order in enumerate(orders):
            mass = weights[start:stop, order.order].astype(np.float64, order="C")
            positive = order.grouped(mass * labels[order.order])
            negative = order.grouped(mass * (1 - labels[order.order]))
            numerator = (positive * (np.cumsum(negative, axis=1) - 0.5 * negative)).sum(axis=1)
            output[start:stop, score] = _divide(
                numerator, positive.sum(axis=1) * negative.sum(axis=1)
            )
    return output


def _iter_pair_aucs(
    panel: Panel, weights: np.ndarray[Any, Any]
) -> Iterator[tuple[int, int, np.ndarray[Any, Any]]]:
    for pair in range(len(panel.pair_ids)):
        orders = tuple(_ScoreOrder.build(panel.scores[score, pair]) for score in range(3))
        cache: dict[bytes, np.ndarray[Any, Any]] = {}
        for cell in range(len(CONDITIONS)):
            labels = panel.labels[cell, pair]
            key = labels.tobytes()
            if key not in cache:
                cache[key] = _auc_draws(orders, labels, weights)
            yield pair, cell, cache[key]


class _Means:
    def __init__(self, rows: int, columns: int) -> None:
        self.sums = np.zeros((18, rows, columns))
        self.denominators = np.zeros((18, rows))
        self.invalid = np.zeros((18, rows), dtype=bool)

    def add(self, cell: int, values: np.ndarray[Any, Any], weights: np.ndarray[Any, Any]) -> None:
        self.sums[cell] += np.nan_to_num(values) * weights[:, None]
        self.denominators[cell] += weights
        self.invalid[cell] |= (weights > 0) & ~np.isfinite(values).all(axis=1)

    def values(self) -> np.ndarray[Any, Any]:
        means = _divide(self.sums, self.denominators[:, :, None])
        means[self.invalid] = np.nan
        return means


def _defined(panel: Panel) -> np.ndarray[Any, Any]:
    positives = panel.labels.sum(axis=2)
    return cast(np.ndarray[Any, Any], (positives > 0) & (positives < len(panel.item_ids)))


def _panel_statistics(
    panel: Panel,
    item_weights: np.ndarray[Any, Any],
    pair_weights: np.ndarray[Any, Any] | None,
    included: np.ndarray[Any, Any],
) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    points = np.full((18, len(panel.pair_ids), 3), np.nan)
    means = _Means(len(item_weights), 3)
    fixed_weights = np.ones(len(item_weights))
    for pair, cell, aucs in _iter_pair_aucs(panel, item_weights):
        points[cell, pair] = aucs[0]
        if included[cell, pair]:
            means.add(cell, aucs, fixed_weights if pair_weights is None else pair_weights[:, pair])
    return points, means.values()


def _with_point(weights: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    return np.concatenate((np.ones((1, weights.shape[1]), dtype=weights.dtype), weights), axis=0)


def _gap(auc: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    return cast(np.ndarray[Any, Any], auc[..., :2] - auc[..., 2:3])


def _number(value: Any) -> float | None:
    return float(value) if value is not None and np.isfinite(value) else None


def _mean(values: np.ndarray[Any, Any]) -> float | None:
    return _number(np.mean(values)) if len(values) else None


def _side(interval: list[float] | None) -> str:
    if interval is None:
        return "undefined"
    if interval[0] > 0:
        return "positive"
    return "negative" if interval[1] < 0 else "includes_zero"


def _direction(value: float | None) -> str:
    if value is None:
        return "undefined"
    return "positive" if value > 0 else "negative" if value < 0 else "zero"


def _summary(values: np.ndarray[Any, Any], pairs: int, *, descriptive: bool) -> dict[str, Any]:
    draws = values[1:]
    finite = draws[np.isfinite(draws)]
    quantiles = DESCRIPTIVE_QUANTILES if descriptive else MAIN_QUANTILES
    interval = np.quantile(finite, quantiles, method="linear").tolist() if len(finite) else None
    return {
        "point": _number(values[0]),
        "point_direction": _direction(_number(values[0])),
        "interval": interval,
        "interval_side": _side(interval),
        "estimable_pairs": pairs,
        "valid_draws": len(finite),
        "undefined_draws": len(draws) - len(finite),
        "valid_fraction": len(finite) / len(draws),
        "descriptive": descriptive,
    }


def _eligibility(
    summaries: Mapping[str, Any],
    pair_count: int,
    old_defined: bool,
    production: bool,
    *,
    descriptive: bool,
    source_pair_count: int | None = None,
) -> dict[str, Any]:
    reasons = []
    if pair_count < MIN_PAIRS:
        reasons.append("fewer_than_12_common_pairs")
    if source_pair_count is not None and source_pair_count < MIN_PAIRS:
        reasons.append("fewer_than_12_source_common_pairs")
    if not old_defined:
        reasons.append("old_references_not_all_defined")
    if any(value["valid_fraction"] < MIN_VALID_FRACTION for value in summaries.values()):
        reasons.append("valid_draw_fraction_below_0.95")
    coverage_eligible = not reasons
    if not production:
        reasons.append("nonproduction_layout_draws_or_seed")
    if descriptive:
        reasons.append("descriptive_condition")
    return {
        "coverage_eligible": coverage_eligible,
        "inferential": coverage_eligible and production and not descriptive,
        "ineligibility_reasons": reasons,
    }


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


def _source_digest(data: _Validated) -> str:
    digest = hashlib.sha256(_digest(data.metadata()).encode("ascii"))
    for cohorts in data.panels.values():
        for splits in cohorts.values():
            for panel in splits.values():
                digest.update(panel.scores.astype("<f8").tobytes())
                digest.update(panel.labels.tobytes())
    return digest.hexdigest()


def _bootstrap_metadata(weights: BootstrapWeights, draws: int, seed: int) -> dict[str, Any]:
    return {
        "draws": draws,
        "seed": seed,
        "required_production_draws": BOOTSTRAP_DRAWS,
        "scheme": "Shared new-pair weights; joint item weights within each independent split",
        "old_references": "Three fixed equal-weight cases; no old-pair bootstrap",
        "pair_mapping": "Same weight columns mapped to each model's sorted new-pair IDs",
        "random_streams": "SeedSequence children: old items, new items, fresh items, new pairs",
        "item_weight_sha256": {
            split: hashlib.sha256(value.tobytes()).hexdigest()
            for split, value in weights.item_weights.items()
        },
        "pair_weight_sha256": hashlib.sha256(weights.pair_weights.tobytes()).hexdigest(),
        "numpy_version": np.__version__,
        "undefined_draw_policy": (
            "Invalidate any undefined fixed reference or included positive-weight new pair; "
            "invalidate zero included pair mass; never impute AUC or change the original mask"
        ),
    }


def _primary_metadata() -> dict[str, Any]:
    return {
        "parser": "strict",
        "budget": 8,
        "family_comparisons": FAMILY_COMPARISONS,
        "family_definition": "2 models x 2 state scores x (P,Q,H,mean_T,MAE0-MAEpred,MAEc-MAEpred)",
        "interval_quantiles": list(MAIN_QUANTILES),
        "interval_method": "Two-sided Bonferroni percentile; linear quantile interpolation",
        "min_estimable_pairs": MIN_PAIRS,
        "min_valid_draw_fraction": MIN_VALID_FRACTION,
        "gap_definition": "AUC(state)-AUC(loss)",
        "fixed_score_direction": "Larger predicts risk switch; no sign flips",
    }


def _effects(
    oo: np.ndarray[Any, Any],
    on: np.ndarray[Any, Any],
    no: np.ndarray[Any, Any],
    nn: np.ndarray[Any, Any],
) -> np.ndarray[Any, Any]:
    return np.stack(
        (0.5 * ((no - oo) + (nn - on)), 0.5 * ((on - oo) + (nn - no)), nn - no - on + oo), axis=-1
    )


def _sensitivity_status(points: Mapping[str, Any], reason: str) -> dict[str, Any]:
    estimable = all(value is not None for value in points.values())
    return {
        "descriptive": True,
        "inferential": False,
        "estimable": estimable,
        "not_estimable_reason": None if estimable else reason,
    }


def _source_cell(
    cell: int,
    panels: dict[str, dict[str, Panel]],
    points: dict[tuple[str, str], np.ndarray[Any, Any]],
    means: dict[tuple[str, str], np.ndarray[Any, Any]],
    common: np.ndarray[Any, Any],
    production: bool,
    *,
    descriptive: bool,
) -> dict[str, Any]:
    """Compute source-panel contrasts using shared resampling weights."""
    pairs = panels["new"]["old"].pair_ids
    selected = np.flatnonzero(common[cell])
    old_pairs = panels["old"]["old"].pair_ids
    keys = (("old", "old"), ("old", "new"), ("new", "old"), ("new", "new"))
    gaps = [_gap(means[key][cell]) for key in keys]
    effects = _effects(*gaps)
    old_defined = all(np.isfinite(points["old", split][cell]).all() for split in ("old", "new"))
    families = {}
    for family_index, family in enumerate(STATE_FAMILIES):
        summaries = {
            name: _summary(effects[:, family_index, i], len(selected), descriptive=descriptive)
            for i, name in enumerate(SOURCE_ESTIMANDS)
        }
        eligible = _eligibility(
            summaries, len(selected), old_defined, production, descriptive=descriptive
        )
        residual = (
            effects[:, family_index, 0]
            + effects[:, family_index, 1]
            - (gaps[3][:, family_index] - gaps[0][:, family_index])
        )
        finite = residual[1:][np.isfinite(residual[1:])]
        if np.any(np.abs(residual[np.isfinite(residual)]) > 1e-12):
            raise ArithmeticError("P + Q must equal the diagonal contrast")
        lopo = []
        for pair in range(len(pairs)):
            is_common = bool(common[cell, pair])
            remaining = selected[selected != pair]
            omitted_gaps = [gaps[i][0, family_index] for i in range(2)]
            omitted_gaps.extend(
                np.mean(_gap(points["new", split][cell, remaining])[:, family_index])
                if len(remaining)
                else np.nan
                for split in ("old", "new")
            )
            omitted = _effects(*map(np.asarray, omitted_gaps)) if is_common else np.full(3, np.nan)
            omitted_points = {name: _number(omitted[i]) for i, name in enumerate(SOURCE_ESTIMANDS)}
            reason = (
                "excluded_from_common"
                if not is_common
                else "no_remaining_common_pairs"
                if not len(remaining)
                else "old_references_not_all_defined"
            )
            lopo.append(
                {
                    "omitted_pair": pairs[pair],
                    "remaining_pairs": len(remaining),
                    "excluded_from_common": not is_common,
                    "points": omitted_points,
                    **_sensitivity_status(omitted_points, reason),
                    "sign_changes": [
                        name
                        for i, name in enumerate(SOURCE_ESTIMANDS)
                        if _direction(_number(omitted[i])) != summaries[name]["point_direction"]
                    ]
                    if is_common and len(remaining) and old_defined
                    else [],
                }
            )
        old_sensitivity = []
        for reference in range(len(old_pairs)):
            remaining = np.delete(np.arange(len(old_pairs)), reference)
            omitted_gaps = [
                np.mean(_gap(points["old", split][cell, remaining])[:, family_index])
                for split in ("old", "new")
            ]
            omitted_gaps.extend(gaps[i][0, family_index] for i in (2, 3))
            omitted = _effects(*map(np.asarray, omitted_gaps))
            omitted_points = {name: _number(omitted[i]) for i, name in enumerate(SOURCE_ESTIMANDS)}
            reason = (
                "no_common_pairs"
                if not len(selected)
                else "remaining_old_references_not_all_defined"
            )
            old_sensitivity.append(
                {
                    "omitted_old_reference": old_pairs[reference],
                    "remaining_old_reference_ids": [old_pairs[i] for i in remaining],
                    "remaining_old_reference_count": len(remaining),
                    "source_common_pair_count": len(selected),
                    "points": omitted_points,
                    **_sensitivity_status(omitted_points, reason),
                    "cohort_gap_means": {
                        f"{cohort}_{split}": _number(omitted_gaps[i])
                        for i, (cohort, split) in enumerate(keys)
                    },
                }
            )
        families[family] = {
            "estimands": summaries,
            **eligible,
            "supported_effects": {
                name: bool(
                    eligible["inferential"] and value["interval_side"] in ("positive", "negative")
                )
                for name, value in summaries.items()
            },
            "cohort_gap_means": {
                f"{cohort}_{split}": _number(gaps[i][0, family_index])
                for i, (cohort, split) in enumerate(keys)
            },
            "diagonal_identity": {
                "identity": "P+Q = G_new,new-G_old,old",
                "point_residual": _number(residual[0]),
                "bootstrap_max_abs_residual": float(np.max(np.abs(finite)))
                if len(finite)
                else None,
            },
            "leave_one_pair_out": lopo,
            "old_reference_leave_one_case_out": old_sensitivity,
        }
    return {
        "parser": CONDITIONS[cell][0],
        "budget": CONDITIONS[cell][1],
        "descriptive": descriptive,
        "new_pair_ids": list(pairs),
        "old_reference_pair_ids": list(old_pairs),
        "source_common_pairs": [pairs[pair] for pair in selected],
        "source_common_pair_count": len(selected),
        "old_references_defined": bool(old_defined),
        "families": families,
        "cohorts": {
            f"{cohort}_{split}": {
                "equal_pair_auc": {
                    score: _summary(
                        means[cohort, split][cell, :, i],
                        3 if cohort == "old" else len(selected),
                        descriptive=True,
                    )
                    for i, score in enumerate(SCORES)
                },
                "pairs": [
                    {
                        "pair": pair,
                        "positive_count": int(panels[cohort][split].labels[cell, i].sum()),
                        "item_count": len(panels[cohort][split].item_ids),
                        "auc": {
                            score: _number(points[cohort, split][cell, i, s])
                            for s, score in enumerate(SCORES)
                        },
                    }
                    for i, pair in enumerate(panels[cohort][split].pair_ids)
                ],
            }
            for cohort, split in keys
        },
    }


def analyze_cross(
    panels: Mapping[str, Any], *, draws: int = BOOTSTRAP_DRAWS, seed: int = BOOTSTRAP_SEED
) -> dict[str, Any]:
    """Analyze source old/new item crosses only; fresh entries are never read."""
    data = _validate(panels, ("old", "new"))
    weights = make_bootstrap_weights(
        {split: len(ids) for split, ids in data.item_ids.items()},
        data.new_pair_count,
        draws=draws,
        seed=seed,
    )
    production = data.production_layout() and draws == BOOTSTRAP_DRAWS and seed == BOOTSTRAP_SEED
    item_weights = {split: _with_point(value) for split, value in weights.item_weights.items()}
    pair_weights = _with_point(weights.pair_weights)
    main, matrix = {}, {}
    for model, model_panels in data.panels.items():
        common = _defined(model_panels["new"]["old"]) & _defined(model_panels["new"]["new"])
        points, means = {}, {}
        for cohort in COHORTS:
            for split in ("old", "new"):
                panel = model_panels[cohort][split]
                points[cohort, split], means[cohort, split] = _panel_statistics(
                    panel,
                    item_weights[split],
                    pair_weights if cohort == "new" else None,
                    common if cohort == "new" else np.ones((18, 3), dtype=bool),
                )
        main[model] = _source_cell(
            MAIN_CONDITION, model_panels, points, means, common, production, descriptive=False
        )
        matrix[model] = [
            _source_cell(cell, model_panels, points, means, common, production, descriptive=True)
            for cell in range(18)
        ]
    return {
        "schema": "diagnostic.crossed_control.source_analysis.v1",
        "production_analysis": production,
        "validation": data.metadata(),
        "source_panel_sha256": _source_digest(data),
        "bootstrap": _bootstrap_metadata(weights, draws, seed),
        "primary": {**_primary_metadata(), "models": main},
        "secondary": {
            "descriptive": True,
            "interval_quantiles": list(DESCRIPTIVE_QUANTILES),
            "selection_policy": "No success selection from parser/budget matrix",
            "models": matrix,
        },
    }


def _prediction_cell(
    cell: int,
    model_panels: dict[str, dict[str, Panel]],
    points: dict[tuple[str, str], np.ndarray[Any, Any]],
    common: np.ndarray[Any, Any],
) -> dict[str, Any]:
    pair_ids = model_panels["new"]["old"].pair_ids
    old_pairs = model_panels["old"]["old"].pair_ids
    old_gaps = [_gap(points["old", split][cell]).mean(axis=0) for split in ("old", "new")]
    old_defined = bool(np.isfinite(old_gaps).all())
    predictions = 0.5 * sum(
        _gap(points["new", split][cell]) - old_gaps[i] for i, split in enumerate(("old", "new"))
    )
    families = {}
    for i, family in enumerate(STATE_FAMILIES):
        valid = common[cell] & np.isfinite(predictions[:, i])
        families[family] = {
            "uniform_baseline": _mean(predictions[valid, i]),
            "per_pair_predictions": [
                {
                    "pair": pair,
                    "prediction": _number(predictions[j, i]),
                    "source_valid": bool(valid[j]),
                }
                for j, pair in enumerate(pair_ids)
            ],
            "old_reference_gaps": {
                split: _number(old_gaps[j][i]) for j, split in enumerate(("old", "new"))
            },
        }
    return {
        "parser": CONDITIONS[cell][0],
        "budget": CONDITIONS[cell][1],
        "new_pair_ids": list(pair_ids),
        "old_reference_pair_ids": list(old_pairs),
        "old_references_defined": old_defined,
        "source_common_pairs": [pair for j, pair in enumerate(pair_ids) if common[cell, j]],
        "source_common_pair_count": int(common[cell].sum()),
        "families": families,
    }


def make_predictions(panels: Mapping[str, Any]) -> dict[str, Any]:
    """Freeze all new-pair predictions and source-only constant baselines.

    The full 18-cell artifact supports descriptive checks; only strict/8 is
    confirmatory. A canonical content digest detects accidental modification.
    It supplements, rather than replaces, the caller's immutable lock/provenance.
    """
    data = _validate(panels, ("old", "new"))
    models = {}
    for model, model_panels in data.panels.items():
        common = _defined(model_panels["new"]["old"]) & _defined(model_panels["new"]["new"])
        points = {}
        for cohort in COHORTS:
            for split in ("old", "new"):
                panel = model_panels[cohort][split]
                points[cohort, split], _ = _panel_statistics(
                    panel,
                    np.ones((1, len(panel.item_ids)), dtype=np.uint16),
                    None,
                    np.ones((18, len(panel.pair_ids)), dtype=bool),
                )
        matrix = [_prediction_cell(cell, model_panels, points, common) for cell in range(18)]
        models[model] = {"main": matrix[MAIN_CONDITION], "matrix": matrix}
    result = {
        "schema": PREDICTION_SCHEMA,
        "production_source_layout": data.production_layout(),
        "validation": data.metadata(),
        "source_panel_sha256": _source_digest(data),
        "main_condition": {"parser": "strict", "budget": 8},
        "scores": list(SCORES),
        "conditions": [list(value) for value in CONDITIONS],
        "prediction_definition": "That_j = mean_d(G_j,d-G_oldcohort,d), d in old/new",
        "uniform_baseline_definition": "Source-valid That_j mean, frozen before fresh labels",
        "models": models,
    }
    result["content_sha256"] = _digest(result)
    return result


def _validate_predictions(predictions: Mapping[str, Any], data: _Validated) -> None:
    """Check locked predictions against their declared coordinates and source identities."""
    try:
        if predictions["schema"] != PREDICTION_SCHEMA:
            raise ValueError("Unknown prediction schema")
        payload = {key: value for key, value in predictions.items() if key != "content_sha256"}
        if _digest(payload) != predictions["content_sha256"]:
            raise ValueError("Frozen prediction integrity digest mismatch")
        if (
            predictions["scores"] != list(SCORES)
            or predictions["conditions"] != [list(value) for value in CONDITIONS]
            or predictions["main_condition"] != {"parser": "strict", "budget": 8}
        ):
            raise ValueError("Frozen prediction score/condition specification mismatch")
        if set(predictions["models"]) != set(data.panels):
            raise ValueError("Frozen prediction model identities mismatch")
        source_items = predictions["validation"]["item_ids_by_split"]
        if set(source_items) != {"old", "new"}:
            raise ValueError("Frozen predictions require source item identities")
        source_ids = {
            split: _ids(source_items[split], "source item identities") for split in ("old", "new")
        }
        if set(source_ids["old"]) & set(source_ids["new"]):
            raise ValueError("Old and new source item identity sets must be disjoint")
        source_production = (
            len(data.panels) == 2
            and data.new_pair_count == 16
            and len(source_ids["old"]) == 200
            and len(source_ids["new"]) == 400
        )
        declared_production = predictions["production_source_layout"]
        if type(declared_production) is not bool or declared_production != source_production:
            raise ValueError("Frozen source production layout is inconsistent with coordinates")
        for split in ("old", "new"):
            if set(source_ids[split]) & set(data.item_ids["fresh"]):
                raise ValueError("Fresh and source item identity sets must be disjoint")
        for model, model_panels in data.panels.items():
            locked = predictions["models"][model]
            if len(locked["matrix"]) != 18 or locked["main"] != locked["matrix"][MAIN_CONDITION]:
                raise ValueError("Frozen prediction main/matrix mismatch")
            pair_ids = model_panels["new"]["fresh"].pair_ids
            for cell, record in enumerate(locked["matrix"]):
                if (record["parser"], record["budget"]) != CONDITIONS[cell]:
                    raise ValueError("Frozen prediction condition order mismatch")
                if record["new_pair_ids"] != list(pair_ids) or record[
                    "old_reference_pair_ids"
                ] != list(model_panels["old"]["fresh"].pair_ids):
                    raise ValueError("Frozen prediction pair identities mismatch")
                common = record["source_common_pairs"]
                if (
                    len(set(common)) != len(common)
                    or set(common) - set(pair_ids)
                    or record["source_common_pair_count"] != len(common)
                ):
                    raise ValueError("Frozen prediction common-pair set mismatch")
                for family in STATE_FAMILIES:
                    family_record = record["families"][family]
                    pairs = family_record["per_pair_predictions"]
                    if [value["pair"] for value in pairs] != list(pair_ids):
                        raise ValueError("Frozen prediction per-pair identities mismatch")
                    valid_values = []
                    for value in pairs:
                        estimate = value["prediction"]
                        if estimate is not None and (
                            isinstance(estimate, bool) or not np.isfinite(estimate)
                        ):
                            raise ValueError("Frozen predictions must be finite or null")
                        expected_valid = (
                            value["pair"] in common and record["old_references_defined"]
                        )
                        if (
                            value["source_valid"] != expected_valid
                            or (estimate is not None) != expected_valid
                        ):
                            raise ValueError("Frozen prediction validity mask mismatch")
                        if expected_valid:
                            valid_values.append(cast(float, estimate))
                    constant = family_record["uniform_baseline"]
                    expected = float(np.mean(valid_values)) if valid_values else None
                    if constant != expected:
                        raise ValueError(
                            "Frozen uniform baseline is not the source-valid prediction mean"
                        )
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError("Malformed frozen prediction artifact") from error


def _fresh_values(
    observed: np.ndarray[Any, Any], prediction: np.ndarray[Any, Any], constant: np.ndarray[Any, Any]
) -> np.ndarray[Any, Any]:
    error = prediction - observed
    pred_error, zero_error, constant_error = (
        np.abs(error),
        np.abs(observed),
        np.abs(constant - observed),
    )
    return np.stack(
        (
            observed,
            error,
            pred_error,
            zero_error,
            constant_error,
            zero_error - pred_error,
            constant_error - pred_error,
        ),
        axis=-1,
    )


def _fresh_model(
    panels: dict[str, dict[str, Panel]],
    locked: Mapping[str, Any],
    item_weights: np.ndarray[Any, Any],
    pair_weights: np.ndarray[Any, Any],
    production: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Evaluate frozen transfer predictions on the held-out model panel."""
    old, new = panels["old"]["fresh"], panels["new"]["fresh"]
    old_points, old_means = _panel_statistics(old, item_weights, None, np.ones((18, 3), dtype=bool))
    old_gaps = _gap(old_means)
    points = np.full((18, len(new.pair_ids), 3), np.nan)
    per_pair = np.full((18, len(new.pair_ids), 2, len(FRESH_METRICS)), np.nan)
    means = _Means(len(item_weights), 2 * len(FRESH_METRICS))
    fresh_defined = _defined(new)
    included = np.zeros((18, len(new.pair_ids)), dtype=bool)
    predictions = np.full((18, len(new.pair_ids), 2), np.nan)
    constants = np.full((18, 2), np.nan)
    for cell, source in enumerate(locked["matrix"]):
        for family_index, family in enumerate(STATE_FAMILIES):
            values = source["families"][family]
            constants[cell, family_index] = (
                values["uniform_baseline"] if values["uniform_baseline"] is not None else np.nan
            )
            predictions[cell, :, family_index] = [
                value["prediction"] if value["prediction"] is not None else np.nan
                for value in values["per_pair_predictions"]
            ]
        included[cell] = fresh_defined[cell] & np.isfinite(predictions[cell]).all(axis=1)
    for pair, cell, aucs in _iter_pair_aucs(new, item_weights):
        points[cell, pair] = aucs[0]
        observed = _gap(aucs) - old_gaps[cell]
        values = _fresh_values(observed, predictions[cell, pair], constants[cell])
        per_pair[cell, pair] = values[0]
        if included[cell, pair]:
            means.add(cell, values.reshape(len(item_weights), -1), pair_weights[:, pair])
    values = means.values().reshape(18, len(item_weights), 2, len(FRESH_METRICS))

    def summarize(cell: int, *, descriptive: bool) -> dict[str, Any]:
        """Summarize transfer error and baseline contrasts with shared bootstrap weights."""
        source = locked["matrix"][cell]
        selected = np.flatnonzero(included[cell])
        old_defined = bool(np.isfinite(old_points[cell]).all())
        families = {}
        for family_index, family in enumerate(STATE_FAMILIES):
            summaries = {
                name: _summary(
                    values[cell, :, family_index, i],
                    len(selected),
                    descriptive=descriptive or name not in FRESH_MAIN,
                )
                for i, name in enumerate(FRESH_METRICS)
            }
            eligible = _eligibility(
                {name: summaries[name] for name in FRESH_MAIN},
                len(selected),
                old_defined and source["old_references_defined"],
                production,
                descriptive=descriptive,
                source_pair_count=source["source_common_pair_count"],
            )
            lopo = []
            for pair in range(len(new.pair_ids)):
                is_common = bool(included[cell, pair])
                remaining = selected[selected != pair]
                omitted_points = {
                    name: _mean(per_pair[cell, remaining, family_index, i]) if is_common else None
                    for i, name in enumerate(FRESH_METRICS)
                }
                reason = (
                    "excluded_from_common"
                    if not is_common
                    else "no_remaining_common_pairs"
                    if not len(remaining)
                    else "old_references_not_all_defined"
                )
                lopo.append(
                    {
                        "omitted_pair": new.pair_ids[pair],
                        "remaining_pairs": len(remaining),
                        "excluded_from_common": not is_common,
                        "points": omitted_points,
                        **_sensitivity_status(omitted_points, reason),
                        "predictions_and_uniform_baseline_fixed": True,
                    }
                )
            old_sensitivity = []
            for reference in range(len(old.pair_ids)):
                remaining = np.delete(np.arange(len(old.pair_ids)), reference)
                reference_gap = np.mean(_gap(old_points[cell, remaining]), axis=0)
                observed = _gap(points[cell]) - reference_gap
                omitted_metrics = _fresh_values(observed, predictions[cell], constants[cell])
                omitted_points = {
                    name: _mean(omitted_metrics[selected, family_index, i])
                    for i, name in enumerate(FRESH_METRICS)
                }
                reason = (
                    "no_common_pairs"
                    if not len(selected)
                    else "remaining_old_references_not_all_defined"
                )
                old_sensitivity.append(
                    {
                        "omitted_old_reference": old.pair_ids[reference],
                        "remaining_old_reference_ids": [old.pair_ids[i] for i in remaining],
                        "remaining_old_reference_count": len(remaining),
                        "confirmation_pair_count": len(selected),
                        "points": omitted_points,
                        **_sensitivity_status(omitted_points, reason),
                        "old_reference_gap": _number(reference_gap[family_index]),
                        "uniform_baseline": _number(constants[cell, family_index]),
                        "predictions_and_uniform_baseline_fixed": True,
                    }
                )
            families[family] = {
                "estimands": summaries,
                **eligible,
                "uniform_baseline": _number(constants[cell, family_index]),
                "source_mean_direction": _direction(_number(constants[cell, family_index])),
                "mean_difference_supported": bool(
                    eligible["inferential"]
                    and summaries["mean_T"]["interval_side"] in ("positive", "negative")
                ),
                "mean_transfer_supported": bool(
                    eligible["inferential"]
                    and summaries["mean_T"]["interval_side"] in ("positive", "negative")
                    and summaries["mean_T"]["interval_side"]
                    == _direction(_number(constants[cell, family_index]))
                ),
                "zero_baseline_improvement_supported": bool(
                    eligible["inferential"]
                    and summaries["improvement_over_zero"]["interval_side"] == "positive"
                ),
                "constant_baseline_improvement_supported": bool(
                    eligible["inferential"]
                    and summaries["improvement_over_constant"]["interval_side"] == "positive"
                ),
                "per_pair_errors": [
                    {
                        "pair": pair,
                        "included_in_confirmation": bool(included[cell, i]),
                        "source_valid": bool(np.isfinite(predictions[cell, i, family_index])),
                        "fresh_auc_defined": bool(fresh_defined[cell, i]),
                        "prediction": _number(predictions[cell, i, family_index]),
                        "observed_T": _number(per_pair[cell, i, family_index, 0]),
                        "prediction_error": _number(per_pair[cell, i, family_index, 1]),
                        "absolute_prediction_error": _number(per_pair[cell, i, family_index, 2]),
                        "absolute_zero_baseline_error": _number(per_pair[cell, i, family_index, 3]),
                        "absolute_constant_baseline_error": _number(
                            per_pair[cell, i, family_index, 4]
                        ),
                    }
                    for i, pair in enumerate(new.pair_ids)
                ],
                "leave_one_pair_out": lopo,
                "old_reference_leave_one_case_out": old_sensitivity,
            }
        return {
            "parser": CONDITIONS[cell][0],
            "budget": CONDITIONS[cell][1],
            "descriptive": descriptive,
            "new_pair_ids": list(new.pair_ids),
            "old_reference_pair_ids": list(old.pair_ids),
            "source_common_pairs": list(source["source_common_pairs"]),
            "source_common_pair_count": source["source_common_pair_count"],
            "confirmation_pairs": [new.pair_ids[pair] for pair in selected],
            "confirmation_pair_count": len(selected),
            "old_references_defined": old_defined,
            "source_old_references_defined": source["old_references_defined"],
            "families": families,
            "fresh_pair_auc": {
                cohort: [
                    {
                        "pair": pair,
                        "positive_count": int(panel.labels[cell, i].sum()),
                        "item_count": len(panel.item_ids),
                        "auc": {score: _number(auc[cell, i, j]) for j, score in enumerate(SCORES)},
                    }
                    for i, pair in enumerate(panel.pair_ids)
                ]
                for cohort, panel, auc in (("old", old, old_points), ("new", new, points))
            },
        }

    return summarize(MAIN_CONDITION, descriptive=False), [
        summarize(cell, descriptive=True) for cell in range(18)
    ]


def analyze_confirm(
    panels: Mapping[str, Any],
    predictions: Mapping[str, Any],
    *,
    draws: int = BOOTSTRAP_DRAWS,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Fresh-only inference with locked predictions and uniform baseline.

    Confirmation uses source-valid intersect fresh-defined pairs. It recomputes
    fresh AUC gaps under shared pair/item draws, retaining source predictions
    exactly, including during leave-one-pair-out checks. The three confirmatory
    endpoints have separate decisions: mean sign alone is no predictive success.
    """
    data = _validate(panels, ("fresh",))
    _validate_predictions(predictions, data)
    weights = make_bootstrap_weights(
        {"fresh": len(data.item_ids["fresh"])}, data.new_pair_count, draws=draws, seed=seed
    )
    production = (
        data.production_layout()
        and predictions["production_source_layout"]
        and draws == BOOTSTRAP_DRAWS
        and seed == BOOTSTRAP_SEED
    )
    main, matrix = {}, {}
    for model, model_panels in data.panels.items():
        main[model], matrix[model] = _fresh_model(
            model_panels,
            predictions["models"][model],
            _with_point(weights.item_weights["fresh"]),
            _with_point(weights.pair_weights),
            production,
        )
    return {
        "schema": "diagnostic.crossed_control.fresh_confirmation.v1",
        "production_analysis": bool(production),
        "validation": data.metadata(),
        "frozen_prediction_sha256": predictions["content_sha256"],
        "source_panel_sha256": predictions["source_panel_sha256"],
        "bootstrap": _bootstrap_metadata(weights, draws, seed),
        "predictions_and_uniform_baseline_fixed": True,
        "primary": {
            **_primary_metadata(),
            "observed_definition": "T_j=G_j,fresh-G_oldcohort,fresh",
            "bias_definition": "prediction minus observed T",
            "selection_policy": "Separate mean-transfer and two baseline-improvement decisions",
            "models": main,
        },
        "secondary": {
            "descriptive": True,
            "interval_quantiles": list(DESCRIPTIVE_QUANTILES),
            "selection_policy": "No success selection from parser/budget matrix",
            "models": matrix,
        },
    }
