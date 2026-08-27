"""Statistical comparisons for prompt variants."""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from promptcontrollab.core.files import JsonDict, write_json
from promptcontrollab.evaluation.evaluation import load_scored_predictions


@dataclass(frozen=True)
class ComparisonResult:
    """Paired comparison result."""

    n: int
    baseline_mean: float
    candidate_mean: float
    mean_delta: float
    bootstrap_ci: tuple[float, float]
    permutation_p_value: float
    holm_adjusted_p_value: float

    def to_json(self) -> JsonDict:
        return {
            "n": self.n,
            "baseline_mean": self.baseline_mean,
            "candidate_mean": self.candidate_mean,
            "mean_delta": self.mean_delta,
            "bootstrap_ci": list(self.bootstrap_ci),
            "permutation_p_value": self.permutation_p_value,
            "holm_adjusted_p_value": self.holm_adjusted_p_value,
            "interpretation": interpret_delta(
                self.mean_delta,
                self.bootstrap_ci,
                self.holm_adjusted_p_value,
            ),
        }


def compare_prediction_files(
    *,
    baseline_path: Path,
    candidate_path: Path,
    out_path: Path,
    seed: int,
    bootstrap_samples: int,
    permutation_samples: int,
) -> JsonDict:
    """Compare two prediction files and write ``stats.json``."""

    baseline = load_scored_predictions(baseline_path)
    candidate = load_scored_predictions(candidate_path)
    result = paired_compare(
        {record.id: record.score for record in baseline},
        {record.id: record.score for record in candidate},
        seed=seed,
        bootstrap_samples=bootstrap_samples,
        permutation_samples=permutation_samples,
    )
    payload: JsonDict = {
        "comparisons": [result.to_json()],
        "holm_family_size": 1,
    }
    write_json(out_path, payload)
    return payload


def paired_compare(
    baseline: dict[str, float],
    candidate: dict[str, float],
    *,
    seed: int,
    bootstrap_samples: int,
    permutation_samples: int,
) -> ComparisonResult:
    """Run paired bootstrap and paired sign-flip permutation test."""

    common_ids = sorted(set(baseline) & set(candidate))
    if not common_ids:
        msg = "Baseline and candidate have no shared ids"
        raise ValueError(msg)
    diffs = [candidate[item_id] - baseline[item_id] for item_id in common_ids]
    baseline_values = [baseline[item_id] for item_id in common_ids]
    candidate_values = [candidate[item_id] for item_id in common_ids]
    mean_delta = mean(diffs)
    ci = bootstrap_ci(diffs, seed=seed, samples=bootstrap_samples)
    p_value = paired_permutation_p_value(diffs, seed=seed, samples=permutation_samples)
    return ComparisonResult(
        n=len(common_ids),
        baseline_mean=mean(baseline_values),
        candidate_mean=mean(candidate_values),
        mean_delta=mean_delta,
        bootstrap_ci=ci,
        permutation_p_value=p_value,
        holm_adjusted_p_value=holm_adjust([p_value])[0],
    )


def mean(values: list[float]) -> float:
    """Mean of a non-empty list."""

    if not values:
        msg = "Cannot compute mean of empty list"
        raise ValueError(msg)
    return sum(values) / len(values)


def bootstrap_ci(diffs: list[float], *, seed: int, samples: int) -> tuple[float, float]:
    """Paired bootstrap confidence interval over score deltas."""

    if samples <= 0:
        return (mean(diffs), mean(diffs))
    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(samples):
        draw = [diffs[rng.randrange(len(diffs))] for _ in diffs]
        estimates.append(mean(draw))
    estimates.sort()
    lo = estimates[int(0.025 * (len(estimates) - 1))]
    hi = estimates[int(0.975 * (len(estimates) - 1))]
    return (lo, hi)


def paired_permutation_p_value(diffs: list[float], *, seed: int, samples: int) -> float:
    """Two-sided paired sign-flip permutation p-value."""

    observed = abs(mean(diffs))
    if samples <= 0:
        return 1.0
    rng = random.Random(seed)
    extreme = 0
    for _ in range(samples):
        flipped = [diff if rng.random() < 0.5 else -diff for diff in diffs]
        if abs(mean(flipped)) >= observed:
            extreme += 1
    return (extreme + 1) / (samples + 1)


def holm_adjust(p_values: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values."""

    indexed = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [1.0 for _ in p_values]
    running_max = 0.0
    family_size = len(p_values)
    for rank, (original_index, p_value) in enumerate(indexed):
        candidate = min(1.0, (family_size - rank) * p_value)
        running_max = max(running_max, candidate)
        adjusted[original_index] = running_max
    return adjusted


def interpret_delta(delta: float, ci: tuple[float, float], adjusted_p_value: float) -> str:
    """Plain-language interpretation for reports."""

    lo, hi = ci
    if lo > 0 and adjusted_p_value < 0.05:
        return "candidate_improved_reliably"
    if hi < 0 and adjusted_p_value < 0.05:
        return "candidate_regressed_reliably"
    if delta > 0:
        return "candidate_higher_but_uncertain"
    if delta < 0:
        return "candidate_lower_but_uncertain"
    return "no_observed_delta"

