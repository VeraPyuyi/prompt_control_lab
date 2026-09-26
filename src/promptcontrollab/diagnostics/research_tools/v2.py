"""Versioned dispatch; legacy schemas retain their original behavior."""

from __future__ import annotations

from pathlib import Path

from .common import JsonDict


def compute(kind: str, document: JsonDict, out_dir: Path) -> JsonDict:
    """Dispatch an explicitly versioned research document to its diagnostic implementation."""
    if kind == "readout":
        from .v2_readout import analyze_document
    elif kind == "response":
        from .v2_response import analyze_document
    elif kind == "measurement-value":
        from .v2_measurement import analyze_document
    elif kind == "transfer":
        from .v2_transfer import analyze_document
    elif kind == "replay":
        from .v2_replay import analyze_document as analyze_replay

        return analyze_replay(document, out_dir)
    else:
        raise ValueError(f"Unknown research kind: {kind}")
    return analyze_document(document)
