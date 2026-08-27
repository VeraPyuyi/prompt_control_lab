"""Backward-compatible facade for :mod:`promptcontrollab.evaluation.history`."""

from promptcontrollab.evaluation.history import (
    PROMPT_IDENTITY_KEYS,
    compare_history,
    index_history,
    summarize_run,
)

__all__ = [
    "PROMPT_IDENTITY_KEYS",
    "compare_history",
    "index_history",
    "summarize_run",
]
