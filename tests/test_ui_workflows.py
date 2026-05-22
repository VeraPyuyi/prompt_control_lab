from __future__ import annotations

import json
import subprocess
import zipfile
from pathlib import Path

from promptcontrollab.cli import main
from promptcontrollab.files import JsonDict, read_json
from promptcontrollab.ui.data import load_run_detail
from promptcontrollab.ui.workflows import (
    build_agent_run_workflow,
    export_report_zip_workflow,
    run_analyze_workflow,
    run_audit_workflow,
    run_gate_workflow,
    run_guard_workflow,
    run_pr_summary_workflow,
)


def test_guard_workflow_preview_auto_and_command_modes(tmp_path: Path) -> None:
    out_dir = tmp_path / "runs" / "guard"

    preview = run_guard_workflow(
        prompt="Fix this bug",
        out_dir=out_dir,
        execution_mode="confirm",
        confirmed=False,
        overwrite=False,
    )

    assert preview["status"] == "preview"
    assert not (out_dir / "guard_result.json").exists()

    command = run_guard_workflow(
        prompt="Fix this bug",
        out_dir=out_dir,
        execution_mode="command",
        confirmed=False,
        overwrite=False,
    )

    assert command["status"] == "command"
    assert "pcl guard" in command["command"]
    assert not (out_dir / "guard_result.json").exists()

    result = run_guard_workflow(
        prompt="Fix this bug",
        out_dir=out_dir,
        execution_mode="auto",
        confirmed=False,
        overwrite=False,
    )

    assert result["status"] == "completed"
    assert (out_dir / "guard_result.json").exists()
    assert (out_dir / "improved_prompt.txt").exists()
    assert (out_dir / "guarded_prompt.txt").exists()


def test_analyze_gate_agent_pr_and_zip_workflows(tmp_path: Path) -> None:
    data, baseline, candidate = _example_eval_files(tmp_path)
    run_dir = tmp_path / "runs" / "quick"
    gate_policy = tmp_path / "gate.policy.yaml"
    gate_policy.write_text("min_candidate_score: 0.5\n", encoding="utf-8")

    analyze = run_analyze_workflow(
        data_path=data,
        baseline_predictions_path=baseline,
        candidate_predictions_path=candidate,
        out_dir=run_dir,
        execution_mode="auto",
        confirmed=False,
        overwrite=False,
        bootstrap_samples=10,
        permutation_samples=10,
    )

    assert analyze["status"] == "completed"
    detail = load_run_detail(run_dir)
    assert detail["candidate_score"] == 1.0
    assert (run_dir / "report.html").exists()

    gate = run_gate_workflow(
        run_dir=run_dir,
        policy_path=gate_policy,
        execution_mode="auto",
        confirmed=False,
        overwrite=True,
    )

    assert gate["status"] == "completed"
    assert read_json(run_dir / "gate_result.json")["status"] == "pass"

    audit_dir = _make_audit_run(tmp_path)
    agent_run = build_agent_run_workflow(
        run_dir=run_dir,
        audit_dir=audit_dir,
        agent="codex",
        out_path=run_dir / "agent_run.json",
        execution_mode="auto",
        confirmed=False,
        overwrite=False,
        policy=str(gate_policy),
    )

    payload = read_json(run_dir / "agent_run.json")
    assert agent_run["status"] == "completed"
    assert payload["schema"] == "prompt_control_lab.agent_run.v1"
    assert payload["created_at"]
    assert payload["repo"]
    assert payload["commit_before"] == "HEAD~1"
    assert payload["commit_after"] == "HEAD"
    assert payload["prompt"] == {}
    assert payload["gate"]["status"] == "pass"
    assert payload["audit"]["tests_run"] == ["pytest"]
    assert payload["review_required"] is False
    assert payload["policy_detail"]["policy_file"] == str(gate_policy)
    assert str(payload["policy_detail"]["policy_hash"]).startswith("sha256:")

    summary = run_pr_summary_workflow(
        audit_path=audit_dir / "audit_result.json",
        gate_path=run_dir / "gate_result.json",
        agent_run_path=run_dir / "agent_run.json",
        markdown_path=run_dir / "pr_summary.md",
        json_path=run_dir / "pr_summary.json",
        execution_mode="auto",
        confirmed=False,
        overwrite=False,
    )

    assert summary["status"] == "completed"
    assert read_json(run_dir / "pr_summary.json")["status"] == "pass"

    _write(run_dir / "src.py", "print('not an artifact')\n")
    exported = export_report_zip_workflow(
        run_dir=run_dir,
        zip_path=tmp_path / "report.zip",
        execution_mode="auto",
        confirmed=False,
        overwrite=False,
    )

    assert exported["status"] == "completed"
    with zipfile.ZipFile(tmp_path / "report.zip") as archive:
        names = set(archive.namelist())
    assert "manifest.json" in names
    assert "report.html" in names
    assert "agent_run.json" in names
    assert "src.py" not in names


