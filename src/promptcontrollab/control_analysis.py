"""Backward-compatible facade for :mod:`promptcontrollab.control.control_analysis`."""

from promptcontrollab.control.control_analysis import (
    analyze_attribution,
    analyze_stability,
    make_control_decision,
)

__all__ = [
    "analyze_attribution",
    "analyze_stability",
    "make_control_decision",
]
