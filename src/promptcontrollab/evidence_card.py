"""Backward-compatible facade for :mod:`promptcontrollab.evidence.evidence_card`."""

from promptcontrollab.evidence.evidence_card import (
    build_evidence_card,
    render_evidence_card_html,
    render_evidence_card_markdown,
    write_evidence_card,
)

__all__ = [
    "build_evidence_card",
    "write_evidence_card",
    "render_evidence_card_markdown",
    "render_evidence_card_html",
]
