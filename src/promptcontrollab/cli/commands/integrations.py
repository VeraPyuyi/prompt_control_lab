"""Integrations command parser registration."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from promptcontrollab.cli.handlers.integrations import (
    _cmd_doctor,
    _cmd_ecosystem_demo,
    _cmd_ecosystem_scorecard,
    _cmd_harness_doctor,
    _cmd_harness_finalize,
    _cmd_harness_init,
    _cmd_harness_replay,
    _cmd_harness_report,
    _cmd_install_plugin,
    _cmd_providers_doctor,
    _cmd_providers_inspect,
    _cmd_providers_list,
    _cmd_ui,
)


def _register_providers(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``providers`` command parser."""
    providers_parser = subcommands.add_parser(
        "providers",
        help="Inspect and validate configured public model providers.",
    )
    providers_subcommands = providers_parser.add_subparsers(
        dest="providers_command",
        required=True,
    )
    providers_list_parser = providers_subcommands.add_parser(
        "list",
        help="List supported provider adapters.",
    )
    providers_list_parser.add_argument("--json", action="store_true", help="Emit stable JSON.")
    providers_list_parser.set_defaults(func=_cmd_providers_list)
    providers_inspect_parser = providers_subcommands.add_parser(
        "inspect",
        help="Inspect local provider configuration without network access.",
    )
    providers_inspect_parser.add_argument("provider")
    providers_inspect_parser.add_argument("--base-url", default=None)
    providers_inspect_parser.add_argument("--api-key-env", default=None)
    providers_inspect_parser.add_argument("--json", action="store_true", help="Emit stable JSON.")
    providers_inspect_parser.set_defaults(func=_cmd_providers_inspect)
    providers_doctor_parser = providers_subcommands.add_parser(
        "doctor",
        help="Check provider configuration offline unless --live is explicit.",
    )
    providers_doctor_parser.add_argument("provider")
    providers_doctor_parser.add_argument("--live", action="store_true")
    providers_doctor_parser.add_argument("--model", default=None)
    providers_doctor_parser.add_argument("--base-url", default=None)
    providers_doctor_parser.add_argument("--api-key-env", default=None)
    providers_doctor_parser.add_argument("--timeout", type=float, default=10.0)
    providers_doctor_parser.add_argument("--json", action="store_true", help="Emit stable JSON.")
    providers_doctor_parser.set_defaults(func=_cmd_providers_doctor)


def _register_harness(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``harness`` command parser."""
    harness_parser = subcommands.add_parser(
        "harness",
        help="Initialize, inspect, replay, and report DeepSeek Harness sessions.",
    )
    harness_subcommands = harness_parser.add_subparsers(dest="harness_command", required=True)
    harness_init_parser = harness_subcommands.add_parser(
        "init",
        help="Write reviewable local Harness integration files.",
    )
    harness_init_parser.add_argument("--project", type=Path, default=Path.cwd())
    harness_init_parser.add_argument("--force", action="store_true")
    harness_init_parser.add_argument("--json", action="store_true", help="Emit stable JSON.")
    harness_init_parser.set_defaults(func=_cmd_harness_init)
    harness_doctor_parser = harness_subcommands.add_parser(
        "doctor",
        help="Check the local Harness integration without network access.",
    )
    harness_doctor_parser.add_argument("--project", type=Path, default=Path.cwd())
    harness_doctor_parser.add_argument("--json", action="store_true", help="Emit stable JSON.")
    harness_doctor_parser.set_defaults(func=_cmd_harness_doctor)
    harness_replay_parser = harness_subcommands.add_parser(
        "replay",
        help="Replay an existing Harness JSONL session into a control run.",
    )
    harness_replay_parser.add_argument("--session", type=Path, required=True)
    harness_replay_parser.add_argument("--out", type=Path, required=True)
    harness_replay_parser.add_argument("--policy", type=Path, default=None)
    harness_replay_parser.add_argument(
        "--authorization",
        choices=["agent-scoped", "agent-full"],
        default="agent-scoped",
    )
    harness_replay_parser.add_argument("--json", action="store_true", help="Emit stable JSON.")
    harness_replay_parser.set_defaults(func=_cmd_harness_replay)
    harness_finalize_parser = harness_subcommands.add_parser(
        "finalize",
        help="Explicitly close a Harness control run after the external process exits.",
    )
    harness_finalize_parser.add_argument("--runs", type=Path, required=True)
    harness_finalize_parser.add_argument("--session", required=True)
    harness_finalize_parser.add_argument(
        "--outcome",
        choices=["completed", "failed", "cancelled"],
        default="completed",
    )
    harness_finalize_parser.add_argument("--exit-code", type=int, default=None)
    harness_finalize_parser.add_argument("--json", action="store_true", help="Emit stable JSON.")
    harness_finalize_parser.set_defaults(func=_cmd_harness_finalize)
    harness_report_parser = harness_subcommands.add_parser(
        "report",
        help="Resolve an existing Harness control report.",
    )
    harness_report_parser.add_argument("--runs", type=Path, required=True)
    harness_report_parser.add_argument("--session", required=True)
    harness_report_parser.add_argument("--json", action="store_true", help="Emit stable JSON.")
    harness_report_parser.set_defaults(func=_cmd_harness_report)


def _register_ecosystem_demo(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``ecosystem-demo`` command parser."""
    ecosystem_demo_parser = subcommands.add_parser(
        "ecosystem-demo",
        help="Run bundled Promptfoo/DeepEval/Langfuse/LangSmith bridge examples.",
    )
    ecosystem_demo_parser.add_argument(
        "--examples",
        type=Path,
        default=Path("examples/external"),
        help="Directory containing external export examples.",
    )
    ecosystem_demo_parser.add_argument(
        "--out",
        type=Path,
        default=Path("runs/ecosystem-demo"),
        help="Output directory for all bridge bundles.",
    )
    ecosystem_demo_parser.add_argument(
        "--split-hash",
        default="external-demo-split",
        help="Stable split hash recorded into imported manifests.",
    )
    ecosystem_demo_parser.add_argument("--provider", default="openai")
    ecosystem_demo_parser.add_argument("--model", default="gpt-4o-mini-20260601")
    ecosystem_demo_parser.add_argument("--bootstrap-samples", type=int, default=1000)
    ecosystem_demo_parser.add_argument("--permutation-samples", type=int, default=1000)
    ecosystem_demo_parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a concise market-readiness summary instead of the full JSON payload.",
    )
    ecosystem_demo_parser.set_defaults(func=_cmd_ecosystem_demo)


