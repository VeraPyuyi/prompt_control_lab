"""Prompt-input guard for IDE and CLI integrations."""

from __future__ import annotations

from dataclasses import dataclass

from promptcontrollab.files import JsonDict
from promptcontrollab.prompt_context import PromptContext
from promptcontrollab.prompt_improver import PromptImprovement, improve_prompt


@dataclass(frozen=True)
class PromptGuardResult:
    """Structured result returned by the prompt guard."""

    action: str
    risk_level: str
    profile: str
    mode: str
    original_prompt: str
    improved_prompt: str
    reasons: list[str]
    token_report: JsonDict
    within_budget: bool | None

    def to_json(self) -> JsonDict:
        return {
            "action": self.action,
            "risk_level": self.risk_level,
            "profile": self.profile,
            "mode": self.mode,
            "original_prompt": self.original_prompt,
            "improved_prompt": self.improved_prompt,
            "reasons": self.reasons,
            "token_report": self.token_report,
            "within_budget": self.within_budget,
        }


def guard_prompt(
    prompt: str,
    *,
    context: PromptContext,
    mode: str,
    profile: str,
    token_mode: str,
    max_tokens: int | None,
    language: str = "auto",
) -> PromptGuardResult:
    """Inspect and improve a prompt before it reaches an IDE or CLI agent."""

    if mode not in {"suggest", "auto", "gate"}:
        msg = "Guard mode must be `suggest`, `auto`, or `gate`"
        raise ValueError(msg)
    if profile not in {"general", "coding", "research"}:
        msg = "Guard profile must be `general`, `coding`, or `research`"
        raise ValueError(msg)

    profile_prompt = _add_profile_hint(prompt.strip(), profile)
    improvement = improve_prompt(
        profile_prompt,
        context=context,
        goal=_goal_for_profile(profile),
        language=language,
        style="stable",
        token_mode=token_mode,
        max_tokens=max_tokens,
    )
    token_report = improvement.token_report.to_json()
    within_budget = token_report["within_budget"]
    reasons = _reasons(prompt, improvement, profile=profile, within_budget=within_budget)
    risk_level = _risk_level(reasons, within_budget)
    action = _action(mode, risk_level, within_budget)
    return PromptGuardResult(
        action=action,
        risk_level=risk_level,
        profile=profile,
        mode=mode,
        original_prompt=prompt.strip(),
        improved_prompt=improvement.improved_prompt,
        reasons=reasons,
        token_report=token_report,
        within_budget=within_budget,
    )


def _add_profile_hint(prompt: str, profile: str) -> str:
    if profile == "coding":
        return f"{prompt}\nFocus on precise code changes, affected files, tests, and verification."
    if profile == "research":
        return f"{prompt}\nFocus on assumptions, evidence, baselines, and reproducible artifacts."
    return prompt


def _goal_for_profile(profile: str) -> str:
    if profile == "coding":
        return "accuracy"
    if profile == "research":
        return "stability"
    return "stability"


def _reasons(
    original_prompt: str,
    improvement: PromptImprovement,
    *,
    profile: str,
    within_budget: bool | None,
) -> list[str]:
    reasons: list[str] = []
    stripped = original_prompt.strip()
    if len(stripped.split()) < 6 and not any("\u4e00" <= char <= "\u9fff" for char in stripped):
        reasons.append("Prompt is short and may be underspecified.")
    if any("\u4e00" <= char <= "\u9fff" for char in stripped) and len(stripped) < 12:
        reasons.append("Prompt is short and may be underspecified.")
    if "{input}" not in stripped:
        reasons.append("Prompt has no explicit input placeholder.")
    if profile == "coding":
        reasons.append("Coding profile adds file, test, and verification focus.")
    if profile == "research":
        reasons.append("Research profile adds evidence and reproducibility focus.")
    if within_budget is False:
        reasons.append("Improved prompt exceeds the requested token budget.")
    if improvement.context_notes:
        reasons.append("Existing diagnostics added run-specific caution notes.")
    if not reasons:
        reasons.append("Prompt is usable; guard produced a clearer version.")
    return reasons


def _risk_level(reasons: list[str], within_budget: bool | None) -> str:
    if within_budget is False:
        return "high"
    if len(reasons) >= 3:
        return "medium"
    return "low"


def _action(mode: str, risk_level: str, within_budget: bool | None) -> str:
    if mode == "gate" and (risk_level == "high" or within_budget is False):
        return "block"
    if mode == "auto":
        return "auto"
    return "suggest"
