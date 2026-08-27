"""Backward-compatible facade for :mod:`promptcontrollab.evidence.server_evidence`."""

from promptcontrollab.evidence.server_evidence import (
    ADAPTERS,
    MANIFEST_SCHEMA,
    MATRIX_SCHEMA,
    REPORT_SCHEMA,
    EvidenceImportOptions,
    evidence_profile_registry,
    import_evidence_manifest,
    merge_evidence_manifests,
    render_interpretability_html,
    scan_evidence_root,
    validate_evidence_destination,
)

__all__ = [
    "MANIFEST_SCHEMA",
    "MATRIX_SCHEMA",
    "REPORT_SCHEMA",
    "ADAPTERS",
    "evidence_profile_registry",
    "EvidenceImportOptions",
    "scan_evidence_root",
    "import_evidence_manifest",
    "merge_evidence_manifests",
    "validate_evidence_destination",
    "render_interpretability_html",
]
