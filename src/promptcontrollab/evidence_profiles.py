"""Backward-compatible facade for :mod:`promptcontrollab.evidence.evidence_profiles`."""

from promptcontrollab.evidence.evidence_profiles import (
    LEGACY_ADAPTER_NAMES,
    EvidenceProfile,
    evidence_profile_registry,
    get_evidence_profile,
)

__all__ = [
    "LEGACY_ADAPTER_NAMES",
    "EvidenceProfile",
    "evidence_profile_registry",
    "get_evidence_profile",
]
