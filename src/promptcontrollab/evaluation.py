"""Backward-compatible facade for :mod:`promptcontrollab.evaluation.evaluation`."""

from promptcontrollab.evaluation.artifact_export import export_report_zip
from promptcontrollab.evaluation.evaluation import (
    RawPredictionOutput,
    build_predictions,
    load_prediction_outputs,
    load_scored_predictions,
    run_import_eval,
)
from promptcontrollab.evaluation.explain import generate_explanation
from promptcontrollab.evaluation.gate import run_gate
from promptcontrollab.evaluation.history import compare_history, index_history
from promptcontrollab.evaluation.metrics import score_output, summarize_predictions
from promptcontrollab.evaluation.report_model import ReportModel
from promptcontrollab.evaluation.reporting import generate_report
from promptcontrollab.evaluation.run_comparison import compare_runs
from promptcontrollab.evaluation.splitting import load_tasks, make_split, write_split
from promptcontrollab.evaluation.statistics import compare_prediction_files
from promptcontrollab.evaluation.validity import run_comparison_validity
from promptcontrollab.evaluation.workflow import (
    config_metric,
    load_analyze_config,
    resolve_analyze_paths,
    run_quick_analysis,
)

__all__ = [
    "RawPredictionOutput",
    "ReportModel",
    "build_predictions",
    "compare_history",
    "compare_prediction_files",
    "compare_runs",
    "config_metric",
    "export_report_zip",
    "generate_explanation",
    "generate_report",
    "index_history",
    "load_analyze_config",
    "load_prediction_outputs",
    "load_scored_predictions",
    "load_tasks",
    "make_split",
    "resolve_analyze_paths",
    "run_comparison_validity",
    "run_gate",
    "run_import_eval",
    "run_quick_analysis",
    "score_output",
    "summarize_predictions",
    "write_split",
]
