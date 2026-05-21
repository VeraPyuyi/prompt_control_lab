"""Git diff based audit for AI coding agent runs."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from promptcontrollab.files import JsonDict, ensure_dir, write_json

SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".go", ".rs", ".java", ".cs", ".c", ".cpp", ".h"}
CONFIG_EXTENSIONS = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"}
DANGEROUS_PARTS = {
    "auth",
    "security",
    "permission",
    "permissions",
    "billing",
    "payment",
    "payments",
    "migration",
    "migrations",
    "secret",
    "secrets",
    "credential",
    "credentials",
}


def run_audit_diff(
    *,
    repo: Path,
    before: str,
    after: str,
    out_dir: Path,
    expected_paths: list[str] | None = None,
    test_commands: list[str] | None = None,
    tests_run: list[str] | None = None,
    tests_passed: bool | None = None,
    test_timeout: int = 120,
    allow_shell_test_command: bool = False,
) -> JsonDict:
    """Audit changed files between two git refs and write audit artifacts."""

    repo = repo.resolve()
    changed_files = _changed_files(repo, before, after)
    diff_text = _git(repo, "diff", "--unified=0", before, after)
    executed_commands, executed_passed, test_results = _run_test_commands(
        repo,
        test_commands or [],
        timeout_seconds=test_timeout,
        allow_shell=allow_shell_test_command,
    )
    recorded_tests = [*(tests_run or []), *executed_commands]
    final_tests_passed = executed_passed if executed_commands else tests_passed
    expected = [item.replace("\\", "/").rstrip("/") for item in expected_paths or []]
    unexpected_files = _unexpected_files(changed_files, expected)
    unnecessary = len(unexpected_files) if expected else None
    dangerous_paths = [path for path in changed_files if _is_dangerous_path(path)]
    public_api_changed = _public_api_changed(diff_text)
    payload: JsonDict = {
        "before": before,
        "after": after,
        "repo": str(repo),
        "changed_files": changed_files,
        "touched_files": len(changed_files),
        "source_files_changed": sum(_is_source_file(path) for path in changed_files),
        "test_files_changed": sum(_is_test_file(path) for path in changed_files),
        "docs_files_changed": sum(_is_docs_file(path) for path in changed_files),
        "config_files_changed": sum(_is_config_file(path) for path in changed_files),
        "dangerous_paths": dangerous_paths,
        "public_api_changed": public_api_changed,
        "tests_run": recorded_tests,
        "tests_passed": final_tests_passed,
        "test_results": test_results,
        "expected_paths": expected,
        "unexpected_files": unexpected_files,
        "unnecessary_file_edits": unnecessary,
        "human_review_required": bool(
            dangerous_paths
            or public_api_changed
            or unexpected_files
            or final_tests_passed is False
        ),
        "warnings": _warnings(expected, final_tests_passed, allow_shell_test_command),
    }
    ensure_dir(out_dir)
    write_json(out_dir / "audit_result.json", payload)
    (out_dir / "audit_summary.md").write_text(_render_summary(payload), encoding="utf-8")
    return payload


def _changed_files(repo: Path, before: str, after: str) -> list[str]:
    output = _git(repo, "diff", "--name-only", before, after)
    return sorted(line.replace("\\", "/") for line in output.splitlines() if line.strip())


def _git(repo: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        msg = "git executable was not found; install git or check PATH."
        raise ValueError(msg) from exc
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        command = " ".join(["git", *args])
        msg = f"{command} failed"
        if details:
            msg += f": {details}"
        raise ValueError(msg) from exc
    return completed.stdout


def _run_test_commands(
    repo: Path,
    commands: list[str],
    *,
    timeout_seconds: int,
    allow_shell: bool,
) -> tuple[list[str], bool | None, list[JsonDict]]:
    if not commands:
        return [], None, []
    passed = True
    results: list[JsonDict] = []
    for command in commands:
        if not allow_shell and _looks_like_shell_command(command):
            msg = (
                "Refusing to execute shell control syntax in --test-command. "
                "Use --tests-run/--tests-passed to record external results, or pass "
                "--allow-shell-test-command when you intentionally want shell execution."
            )
            raise ValueError(msg)
        try:
            if allow_shell:
                completed = subprocess.run(
                    command,
                    cwd=repo,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                )
            else:
                completed = subprocess.run(
                    shlex.split(command, posix=True),
                    cwd=repo,
                    shell=False,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                )
        except subprocess.TimeoutExpired as exc:
            passed = False
            results.append(
                {
                    "command": command,
                    "returncode": None,
                    "timed_out": True,
                    "timeout_seconds": timeout_seconds,
                    "stdout": _truncate(exc.stdout),
                    "stderr": _truncate(exc.stderr),
                    "mode": "shell" if allow_shell else "exec",
                }
            )
            continue
        if completed.returncode != 0:
            passed = False
        results.append(
            {
                "command": command,
                "returncode": completed.returncode,
                "timed_out": False,
                "timeout_seconds": timeout_seconds,
                "stdout": _truncate(completed.stdout),
                "stderr": _truncate(completed.stderr),
                "mode": "shell" if allow_shell else "exec",
            }
        )
    return commands, passed, results


def _looks_like_shell_command(command: str) -> bool:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(command):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote is not None:
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            continue
        if char in {";", "|", ">", "<", "`", "\n", "\r"}:
            return True
        if char == "&" and command[index : index + 2] == "&&":
            return True
        if char == "$" and command[index : index + 2] == "$(":
            return True
    return False


def _truncate(value: object, *, limit: int = 4000) -> str:
    if value is None:
        return ""
    text = str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"


def _unexpected_files(changed_files: list[str], expected_paths: list[str]) -> list[str]:
    if not expected_paths:
        return []
    unexpected: list[str] = []
    for path in changed_files:
        normalized = path.replace("\\", "/")
        in_expected_scope = any(
            normalized == expected or normalized.startswith(expected + "/")
            for expected in expected_paths
        )
        if not in_expected_scope:
            unexpected.append(path)
    return unexpected


def _is_source_file(path: str) -> bool:
    return not _is_test_file(path) and Path(path).suffix.lower() in SOURCE_EXTENSIONS


def _is_test_file(path: str) -> bool:
    lowered = path.lower()
    name = Path(path).name.lower()
    return (
        lowered.startswith("tests/")
        or "/tests/" in lowered
        or name.startswith("test_")
        or "_test." in name
        or ".test." in name
        or ".spec." in name
    )


def _is_docs_file(path: str) -> bool:
    lowered = path.lower()
    return lowered.startswith("docs/") or Path(path).suffix.lower() in {".md", ".rst"}


def _is_config_file(path: str) -> bool:
    name = Path(path).name.lower()
    lowered = path.lower()
    return (
        Path(path).suffix.lower() in CONFIG_EXTENSIONS
        or lowered.startswith(".github/")
        or name in {"dockerfile", "makefile"}
    )


def _is_dangerous_path(path: str) -> bool:
    parts = [part.lower() for part in Path(path).parts]
    return any(part in DANGEROUS_PARTS for part in parts)


def _public_api_changed(diff_text: str) -> bool:
    for line in diff_text.splitlines():
        if not line.startswith(("+", "-")) or line.startswith(("+++", "---")):
            continue
        stripped = line[1:].lstrip()
        if stripped.startswith(("def ", "async def ", "class ")):
            name = stripped.split("(", maxsplit=1)[0].split(":", maxsplit=1)[0].split()[-1]
            if not name.startswith("_"):
                return True
        if stripped.startswith("export "):
            return True
    return False


def _warnings(
    expected_paths: list[str],
    tests_passed: bool | None,
    allow_shell_test_command: bool,
) -> list[str]:
    warnings: list[str] = []
    if not expected_paths:
        warnings.append("No expected paths were provided; unnecessary_file_edits is unknown.")
    if tests_passed is None:
        warnings.append("No test result was recorded for this audit.")
    if allow_shell_test_command:
        warnings.append(
            "Shell test command execution was explicitly enabled; only use this with trusted input."
        )
    return warnings


def _render_summary(payload: JsonDict) -> str:
    return "\n".join(
        [
            "# Agent Run Audit",
            "",
            f"- Changed files: {payload['touched_files']}",
            f"- Source files changed: {payload['source_files_changed']}",
            f"- Test files changed: {payload['test_files_changed']}",
            f"- Dangerous paths: {', '.join(payload['dangerous_paths']) or 'none'}",
            f"- Public API changed: {payload['public_api_changed']}",
            f"- Tests passed: {payload['tests_passed']}",
            f"- Human review required: {payload['human_review_required']}",
            "",
            "## Changed Files",
            "",
            *[f"- `{path}`" for path in payload["changed_files"]],
            "",
        ]
    )
