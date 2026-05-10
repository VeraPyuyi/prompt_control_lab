"""Simple offline prompt improvement rules."""

# ruff: noqa: RUF001

from __future__ import annotations

import re
from dataclasses import dataclass

from promptcontrollab.files import JsonDict
from promptcontrollab.prompt_context import PromptContext


@dataclass(frozen=True)
class PromptTokenReport:
    """Dependency-free token-cost estimate for a prompt rewrite."""

    original_estimated_tokens: int
    improved_estimated_tokens: int
    token_mode: str
    max_tokens: int | None
    within_budget: bool | None
    compression_applied: bool

    def to_json(self) -> JsonDict:
        return {
            "original_estimated_tokens": self.original_estimated_tokens,
            "improved_estimated_tokens": self.improved_estimated_tokens,
            "token_mode": self.token_mode,
            "max_tokens": self.max_tokens,
            "within_budget": self.within_budget,
            "compression_applied": self.compression_applied,
            "estimate_note": "Estimated with a dependency-free heuristic.",
        }


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
    token_report: PromptTokenReport

    def to_json(self) -> JsonDict:
        return {
            "original_prompt": self.original_prompt,
            "improved_prompt": self.improved_prompt,
            "language": self.language,
            "goal": self.goal,
            "style": self.style,
            "changes": self.changes,
            "context_notes": self.context_notes,
            "token_report": self.token_report.to_json(),
        }


def improve_prompt(
    prompt: str,
    *,
    context: PromptContext,
    goal: str,
    language: str,
    style: str,
    token_mode: str = "balanced",
    max_tokens: int | None = None,
) -> PromptImprovement:
    """Improve a prompt with deterministic, dependency-free rules."""

    original = prompt.strip()
    if not original:
        msg = "Prompt must not be empty"
        raise ValueError(msg)
    if token_mode not in {"balanced", "aggressive"}:
        msg = "Token mode must be `balanced` or `aggressive`"
        raise ValueError(msg)
    if max_tokens is not None and max_tokens <= 0:
        msg = "Max tokens must be greater than zero"
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
        improved = _improve_zh(
            original,
            goal=goal,
            style=style,
            context_notes=context_notes,
            token_mode=token_mode,
        )
    else:
        improved = _improve_en(
            original,
            goal=goal,
            style=style,
            context_notes=context_notes,
            token_mode=token_mode,
        )
    original_estimated_tokens = estimate_tokens(original)
    pre_budget_estimated_tokens = estimate_tokens(improved)
    improved = _fit_token_budget(
        improved,
        original=original,
        language=resolved_language,
        max_tokens=max_tokens,
    )
    improved_estimated_tokens = estimate_tokens(improved)
    compression_applied = (
        token_mode == "balanced"
        or token_mode == "aggressive"
        or improved_estimated_tokens < pre_budget_estimated_tokens
    )
    token_report = PromptTokenReport(
        original_estimated_tokens=original_estimated_tokens,
        improved_estimated_tokens=improved_estimated_tokens,
        token_mode=token_mode,
        max_tokens=max_tokens,
        within_budget=None if max_tokens is None else improved_estimated_tokens <= max_tokens,
        compression_applied=compression_applied,
    )
    if compression_applied:
        changes.append("Reduced prompt length to lower estimated token cost.")
    if max_tokens is not None:
        changes.append("Checked the rewritten prompt against the requested token budget.")
    return PromptImprovement(
        original_prompt=original,
        improved_prompt=improved,
        language=resolved_language,
        goal=goal,
        style=style,
        changes=changes,
        context_notes=context_notes,
        token_report=token_report,
    )


def _resolve_language(prompt: str, language: str) -> str:
    if language in {"zh", "en"}:
        return language
    if language != "auto":
        msg = "Language must be `auto`, `zh`, or `en`"
        raise ValueError(msg)
    return "zh" if any("\u4e00" <= char <= "\u9fff" for char in prompt) else "en"


