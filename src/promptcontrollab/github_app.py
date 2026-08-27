"""Backward-compatible facade for :mod:`promptcontrollab.audit.github_app`."""

from promptcontrollab.audit.github_app import (
    SUMMARY_COMMENT_MARKER,
    PullRequestClient,
    _HttpGithubClient,
    handle_pull_request_payload,
    serve_github_app,
    summarize_pull_files,
    verify_webhook_signature,
)

__all__ = [
    "SUMMARY_COMMENT_MARKER",
    "PullRequestClient",
    "_HttpGithubClient",
    "handle_pull_request_payload",
    "serve_github_app",
    "summarize_pull_files",
    "verify_webhook_signature",
]
