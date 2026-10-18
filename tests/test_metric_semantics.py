"""Versioned JSON metrics must not redefine legacy empty-output scores."""

import json
from pathlib import Path
from typing import Any

import pytest

from promptcontrollab.evaluation import metrics


@pytest.mark.parametrize("output,want", [("", 1.0), ("  ", 1.0), ("garbage", 0.0)])
def test_legacy_format_error_remains_an_empty_output_check(output: str, want: float) -> None:
    assert metrics.score_output(output, "", "format_error") == want


@pytest.mark.parametrize(
    "output,metric,expected,score,reason",
    [
        ("", "json_valid@1", "", 0.0, "missing_output"),
        ("garbage", "json_valid@1", "", 0.0, "invalid_json"),
        ('{"a":', "json_valid@1", "", 0.0, "invalid_json"),
        ('{"a": 1}', "json_valid@1", "", 1.0, None),
        ("NaN", "json_valid@1", "", 0.0, "invalid_json"),
        ("{}", "json_schema@1", '{"type":"object","required":["a"]}', 0.0, "required:$.a"),
        ('{"a":"x"}', "json_schema@1", '{"properties":{"a":{"type":"integer"}}}', 0.0, "type:$.a"),
        ('{"a":"x"}', "json_schema@1", '{"properties":{"a":{"enum":["y"]}}}', 0.0, "enum:$.a"),
        ('{"a":1}', "json_schema@1", '{"properties":{"a":{"type":"integer"}}}', 1.0, None),
    ],
)
def test_json_metrics_explain_failures(
    output: str, metric: str, expected: str, score: float, reason: str | None
) -> None:
    assert metrics.score_output(output, expected, metric) == score
    detail = metrics.score_details(output, expected, metric)
    assert detail["score"] == score
    assert detail["failure_reason"] == reason
    assert detail["metric_version"] == "1"
    assert detail["direction"] == "higher_is_better"
    assert detail["metric_id"] == metric.split("@")[0]
    json.dumps(detail, allow_nan=False)


@pytest.mark.parametrize("operation", ["run", "import"])
def test_json_experiment_records_and_replay_keep_scorer_evidence(
    tmp_path: Path, operation: str
) -> None:
    from promptcontrollab.evaluation.experiments import (
        create_experiment,
        export_experiment,
        run_experiment,
    )
    from promptcontrollab.evaluation.experiments.replay import replay_experiment

    spec: dict[str, Any] = {
        "operation": operation,
        "metric": "json_schema@1",
        "data": [{"id": "a", "input": "task", "expected": '{"required":["a"]}'}],
        "baseline": {"provider": "openai", "model": "offline", "prompt": "before"},
        "candidate": {"provider": "openai", "model": "offline", "prompt": "after"},
    }
    if operation == "import":
        spec["predictions"] = {
            arm: [{"id": "a", "output": "{}"}] for arm in ("baseline", "candidate")
        }
    job = create_experiment(tmp_path, spec)
    run_experiment(tmp_path, job["id"], lambda **kw: {"output_text": "{}"})
    result = replay_experiment(export_experiment(tmp_path, job["id"]), tmp_path / "replayed")
    assert result["numerical_replay"]["status"] == "passed"
    for rows in result["records_recomputed"].values():
        assert rows[0]["metric_id"] == "json_schema"
        assert rows[0]["metric_version"] == "1"
        assert rows[0]["failure_reason"] == "required:$.a"


def test_unknown_metric_version_and_invalid_schema_are_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported metric"):
        metrics.score_output("{}", "", "json_valid@2")
    with pytest.raises(ValueError, match="Invalid JSON schema"):
        metrics.score_output("", '{"type":"bogus"}', "json_schema@1")
