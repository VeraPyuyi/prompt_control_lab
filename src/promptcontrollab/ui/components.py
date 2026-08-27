"""Backward-compatible facade for :mod:`promptcontrollab.integrations.ui.components`."""
# ruff: noqa: F401

from promptcontrollab.integrations.ui.components import (
    badge,
    dashboard_css,
    empty_state,
    evidence_ladder_html,
    metric_cards,
    paper_card_html,
    prompt_diff,
    recommendation_card_html,
    research_evidence_map_html,
    stat_card_html,
)

__all__ = [name for name in globals() if not name.startswith("_")]
