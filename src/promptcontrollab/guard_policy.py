"""Backward-compatible facade for :mod:`promptcontrollab.preflight.guard_policy`."""

from promptcontrollab.preflight.guard_policy import (
    GuardPolicy,
    GuardPolicyRule,
    GuardViolation,
    evaluate_guard_policy,
    highest_severity,
    load_guard_policy,
    severity_at_least,
    unique_categories,
)

__all__ = [
    "GuardPolicy",
    "GuardPolicyRule",
    "GuardViolation",
    "evaluate_guard_policy",
    "highest_severity",
    "load_guard_policy",
    "severity_at_least",
    "unique_categories",
]
