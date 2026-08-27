"""Backward-compatible facade for :mod:`promptcontrollab.preflight.tool_choice`."""

from promptcontrollab.preflight.tool_choice import (
    adoption_path_rows,
    choose_tool_for_need,
    format_tool_choice,
    market_gap_action_for_lane,
    market_gap_action_rows,
    render_tool_choice_markdown,
    tool_choice_lanes,
)

__all__ = [
    "adoption_path_rows",
    "choose_tool_for_need",
    "format_tool_choice",
    "market_gap_action_for_lane",
    "market_gap_action_rows",
    "render_tool_choice_markdown",
    "tool_choice_lanes",
]
