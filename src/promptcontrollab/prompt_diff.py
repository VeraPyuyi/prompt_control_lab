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
    lines.append("")
    return "\n".join(lines)
