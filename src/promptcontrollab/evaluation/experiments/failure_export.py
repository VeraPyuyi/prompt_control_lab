"""Create a new dataset version from selected experiment failures."""

from __future__ import annotations

import copy
import re
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
    if (
        not isinstance(selected_ids, list)
        or not selected_ids
        or any(not isinstance(item, str) or item not in tasks for item in selected_ids)
    ):
        raise ValueError("Select at least one known example to export")
    if not isinstance(version, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", version
    ):
        raise ValueError("Dataset version must be a filename-safe identifier (1-96 characters)")
    target = job_dir / "datasets" / f"{version}.json"
    if target.resolve().parent.parent != job_dir.resolve():
        raise ValueError("Dataset export cannot escape its experiment")
    if target.exists():
        raise ValueError("Dataset version already exists; choose a new version")
    if not isinstance(confirmed_expected, dict):
        raise ValueError("Expected answers must be confirmed by example ID")
    exported = []
    for item_id in dict.fromkeys(selected_ids):
        if not isinstance(confirmed_expected.get(item_id), str):
            raise ValueError(f"Expected answer for {item_id} must be confirmed as text")
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
    write_json(target, payload)
    return payload
