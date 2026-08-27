"""Self-hosted GitHub App helpers for PromptControlLab PR review."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from promptcontrollab.audit.pr_summary import render_pr_summary_markdown
from promptcontrollab.core.errors import PromptControlLabError
from promptcontrollab.core.files import JsonDict
from promptcontrollab.core.optional import require_module

SUMMARY_COMMENT_MARKER = "<!-- prompt-control-lab-summary -->"


class PullRequestClient(Protocol):
    """Minimal client contract used by the webhook handler."""

    def list_pull_files(self, repo: str, number: int) -> list[JsonDict]:
        """Return all changed files visible for a pull request."""

        ...

    def create_comment(self, repo: str, number: int, body: str) -> None:
        """Create a pull-request summary comment."""

        ...

    def list_comments(self, repo: str, number: int) -> list[JsonDict]:
        """Return existing issue comments associated with a pull request."""

        ...

    def update_comment(self, repo: str, comment_id: int, body: str) -> None:
        """Replace an existing pull-request summary comment."""

        ...

    def add_labels(self, repo: str, number: int, labels: list[str]) -> None:
        """Add review labels to a pull request."""

        ...

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
        """Create a completed PromptControlLab check run for a commit."""

        ...


def verify_webhook_signature(secret: str, body: bytes, signature_header: str | None) -> bool:
    """Verify a GitHub webhook HMAC SHA256 signature."""

    if not secret or not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    actual = signature_header.split("=", maxsplit=1)[1]
    return hmac.compare_digest(expected, actual)


def handle_pull_request_payload(
    payload: JsonDict,
    *,
    client: PullRequestClient,
    summary: JsonDict | None = None,
) -> JsonDict:
    """Post PromptControlLab review output for one pull request payload."""

    action = str(payload.get("action", ""))
    if action not in {"opened", "synchronize", "reopened"}:
        return {"handled": False, "reason": "unsupported_action"}
    repository = payload.get("repository")
    pull_request = payload.get("pull_request")
    if not isinstance(repository, dict) or not isinstance(pull_request, dict):
        return {"handled": False, "reason": "missing_repository_or_pull_request"}
    repo = str(repository.get("full_name", ""))
    number = int(pull_request.get("number", 0))
    head = pull_request.get("head")
    sha = str(head.get("sha", "")) if isinstance(head, dict) else ""
    if not repo or number <= 0:
        return {"handled": False, "reason": "missing_repo_or_pr_number"}

    if summary is None:
        summary = summarize_pull_files(client.list_pull_files(repo, number))
    body = f"{SUMMARY_COMMENT_MARKER}\n{render_pr_summary_markdown(summary)}"
    _upsert_summary_comment(client, repo, number, body)
    labels = summary.get("labels")
    if isinstance(labels, list) and labels:
        client.add_labels(repo, number, [str(label) for label in labels])
    status = str(summary.get("status", "pass"))
    if sha:
        client.create_check_run(
            repo,
            sha,
            name="PromptControlLab Gate",
            conclusion=_check_conclusion(status),
            title=f"PromptControlLab: {status}",
            summary=body,
        )
    return {"handled": True, "repo": repo, "number": number, "status": status}


def _check_conclusion(status: str) -> str:
    if status == "fail":
        return "failure"
    if status == "needs_review":
        return "neutral"
    if status == "pass":
        return "success"
    return "neutral"


def summarize_pull_files(files: list[JsonDict]) -> JsonDict:
    """Generate a PR summary from GitHub changed-file records."""

    filenames = [str(item.get("filename", "")) for item in files if item.get("filename")]
    dangerous_paths = [path for path in filenames if _dangerous_path(path)]
    workflow_files = [path for path in filenames if path.startswith(".github/workflows/")]
    dependency_files = [path for path in filenames if _dependency_file(path)]
    source_changed = any(_source_file(path) for path in filenames)
    test_changed = any(_test_file(path) for path in filenames)
    secret_findings = _secret_findings(files)
    status = "pass"
    labels: list[str] = []
    reasons: list[str] = []
    if dangerous_paths:
        status = "needs_review"
        labels.append("prompt-control-lab:needs-review")
        labels.append("prompt-control-lab:dangerous-path")
        reasons.append("PR changes security, auth, billing, payment, migration, or secret paths.")
    if workflow_files:
        status = "needs_review" if status == "pass" else status
        labels.append("prompt-control-lab:workflow-change")
        reasons.append("PR changes GitHub workflow files.")
    if dependency_files:
        status = "needs_review" if status == "pass" else status
        labels.append("prompt-control-lab:dependency-change")
        reasons.append("PR changes dependency or lock files.")
    if secret_findings:
        status = "fail"
        labels.append("prompt-control-lab:secret-finding")
        reasons.append("PR patch appears to add a secret-like value.")
    if source_changed and not test_changed:
        status = "needs_review" if status == "pass" else status
        labels.append("prompt-control-lab:missing-tests")
        reasons.append("No test file change was detected in the PR file list.")
    return {
        "status": status,
        "labels": sorted(set(labels)),
        "reasons": reasons or ["No obvious PR file risk detected."],
        "dangerous_paths": dangerous_paths,
        "tests_run": [],
        "tests_passed": None,
        "secret_findings": secret_findings,
        "changed_files": filenames,
        "human_review_required": status != "pass",
    }


def _upsert_summary_comment(
    client: PullRequestClient,
    repo: str,
    number: int,
    body: str,
) -> None:
    for comment in client.list_comments(repo, number):
        if not isinstance(comment, dict):
            continue
        comment_body = comment.get("body")
        comment_id = comment.get("id")
        if (
            isinstance(comment_body, str)
            and SUMMARY_COMMENT_MARKER in comment_body
            and isinstance(comment_id, int)
        ):
            client.update_comment(repo, comment_id, body)
            return
    client.create_comment(repo, number, body)


def serve_github_app(*, host: str, port: int) -> None:
    """Serve a minimal self-hosted FastAPI GitHub App webhook."""

    fastapi = require_module("fastapi", feature="GitHub App bot", extra="bot")
    uvicorn = require_module("uvicorn", feature="GitHub App bot", extra="bot")
    app = fastapi.FastAPI(title="PromptControlLab GitHub App")
    config = _load_config()

    async def webhook(request: Any) -> JsonDict:  # pragma: no cover - exercised by app runtime
        body = await request.body()
        signature = request.headers.get("X-Hub-Signature-256")
        if not verify_webhook_signature(config.webhook_secret, body, signature):
            raise fastapi.HTTPException(status_code=401, detail="invalid signature")
        event = request.headers.get("X-GitHub-Event", "")
        payload = await request.json()
        if event != "pull_request":
            return {"handled": False, "reason": "unsupported_event"}
        installation = payload.get("installation")
        installation_id = (
            int(installation.get("id", 0)) if isinstance(installation, dict) else 0
        )
        client = _HttpGithubClient(config, installation_id=installation_id)
        return handle_pull_request_payload(payload, client=client)

    app.add_api_route("/webhook", webhook, methods=["POST"])
    uvicorn.run(app, host=host, port=port)


@dataclass(frozen=True)
class _GithubAppConfig:
    app_id: str
    private_key_path: Path
    webhook_secret: str


def _load_config() -> _GithubAppConfig:
    app_id = os.environ.get("GITHUB_APP_ID", "")
    private_key_path = os.environ.get("GITHUB_PRIVATE_KEY_PATH", "")
    webhook_secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    missing = [
        name
        for name, value in [
            ("GITHUB_APP_ID", app_id),
            ("GITHUB_PRIVATE_KEY_PATH", private_key_path),
            ("GITHUB_WEBHOOK_SECRET", webhook_secret),
        ]
        if not value
    ]
    if missing:
        msg = f"Missing GitHub App environment variables: {', '.join(missing)}"
        raise PromptControlLabError(msg)
    return _GithubAppConfig(
        app_id=app_id,
        private_key_path=Path(private_key_path),
        webhook_secret=webhook_secret,
    )


class _HttpGithubClient:
    def __init__(self, config: _GithubAppConfig, *, installation_id: int) -> None:
        self.config = config
        self.installation_id = installation_id
        self.httpx = require_module("httpx", feature="GitHub App bot", extra="bot")
        self.jwt = require_module("jwt", feature="GitHub App bot", extra="bot")
        if installation_id <= 0:
            msg = "GitHub webhook payload did not include an installation id."
            raise PromptControlLabError(msg)

    def create_comment(self, repo: str, number: int, body: str) -> None:
        self._request("POST", f"/repos/{repo}/issues/{number}/comments", {"body": body})

    def list_comments(self, repo: str, number: int) -> list[JsonDict]:
        token = self._installation_token()
        comments: list[JsonDict] = []
        page = 1
        while True:
            response = self.httpx.get(
                f"https://api.github.com/repos/{repo}/issues/{number}/comments",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                params={"per_page": 100, "page": page},
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                msg = "GitHub issue comments response was not a list."
                raise PromptControlLabError(msg)
            items = [item for item in payload if isinstance(item, dict)]
            comments.extend(items)
            if len(payload) < 100:
                return comments
            page += 1

    def update_comment(self, repo: str, comment_id: int, body: str) -> None:
        self._request("PATCH", f"/repos/{repo}/issues/comments/{comment_id}", {"body": body})

    def list_pull_files(self, repo: str, number: int) -> list[JsonDict]:
        token = self._installation_token()
        files: list[JsonDict] = []
        page = 1
        while True:
            response = self.httpx.get(
                f"https://api.github.com/repos/{repo}/pulls/{number}/files",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                params={"per_page": 100, "page": page},
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                msg = "GitHub pull files response was not a list."
                raise PromptControlLabError(msg)
            items = [item for item in payload if isinstance(item, dict)]
            files.extend(items)
            if len(payload) < 100:
                return files
            page += 1

    def add_labels(self, repo: str, number: int, labels: list[str]) -> None:
        self._request("POST", f"/repos/{repo}/issues/{number}/labels", {"labels": labels})

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
        self._request(
            "POST",
            f"/repos/{repo}/check-runs",
            {
                "name": name,
                "head_sha": sha,
                "status": "completed",
                "conclusion": conclusion,
                "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "output": {"title": title, "summary": summary},
            },
        )

    def _request(self, method: str, path: str, json_body: JsonDict) -> None:
        token = self._installation_token()
        response = self.httpx.request(
            method,
            f"https://api.github.com{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json=json_body,
            timeout=20,
        )
        response.raise_for_status()

    def _installation_token(self) -> str:
        app_jwt = self._app_jwt()
        response = self.httpx.post(
            f"https://api.github.com/app/installations/{self.installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("token"), str):
            msg = "GitHub installation token response did not include token."
            raise PromptControlLabError(msg)
        return str(payload["token"])

    def _app_jwt(self) -> str:
        private_key = self.config.private_key_path.read_text(encoding="utf-8")
        now = int(time.time())
        token = self.jwt.encode(
            {"iat": now - 60, "exp": now + 9 * 60, "iss": self.config.app_id},
            private_key,
            algorithm="RS256",
        )
        return cast(str, token)


def _dangerous_path(path: str) -> bool:
    lowered = path.lower()
    return any(
        part in lowered
        for part in ["auth", "security", "permission", "billing", "payment", "migration", "secret"]
    )


def _dependency_file(path: str) -> bool:
    name = Path(path).name.lower()
    return name in {
        "pyproject.toml",
        "requirements.txt",
        "package.json",
        "uv.lock",
        "poetry.lock",
        "package-lock.json",
        "pnpm-lock.yaml",
        "cargo.toml",
        "cargo.lock",
        "go.mod",
        "go.sum",
    } or (name.startswith("requirements") and name.endswith(".txt"))


def _test_file(path: str) -> bool:
    lowered = path.lower()
    name = Path(path).name.lower()
    return lowered.startswith("tests/") or "/tests/" in lowered or name.startswith("test_")


def _source_file(path: str) -> bool:
    lowered = path.lower()
    suffix = Path(path).suffix.lower()
    if _test_file(path) or _dependency_file(path) or lowered.startswith(".github/workflows/"):
        return False
    if lowered.startswith(("docs/", "doc/")) or "/docs/" in lowered or "/doc/" in lowered:
        return False
    return suffix in {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".go",
        ".rs",
        ".java",
        ".kt",
        ".c",
        ".cc",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".rb",
        ".php",
        ".swift",
    }


def _secret_findings(files: list[JsonDict]) -> list[JsonDict]:
    import re

    pattern = re.compile(r"(api[_-]?key|secret|token|private[_-]?key|password)\s*[:=]", re.I)
    findings: list[JsonDict] = []
    for item in files:
        filename = str(item.get("filename", ""))
        patch = item.get("patch")
        if not isinstance(patch, str):
            continue
        for line in patch.splitlines():
            if line.startswith("+") and not line.startswith("+++") and pattern.search(line):
                findings.append({"path": filename, "kind": "secret_like", "redacted": "***"})
                break
    return findings
