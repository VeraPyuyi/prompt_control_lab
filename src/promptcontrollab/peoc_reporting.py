"""Backward-compatible facade for :mod:`promptcontrollab.evidence.peoc_reporting`."""

from promptcontrollab.evidence.peoc_reporting import (
    render_peoc_case_study_html,
    render_peoc_case_study_markdown,
)

__all__ = [
    "render_peoc_case_study_markdown",
    "render_peoc_case_study_html",
]
