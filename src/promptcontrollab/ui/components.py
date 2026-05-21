"""Reusable Streamlit component helpers."""

from __future__ import annotations

import difflib
from typing import Any


def badge(label: str, value: object) -> str:
    """Return a compact badge-like Markdown string."""

    return f"**{label}:** `{value}`"


def prompt_diff(original: str, improved: str) -> str:
    """Return a readable unified diff for two prompt strings."""

    lines = difflib.unified_diff(
        original.splitlines(),
        improved.splitlines(),
        fromfile="original",
        tofile="guarded",
        lineterm="",
    )
    return "\n".join(lines)


def metric_cards(st: Any, cards: list[tuple[str, object]]) -> None:
    """Render metric cards in a stable column layout."""

    columns = st.columns(max(1, len(cards)))
    for column, (label, value) in zip(columns, cards, strict=False):
        column.metric(label, "-" if value is None else str(value))


def empty_state(st: Any, message: str, command: str | None = None) -> None:
    """Render an empty-state warning with an optional command."""

    st.warning(message)
    if command:
        st.code(command, language="bash")
