"""Readable prompt improvement diffs."""

from __future__ import annotations

from promptcontrollab.prompt_improver import PromptImprovement


def render_prompt_diff(improvement: PromptImprovement) -> str:
    """Render a simple Markdown diff-style explanation."""

    lines = [
        "# Prompt Improvement",
        "",
        "## Original Prompt",
        "",
        "```text",
        improvement.original_prompt,
        "```",
        "",
        "## Improved Prompt",
        "",
        "```text",
        improvement.improved_prompt,
        "```",
        "",
        "## Why It Changed",
        "",
    ]
    lines.extend(f"- {change}" for change in improvement.changes)
    if improvement.context_notes:
        lines += ["", "## Context Notes", ""]
        lines.extend(f"- {note}" for note in improvement.context_notes)
    token_report = improvement.token_report.to_json()
    lines += [
        "",
        "## Estimated Token Cost",
        "",
        f"- Original prompt: {token_report['original_estimated_tokens']}",
        f"- Improved prompt: {token_report['improved_estimated_tokens']}",
        f"- Token mode: {token_report['token_mode']}",
    ]
    if token_report["max_tokens"] is not None:
        lines.extend(
            [
                f"- Max tokens: {token_report['max_tokens']}",
                f"- Within budget: {token_report['within_budget']}",
            ]
        )
    lines.append("")
    return "\n".join(lines)
