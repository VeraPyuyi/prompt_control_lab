"""Public coordinator for the split research diagnostic workflow."""

from promptcontrollab.diagnostics.bundle import (
    build_research_bundle_index,
    verify_research_bundle_index,
    write_research_bundle_index,
)
from promptcontrollab.diagnostics.bundle_renderers import (
    render_research_bundle_index_html,
    render_research_bundle_index_markdown,
    render_research_bundle_verification_html,
)
from promptcontrollab.diagnostics.constants import PAPER_MAPPING, PAPER_REMEDIATION
from promptcontrollab.diagnostics.gap import (
    write_peoc_research_gap_plan,
    write_research_gap_status,
)
from promptcontrollab.diagnostics.gap_renderers import (
    render_research_gap_plan_html,
    render_research_gap_status_html,
)
from promptcontrollab.diagnostics.models import ResearchPaths
from promptcontrollab.diagnostics.renderers import (
    render_research_diagnostics_html,
    render_research_diagnostics_markdown,
    render_research_overview_svg,
)
from promptcontrollab.diagnostics.runner import run_research_diagnostics, write_research_demo

__all__ = [
    "PAPER_MAPPING",
    "PAPER_REMEDIATION",
    "ResearchPaths",
    "build_research_bundle_index",
    "render_research_bundle_index_html",
    "render_research_bundle_index_markdown",
    "render_research_bundle_verification_html",
    "render_research_diagnostics_html",
    "render_research_diagnostics_markdown",
    "render_research_gap_plan_html",
    "render_research_gap_status_html",
    "render_research_overview_svg",
    "run_research_diagnostics",
    "verify_research_bundle_index",
    "write_peoc_research_gap_plan",
    "write_research_bundle_index",
    "write_research_demo",
    "write_research_gap_status",
]
