"""Backward-compatible facade for :mod:`promptcontrollab.evaluation.metrics`."""

from promptcontrollab.evaluation.metrics import (
    normalize_text,
    score_output,
    summarize_predictions,
)

__all__ = [
    "normalize_text",
    "score_output",
    "summarize_predictions",
]
