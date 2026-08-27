"""Backward-compatible facade for :mod:`promptcontrollab.preflight.scaffold_check`."""

from promptcontrollab.preflight.scaffold_check import (
    PLACEHOLDER_MARKERS,
    check_prompt_optimizer_eval_scaffold,
    render_scaffold_check_html,
    render_scaffold_check_markdown,
    write_scaffold_check,
)

__all__ = [
    "PLACEHOLDER_MARKERS",
    "check_prompt_optimizer_eval_scaffold",
    "render_scaffold_check_html",
    "render_scaffold_check_markdown",
    "write_scaffold_check",
]
