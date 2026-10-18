"""Public benchmark protocol must reject incomplete declarations."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from promptcontrollab.evaluation.experiments.protocol import validate_protocol


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


def _protocol() -> dict[str, Any]:
    return {
        "protocol_version": "1",
        "benchmark_name": "offline fixture",
        "provider": "imported",
        "model": "declared",
        "prompt_version": "v1",
        "dataset_version": "v1",
        "metric_id": "exact_match",
        "metric_version": "1",
        "score_mode": "recompute",
        "negative_results_allowed": True,
        "replay_entry": "experiment.zip",
        "limitations": ["synthetic, no competitor claim"],
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("protocol_version", "99"),
        ("negative_results_allowed", "true"),
        ("negative_results_allowed", False),
        ("limitations", "none"),
        ("metric_version", 1),
        ("score_mode", "pooled"),
        ("model", ""),
        ("replay_entry", "https://example.org/experiment.zip"),
    ],
)
def test_protocol_rejects_invalid_fixed_schema(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        validate_protocol({**_protocol(), field: value})


def test_protocol_cli_validates_and_replays_real_bundle(tmp_path: Path) -> None:
    from promptcontrollab.evaluation.experiments import (
        create_experiment,
        export_experiment,
        run_experiment,
    )

    spec = {
        "operation": "import",
        "synthetic": True,
        "data": [{"id": "a", "input": "task", "expected": "yes"}],
        "predictions": {arm: [{"id": "a", "output": "yes"}] for arm in ("baseline", "candidate")},
    }
    job = run_experiment(tmp_path, create_experiment(tmp_path, spec)["id"])
    bundle = export_experiment(tmp_path, job["id"])
    (tmp_path / "experiment.zip").write_bytes(bundle.read_bytes())
    document = tmp_path / "protocol.json"
    document.write_text(json.dumps(_protocol()), encoding="utf-8")
    command = [
        sys.executable,
        "-m",
        "promptcontrollab",
        "experiment",
        "protocol",
        "--input",
        str(document),
        "--out",
        str(tmp_path / "replay"),
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["protocol_status"] == "passed"
    assert receipt["replay"]["integrity"]["status"] == "passed"
    assert receipt["replay"]["numerical_replay"]["status"] == "passed"
    document.write_text(json.dumps({**_protocol(), "metric_version": "99"}), encoding="utf-8")
    bad = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
    assert bad.returncode != 0
    assert "metric" in bad.stderr.lower()
