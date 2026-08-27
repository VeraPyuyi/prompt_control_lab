"""Backward-compatible facade for :mod:`promptcontrollab.preflight.prompt_guard`."""

from promptcontrollab.preflight.prompt_guard import (
    PromptGuardResult,
    guard_prompt,
)

__all__ = [
    "PromptGuardResult",
    "guard_prompt",
]
