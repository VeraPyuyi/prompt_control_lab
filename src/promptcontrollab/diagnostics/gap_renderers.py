"""Renderers and command writers for research evidence gap plans."""

from __future__ import annotations

from promptcontrollab.core.files import JsonDict
from promptcontrollab.diagnostics.common import _remediation_list
from promptcontrollab.diagnostics.renderers import (
    _badge,
    _html_page,
    _metric_grid,
    _paragraph,
    _table,
)


def _render_research_gap_status_markdown(payload: JsonDict) -> str:
    actions = _remediation_list(payload.get("actions"))
    lines = [
        "# Research Evidence Gap Status",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Complete: `{payload.get('complete_count')}/{payload.get('action_count')}`",
        f"- Missing: `{payload.get('missing_count')}`",
        "",
        str(payload.get("boundary", "")),
        "",
        "| Step | Diagnostic | Status | Artifact | Command |",
        "|---:|---|---|---|---|",
    ]
    for action in actions:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(action.get("step", "")),
                    str(action.get("concept", "")),
                    str(action.get("status", "")),
                    f"`{action.get('artifact', '')}`",
                    f"`{action.get('command', '')}`",
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def render_research_gap_status_html(payload: JsonDict) -> str:
    """Render research gap closure status as browser-friendly HTML."""

    actions = _remediation_list(payload.get("actions"))
    rows = [
        [
            action.get("step", ""),
            action.get("concept", ""),
            _badge(str(action.get("status", ""))),
            action.get("artifact", ""),
            action.get("command", ""),
        ]
        for action in actions
    ]
    return _html_page(
        title="Research Evidence Gap Status",
        subtitle=(
            f"Status: {payload.get('status')} - "
            f"{payload.get('complete_count')}/{payload.get('action_count')} complete"
        ),
        body=[
            _metric_grid(
                [
                    ("Status", _badge(str(payload.get("status", "")))),
                    ("Complete", f"{payload.get('complete_count')}/{payload.get('action_count')}"),
                    ("Missing", payload.get("missing_count", "")),
                ]
            ),
            _paragraph(payload.get("boundary")),
            _table(["Step", "Diagnostic", "Status", "Artifact", "Command"], rows),
        ],
    )


def _render_research_gap_plan_markdown(plan: JsonDict) -> str:
    actions = _remediation_list(plan.get("actions"))
    lines = [
        "# Research Evidence Gap Plan",
        "",
        str(plan.get("boundary", "")),
        "",
    ]
    if not actions:
        lines.extend(["No missing paper-derived diagnostic actions were found.", ""])
        return "\n".join(lines)
    lines.extend(
        [
            (
                "| Step | Missing diagnostic | Required inputs | Command | Artifact | "
                "What it explains |"
            ),
            "|---:|---|---|---|---|---|",
        ]
    )
    for action in actions:
        required = action.get("required_inputs")
        required_inputs = (
            ", ".join(str(item) for item in required) if isinstance(required, list) else ""
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    str(action.get("step", "")),
                    str(action.get("concept", "")),
                    required_inputs,
                    f"`{action.get('command', '')}`",
                    f"`{action.get('artifact', '')}`",
                    str(action.get("explains", "")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "The companion `research_gap_commands.ps1` and `research_gap_commands.sh` files are "
            "review-first scripts. They intentionally stop before running commands so you can "
            "replace placeholders and confirm paths.",
            "",
        ]
    )
    return "\n".join(lines)


def render_research_gap_plan_html(plan: JsonDict) -> str:
    """Render the research gap plan as browser-friendly HTML."""

    actions = _remediation_list(plan.get("actions"))
    if actions:
        rows = []
        for action in actions:
            required = action.get("required_inputs")
            required_inputs = (
                ", ".join(str(item) for item in required) if isinstance(required, list) else ""
            )
            rows.append(
                [
                    action.get("step", ""),
                    action.get("concept", ""),
                    required_inputs,
                    action.get("command", ""),
                    action.get("artifact", ""),
                    action.get("explains", ""),
                ]
            )
        table = _table(
            [
                "Step",
                "Missing diagnostic",
                "Required inputs",
                "Command",
                "Artifact",
                "What it explains",
            ],
            rows,
        )
    else:
        table = '<div class="empty">No missing paper-derived diagnostic actions were found.</div>'
    return _html_page(
        title="Research Evidence Gap Plan",
        subtitle="Copy-paste guide for collecting missing paper-derived evidence.",
        body=[
            _paragraph(plan.get("boundary")),
            table,
            _paragraph(
                "The companion research_gap_commands.ps1 and research_gap_commands.sh files are "
                "review-first scripts. They stop before running commands so placeholders and paths "
                "can be checked."
            ),
        ],
    )


def _render_gap_commands_ps1(plan: JsonDict) -> str:
    lines = [
        "# PromptControlLab research evidence gap commands",
        (
            "# Review this file, replace placeholders, then remove the exit line "
            "and uncomment commands."
        ),
        'Write-Host "Review research_gap_plan.md before running these commands."',
        "exit 1",
        "",
    ]
    for action in _remediation_list(plan.get("actions")):
        lines.extend(_command_comment_block(action, comment="#"))
    return "\n".join(lines)


def _render_gap_commands_sh(plan: JsonDict) -> str:
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        (
            "# Review this file, replace placeholders, then remove the exit line "
            "and uncomment commands."
        ),
        'echo "Review research_gap_plan.md before running these commands."',
        "exit 1",
        "",
    ]
    for action in _remediation_list(plan.get("actions")):
        lines.extend(_command_comment_block(action, comment="#"))
    return "\n".join(lines)


def _command_comment_block(action: JsonDict, *, comment: str) -> list[str]:
    required = action.get("required_inputs")
    required_inputs = (
        ", ".join(str(item) for item in required) if isinstance(required, list) else ""
    )
    return [
        f"{comment} Step {action.get('step')}: {action.get('concept')}",
        f"{comment} Requires: {required_inputs}",
        f"{comment} Writes: {action.get('artifact')}",
        f"{comment} {action.get('command')}",
        "",
    ]
