"""Pull request summary helpers for GitHub Action and GitHub App integrations."""

from __future__ import annotations

from pathlib import Path

from promptcontrollab.files import JsonDict, read_json, write_json


def build_pr_summary(
    *,
    audit_path: Path | None = None,
    gate_path: Path | None = None,
    agent_run_path: Path | None = None,
) -> JsonDict:
    """Build a concise PR review summary from local artifacts."""

    audit = _read_optional(audit_path)
    gate = _read_optional(gate_path)
    agent_run = _read_optional(agent_run_path)
    has_artifacts = any(
        path is not None and path.exists() for path in [audit_path, gate_path, agent_run_path]
    )
    labels: list[str] = []
    reasons: list[str] = []
    status = "pass"
    if not has_artifacts:
        status = "needs_review"
        labels.append("prompt-control-lab:needs-review")
        reasons.append("No PromptControlLab artifacts were provided.")
    gate_status = gate.get("status")
    if gate_status == "fail":
        status = "fail"
        labels.append("prompt-control-lab:gate-failed")
        reasons.append(
            str(gate.get("plain_summary") or gate.get("what_this_means") or "Gate failed.")
        )
    elif gate_status == "needs_review":
        status = "needs_review"
        labels.append("prompt-control-lab:needs-review")
        reasons.append("Gate requires review.")
    if audit.get("human_review_required"):
        if status == "pass":
            status = "needs_review"
        labels.append("prompt-control-lab:needs-review")
        reasons.append("Agent diff audit requires human review.")
    if audit.get("dangerous_paths"):
        labels.append("prompt-control-lab:dangerous-path")
        reasons.append("Dangerous paths changed.")
    if audit.get("secret_findings"):
        status = "fail"
        labels.append("prompt-control-lab:secret-finding")
        reasons.append("Potential secret was added in the diff.")
    if audit and not audit.get("tests_run"):
        labels.append("prompt-control-lab:missing-tests")
        reasons.append("No test command was recorded.")
    if audit.get("workflow_files_changed"):
        labels.append("prompt-control-lab:workflow-change")
    if audit.get("dependency_files_changed") or audit.get("lockfiles_changed"):
        labels.append("prompt-control-lab:dependency-change")
    labels = sorted(set(labels))
    return {
        "status": status,
        "labels": labels,
        "reasons": reasons,
        "gate_status": gate_status,
        "human_review_required": bool(audit.get("human_review_required")),
        "dangerous_paths": audit.get("dangerous_paths", []),
        "tests_run": audit.get("tests_run", []),
        "tests_passed": audit.get("tests_passed"),
        "secret_findings": audit.get("secret_findings", []),
        "agent": agent_run.get("agent"),
        "model": agent_run.get("model"),
        "provider": agent_run.get("provider"),
    }


def write_pr_summary(
    *,
    audit_path: Path | None,
    gate_path: Path | None,
    agent_run_path: Path | None,
    markdown_path: Path | None,
    json_path: Path | None,
) -> JsonDict:
    """Build and optionally write PR summary artifacts."""

    payload = build_pr_summary(
        audit_path=audit_path,
        gate_path=gate_path,
        agent_run_path=agent_run_path,
    )
    if json_path is not None:
        write_json(json_path, payload)
    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_pr_summary_markdown(payload), encoding="utf-8")
    return payload


def render_pr_summary_markdown(payload: JsonDict) -> str:
    """Render a PR comment body."""

    lines = [
        "## PromptControlLab PR Summary",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Agent: `{payload.get('agent') or 'unknown'}`",
        f"- Model: `{payload.get('model') or 'unknown'}`",
        f"- Tests passed: `{payload.get('tests_passed')}`",
        "",
        "### Reasons",
    ]
    reasons = payload.get("reasons")
    if isinstance(reasons, list) and reasons:
        lines.extend(f"- {reason}" for reason in reasons)
    else:
        lines.append("- No blocking issue detected.")
    dangerous = payload.get("dangerous_paths")
    if isinstance(dangerous, list) and dangerous:
        lines += ["", "### Dangerous paths", *[f"- `{path}`" for path in dangerous]]
    labels = payload.get("labels")
    if isinstance(labels, list) and labels:
        lines += ["", "### Suggested labels", *[f"- `{label}`" for label in labels]]
    return "\n".join(lines) + "\n"


def _read_optional(path: Path | None) -> JsonDict:
    if path is None or not path.exists():
        return {}
    return read_json(path)
