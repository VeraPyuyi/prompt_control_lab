"""Simple offline prompt improvement rules."""

# ruff: noqa: RUF001

from __future__ import annotations

from dataclasses import dataclass

from promptcontrollab.files import JsonDict
from promptcontrollab.prompt_context import PromptContext


@dataclass(frozen=True)
class PromptImprovement:
    """Result of improving a prompt."""

    original_prompt: str
    improved_prompt: str
    language: str
    goal: str
    style: str
    changes: list[str]
    context_notes: list[str]

    def to_json(self) -> JsonDict:
        return {
            "original_prompt": self.original_prompt,
            "improved_prompt": self.improved_prompt,
            "language": self.language,
            "goal": self.goal,
            "style": self.style,
            "changes": self.changes,
            "context_notes": self.context_notes,
        }


def improve_prompt(
    prompt: str,
    *,
    context: PromptContext,
    goal: str,
    language: str,
    style: str,
) -> PromptImprovement:
    """Improve a prompt with deterministic, dependency-free rules."""

    original = prompt.strip()
    if not original:
        msg = "Prompt must not be empty"
        raise ValueError(msg)
    resolved_language = _resolve_language(original, language)
    changes = [
        "Added a clear task goal.",
        "Added output-format constraints.",
        "Added stability rules to reduce unsupported guessing.",
    ]
    context_notes = _context_notes(context, resolved_language)
    if context_notes:
        changes.append("Added warnings from the existing diagnostic report.")
    if resolved_language == "zh":
        improved = _improve_zh(original, goal=goal, style=style, context_notes=context_notes)
    else:
        improved = _improve_en(original, goal=goal, style=style, context_notes=context_notes)
    return PromptImprovement(
        original_prompt=original,
        improved_prompt=improved,
        language=resolved_language,
        goal=goal,
        style=style,
        changes=changes,
        context_notes=context_notes,
    )


def _resolve_language(prompt: str, language: str) -> str:
    if language in {"zh", "en"}:
        return language
    if language != "auto":
        msg = "Language must be `auto`, `zh`, or `en`"
        raise ValueError(msg)
    return "zh" if any("\u4e00" <= char <= "\u9fff" for char in prompt) else "en"


def _improve_zh(prompt: str, *, goal: str, style: str, context_notes: list[str]) -> str:
    lines = [
        _zh_goal_line(prompt),
        "",
        "要求：",
        "1. 先理解问题的核心含义。",
        "2. 只输出最终答案，不输出无关内容。",
        "3. 如果问题要求固定格式，请严格遵守格式。",
        "4. 如果信息不足，请明确说明无法确定，不要编造。",
    ]
    if goal in {"accuracy", "stability"} or style == "stable":
        lines.append("5. 回答前检查关键事实、计算和单位，减少不稳定输出。")
    if goal == "format" or style == "strict":
        lines.append("6. 不要改变要求中的标签、大小写、编号或 JSON 字段。")
    if context_notes:
        lines += ["", "注意：", *[f"- {note}" for note in context_notes]]
    lines += ["", "用户问题：", "{input}"]
    return "\n".join(lines)


def _improve_en(prompt: str, *, goal: str, style: str, context_notes: list[str]) -> str:
    lines = [
        _en_goal_line(prompt),
        "",
        "Requirements:",
        "1. Understand the core request before answering.",
        "2. Output only the final answer unless the task asks for explanation.",
        "3. Follow any required format exactly.",
        "4. If there is not enough information, say that clearly instead of guessing.",
    ]
    if goal in {"accuracy", "stability"} or style == "stable":
        lines.append("5. Check key facts, calculations, and units before finalizing the answer.")
    if goal == "format" or style == "strict":
        lines.append("6. Do not change required labels, casing, numbering, or JSON fields.")
    if context_notes:
        lines += ["", "Notes from previous diagnostics:", *[f"- {note}" for note in context_notes]]
    lines += ["", "User input:", "{input}"]
    return "\n".join(lines)


def _zh_goal_line(prompt: str) -> str:
    normalized = prompt.rstrip("。.!！")
    if normalized.startswith("回答"):
        return f"请准确{normalized}。"
    return f"请准确完成以下任务：{normalized}。"


def _en_goal_line(prompt: str) -> str:
    normalized = prompt.rstrip(".! ")
    lowered = normalized.lower()
    if lowered.startswith("answer"):
        return "Please answer the user question accurately."
    return f"Please complete this task accurately: {normalized}."


def _context_notes(context: PromptContext, language: str) -> list[str]:
    notes: list[str] = []
    if language == "zh":
        for slice_name in context.regressed_slices:
            notes.append(f"{slice_name} 类任务之前出现退化，请重点核对。")
        if context.broken_ids:
            notes.append(f"这些样本之前变差：{', '.join(context.broken_ids)}。")
        if context.deployment_notes:
            notes.append("之前检测到稳定性或部署风险，请保持回答一致并避免无依据猜测。")
        return notes
    for slice_name in context.regressed_slices:
        notes.append(f"The `{slice_name}` slice regressed before; check it carefully.")
    if context.broken_ids:
        notes.append(f"These examples broke before: {', '.join(context.broken_ids)}.")
    if context.deployment_notes:
        notes.append(
            "Previous diagnostics found stability or deployment risk; avoid unsupported guesses."
        )
    return notes
