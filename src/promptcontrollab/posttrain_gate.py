"""Backward-compatible facade for :mod:`promptcontrollab.evidence.posttrain_gate`."""

from promptcontrollab.evidence.posttrain_gate import (
    render_posttrain_html,
    render_posttrain_markdown,
    run_posttrain_gate,
)

__all__ = [
    "run_posttrain_gate",
    "render_posttrain_markdown",
    "render_posttrain_html",
]
