# Adapted for PromptControlLab: generic identities and typed data-only entrypoints.
# Numerical ordering, seeds, corrections and missingness policies are retained.
"""Original saved-score interaction statistics, without model/runtime dependencies."""

from __future__ import annotations

from typing import Any

import numpy as np


def finite(value: Any) -> np.ndarray[Any, Any]:
    """Convert numeric input to a finite float64 array or reject it."""
    a = np.asarray(value, dtype=np.float64)
    if not np.isfinite(a).all():
        raise ValueError("Nonfinite scientific input")
    return a


def weighted_auc(labels: Any, scores: Any, weights: Any = None) -> float | None:
    """Compute weighted AUC with half credit for ties and undefined single-class outcomes."""
    labels, scores = np.asarray(labels), finite(scores)
    if labels.shape != scores.shape or labels.ndim != 1 or not np.isin(labels, [0, 1]).all():
        raise ValueError("AUC coordinates or labels invalid")
    w = np.ones(len(labels)) if weights is None else finite(weights)
    if w.shape != labels.shape or (w < 0).any():
        raise ValueError("AUC weights invalid")
    positive, negative = w[labels == 1].sum(), w[labels == 0].sum()
    if positive == 0 or negative == 0:
        return None
    order = np.argsort(scores, kind="stable")
    s, y, w = scores[order], labels[order], w[order]
    total = below = 0.0
    first = 0
    while first < len(y):
        last = first + 1
        while last < len(y) and s[last] == s[first]:
            last += 1
        pos = w[first:last][y[first:last] == 1].sum()
        neg = w[first:last][y[first:last] == 0].sum()
        total += pos * (below + 0.5 * neg)
        below += neg
        first = last
    return float(total / (positive * negative))


def _auc_many(labels: Any, scores: Any, weights: Any) -> np.ndarray[Any, Any]:
    """Weighted exact tied AUC, one shared item bootstrap per row."""
    labels, scores = np.asarray(labels), np.asarray(scores)
    order = np.argsort(scores, kind="stable")
    y, s, w = labels[order], scores[order], weights[:, order]
    starts = np.r_[0, np.flatnonzero(np.diff(s)) + 1]
    positives = np.add.reduceat(w * y, starts, axis=1)
    negatives = np.add.reduceat(w * (1 - y), starts, axis=1)
    below = np.cumsum(negatives, axis=1) - negatives
    numerator = np.sum(positives * (below + 0.5 * negatives), axis=1)
    denominator = positives.sum(axis=1) * negatives.sum(axis=1)
    return np.divide(
        numerator, denominator, out=np.full(len(weights), np.nan), where=denominator > 0
    )


def interaction_statistics(
    labels: Any, score_arrays: Any, old_count: int = 3, draws: int = 20000, seed: int = 2026091201
) -> list[dict[str, Any]]:
    """Scores shape [pairs,3,items]; old fixed cases, new disjoint pair bootstrap."""
    labels, scores = np.asarray(labels), np.asarray(score_arrays, dtype=float)
    if labels.ndim != 2 or scores.shape != (labels.shape[0], 3, labels.shape[1]):
        raise ValueError("Interaction score coordinates invalid")
    if not np.isfinite(scores).all() or not np.isin(labels, [0, 1]).all():
        raise ValueError("Invalid stored scores/risks")
    point = np.array(
        [
            [np.nan if (v := weighted_auc(y, s)) is None else v for s in ss]
            for y, ss in zip(labels, scores, strict=False)
        ]
    )
    common = np.isfinite(point).all(axis=1)
    old = np.arange(old_count)
    new = np.flatnonzero(common & (np.arange(len(labels)) >= old_count))
    descriptive = not common[old].all() or len(new) < 12
    outputs: list[dict[str, Any]] = []
    for index, name in ((1, "reference"), (2, "entropy")):
        delta = point[:, index] - point[:, 0]
        estimate = (
            float(delta[new].mean() - delta[old].mean()) if common[old].all() and len(new) else None
        )
        outputs.append(
            {
                "alternative": name,
                "estimate": estimate,
                "common_new_pairs": len(new),
                "old_reference_complete": bool(common[old].all()),
                "status": "descriptive" if descriptive else "pending",
                "per_pair_auc": [None if not np.isfinite(v) else float(v) for v in point[:, index]],
                "per_pair_gold_auc": [
                    None if not np.isfinite(v) else float(v) for v in point[:, 0]
                ],
                "ci": None,
                "valid_bootstrap_fraction": None,
                "leave_one_new_pair_out": (
                    []
                    if estimate is None or len(new) < 2
                    else [
                        float(np.delete(delta[new], j).mean() - delta[old].mean())
                        for j in range(len(new))
                    ]
                ),
            }
        )
    if descriptive:
        return outputs
    item_rng = np.random.default_rng(seed)
    pair_rng = np.random.default_rng(seed + 1)
    values: list[list[Any]] = [[], []]
    for start in range(0, draws, 128):
        count = min(128, draws - start)
        weights = item_rng.multinomial(
            labels.shape[1], np.full(labels.shape[1], 1 / labels.shape[1]), size=count
        )
        pair_indices = pair_rng.integers(len(new), size=(count, len(new)))
        auc = np.stack(
            [
                np.stack([_auc_many(labels[p], scores[p, s], weights) for s in range(3)], axis=1)
                for p in [*old, *new]
            ],
            axis=1,
        )
        for out_index, score_index in enumerate((1, 2)):
            differences = auc[:, :, score_index] - auc[:, :, 0]
            old_average = differences[:, :old_count].mean(axis=1)
            selected = np.take_along_axis(differences[:, old_count:], pair_indices, axis=1)
            values[out_index].extend(selected.mean(axis=1) - old_average)
    alpha = 0.05 / 22
    for output, samples in zip(outputs, values, strict=False):
        distribution = np.asarray(samples)
        valid = distribution[np.isfinite(distribution)]
        output["valid_bootstrap_fraction"] = len(valid) / draws
        output["bootstrap_draws"] = draws
        output["bonferroni_family"] = 22
        output["ci"] = (
            np.quantile(valid, [alpha / 2, 1 - alpha / 2]).tolist() if len(valid) else None
        )
        output["status"] = "inferential" if len(valid) / draws >= 0.95 else "descriptive"
    return outputs
