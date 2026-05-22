from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from promptcontrollab.cli import main
from promptcontrollab.files import JsonDict
from promptcontrollab.github_app import (
    _HttpGithubClient,
    handle_pull_request_payload,
    summarize_pull_files,
    verify_webhook_signature,
)
from promptcontrollab.report_model import ReportModel


def test_cli_analyze_writes_prompt_identity(tmp_path: Path) -> None:
    data = tmp_path / "tasks.jsonl"
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    prompt_file = tmp_path / "prompt.txt"
    _write(
        data,
        '\n'.join(
            [
                '{"id":"a","input":"1+1","expected":"2","slice":"math"}',
                '{"id":"b","input":"label","expected":"OK","slice":"format"}',
            ]
        )
        + "\n",
    )
    _write(baseline, '{"id":"a","output":"1"}\n{"id":"b","output":"OK"}\n')
    _write(candidate, '{"id":"a","output":"2"}\n{"id":"b","output":"OK"}\n')
    _write(prompt_file, "Answer exactly.\n")
    out = tmp_path / "runs" / "quick"

    assert (
        main(
            [
                "analyze",
                "--data",
                str(data),
                "--baseline-predictions",
                str(baseline),
                "--candidate-predictions",
                str(candidate),
                "--out",
                str(out),
                "--prompt-id",
                "math-format-v1",
                "--prompt-file",
                str(prompt_file),
                "--prompt-version",
                "v1",
                "--bootstrap-samples",
                "10",
                "--permutation-samples",
                "10",
            ]
        )
        == 0
    )

    manifest = _read_json(out / "manifest.json")
    assert manifest["prompt"]["prompt_id"] == "math-format-v1"
    assert manifest["prompt"]["prompt_file"] == str(prompt_file)
    assert manifest["prompt"]["prompt_version"] == "v1"
    assert str(manifest["prompt"]["prompt_hash"]).startswith("sha256:")


