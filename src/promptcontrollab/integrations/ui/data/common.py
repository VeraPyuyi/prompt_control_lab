"""Small normalization helpers shared by dashboard data readers."""

from __future__ import annotations

from promptcontrollab.core.files import JsonDict


def _mapping(value: object) -> JsonDict:
    """Normalize mapping values for dashboard use."""
    return value if isinstance(value, dict) else {}


def _nonnegative_int(value: object) -> int:
    """Normalize nonnegative int values for dashboard use."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    return 0
