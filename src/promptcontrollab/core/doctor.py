"""Environment diagnostics for PromptControlLab installations."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from promptcontrollab.core.files import JsonDict
from promptcontrollab.evaluation.workflow import run_quick_analysis
from promptcontrollab.preflight.guard_policy import load_guard_policy
from promptcontrollab.templates import write_example_project


def run_doctor(*, repo_root: Path | None = None) -> JsonDict:
    """Run local installation and integration diagnostics."""

    root = repo_root or Path.cwd()
    checks = [
        _check_python_version(),
        _check_package_import(),
        _check_cli_parser(),
        _check_openai_key(),
        _check_guard_policy(root),
        _check_claude_hook(root),
        _check_cursor_mcp(root),
        _check_demo_report(),
        _check_optional_research_dependencies(),
    ]
    status = _overall_status(checks)
    return {"status": status, "checks": checks}


def format_doctor(payload: JsonDict) -> str:
    """Render human-readable doctor output."""

    lines = ["PromptControlLab Doctor", "", f"Overall: {payload['status']}", "", "Checks:"]
    for check in payload["checks"]:
        lines.append(f"- {check['status']}: {check['name']} - {check['message']}")
    return "\n".join(lines)


def _check_python_version() -> JsonDict:
    major = int(sys.version_info[0])
    minor = int(sys.version_info[1])
    micro = int(sys.version_info[2])
    version = f"{major}.{minor}.{micro}"
    if (major, minor) < (3, 10):
        return _check(
            "python_version",
            "fail",
            f"Python {version} is installed; PromptControlLab requires Python >=3.10.",
        )
    return _check("python_version", "pass", f"Python {version} is supported.")


def _check_package_import() -> JsonDict:
    try:
        import promptcontrollab  # noqa: F401
    except Exception as exc:  # pragma: no cover - defensive environment boundary
        return _check("package_import", "fail", f"Import failed: {exc}")
    return _check("package_import", "pass", "Package imports successfully.")


def _check_cli_parser() -> JsonDict:
    try:
        from promptcontrollab.cli import build_parser

        parser = build_parser()
        if parser.prog == "pcl":
            return _check("cli_parser", "pass", "CLI parser is available.")
        return _check("cli_parser", "fail", f"Unexpected CLI parser prog: {parser.prog}.")
    except Exception as exc:  # pragma: no cover - defensive environment boundary
        return _check("cli_parser", "fail", f"CLI parser failed: {exc}")
    return _check("cli_parser", "pass", "CLI parser is available.")


def _check_openai_key() -> JsonDict:
    if os.environ.get("OPENAI_API_KEY"):
        return _check("openai_api_key", "pass", "OPENAI_API_KEY is present.")
    return _check(
        "openai_api_key",
        "warning",
        "OPENAI_API_KEY is not set; online model verify will be skipped.",
    )


def _check_guard_policy(root: Path) -> JsonDict:
    policy = root / "examples" / "guard.policy.yaml"
    if not policy.exists():
        return _check("guard_policy", "warning", f"{policy} was not found.")
    try:
        load_guard_policy(policy)
    except Exception as exc:
        return _check("guard_policy", "fail", f"Guard policy failed to parse: {exc}")
    return _check("guard_policy", "pass", "examples/guard.policy.yaml parses successfully.")


def _check_claude_hook(root: Path) -> JsonDict:
    hook = root / "plugins" / "claude-code" / "hooks" / "prompt_guard.py"
    if not hook.exists():
        return _check("claude_code_hook", "warning", "Claude Code hook script was not found.")
    event = json.dumps({"prompt": "Fix this bug"})
    return _run_subprocess_check(
        "claude_code_hook",
        [sys.executable, str(hook), "--mode", "suggest"],
        input_text=event,
        cwd=root,
        success_message="Claude Code hook runs.",
    )


def _check_cursor_mcp(root: Path) -> JsonDict:
    server = root / "plugins" / "cursor" / "mcp_server.py"
    if not server.exists():
        return _check("cursor_mcp_server", "warning", "Cursor MCP server script was not found.")
    request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}) + "\n"
    return _run_subprocess_check(
        "cursor_mcp_server",
        [sys.executable, str(server)],
        input_text=request,
        cwd=root,
        success_message="Cursor MCP server initializes.",
    )


def _check_demo_report() -> JsonDict:
    try:
        with tempfile.TemporaryDirectory() as raw:
            demo = Path(raw) / "demo"
            write_example_project(demo)
            run_quick_analysis(
                data_path=demo / "examples" / "tasks.jsonl",
                baseline_predictions_path=demo / "examples" / "predictions_baseline.jsonl",
                candidate_predictions_path=demo / "examples" / "predictions_candidate.jsonl",
                out_dir=demo / "runs" / "quick",
                metric="exact_match",
                train_ratio=0.5,
                val_ratio=0.25,
                seed=0,
                bootstrap_samples=100,
                permutation_samples=100,
                explain_level="plain",
                title="Doctor Demo",
                policy_path=demo / "examples" / "gate.policy.yaml",
            )
    except Exception as exc:
        return _check("demo_report", "fail", f"Demo report failed: {exc}")
    return _check("demo_report", "pass", "Demo quick analysis can generate a report.")


def _check_optional_research_dependencies() -> JsonDict:
    missing = [
        name
        for name in ["numpy", "scipy"]
        if importlib.util.find_spec(name) is None
    ]
    if missing:
        return _check(
            "optional_research_dependencies",
            "warning",
            "Missing optional research dependencies: " + ", ".join(missing),
        )
    return _check(
        "optional_research_dependencies",
        "pass",
        "Optional research dependencies are available.",
    )


def _run_subprocess_check(
    name: str,
    command: list[str],
    *,
    input_text: str,
    cwd: Path,
    success_message: str,
) -> JsonDict:
    try:
        completed = subprocess.run(
            command,
            input=input_text,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception as exc:  # pragma: no cover - defensive environment boundary
        return _check(name, "fail", f"Could not run check: {exc}")
    if completed.returncode != 0:
        return _check(name, "fail", completed.stderr.strip() or f"Exited {completed.returncode}.")
    return _check(name, "pass", success_message)


def _check(name: str, status: str, message: str) -> JsonDict:
    return {"name": name, "status": status, "message": message}


def _overall_status(checks: list[JsonDict]) -> str:
    statuses = {str(check["status"]) for check in checks}
    if "fail" in statuses:
        return "fail"
    if "warning" in statuses:
        return "warning"
    return "pass"
