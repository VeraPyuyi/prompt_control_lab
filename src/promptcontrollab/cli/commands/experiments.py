"""Unified experiment and research tool entry points."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def register_commands(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register typed experiment execution, management and offline research commands."""
    experiment = subcommands.add_parser("experiment", help="Evaluate, import, or optimize prompts")
    actions = experiment.add_subparsers(dest="action", required=True)
    for action in ("run", "import", "optimize"):
        parser = actions.add_parser(action)
        source = parser.add_mutually_exclusive_group(required=True)
        source.add_argument("--config", type=Path)
        if action == "import":
            source.add_argument(
                "--example", action="store_true", help="Run the packaged offline example"
            )
        parser.add_argument("--runs", type=Path, default=Path("runs"))
        parser.set_defaults(func=_execute)
    for action in ("status", "cancel", "resume"):
        parser = actions.add_parser(action)
        parser.add_argument("id", nargs="?" if action == "status" else None)
        if action == "resume":
            parser.add_argument(
                "--retry-failed",
                action="store_true",
                help="Retry explicitly rejected requests; uncertain requests are never replayed",
            )
        parser.add_argument("--runs", type=Path, default=Path("runs"))
        parser.set_defaults(func=_manage)
    replay = actions.add_parser(
        "replay", help="Recompute an exported experiment without model calls"
    )
    replay.add_argument("--bundle", type=Path, required=True)
    replay.add_argument("--out", type=Path, required=True)
    replay.set_defaults(func=_replay)
    research = subcommands.add_parser(
        "research", help="Readout, response, cost, transfer, and replay tools"
    )
    tools = research.add_subparsers(dest="research_kind", required=True)
    for kind in ("readout", "response", "measurement-value", "transfer", "replay"):
        parser = tools.add_parser(kind)
        parser.add_argument("--input", type=Path, required=True)
        parser.add_argument("--out", type=Path, required=True)
        parser.set_defaults(func=_research)


def _execute(args: argparse.Namespace) -> None:
    from promptcontrollab.evaluation.experiments import create_experiment, run_experiment

    if getattr(args, "example", False):
        from importlib.resources import files

        packaged = files("promptcontrollab").joinpath("example_data").joinpath("experiments")
        sample = packaged.joinpath("synthetic-import.json")
        if not sample.is_file():
            sample = (
                Path(__file__).resolve().parents[4] / "examples/experiments/synthetic-import.json"
            )
        spec = json.loads(sample.read_text(encoding="utf-8-sig"))
    else:
        spec = json.loads(args.config.read_text(encoding="utf-8-sig"))
    spec["operation"] = args.action
    if isinstance(spec.get("data"), str):
        from promptcontrollab.integrations.experiment_inputs import parse_dataset

        data_path = (args.config.parent / spec["data"]).resolve()
        spec["data"] = parse_dataset(
            data_path.read_text(encoding="utf-8-sig"), data_path.suffix.lstrip(".")
        )
    job = create_experiment(args.runs, spec)
    result = run_experiment(args.runs, job["id"])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] not in {"completed"}:
        raise SystemExit(1)


def _manage(args: argparse.Namespace) -> None:
    from promptcontrollab.evaluation.experiments import (
        cancel_experiment,
        get_experiment,
        list_experiments,
        prepare_resume,
        run_experiment,
    )

    result: object
    if args.action == "cancel":
        result = cancel_experiment(args.runs, args.id)
    elif args.action == "resume":
        prepare_resume(args.runs, args.id, retry_failed=args.retry_failed)
        result = run_experiment(args.runs, args.id)
    else:
        result = get_experiment(args.runs, args.id) if args.id else list_experiments(args.runs)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _research(args: argparse.Namespace) -> None:
    from promptcontrollab.diagnostics.research_tools import analyze_research

    document = json.loads(args.input.read_text(encoding="utf-8-sig"))
    result = analyze_research(args.research_kind, document, args.out)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _replay(args: argparse.Namespace) -> None:
    from promptcontrollab.evaluation.experiments.replay import replay_experiment

    print(json.dumps(replay_experiment(args.bundle, args.out), ensure_ascii=False, indent=2))
