"""Mechanism, stability, projection, and bounded control-certificate diagnostics."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "analyze_green_certificate": (
        "promptcontrollab.diagnostics.green_certificate",
        "analyze_green_certificate",
    ),
    "analyze_posterior_certificate": (
        "promptcontrollab.diagnostics.posterior_certificate",
        "analyze_posterior_certificate",
    ),
    "analyze_riccati": ("promptcontrollab.diagnostics.riccati", "analyze_riccati"),
    "analyze_soft_hard": ("promptcontrollab.diagnostics.soft_hard", "analyze_soft_hard"),
    "analyze_terminal_sensitivity": (
        "promptcontrollab.diagnostics.terminal_sensitivity",
        "analyze_terminal_sensitivity",
    ),
    "diagnostic_catalog": (
        "promptcontrollab.diagnostics.presentation",
        "diagnostic_catalog",
    ),
    "diagnostic_metric_label": (
        "promptcontrollab.diagnostics.presentation",
        "diagnostic_metric_label",
    ),
    "diagnostic_status_label": (
        "promptcontrollab.diagnostics.presentation",
        "diagnostic_status_label",
    ),
    "get_diagnostic_presentation": (
        "promptcontrollab.diagnostics.presentation",
        "get_diagnostic_presentation",
    ),
    "analyze_trajectory": ("promptcontrollab.diagnostics.trajectory", "analyze_trajectory"),
    "extract_hidden_states": (
        "promptcontrollab.diagnostics.hf_hidden",
        "extract_hidden_states",
    ),
    "load_prompt_texts": ("promptcontrollab.diagnostics.hf_hidden", "load_prompt_texts"),
    "summarize_tv_soft": ("promptcontrollab.diagnostics.tv_soft", "summarize_tv_soft"),
    "ResearchPaths": ("promptcontrollab.diagnostics.research_workflow", "ResearchPaths"),
    "PAPER_MAPPING": (
        "promptcontrollab.diagnostics.research_workflow",
        "PAPER_MAPPING",
    ),
    "PAPER_REMEDIATION": (
        "promptcontrollab.diagnostics.research_workflow",
        "PAPER_REMEDIATION",
    ),
    "build_research_bundle_index": (
        "promptcontrollab.diagnostics.research_workflow",
        "build_research_bundle_index",
    ),
    "render_research_diagnostics_html": (
        "promptcontrollab.diagnostics.research_workflow",
        "render_research_diagnostics_html",
    ),
    "render_research_diagnostics_markdown": (
        "promptcontrollab.diagnostics.research_workflow",
        "render_research_diagnostics_markdown",
    ),
    "render_research_bundle_index_html": (
        "promptcontrollab.diagnostics.research_workflow",
        "render_research_bundle_index_html",
    ),
    "render_research_bundle_index_markdown": (
        "promptcontrollab.diagnostics.research_workflow",
        "render_research_bundle_index_markdown",
    ),
    "render_research_bundle_verification_html": (
        "promptcontrollab.diagnostics.research_workflow",
        "render_research_bundle_verification_html",
    ),
    "render_research_gap_plan_html": (
        "promptcontrollab.diagnostics.research_workflow",
        "render_research_gap_plan_html",
    ),
    "render_research_gap_status_html": (
        "promptcontrollab.diagnostics.research_workflow",
        "render_research_gap_status_html",
    ),
    "render_research_overview_svg": (
        "promptcontrollab.diagnostics.research_workflow",
        "render_research_overview_svg",
    ),
    "run_research_diagnostics": (
        "promptcontrollab.diagnostics.research_workflow",
        "run_research_diagnostics",
    ),
    "verify_research_bundle_index": (
        "promptcontrollab.diagnostics.research_workflow",
        "verify_research_bundle_index",
    ),
    "write_peoc_research_gap_plan": (
        "promptcontrollab.diagnostics.research_workflow",
        "write_peoc_research_gap_plan",
    ),
    "write_research_bundle_index": (
        "promptcontrollab.diagnostics.research_workflow",
        "write_research_bundle_index",
    ),
    "write_research_demo": (
        "promptcontrollab.diagnostics.research_workflow",
        "write_research_demo",
    ),
    "write_research_gap_status": (
        "promptcontrollab.diagnostics.research_workflow",
        "write_research_gap_status",
    ),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Load a public diagnostic symbol without importing every optional backend."""

    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, symbol_name = target
    value = getattr(import_module(module_name), symbol_name)
    globals()[name] = value
    return value
