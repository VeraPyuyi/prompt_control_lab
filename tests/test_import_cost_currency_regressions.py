"""Imported receipts retain per-kind currencies without requiring a price snapshot."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest

from promptcontrollab.evaluation.experiments import (
    create_experiment,
    export_experiment,
    run_experiment,
)
from promptcontrollab.evaluation.experiments.replay import replay_experiment
from promptcontrollab.evaluation.experiments.storage import job_directory, read_json


@pytest.mark.parametrize("kind", ["actual", "reported", "both"])
@pytest.mark.parametrize("candidate_currency", ["USD", "EUR"])
@pytest.mark.parametrize("baseline_amount", [0.0, 0.007])
def test_imported_receipt_currency_survives_reports_and_replay_without_prices(
    tmp_path: Path, kind: str, candidate_currency: str, baseline_amount: float
) -> None:
    predictions: dict[str, Any] = {}
    for arm, amount, currency in (
        ("baseline", baseline_amount, "USD"),
        ("candidate", 0.009, candidate_currency),
    ):
        row: dict[str, Any] = {"id": "a", "output": "yes"}
        for cost_kind in (("actual", "reported") if kind == "both" else (kind,)):
            row[f"{cost_kind}_cost"] = amount
            row[f"{cost_kind}_cost_currency"] = currency
        predictions[arm] = [row]
    spec = {
        "operation": "import",
        "data": [{"id": "a", "input": "independent task", "expected": "yes"}],
        "predictions": predictions,
    }
    job = run_experiment(tmp_path, create_experiment(tmp_path, spec)["id"])
    directory = job_directory(tmp_path, job["id"])
    records = read_json(directory / "report/records.json")
    for arm, amount, currency in (
        ("baseline", baseline_amount, "USD"),
        ("candidate", 0.009, candidate_currency),
    ):
        row = records[arm][0]
        assert row["reported_cost"] == amount
        assert row["reported_cost_currency"] == currency
        assert row["actual_cost"] == (amount if kind in {"actual", "both"} else None)
        if kind in {"actual", "both"}:
            assert row["actual_cost_currency"] == currency
        summary = job["assessment"]["practical"][arm]
        assert summary["reported_cost"] == summary["known_cost"] == amount
        assert summary["estimated_cost"] is None
        assert summary["cost_status"] == "known"
        assert summary["cost_currency"] == currency
        assert summary["cost_by_currency"][currency]["reported_cost"] == amount
        assert "unknown" not in summary["cost_by_currency"]
        assert summary["cost_basis"] == "reported"
    delta = job["assessment"]["practical"]["delta"]["cost"]
    if candidate_currency == "USD":
        assert delta == pytest.approx(0.009 - baseline_amount)
    else:
        assert delta is None
        assert job["assessment"]["practical"]["cost_currency"] is None
    with (directory / "report/records.csv").open(encoding="utf-8-sig", newline="") as stream:
        csv_rows = list(csv.DictReader(stream))
    assert {row["reported_cost_currency"] for row in csv_rows} == {"USD", candidate_currency}
    assert sorted(float(row["reported_cost"]) for row in csv_rows) == [baseline_amount, 0.009]
    for language in ("en", "zh"):
        page = (directory / f"report/report.{language}.html").read_text(encoding="utf-8")
        assert f"{baseline_amount} USD" in page
        assert f"0.009 {candidate_currency}" in page
    assert job["budget"]["calls"] == 0
    replay = replay_experiment(export_experiment(tmp_path, job["id"]), tmp_path / "replay")
    assert replay["integrity"]["status"] == "passed"
    assert replay["numerical_replay"]["status"] == "passed"
    assert replay["numerical_replay"]["assessment_differences"] == []


def test_imported_actual_and_reported_currencies_stay_separate(tmp_path: Path) -> None:
    row = {
        "id": "a",
        "output": "yes",
        "actual_cost": 0.007,
        "actual_cost_currency": "USD",
        "reported_cost": 0.009,
        "reported_cost_currency": "EUR",
    }
    spec = {
        "operation": "import",
        "data": [{"id": "a", "input": "task", "expected": "yes"}],
        "predictions": {"baseline": [row], "candidate": [row]},
    }
    job = run_experiment(tmp_path, create_experiment(tmp_path, spec)["id"])
    record = read_json(job_directory(tmp_path, job["id"]) / "report/records.json")["baseline"][0]
    assert record["actual_cost_currency"] == "USD"
    assert record["reported_cost_currency"] == "EUR"
    summary = job["assessment"]["practical"]["baseline"]
    assert summary["cost_by_currency"]["USD"]["actual_cost"] == 0.007
    assert summary["cost_by_currency"]["EUR"]["reported_cost"] == 0.009
    assert summary["known_cost"] is None
    assert summary["cost_status"] == "unknown"
    assert job["assessment"]["practical"]["delta"]["cost"] is None
