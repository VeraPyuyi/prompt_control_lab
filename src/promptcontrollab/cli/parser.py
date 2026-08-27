"""Top-level parser composition for the PromptControlLab CLI."""

from __future__ import annotations

import argparse

from promptcontrollab.cli.commands import (
    audit,
    control,
    diagnostics,
    evaluation,
    evidence,
    integrations,
    preflight,
    provenance,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the complete CLI parser without changing legacy ordering."""

    parser = argparse.ArgumentParser(
        prog="pcl",
        description=(
            "PromptControlLab local control, attribution, and stability diagnostics "
            "for prompts and AI agents."
        ),
        epilog=(
            "Start here: `pcl start --guide`, `pcl quickstart --out demo --open-report`, "
            'or `pcl choose --need "<your goal>"`.'
        ),
    )
    subcommands = parser.add_subparsers(dest="command", metavar="command", required=True)
    preflight.register_commands(subcommands, ("start", "quickstart", "choose", "init"))
    evidence.register_commands(subcommands, ("ingest",))
    preflight.register_commands(subcommands, ("scaffold-check", "improve"))
    control.register_commands(subcommands, ("control",))
    integrations.register_commands(subcommands, ("providers", "harness"))
    control.register_commands(subcommands, ("bridge",))
    preflight.register_commands(subcommands, ("guard",))
    provenance.register_commands(subcommands, ("model-detect", "model-drift"))
    evaluation.register_commands(subcommands, ("validity", "compare-runs"))
    evidence.register_commands(
        subcommands,
        ("evidence-from", "evidence-audit", "source-verify", "evidence-gate"),
    )
    integrations.register_commands(subcommands, ("ecosystem-demo", "ecosystem-scorecard"))
    audit.register_commands(subcommands, ("audit-diff",))
    evaluation.register_commands(subcommands, ("history",))
    audit.register_commands(subcommands, ("agent-run", "pr-summary", "github-app"))
    integrations.register_commands(subcommands, ("install-plugin", "doctor", "ui"))
    evaluation.register_commands(subcommands, ("export-report",))
    evidence.register_commands(
        subcommands,
        (
            "evidence",
            "posttrain-gate",
            "posttrain-pilot",
            "posttrain-pilot-export",
            "posttrain-model-provenance",
            "posttrain-pilot-prepare",
            "research-import",
        ),
    )
    diagnostics.register_commands(
        subcommands,
        (
            "research-demo",
            "research-quickstart",
            "research-bundle",
            "terminal-sensitivity",
            "green-certificate",
            "posterior-certificate",
            "diagnose",
            "gap-status",
            "extract-hidden",
        ),
    )
    evaluation.register_commands(subcommands, ("analyze", "split", "eval", "stats", "report"))
    evidence.register_commands(subcommands, ("evidence-card",))
    audit.register_commands(subcommands, ("claim-check",))
    evaluation.register_commands(subcommands, ("explain", "gate"))
    diagnostics.register_commands(subcommands, ("soft-hard", "trajectory", "riccati", "tv-soft"))
    return parser
