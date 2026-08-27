"""Backward-compatible facade for :mod:`promptcontrollab.evaluation.metrics`."""

from promptcontrollab.core.schemas import MetricSummary, PredictionRecord
from promptcontrollab.evaluation.metrics import (
    normalize_text,
    score_output,
    summarize_predictions,
)

__all__ = [
    "MetricSummary",
    "PredictionRecord",
    "normalize_text",
    "score_output",
    "summarize_predictions",
]
