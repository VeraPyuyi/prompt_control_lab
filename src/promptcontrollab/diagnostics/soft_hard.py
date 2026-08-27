"""Soft-to-hard prompt projection diagnostics."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from promptcontrollab.core.files import JsonDict, ensure_dir, write_json
from promptcontrollab.core.optional import require_module


def analyze_soft_hard(*, soft_path: Path, vocab_path: Path, out_dir: Path) -> JsonDict:
    """Project soft prompt vectors to nearest vocabulary embeddings."""

    np = require_module("numpy", feature="soft-hard diagnostics", extra="research")
    soft_data = cast(Any, np.load(soft_path, allow_pickle=False))
    vocab_data = cast(Any, np.load(vocab_path, allow_pickle=False))
    if "soft" not in soft_data:
        msg = f"{soft_path} must contain an array named `soft`"
        raise ValueError(msg)
    if "embeddings" not in vocab_data:
        msg = f"{vocab_path} must contain an array named `embeddings`"
        raise ValueError(msg)
    soft = cast(Any, soft_data["soft"])
    embeddings = cast(Any, vocab_data["embeddings"])
    if len(soft.shape) != 2 or len(embeddings.shape) != 2:
        msg = "`soft` and `embeddings` must both be rank-2 arrays"
        raise ValueError(msg)
    if soft.shape[1] != embeddings.shape[1]:
        msg = "Soft prompt vectors and vocabulary embeddings must have the same width"
        raise ValueError(msg)

    nearest: list[int] = []
    distances: list[float] = []
    for row in soft:
        diff = embeddings - row
        norms = cast(Any, np.linalg.norm(diff, axis=1))
        index = int(np.argmin(norms))
        nearest.append(index)
        distances.append(float(norms[index]))

    mean_distance = float(np.mean(distances)) if distances else 0.0
    max_distance = float(np.max(distances)) if distances else 0.0
    payload: JsonDict = {
        "kind": "soft_hard",
        "soft_path": str(soft_path),
        "vocab_path": str(vocab_path),
        "token_indices": nearest,
        "mean_projection_distance": mean_distance,
        "max_projection_distance": max_distance,
        "risk": _risk_label(mean_distance, max_distance),
        "interpretation": (
            "Large projection distances mean the learned soft vectors are far from real token "
            "embeddings, so a hard prompt projection may lose behavior."
        ),
    }
    ensure_dir(out_dir)
    write_json(out_dir / "soft_hard.json", payload)
    return payload


def _risk_label(mean_distance: float, max_distance: float) -> str:
    if max_distance > 2.0 or mean_distance > 1.0:
        return "high"
    if max_distance > 1.0 or mean_distance > 0.5:
        return "medium"
    return "low"
