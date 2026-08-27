"""Reproducible prompt evaluation, statistics, gates, and reporting APIs."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "ComparisonResult": (
        "promptcontrollab.evaluation.statistics",
        "ComparisonResult",
    ),
    "ReportModel": ("promptcontrollab.evaluation.report_model", "ReportModel"),
    "SplitResult": ("promptcontrollab.evaluation.splitting", "SplitResult"),
    "compare_prediction_files": (
        "promptcontrollab.evaluation.statistics",
        "compare_prediction_files",
    ),
    "generate_explanation": ("promptcontrollab.evaluation.explain", "generate_explanation"),
    "generate_report": ("promptcontrollab.evaluation.reporting", "generate_report"),
    "make_split": ("promptcontrollab.evaluation.splitting", "make_split"),
    "run_gate": ("promptcontrollab.evaluation.gate", "run_gate"),
    "run_import_eval": ("promptcontrollab.evaluation.evaluation", "run_import_eval"),
    "run_quick_analysis": ("promptcontrollab.evaluation.workflow", "run_quick_analysis"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Load a public evaluation symbol without creating domain import cycles."""

    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, symbol_name = target
    value = getattr(import_module(module_name), symbol_name)
    globals()[name] = value
    return value
