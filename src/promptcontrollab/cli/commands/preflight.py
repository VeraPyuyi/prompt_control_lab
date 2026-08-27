"""Preflight command parser registration."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from promptcontrollab.cli.handlers.preflight import (
    _cmd_choose,
    _cmd_guard,
    _cmd_improve,
    _cmd_init,
    _cmd_quickstart,
    _cmd_scaffold_check,
    _cmd_start,
)


def _register_start(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``start`` command parser."""
    start_parser = subcommands.add_parser(
        "start",
        help="Beginner mode: choose a scenario and get guided output.",
    )
    start_parser.add_argument(
        "--choice",
        choices=[
            "demo",
            "research",
            "choose",
            "ecosystem",
            "import",
            "evidence",
            "plugins",
            "improve",
            "guard",
            "analyze",
        ],
        default=None,
        help="Skip the menu and choose a beginner scenario.",
    )
    start_parser.add_argument(
        "--guide",
        action="store_true",
        help="Print a goal-based beginner guide and exit.",
    )
    start_parser.add_argument(
        "--language",
        choices=["en", "zh"],
        default="en",
        help="Language for beginner guide and menu text.",
    )
    start_parser.add_argument("--prompt", default=None, help="Prompt string for improve/guard.")
    start_parser.add_argument("--prompt-file", type=Path, default=None, help="Prompt text file.")
    start_parser.add_argument(
        "--need",
        default=None,
        help="Free-text need used when choice is choose.",
    )
    start_parser.add_argument("--run", type=Path, default=None, help="Optional run directory.")
    start_parser.add_argument("--out", type=Path, default=None, help="Optional output directory.")
    start_parser.add_argument("--policy", type=Path, default=None, help="Optional guard policy.")
    start_parser.add_argument(
        "--profile",
        choices=["general", "coding", "research"],
        default="coding",
        help="Prompt profile used when choice is guard.",
    )
    start_parser.add_argument(
        "--token-mode",
        choices=["balanced", "aggressive"],
        default="balanced",
        help="Token-cost mode used for prompt rewriting.",
    )
    start_parser.add_argument("--max-tokens", type=int, default=None)
    start_parser.add_argument("--config", type=Path, default=None, help="Config for analyze mode.")
    start_parser.add_argument(
        "--tool",
        choices=["auto", "promptfoo", "langfuse", "langsmith", "deepeval", "prompt-optimizer"],
        default="auto",
        help="External tool used when choice is import.",
    )
    start_parser.add_argument("--input", type=Path, default=None, help="External export file.")
    start_parser.add_argument("--prompt-id", default=None, help="Promptfoo prompt filter.")
    start_parser.add_argument("--name", default=None, help="Langfuse observation name filter.")
    start_parser.add_argument("--experiment", default=None, help="LangSmith experiment filter.")
    start_parser.add_argument("--score-name", default=None, help="External score/metric filter.")
    start_parser.add_argument("--model", default=None, help="External model id filter.")
    start_parser.add_argument("--provider", default=None, help="External provider filter.")
    start_parser.add_argument("--method", default=None, help="Method name written to predictions.")
    start_parser.add_argument("--asset-id", default=None, help="prompt-optimizer asset id filter.")
    start_parser.add_argument("--seed", type=int, default=0, help="Synthetic fixture seed.")
    start_parser.add_argument(
        "--open-report",
        action="store_true",
        help="Open the generated demo report in the default browser.",
    )
    start_parser.set_defaults(func=_cmd_start)


def _register_quickstart(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``quickstart`` command parser."""
    quickstart_parser = subcommands.add_parser(
        "quickstart",
        help="Create a runnable demo project and quick report.",
    )
    quickstart_parser.add_argument(
        "--out",
        type=Path,
        default=Path("demo"),
        help="Demo project directory.",
    )
    quickstart_parser.add_argument(
        "--language",
        choices=["en", "zh"],
        default="en",
        help="Output language.",
    )
    quickstart_parser.add_argument("--seed", type=int, default=0, help="Synthetic fixture seed.")
    quickstart_parser.add_argument(
        "--open-report",
        action="store_true",
        help="Open the generated report in the default browser.",
    )
    quickstart_parser.set_defaults(func=_cmd_quickstart)


def _register_choose(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``choose`` command parser."""
    choose_parser = subcommands.add_parser(
        "choose",
        help="Choose which adjacent tool to use first, and where PCL adds evidence.",
    )
    choose_parser.add_argument(
        "--need",
        default=None,
        help=(
            "Free-text need, such as security, prompt writing, observability, "
            "unit tests, or research evidence."
        ),
    )
    choose_parser.add_argument("--language", choices=["auto", "en", "zh"], default="auto")
    choose_parser.add_argument("--json", action="store_true")
    choose_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write tool-choice JSON plus a sibling Markdown summary.",
    )
    choose_parser.set_defaults(func=_cmd_choose)


