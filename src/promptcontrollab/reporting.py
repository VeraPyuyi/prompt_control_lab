"""Backward-compatible facade for :mod:`promptcontrollab.evaluation.reporting`."""

from promptcontrollab.evaluation.reporting import (
    generate_report,
    render_html,
    render_markdown,
)

__all__ = [
    "generate_report",
    "render_html",
    "render_markdown",
]
