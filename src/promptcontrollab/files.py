"""Small file helpers used by the CLI and tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

JsonDict = dict[str, Any]


def ensure_dir(path: Path) -> None:
    """Create ``path`` if needed."""

    path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> JsonDict:
    """Read a JSON object from ``path``."""

    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        msg = f"Expected JSON object in {path}"
        raise ValueError(msg)
    return cast(JsonDict, value)


def write_json(path: Path, value: JsonDict) -> None:
    """Write a stable JSON object."""

    ensure_dir(path.parent)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[JsonDict]:
    """Read JSONL records from ``path``."""

    records: list[JsonDict] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        value = json.loads(stripped)
        if not isinstance(value, dict):
            msg = f"Expected object on {path}:{line_number}"
            raise ValueError(msg)
        records.append(cast(JsonDict, value))
    return records


def write_jsonl(path: Path, records: list[JsonDict]) -> None:
    """Write JSONL records to ``path``."""

    ensure_dir(path.parent)
    text = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    path.write_text(text, encoding="utf-8")


def stable_digest(value: object) -> str:
    """Return a stable SHA256 digest for a JSON-compatible value."""

    import hashlib

    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

