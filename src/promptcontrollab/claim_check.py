"""Backward-compatible facade for :mod:`promptcontrollab.audit.claim_check`."""

from promptcontrollab.audit.claim_check import (
    CLAIM_LABELS,
    CLAIM_REQUIREMENTS,
    TIER_ORDER,
    render_claim_check_html,
    render_claim_check_markdown,
    run_claim_check,
)

__all__ = [
    "CLAIM_LABELS",
    "CLAIM_REQUIREMENTS",
    "TIER_ORDER",
    "render_claim_check_html",
    "render_claim_check_markdown",
    "run_claim_check",
]
