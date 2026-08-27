"""Small shared helpers for research diagnostic artifacts."""

from __future__ import annotations

from pathlib import Path

from promptcontrollab.core.files import JsonDict, read_json


def _read_optional_json(path: Path) -> JsonDict:
    if not path.exists():
        return {}
    return read_json(path)


def _remediation_list(value: object) -> list[JsonDict]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _dedupe_remediation(items: list[JsonDict]) -> list[JsonDict]:
    rows = _remediation_list(items)
    seen: set[str] = set()
    deduped: list[JsonDict] = []
    for row in rows:
        concept = str(row.get("concept") or "")
        if not concept or concept in seen:
            continue
        seen.add(concept)
        deduped.append(row)
    return deduped
