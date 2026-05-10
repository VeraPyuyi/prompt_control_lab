"""Command line interface for PromptControlLab."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from promptcontrollab.errors import PromptControlLabError
from promptcontrollab.evaluation import run_import_eval
from promptcontrollab.reporting import generate_report
from promptcontrollab.riccati import analyze_riccati
from promptcontrollab.soft_hard import analyze_soft_hard
from promptcontrollab.splitting import load_tasks, make_split, write_split
from promptcontrollab.statistics import compare_prediction_files
from promptcontrollab.templates import write_example_project
from promptcontrollab.trajectory import analyze_trajectory
from promptcontrollab.tv_soft import summarize_tv_soft


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

    soft_parser = subcommands.add_parser("soft-hard", help="Analyze soft-to-hard projection risk.")
    soft_parser.add_argument("--soft", type=Path, required=True, help=".npz with array `soft`.")
    soft_parser.add_argument(
        "--vocab",
        type=Path,
        required=True,
        help=".npz with array `embeddings`.",
    )
    soft_parser.add_argument("--out", type=Path, required=True, help="Diagnostics directory.")
    soft_parser.set_defaults(func=_cmd_soft_hard)

    traj_parser = subcommands.add_parser(
        "trajectory",
        help="Analyze hidden-state trajectory drift.",
    )
    traj_parser.add_argument("--states", type=Path, required=True, help=".npz with array `states`.")
    traj_parser.add_argument("--out", type=Path, required=True, help="Diagnostics directory.")
    traj_parser.add_argument("--tail", type=int, default=3)
    traj_parser.set_defaults(func=_cmd_trajectory)

    riccati_parser = subcommands.add_parser("riccati", help="Analyze Riccati surrogate stability.")
    riccati_parser.add_argument("--matrices", type=Path, default=None, help=".npz with A/B/Q/R.")
    riccati_parser.add_argument("--trajectory", type=Path, default=None, help=".npz with states.")
    riccati_parser.add_argument("--out", type=Path, required=True, help="Diagnostics directory.")
    riccati_parser.add_argument("--iterations", type=int, default=200)
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
    tv_parser.set_defaults(func=_cmd_tv_soft)
    return parser


def _cmd_init(args: argparse.Namespace) -> None:
    write_example_project(args.path)
    print(f"Created PromptControlLab example at {args.path}")


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


def _cmd_soft_hard(args: argparse.Namespace) -> None:
    analyze_soft_hard(soft_path=args.soft, vocab_path=args.vocab, out_dir=args.out)
    print(f"Wrote soft-hard diagnostics to {args.out}")


def _cmd_trajectory(args: argparse.Namespace) -> None:
    analyze_trajectory(states_path=args.states, out_dir=args.out, tail=args.tail)
    print(f"Wrote trajectory diagnostics to {args.out}")


def _cmd_riccati(args: argparse.Namespace) -> None:
    analyze_riccati(
        matrices_path=args.matrices,
        trajectory_path=args.trajectory,
        out_dir=args.out,
        iterations=args.iterations,
    )
    print(f"Wrote Riccati diagnostics to {args.out}")


def _cmd_tv_soft(args: argparse.Namespace) -> None:
    summarize_tv_soft(
        predictions_path=args.predictions,
        out_dir=args.out,
        baseline_method=args.baseline_method,
    )
    print(f"Wrote time-varying soft-control summary to {args.out}")
