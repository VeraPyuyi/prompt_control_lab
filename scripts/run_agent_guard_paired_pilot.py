"""Run a small real raw-agent vs guarded-agent paired Codex pilot.

This script intentionally uses isolated temporary repositories. It never asks Codex to edit the
PromptControlLab repository itself.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

JsonDict = dict[str, Any]


@dataclass(frozen=True)
class PilotTask:
    task_id: str
    task_type: str
    raw_prompt: str
    files: dict[str, str]
    expected_paths: tuple[str, ...]
    test_command: str = "python -m pytest -q"


TASKS: tuple[PilotTask, ...] = (
    PilotTask(
        task_id="paired-001",
        task_type="math-bugfix",
        raw_prompt="Fix the failing test.",
        expected_paths=("src/pilot_app/math_utils.py",),
        files={
            "src/pilot_app/__init__.py": "",
            "src/pilot_app/math_utils.py": "def add(a: int, b: int) -> int:\n    return a - b\n",
            "tests/test_math_utils.py": (
                "from pilot_app.math_utils import add\n\n\n"
                "def test_adds_two_numbers() -> None:\n"
                "    assert add(2, 3) == 5\n"
            ),
        },
    ),
    PilotTask(
        task_id="paired-002",
        task_type="string-bugfix",
        raw_prompt="Make the failing slug test pass.",
        expected_paths=("src/pilot_app/text_utils.py",),
        files={
            "src/pilot_app/__init__.py": "",
            "src/pilot_app/text_utils.py": (
                "def slugify(text: str) -> str:\n"
                "    return text.strip().replace(' ', '-')\n"
            ),
            "tests/test_text_utils.py": (
                "from pilot_app.text_utils import slugify\n\n\n"
                "def test_slugify_lowercases_and_collapses_spaces() -> None:\n"
                "    assert slugify(' Hello   World ') == 'hello-world'\n"
            ),
        },
    ),
    PilotTask(
        task_id="paired-003",
        task_type="parser-bugfix",
        raw_prompt="Fix boolean parsing.",
        expected_paths=("src/pilot_app/parser.py",),
        files={
            "src/pilot_app/__init__.py": "",
            "src/pilot_app/parser.py": (
                "def parse_bool(value: str) -> bool:\n"
                "    return value.strip().lower() == 'true'\n"
            ),
            "tests/test_parser.py": (
                "from pilot_app.parser import parse_bool\n\n\n"
                "def test_parse_yes_as_true() -> None:\n"
                "    assert parse_bool(' yes ') is True\n\n\n"
                "def test_parse_no_as_false() -> None:\n"
                "    assert parse_bool('no') is False\n"
            ),
        },
    ),
    PilotTask(
        task_id="paired-004",
        task_type="validation-bugfix",
        raw_prompt="Fix the email redaction bug.",
        expected_paths=("src/pilot_app/privacy.py",),
        files={
            "src/pilot_app/__init__.py": "",
            "src/pilot_app/privacy.py": (
                "def redact_email(email: str) -> str:\n"
                "    return email\n"
            ),
            "tests/test_privacy.py": (
                "from pilot_app.privacy import redact_email\n\n\n"
                "def test_redact_email_keeps_domain() -> None:\n"
                "    assert redact_email('alice@example.com') == 'a***@example.com'\n"
            ),
        },
    ),
    PilotTask(
        task_id="paired-005",
        task_type="config-bugfix",
        raw_prompt="Fix the config default.",
        expected_paths=("src/pilot_app/config.py",),
        files={
            "src/pilot_app/__init__.py": "",
            "src/pilot_app/config.py": (
                "def default_port(config: dict[str, int]) -> int:\n"
                "    return config['port']\n"
            ),
            "tests/test_config.py": (
                "from pilot_app.config import default_port\n\n\n"
                "def test_default_port_when_missing() -> None:\n"
                "    assert default_port({}) == 8080\n"
            ),
        },
    ),
    PilotTask(
        task_id="paired-006",
        task_type="format-bugfix",
        raw_prompt="Fix the formatter.",
        expected_paths=("src/pilot_app/formatting.py",),
        files={
            "src/pilot_app/__init__.py": "",
            "src/pilot_app/formatting.py": (
                "def initials(name: str) -> str:\n"
                "    return ''.join(part[0] for part in name.split())\n"
            ),
            "tests/test_formatting.py": (
                "from pilot_app.formatting import initials\n\n\n"
                "def test_initials_are_uppercase() -> None:\n"
                "    assert initials('ada lovelace') == 'AL'\n"
            ),
        },
    ),
    PilotTask(
        task_id="paired-007",
        task_type="multi-file-serialization-bugfix",
        raw_prompt="Fix the failing user card regression without changing the public User fields.",
        expected_paths=("src/pilot_app/serializers.py",),
        files={
            "src/pilot_app/__init__.py": "",
            "src/pilot_app/models.py": (
                "from dataclasses import dataclass\n\n\n"
                "@dataclass(frozen=True)\n"
                "class User:\n"
                "    first_name: str\n"
                "    last_name: str\n"
                "    email: str\n"
            ),
            "src/pilot_app/serializers.py": (
                "from pilot_app.models import User\n\n\n"
                "def user_card(user: User) -> str:\n"
                "    return f'{user.first_name} {user.last_name}'\n"
            ),
            "tests/test_serializers.py": (
                "from pilot_app.models import User\n"
                "from pilot_app.serializers import user_card\n\n\n"
                "def test_user_card_includes_email() -> None:\n"
                "    user = User('Ada', 'Lovelace', 'ada@example.com')\n"
                "    assert user_card(user) == 'Ada Lovelace <ada@example.com>'\n"
            ),
        },
    ),
    PilotTask(
        task_id="paired-008",
        task_type="client-error-handling-bugfix",
        raw_prompt="Fix the client retry behavior and keep the callable API stable.",
        expected_paths=("src/pilot_app/client.py",),
        files={
            "src/pilot_app/__init__.py": "",
            "src/pilot_app/client.py": (
                "def fetch_with_retry(fetch, retries: int = 2):\n"
                "    return fetch()\n"
            ),
            "tests/test_client.py": (
                "from pilot_app.client import fetch_with_retry\n\n\n"
                "def test_fetch_retries_once_after_transient_error() -> None:\n"
                "    calls = {'count': 0}\n\n"
                "    def flaky():\n"
                "        calls['count'] += 1\n"
                "        if calls['count'] == 1:\n"
                "            raise TimeoutError('try again')\n"
                "        return 'ok'\n\n"
                "    assert fetch_with_retry(flaky, retries=2) == 'ok'\n"
                "    assert calls['count'] == 2\n"
            ),
        },
    ),
    PilotTask(
        task_id="paired-009",
        task_type="cli-config-bugfix",
        raw_prompt="Fix CLI config loading so environment defaults work.",
        expected_paths=("src/pilot_app/cli.py",),
        files={
            "src/pilot_app/__init__.py": "",
            "src/pilot_app/cli.py": (
                "import argparse\n\n\n"
                "def parse_port(argv: list[str], env: dict[str, str]) -> int:\n"
                "    parser = argparse.ArgumentParser()\n"
                "    parser.add_argument('--port', type=int, default=8000)\n"
                "    args = parser.parse_args(argv)\n"
                "    return args.port\n"
            ),
            "tests/test_cli_config.py": (
                "from pilot_app.cli import parse_port\n\n\n"
                "def test_port_uses_env_default_when_flag_missing() -> None:\n"
                "    assert parse_port([], {'APP_PORT': '9001'}) == 9001\n\n\n"
                "def test_cli_flag_overrides_env_default() -> None:\n"
                "    assert parse_port(['--port', '7000'], {'APP_PORT': '9001'}) == 7000\n"
            ),
        },
    ),
    PilotTask(
        task_id="paired-010",
        task_type="business-logic-bugfix",
        raw_prompt="Fix inventory totals and keep discount behavior covered by tests.",
        expected_paths=("src/pilot_app/inventory.py",),
        files={
            "src/pilot_app/__init__.py": "",
            "src/pilot_app/inventory.py": (
                "def invoice_total(\n"
                "    items: list[dict[str, float]], discount: float = 0.0\n"
                ") -> float:\n"
                "    subtotal = sum(item['price'] for item in items)\n"
                "    return round(subtotal - discount, 2)\n"
            ),
            "tests/test_inventory.py": (
                "from pilot_app.inventory import invoice_total\n\n\n"
                "def test_invoice_total_multiplies_quantities() -> None:\n"
                "    items = [{'price': 2.5, 'quantity': 4}, {'price': 3.0, 'quantity': 2}]\n"
                "    assert invoice_total(items) == 16.0\n\n\n"
                "def test_invoice_total_applies_discount_after_subtotal() -> None:\n"
                "    items = [{'price': 10.0, 'quantity': 2}]\n"
                "    assert invoice_total(items, discount=2.5) == 17.5\n"
            ),
        },
    ),
    PilotTask(
        task_id="paired-011",
        task_type="stateful-cache-bugfix",
        raw_prompt="Fix cache expiration without changing the public cache API.",
        expected_paths=("src/pilot_app/cache.py",),
        files={
            "src/pilot_app/__init__.py": "",
            "src/pilot_app/cache.py": (
                "class Cache:\n"
                "    def __init__(self) -> None:\n"
                "        self._items = {}\n\n"
                "    def set(self, key: str, value: str, ttl: int, now: int) -> None:\n"
                "        self._items[key] = (value, now + ttl)\n\n"
                "    def get(self, key: str, now: int) -> str | None:\n"
                "        value, expires_at = self._items[key]\n"
                "        return value\n"
            ),
            "tests/test_cache.py": (
                "from pilot_app.cache import Cache\n\n\n"
                "def test_cache_returns_none_after_expiry() -> None:\n"
                "    cache = Cache()\n"
                "    cache.set('session', 'abc', ttl=5, now=10)\n"
                "    assert cache.get('session', now=16) is None\n\n\n"
                "def test_cache_returns_none_for_missing_key() -> None:\n"
                "    assert Cache().get('missing', now=1) is None\n"
            ),
        },
    ),
    PilotTask(
        task_id="paired-012",
        task_type="csv-import-validation-bugfix",
        raw_prompt="Fix CSV import validation and preserve the existing return shape.",
        expected_paths=("src/pilot_app/importer.py",),
        files={
            "src/pilot_app/__init__.py": "",
            "src/pilot_app/importer.py": (
                "import csv\n"
                "from io import StringIO\n\n\n"
                "def import_users(csv_text: str) -> list[dict[str, str]]:\n"
                "    reader = csv.DictReader(StringIO(csv_text))\n"
                "    return [dict(row) for row in reader]\n"
            ),
            "tests/test_importer.py": (
                "import pytest\n\n"
                "from pilot_app.importer import import_users\n\n\n"
                "def test_import_users_skips_blank_rows() -> None:\n"
                "    csv_text = (\n"
                "        'name,email\\n'\n"
                "        'Ada,ada@example.com\\n'\n"
                "        ',\\n'\n"
                "        'Grace,grace@example.com\\n'\n"
                "    )\n"
                "    rows = import_users(csv_text)\n"
                "    assert rows == [\n"
                "        {'name': 'Ada', 'email': 'ada@example.com'},\n"
                "        {'name': 'Grace', 'email': 'grace@example.com'},\n"
                "    ]\n\n\n"
                "def test_import_users_requires_email_column() -> None:\n"
                "    with pytest.raises(ValueError, match='email'):\n"
                "        import_users('name\\nAda\\n')\n"
            ),
        },
    ),
)


CSV_FIELDS = [
    "task_id",
    "base_task_id",
    "trial",
    "agent",
    "task_type",
    "raw_prompt_summary",
    "guarded_prompt_summary",
    "raw_success",
    "guarded_success",
    "raw_touched_files",
    "guarded_touched_files",
    "raw_unnecessary_file_edits",
    "guarded_unnecessary_file_edits",
    "raw_tests_passed",
    "guarded_tests_passed",
    "raw_human_corrections",
    "guarded_human_corrections",
    "raw_prompt_tokens",
    "guarded_prompt_tokens",
    "raw_input_tokens",
    "guarded_input_tokens",
    "raw_cached_input_tokens",
    "guarded_cached_input_tokens",
    "raw_output_tokens",
    "guarded_output_tokens",
    "raw_total_tokens",
    "guarded_total_tokens",
    "raw_tool_calls",
    "guarded_tool_calls",
    "raw_duration_seconds",
    "guarded_duration_seconds",
    "notes",
]


def main() -> int:
    from promptcontrollab.prompt_context import empty_prompt_context
    from promptcontrollab.prompt_guard import guard_prompt

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "runs" / "paired-pilot")
    parser.add_argument(
        "--csv",
        type=Path,
        default=REPO_ROOT / "docs" / "case_studies" / "agent_guard_paired_pilot.csv",
    )
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=420)
    parser.add_argument("--proxy", default=_default_proxy())
    parser.add_argument("--policy", type=Path, default=REPO_ROOT / "examples" / "guard.policy.yaml")
    parser.add_argument("--codex-model", default=None)
    args = parser.parse_args()

    args.out = args.out.resolve(strict=False)
    args.csv = args.csv.resolve(strict=False)
    args.policy = args.policy.resolve(strict=False)
    selected_tasks = TASKS[: max(0, min(args.limit, len(TASKS)))]
    args.out.mkdir(parents=True, exist_ok=True)
    args.csv.parent.mkdir(parents=True, exist_ok=True)

    rows: list[JsonDict] = []
    details: list[JsonDict] = []
    for task_index, task in enumerate(selected_tasks):
        guarded_result = guard_prompt(
            task.raw_prompt,
            context=empty_prompt_context(),
            mode="suggest",
            profile="coding",
            token_mode="balanced",
            max_tokens=None,
            language="en",
            policy_path=args.policy,
        ).to_json()
        guarded_prompt = str(guarded_result["improved_prompt"])
        for trial in range(1, max(0, args.trials) + 1):
            prompts = {"raw": task.raw_prompt, "guarded": guarded_prompt}
            sides: dict[str, JsonDict] = {}
            order = (
                ("raw", "guarded")
                if (task_index + trial) % 2 == 0
                else ("guarded", "raw")
            )
            for side in order:
                print(f"[pilot] {task.task_id} trial={trial} {side}", flush=True)
                sides[side] = _run_side(
                    task,
                    side=side,
                    trial=trial,
                    prompt=prompts[side],
                    root=args.out,
                    timeout=args.timeout,
                    proxy=args.proxy,
                    codex_model=args.codex_model,
                )
            row = _row(
                task,
                trial=trial,
                raw=sides["raw"],
                guarded=sides["guarded"],
                guarded_prompt=guarded_prompt,
            )
            rows.append(row)
            details.append(
                {
                    "task": {
                        "task_id": task.task_id,
                        "task_type": task.task_type,
                        "trial": trial,
                        "raw_prompt": task.raw_prompt,
                        "expected_paths": list(task.expected_paths),
                    },
                    "execution_order": list(order),
                    "guard": guarded_result,
                    "raw": sides["raw"],
                    "guarded": sides["guarded"],
                }
            )
            _write_csv(args.csv, rows)
            _write_json(args.out / "agent_guard_paired_pilot_details.json", details)
            _write_json(
                args.out / "agent_guard_paired_pilot_summary.json",
                _summary(rows, details),
            )

    _write_csv(args.csv, rows)
    _write_json(args.csv.with_suffix(".summary.json"), _summary(rows, details))
    print(f"[pilot] wrote {args.csv}")
    return 0


def _run_side(
    task: PilotTask,
    *,
    side: str,
    trial: int,
    prompt: str,
    root: Path,
    timeout: int,
    proxy: str | None,
    codex_model: str | None,
) -> JsonDict:
    worktree = root / "workspaces" / f"{task.task_id}-trial-{trial:02d}-{side}"
    if worktree.exists():
        _remove_tree(worktree)
    _create_repo(task, worktree)
    logs = root / "logs" / task.task_id / f"trial-{trial:02d}" / side
    logs.mkdir(parents=True, exist_ok=True)
    last_message = logs / "last_message.txt"
    stdout_path = logs / "stdout.txt"
    stderr_path = logs / "stderr.txt"
    command = [
        "codex",
        "--dangerously-bypass-approvals-and-sandbox",
    ]
    if codex_model:
        command.extend(["--model", codex_model])
    command.extend(
        [
            "exec",
            "--json",
            "--cd",
            str(worktree),
            "--ephemeral",
            "--ignore-rules",
            "--ignore-user-config",
            "--output-last-message",
            str(last_message),
            "-",
        ]
    )
    env = os.environ.copy()
    if proxy:
        env["HTTP_PROXY"] = proxy
        env["HTTPS_PROXY"] = proxy
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            input=prompt,
            cwd=worktree,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        completed = subprocess.CompletedProcess(
            command,
            returncode=124,
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
        )
        timed_out = True
    duration = round(time.monotonic() - started, 2)
    stdout_path.write_text(str(completed.stdout or ""), encoding="utf-8")
    stderr_path.write_text(str(completed.stderr or ""), encoding="utf-8")
    test_result = _run_test(worktree, task.test_command)
    touched_files = _touched_files(worktree)
    unexpected = [
        path
        for path in touched_files
        if not any(
            path == expected or path.startswith(f"{expected}/") for expected in task.expected_paths
        )
    ]
    changed_lines = _changed_lines(worktree, touched_files)
    success = bool(test_result["passed"])
    usage = _codex_usage(str(completed.stdout or ""))
    return {
        "side": side,
        "trial": trial,
        "worktree": str(worktree),
        "prompt": prompt,
        "codex_returncode": completed.returncode,
        "codex_timed_out": timed_out,
        "duration_seconds": duration,
        "tests_passed": test_result["passed"],
        "test_command": task.test_command,
        "test_stdout": test_result["stdout"][-4000:],
        "test_stderr": test_result["stderr"][-4000:],
        "success": success,
        "touched_files": touched_files,
        "touched_file_count": len(touched_files),
        "unexpected_files": unexpected,
        "unnecessary_file_edits": len(unexpected),
        "changed_lines": changed_lines,
        "human_corrections": 0,
        "usage": usage,
        "tool_calls": _codex_tool_call_count(str(completed.stdout or "")),
        "last_message_path": str(last_message),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
    }


def _create_repo(task: PilotTask, path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "pytest.ini").write_text("[pytest]\npythonpath = src\n", encoding="utf-8", newline="\n")
    for relative, content in task.files.items():
        target = path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "pilot@example.local")
    _git(path, "config", "user.name", "PromptControlLab Pilot")
    _git(path, "add", ".")
    _git(path, "commit", "-q", "-m", "initial")


def _run_test(repo: Path, command: str) -> JsonDict:
    completed = subprocess.run(
        command.split(),
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=60,
    )
    return {
        "passed": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _touched_files(repo: Path) -> list[str]:
    output = _git(repo, "status", "--porcelain")
    files: list[str] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        path = line[3:].replace("\\", "/")
        if _ignore_touched(path):
            continue
        files.append(path)
    return sorted(set(files))


def _changed_lines(repo: Path, touched_files: list[str]) -> list[JsonDict]:
    tracked = _git(repo, "diff", "--numstat", "HEAD")
    rows: list[JsonDict] = []
    seen: set[str] = set()
    for line in tracked.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added, deleted, path = parts
        normalized = path.replace("\\", "/")
        seen.add(normalized)
        rows.append(
            {
                "file": normalized,
                "added": _safe_int(added),
                "deleted": _safe_int(deleted),
            }
        )
    for path in touched_files:
        if path in seen:
            continue
        target = repo / path
        if target.exists() and target.is_file():
            try:
                added = len(target.read_text(encoding="utf-8", errors="ignore").splitlines())
            except OSError:
                added = 0
        else:
            added = 0
        rows.append({"file": path, "added": added, "deleted": 0})
    return sorted(rows, key=lambda item: str(item["file"]))


def _row(
    task: PilotTask,
    *,
    trial: int,
    raw: JsonDict,
    guarded: JsonDict,
    guarded_prompt: str,
) -> JsonDict:
    from promptcontrollab.prompt_improver import estimate_tokens

    notes = (
        "real Codex paired pilot; "
        f"raw_code={raw['codex_returncode']}; guarded_code={guarded['codex_returncode']}; "
        f"raw_timeout={raw['codex_timed_out']}; guarded_timeout={guarded['codex_timed_out']}"
    )
    raw_usage = _mapping(raw.get("usage"))
    guarded_usage = _mapping(guarded.get("usage"))
    return {
        "task_id": f"{task.task_id}-trial-{trial:02d}",
        "base_task_id": task.task_id,
        "trial": trial,
        "agent": "codex-local-exec",
        "task_type": task.task_type,
        "raw_prompt_summary": task.raw_prompt,
        "guarded_prompt_summary": _compact(guarded_prompt),
        "raw_success": str(bool(raw["success"])).lower(),
        "guarded_success": str(bool(guarded["success"])).lower(),
        "raw_touched_files": raw["touched_file_count"],
        "guarded_touched_files": guarded["touched_file_count"],
        "raw_unnecessary_file_edits": raw["unnecessary_file_edits"],
        "guarded_unnecessary_file_edits": guarded["unnecessary_file_edits"],
        "raw_tests_passed": str(bool(raw["tests_passed"])).lower(),
        "guarded_tests_passed": str(bool(guarded["tests_passed"])).lower(),
        "raw_human_corrections": raw["human_corrections"],
        "guarded_human_corrections": guarded["human_corrections"],
        "raw_prompt_tokens": estimate_tokens(task.raw_prompt),
        "guarded_prompt_tokens": estimate_tokens(guarded_prompt),
        "raw_input_tokens": raw_usage.get("input_tokens"),
        "guarded_input_tokens": guarded_usage.get("input_tokens"),
        "raw_cached_input_tokens": raw_usage.get("cached_input_tokens"),
        "guarded_cached_input_tokens": guarded_usage.get("cached_input_tokens"),
        "raw_output_tokens": raw_usage.get("output_tokens"),
        "guarded_output_tokens": guarded_usage.get("output_tokens"),
        "raw_total_tokens": raw_usage.get("total_tokens"),
        "guarded_total_tokens": guarded_usage.get("total_tokens"),
        "raw_tool_calls": raw["tool_calls"],
        "guarded_tool_calls": guarded["tool_calls"],
        "raw_duration_seconds": raw["duration_seconds"],
        "guarded_duration_seconds": guarded["duration_seconds"],
        "notes": notes,
    }


def _summary(rows: list[JsonDict], details: list[JsonDict]) -> JsonDict:
    total = len(rows)
    raw_success = sum(row["raw_success"] == "true" for row in rows)
    guarded_success = sum(row["guarded_success"] == "true" for row in rows)
    raw_tests = sum(row["raw_tests_passed"] == "true" for row in rows)
    guarded_tests = sum(row["guarded_tests_passed"] == "true" for row in rows)
    return {
        "sample_size": total,
        "task_count": len({str(row["base_task_id"]) for row in rows}),
        "trials_per_task": max((int(row["trial"]) for row in rows), default=0),
        "agent_executions": total * 2,
        "agent": "codex-local-exec",
        "raw_success": raw_success,
        "guarded_success": guarded_success,
        "raw_tests_passed": raw_tests,
        "guarded_tests_passed": guarded_tests,
        "raw_avg_touched_files": _avg(row["raw_touched_files"] for row in rows),
        "guarded_avg_touched_files": _avg(row["guarded_touched_files"] for row in rows),
        "raw_total_unnecessary_file_edits": sum(
            int(row["raw_unnecessary_file_edits"]) for row in rows
        ),
        "guarded_total_unnecessary_file_edits": sum(
            int(row["guarded_unnecessary_file_edits"]) for row in rows
        ),
        "raw_avg_prompt_tokens": _avg(row["raw_prompt_tokens"] for row in rows),
        "guarded_avg_prompt_tokens": _avg(row["guarded_prompt_tokens"] for row in rows),
        "raw_avg_total_tokens": _avg_present(row.get("raw_total_tokens") for row in rows),
        "guarded_avg_total_tokens": _avg_present(
            row.get("guarded_total_tokens") for row in rows
        ),
        "raw_avg_tool_calls": _avg(row["raw_tool_calls"] for row in rows),
        "guarded_avg_tool_calls": _avg(row["guarded_tool_calls"] for row in rows),
        "raw_avg_duration_seconds": _avg(row["raw_duration_seconds"] for row in rows),
        "guarded_avg_duration_seconds": _avg(row["guarded_duration_seconds"] for row in rows),
        "task_ids": [row["task_id"] for row in rows],
        "limitations": [
            "Small repeated local fixture pilot, not a universal benchmark.",
            "No human correction turns were provided after failed runs.",
            "Tasks are isolated Python pytest fixtures, not full production PRs.",
            "Full-run token usage is reported only when the Codex JSON event stream provides it.",
        ],
        "detail_count": len(details),
    }


def _write_csv(path: Path, rows: list[JsonDict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: JsonDict | list[JsonDict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _remove_tree(path: Path) -> None:
    def onexc(function: Callable[[str], object], target: str, exc_info: BaseException) -> None:
        del exc_info
        os.chmod(target, stat.S_IWRITE)
        function(target)

    shutil.rmtree(path, onexc=onexc)


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return completed.stdout


def _ignore_touched(path: str) -> bool:
    lowered = path.lower()
    return (
        "__pycache__/" in lowered
        or lowered.endswith(".pyc")
        or lowered in {"events.jsonl", "last.txt"}
    )


def _compact(text: str, limit: int = 180) -> str:
    cleaned = " ".join(text.split())
    return cleaned[:limit]


def _safe_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def _codex_usage(stdout: str) -> JsonDict:
    """Return the last complete token-usage record from a Codex JSONL stream."""

    last: JsonDict = {}
    for event in _jsonl_objects(stdout):
        for candidate in _usage_candidates(event):
            normalized = _normalize_usage(candidate)
            if normalized:
                last = normalized
    return last


def _codex_tool_call_count(stdout: str) -> int:
    """Count completed tool-like items without double-counting start events."""

    count = 0
    tool_types = {
        "command_execution",
        "file_change",
        "mcp_tool_call",
        "web_search",
    }
    for event in _jsonl_objects(stdout):
        if event.get("type") not in {"item.completed", "tool.completed"}:
            continue
        item = event.get("item")
        item_type = item.get("type") if isinstance(item, dict) else event.get("tool_type")
        if item_type in tool_types:
            count += 1
    return count


def _jsonl_objects(text: str) -> list[JsonDict]:
    rows: list[JsonDict] = []
    for line in text.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _usage_candidates(value: object) -> list[JsonDict]:
    candidates: list[JsonDict] = []
    if isinstance(value, dict):
        usage = value.get("usage")
        if isinstance(usage, dict):
            candidates.append(usage)
        for nested in value.values():
            candidates.extend(_usage_candidates(nested))
    elif isinstance(value, list):
        for nested in value:
            candidates.extend(_usage_candidates(nested))
    return candidates


def _normalize_usage(value: JsonDict) -> JsonDict:
    aliases = {
        "input_tokens": ("input_tokens", "prompt_tokens"),
        "cached_input_tokens": ("cached_input_tokens", "cached_prompt_tokens"),
        "output_tokens": ("output_tokens", "completion_tokens"),
        "total_tokens": ("total_tokens",),
    }
    result: JsonDict = {}
    for target, keys in aliases.items():
        raw = next((value[key] for key in keys if key in value), None)
        if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0:
            result[target] = raw
    if "total_tokens" not in result and {
        "input_tokens",
        "output_tokens",
    }.issubset(result):
        result["total_tokens"] = int(result["input_tokens"]) + int(result["output_tokens"])
    return result


def _mapping(value: object) -> JsonDict:
    return value if isinstance(value, dict) else {}


def _avg(values: object) -> float:
    items = [float(value) for value in values]
    if not items:
        return 0.0
    return round(sum(items) / len(items), 2)


def _avg_present(values: object) -> float | None:
    items = [float(value) for value in values if isinstance(value, int | float)]
    if not items:
        return None
    return round(sum(items) / len(items), 2)


def _default_proxy() -> str | None:
    for key in ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy"):
        value = os.getenv(key)
        if value:
            return value
    return None


if __name__ == "__main__":
    raise SystemExit(main())
