"""Backward-compatible facade for :mod:`promptcontrollab.preflight.prompt_context`."""

from promptcontrollab.preflight.prompt_context import (
    PromptContext,
    empty_prompt_context,
    load_prompt_context,
)

__all__ = [
    "PromptContext",
    "empty_prompt_context",
    "load_prompt_context",
]