def _register_init(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``init`` command parser."""
    init_parser = subcommands.add_parser("init", help="Create an example project.")
    init_parser.add_argument("--path", type=Path, default=Path("."), help="Project directory.")
    init_parser.set_defaults(func=_cmd_init)


def _register_scaffold_check(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``scaffold-check`` command parser."""
    scaffold_check_parser = subcommands.add_parser(
        "scaffold-check",
        help="Check whether a generated eval scaffold is ready for paired scoring.",
    )
    scaffold_source = scaffold_check_parser.add_mutually_exclusive_group(required=True)
    scaffold_source.add_argument(
        "--run",
        type=Path,
        help="Run directory containing eval_scaffold/.",
    )
    scaffold_source.add_argument(
        "--scaffold",
        type=Path,
        help="Path to an eval_scaffold directory.",
    )
    scaffold_check_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional JSON output path. Defaults to <eval_scaffold>/scaffold_check.json.",
    )
    scaffold_check_parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero unless the scaffold status is pass.",
    )
    scaffold_check_parser.set_defaults(func=_cmd_scaffold_check)


def _register_improve(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``improve`` command parser."""
    improve_parser = subcommands.add_parser(
        "improve",
        help="Improve one prompt with simple offline rules.",
    )
    improve_parser.add_argument("--prompt", default=None, help="Prompt string to improve.")
    improve_parser.add_argument("--prompt-file", type=Path, default=None, help="Prompt text file.")
    improve_parser.add_argument("--run", type=Path, default=None, help="Optional run directory.")
    improve_parser.add_argument("--out", type=Path, default=None, help="Optional output directory.")
    improve_parser.add_argument(
        "--goal",
        default="stability",
        help="accuracy, format, or stability.",
    )
    improve_parser.add_argument("--language", choices=["auto", "zh", "en"], default="auto")
    improve_parser.add_argument("--style", choices=["simple", "strict", "stable"], default="stable")
    improve_parser.add_argument(
        "--token-mode",
        choices=["balanced", "aggressive"],
        default="balanced",
        help="Token-cost mode. Balanced preserves key constraints; aggressive is shorter.",
    )
    improve_parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Optional estimated-token budget for the rewritten prompt.",
    )
    improve_parser.set_defaults(func=_cmd_improve)


def _register_guard(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``guard`` command parser."""
    guard_parser = subcommands.add_parser(
        "guard",
        help="Guard and improve one prompt before an IDE or CLI agent uses it.",
    )
    guard_parser.add_argument("--prompt", default=None, help="Prompt string to guard.")
    guard_parser.add_argument("--prompt-file", type=Path, default=None, help="Prompt text file.")
    guard_parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read prompt text from stdin. Useful for hooks and wrappers.",
    )
    guard_parser.add_argument("--run", type=Path, default=None, help="Optional run directory.")
    guard_parser.add_argument(
        "--policy",
        type=Path,
        default=None,
        help="Optional guard policy YAML.",
    )
    guard_parser.add_argument(
        "--mode",
        choices=["suggest", "auto", "gate"],
        default="suggest",
        help="suggest returns a recommendation, auto marks it auto-usable, gate can block.",
    )
    guard_parser.add_argument(
        "--profile",
        choices=["general", "coding", "research"],
        default="general",
        help="Prompt profile for context-specific guardrails.",
    )
    guard_parser.add_argument("--language", choices=["auto", "zh", "en"], default="auto")
    guard_parser.add_argument(
        "--token-mode",
        choices=["balanced", "aggressive"],
        default="balanced",
        help="Token-cost mode passed to the prompt improver.",
    )
    guard_parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Optional estimated-token budget for the guarded prompt.",
    )
    guard_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit stable JSON for IDE hooks and wrappers.",
    )
    guard_parser.set_defaults(func=_cmd_guard)


_REGISTRARS = {
    "start": _register_start,
    "quickstart": _register_quickstart,
    "choose": _register_choose,
    "init": _register_init,
    "scaffold-check": _register_scaffold_check,
    "improve": _register_improve,
    "guard": _register_guard,
}


def register_commands(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    names: Sequence[str] | None = None,
) -> None:
    """Register selected preflight commands in the requested order."""

    selected = tuple(_REGISTRARS) if names is None else tuple(names)
    for name in selected:
        _REGISTRARS[name](subcommands)
