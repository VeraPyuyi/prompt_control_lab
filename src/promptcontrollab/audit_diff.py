"""Backward-compatible facade for :mod:`promptcontrollab.audit.audit_diff`."""

from promptcontrollab.audit.audit_diff import (
    _parse_external_secret_output,
    run_audit_diff,
)

__all__ = [
    "_parse_external_secret_output",
    "run_audit_diff",
]
