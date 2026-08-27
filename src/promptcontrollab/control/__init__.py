"""Versioned control runs, events, bridges, attribution, and stability analysis."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "AttributionReport": ("promptcontrollab.control.control_protocol", "AttributionReport"),
    "ControlDecision": ("promptcontrollab.control.control_protocol", "ControlDecision"),
    "ControlEvent": ("promptcontrollab.control.control_protocol", "ControlEvent"),
    "ControlRun": ("promptcontrollab.control.control_protocol", "ControlRun"),
    "PreflightDecision": ("promptcontrollab.control.control_protocol", "PreflightDecision"),
    "StabilityReport": ("promptcontrollab.control.control_protocol", "StabilityReport"),
    "analyze_attribution": ("promptcontrollab.control.control_analysis", "analyze_attribution"),
    "analyze_stability": ("promptcontrollab.control.control_analysis", "analyze_stability"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Load a public control symbol without eagerly importing bridge services."""

    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, symbol_name = target
    value = getattr(import_module(module_name), symbol_name)
    globals()[name] = value
    return value
