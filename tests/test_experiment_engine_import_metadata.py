"""Import metadata remains auditable and constrains prompt-effect attribution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from promptcontrollab.evaluation.experiments import create_experiment, run_experiment
from promptcontrollab.evaluation.experiments.storage import job_directory
from promptcontrollab.integrations.experiment_imports import normalize_import_document


def _run(
    root: Path, baseline: list[dict[str, Any]], candidate: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    config = {"provider": "imported", "model": "declared-import", "prompt": "prompt"}
    spec = {
        "schema_version": "experiment/v1",
        "operation": "import",
        "baseline": config,
        "candidate": config,
        "data": [
            {"id": row["id"], "input": f"task {row['id']}", "expected": "yes"} for row in baseline
        ],
        "metric": "exact_match",
        "predictions": {"baseline": baseline, "candidate": candidate},
        "budget": {"max_calls": 10, "max_output_tokens": 100, "max_seconds": 10},
    }
    job = run_experiment(root, create_experiment(root, spec)["id"])
    records = json.loads(
        (job_directory(root, job["id"]) / "report" / "records.json").read_text(encoding="utf-8")
    )
    return job, records


def test_normalized_import_keeps_provider_and_original_model_metadata(tmp_path: Path) -> None:
    def normalize(provider: str) -> list[dict[str, Any]]:
        source = [
            {
                "id": "a",
                "output": "yes",
                "model": {
                    "model_id": "same-name",
                    "provider": provider,
                    "revision": "2026-09",
                    "decoding": {"temperature": 0, "top_p": 1},
                },
            }
        ]
        result = normalize_import_document(
            {"text": json.dumps(source), "format": "json"}, tmp_path / "imports"
        )
        return result["predictions"]  # type: ignore[no-any-return]

    job, records = _run(tmp_path, normalize("provider-a"), normalize("provider-b"))
    assert job["assessment"]["comparability"]["status"] == "confounded"
    assert job["assessment"]["comparability"]["differing_settings"] == ["observed_provider"]
    assert job["assessment"]["next_action"]["code"] == "align_settings"
    for arm, provider in (("baseline", "provider-a"), ("candidate", "provider-b")):
        row = records[arm][0]
        assert row["observed_provider"] == provider
        assert row["observed_model"] == "same-name"
        assert row["model_metadata"]["revision"] == "2026-09"
        assert row["model_metadata"]["provider"] == provider
        assert row["decoding_metadata"] == {"temperature": 0, "top_p": 1}
        assert row["observed_settings"]["temperature"] == 0


@pytest.mark.parametrize(
    "field,left,right",
    [
        ("temperature", 0, 0.7),
        ("top_p", 0, 1),
        ("seed", 0, 1),
        ("max_output_tokens", 10, 20),
        ("thinking", "disabled", "enabled"),
    ],
)
def test_imported_decoding_changes_are_confounded(
    tmp_path: Path, field: str, left: object, right: object
) -> None:
    baseline = [{"id": "a", "output": "yes", "model": "same", "decoding": {field: left}}]
    candidate = [{"id": "a", "output": "yes", "model": "same", field: right}]
    job, records = _run(tmp_path, baseline, candidate)
    assert job["assessment"]["comparability"]["differing_settings"] == [f"observed_{field}"]
    assert job["assessment"]["comparability"]["status"] == "confounded"
    assert records["baseline"][0]["decoding_metadata"][field] == left
    assert records["candidate"][0]["decoding_metadata"][field] == right


def test_import_compares_conditions_within_pairs_and_retains_unknowns(tmp_path: Path) -> None:
    baseline = [
        {"id": str(index), "output": "yes", "model": model}
        for index, model in enumerate(("a", "b"))
    ]
    candidate = [
        {"id": str(index), "output": "yes", "model": model}
        for index, model in enumerate(("b", "a"))
    ]
    job, _ = _run(tmp_path / "swapped", baseline, candidate)
    assert job["assessment"]["comparability"]["differing_settings"] == ["observed_model"]
    job, records = _run(
        tmp_path / "unknown",
        [{"id": "a", "output": "yes"}],
        [{"id": "a", "output": "yes", "temperature": 0}],
    )
    assert job["assessment"]["comparability"]["status"] == "declared_only"
    assert records["baseline"][0]["observed_settings"] == {}
    assert records["candidate"][0]["observed_settings"] == {"temperature": 0}
