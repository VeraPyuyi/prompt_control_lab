"""Evidence ingestion, normalization, interpretation, and post-training gates."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "build_evidence_card": ("promptcontrollab.evidence_card", "build_evidence_card"),
    "import_evidence_manifest": (
        "promptcontrollab.server_evidence",
        "import_evidence_manifest",
    ),
    "merge_evidence_manifests": (
        "promptcontrollab.server_evidence",
        "merge_evidence_manifests",
    ),
    "run_posttrain_gate": ("promptcontrollab.posttrain_gate", "run_posttrain_gate"),
    "scan_evidence_root": ("promptcontrollab.server_evidence", "scan_evidence_root"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Load a public evidence symbol on first access."""

    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, symbol_name = target
    value = getattr(import_module(module_name), symbol_name)
    globals()[name] = value
    return value
