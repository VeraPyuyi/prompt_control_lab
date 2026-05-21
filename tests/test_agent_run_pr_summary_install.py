from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from promptcontrollab.cli import main
from promptcontrollab.files import JsonDict
from promptcontrollab.github_app import handle_pull_request_payload, verify_webhook_signature
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


class _FakeGithubClient:
    def __init__(self) -> None:
        self.comments: list[dict[str, object]] = []
        self.labels: list[dict[str, object]] = []
        self.checks: list[dict[str, object]] = []

    def list_pull_files(self, repo: str, number: int) -> list[JsonDict]:
        return [
            {"filename": "auth/session.py", "patch": "+TOKEN = 'secret'"},
            {"filename": "src/app.py", "patch": "+print('ok')"},
        ]

    def create_comment(self, repo: str, number: int, body: str) -> None:
        self.comments.append({"repo": repo, "number": number, "body": body})

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
