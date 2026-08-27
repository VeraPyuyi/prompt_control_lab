"""Mechanism, stability, projection, and bounded control-certificate diagnostics."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "analyze_green_certificate": (
        "promptcontrollab.green_certificate",
        "analyze_green_certificate",
    ),
    "analyze_posterior_certificate": (
        "promptcontrollab.posterior_certificate",
        "analyze_posterior_certificate",
    ),
    "analyze_riccati": ("promptcontrollab.riccati", "analyze_riccati"),
    "analyze_soft_hard": ("promptcontrollab.soft_hard", "analyze_soft_hard"),
    "analyze_terminal_sensitivity": (
        "promptcontrollab.terminal_sensitivity",
        "analyze_terminal_sensitivity",
    ),
    "analyze_trajectory": ("promptcontrollab.trajectory", "analyze_trajectory"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Load a public diagnostic symbol without importing every optional backend."""

    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, symbol_name = target
    value = getattr(import_module(module_name), symbol_name)
    globals()[name] = value
    return value
