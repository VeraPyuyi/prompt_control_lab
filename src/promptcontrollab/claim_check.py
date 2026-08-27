"""Backward-compatible facade for :mod:`promptcontrollab.audit.claim_check`."""

from promptcontrollab.audit.claim_check import (
    render_claim_check_html,
    render_claim_check_markdown,
    run_claim_check,
)

__all__ = [
    "render_claim_check_html",
    "render_claim_check_markdown",
    "run_claim_check",
]
