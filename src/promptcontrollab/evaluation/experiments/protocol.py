"""Fixed public benchmark declaration schema and offline evidence replay."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .replay import replay_experiment

_REQUIRED = {
    "protocol_version",
    "benchmark_name",
    "provider",
    "model",
    "prompt_version",
    "dataset_version",
    "metric_id",
    "metric_version",
    "score_mode",
    "negative_results_allowed",
    "replay_entry",
    "limitations",
}


def validate_protocol(payload: object) -> dict[str, Any]:
    """Validate protocol v1 without executing commands or accessing a network."""
    if not isinstance(payload, dict):
        raise ValueError("Protocol must be an object")
    missing = sorted(_REQUIRED - payload.keys())
    if missing:
        raise ValueError(f"Missing protocol fields: {', '.join(missing)}")
    if payload.keys() - _REQUIRED:
        raise ValueError("Unsupported protocol fields")
    for field in _REQUIRED - {"negative_results_allowed", "limitations"}:
        if not isinstance(payload[field], str) or not payload[field].strip():
            raise ValueError(f"{field} must be a nonempty string")
    if payload["protocol_version"] != "1":
        raise ValueError("protocol_version must be 1")
    if payload["score_mode"] not in {"preserve", "recompute"}:
        raise ValueError("score_mode must be preserve or recompute")
    if payload["negative_results_allowed"] is not True:
        raise ValueError("negative_results_allowed must be true")
    if (
        not isinstance(payload["limitations"], list)
        or not payload["limitations"]
        or any(not isinstance(item, str) or not item.strip() for item in payload["limitations"])
    ):
        raise ValueError("limitations must be a nonempty array of nonempty strings")
    entry = payload["replay_entry"]
    if urlsplit(entry).scheme and not (len(entry) > 2 and entry[1:3] in {":\\", ":/"}):
        raise ValueError("replay_entry must be a local bundle path, never a URL or command")
    return copy.deepcopy(payload)


def replay_protocol(payload: object, *, base_dir: Path, out_dir: Path) -> dict[str, Any]:
    """Replay a declared local bundle and require the selected metric identity to agree."""
    declaration = validate_protocol(payload)
    bundle = base_dir / declaration["replay_entry"]
    replay = replay_experiment(bundle, out_dir)
    comparison = replay["assessment_recomputed"]["comparability"]
    metric = f"{declaration['metric_id']}@{declaration['metric_version']}"
    observed = comparison["metric"]
    if "@" not in observed:
        observed += "@1"
    if metric != observed or declaration["score_mode"] != comparison["score_mode"]:
        raise ValueError("Declared metric identity or score_mode differs from replay evidence")
    return {"protocol_status": "passed", "declaration": declaration, "replay": replay}
