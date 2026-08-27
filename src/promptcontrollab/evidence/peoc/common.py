"""Shared PEOC import records and integrity helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from promptcontrollab.core.files import JsonDict
from promptcontrollab.evidence.peoc.constants import CHUNK_SIZE

_CHUNK_SIZE = CHUNK_SIZE


@dataclass(frozen=True)
class PeocSourceOverrides:
    """Optional source selections within a PEOC bundle."""

    hard_summary: Path | None = None
    trajectory_files: tuple[Path, ...] = ()
    heterogeneity_summary: Path | None = None


@dataclass(frozen=True)
class _TrajectoryBinaryResults:
    valid: dict[str, list[JsonDict]]
    invalid: dict[str, list[JsonDict]]
    all_valid: list[JsonDict]
    all_invalid: list[JsonDict]


def _file_integrity(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(_CHUNK_SIZE):
            size += len(chunk)
            digest.update(chunk)
    return size, f"sha256:{digest.hexdigest()}"


def _sha256_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _strict_json_text(payload: JsonDict) -> str:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )
