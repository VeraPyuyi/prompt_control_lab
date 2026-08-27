"""Backward-compatible facade for :mod:`promptcontrollab.core.doctor`."""

from promptcontrollab.core.doctor import (
    format_doctor,
    run_doctor,
)

__all__ = [
    "format_doctor",
    "run_doctor",
]
