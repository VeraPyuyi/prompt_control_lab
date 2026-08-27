"""Diagnostics command parser registration."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from promptcontrollab.cli.handlers.diagnostics import (
    _cmd_diagnose,
    _cmd_extract_hidden,
    _cmd_gap_status,
    _cmd_green_certificate,
    _cmd_posterior_certificate,
    _cmd_research_bundle,
    _cmd_research_demo,
    _cmd_research_quickstart,
    _cmd_riccati,
    _cmd_soft_hard,
    _cmd_terminal_sensitivity,
    _cmd_trajectory,
    _cmd_tv_soft,
)


def _register_research_demo(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``research-demo`` command parser."""
    research_demo_parser = subcommands.add_parser(
        "research-demo",
        help="Create a synthetic paper-style demo and run all research diagnostics.",
    )
    research_demo_parser.add_argument("--out", type=Path, required=True, help="Demo run directory.")
    research_demo_parser.add_argument("--seed", type=int, default=0, help="Synthetic fixture seed.")
    research_demo_parser.add_argument("--language", choices=["en", "zh"], default="en")
    research_demo_parser.set_defaults(func=_cmd_research_demo)


def _register_research_quickstart(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``research-quickstart`` command parser."""
    research_quickstart_parser = subcommands.add_parser(
        "research-quickstart",
        help="Create a paper-style research demo, run diagnose, and optionally open the bundle.",
    )
    research_quickstart_parser.add_argument(
        "--out",
        type=Path,
        default=Path("runs") / "research-demo",
        help="Demo run directory.",
    )
    research_quickstart_parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Synthetic fixture seed.",
    )
    research_quickstart_parser.add_argument("--language", choices=["en", "zh"], default="en")
    research_quickstart_parser.add_argument(
        "--open-report",
        action="store_true",
        help="Open the generated research bundle in the default browser.",
    )
    research_quickstart_parser.set_defaults(func=_cmd_research_quickstart)


def _register_research_bundle(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``research-bundle`` command parser."""
    research_bundle_parser = subcommands.add_parser(
        "research-bundle",
        help="Refresh research_bundle.json/html for a run directory.",
    )
    research_bundle_parser.add_argument("--run", type=Path, required=True, help="Run directory.")
    research_bundle_parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify hashes in the existing bundle instead of refreshing it.",
    )
    research_bundle_parser.add_argument(
        "--strict",
        action="store_true",
        help="With --verify, return a non-zero exit code when bundle verification does not pass.",
    )
    research_bundle_parser.set_defaults(func=_cmd_research_bundle)


