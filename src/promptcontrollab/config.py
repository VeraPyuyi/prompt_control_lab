"""Small dependency-free configuration helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from promptcontrollab.files import JsonDict


def read_simple_yaml(path: Path) -> JsonDict:
    """Read a tiny ``key: value`` YAML subset used by examples and policies."""

    payload: JsonDict = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            msg = f"Expected `key: value` on {path}:{line_number}"
            raise ValueError(msg)
        key, raw_value = stripped.split(":", maxsplit=1)
        normalized_key = key.strip()
        if not normalized_key:
            msg = f"Empty config key on {path}:{line_number}"
            raise ValueError(msg)
        payload[normalized_key] = _parse_scalar(raw_value.strip())
    return payload


def get_config_path(config: JsonDict, key: str, *, base_dir: Path) -> Path | None:
    """Return a path from config, resolving relative paths against ``base_dir``."""

    value = config.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        msg = f"Config key `{key}` must be a path string"
        raise ValueError(msg)
    path = Path(value)
    return path if path.is_absolute() else base_dir / path


def get_config_str(config: JsonDict, key: str, default: str) -> str:
    """Return a string config value."""

    value = config.get(key, default)
    if not isinstance(value, str):
        msg = f"Config key `{key}` must be a string"
        raise ValueError(msg)
    return value


def get_config_float(config: JsonDict, key: str, default: float) -> float:
    """Return a float config value."""

    value = config.get(key, default)
    if not isinstance(value, int | float):
        msg = f"Config key `{key}` must be numeric"
        raise ValueError(msg)
    return float(value)


def get_config_int(config: JsonDict, key: str, default: int) -> int:
    """Return an integer config value."""

    value = config.get(key, default)
    if not isinstance(value, int):
        msg = f"Config key `{key}` must be an integer"
        raise ValueError(msg)
    return value


def _parse_scalar(value: str) -> Any:
    if value == "":
        return ""
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value
