"""Backward-compatible facade for :mod:`promptcontrollab.evidence.external_evidence`."""

from promptcontrollab.evidence.external_evidence import (
    ExternalTool,
    attach_evidence_gate_to_audit,
    build_external_evidence,
    build_external_evidence_audit,
    render_bridge_summary_html,
    render_evidence_audit_html,
    render_source_input_verification_html,
    verify_source_inputs,
)

__all__ = [
    "ExternalTool",
    "build_external_evidence",
    "build_external_evidence_audit",
    "verify_source_inputs",
    "attach_evidence_gate_to_audit",
    "render_evidence_audit_html",
    "render_source_input_verification_html",
    "render_bridge_summary_html",
]
