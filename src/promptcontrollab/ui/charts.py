"""Backward-compatible facade for :mod:`promptcontrollab.integrations.ui.charts`."""
# ruff: noqa: F401

from promptcontrollab.integrations.ui.charts import (
    control_event_timeline,
    control_signal_bar,
    file_breakdown_bar,
    green_boundary_margin,
    history_category_timeline,
    history_numeric_trend,
    research_diagnostic_bar,
    risk_category_bar,
    score_delta_ci,
    slice_score_heatmap,
    terminal_sensitivity_decay,
)

__all__ = [name for name in globals() if not name.startswith("_")]