def _register_terminal_sensitivity(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``terminal-sensitivity`` command parser."""
    terminal_parser = subcommands.add_parser(
        "terminal-sensitivity",
        help="Measure early-control sensitivity to terminal objective or readout changes.",
    )
    terminal_source = terminal_parser.add_mutually_exclusive_group(required=True)
    terminal_source.add_argument(
        "--records",
        type=Path,
        help="JSONL intervention records.",
    )
    terminal_source.add_argument(
        "--surrogate",
        type=Path,
        help="NPZ low-dimensional boundary-value surrogate.",
    )
    terminal_parser.add_argument("--horizon", type=int, action="append", dest="horizons")
    terminal_parser.add_argument(
        "--early-step",
        type=int,
        action="append",
        dest="early_steps",
    )
    terminal_parser.add_argument("--bootstrap-samples", type=int, default=1000)
    terminal_parser.add_argument("--out", type=Path, required=True)
    terminal_parser.set_defaults(func=_cmd_terminal_sensitivity)


def _register_green_certificate(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``green-certificate`` command parser."""
    green_parser = subcommands.add_parser(
        "green-certificate",
        help="Check Green-response hyperbolicity and boundary transversality on a surrogate.",
    )
    green_parser.add_argument("--surrogate", type=Path, required=True)
    green_parser.add_argument(
        "--horizon",
        type=int,
        action="append",
        dest="horizons",
        required=True,
    )
    green_parser.add_argument(
        "--premises",
        type=Path,
        default=None,
        help="Optional conservative premise manifest for a scoped verified certificate.",
    )
    green_parser.add_argument("--out", type=Path, required=True)
    green_parser.set_defaults(func=_cmd_green_certificate)


def _register_posterior_certificate(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``posterior-certificate`` command parser."""
    posterior_parser = subcommands.add_parser(
        "posterior-certificate",
        help="Check local posterior existence conditions from conservative scalar bounds.",
    )
    posterior_parser.add_argument("--input", type=Path, required=True)
    posterior_parser.add_argument("--out", type=Path, required=True)
    posterior_parser.set_defaults(func=_cmd_posterior_certificate)


def _register_diagnose(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``diagnose`` command parser."""
    diagnose_parser = subcommands.add_parser(
        "diagnose",
        help="Run paper-derived soft-hard, trajectory, Riccati, and tv-soft diagnostics.",
    )
    diagnose_parser.add_argument("--run", type=Path, default=None, help="Run dir with inputs/.")
    diagnose_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Diagnostics output directory. Defaults to <run>/diagnostics.",
    )
    diagnose_parser.add_argument("--soft", type=Path, default=None, help=".npz with array `soft`.")
    diagnose_parser.add_argument(
        "--vocab",
        type=Path,
        default=None,
        help=".npz with array `embeddings`.",
    )
    diagnose_parser.add_argument(
        "--states",
        type=Path,
        default=None,
        help=".npz with array `states`.",
    )
    diagnose_parser.add_argument("--matrices", type=Path, default=None, help=".npz with A/B/Q/R.")
    diagnose_parser.add_argument(
        "--tv-predictions",
        type=Path,
        default=None,
        help="Scored predictions JSONL for tv-soft summary.",
    )
    diagnose_parser.add_argument("--baseline-method", default="static")
    diagnose_parser.add_argument("--tail", type=int, default=1)
    diagnose_parser.add_argument("--iterations", type=int, default=200)
    diagnose_parser.add_argument("--language", choices=["en", "zh"], default="en")
    diagnose_parser.set_defaults(func=_cmd_diagnose)


def _register_gap_status(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``gap-status`` command parser."""
    gap_status_parser = subcommands.add_parser(
        "gap-status",
        help="Check whether research_gap_plan actions have produced their expected artifacts.",
    )
    gap_status_parser.add_argument("--run", type=Path, required=True, help="Run directory.")
    gap_status_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output JSON file or directory. Defaults to <run>/research_gap_status.json.",
    )
    gap_status_parser.set_defaults(func=_cmd_gap_status)


def _register_extract_hidden(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``extract-hidden`` command parser."""
    hidden_parser = subcommands.add_parser(
        "extract-hidden",
        help="Extract HuggingFace hidden states into a trajectory-compatible .npz file.",
    )
    hidden_parser.add_argument("--model", required=True, help="HuggingFace model id or path.")
    hidden_parser.add_argument(
        "--prompts",
        type=Path,
        required=True,
        help="Prompt JSONL or text file.",
    )
    hidden_parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output .npz path containing array `states`.",
    )
    hidden_parser.add_argument("--layer", type=int, default=-1)
    hidden_parser.add_argument(
        "--pool",
        choices=["last-token", "mean", "token-trajectory"],
        default="last-token",
    )
    hidden_parser.add_argument("--max-items", type=int, default=None)
    hidden_parser.add_argument("--max-length", type=int, default=512)
    hidden_parser.add_argument("--device", default="auto")
    hidden_parser.add_argument("--trust-remote-code", action="store_true")
    hidden_parser.set_defaults(func=_cmd_extract_hidden)


def _register_soft_hard(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``soft-hard`` command parser."""
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


def _register_trajectory(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``trajectory`` command parser."""
    traj_parser = subcommands.add_parser(
        "trajectory",
        help="Analyze hidden-state trajectory drift.",
    )
    traj_parser.add_argument("--states", type=Path, required=True, help=".npz with array `states`.")
    traj_parser.add_argument("--out", type=Path, required=True, help="Diagnostics directory.")
    traj_parser.add_argument("--tail", type=int, default=3)
    traj_parser.add_argument("--explain-level", choices=["plain", "technical"], default=None)
    traj_parser.set_defaults(func=_cmd_trajectory)


def _register_riccati(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``riccati`` command parser."""
    riccati_parser = subcommands.add_parser("riccati", help="Analyze Riccati surrogate stability.")
    riccati_parser.add_argument("--matrices", type=Path, default=None, help=".npz with A/B/Q/R.")
    riccati_parser.add_argument("--trajectory", type=Path, default=None, help=".npz with states.")
    riccati_parser.add_argument("--out", type=Path, required=True, help="Diagnostics directory.")
    riccati_parser.add_argument("--iterations", type=int, default=200)
    riccati_parser.add_argument("--explain-level", choices=["plain", "technical"], default=None)
    riccati_parser.set_defaults(func=_cmd_riccati)


def _register_tv_soft(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``tv-soft`` command parser."""
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


_REGISTRARS = {
    "research-demo": _register_research_demo,
    "research-quickstart": _register_research_quickstart,
    "research-bundle": _register_research_bundle,
    "terminal-sensitivity": _register_terminal_sensitivity,
    "green-certificate": _register_green_certificate,
    "posterior-certificate": _register_posterior_certificate,
    "diagnose": _register_diagnose,
    "gap-status": _register_gap_status,
    "extract-hidden": _register_extract_hidden,
    "soft-hard": _register_soft_hard,
    "trajectory": _register_trajectory,
    "riccati": _register_riccati,
    "tv-soft": _register_tv_soft,
}


def register_commands(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    names: Sequence[str] | None = None,
) -> None:
    """Register selected diagnostics commands in the requested order."""

    selected = tuple(_REGISTRARS) if names is None else tuple(names)
    for name in selected:
        _REGISTRARS[name](subcommands)
