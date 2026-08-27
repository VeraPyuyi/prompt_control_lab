"""Backward-compatible facade for :mod:`promptcontrollab.control.control_protocol`."""

from promptcontrollab.control.control_protocol import (
    REDACTED,
    AttributionReport,
    ControlDecision,
    ControlEvent,
    ControlRun,
    PreflightDecision,
    StabilityReport,
    redact_sensitive,
    utc_now,
)

__all__ = [
    "REDACTED",
    "AttributionReport",
    "ControlDecision",
    "ControlEvent",
    "ControlRun",
    "PreflightDecision",
    "StabilityReport",
    "redact_sensitive",
    "utc_now",
]
