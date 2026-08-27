"""Backward-compatible facade for :mod:`promptcontrollab.evaluation.history`."""

from promptcontrollab.evaluation.history import (
    compare_history,
    index_history,
    summarize_run,
)

__all__ = [
    "compare_history",
    "index_history",
    "summarize_run",
]
