"""Public benchmark protocol must reject incomplete declarations."""

import json
from pathlib import Path

import pytest


def validate_protocol(payload: dict) -> None:
    required = {
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
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"Missing protocol fields: {', '.join(missing)}")
    if payload["score_mode"] not in {"preserve", "recompute"}:
        raise ValueError("score_mode must be preserve or recompute")


def test_protocol_schema_rejects_missing_fields() -> None:
    with pytest.raises(ValueError, match="Missing protocol fields"):
        validate_protocol({"protocol_version": "1"})


def test_protocol_document_is_loadable() -> None:
    text = Path("docs/public-benchmark-protocol.md").read_text(encoding="utf-8")
    assert "negative_results_allowed" in text
    assert "replay_entry" in text
    json.dumps(
        {
            "protocol_version": "1",
            "benchmark_name": "offline",
            "provider": "imported",
            "model": "declared",
            "prompt_version": "v1",
            "dataset_version": "v1",
            "metric_id": "exact_match",
            "metric_version": "1",
            "score_mode": "preserve",
            "negative_results_allowed": True,
            "replay_entry": "experiment.zip",
            "limitations": ["historical only"],
        }
    )
