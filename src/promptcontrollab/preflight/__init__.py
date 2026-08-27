"""Prompt preflight, policy evaluation, and offline improvement APIs."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "GuardPolicy": ("promptcontrollab.preflight.guard_policy", "GuardPolicy"),
    "GuardViolation": ("promptcontrollab.preflight.guard_policy", "GuardViolation"),
    "PromptGuardResult": ("promptcontrollab.preflight.prompt_guard", "PromptGuardResult"),
    "PromptImprovement": ("promptcontrollab.preflight.prompt_improver", "PromptImprovement"),
    "choose_tool_for_need": ("promptcontrollab.preflight.tool_choice", "choose_tool_for_need"),
    "guard_prompt": ("promptcontrollab.preflight.prompt_guard", "guard_prompt"),
    "improve_prompt": ("promptcontrollab.preflight.prompt_improver", "improve_prompt"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Load a public preflight symbol without importing the entire domain."""

    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, symbol_name = target
    value = getattr(import_module(module_name), symbol_name)
    globals()[name] = value
    return value
