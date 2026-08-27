"""Backward-compatible facade for :mod:`promptcontrollab.evidence.evidence_gate`."""

from promptcontrollab.evidence.evidence_gate import (
    DYNAMIC_BUNDLE_ARTIFACTS,
    run_evidence_gate,
)

__all__ = [
    "DYNAMIC_BUNDLE_ARTIFACTS",
    "run_evidence_gate",
]
