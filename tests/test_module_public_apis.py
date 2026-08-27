"""Smoke tests for the canonical imports shown in module documentation."""

from __future__ import annotations

import importlib

DOCUMENTED_IMPORTS = {
    "core": (
        "PromptControlLabError",
        "TaskRecord",
        "load_project_config",
        "read_json",
        "stable_digest",
        "write_json",
    ),
    "preflight": (
        "choose_tool_for_need",
        "guard_prompt",
        "improve_prompt",
        "load_guard_policy",
    ),
    "evaluation": (
        "compare_prediction_files",
        "generate_report",
        "run_gate",
        "run_import_eval",
        "run_quick_analysis",
    ),
    "control": (
        "ControlEvent",
        "ControlRun",
        "analyze_attribution",
        "analyze_stability",
        "run_control",
    ),
    "provenance": (
        "build_prompt_identity",
        "compare_model_identities",
        "detect_model_identity",
        "run_model_drift",
    ),
    "audit": (
        "build_agent_run_manifest",
        "build_pr_summary",
        "run_audit_diff",
        "run_claim_check",
    ),
    "diagnostics": (
        "analyze_green_certificate",
        "analyze_posterior_certificate",
        "analyze_terminal_sensitivity",
        "analyze_trajectory",
    ),
    "integrations": (
        "build_space_bundle",
        "call_provider",
        "doctor_harness",
        "install_plugin",
        "list_providers",
        "run_doctor",
    ),
}


def test_documented_canonical_imports_resolve() -> None:
    """Require every symbol shown in a module guide to be importable."""

    missing: list[str] = []
    for domain, symbols in DOCUMENTED_IMPORTS.items():
        module = importlib.import_module(f"promptcontrollab.{domain}")
        for symbol in symbols:
            if not hasattr(module, symbol):
                missing.append(f"promptcontrollab.{domain}.{symbol}")
    assert missing == []
