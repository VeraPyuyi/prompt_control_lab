"""Compatibility facade for the canonical measurement-value research tool."""

from promptcontrollab.diagnostics.research_tools.measurement_value import (
    EVIDENCE_STATUSES,
    SCORES,
    STRATEGIES,
    analyze_document,
    fixed_order,
    locked_decision,
)

__all__ = [
    "EVIDENCE_STATUSES",
    "SCORES",
    "STRATEGIES",
    "analyze_document",
    "fixed_order",
    "locked_decision",
]
