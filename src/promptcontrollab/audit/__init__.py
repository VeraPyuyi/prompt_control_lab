"""Repository changes, agent runs, pull requests, and claim auditing."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "build_agent_run_manifest": ("promptcontrollab.audit.agent_run", "build_agent_run_manifest"),
    "build_pr_summary": ("promptcontrollab.audit.pr_summary", "build_pr_summary"),
    "run_audit_diff": ("promptcontrollab.audit.audit_diff", "run_audit_diff"),
    "run_claim_check": ("promptcontrollab.audit.claim_check", "run_claim_check"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Load a public audit symbol without importing evaluation workflows."""

    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, symbol_name = target
    value = getattr(import_module(module_name), symbol_name)
    globals()[name] = value
    return value
