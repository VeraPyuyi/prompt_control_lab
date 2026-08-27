"""Backward-compatible facade for :mod:`promptcontrollab.control.control_events`."""

from promptcontrollab.control.control_events import (
    EventLog,
    run_lifecycle_lock,
)

__all__ = [
    "EventLog",
    "run_lifecycle_lock",
]
