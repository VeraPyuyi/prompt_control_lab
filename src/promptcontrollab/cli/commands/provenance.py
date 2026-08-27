"""Provenance command parser registration."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from promptcontrollab.cli.handlers.provenance import (
    _cmd_model_detect,
    _cmd_model_drift,
)


def _register_model_detect(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``model-detect`` command parser."""
    model_parser = subcommands.add_parser(
        "model-detect",
        help="Detect public model id from an API response, prediction file, or declared model.",
    )
    model_parser.add_argument("--response", type=Path, default=None, help="API response JSON file.")
    model_parser.add_argument(
        "--predictions",
        type=Path,
        default=None,
        help="Raw predictions JSONL with optional model/provider fields.",
    )
    model_parser.add_argument("--model", default=None, help="Declared model id, such as gpt-5.2.")
    model_parser.add_argument("--provider", default=None, help="Provider hint, such as openai.")
    model_parser.add_argument("--api-version", default=None, help="Optional API version string.")
    model_parser.add_argument("--request-id", default=None, help="Provider request id, if known.")
    model_parser.add_argument("--request-json", type=Path, default=None, help="Request JSON file.")
    model_parser.add_argument("--request-sha256", default=None, help="Precomputed request hash.")
    model_parser.add_argument("--response-sha256", default=None, help="Precomputed response hash.")
    model_parser.add_argument(
        "--provider-log-reference",
        default=None,
        help="Provider-side log or usage record reference.",
    )
    model_parser.add_argument(
        "--signed-receipt",
        default=None,
        help="Provider signed receipt id or digest, if available.",
    )
    model_parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify public model metadata when the provider exposes a supported endpoint.",
    )
    model_parser.add_argument("--out", type=Path, default=None, help="Optional JSON output path.")
    model_parser.set_defaults(func=_cmd_model_detect)


def _register_model_drift(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``model-drift`` command parser."""
    drift_parser = subcommands.add_parser(
        "model-drift",
        help="Compare model provenance between a current run and a previous run.",
    )
    drift_parser.add_argument("--run", type=Path, required=True, help="Current run directory.")
    drift_parser.add_argument("--history", type=Path, required=True, help="Previous run directory.")
    drift_parser.add_argument("--out", type=Path, required=True, help="model_drift.json output.")
    drift_parser.set_defaults(func=_cmd_model_drift)


_REGISTRARS = {
    "model-detect": _register_model_detect,
    "model-drift": _register_model_drift,
}


def register_commands(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    names: Sequence[str] | None = None,
) -> None:
    """Register selected provenance commands in the requested order."""

    selected = tuple(_REGISTRARS) if names is None else tuple(names)
    for name in selected:
        _REGISTRARS[name](subcommands)
