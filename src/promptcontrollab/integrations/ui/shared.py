"""Small helpers shared by Streamlit dashboard pages."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from promptcontrollab.core.files import JsonDict


def _dict(value: object) -> JsonDict:
    """Normalize dict values for the dashboard."""
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    """Normalize list values for the dashboard."""
    return value if isinstance(value, list) else []


def _strings(value: object) -> list[str]:
    """Normalize strings values for the dashboard."""
    return [str(item) for item in _list(value)]


def _category_count(items: list[str]) -> dict[str, int]:
    """Normalize category count values for the dashboard."""
    counts: dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return counts


def _recommendation_label(value: object) -> object:
    """Normalize recommendation label values for the dashboard."""
    if isinstance(value, dict):
        return value.get("label") or value.get("recommendation") or value.get("verdict")
    return value


def _confirm_checkbox(
    st: Any,
    text: dict[str, str],
    execution_mode: str,
    key: str,
) -> bool:
    """Normalize confirm checkbox values for the dashboard."""
    if execution_mode != "confirm":
        return False
    return bool(st.checkbox(text["confirm_write"], value=False, key=key))


def _render_workflow_result(
    st: Any,
    text: dict[str, str],
    callback: Callable[[], JsonDict],
) -> None:
    """Render workflow result content without changing dashboard state."""
    try:
        result = callback()
    except Exception as exc:
        st.error(str(exc))
        return
    title = (
        text["workflow_preview"]
        if result.get("status") == "preview"
        else text["workflow_result"]
    )
    st.subheader(title)
    warnings = result.get("path_warnings")
    if isinstance(warnings, list) and warnings:
        for warning in warnings:
            st.warning(str(warning))
    st.json(result)


def _optional_path(value: str) -> Path | None:
    """Normalize optional path values for the dashboard."""
    stripped = value.strip()
    return Path(stripped) if stripped else None


def _split_lines(value: str) -> list[str]:
    """Normalize split lines values for the dashboard."""
    return [line.strip() for line in value.splitlines() if line.strip()]


def _optional_bool_label(value: object) -> bool | None:
    """Normalize optional bool label values for the dashboard."""
    if value == "true":
        return True
    if value == "false":
        return False
    return None
