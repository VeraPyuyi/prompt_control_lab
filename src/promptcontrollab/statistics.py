"""Backward-compatible facade for :mod:`promptcontrollab.evaluation.statistics`."""

from promptcontrollab.evaluation.statistics import (
    ComparisonResult,
    bootstrap_ci,
    compare_prediction_files,
    holm_adjust,
    interpret_delta,
    mean,
    paired_compare,
    paired_permutation_p_value,
)

__all__ = [
    "ComparisonResult",
    "bootstrap_ci",
    "compare_prediction_files",
    "holm_adjust",
    "interpret_delta",
    "mean",
    "paired_compare",
    "paired_permutation_p_value",
]
