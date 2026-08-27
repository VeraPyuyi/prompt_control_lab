"""Backward-compatible facade for :mod:`promptcontrollab.integrations.doctor`."""

from promptcontrollab.integrations.doctor import (
    format_doctor,
    run_doctor,
)

__all__ = [
    "format_doctor",
    "run_doctor",
]
