"""Self-hosted GitHub App helpers for PromptControlLab PR review."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from promptcontrollab.errors import PromptControlLabError
from promptcontrollab.files import JsonDict
from promptcontrollab.optional import require_module
from promptcontrollab.pr_summary import render_pr_summary_markdown


class PullRequestClient(Protocol):
    """Minimal client contract used by the webhook handler."""

    def create_comment(self, repo: str, number: int, body: str) -> None: ...

    def add_labels(self, repo: str, number: int, labels: list[str]) -> None: ...

    def create_check_run(
        self,
        repo: str,
        sha: str,
        *,
        name: str,
        conclusion: str,
        title: str,
        summary: str,
    ) -> None: ...


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
    summary: JsonDict,
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

    body = render_pr_summary_markdown(summary)
    client.create_comment(repo, number, body)
    labels = summary.get("labels")
    if isinstance(labels, list) and labels:
        client.add_labels(repo, number, [str(label) for label in labels])
    status = str(summary.get("status", "pass"))
    if status in {"fail", "needs_review"} and sha:
        client.create_check_run(
            repo,
            sha,
            name="PromptControlLab Gate",
            conclusion="failure" if status == "fail" else "neutral",
            title=f"PromptControlLab: {status}",
            summary=body,
        )
    return {"handled": True, "repo": repo, "number": number, "status": status}


def serve_github_app(*, host: str, port: int) -> None:
    """Serve a minimal self-hosted FastAPI GitHub App webhook."""

    fastapi = require_module("fastapi", feature="GitHub App bot", extra="bot")
    uvicorn = require_module("uvicorn", feature="GitHub App bot", extra="bot")
    app = fastapi.FastAPI(title="PromptControlLab GitHub App")
    config = _load_config()

    @app.post("/webhook")  # type: ignore[misc]
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
        summary = {"status": "needs_review", "reasons": ["Webhook received."], "labels": []}
        return handle_pull_request_payload(payload, client=client, summary=summary)

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
