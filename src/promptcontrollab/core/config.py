"""Small dependency-free configuration helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from promptcontrollab.core.files import JsonDict


def read_simple_yaml(path: Path) -> JsonDict:
    """Read a tiny ``key: value`` YAML subset used by examples and policies."""

    payload: JsonDict = {}
    current_list_key: str | None = None
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            if current_list_key is None:
                msg = f"Unexpected list item on {path}:{line_number}"
                raise ValueError(msg)
            values = payload.setdefault(current_list_key, [])
            if not isinstance(values, list):
                msg = f"Config key `{current_list_key}` cannot mix scalar and list values"
                raise ValueError(msg)
            values.append(_parse_scalar(stripped[2:].strip()))
            continue
        current_list_key = None
        if ":" not in stripped:
            msg = f"Expected `key: value` on {path}:{line_number}"
            raise ValueError(msg)
        key, raw_value = stripped.split(":", maxsplit=1)
        normalized_key = key.strip()
        if not normalized_key:
            msg = f"Empty config key on {path}:{line_number}"
            raise ValueError(msg)
        value = raw_value.strip()
        if value == "":
            payload[normalized_key] = []
            current_list_key = normalized_key
        else:
            payload[normalized_key] = _parse_scalar(value)
    return payload


def find_project_config(start: Path | None = None) -> Path | None:
    """Find ``.promptcontrol.yaml`` by walking from ``start`` toward the filesystem root."""

    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for directory in [current, *current.parents]:
        candidate = directory / ".promptcontrol.yaml"
        if candidate.exists():
            return candidate
    return None


def load_project_config(start: Path | None = None) -> tuple[JsonDict, Path | None]:
    """Load the nearest project config, returning an empty config if none exists."""

    path = find_project_config(start)
    if path is None:
        return {}, None
    return read_simple_yaml(path), path


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


def get_config_list(config: JsonDict, key: str, default: list[str] | None = None) -> list[str]:
    """Return a list config value from comma-separated or minimal YAML-list syntax."""

    value = config.get(key)
    if value is None:
        return list(default or [])
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str):
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]
    msg = f"Config key `{key}` must be a list or comma-separated string"
    raise ValueError(msg)


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


def get_config_bool(config: JsonDict, key: str, default: bool) -> bool:
    """Return a boolean config value."""

    value = config.get(key, default)
    if not isinstance(value, bool):
        msg = f"Config key `{key}` must be true or false"
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
