"""Audit command handlers and terminal formatters."""

from __future__ import annotations

import argparse
import json

from promptcontrollab.audit.agent_run import build_agent_run_manifest
from promptcontrollab.audit.audit_diff import run_audit_diff
from promptcontrollab.audit.claim_check import run_claim_check
from promptcontrollab.audit.pr_summary import write_pr_summary
from promptcontrollab.cli.common import _optional_bool
from promptcontrollab.core.config import (
    get_config_list,
    load_project_config,
)


def _cmd_audit_diff(args: argparse.Namespace) -> None:
    """Execute the audit diff command handler."""
    project_config, _project_config_path = load_project_config(args.repo)
    expected_paths = list(args.expected_path) or get_config_list(project_config, "expected_paths")
    test_commands = list(args.test_command) or get_config_list(project_config, "test_commands")
    payload = run_audit_diff(
        repo=args.repo,
        before=args.before,
        after=args.after,
        out_dir=args.out,
        expected_paths=expected_paths,
        test_commands=test_commands,
        tests_run=list(args.tests_run),
        tests_passed=_optional_bool(args.tests_passed),
        test_timeout=args.test_timeout,
        allow_shell_test_command=args.allow_shell_test_command,
        sarif_path=args.sarif,
        secret_scanner=args.secret_scanner,
    )
    print(f"Wrote audit artifacts to {args.out}")
    print(f"Human review required: {payload['human_review_required']}")


def _cmd_agent_run_build(args: argparse.Namespace) -> None:
    """Execute the agent run build command handler."""
    build_agent_run_manifest(
        run_dir=args.run,
        audit_dir=args.audit,
        agent=args.agent,
        out_path=args.out,
        policy=args.policy,
    )
    print(f"Wrote agent run manifest to {args.out}")


def _cmd_pr_summary(args: argparse.Namespace) -> None:
    """Execute the pr summary command handler."""
    payload = write_pr_summary(
        audit_path=args.audit,
        gate_path=args.gate,
        evidence_gate_path=args.evidence_gate,
        agent_run_path=args.agent_run,
        markdown_path=args.out,
        json_path=args.json_out,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_github_app_serve(args: argparse.Namespace) -> None:
    """Execute the github app serve command handler."""
    from promptcontrollab.audit.github_app import serve_github_app

    serve_github_app(host=args.host, port=args.port)


def _cmd_claim_check(args: argparse.Namespace) -> None:
    """Execute the claim check command handler."""
    payload = run_claim_check(args.run, claim=args.claim, out_path=args.out)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
