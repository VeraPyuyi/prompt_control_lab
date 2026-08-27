"""Audit command parser registration."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from promptcontrollab.cli.handlers.audit import (
    _cmd_agent_run_build,
    _cmd_audit_diff,
    _cmd_claim_check,
    _cmd_github_app_serve,
    _cmd_pr_summary,
)


def _register_audit_diff(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``audit-diff`` command parser."""
    audit_parser = subcommands.add_parser(
        "audit-diff",
        help="Audit what an AI coding agent changed between two git refs.",
    )
    audit_parser.add_argument("--repo", type=Path, default=Path("."), help="Git repository path.")
    audit_parser.add_argument("--before", required=True, help="Base git ref.")
    audit_parser.add_argument("--after", required=True, help="Head git ref.")
    audit_parser.add_argument("--out", type=Path, required=True, help="Audit output directory.")
    audit_parser.add_argument(
        "--expected-path",
        action="append",
        default=[],
        help="Expected changed path prefix. Repeat for multiple allowed scopes.",
    )
    audit_parser.add_argument(
        "--test-command",
        action="append",
        default=[],
        help=(
            "Test command to execute without shell syntax and record. Repeat for multiple commands."
        ),
    )
    audit_parser.add_argument(
        "--allow-shell-test-command",
        action="store_true",
        help="Allow --test-command to run through the shell. Use only with trusted input.",
    )
    audit_parser.add_argument(
        "--test-timeout",
        type=int,
        default=120,
        help="Timeout in seconds for each --test-command.",
    )
    audit_parser.add_argument(
        "--tests-run",
        action="append",
        default=[],
        help="Previously run test command to record without executing.",
    )
    audit_parser.add_argument(
        "--tests-passed",
        choices=["true", "false"],
        default=None,
        help="Whether externally run tests passed.",
    )
    audit_parser.add_argument(
        "--sarif",
        type=Path,
        default=None,
        help="Optional SARIF output path.",
    )
    audit_parser.add_argument(
        "--secret-scanner",
        choices=["builtin", "gitleaks", "trufflehog"],
        default="builtin",
        help=(
            "Secret scanner to use. builtin scans added diff lines; "
            "gitleaks/trufflehog scan the current workspace."
        ),
    )
    audit_parser.set_defaults(func=_cmd_audit_diff)


def _register_agent_run(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``agent-run`` command parser."""
    agent_parser = subcommands.add_parser("agent-run", help="Build agent run manifests.")
    agent_subcommands = agent_parser.add_subparsers(dest="agent_command", required=True)
    agent_build = agent_subcommands.add_parser("build", help="Build agent_run.json.")
    agent_build.add_argument("--run", type=Path, required=True, help="PromptControlLab run dir.")
    agent_build.add_argument("--audit", type=Path, default=None, help="Audit output directory.")
    agent_build.add_argument("--agent", required=True, help="Agent name, such as codex.")
    agent_build.add_argument("--out", type=Path, required=True, help="agent_run.json output path.")
    agent_build.add_argument("--policy", default=None, help="Policy path or id used for the run.")
    agent_build.set_defaults(func=_cmd_agent_run_build)


def _register_pr_summary(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``pr-summary`` command parser."""
    summary_parser = subcommands.add_parser("pr-summary", help="Build PR review summary artifacts.")
    summary_parser.add_argument("--audit", type=Path, default=None, help="audit_result.json path.")
    summary_parser.add_argument("--gate", type=Path, default=None, help="gate_result.json path.")
    summary_parser.add_argument(
        "--evidence-gate",
        type=Path,
        default=None,
        help="evidence_gate_result.json path.",
    )
    summary_parser.add_argument(
        "--agent-run",
        type=Path,
        default=None,
        help="agent_run.json path.",
    )
    summary_parser.add_argument("--out", type=Path, default=None, help="Markdown output path.")
    summary_parser.add_argument("--json-out", type=Path, default=None, help="JSON output path.")
    summary_parser.set_defaults(func=_cmd_pr_summary)


def _register_github_app(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``github-app`` command parser."""
    github_app_parser = subcommands.add_parser("github-app", help="Run GitHub App bot commands.")
    github_app_subcommands = github_app_parser.add_subparsers(
        dest="github_app_command",
        required=True,
    )
    github_serve = github_app_subcommands.add_parser("serve", help="Serve webhook endpoint.")
    github_serve.add_argument("--host", default="0.0.0.0", help="Host address.")
    github_serve.add_argument("--port", type=int, default=8080, help="Port number.")
    github_serve.set_defaults(func=_cmd_github_app_serve)


def _register_claim_check(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``claim-check`` command parser."""
    claim_parser = subcommands.add_parser(
        "claim-check",
        help="Check what prompt-optimization claim the run artifacts support.",
    )
    claim_parser.add_argument("--run", type=Path, required=True, help="Run directory.")
    claim_parser.add_argument(
        "--claim",
        choices=["paired", "partial-research", "full-research"],
        default="paired",
        help="Claim scope to check against recorded artifacts.",
    )
    claim_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional JSON output path. Sibling Markdown and HTML files are also written.",
    )
    claim_parser.set_defaults(func=_cmd_claim_check)


_REGISTRARS = {
    "audit-diff": _register_audit_diff,
    "agent-run": _register_agent_run,
    "pr-summary": _register_pr_summary,
    "github-app": _register_github_app,
    "claim-check": _register_claim_check,
}


def register_commands(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    names: Sequence[str] | None = None,
) -> None:
    """Register selected audit commands in the requested order."""

    selected = tuple(_REGISTRARS) if names is None else tuple(names)
    for name in selected:
        _REGISTRARS[name](subcommands)
