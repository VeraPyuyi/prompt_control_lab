from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from promptcontrollab import doctor
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


def test_cli_audit_diff_uses_project_config_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _make_git_repo(tmp_path)
    _write(repo / "src" / "app.py", "def existing() -> str:\n    return 'ok'\n")
    _write(repo / "README.md", "# demo\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")

    _write(repo / "src" / "app.py", "def existing() -> str:\n    return 'changed'\n")
    _write(repo / "docs" / "guide.md", "changed\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "agent changes")
    (repo / ".promptcontrol.yaml").write_text(
        "\n".join(
            [
                "expected_paths:",
                "  - src",
                "test_commands:",
                f"  - \"{sys.executable}\" --version",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(repo)

    out = repo / "runs" / "audit"
    assert (
        main(
            [
                "audit-diff",
                "--before",
                "HEAD~1",
                "--after",
                "HEAD",
                "--out",
                str(out),
            ]
        )
        == 0
    )

    payload = json.loads((out / "audit_result.json").read_text(encoding="utf-8"))
    assert payload["expected_paths"] == ["src"]
    assert payload["unexpected_files"] == ["docs/guide.md"]
    assert payload["tests_run"]
    assert payload["tests_passed"] is True


def test_cli_audit_diff_does_not_treat_tests_or_docs_as_public_api(tmp_path: Path) -> None:
    repo = _make_git_repo(tmp_path)
    _write(repo / "README.md", "# demo\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")

    _write(repo / "tests" / "test_app.py", "def test_public_behavior():\n    assert True\n")
    _write(repo / "docs" / "api.md", "```python\ndef public_example():\n    return True\n```\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "docs and tests")

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
            ]
        )
        == 0
    )

    payload = json.loads((out / "audit_result.json").read_text(encoding="utf-8"))
    assert payload["public_api_changed"] is False
    assert payload["human_review_required"] is False


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
                "--test-timeout",
                "30",
            ]
        )
        == 0
    )

    payload = json.loads((out / "audit_result.json").read_text(encoding="utf-8"))
    assert payload["tests_run"] == [command]
    assert payload["tests_passed"] is True
    assert payload["unnecessary_file_edits"] is None
    assert payload["test_results"][0]["returncode"] == 0
    assert payload["test_results"][0]["timeout_seconds"] == 30


def test_cli_audit_diff_invalid_ref_reports_friendly_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _make_git_repo(tmp_path)
    _write(repo / "src" / "app.py", "def existing() -> str:\n    return 'ok'\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")

    assert (
        main(
            [
                "audit-diff",
                "--repo",
                str(repo),
                "--before",
                "missing-ref",
                "--after",
                "HEAD",
                "--out",
                str(repo / "runs" / "audit"),
            ]
        )
        == 2
    )

    captured = capsys.readouterr()
    assert captured.err.startswith("pcl: error:")
    assert "git diff" in captured.err
    assert "Traceback" not in captured.err


def test_cli_audit_diff_rejects_shell_test_command_without_opt_in(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _make_git_repo(tmp_path)
    _write(repo / "src" / "app.py", "def existing() -> str:\n    return 'ok'\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    _write(repo / "src" / "app.py", "def existing() -> str:\n    return 'changed'\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "change")

    command = f'"{sys.executable}" -c "import sys; sys.exit(0)" && echo unsafe'
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
                str(repo / "runs" / "audit"),
                "--test-command",
                command,
            ]
        )
        == 2
    )

    captured = capsys.readouterr()
    assert "--allow-shell-test-command" in captured.err