def test_agent_run_build_and_report_model(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "quick"
    audit = tmp_path / "runs" / "audit"
    _write_json(
        run / "manifest.json",
        {
            "prompt": {"prompt_hash": "sha256:abc", "prompt_id": "demo"},
            "candidate_model": {"provider": "openai", "model_id": "gpt-5.2"},
        },
    )
    _write_json(run / "candidate" / "metrics.json", {"mean_score": 0.9})
    _write_json(run / "gate_result.json", {"status": "needs_review"})
    _write_json(
        audit / "audit_result.json",
        {
            "changed_files": ["src/app.py"],
            "tests_run": ["pytest"],
            "tests_passed": True,
            "human_review_required": True,
            "dangerous_paths": [],
        },
    )
    out = tmp_path / "runs" / "agent_run.json"

    assert (
        main(
            [
                "agent-run",
                "build",
                "--run",
                str(run),
                "--audit",
                str(audit),
                "--agent",
                "codex",
                "--out",
                str(out),
            ]
        )
        == 0
    )

    payload = _read_json(out)
    assert payload["agent"] == "codex"
    assert payload["prompt_hash"] == "sha256:abc"
    assert payload["provider"] == "openai"
    assert payload["model"] == "gpt-5.2"
    assert payload["decision"] == "needs_review"
    assert payload["changed_files"] == ["src/app.py"]
    assert payload["human_review_required"] is True

    (run / "agent_run.json").write_text(out.read_text(encoding="utf-8"), encoding="utf-8")
    model = ReportModel.from_run(run)
    assert model.agent_run["agent"] == "codex"
    assert model.candidate_score == 0.9
    assert model.gate["status"] == "needs_review"


def test_agent_run_promotes_high_risk_audit_findings(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "quick"
    audit = tmp_path / "runs" / "audit"
    _write_json(
        run / "manifest.json",
        {"candidate_model": {"provider": "openai", "model_id": "gpt-5.2"}},
    )
    _write_json(run / "gate_result.json", {"status": "pass"})
    _write_json(
        audit / "audit_result.json",
        {
            "changed_files": [".github/workflows/ci.yml"],
            "tests_run": ["pytest"],
            "tests_passed": True,
            "human_review_required": True,
            "secret_findings": [{"path": "src/app.py", "kind": "secret_like"}],
            "dangerous_paths": [],
            "workflow_files_changed": [".github/workflows/ci.yml"],
            "deleted_test_files": [],
        },
    )
    out = tmp_path / "agent_run.json"

    assert (
        main(
            [
                "agent-run",
                "build",
                "--run",
                str(run),
                "--audit",
                str(audit),
                "--agent",
                "codex",
                "--out",
                str(out),
            ]
        )
        == 0
    )

    assert _read_json(out)["risk_level"] == "high"


def test_pr_summary_cli_and_github_app_helpers(tmp_path: Path) -> None:
    audit = tmp_path / "audit_result.json"
    gate = tmp_path / "gate_result.json"
    agent_run = tmp_path / "agent_run.json"
    _write_json(
        audit,
        {
            "human_review_required": True,
            "dangerous_paths": ["auth/session.py"],
            "tests_run": [],
            "tests_passed": None,
            "secret_findings": [{"path": "src/app.py", "kind": "token", "redacted": "***"}],
        },
    )
    _write_json(gate, {"status": "fail", "plain_summary": "Candidate failed policy."})
    _write_json(agent_run, {"agent": "codex", "model": "gpt-5.2"})
    md = tmp_path / "summary.md"
    js = tmp_path / "summary.json"

    assert (
        main(
            [
                "pr-summary",
                "--audit",
                str(audit),
                "--gate",
                str(gate),
                "--agent-run",
                str(agent_run),
                "--out",
                str(md),
                "--json-out",
                str(js),
            ]
        )
        == 0
    )

    payload = _read_json(js)
    assert payload["status"] == "fail"
    assert "prompt-control-lab:needs-review" in payload["labels"]
    assert "prompt-control-lab:gate-failed" in payload["labels"]
    assert "auth/session.py" in md.read_text(encoding="utf-8")

    body = b'{"action":"opened"}'
    secret = "webhook-secret"
    signature = _hmac_header(secret, body)
    assert verify_webhook_signature(secret, body, signature) is True
    assert verify_webhook_signature(secret, body, "sha256=bad") is False

    fake = _FakeGithubClient()
    handle_pull_request_payload(
        {
            "action": "opened",
            "repository": {"full_name": "owner/repo"},
            "pull_request": {"number": 7, "head": {"sha": "abc"}},
        },
        client=fake,
        summary=payload,
    )
    assert fake.comments[0]["number"] == 7
    assert "PromptControlLab PR Summary" in cast(str, fake.comments[0]["body"])
    assert "prompt-control-lab:needs-review" in cast(list[str], fake.labels[0]["labels"])
    assert fake.checks[0]["conclusion"] == "failure"


def test_pr_summary_without_artifacts_requires_review(tmp_path: Path) -> None:
    js = tmp_path / "summary.json"

    assert main(["pr-summary", "--json-out", str(js)]) == 0

    payload = _read_json(js)
    assert payload["status"] == "needs_review"
    assert "No PromptControlLab artifacts were provided." in payload["reasons"]


def test_github_app_upserts_existing_summary_comment() -> None:
    fake = _FakeGithubClient()
    fake.existing_comments.append(
        {
            "id": 42,
            "user": {"type": "Bot"},
            "body": "<!-- prompt-control-lab-summary -->\nold",
        }
    )

    result = handle_pull_request_payload(
        {
            "action": "synchronize",
            "repository": {"full_name": "owner/repo"},
            "pull_request": {"number": 7, "head": {"sha": "abc"}},
        },
        client=fake,
        summary={"status": "pass", "reasons": ["ok"], "labels": []},
    )

    assert result["handled"] is True
    assert fake.comments == []
    assert fake.updated_comments == [
        {"repo": "owner/repo", "comment_id": 42, "body": fake.last_body}
    ]
    assert "<!-- prompt-control-lab-summary -->" in fake.last_body


def test_github_app_pull_files_are_paginated() -> None:
    client = cast(Any, object.__new__(_HttpGithubClient))
    client.httpx = _FakeHttpx(
        [
            [{"filename": f"src/file_{index}.py"} for index in range(100)],
            [{"filename": "src/file_100.py"}],
        ]
    )
    client._installation_token = lambda: "token"

    files = client.list_pull_files("owner/repo", 12)

    assert len(files) == 101
    assert client.httpx.pages_seen == [1, 2]


def test_summarize_pull_files_only_requires_tests_for_source_changes() -> None:
    docs_summary = summarize_pull_files(
        [{"filename": "docs/deployment.md", "patch": "+clarify production deployment"}]
    )
    assert docs_summary["status"] == "pass"
    assert "prompt-control-lab:missing-tests" not in docs_summary["labels"]

    source_summary = summarize_pull_files([{"filename": "src/app.py", "patch": "+return 1"}])
    assert source_summary["status"] == "needs_review"
    assert "prompt-control-lab:missing-tests" in source_summary["labels"]

    workflow_summary = summarize_pull_files(
        [{"filename": ".github/workflows/ci.yml", "patch": "+name: CI"}]
    )
    assert workflow_summary["status"] == "needs_review"
    assert "prompt-control-lab:workflow-change" in workflow_summary["labels"]
    assert "prompt-control-lab:missing-tests" not in workflow_summary["labels"]


def test_install_plugin_writes_templates_without_overwrite(tmp_path: Path) -> None:
    codex_target = tmp_path / "codex-skill"
    assert main(["install-plugin", "codex", "--target", str(codex_target)]) == 0
    skill = codex_target / "SKILL.md"
    assert skill.exists()
    original = skill.read_text(encoding="utf-8")

    skill.write_text("custom\n", encoding="utf-8")
    assert main(["install-plugin", "codex", "--target", str(codex_target)]) == 2
    assert skill.read_text(encoding="utf-8") == "custom\n"
    assert main(["install-plugin", "codex", "--target", str(codex_target), "--force"]) == 0
    assert skill.read_text(encoding="utf-8") == original

    action_target = tmp_path / "workflow.yml"
    assert main(["install-plugin", "github-action", "--target", str(action_target)]) == 0
    assert "PromptControlLab Gate" in action_target.read_text(encoding="utf-8")


def test_install_plugin_all_uses_target_as_root(tmp_path: Path) -> None:
    target = tmp_path / "templates"

    assert main(["install-plugin", "all", "--target", str(target)]) == 0

    assert (target / "codex" / "SKILL.md").exists()
    assert (target / "cursor" / "prompt_control_lab.mdc").exists()
    assert (target / "claude-code" / "prompt_guard.py").exists()
    assert (target / "github-action" / "prompt-control-lab-gate.yml").exists()


class _FakeGithubClient:
    def __init__(self) -> None:
        self.comments: list[dict[str, object]] = []
        self.existing_comments: list[JsonDict] = []
        self.updated_comments: list[dict[str, object]] = []
        self.labels: list[dict[str, object]] = []
        self.checks: list[dict[str, object]] = []
        self.last_body = ""

    def list_pull_files(self, repo: str, number: int) -> list[JsonDict]:
        return [
            {"filename": "auth/session.py", "patch": "+TOKEN = 'secret'"},
            {"filename": "src/app.py", "patch": "+print('ok')"},
        ]

    def create_comment(self, repo: str, number: int, body: str) -> None:
        self.last_body = body
        self.comments.append({"repo": repo, "number": number, "body": body})

    def list_comments(self, repo: str, number: int) -> list[JsonDict]:
        return self.existing_comments

    def update_comment(self, repo: str, comment_id: int, body: str) -> None:
        self.last_body = body
        self.updated_comments.append({"repo": repo, "comment_id": comment_id, "body": body})

    def add_labels(self, repo: str, number: int, labels: list[str]) -> None:
        self.labels.append({"repo": repo, "number": number, "labels": labels})

    def create_check_run(
        self,
        repo: str,
        sha: str,
        *,
        name: str,
        conclusion: str,
        title: str,
        summary: str,
    ) -> None:
        self.checks.append(
            {
                "repo": repo,
                "sha": sha,
                "name": name,
                "conclusion": conclusion,
                "title": title,
                "summary": summary,
            }
        )


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return

    def json(self) -> object:
        return self.payload


class _FakeHttpx:
    def __init__(self, pages: list[list[JsonDict]]) -> None:
        self.pages = pages
        self.pages_seen: list[int] = []

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, int],
        timeout: int,
    ) -> _FakeResponse:
        page = params["page"]
        self.pages_seen.append(page)
        return _FakeResponse(self.pages[page - 1] if page <= len(self.pages) else [])


def _hmac_header(secret: str, body: bytes) -> str:
    import hashlib
    import hmac

    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _read_json(path: Path) -> JsonDict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: object) -> None:
    _write(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
