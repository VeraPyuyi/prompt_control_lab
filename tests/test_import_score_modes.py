"""External judgements remain distinct from deterministic rescoring."""

import csv
import json
from pathlib import Path
from typing import Any

import pytest

from promptcontrollab.evaluation.experiments import (
    create_experiment,
    export_experiment,
    run_experiment,
)
from promptcontrollab.evaluation.experiments.replay import replay_experiment
from promptcontrollab.evaluation.experiments.storage import job_directory


def spec(mode: str) -> dict[str, Any]:
    return {
        "operation": "import",
        "score_mode": mode,
        "source_metric": {
            "id": "judge",
            "version": "2026-01",
            "direction": "higher_is_better",
            "source": "external",
            "reviewer": "fixed-judge",
            "scale": [0, 1],
        },
        "data": [{"id": "a", "input": "task", "expected": "yes"}],
        "predictions": {
            arm: [{"id": "a", "output": "no", "score": 0.75}] for arm in ("baseline", "candidate")
        },
    }


@pytest.mark.parametrize("mode,want", [("preserve", 0.75), ("recompute", 0)])
def test_import_report_csv_and_relocated_replay_retain_both_scores(
    tmp_path: Path,
    mode: str,
    want: float,
) -> None:
    job = create_experiment(tmp_path, spec(mode))
    job = run_experiment(tmp_path, job["id"])
    report = job_directory(tmp_path, job["id"]) / "report"
    row = json.loads((report / "records.json").read_text())["baseline"][0]
    assert row["score"] == want
    assert row["source_score"] == 0.75
    assert row["derived_score"] == 0
    assert row["source_metric"]["reviewer"] == "fixed-judge"
    html = (report / "report.en.html").read_text(encoding="utf-8")
    assert 'Source score' in html
    assert 'Derived score' in html
    with (report / "records.csv").open(encoding="utf-8-sig", newline="") as stream:
        csvrow = next(csv.DictReader(stream))
    assert float(csvrow["source_score"]) == 0.75
    assert float(csvrow["derived_score"]) == 0
    result = replay_experiment(export_experiment(tmp_path, job["id"]), tmp_path / "relocated")
    assert result["numerical_replay"]["status"] == "passed"
    assert result["records_recomputed"]["baseline"][0]["score"] == want


def test_preserve_rejects_mixed_versions_and_uses_external_direction(tmp_path: Path) -> None:
    value = spec("preserve")
    value["source_metric"]["direction"] = "lower_is_better"
    job = run_experiment(tmp_path, create_experiment(tmp_path, value)["id"])
    assert job["assessment"]["effect"]["direction"] == "lower_is_better"
    value["predictions"]["candidate"][0]["source_metric"] = {
        **value["source_metric"],
        "version": "other",
    }
    with pytest.raises(ValueError, match="metric identity"):
        create_experiment(tmp_path, value)


def test_report_html_is_standalone_without_network_resources(tmp_path: Path) -> None:
    job = run_experiment(tmp_path, create_experiment(tmp_path, spec("preserve"))["id"])
    report = job_directory(tmp_path, job["id"]) / "report/report.en.html"
    html = report.read_text(encoding="utf-8")
    assert "<style>" in html and "<script>" not in html
    assert "http://" not in html and "https://" not in html and "src=\"http" not in html


def test_native_multiple_scores_require_explicit_selection(tmp_path: Path) -> None:
    from promptcontrollab.integrations.experiment_imports import normalize_import_document

    payload = {
        "text": json.dumps([{"id": "a", "output": "yes", "scores": {"judge": 0.7, "accuracy": 1}}])
    }
    with pytest.raises(ValueError, match="score_name"):
        normalize_import_document(payload, tmp_path)
    result = normalize_import_document({**payload, "score_name": "judge"}, tmp_path)
    assert result["predictions"][0]["source_score"] == 0.7


def test_preserve_requires_metric_identity_and_keeps_missing_score_unknown(tmp_path: Path) -> None:
    value = spec("preserve")
    del value["source_metric"]
    with pytest.raises(ValueError, match="source_metric"):
        create_experiment(tmp_path, value)
    value = spec("preserve")
    del value["predictions"]["baseline"][0]["score"]
    job = run_experiment(tmp_path, create_experiment(tmp_path, value)["id"])
    assert job["assessment"]["coverage"]["matched"] == 0
