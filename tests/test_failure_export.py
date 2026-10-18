"""Failure exports must create a new dataset version with lineage."""

from pathlib import Path

from promptcontrollab.evaluation.experiments import create_experiment, run_experiment
from promptcontrollab.evaluation.experiments.failure_export import export_failure_dataset
from promptcontrollab.evaluation.experiments.storage import job_directory


def test_failure_export_keeps_withheld_lineage_and_requires_confirmed_expected(
    tmp_path: Path,
) -> None:
    spec = {
        "operation": "import",
        "data": [
            {
                "id": "a",
                "input": "task",
                "expected": "yes",
                "meta": {"withheld_lineage": "withheld-v1"},
            }
        ],
        "predictions": {
            "baseline": [{"id": "a", "output": "no"}],
            "candidate": [{"id": "a", "output": "no"}],
        },
    }
    job = run_experiment(tmp_path, create_experiment(tmp_path, spec)["id"])
    directory = job_directory(tmp_path, job["id"])
    payload = export_failure_dataset(
        directory,
        selected_ids=["a"],
        confirmed_expected={"a": "yes"},
        version="failures-2026-10-18",
    )
    assert payload["records"][0]["expected"] == "yes"
    assert payload["records"][0]["meta"]["not_for_current_withheld_training"] is True
    assert payload["records"][0]["meta"]["withheld_lineage"] == "withheld-v1"
    assert (directory / "datasets/failures-2026-10-18.json").is_file()
