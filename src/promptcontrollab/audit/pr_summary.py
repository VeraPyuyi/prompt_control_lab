"""Pull request summary helpers for GitHub Action and GitHub App integrations."""

from __future__ import annotations

from pathlib import Path

from promptcontrollab.core.files import JsonDict, read_json, write_json


def build_pr_summary(
    *,
    audit_path: Path | None = None,
    gate_path: Path | None = None,
    evidence_gate_path: Path | None = None,
    agent_run_path: Path | None = None,
) -> JsonDict:
    """Build a concise PR review summary from local artifacts."""

    audit = _read_optional(audit_path)
    gate = _read_optional(gate_path)
    evidence_gate = _read_optional(evidence_gate_path)
    agent_run = _read_optional(agent_run_path)
    has_artifacts = any(
        path is not None and path.exists()
        for path in [audit_path, gate_path, evidence_gate_path, agent_run_path]
    )
    coverage = {
        "gate": bool(gate),
        "evidence_gate": bool(evidence_gate),
        "audit": bool(audit),
        "agent_run": bool(agent_run),
    }
    labels: list[str] = []
    reasons: list[str] = []
    warnings: list[str] = []
    status = "pass"
    if not has_artifacts:
        status = "needs_review"
        labels.append("prompt-control-lab:needs-review")
        reasons.append("No PromptControlLab artifacts were provided.")
    elif not coverage["audit"]:
        warnings.append("No audit artifact was provided; diff-level PR risk was not checked.")
    if coverage["gate"] and not coverage["evidence_gate"]:
        warnings.append(
            "No evidence gate artifact was provided; source/bundle evidence was not checked."
        )
    gate_status = gate.get("status")
    evidence_status = evidence_gate.get("status")
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
    if evidence_status == "fail":
        status = "fail"
        labels.append("prompt-control-lab:evidence-failed")
        reasons.append(str(evidence_gate.get("summary") or "Evidence gate failed."))
    elif evidence_status == "needs_review":
        if status == "pass":
            status = "needs_review"
        labels.append("prompt-control-lab:needs-review")
        reasons.append("Evidence gate requires review.")
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
    source_changed = _positive_count(audit.get("source_files_changed"))
    if source_changed and not audit.get("tests_run"):
        labels.append("prompt-control-lab:missing-tests")
        reasons.append("No test command was recorded.")
    if audit.get("workflow_files_changed"):
        labels.append("prompt-control-lab:workflow-change")
    if audit.get("dependency_files_changed") or audit.get("lockfiles_changed"):
        labels.append("prompt-control-lab:dependency-change")
    agent_risk = agent_run.get("risk_level")
    agent_review_required = bool(
        agent_run.get("review_required") or agent_run.get("human_review_required")
    )
    if agent_risk == "high":
        status = "fail"
        labels.append("prompt-control-lab:needs-review")
        reasons.append("Agent run risk level is high.")
    elif agent_review_required or agent_risk == "medium":
        if status == "pass":
            status = "needs_review"
        labels.append("prompt-control-lab:needs-review")
        reasons.append("Agent run requires human review.")
    labels = sorted(set(labels))
    return {
        "status": status,
        "labels": labels,
        "reasons": reasons,
        "coverage": coverage,
        "warnings": warnings,
        "gate_status": gate_status,
        "evidence_gate_status": evidence_status,
        "human_review_required": bool(audit.get("human_review_required") or agent_review_required),
        "agent_risk_level": agent_risk,
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
    evidence_gate_path: Path | None = None,
    agent_run_path: Path | None,
    markdown_path: Path | None,
    json_path: Path | None,
) -> JsonDict:
    """Build and optionally write PR summary artifacts."""

    payload = build_pr_summary(
        audit_path=audit_path,
        gate_path=gate_path,
        evidence_gate_path=evidence_gate_path,
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
        "### Coverage",
        f"- Gate: `{_yes_no(_coverage_value(payload, 'gate'))}`",
        f"- Evidence gate: `{_yes_no(_coverage_value(payload, 'evidence_gate'))}`",
        f"- Audit: `{_yes_no(_coverage_value(payload, 'audit'))}`",
        f"- Agent run: `{_yes_no(_coverage_value(payload, 'agent_run'))}`",
        "",
        "### Reasons",
    ]
    reasons = payload.get("reasons")
    if isinstance(reasons, list) and reasons:
        lines.extend(f"- {reason}" for reason in reasons)
    else:
        lines.append("- No blocking issue detected.")
    warnings = payload.get("warnings")
    if isinstance(warnings, list) and warnings:
        lines += ["", "### Warnings", *[f"- {warning}" for warning in warnings]]
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


def _positive_count(value: object) -> bool:
    return isinstance(value, int | float) and value > 0


def _coverage_value(payload: JsonDict, key: str) -> bool:
    coverage = payload.get("coverage")
    return bool(coverage.get(key)) if isinstance(coverage, dict) else False


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
