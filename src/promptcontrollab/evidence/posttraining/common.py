"""Shared scalar and policy validation helpers for post-training evidence."""

from __future__ import annotations

import math
from typing import Any

from promptcontrollab.core.files import JsonDict


def _not_applicable_check(message: str) -> JsonDict:
    return {
        "passed": None,
        "applicable": False,
        "severity": "info",
        "observed": "not_applicable",
        "evidence_status": "not_applicable",
        "message": message,
    }


def _valid_interval(value: object) -> bool:
    if not isinstance(value, list) or len(value) != 2:
        return False
    lower = _optional_float(value[0])
    upper = _optional_float(value[1])
    return lower is not None and upper is not None and lower <= upper


def _optional_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        converted = float(value)
        return converted if math.isfinite(converted) else None
    if isinstance(value, str):
        try:
            converted = float(value)
            return converted if math.isfinite(converted) else None
        except ValueError:
            return None
    return None


def _optional_positive_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _bool(value: object, *, key: str, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    raise ValueError(f"Policy key `{key}` must be true or false")


def _dict(value: object) -> JsonDict:
    return value if isinstance(value, dict) else {}
