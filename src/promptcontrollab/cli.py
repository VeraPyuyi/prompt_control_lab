"""Command line interface for PromptControlLab."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from promptcontrollab.config import (
    get_config_float,
    get_config_int,
    get_config_path,
    get_config_str,
)
from promptcontrollab.errors import PromptControlLabError
from promptcontrollab.evaluation import run_import_eval
from promptcontrollab.explain import generate_explanation
from promptcontrollab.gate import run_gate
from promptcontrollab.reporting import generate_report
from promptcontrollab.riccati import analyze_riccati
from promptcontrollab.soft_hard import analyze_soft_hard
from promptcontrollab.splitting import load_tasks, make_split, write_split
from promptcontrollab.statistics import compare_prediction_files
from promptcontrollab.templates import write_example_project
from promptcontrollab.trajectory import analyze_trajectory
from promptcontrollab.tv_soft import summarize_tv_soft
from promptcontrollab.workflow import (
    config_metric,
    load_analyze_config,
    resolve_analyze_paths,
    run_quick_analysis,
)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (PromptControlLabError, ValueError, OSError) as exc:
        print(f"pcl: error: {exc}", file=sys.stderr)
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""

    parser = argparse.ArgumentParser(
        prog="pcl",
        description="PromptControlLab prompt evaluation and diagnostics toolkit.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    init_parser = subcommands.add_parser("init", help="Create an example project.")
    init_parser.add_argument("--path", type=Path, default=Path("."), help="Project directory.")
    init_parser.set_defaults(func=_cmd_init)

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

    split_parser = subcommands.add_parser("split", help="Create train/val/withheld split manifest.")
    split_parser.add_argument("--data", type=Path, required=True, help="Task JSONL file.")
    split_parser.add_argument("--out", type=Path, required=True, help="Run directory.")
    split_parser.add_argument("--train-ratio", type=float, default=0.5)
    split_parser.add_argument("--val-ratio", type=float, default=0.25)
    split_parser.add_argument("--seed", type=int, default=0)
    split_parser.set_defaults(func=_cmd_split)

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
    eval_parser.set_defaults(func=_cmd_eval)

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

    report_parser = subcommands.add_parser("report", help="Generate Markdown and HTML reports.")
    report_parser.add_argument("--run", type=Path, required=True, help="Run directory.")
    report_parser.add_argument("--title", default="PromptControlLab Report")
    report_parser.set_defaults(func=_cmd_report)

    explain_parser = subcommands.add_parser(
        "explain",
        help="Generate plain or technical explanation.json for a run.",
    )
    explain_parser.add_argument("--run", type=Path, required=True, help="Run directory.")
    explain_parser.add_argument("--level", choices=["plain", "technical"], default="plain")
    explain_parser.set_defaults(func=_cmd_explain)

    gate_parser = subcommands.add_parser("gate", help="Evaluate a run against policy thresholds.")
    gate_parser.add_argument("--run", type=Path, required=True, help="Run directory.")
    gate_parser.add_argument("--policy", type=Path, required=True, help="Gate policy YAML.")
    gate_parser.set_defaults(func=_cmd_gate)

    soft_parser = subcommands.add_parser("soft-hard", help="Analyze soft-to-hard projection risk.")
    soft_parser.add_argument("--soft", type=Path, required=True, help=".npz with array `soft`.")
    soft_parser.add_argument(
        "--vocab",
        type=Path,
        required=True,
        help=".npz with array `embeddings`.",
    )
    soft_parser.add_argument("--out", type=Path, required=True, help="Diagnostics directory.")
    soft_parser.add_argument("--explain-level", choices=["plain", "technical"], default=None)
    soft_parser.set_defaults(func=_cmd_soft_hard)

    traj_parser = subcommands.add_parser(
        "trajectory",
        help="Analyze hidden-state trajectory drift.",
    )
    traj_parser.add_argument("--states", type=Path, required=True, help=".npz with array `states`.")
    traj_parser.add_argument("--out", type=Path, required=True, help="Diagnostics directory.")
    traj_parser.add_argument("--tail", type=int, default=3)
    traj_parser.add_argument("--explain-level", choices=["plain", "technical"], default=None)
    traj_parser.set_defaults(func=_cmd_trajectory)

    riccati_parser = subcommands.add_parser("riccati", help="Analyze Riccati surrogate stability.")
    riccati_parser.add_argument("--matrices", type=Path, default=None, help=".npz with A/B/Q/R.")
    riccati_parser.add_argument("--trajectory", type=Path, default=None, help=".npz with states.")
    riccati_parser.add_argument("--out", type=Path, required=True, help="Diagnostics directory.")
    riccati_parser.add_argument("--iterations", type=int, default=200)
    riccati_parser.add_argument("--explain-level", choices=["plain", "technical"], default=None)
    riccati_parser.set_defaults(func=_cmd_riccati)

    tv_parser = subcommands.add_parser("tv-soft", help="Summarize time-varying soft-control lane.")
    tv_parser.add_argument(
        "--predictions",
        type=Path,
        required=True,
        help="Scored predictions JSONL.",
    )
    tv_parser.add_argument("--out", type=Path, required=True, help="Diagnostics directory.")
    tv_parser.add_argument("--baseline-method", default="static")
    tv_parser.add_argument("--explain-level", choices=["plain", "technical"], default=None)
    tv_parser.set_defaults(func=_cmd_tv_soft)
    return parser


def _cmd_init(args: argparse.Namespace) -> None:
    write_example_project(args.path)
    print(f"Created PromptControlLab example at {args.path}")


def _cmd_analyze(args: argparse.Namespace) -> None:
    config = load_analyze_config(args.config) if args.config is not None else {}
    paths = (
        resolve_analyze_paths(config, config_path=args.config) if args.config is not None else {}
    )
    data_path = _path_arg(args.data, paths.get("data"), "data")
    baseline_path = _path_arg(
        args.baseline_predictions,
        paths.get("baseline_predictions"),
        "baseline-predictions",
    )
    candidate_path = _path_arg(
        args.candidate_predictions,
        paths.get("candidate_predictions"),
        "candidate-predictions",
    )
    config_out = None
    if args.config is not None:
        config_out = get_config_path(config, "out", base_dir=args.config.parent)
    out_dir = _path_arg(args.out, config_out, "out")
    policy_path = args.policy if args.policy is not None else paths.get("gate_policy")
    metric = args.metric if args.metric is not None else config_metric(config, "exact_match")
    train_ratio = (
        args.train_ratio
        if args.train_ratio is not None
        else get_config_float(config, "train_ratio", 0.5)
    )
    val_ratio = (
        args.val_ratio
        if args.val_ratio is not None
        else get_config_float(config, "val_ratio", 0.25)
    )
    seed = args.seed if args.seed is not None else get_config_int(config, "seed", 0)
    bootstrap_samples = (
        args.bootstrap_samples
        if args.bootstrap_samples is not None
        else get_config_int(config, "bootstrap_samples", 1000)
    )
    permutation_samples = (
        args.permutation_samples
        if args.permutation_samples is not None
        else get_config_int(config, "permutation_samples", 1000)
    )
    explain_level = (
        args.explain_level
        if args.explain_level is not None
        else get_config_str(config, "explain_level", "plain")
    )
    title = (
        args.title
        if args.title is not None
        else get_config_str(config, "title", "PromptControlLab Quick Analysis")
    )
    run_quick_analysis(
        data_path=data_path,
        baseline_predictions_path=baseline_path,
        candidate_predictions_path=candidate_path,
        out_dir=out_dir,
        metric=metric,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        seed=seed,
        bootstrap_samples=bootstrap_samples,
        permutation_samples=permutation_samples,
        explain_level=explain_level,
        title=title,
        policy_path=policy_path,
    )
    print(f"Wrote quick analysis artifacts to {out_dir}")


def _cmd_split(args: argparse.Namespace) -> None:
    tasks = load_tasks(args.data)
    split = make_split(
        tasks,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        seed=args.seed,
    )
    write_split(args.out / "splits.json", split)
    print(f"Wrote split manifest to {args.out / 'splits.json'}")


def _cmd_eval(args: argparse.Namespace) -> None:
    run_import_eval(
        data_path=args.data,
        predictions_path=args.predictions,
        out_dir=args.out,
        metric=args.metric,
        method=args.method,
    )
    print(f"Wrote scored predictions and metrics to {args.out}")


def _cmd_stats(args: argparse.Namespace) -> None:
    compare_prediction_files(
        baseline_path=args.baseline,
        candidate_path=args.candidate,
        out_path=args.out,
        seed=args.seed,
        bootstrap_samples=args.bootstrap_samples,
        permutation_samples=args.permutation_samples,
    )
    print(f"Wrote statistical comparison to {args.out}")


def _cmd_report(args: argparse.Namespace) -> None:
    md_path, html_path = generate_report(args.run, title=args.title)
    print(f"Wrote reports to {md_path} and {html_path}")


def _cmd_explain(args: argparse.Namespace) -> None:
    generate_explanation(args.run, level=args.level)
    print(f"Wrote explanation to {args.run / 'explanation.json'}")


def _cmd_gate(args: argparse.Namespace) -> None:
    run_gate(args.run, policy_path=args.policy)
    print(f"Wrote gate result to {args.run / 'gate_result.json'}")


def _cmd_soft_hard(args: argparse.Namespace) -> None:
    analyze_soft_hard(soft_path=args.soft, vocab_path=args.vocab, out_dir=args.out)
    _maybe_refresh_explanation(args.out, args.explain_level)
    print(f"Wrote soft-hard diagnostics to {args.out}")


def _cmd_trajectory(args: argparse.Namespace) -> None:
    analyze_trajectory(states_path=args.states, out_dir=args.out, tail=args.tail)
    _maybe_refresh_explanation(args.out, args.explain_level)
    print(f"Wrote trajectory diagnostics to {args.out}")


def _cmd_riccati(args: argparse.Namespace) -> None:
    analyze_riccati(
        matrices_path=args.matrices,
        trajectory_path=args.trajectory,
        out_dir=args.out,
        iterations=args.iterations,
    )
    _maybe_refresh_explanation(args.out, args.explain_level)
    print(f"Wrote Riccati diagnostics to {args.out}")


def _cmd_tv_soft(args: argparse.Namespace) -> None:
    summarize_tv_soft(
        predictions_path=args.predictions,
        out_dir=args.out,
        baseline_method=args.baseline_method,
    )
    _maybe_refresh_explanation(args.out, args.explain_level)
    print(f"Wrote time-varying soft-control summary to {args.out}")


def _path_arg(value: Path | None, config_value: Path | None, name: str) -> Path:
    path = value if value is not None else config_value
    if path is None:
        msg = f"Missing required --{name} argument or config key"
        raise ValueError(msg)
    return path


def _maybe_refresh_explanation(out_dir: Path, level: str | None) -> None:
    if level is None:
        return
    run_dir = out_dir.parent if out_dir.name == "diagnostics" else out_dir
    generate_explanation(run_dir, level=level)
