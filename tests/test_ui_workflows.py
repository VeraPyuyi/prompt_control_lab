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
    create_demo_artifacts_workflow,
    export_report_zip_workflow,
    run_analyze_workflow,
    run_audit_workflow,
    run_evidence_card_workflow,
    run_external_evidence_workflow,
    run_gate_workflow,
    run_guard_workflow,
    run_import_external_workflow,
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


def test_workflow_path_guard_blocks_auto_outside_runs_root(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    outside = tmp_path / "outside" / "guard"

    preview = run_guard_workflow(
        prompt="Fix this bug",
        out_dir=outside,
        execution_mode="confirm",
        confirmed=False,
        overwrite=False,
        safe_root=runs_dir,
        allow_external_outputs=False,
    )

    assert preview["status"] == "preview"
    assert preview["path_warnings"]

    command = run_guard_workflow(
        prompt="Fix this bug",
        out_dir=outside,
        execution_mode="command",
        confirmed=False,
        overwrite=False,
        safe_root=runs_dir,
        allow_external_outputs=False,
    )

    assert command["status"] == "command"
    assert command["path_warnings"]

    try:
        run_guard_workflow(
            prompt="Fix this bug",
            out_dir=outside,
            execution_mode="auto",
            confirmed=False,
            overwrite=False,
            safe_root=runs_dir,
            allow_external_outputs=False,
        )
    except ValueError as exc:
        assert "outside the configured runs directory" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected external output path to be blocked in auto mode.")

    allowed = run_guard_workflow(
        prompt="Fix this bug",
        out_dir=outside,
        execution_mode="auto",
        confirmed=False,
        overwrite=False,
        safe_root=runs_dir,
        allow_external_outputs=True,
    )

    assert allowed["status"] == "completed"
    assert (outside / "guard_result.json").exists()


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
    assert (run_dir / "evidence_card.json").exists()
    assert (run_dir / "evidence_card.md").exists()
    assert (run_dir / "evidence_card.html").exists()
    assert (run_dir / "claim_check.json").exists()
    assert (run_dir / "claim_check.html").exists()
    assert (run_dir / "report.html").exists()

    gate = run_gate_workflow(
        run_dir=run_dir,
        policy_path=gate_policy,
        execution_mode="auto",
        confirmed=False,
        overwrite=True,
    )

    assert gate["status"] == "completed"
    assert read_json(run_dir / "gate_result.json")["status"] == "needs_review"

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
    assert payload["gate"]["status"] == "needs_review"
    assert payload["audit"]["tests_run"] == ["pytest"]
    assert payload["review_required"] is True
    assert payload["policy_detail"]["policy_file"] == str(gate_policy)
    assert str(payload["policy_detail"]["policy_hash"]).startswith("sha256:")
    assert payload["policy_detail"]["path"] == str(gate_policy)
    assert str(payload["policy_detail"]["sha256"]).startswith("sha256:")
    assert payload["policy_detail"]["exists"] is True

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
    assert read_json(run_dir / "pr_summary.json")["status"] == "needs_review"

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
    assert "evidence_card.json" in names
    assert "evidence_card.md" in names
    assert "evidence_card.html" in names
    assert "claim_check.json" in names
    assert "claim_check.html" in names
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


def test_evidence_card_workflow_preview_command_and_auto_modes(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "quick"
    _write_json(run_dir / "stats.json", {"comparisons": [{"mean_delta": 0.2}]})

    preview = run_evidence_card_workflow(
        run_dir=run_dir,
        markdown_path=None,
        json_path=None,
        execution_mode="confirm",
        confirmed=False,
        overwrite=False,
        safe_root=tmp_path / "runs",
    )
    assert preview["status"] == "preview"
    assert "pcl evidence-card" in preview["command"]
    assert not (run_dir / "evidence_card.json").exists()

    command = run_evidence_card_workflow(
        run_dir=run_dir,
        markdown_path=None,
        json_path=None,
        execution_mode="command",
        confirmed=False,
        overwrite=False,
        safe_root=tmp_path / "runs",
    )
    assert command["status"] == "command"
    assert "evidence_card.md" in command["command"]

    result = run_evidence_card_workflow(
        run_dir=run_dir,
        markdown_path=None,
        json_path=None,
        execution_mode="auto",
        confirmed=False,
        overwrite=False,
        safe_root=tmp_path / "runs",
    )
    assert result["status"] == "completed"
    assert (run_dir / "evidence_card.json").exists()
    assert (run_dir / "evidence_card.md").exists()


def test_external_evidence_workflow_preview_and_auto_modes(tmp_path: Path) -> None:
    source = tmp_path / "promptfoo-results.json"
    source.write_text(json.dumps(_paired_promptfoo_payload(count=20)), encoding="utf-8")
    out_dir = tmp_path / "runs" / "external-evidence"

    preview = run_external_evidence_workflow(
        tool="promptfoo",
        baseline_input=source,
        candidate_input=source,
        out_dir=out_dir,
        execution_mode="confirm",
        confirmed=False,
        overwrite=False,
        provider="openai:gpt-4o-mini-20260601",
        baseline_prompt_id="baseline",
        candidate_prompt_id="candidate",
        split_hash="split-ui-123",
        bootstrap_samples=20,
        permutation_samples=100,
        safe_root=tmp_path / "runs",
    )

    assert preview["status"] == "preview"
    assert "pcl evidence-from" in preview["command"]
    assert str(out_dir / "research_diagnostics.md") in preview["outputs"]
    assert str(out_dir / "research_bundle.html") in preview["outputs"]
    assert str(out_dir / "research_diagnostics.html") in preview["outputs"]
    assert str(out_dir / "research_gap_plan.html") in preview["outputs"]
    assert not (out_dir / "evidence_from_result.json").exists()

    result = run_external_evidence_workflow(
        tool="promptfoo",
        baseline_input=source,
        candidate_input=source,
        out_dir=out_dir,
        execution_mode="auto",
        confirmed=False,
        overwrite=False,
        provider="openai:gpt-4o-mini-20260601",
        baseline_prompt_id="baseline",
        candidate_prompt_id="candidate",
        split_hash="split-ui-123",
        bootstrap_samples=20,
        permutation_samples=100,
        safe_root=tmp_path / "runs",
    )

    assert result["status"] == "completed"
    assert result["external_evidence"]["kind"] == "external_evidence"
    assert (out_dir / "evidence_from_result.json").exists()
    assert (out_dir / "evidence_card.md").exists()
    assert (out_dir / "claim_check.md").exists()
    assert (out_dir / "research_bundle.html").exists()
    assert (out_dir / "research_diagnostics.md").exists()
    assert (out_dir / "research_diagnostics.html").exists()
    assert (out_dir / "research_gap_plan.html").exists()
    assert (out_dir / "report.html").exists()
    validity = read_json(out_dir / "comparison" / "comparison_validity.json")
    assert validity["validity"] == "clean"


def test_import_external_workflow_preview_and_auto_modes(tmp_path: Path) -> None:
    source = tmp_path / "promptfoo-results.json"
    source.write_text(json.dumps(_paired_promptfoo_payload(count=2)), encoding="utf-8")
    out_dir = tmp_path / "runs" / "from-promptfoo"

    preview = run_import_external_workflow(
        tool="promptfoo",
        input_path=source,
        out_dir=out_dir,
        execution_mode="confirm",
        confirmed=False,
        overwrite=False,
        prompt_id="candidate",
        safe_root=tmp_path / "runs",
    )

    assert preview["status"] == "preview"
    assert "pcl import promptfoo" in preview["command"]
    assert str(out_dir / "manifest.json") in preview["outputs"]
    assert not (out_dir / "manifest.json").exists()

    result = run_import_external_workflow(
        tool="promptfoo",
        input_path=source,
        out_dir=out_dir,
        execution_mode="auto",
        confirmed=False,
        overwrite=False,
        prompt_id="candidate",
        safe_root=tmp_path / "runs",
    )

    assert result["status"] == "completed"
    assert result["import_result"]["count"] == 2
    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "predictions.jsonl").exists()
    assert read_json(out_dir / "manifest.json")["source_tool"] == "promptfoo"


def test_create_demo_artifacts_workflow_generates_demo_run(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"

    result = create_demo_artifacts_workflow(
        runs_dir=runs_dir,
        execution_mode="auto",
        confirmed=False,
        overwrite=False,
    )

    assert result["status"] == "completed"
    assert (runs_dir / "demo" / "manifest.json").exists()
    assert (runs_dir / "demo" / "evidence_card.json").exists()
    assert (runs_dir / "demo" / "claim_check.json").exists()
    assert (runs_dir / "demo" / "report.html").exists()
    assert (runs_dir / "_demo_project" / "promptcontrol.example.yaml").exists()


def test_cli_export_report_zip_contains_known_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "quick"
    _write_json(run_dir / "manifest.json", {"mode": "quick"})
    _write_json(run_dir / "evidence_card.json", {"recommendation": "needs_review"})
    _write(run_dir / "evidence_card.md", "# evidence\n")
    _write(run_dir / "evidence_card.html", "<h1>evidence</h1>\n")
    _write_json(run_dir / "claim_check.json", {"status": "pass"})
    _write(run_dir / "claim_check.md", "# claim\n")
    _write(run_dir / "claim_check.html", "<h1>claim</h1>\n")
    _write_json(run_dir / "research_bundle.json", {"kind": "research_bundle_index"})
    _write(run_dir / "research_bundle.html", "<h1>bundle</h1>\n")
    _write_json(
        run_dir / "research_bundle_verification.json",
        {"kind": "research_bundle_verification"},
    )
    _write(run_dir / "research_bundle_verification.md", "# verification\n")
    _write(run_dir / "research_bundle_verification.html", "<h1>verification</h1>\n")
    _write_json(run_dir / "research_gap_plan.json", {"kind": "research_gap_plan"})
    _write(run_dir / "research_gap_plan.md", "# gap plan\n")
    _write(run_dir / "research_gap_plan.html", "<h1>gap plan</h1>\n")
    _write(run_dir / "research_gap_commands.ps1", "exit 1\n")
    _write(run_dir / "research_gap_commands.sh", "exit 1\n")
    _write_json(run_dir / "research_gap_status.json", {"kind": "research_gap_status"})
    _write(run_dir / "research_gap_status.md", "# gap status\n")
    _write(run_dir / "research_gap_status.html", "<h1>gap status</h1>\n")
    _write(run_dir / "research_diagnostics.html", "<h1>diagnostics</h1>\n")
    _write(run_dir / "report.md", "# report\n")
    _write_json(run_dir / "diagnostics" / "trajectory.json", {"drift": 0.2})
    _write(run_dir / "src.py", "print('not an artifact')\n")
    zip_path = tmp_path / "report.zip"

    assert main(["export-report", "--run", str(run_dir), "--out", str(zip_path)]) == 0

    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    assert names == {
        "diagnostics/trajectory.json",
        "evidence_card.json",
        "evidence_card.md",
        "evidence_card.html",
        "claim_check.json",
        "claim_check.md",
        "claim_check.html",
        "manifest.json",
        "research_bundle.json",
        "research_bundle.html",
        "research_bundle_verification.json",
        "research_bundle_verification.md",
        "research_bundle_verification.html",
        "research_diagnostics.html",
        "research_gap_commands.ps1",
        "research_gap_commands.sh",
        "research_gap_plan.json",
        "research_gap_plan.md",
        "research_gap_plan.html",
        "research_gap_status.json",
        "research_gap_status.md",
        "research_gap_status.html",
        "report.md",
    }


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


def _paired_promptfoo_payload(*, count: int) -> JsonDict:
    provider = "openai:gpt-4o-mini-20260601"
    results: list[JsonDict] = []
    for index in range(count):
        expected = str(index + 1)
        test_case: JsonDict = {
            "vars": {"slice": "demo", "question": f"{index}+1"},
            "assert": [{"type": "equals", "value": expected}],
        }
        results.append(
            {
                "promptId": "baseline",
                "provider": {"id": provider, "label": "OpenAI mini pinned"},
                "testIdx": index,
                "testCase": test_case,
                "response": {"output": "wrong"},
                "success": False,
                "score": 0,
            }
        )
        results.append(
            {
                "promptId": "candidate",
                "provider": {"id": provider, "label": "OpenAI mini pinned"},
                "testIdx": index,
                "testCase": test_case,
                "response": {"output": expected},
                "success": True,
                "score": 1,
            }
        )
    return {
        "version": 3,
        "timestamp": "2026-06-13T00:00:00Z",
        "prompts": [
            {"id": "baseline", "raw": "Answer the question.", "label": "Baseline"},
            {
                "id": "candidate",
                "raw": "Answer with only the final result.",
                "label": "Candidate",
            },
        ],
        "results": results,
    }
