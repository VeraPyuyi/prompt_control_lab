"""Evidence ingestion, normalization, interpretation, and post-training gates."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "EvidenceImportOptions": ("promptcontrollab.evidence.server_evidence", "EvidenceImportOptions"),
    "EvidenceProfile": ("promptcontrollab.evidence.evidence_profiles", "EvidenceProfile"),
    "PeocImportOptions": ("promptcontrollab.evidence.peoc_import", "PeocImportOptions"),
    "PeocSourceOverrides": ("promptcontrollab.evidence.peoc_import", "PeocSourceOverrides"),
    "PilotInputs": ("promptcontrollab.evidence.posttrain_pilot", "PilotInputs"),
    "PosttrainPilotError": (
        "promptcontrollab.evidence.posttrain_pilot_runner",
        "PosttrainPilotError",
    ),
    "build_evidence_card": ("promptcontrollab.evidence.evidence_card", "build_evidence_card"),
    "build_external_evidence": (
        "promptcontrollab.evidence.external_evidence",
        "build_external_evidence",
    ),
    "build_external_evidence_audit": (
        "promptcontrollab.evidence.external_evidence",
        "build_external_evidence_audit",
    ),
    "build_peoc_evidence": ("promptcontrollab.evidence.peoc_import", "build_peoc_evidence"),
    "build_sft_pilot_plan": (
        "promptcontrollab.evidence.posttrain_pilot",
        "build_sft_pilot_plan",
    ),
    "detect_ingest_source": ("promptcontrollab.evidence.ingest", "detect_ingest_source"),
    "discover_peoc_sources": (
        "promptcontrollab.evidence.peoc_import",
        "discover_peoc_sources",
    ),
    "evidence_profile_registry": (
        "promptcontrollab.evidence.evidence_profiles",
        "evidence_profile_registry",
    ),
    "execute_sft_pilot": (
        "promptcontrollab.evidence.posttrain_pilot_runner",
        "execute_sft_pilot",
    ),
    "export_posttrain_pilot": (
        "promptcontrollab.evidence.posttrain_export",
        "export_posttrain_pilot",
    ),
    "get_evidence_profile": (
        "promptcontrollab.evidence.evidence_profiles",
        "get_evidence_profile",
    ),
    "import_evidence_manifest": (
        "promptcontrollab.evidence.server_evidence",
        "import_evidence_manifest",
    ),
    "import_peoc_bundle": ("promptcontrollab.evidence.peoc_import", "import_peoc_bundle"),
    "ingest_auto_results": ("promptcontrollab.evidence.ingest", "ingest_auto_results"),
    "ingest_deepeval_results": ("promptcontrollab.evidence.ingest", "ingest_deepeval_results"),
    "ingest_langfuse_results": ("promptcontrollab.evidence.ingest", "ingest_langfuse_results"),
    "ingest_langsmith_results": ("promptcontrollab.evidence.ingest", "ingest_langsmith_results"),
    "ingest_prompt_optimizer_assets": (
        "promptcontrollab.evidence.ingest",
        "ingest_prompt_optimizer_assets",
    ),
    "ingest_promptfoo_results": ("promptcontrollab.evidence.ingest", "ingest_promptfoo_results"),
    "merge_evidence_manifests": (
        "promptcontrollab.evidence.server_evidence",
        "merge_evidence_manifests",
    ),
    "prepare_sft_pilot_data": (
        "promptcontrollab.evidence.posttrain_pilot_data",
        "prepare_sft_pilot_data",
    ),
    "render_peoc_case_study_html": (
        "promptcontrollab.evidence.peoc_reporting",
        "render_peoc_case_study_html",
    ),
    "render_peoc_case_study_markdown": (
        "promptcontrollab.evidence.peoc_reporting",
        "render_peoc_case_study_markdown",
    ),
    "run_evidence_gate": ("promptcontrollab.evidence.evidence_gate", "run_evidence_gate"),
    "run_posttrain_gate": ("promptcontrollab.evidence.posttrain_gate", "run_posttrain_gate"),
    "scan_evidence_root": ("promptcontrollab.evidence.server_evidence", "scan_evidence_root"),
    "verify_source_inputs": (
        "promptcontrollab.evidence.external_evidence",
        "verify_source_inputs",
    ),
    "write_evidence_card": ("promptcontrollab.evidence.evidence_card", "write_evidence_card"),
    "write_pilot_summary": (
        "promptcontrollab.evidence.posttrain_pilot_summary",
        "write_pilot_summary",
    ),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Load a public evidence symbol on first access."""

    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, symbol_name = target
    value = getattr(import_module(module_name), symbol_name)
    globals()[name] = value
    return value
