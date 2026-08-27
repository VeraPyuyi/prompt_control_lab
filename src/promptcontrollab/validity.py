"""Backward-compatible facade for :mod:`promptcontrollab.evaluation.validity`."""

from promptcontrollab.evaluation.validity import (
    PROMPT_IDENTITY_KEYS,
    run_comparison_validity,
)

__all__ = [
    "PROMPT_IDENTITY_KEYS",
    "run_comparison_validity",
]
