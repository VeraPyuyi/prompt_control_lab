"""Reproducible prompt evaluation, statistics, gates, and reporting APIs."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from promptcontrollab.core.schemas import (
    PredictionRecord as PredictionRecord,
)
from promptcontrollab.core.schemas import (
    TaskRecord as TaskRecord,
)

_EXPORTS = {
    "RawPredictionOutput": (
        "promptcontrollab.evaluation.evaluation",
        "RawPredictionOutput",
    ),
    "PredictionRecord": ("promptcontrollab.core.schemas", "PredictionRecord"),
    "ComparisonResult": (
        "promptcontrollab.evaluation.statistics",
        "ComparisonResult",
    ),
    "ReportModel": ("promptcontrollab.evaluation.report_model", "ReportModel"),
    "SplitResult": ("promptcontrollab.evaluation.splitting", "SplitResult"),
    "TaskRecord": ("promptcontrollab.core.schemas", "TaskRecord"),
    "build_predictions": (
        "promptcontrollab.evaluation.evaluation",
        "build_predictions",
    ),
    "compare_history": ("promptcontrollab.evaluation.history", "compare_history"),
    "compare_prediction_files": (
        "promptcontrollab.evaluation.statistics",
        "compare_prediction_files",
    ),
    "compare_runs": ("promptcontrollab.evaluation.run_comparison", "compare_runs"),
    "review_changes": ("promptcontrollab.evaluation.change_review", "review_changes"),
    "config_metric": ("promptcontrollab.evaluation.workflow", "config_metric"),
    "export_report_zip": (
        "promptcontrollab.evaluation.artifact_export",
        "export_report_zip",
    ),
    "generate_explanation": ("promptcontrollab.evaluation.explain", "generate_explanation"),
    "generate_report": ("promptcontrollab.evaluation.reporting", "generate_report"),
    "index_history": ("promptcontrollab.evaluation.history", "index_history"),
    "load_analyze_config": (
        "promptcontrollab.evaluation.workflow",
        "load_analyze_config",
    ),
    "load_prediction_outputs": (
        "promptcontrollab.evaluation.evaluation",
        "load_prediction_outputs",
    ),
    "load_scored_predictions": (
        "promptcontrollab.evaluation.evaluation",
        "load_scored_predictions",
    ),
    "load_tasks": ("promptcontrollab.evaluation.splitting", "load_tasks"),
    "make_split": ("promptcontrollab.evaluation.splitting", "make_split"),
    "resolve_analyze_paths": (
        "promptcontrollab.evaluation.workflow",
        "resolve_analyze_paths",
    ),
    "run_comparison_validity": (
        "promptcontrollab.evaluation.validity",
        "run_comparison_validity",
    ),
    "run_gate": ("promptcontrollab.evaluation.gate", "run_gate"),
    "run_import_eval": ("promptcontrollab.evaluation.evaluation", "run_import_eval"),
    "run_quick_analysis": ("promptcontrollab.evaluation.workflow", "run_quick_analysis"),
    "score_output": ("promptcontrollab.evaluation.metrics", "score_output"),
    "summarize_predictions": (
        "promptcontrollab.evaluation.metrics",
        "summarize_predictions",
    ),
    "write_split": ("promptcontrollab.evaluation.splitting", "write_split"),
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