def _register_ecosystem_scorecard(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``ecosystem-scorecard`` command parser."""
    ecosystem_scorecard_parser = subcommands.add_parser(
        "ecosystem-scorecard",
        help="Regenerate ecosystem_scorecard.json/md/html for an ecosystem bridge run.",
    )
    ecosystem_scorecard_parser.add_argument(
        "--run",
        type=Path,
        required=True,
        help="Existing ecosystem demo run directory.",
    )
    ecosystem_scorecard_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=("Output JSON file or output directory. Defaults to <run>/ecosystem_scorecard.json."),
    )
    ecosystem_scorecard_parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a concise market-readiness summary instead of the full JSON payload.",
    )
    ecosystem_scorecard_parser.set_defaults(func=_cmd_ecosystem_scorecard)


def _register_install_plugin(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``install-plugin`` command parser."""
    install_parser = subcommands.add_parser(
        "install-plugin",
        help="Install local IDE/CLI integration templates.",
    )
    install_parser.add_argument(
        "plugin",
        choices=[
            "codex",
            "cursor",
            "claude-code",
            "github-action",
            "deepseek-harness",
            "all",
        ],
    )
    install_parser.add_argument("--target", type=Path, default=None, help="Override install path.")
    install_parser.add_argument("--force", action="store_true", help="Overwrite existing files.")
    install_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview target files without writing templates.",
    )
    install_parser.set_defaults(func=_cmd_install_plugin)


def _register_doctor(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``doctor`` command parser."""
    doctor_parser = subcommands.add_parser("doctor", help="Check local setup and integrations.")
    doctor_parser.add_argument("--json", action="store_true", help="Emit stable JSON.")
    doctor_parser.set_defaults(func=_cmd_doctor)


def _register_ui(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``ui`` command parser."""
    ui_parser = subcommands.add_parser("ui", help="Launch the local workflow cockpit.")
    ui_parser.add_argument("--runs", type=Path, default=None, help="Runs directory.")
    ui_parser.add_argument("--policy", type=Path, default=None, help="Optional guard policy.")
    ui_parser.add_argument("--host", default="localhost", help="Host address.")
    ui_parser.add_argument("--port", type=int, default=8501, help="Port number.")
    ui_parser.add_argument("--language", choices=["en", "zh"], default="en")
    ui_parser.add_argument("--no-browser", action="store_true", help="Do not open a browser.")
    ui_parser.add_argument(
        "--legacy-streamlit",
        action="store_true",
        help="Launch the compatibility Streamlit dashboard instead of the React cockpit.",
    )
    ui_parser.set_defaults(func=_cmd_ui)


_REGISTRARS = {
    "providers": _register_providers,
    "harness": _register_harness,
    "ecosystem-demo": _register_ecosystem_demo,
    "ecosystem-scorecard": _register_ecosystem_scorecard,
    "install-plugin": _register_install_plugin,
    "doctor": _register_doctor,
    "ui": _register_ui,
}


def register_commands(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    names: Sequence[str] | None = None,
) -> None:
    """Register selected integrations commands in the requested order."""

    selected = tuple(_REGISTRARS) if names is None else tuple(names)
    for name in selected:
        _REGISTRARS[name](subcommands)
