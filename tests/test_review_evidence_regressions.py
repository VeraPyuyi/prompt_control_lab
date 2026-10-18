"""Review reproductions: score identity, independent units, cost provenance and reuse."""

from __future__ import annotations

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
from promptcontrollab.evaluation.experiments.assessment import assess
from promptcontrollab.evaluation.experiments.failure_export import export_failure_dataset
from promptcontrollab.evaluation.experiments.replay import replay_experiment
from promptcontrollab.evaluation.experiments.storage import job_directory, read_json
from promptcontrollab.integrations.experiment_inputs import parse_dataset


def _import_spec(mode: str = "preserve") -> dict[str, Any]:
    return {
        "operation": "import",
        "metric": "json_valid@1",
        "score_mode": mode,
        "source_metric": {
            "id": "external-judge",
            "version": "2",
            "source": "fixture",
            "reviewer": "reviewer",
            "direction": "lower_is_better",
            "scale": [0, 1],
        },
        "data": [{"id": "a", "input": "unique task", "expected": "{}"}],
        "predictions": {
            "baseline": [{"id": "a", "output": "{}", "score": 0.25}],
            "candidate": [{"id": "a", "output": "{}", "score": 0.75}],
        },
    }


@pytest.mark.parametrize("mode,score", [("preserve", 0.25), ("recompute", 1.0)])
def test_json_import_selected_score_survives_reports_and_bundle_replay(
    tmp_path: Path,
    mode: str,
    score: float,
) -> None:
    job = run_experiment(tmp_path, create_experiment(tmp_path, _import_spec(mode))["id"])
    directory = job_directory(tmp_path, job["id"])
    saved = read_json(directory / "report/records.json")["baseline"][0]
    assert saved["status"] == "completed"
    assert saved["score"] == score
    assert saved["source_score"] == 0.25
    assert saved["derived_score"] == 1
    assert job["assessment"]["coverage"]["matched"] == 1
    assert job["assessment"]["practical"]["baseline"]["score_mean"] == score
    assert job["assessment"]["practical"]["score_direction"] == (
        "lower_is_better" if mode == "preserve" else "higher_is_better"
    )
    with (directory / "report/records.csv").open(encoding="utf-8-sig", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert float(row["score"]) == score
    assert float(row["source_score"]) == 0.25
    assert float(row["derived_score"]) == 1
    for language in ("en", "zh"):
        page = (directory / f"report/report.{language}.html").read_text(encoding="utf-8")
        assert "<td>0.25</td>" in page and "<td>1.0</td>" in page
    replay = replay_experiment(export_experiment(tmp_path, job["id"]), tmp_path / "replay")
    assert replay["integrity"]["status"] == "passed"
    assert replay["numerical_replay"]["status"] == "passed"
    assert replay["numerical_replay"]["assessment_differences"] == []
    assert replay["records_recomputed"]["baseline"][0]["score"] == score
    with (tmp_path / "replay/records.recomputed.csv").open(encoding="utf-8", newline="") as stream:
        replay_row = next(csv.DictReader(stream))
    assert float(replay_row["source_score"]) == 0.25
    assert float(replay_row["derived_score"]) == 1
    replay_page = (tmp_path / "replay/report.en.html").read_text(encoding="utf-8")
    assert "<th>Source score</th>" in replay_page
    assert "<th>Derived score</th>" in replay_page


@pytest.mark.parametrize("groups", [1, 2, 30])
def test_task_group_boundaries_use_independent_units(groups: int) -> None:
    tasks = [
        {"id": str(i), "input": f"independent rooftop {i}", "meta": {"task": str(i % groups)}}
        for i in range(30)
    ]
    rows = [{"id": str(i), "status": "completed", "score": 0.0} for i in range(30)]
    spec = {
        "data": tasks,
        "operation": "run",
        "metric": "exact_match",
        "seed": 0,
        "baseline": {},
        "candidate": {},
        "budget": {},
    }
    result = assess(
        spec,
        rows,
        [{**r, "score": 1.0} for r in rows],
        expected_ids=[str(r["id"]) for r in rows],
        scope="evaluation",
        budget={},
    )
    stats = result["effect"]["statistics"]
    assert stats["record_count"] == 30
    assert stats["independent_group_count"] == groups
    if groups == 1:
        assert result["effect"]["status"] == "insufficient_data"
        assert stats["bootstrap_ci"] is None
        assert stats["holm_adjusted_p_value"] is None
        assert stats["inference_status"].startswith("descriptive")
    elif groups == 2:
        assert result["effect"]["status"] == "uncertain"
        assert stats["bootstrap_ci"] is None
        assert stats["permutation_p_value"] is None
        assert stats["holm_adjusted_p_value"] is None
        assert stats["inference_status"] == "descriptive_only_insufficient_groups"
        assert stats["estimation_target"] == "mean_task_effect"
    else:
        assert stats["inference_status"] == "cluster_bootstrap"
        assert stats["estimation_target"] == "mean_task_effect"
        assert result["effect"]["status"] == "improved"


def test_shared_input_does_not_merge_explicit_task_units_or_enable_inference() -> None:
    rows = [{"id": str(i), "status": "completed", "score": 0.0} for i in range(30)]
    result = assess(
        {
            "operation": "run",
            "metric": "exact_match",
            "seed": 0,
            "baseline": {},
            "candidate": {},
            "budget": {},
            "data": [
                {"id": str(i), "input": "shared input", "meta": {"task": str(i % 2)}}
                for i in range(30)
            ],
        },
        rows,
        [{**row, "score": 1.0} for row in rows],
        expected_ids=[str(i) for i in range(30)],
        scope="evaluation",
        budget={},
    )
    stats = result["effect"]["statistics"]
    assert stats["independent_group_count"] == stats["n"] == 2
    assert stats["record_count"] == 30
    assert stats["bootstrap_ci"] is None
    assert stats["permutation_p_value"] is None
    assert stats["holm_adjusted_p_value"] is None
    assert stats.get("iid_diagnostics", {}).get("bootstrap_ci") is None
    assert stats["inference_status"] == "descriptive_only_nonindependent_rows"
    assert result["effect"]["status"] != "improved"


def test_independent_rooftop_rows_without_groups_keep_inference() -> None:
    spec = {
        "operation": "run",
        "metric": "exact_match",
        "seed": 0,
        "baseline": {},
        "candidate": {},
        "budget": {},
        "data": [{"id": str(i), "input": f"independent rooftop {i}"} for i in range(30)],
    }
    rows = [{"id": str(i), "status": "completed", "score": 0.0} for i in range(30)]
    result = assess(
        spec,
        rows,
        [{**r, "score": 1.0} for r in rows],
        expected_ids=[str(i) for i in range(30)],
        scope="evaluation",
        budget={},
    )
    assert result["effect"]["status"] == "improved"
    assert result["effect"]["statistics"]["independent_group_count"] == 30
    assert result["effect"]["statistics"]["inference_status"] == "iid_assumed"


def test_missing_external_score_keeps_derived_score_and_replay_integrity(tmp_path: Path) -> None:
    spec = _import_spec()
    del spec["predictions"]["baseline"][0]["score"]
    job = run_experiment(tmp_path, create_experiment(tmp_path, spec)["id"])
    replay = replay_experiment(export_experiment(tmp_path, job["id"]), tmp_path / "replay")
    assert replay["integrity"]["status"] == "passed"
    assert replay["records_recomputed"]["baseline"][0]["derived_score"] == 1
    assert replay["records_recomputed"]["baseline"][0]["score"] is None


def test_recompute_keeps_the_actual_external_metric_version(tmp_path: Path) -> None:
    spec = _import_spec("recompute")
    identity = {**spec["source_metric"], "version": "other"}
    spec["predictions"]["candidate"][0]["source_metric"] = identity
    job = run_experiment(tmp_path, create_experiment(tmp_path, spec)["id"])
    row = read_json(job_directory(tmp_path, job["id"]) / "report/records.json")["candidate"][0]
    assert row["source_metric"] == identity
    assert row["score"] == row["derived_score"] == 1


def _priced_spec(currency: str = "USD") -> dict[str, Any]:
    return {
        "operation": "run",
        "data": [{"id": "a", "input": "task", "expected": "yes"}],
        "baseline": {"provider": "openai", "model": "base", "prompt": "base"},
        "candidate": {"provider": "openai", "model": "cand", "prompt": "cand"},
        "budget": {
            "price_snapshots": [
                {
                    "provider": "openai",
                    "model": model,
                    "phase": "evaluation",
                    "currency": curr,
                    "effective_date": "2026-10-18",
                    "input_cost_per_million": rate,
                    "output_cost_per_million": rate + 1,
                    "source": "fixed test tariff",
                }
                for model, curr, rate in (("base", "USD", 1), ("cand", currency, 3))
            ]
        },
    }


def _fixed_tokens(**kwargs: Any) -> dict[str, Any]:
    return {
        "output": "yes",
        "model_id": kwargs["model"],
        "usage": {"input_tokens": 1000, "output_tokens": 100},
    }


def test_estimated_cost_is_not_reported_or_actual_and_replays(tmp_path: Path) -> None:
    job = run_experiment(tmp_path, create_experiment(tmp_path, _priced_spec())["id"], _fixed_tokens)
    directory = job_directory(tmp_path, job["id"])
    rows = read_json(directory / "report/records.json")
    for arm, want in (("baseline", 0.0012), ("candidate", 0.0034)):
        row = rows[arm][0]
        assert row["actual_cost"] is None
        assert row["reported_cost"] is None
        assert row["estimated_cost"] == pytest.approx(want)
        assert row["cost_currency"] == "USD"
        assert row["price_snapshot"]["source"] == "fixed test tariff"
        summary = job["assessment"]["practical"][arm]
        assert summary["estimated_cost"] == pytest.approx(want)
        assert summary["actual_cost"] is None
        assert summary["cost_basis"] == "estimated"
    assert job["budget"]["reported_cost"] is None
    assert rows["baseline"][0]["reserved_price_snapshot"]["source"] == "fixed test tariff"
    assert job["budget"]["actual_cost"] is None
    assert job["budget"]["estimated_cost"] == pytest.approx(0.0046)
    assert job["assessment"]["practical"]["delta"]["cost"] == pytest.approx(0.0022)
    with (directory / "report/records.csv").open(encoding="utf-8-sig", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["actual_cost"] == row["reported_cost"] == ""
    assert row["cost_currency"] == "USD"
    assert "Estimated cost" in (directory / "report/report.en.html").read_text(encoding="utf-8")
    replay = replay_experiment(export_experiment(tmp_path, job["id"]), tmp_path / "replay")
    assert replay["numerical_replay"]["status"] == "passed"
    assert replay["numerical_replay"]["assessment_differences"] == []


def test_currency_totals_are_separate_and_cross_currency_delta_is_unknown(tmp_path: Path) -> None:
    job = run_experiment(
        tmp_path,
        create_experiment(tmp_path, _priced_spec("EUR"))["id"],
        _fixed_tokens,
    )
    assert job["budget"]["estimated_cost"] is None
    assert job["budget"]["cost_by_currency"]["USD"]["estimated_cost"] == pytest.approx(0.0012)
    assert job["budget"]["cost_by_currency"]["EUR"]["estimated_cost"] == pytest.approx(0.0034)
    assert job["assessment"]["practical"]["delta"]["cost"] is None
    assert job["assessment"]["cost"]["status"] == "unknown"


def test_reported_cost_does_not_require_a_price_snapshot(tmp_path: Path) -> None:
    spec = _priced_spec()
    spec["budget"] = {}

    def provider(**kwargs: Any) -> dict[str, Any]:
        return {**_fixed_tokens(**kwargs), "actual_cost": 0.007, "cost_currency": "USD"}

    job = run_experiment(tmp_path, create_experiment(tmp_path, spec)["id"], provider)
    summary = job["assessment"]["practical"]["baseline"]
    assert summary["actual_cost"] == summary["reported_cost"] == pytest.approx(0.007)
    assert summary["estimated_cost"] is None
    assert summary["cost_basis"] == "reported"


def test_imported_snapshot_only_usage_is_estimated_not_actual(tmp_path: Path) -> None:
    spec = _priced_spec()
    spec.update(
        operation="import",
        predictions={
            arm: [
                {"id": "a", "output": "yes", "usage": {"input_tokens": 1000, "output_tokens": 100}}
            ]
            for arm in ("baseline", "candidate")
        },
    )
    job = run_experiment(tmp_path, create_experiment(tmp_path, spec)["id"])
    summary = job["assessment"]["practical"]["candidate"]
    assert summary["estimated_cost"] == pytest.approx(0.0034)
    assert summary["actual_cost"] is None


def test_replay_recomputes_estimated_amount_from_saved_tokens(tmp_path: Path) -> None:
    from promptcontrollab.evaluation.experiments.storage import write_json

    job = run_experiment(tmp_path, create_experiment(tmp_path, _priced_spec())["id"], _fixed_tokens)
    directory = job_directory(tmp_path, job["id"])
    for path in (directory / "calls").glob("*.json"):
        row = read_json(path)
        row["estimated_cost"] = 99
        write_json(path, row)
    replay = replay_experiment(export_experiment(tmp_path, job["id"]), tmp_path / "replay")
    assert replay["assessment_recomputed"]["cost"]["estimated_cost"] == pytest.approx(0.0046)


def test_cost_limit_never_adds_different_currencies(tmp_path: Path) -> None:
    spec = _priced_spec("EUR")
    spec["budget"].update(max_cost=1, currency="USD")
    job = run_experiment(tmp_path, create_experiment(tmp_path, spec)["id"], _fixed_tokens)
    assert job["status"] == "stopped"
    assert job["stop_reason"] == "cost_unknown"
    assert job["budget"]["calls"] == 1


def test_failure_dataset_export_import_new_experiment_and_replay(tmp_path: Path) -> None:
    first = run_experiment(tmp_path, create_experiment(tmp_path, _import_spec())["id"])
    directory = job_directory(tmp_path, first["id"])
    before = {name: (directory / name).read_bytes() for name in ("spec.json", "job.json")}
    exported = export_failure_dataset(
        directory,
        selected_ids=["a"],
        confirmed_expected={"a": "{}"},
        version="follow-up-v2",
    )
    tasks = parse_dataset(json.dumps(exported), "json")
    assert tasks[0]["id"] == "a" and tasks[0]["expected"] == "{}"
    assert tasks[0]["meta"]["dataset_version"] == "follow-up-v2"
    assert tasks[0]["meta"]["source_experiment_id"] == first["id"]
    assert tasks[0]["meta"]["not_for_current_withheld_training"] is True
    assert tasks[0]["meta"]["failure_lineage"] == exported["records"][0]["lineage"]
    spec = _import_spec()
    spec["data"] = tasks
    second = run_experiment(tmp_path, create_experiment(tmp_path, spec)["id"])
    assert first["id"] != second["id"]
    assert read_json(job_directory(tmp_path, second["id"]) / "data.json")["records"] == tasks
    for name, content in before.items():
        assert (directory / name).read_bytes() == content
    replay = replay_experiment(export_experiment(tmp_path, second["id"]), tmp_path / "replay")
    assert replay["integrity"]["status"] == replay["numerical_replay"]["status"] == "passed"
    from promptcontrollab.evaluation.experiments.runtime import ExperimentRuntime

    runtime = ExperimentRuntime(
        directory, read_json(directory / "spec.json"), read_json(directory / "split.json")
    )
    try:
        with pytest.raises(ValueError, match="immutable snapshot"):
            runtime.evaluate("baseline", spec.get("baseline", {}), tasks, "evaluation")
    finally:
        runtime.close()
