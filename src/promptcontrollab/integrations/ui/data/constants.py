"""Artifact names shared by dashboard data readers."""

from __future__ import annotations

CONTROL_ARTIFACTS = (
    "control_run.json",
    "events.jsonl",
    "preflight.json",
    "attribution.json",
    "stability.json",
    "decision.json",
    "provider_result.json",
    "audit_result.json",
    "report.md",
    "report.html",
)


PROMPT_REACH_ARTIFACTS = (
    "prompt_reachability",
    "readout_alignment",
    "prompt_routing",
    "prompt_projection",
    "prompt_stability",
)


_PROMPT_REACH_PATHS = tuple(
    path
    for name in PROMPT_REACH_ARTIFACTS
    for path in (f"{name}.json", f"diagnostics/{name}.json")
)


_CONTROL_CERTIFICATE_PATHS = tuple(
    path
    for name in ("terminal_sensitivity", "green_certificate", "posterior_certificate")
    for path in (f"{name}.json", f"diagnostics/{name}.json")
)


RUN_ARTIFACTS = [
    *CONTROL_ARTIFACTS,
    "manifest.json",
    "source_manifest.json",
    "evidence_matrix.json",
    "interpretability_report.json",
    "interpretability_report.html",
    "peoc_evidence.json",
    "research_case_study.json",
    "research_case_study.md",
    "research_case_study.html",
    "stats.json",
    "gate_result.json",
    "comparison_validity.json",
    "explanation.json",
    "model_drift.json",
    "audit_result.json",
    "history_index.json",
    "history_compare.json",
    "agent_run.json",
    "posttrain_gate.json",
    "checkpoint_comparison.json",
    "mechanism_attribution.json",
    "decision_trace.json",
    *_PROMPT_REACH_PATHS,
    *_CONTROL_CERTIFICATE_PATHS,
    "research_bundle.json",
    "research_bundle.html",
    "research_overview.svg",
    "research_bundle_verification.json",
    "research_bundle_verification.html",
    "source_input_verification.json",
    "source_input_verification.html",
    "research_diagnostics.json",
    "research_gap_plan.json",
    "research_gap_status.json",
    "evidence_card.json",
    "evidence_gate_result.json",
    "evidence_gate_result.md",
    "evidence_gate_result.html",
    "claim_check.json",
    "evidence_from_result.json",
    "evidence_audit_result.json",
    "evidence_audit_result.html",
    "bridge_summary.json",
    "bridge_summary.html",
    "ecosystem_demo.json",
    "ecosystem_scorecard.json",
    "ecosystem_scorecard.html",
    "prompt_assets.json",
    "prompt_assets.html",
    "prompt_optimizer_gap_plan.json",
    "prompt_optimizer_gap_plan.html",
    "eval_scaffold/scaffold_check.json",
    "eval_scaffold/scaffold_check.html",
]


RUN_LEVEL_ARTIFACTS = [
    *CONTROL_ARTIFACTS,
    "manifest.json",
    "source_manifest.json",
    "evidence_matrix.json",
    "interpretability_report.json",
    "interpretability_report.html",
    "peoc_evidence.json",
    "research_case_study.json",
    "research_case_study.md",
    "research_case_study.html",
    "stats.json",
    "gate_result.json",
    "comparison_validity.json",
    "explanation.json",
    "model_drift.json",
    "audit_result.json",
    "agent_run.json",
    "posttrain_gate.json",
    "checkpoint_comparison.json",
    "mechanism_attribution.json",
    "decision_trace.json",
    *_PROMPT_REACH_PATHS,
    *_CONTROL_CERTIFICATE_PATHS,
    "research_bundle.json",
    "research_bundle.html",
    "research_overview.svg",
    "research_bundle_verification.json",
    "research_bundle_verification.html",
    "source_input_verification.json",
    "source_input_verification.html",
    "research_diagnostics.json",
    "research_gap_plan.json",
    "research_gap_status.json",
    "evidence_card.json",
    "evidence_gate_result.json",
    "evidence_gate_result.md",
    "evidence_gate_result.html",
    "claim_check.json",
    "evidence_from_result.json",
    "evidence_audit_result.json",
    "evidence_audit_result.html",
    "bridge_summary.json",
    "bridge_summary.html",
    "ecosystem_demo.json",
    "ecosystem_scorecard.json",
    "ecosystem_scorecard.html",
    "prompt_assets.json",
    "prompt_assets.html",
    "prompt_optimizer_gap_plan.json",
    "prompt_optimizer_gap_plan.html",
    "eval_scaffold/scaffold_check.json",
    "eval_scaffold/scaffold_check.html",
]


_INTERNAL_RUN_DIRECTORIES = {
    "baseline",
    "candidate",
    "diagnostics",
    "eval_scaffold",
    "inputs",
}


PEOC_STATUSES = ("available", "partial", "failed_validation", "unusable", "missing")
