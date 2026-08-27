"""Backward-compatible facade for :mod:`promptcontrollab.audit.pr_summary`."""

from promptcontrollab.audit.pr_summary import (
    build_pr_summary,
    render_pr_summary_markdown,
    write_pr_summary,
)

__all__ = [
    "build_pr_summary",
    "render_pr_summary_markdown",
    "write_pr_summary",
]
