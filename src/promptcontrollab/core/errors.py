"""Shared exceptions."""


class PromptControlLabError(Exception):
    """Base class for user-facing PromptControlLab errors."""


class OptionalDependencyError(PromptControlLabError):
    """Raised when a command needs an optional dependency that is not installed."""


def optional_dependency_message(feature: str, extra: str) -> str:
    """Return a clear install hint for an optional feature."""

    return (
        f"{feature} requires optional dependencies. Install them with "
        f"`pip install promptcontrollab[{extra}]` or "
        f"`uv pip install 'promptcontrollab[{extra}]'`."
    )