def test_audit_workflow_records_tests_without_running_shell(tmp_path: Path) -> None:
    repo = _make_git_repo(tmp_path)
    _write(repo / "src" / "app.py", "def old() -> int:\n    return 1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    _write(repo / "src" / "app.py", "def old() -> int:\n    return 2\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "change")
    out_dir = repo / "runs" / "audit"

    result = run_audit_workflow(
        repo=repo,
        before="HEAD~1",
        after="HEAD",
        out_dir=out_dir,
        execution_mode="auto",
        confirmed=False,
        overwrite=False,
        tests_run=["pytest"],
        tests_passed=True,
    )

    payload = read_json(out_dir / "audit_result.json")
    assert result["status"] == "completed"
    assert payload["tests_run"] == ["pytest"]
    assert payload["tests_passed"] is True
    assert payload["test_results"] == []


def test_pr_summary_workflow_without_artifacts_needs_review(tmp_path: Path) -> None:
    result = run_pr_summary_workflow(
        audit_path=None,
        gate_path=None,
        agent_run_path=None,
        markdown_path=tmp_path / "pr_summary.md",
        json_path=tmp_path / "pr_summary.json",
        execution_mode="auto",
        confirmed=False,
        overwrite=False,
    )

    assert result["status"] == "completed"
    assert read_json(tmp_path / "pr_summary.json")["status"] == "needs_review"


def test_cli_export_report_zip_contains_known_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "quick"
    _write_json(run_dir / "manifest.json", {"mode": "quick"})
    _write(run_dir / "report.md", "# report\n")
    _write_json(run_dir / "diagnostics" / "trajectory.json", {"drift": 0.2})
    _write(run_dir / "src.py", "print('not an artifact')\n")
    zip_path = tmp_path / "report.zip"

    assert main(["export-report", "--run", str(run_dir), "--out", str(zip_path)]) == 0

    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    assert names == {"diagnostics/trajectory.json", "manifest.json", "report.md"}


def _example_eval_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    data = tmp_path / "tasks.jsonl"
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    _write(
        data,
        "\n".join(
            [
                '{"id":"a","input":"1+1","expected":"2","slice":"math"}',
                '{"id":"b","input":"label","expected":"OK","slice":"format"}',
            ]
        )
        + "\n",
    )
    _write(baseline, '{"id":"a","output":"1"}\n{"id":"b","output":"OK"}\n')
    _write(candidate, '{"id":"a","output":"2"}\n{"id":"b","output":"OK"}\n')
    return data, baseline, candidate


def _make_audit_run(tmp_path: Path) -> Path:
    audit_dir = tmp_path / "runs" / "audit"
    _write_json(
        audit_dir / "audit_result.json",
        {
            "before": "HEAD~1",
            "after": "HEAD",
            "repo": str(tmp_path),
            "changed_files": ["src/app.py"],
            "tests_run": ["pytest"],
            "tests_passed": True,
            "human_review_required": False,
        },
    )
    return audit_dir


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


def _write_json(path: Path, payload: JsonDict) -> None:
    _write(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
