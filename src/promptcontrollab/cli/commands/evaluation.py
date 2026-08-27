"""Evaluation command parser registration."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from promptcontrollab.cli.handlers.evaluation import (
    _cmd_analyze,
    _cmd_compare_runs,
    _cmd_eval,
    _cmd_explain,
    _cmd_export_report,
    _cmd_gate,
    _cmd_history_compare,
    _cmd_history_index,
    _cmd_report,
    _cmd_review,
    _cmd_split,
    _cmd_stats,
    _cmd_validity,
)


def _register_validity(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``validity`` command parser."""
    validity_parser = subcommands.add_parser(
        "validity",
        help="Audit whether a baseline/candidate run comparison is clean prompt-only evidence.",
    )
    validity_parser.add_argument(
        "--baseline",
        type=Path,
        required=True,
        help="Baseline run directory.",
    )
    validity_parser.add_argument(
        "--candidate",
        type=Path,
        required=True,
        help="Candidate run directory.",
    )
    validity_parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="comparison_validity.json output path. A sibling .md report is also written.",
    )
    validity_parser.set_defaults(func=_cmd_validity)


def _register_compare_runs(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``compare-runs`` command parser."""
    compare_runs_parser = subcommands.add_parser(
        "compare-runs",
        help="Compare two scored run directories and generate stats, validity, and report.",
    )
    compare_runs_parser.add_argument(
        "--baseline",
        type=Path,
        required=True,
        help="Baseline run directory.",
    )
    compare_runs_parser.add_argument(
        "--candidate",
        type=Path,
        required=True,
        help="Candidate run directory.",
    )
    compare_runs_parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Comparison run directory.",
    )
    compare_runs_parser.add_argument("--title", default="PromptControlLab Run Comparison")
    compare_runs_parser.add_argument("--seed", type=int, default=0)
    compare_runs_parser.add_argument("--bootstrap-samples", type=int, default=1000)
    compare_runs_parser.add_argument("--permutation-samples", type=int, default=1000)
    compare_runs_parser.set_defaults(func=_cmd_compare_runs)


def _register_review(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the unified ``review`` command parser."""

    parser = subcommands.add_parser(
        "review",
        help="Review a prompt, model, agent, or checkpoint change from two run directories.",
    )
    parser.add_argument("--baseline", type=Path, required=True, help="Baseline run directory.")
    parser.add_argument("--candidate", type=Path, required=True, help="Candidate run directory.")
    parser.add_argument("--out", type=Path, required=True, help="Change review output directory.")
    parser.add_argument(
        "--kind",
        choices=["auto", "prompt_change", "model_change", "agent_change", "checkpoint_change"],
        default="auto",
    )
    parser.add_argument("--mode", choices=["shadow"], default="shadow")
    parser.set_defaults(func=_cmd_review)


def _register_history(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``history`` command parser."""
    history_parser = subcommands.add_parser("history", help="Index or compare runs.")
    history_subcommands = history_parser.add_subparsers(dest="history_command", required=True)
    history_index = history_subcommands.add_parser("index", help="Build a run history index.")
    history_index.add_argument("--runs", type=Path, required=True, help="Runs directory.")
    history_index.add_argument("--out", type=Path, required=True, help="history_index.json path.")
    history_index.set_defaults(func=_cmd_history_index)
    history_compare = history_subcommands.add_parser("compare", help="Compare two run dirs.")
    history_compare.add_argument("--a", type=Path, required=True, help="Older run directory.")
    history_compare.add_argument("--b", type=Path, required=True, help="Newer run directory.")
    history_compare.add_argument(
        "--out",
        type=Path,
        required=True,
        help="history_compare.json path.",
    )
    history_compare.set_defaults(func=_cmd_history_compare)


def _register_export_report(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``export-report`` command parser."""
    export_parser = subcommands.add_parser(
        "export-report",
        help="Zip recognized artifacts from one run directory.",
    )
    export_parser.add_argument("--run", type=Path, required=True, help="Run directory.")
    export_parser.add_argument("--out", type=Path, required=True, help="Zip output path.")
    export_parser.set_defaults(func=_cmd_export_report)


def _register_analyze(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``analyze`` command parser."""
    analyze_parser = subcommands.add_parser(
        "analyze",
        help="Quick Mode: run split, eval, stats, explanation, gate, and report.",
    )
    analyze_parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="promptcontrol YAML file.",
    )
    analyze_parser.add_argument("--data", type=Path, default=None, help="Task JSONL file.")
    analyze_parser.add_argument(
        "--baseline-predictions",
        type=Path,
        default=None,
        help="Baseline raw predictions JSONL.",
    )
    analyze_parser.add_argument(
        "--candidate-predictions",
        type=Path,
        default=None,
        help="Candidate raw predictions JSONL.",
    )
    analyze_parser.add_argument("--out", type=Path, default=None, help="Quick run directory.")
    analyze_parser.add_argument("--metric", default=None, help="Deterministic metric name.")
    analyze_parser.add_argument("--baseline-model", default=None, help="Baseline model id.")
    analyze_parser.add_argument("--candidate-model", default=None, help="Candidate model id.")
    analyze_parser.add_argument("--baseline-provider", default=None, help="Baseline provider.")
    analyze_parser.add_argument("--candidate-provider", default=None, help="Candidate provider.")
    analyze_parser.add_argument("--api-version", default=None, help="Optional shared API version.")
    analyze_parser.add_argument("--prompt-id", default=None, help="Stable prompt id.")
    analyze_parser.add_argument("--prompt-file", type=Path, default=None, help="Prompt text file.")
    analyze_parser.add_argument("--prompt-version", default=None, help="Prompt version string.")
    analyze_parser.add_argument(
        "--baseline-prompt-id",
        default=None,
        help="Stable baseline prompt id for prompt-only validity checks.",
    )
    analyze_parser.add_argument(
        "--baseline-prompt-file",
        type=Path,
        default=None,
        help="Baseline prompt text file for prompt-only validity checks.",
    )
    analyze_parser.add_argument(
        "--baseline-prompt-version",
        default=None,
        help="Baseline prompt version string.",
    )
    analyze_parser.add_argument(
        "--candidate-prompt-id",
        default=None,
        help="Stable candidate prompt id for prompt-only validity checks.",
    )
    analyze_parser.add_argument(
        "--candidate-prompt-file",
        type=Path,
        default=None,
        help="Candidate prompt text file for prompt-only validity checks.",
    )
    analyze_parser.add_argument(
        "--candidate-prompt-version",
        default=None,
        help="Candidate prompt version string.",
    )
    analyze_parser.add_argument(
        "--verify-model",
        action="store_true",
        help="Verify public model metadata for supported providers.",
    )
    analyze_parser.add_argument("--train-ratio", type=float, default=None)
    analyze_parser.add_argument("--val-ratio", type=float, default=None)
    analyze_parser.add_argument("--seed", type=int, default=None)
    analyze_parser.add_argument("--bootstrap-samples", type=int, default=None)
    analyze_parser.add_argument("--permutation-samples", type=int, default=None)
    analyze_parser.add_argument(
        "--explain-level",
        choices=["plain", "technical"],
        default=None,
        help="Explanation detail level.",
    )
    analyze_parser.add_argument(
        "--policy",
        "--gate-policy",
        dest="policy",
        type=Path,
        default=None,
        help="Optional gate policy YAML.",
    )
    analyze_parser.add_argument("--title", default=None)
    analyze_parser.set_defaults(func=_cmd_analyze)


def _register_split(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``split`` command parser."""
    split_parser = subcommands.add_parser("split", help="Create train/val/withheld split manifest.")
    split_parser.add_argument("--data", type=Path, required=True, help="Task JSONL file.")
    split_parser.add_argument("--out", type=Path, required=True, help="Run directory.")
    split_parser.add_argument("--train-ratio", type=float, default=0.5)
    split_parser.add_argument("--val-ratio", type=float, default=0.25)
    split_parser.add_argument("--seed", type=int, default=0)
    split_parser.set_defaults(func=_cmd_split)


def _register_eval(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``eval`` command parser."""
    eval_parser = subcommands.add_parser("eval", help="Import and score model outputs.")
    eval_parser.add_argument("--data", type=Path, required=True, help="Task JSONL file.")
    eval_parser.add_argument(
        "--predictions",
        type=Path,
        required=True,
        help="Raw predictions JSONL.",
    )
    eval_parser.add_argument("--out", type=Path, required=True, help="Run directory.")
    eval_parser.add_argument("--metric", default="exact_match", help="Deterministic metric name.")
    eval_parser.add_argument("--method", default="candidate", help="Prompt/method name.")
    eval_parser.add_argument("--model", default=None, help="Model id used to produce predictions.")
    eval_parser.add_argument(
        "--provider",
        default=None,
        help="Provider used to produce predictions.",
    )
    eval_parser.add_argument("--api-version", default=None, help="Optional API version string.")
    eval_parser.add_argument(
        "--verify-model",
        action="store_true",
        help="Verify public model metadata for supported providers.",
    )
    eval_parser.set_defaults(func=_cmd_eval)


def _register_stats(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``stats`` command parser."""
    stats_parser = subcommands.add_parser(
        "stats",
        help="Compare baseline and candidate predictions.",
    )
    stats_parser.add_argument("--baseline", type=Path, required=True, help="Baseline scored JSONL.")
    stats_parser.add_argument(
        "--candidate",
        type=Path,
        required=True,
        help="Candidate scored JSONL.",
    )
    stats_parser.add_argument("--out", type=Path, required=True, help="stats.json output path.")
    stats_parser.add_argument("--seed", type=int, default=0)
    stats_parser.add_argument("--bootstrap-samples", type=int, default=1000)
    stats_parser.add_argument("--permutation-samples", type=int, default=1000)
    stats_parser.set_defaults(func=_cmd_stats)


def _register_report(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``report`` command parser."""
    report_parser = subcommands.add_parser("report", help="Generate Markdown and HTML reports.")
    report_parser.add_argument("--run", type=Path, required=True, help="Run directory.")
    report_parser.add_argument("--title", default="PromptControlLab Report")
    report_parser.set_defaults(func=_cmd_report)


def _register_explain(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``explain`` command parser."""
    explain_parser = subcommands.add_parser(
        "explain",
        help="Generate plain or technical explanation.json for a run.",
    )
    explain_parser.add_argument("--run", type=Path, required=True, help="Run directory.")
    explain_parser.add_argument("--level", choices=["plain", "technical"], default="plain")
    explain_parser.set_defaults(func=_cmd_explain)


def _register_gate(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``gate`` command parser."""
    gate_parser = subcommands.add_parser("gate", help="Evaluate a run against policy thresholds.")
    gate_parser.add_argument("--run", type=Path, required=True, help="Run directory.")
    gate_parser.add_argument("--policy", type=Path, default=None, help="Gate policy YAML.")
    gate_parser.set_defaults(func=_cmd_gate)


_REGISTRARS = {
    "validity": _register_validity,
    "compare-runs": _register_compare_runs,
    "review": _register_review,
    "history": _register_history,
    "export-report": _register_export_report,
    "analyze": _register_analyze,
    "split": _register_split,
    "eval": _register_eval,
    "stats": _register_stats,
    "report": _register_report,
    "explain": _register_explain,
    "gate": _register_gate,
}


def register_commands(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    names: Sequence[str] | None = None,
) -> None:
    """Register selected evaluation commands in the requested order."""

    selected = tuple(_REGISTRARS) if names is None else tuple(names)
    for name in selected:
        _REGISTRARS[name](subcommands)
