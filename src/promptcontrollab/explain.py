"""Backward-compatible facade for :mod:`promptcontrollab.evaluation.explain`."""

from promptcontrollab.evaluation.explain import (
    EXPLAIN_LEVELS,
    generate_explanation,
)

__all__ = [
    "EXPLAIN_LEVELS",
    "generate_explanation",
]
