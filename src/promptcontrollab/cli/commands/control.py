"""Control command parser registration."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from promptcontrollab.cli.handlers.control import (
    _cmd_bridge_serve,
    _cmd_control,
)
from promptcontrollab.control.control_workflow import AUTHORIZATIONS


def _register_control(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``control`` command parser."""
    control_parser = subcommands.add_parser(
        "control",
        help="Run a local preflight control loop without implicit model or agent execution.",
    )
    control_parser.add_argument("--prompt", default=None, help="Prompt string to inspect.")
    control_parser.add_argument("--prompt-file", type=Path, default=None, help="Prompt text file.")
    control_parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read the prompt from stdin.",
    )
    control_parser.add_argument(
        "--authorization",
        choices=list(AUTHORIZATIONS),
        default=None,
        help="Explicit execution boundary. Required when stdin is not a TTY.",
    )
    control_parser.add_argument(
        "--out",
        type=Path,
        default=Path("runs") / "control",
        help="Control run directory.",
    )
    control_parser.add_argument("--run-id", default=None, help="Optional stable run id.")
    control_parser.add_argument("--provider", default=None, help="Declared provider metadata.")
    control_parser.add_argument("--model", default=None, help="Declared public model id.")
    control_parser.add_argument("--agent", default=None, help="Declared agent adapter id.")
    control_parser.add_argument("--policy", type=Path, default=None, help="Guard policy YAML.")
    control_parser.add_argument(
        "--profile",
        choices=["general", "coding", "research"],
        default="general",
    )
    control_parser.add_argument("--language", choices=["auto", "zh", "en"], default="auto")
    control_parser.add_argument(
        "--token-mode",
        choices=["balanced", "aggressive"],
        default="balanced",
    )
    control_parser.add_argument("--max-tokens", type=int, default=None)
    control_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the final status as JSON.",
    )
    control_parser.set_defaults(func=_cmd_control)


def _register_bridge(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``bridge`` command parser."""
    bridge_parser = subcommands.add_parser(
        "bridge",
        help="Serve the persistent local control protocol bridge.",
    )
    bridge_subcommands = bridge_parser.add_subparsers(dest="bridge_command", required=True)
    bridge_serve_parser = bridge_subcommands.add_parser(
        "serve",
        help="Serve line-delimited JSON-RPC requests.",
    )
    bridge_serve_parser.add_argument("--transport", choices=["stdio"], default="stdio")
    bridge_serve_parser.add_argument(
        "--runs-root",
        type=Path,
        default=Path("runs"),
        help="Default parent directory for bridge-created runs.",
    )
    bridge_serve_parser.set_defaults(func=_cmd_bridge_serve)


_REGISTRARS = {
    "control": _register_control,
    "bridge": _register_bridge,
}


def register_commands(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    names: Sequence[str] | None = None,
) -> None:
    """Register selected control commands in the requested order."""

    selected = tuple(_REGISTRARS) if names is None else tuple(names)
    for name in selected:
        _REGISTRARS[name](subcommands)