def test_cli_audit_diff_reports_industrial_review_signals(tmp_path: Path) -> None:
    repo = _make_git_repo(tmp_path)
    _write(repo / "src" / "app.py", "def existing() -> str:\n    return 'ok'\n")
    _write(repo / "tests" / "test_old.py", "def test_old():\n    assert True\n")
    _write(repo / "pyproject.toml", "[project]\nname = 'demo'\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")

    _write(
        repo / "src" / "app.py",
        "def existing() -> str:\n    return 'changed'\n\nAPI_TOKEN = 'sk-test-1234567890abcdef'\n",
    )
    _write(repo / "pyproject.toml", "[project]\nname = 'demo'\ndependencies = ['pytest']\n")
    _write(repo / "uv.lock", "version = 1\n")
    _write(repo / ".github" / "workflows" / "pcl.yml", "name: pcl\n")
    (repo / "tests" / "test_old.py").unlink()
    _write(repo / "dist" / "bundle.min.js", "generated();\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "industrial signals")

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
                "--tests-run",
                "pytest",
                "--tests-passed",
                "true",
            ]
        )
        == 0
    )

    payload = json.loads((out / "audit_result.json").read_text(encoding="utf-8"))
    assert payload["changed_lines"]["src/app.py"]["added"] >= 2
    assert payload["changed_lines"]["tests/test_old.py"]["deleted"] >= 1
    assert payload["dependency_files_changed"] == ["pyproject.toml"]
    assert payload["lockfiles_changed"] == ["uv.lock"]
    assert payload["workflow_files_changed"] == [".github/workflows/pcl.yml"]
    assert payload["deleted_test_files"] == ["tests/test_old.py"]
    assert payload["generated_files_changed"] == ["dist/bundle.min.js"]
    assert payload["secret_findings"]
    assert payload["secret_findings"][0]["path"] == "src/app.py"
    assert "sk-test-1234567890abcdef" not in json.dumps(payload["secret_findings"])
    assert payload["human_review_required"] is True


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
    _write_json(
        new / "audit_result.json",
        {
            "human_review_required": True,
            "secret_findings": [{"path": "src/app.py", "kind": "secret_like"}],
            "workflow_files_changed": [".github/workflows/ci.yml"],
        },
    )
    _write_json(
        new / "agent_run.json",
        {"risk_level": "high", "review_required": True, "agent": "codex"},
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
    assert compare["new_risk_categories"] == ["model_mismatch", "secret", "workflow"]
    new_summary = next(item for item in index["runs"] if item["run_name"] == "new")
    assert new_summary["risk_level"] == "high"
    assert new_summary["review_required"] is True
    assert new_summary["human_review_required"] is True


def test_history_index_reads_quick_mode_candidate_metrics(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    quick = runs / "quick"
    _write_json(
        quick / "manifest.json",
        {"candidate_model": {"provider": "openai", "model_id": "gpt-5.2"}},
    )
    _write_json(
        quick / "candidate" / "metrics.json",
        {"mean_score": 0.92, "by_slice": {"math": 1.0, "format": 0.8}},
    )

    index_out = runs / "history_index.json"
    assert main(["history", "index", "--runs", str(runs), "--out", str(index_out)]) == 0

    payload = json.loads(index_out.read_text(encoding="utf-8"))
    assert payload["runs"][0]["mean_score"] == 0.92
    assert payload["runs"][0]["by_slice"] == {"math": 1.0, "format": 0.8}
    assert payload["runs"][0]["agent_run"] == {}


def test_cli_doctor_json_outputs_stable_checks(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["doctor", "--json"]) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    names = {item["name"] for item in payload["checks"]}
    assert payload["status"] in {"pass", "warning", "fail"}
    assert {"python_version", "package_import", "cli_parser", "guard_policy"}.issubset(names)
    assert "optional_research_dependencies" in names


def test_doctor_python_version_fails_below_supported_minimum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("promptcontrollab.doctor.sys.version_info", (3, 9, 18))

    payload = doctor._check_python_version()

    assert payload["status"] == "fail"
    assert "requires Python >=3.10" in payload["message"]


def test_github_action_example_exists_and_uses_real_cli() -> None:
    action = Path("examples/github-action/prompt-control-lab-gate.yml")
    text = action.read_text(encoding="utf-8")
    assert "on:" in text
    assert "pull_request" in text
    assert "pcl analyze --config promptcontrol.example.yaml --out runs/quick" in text
    assert "pcl gate --run runs/quick --policy examples/gate.policy.yaml" in text
    assert "pcl audit-diff" in text
    assert "gate_result.json was not found" in text
    assert "cat > runs/quick/manifest.json" in text
    assert "[ -f runs/quick/candidate/metrics.json ]" in text
    assert "actions/github-script" in text

    template = Path("src/promptcontrollab/template_data/github_action/prompt-control-lab-gate.yml")
    template_text = template.read_text(encoding="utf-8")
    assert "cat > runs/quick/manifest.json" in template_text
    assert "[ -f runs/quick/candidate/metrics.json ]" in template_text


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
