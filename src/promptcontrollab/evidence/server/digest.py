"""Canonical digests for structured evidence sources."""

from __future__ import annotations

import json
from pathlib import Path

from promptcontrollab.core.files import stable_digest


def _canonical_source_digest(path: Path, content: bytes, fallback: str) -> str:
    try:
        if path.suffix.lower() == ".json":
            value = json.loads(content.decode("utf-8-sig"))
            return f"sha256:{stable_digest(value)}"
        if path.suffix.lower() == ".jsonl":
            values = [
                json.loads(line)
                for line in content.decode("utf-8-sig").splitlines()
                if line.strip()
            ]
            return f"sha256:{stable_digest(values)}"
    except (UnicodeError, json.JSONDecodeError):
        return fallback
    return fallback
