"""Backward-compatible facade for :mod:`promptcontrollab.evidence.ingest`."""

from promptcontrollab.evidence.ingest import (
    detect_ingest_source,
    ingest_auto_results,
    ingest_deepeval_results,
    ingest_langfuse_results,
    ingest_langsmith_results,
    ingest_prompt_optimizer_assets,
    ingest_promptfoo_results,
    render_prompt_assets_html,
    render_prompt_assets_markdown,
    render_prompt_optimizer_eval_scaffold_markdown,
    render_prompt_optimizer_gap_plan_html,
    render_prompt_optimizer_gap_plan_markdown,
)

__all__ = [
    "ingest_auto_results",
    "detect_ingest_source",
    "ingest_promptfoo_results",
    "ingest_langfuse_results",
    "ingest_langsmith_results",
    "ingest_deepeval_results",
    "ingest_prompt_optimizer_assets",
    "render_prompt_assets_markdown",
    "render_prompt_optimizer_gap_plan_markdown",
    "render_prompt_optimizer_eval_scaffold_markdown",
    "render_prompt_assets_html",
    "render_prompt_optimizer_gap_plan_html",
]
