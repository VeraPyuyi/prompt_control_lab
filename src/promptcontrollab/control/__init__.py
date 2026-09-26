"""Versioned control runs, events, bridges, attribution, and stability analysis."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "AttributionReport": ("promptcontrollab.control.control_protocol", "AttributionReport"),
    "ControlDecision": ("promptcontrollab.control.control_protocol", "ControlDecision"),
    "ControlBridge": ("promptcontrollab.control.control_bridge", "ControlBridge"),
    "ControlEvent": ("promptcontrollab.control.control_protocol", "ControlEvent"),
    "ControlRun": ("promptcontrollab.control.control_protocol", "ControlRun"),
    "EventLog": ("promptcontrollab.control.control_events", "EventLog"),
    "PreflightDecision": ("promptcontrollab.control.control_protocol", "PreflightDecision"),
    "StabilityReport": ("promptcontrollab.control.control_protocol", "StabilityReport"),
    "analyze_attribution": ("promptcontrollab.control.control_analysis", "analyze_attribution"),
    "analyze_stability": ("promptcontrollab.control.control_analysis", "analyze_stability"),
    "create_trace_server": ("promptcontrollab.control.trace_receiver", "create_trace_server"),
    "import_trace_file": ("promptcontrollab.control.trace_ingest", "import_trace_file"),
    "import_trace_payloads": (
        "promptcontrollab.control.trace_ingest",
        "import_trace_payloads",
    ),
    "run_control": ("promptcontrollab.control.control_workflow", "run_control"),
    "serve_trace_http": ("promptcontrollab.control.trace_receiver", "serve_trace_http"),
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
