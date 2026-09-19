"""Portable, offline scientific diagnostics with explicit evidence boundaries."""

from __future__ import annotations

from pathlib import Path

from .common import JsonDict, canonical, evidence, write_reports

KINDS = ("readout", "response", "measurement-value", "transfer", "replay")


def _compute(kind: str, document: JsonDict, out_dir: Path) -> JsonDict:
    if not isinstance(document, dict):
        raise ValueError("Research input must be a JSON object")
    canonical(document)
    if kind == "readout":
        from .readout import analyze_document
    elif kind == "response":
        from .response import analyze_document
    elif kind == "measurement-value":
        from .measurement_value import analyze_document
    elif kind == "transfer":
        from .transfer_prediction import analyze_document
    elif kind == "replay":
        from .replay import analyze_document as analyze_replay

        return analyze_replay(document, out_dir)
    else:
        raise ValueError(f"Unknown research kind {kind!r}; choose {', '.join(KINDS)}")
    result = analyze_document(document)
    result.setdefault("kind", kind)
    result.setdefault("evidence", evidence(document))
    if kind == "transfer":
        from .bootstrap import analyze_bootstrap

        result["bootstrap"] = analyze_bootstrap(document, result)
        for summary in result["summaries"]:
            summary["inference_status"] = (
                "See shared panel and endpoint component bootstrap, "
                "including its conditional scope and undefined draws."
            )
    if kind == "measurement-value":
        from .reporting import measurement_profiles

        result["budget_profiles"] = measurement_profiles(document, result)
        result["cost_accounting"] = {
            "transmission_seconds": (
                "shared upfront transfer cost; omitted in legacy v1 inputs means zero"
            ),
            "transmission_pair_seconds": (
                "optional aligned per-pair transfer time, added to generation cost"
            ),
            "all_declared_costs_included": True,
        }
    return result


def analyze_research(kind: str, document: JsonDict, out_dir: Path) -> JsonDict:
    """Recompute an allowlisted diagnostic and write deterministic JSON/CSV/EN/ZH reports."""
    return write_reports(_compute(kind, document, Path(out_dir)), Path(out_dir))


__all__ = ["KINDS", "analyze_research"]
