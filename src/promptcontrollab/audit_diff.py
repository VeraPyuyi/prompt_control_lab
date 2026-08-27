"""Backward-compatible facade for :mod:`promptcontrollab.audit.audit_diff`."""

from promptcontrollab.audit.audit_diff import (
    CONFIG_EXTENSIONS,
    DANGEROUS_PARTS,
    DEPENDENCY_FILES,
    LOCKFILES,
    SOURCE_EXTENSIONS,
    _parse_external_secret_output,
    run_audit_diff,
)

__all__ = [
    "CONFIG_EXTENSIONS",
    "DANGEROUS_PARTS",
    "DEPENDENCY_FILES",
    "LOCKFILES",
    "SOURCE_EXTENSIONS",
    "_parse_external_secret_output",
    "run_audit_diff",
]
