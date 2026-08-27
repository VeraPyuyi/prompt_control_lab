"""Backward-compatible facade for :mod:`promptcontrollab.core.errors`."""

from promptcontrollab.core.errors import (
    OptionalDependencyError,
    PromptControlLabError,
    optional_dependency_message,
)

__all__ = [
    "OptionalDependencyError",
    "PromptControlLabError",
    "optional_dependency_message",
]
