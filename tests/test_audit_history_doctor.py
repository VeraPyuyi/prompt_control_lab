from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from promptcontrollab.cli import main


def test_cli_audit_diff_reports_agent_run_risks(tmp_path: Path) -> None:
    repo = _make_git_repo(tmp_path)
    _write(repo / "src" / "app.py", "def existing() -> str:\n    return 'ok'\n")
    _write(repo / "README.md", "# demo\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")

    _write(
        repo / "src" / "app.py",
        "def existing() -> str:\n    return 'ok'\n\ndef public_api() -> str:\n    return 'new'\n",
    )
    _write(repo / "auth" / "session.py", "def disable_auth() -> bool:\n    return True\n")
    _write(repo / "tests" / "test_app.py", "def test_existing():\n    assert True\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "agent changes")

    out = repo / "runs" / "audit"
    assert (
        main(
            [
                "audit-diff",
                "--repo",
                str(repo),
                "--before",
                "HEAD~1",
                "--after",
                "HEAD",
                "--out",
                str(out),
                "--expected-path",
                "src",
                "--tests-run",
                "pytest tests/test_app.py",
                "--tests-passed",
                "true",
            ]
        )
        == 0
    )

    payload = json.loads((out / "audit_result.json").read_text(encoding="utf-8"))
    assert payload["touched_files"] == 3
    assert payload["source_files_changed"] == 2
    assert payload["test_files_changed"] == 1
    assert payload["dangerous_paths"] == ["auth/session.py"]
    assert payload["public_api_changed"] is True
    assert payload["tests_run"] == ["pytest tests/test_app.py"]
    assert payload["tests_passed"] is True
    assert payload["unnecessary_file_edits"] == 2
    assert payload["human_review_required"] is True
    assert (out / "audit_summary.md").exists()


def test_cli_audit_diff_can_run_test_command(tmp_path: Path) -> None:
    repo = _make_git_repo(tmp_path)
    _write(repo / "src" / "app.py", "def existing() -> str:\n    return 'ok'\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    _write(repo / "src" / "app.py", "def existing() -> str:\n    return 'changed'\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "change")

    out = repo / "runs" / "audit"
    command = f'"{sys.executable}" -c "import sys; sys.exit(0)"'
    assert (
        main(
            [
                "audit-diff",
                "--repo",
                str(repo),
                "--before",
                "HEAD~1",
                "--after",
                "HEAD",
                "--out",
                str(out),
                "--test-command",
                command,
            ]
        )
        == 0
    )

    payload = json.loads((out / "audit_result.json").read_text(encoding="utf-8"))
    assert payload["tests_run"] == [command]
    assert payload["tests_passed"] is True
    assert payload["unnecessary_file_edits"] is None


def test_cli_history_index_and_compare(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    old = runs / "old"
    new = runs / "new"
    _write_json(
        old / "manifest.json",
        {
            "prompt_hash": "old-prompt",
            "candidate_model": {"provider": "openai", "model_id": "gpt-4o"},
        },
    )
    _write_json(
        old / "metrics.json",
        {"mean_score": 0.8, "by_slice": {"math": 0.9, "format": 0.7}},
    )
    _write_json(old / "gate_result.json", {"status": "pass", "checks": {}})
    _write_json(
        new / "manifest.json",
        {
            "prompt_hash": "new-prompt",
            "candidate_model": {"provider": "openai", "model_id": "gpt-5.2"},
        },
    )
    _write_json(
        new / "metrics.json",
        {"mean_score": 0.75, "by_slice": {"math": 0.8, "format": 0.72}},
    )
    _write_json(
        new / "gate_result.json",
        {
            "status": "fail",
            "checks": {"model_provenance": {"violations": ["model_mismatch"]}},
        },
    )
    _write(runs / "notes.txt", "not a run")

    index_out = runs / "history_index.json"
    compare_out = runs / "history_compare.json"
    assert main(["history", "index", "--runs", str(runs), "--out", str(index_out)]) == 0
    assert (
        main(["history", "compare", "--a", str(old), "--b", str(new), "--out", str(compare_out)])
        == 0
    )

    index = json.loads(index_out.read_text(encoding="utf-8"))
    assert [item["run_name"] for item in index["runs"]] == ["new", "old"]
    compare = json.loads(compare_out.read_text(encoding="utf-8"))
    assert compare["prompt_same"] is False
    assert compare["model_same"] is False
    assert compare["gate_status_change"] == {"a": "pass", "b": "fail"}
    assert compare["metric_delta"] == -0.05
    assert compare["regressed_slices"] == [{"slice": "math", "a": 0.9, "b": 0.8, "delta": -0.1}]
    assert compare["new_risk_categories"] == ["model_mismatch"]


def test_cli_doctor_json_outputs_stable_checks(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["doctor", "--json"]) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    names = {item["name"] for item in payload["checks"]}
    assert payload["status"] in {"pass", "warning", "fail"}
    assert {"python_version", "package_import", "cli_parser", "guard_policy"}.issubset(names)
    assert "optional_research_dependencies" in names


def test_github_action_example_exists_and_uses_real_cli() -> None:
    action = Path("examples/github-action/prompt-control-lab-gate.yml")
    text = action.read_text(encoding="utf-8")
    assert "on:" in text
    assert "pull_request" in text
    assert "pcl gate --run runs/quick --policy examples/gate.policy.yaml" in text
    assert "pcl audit-diff" in text
    assert "actions/github-script" in text


def _make_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "PromptControlLab Test")
    return repo


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: object) -> None:
    _write(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
