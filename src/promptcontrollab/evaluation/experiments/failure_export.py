"""Create a new dataset version from selected experiment failures."""

from __future__ import annotations

import copy
import time
from pathlib import Path
from typing import Any

from .storage import read_json, snapshot_hash, write_json


def export_failure_dataset(
    job_dir: Path,
    *,
    selected_ids: list[str],
    confirmed_expected: dict[str, str],
    version: str,
) -> dict[str, Any]:
    """Write a new dataset version from confirmed failure records and lineage."""
    spec = read_json(job_dir / "spec.json")
    records = [read_json(path) for path in sorted((job_dir / "records").glob("*.json"))]
    tasks = {task["id"]: task for task in spec["data"]}
    if not selected_ids:
        raise ValueError("Select at least one failure to export")
    if not version.strip():
        raise ValueError("Dataset version is required")
    exported = []
    for item_id in selected_ids:
        if item_id not in confirmed_expected:
            raise ValueError(f"Expected answer for {item_id} must be confirmed")
        task = tasks[item_id]
        source_rows = [row for row in records if row.get("id") == item_id]
        exported.append(
            {
                "id": item_id,
                "input": task["input"],
                "expected": confirmed_expected[item_id],
                "slice": task.get("slice", "default"),
                "meta": {
                    **copy.deepcopy(task.get("meta", {})),
                    "dataset_version": version,
                    "source_experiment_id": read_json(job_dir / "job.json")["id"],
                    "source_run": spec.get("name"),
                    "withheld_lineage": task.get("meta", {}).get("withheld_lineage"),
                    "failure_export": True,
                    "not_for_current_withheld_training": True,
                },
                "lineage": {
                    "baseline": next(
                        (row for row in source_rows if row.get("name") == "baseline"), None
                    ),
                    "candidate": next(
                        (row for row in source_rows if row.get("name") == "candidate"), None
                    ),
                },
            }
        )
    payload = {
        "schema_version": "experiment-failure-dataset/v1",
        "version": version,
        "created_at": time.time(),
        "source_experiment_id": read_json(job_dir / "job.json")["id"],
        "source_snapshot_hash": snapshot_hash(spec),
        "records": exported,
        "usage": "for_follow_up_experiments_only",
    }
    target = job_dir / "datasets" / f"{version}.json"
    write_json(target, payload)
    return payload
