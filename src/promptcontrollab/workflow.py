"""Backward-compatible facade for :mod:`promptcontrollab.evaluation.workflow`."""

from promptcontrollab.evaluation.workflow import (
    config_metric,
    load_analyze_config,
    resolve_analyze_paths,
    run_quick_analysis,
)

__all__ = [
    "config_metric",
    "load_analyze_config",
    "resolve_analyze_paths",
    "run_quick_analysis",
]
