"""Compatibility facade for canonical fixed transfer forecasts."""

from promptcontrollab.diagnostics.research_tools.transfer_prediction import (
    EVIDENCE,
    PAIR_TYPES,
    PREDICTORS,
    SCORES,
    analyze_document,
    binary_auc,
    fixed_predictions,
)

__all__ = [
    "EVIDENCE",
    "PAIR_TYPES",
    "PREDICTORS",
    "SCORES",
    "analyze_document",
    "binary_auc",
    "fixed_predictions",
]