def estimate_tokens(text: str) -> int:
    """Estimate token count without model-specific tokenizer dependencies."""

    cjk_chars = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    non_cjk_text = "".join(" " if "\u4e00" <= char <= "\u9fff" else char for char in text)
    word_or_symbol_tokens = re.findall(r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]", non_cjk_text)
    return max(1, cjk_chars + len(word_or_symbol_tokens))


def _improve_zh(
    prompt: str,
    *,
    goal: str,
    style: str,
    context_notes: list[str],
    token_mode: str,
) -> str:
    if token_mode == "aggressive":
        return _improve_zh_aggressive(prompt, context_notes=context_notes)
    lines = [
        _zh_goal_line(prompt),
        "",
        "要求：",
        "1. 理解问题后再答。",
        "2. 只输出需要的答案。",
        "3. 严格遵守指定格式。",
        "4. 信息不足时说明无法确定，不要编造。",
    ]
    if goal in {"accuracy", "stability"} or style == "stable":
        lines.append("5. 检查事实、计算和单位。")
    if goal == "format" or style == "strict":
        lines.append("6. 不改标签、大小写、编号或 JSON 字段。")
    if context_notes:
        lines += ["", "注意：", *[f"- {note}" for note in context_notes]]
    lines += ["", "用户问题：", "{input}"]
    return "\n".join(lines)


def _improve_en(
    prompt: str,
    *,
    goal: str,
    style: str,
    context_notes: list[str],
    token_mode: str,
) -> str:
    if token_mode == "aggressive":
        return _improve_en_aggressive(prompt, context_notes=context_notes)
    lines = [
        _en_goal_line(prompt),
        "",
        "Requirements:",
        "1. Understand the request before answering.",
        "2. Output only what the task asks for.",
        "3. Follow any required format exactly.",
        "4. If information is missing, say so instead of guessing.",
    ]
    if goal in {"accuracy", "stability"} or style == "stable":
        lines.append("5. Check key facts, calculations, and units.")
    if goal == "format" or style == "strict":
        lines.append("6. Do not change labels, casing, numbering, or JSON fields.")
    if context_notes:
        lines += ["", "Notes from previous diagnostics:", *[f"- {note}" for note in context_notes]]
    lines += ["", "User input:", "{input}"]
    return "\n".join(lines)


def _improve_zh_aggressive(prompt: str, *, context_notes: list[str]) -> str:
    lines = [
        _zh_goal_line(prompt),
        "规则：按指定格式答；不确定就说明；不要编造。",
    ]
    if context_notes:
        lines.append("注意：" + "；".join(note.rstrip("。") for note in context_notes) + "。")
    lines += ["输入：", "{input}"]
    return "\n".join(lines)


def _improve_en_aggressive(prompt: str, *, context_notes: list[str]) -> str:
    lines = [
        _en_goal_line(prompt),
        "Rules: follow the required format; say when unsure; do not invent facts.",
    ]
    if context_notes:
        lines.append("Notes: " + "; ".join(note.rstrip(".") for note in context_notes) + ".")
    lines += ["Input:", "{input}"]
    return "\n".join(lines)


def _fit_token_budget(
    prompt: str,
    *,
    original: str,
    language: str,
    max_tokens: int | None,
) -> str:
    if max_tokens is None or estimate_tokens(prompt) <= max_tokens:
        return prompt
    compact = _minimal_zh(original) if language == "zh" else _minimal_en(original)
    if estimate_tokens(compact) <= max_tokens:
        return compact
    lines = compact.splitlines()
    while len(lines) > 2 and estimate_tokens("\n".join(lines)) > max_tokens:
        lines.pop(-2)
    return "\n".join(lines)


def _minimal_zh(prompt: str) -> str:
    return "\n".join([_zh_goal_line(prompt), "只输出答案；不确定就说明。", "{input}"])


def _minimal_en(prompt: str) -> str:
    return "\n".join([_en_goal_line(prompt), "Answer only; say when unsure.", "{input}"])


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
