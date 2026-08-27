"""Prompt and model identity, provenance evidence, and drift analysis."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "ModelIdentity": ("promptcontrollab.provenance.model_identity", "ModelIdentity"),
    "build_prompt_identity": (
        "promptcontrollab.provenance.prompt_identity",
        "build_prompt_identity",
    ),
    "compare_model_identities": (
        "promptcontrollab.provenance.model_identity",
        "compare_model_identities",
    ),
    "detect_model_identity": (
        "promptcontrollab.provenance.model_identity",
        "detect_model_identity",
    ),
    "run_model_drift": ("promptcontrollab.provenance.model_drift", "run_model_drift"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Load a public provenance symbol on first access."""

    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, symbol_name = target
    value = getattr(import_module(module_name), symbol_name)
    globals()[name] = value
    return value
