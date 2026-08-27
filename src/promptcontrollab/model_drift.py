"""Backward-compatible facade for :mod:`promptcontrollab.provenance.model_drift`."""

from promptcontrollab.provenance.model_drift import (
    PROMPT_IDENTITY_KEYS,
    run_model_drift,
)

__all__ = [
    "PROMPT_IDENTITY_KEYS",
    "run_model_drift",
]
