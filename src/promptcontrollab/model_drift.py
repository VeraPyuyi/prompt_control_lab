"""Model drift audit helpers."""

from __future__ import annotations

from pathlib import Path

from promptcontrollab.files import JsonDict, read_json, write_json
from promptcontrollab.model_identity import is_alias_model


def run_model_drift(*, run_dir: Path, history_dir: Path, out_path: Path) -> JsonDict:
    """Compare model provenance between two runs and write a drift report."""

    previous = _extract_model(read_json(history_dir / "manifest.json"))
    current = _extract_model(read_json(run_dir / "manifest.json"))
    risk, reason = _risk_and_reason(previous, current)
    payload: JsonDict = {
        "same_prompt": True,
        "previous_provider": previous.get("provider", "unknown"),
        "current_provider": current.get("provider", "unknown"),
        "previous_model": previous.get("model_id", "unknown"),
        "current_model": current.get("model_id", "unknown"),
        "risk": risk,
        "reason": reason,
    }
    write_json(out_path, payload)
    return payload


def _extract_model(manifest: JsonDict) -> JsonDict:
    for key in ["candidate_model", "model", "baseline_model"]:
        value = manifest.get(key)
        if isinstance(value, dict):
            return value
    return {"provider": "unknown", "model_id": "unknown"}


def _risk_and_reason(previous: JsonDict, current: JsonDict) -> tuple[str, str]:
    previous_model = _str(previous.get("model_id"), "unknown")
    current_model = _str(current.get("model_id"), "unknown")
    previous_provider = _str(previous.get("provider"), "unknown")
    current_provider = _str(current.get("provider"), "unknown")
    if "unknown" in {previous_model, current_model, previous_provider, current_provider}:
        return "medium", "Model identity is missing on one side, so drift risk is uncertain."
    if previous_provider != current_provider or previous_model != current_model:
        return "high", "Prompt comparison is confounded by model change."
    if is_alias_model(current_model) or is_alias_model(previous_model):
        return "medium", "Model id may be an alias; pin a dated model id for reproducibility."
    return "low", "Recorded provider and model id match."


def _str(value: object, default: str) -> str:
    return value if isinstance(value, str) and value else default

