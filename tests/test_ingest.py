import json
from pathlib import Path
from typing import Any

import pytest

from promptcontrollab.cli import main
from promptcontrollab.files import read_json, read_jsonl
from promptcontrollab.ingest import (
    ingest_langfuse_results,
    ingest_langsmith_results,
    ingest_promptfoo_results,
)


def test_ingest_promptfoo_v3_writes_pcl_run(tmp_path: Path) -> None:
    source = tmp_path / "promptfoo-results.json"
    out_dir = tmp_path / "runs" / "candidate"
    source.write_text(json.dumps(_promptfoo_v3_payload()), encoding="utf-8")

    payload = ingest_promptfoo_results(source_path=source, out_dir=out_dir)

    assert payload["count"] == 2
    predictions = read_jsonl(out_dir / "predictions.jsonl")
    assert [item["id"] for item in predictions] == ["test-0", "test-1"]
    assert [item["score"] for item in predictions] == [1.0, 0.0]
    assert predictions[0]["output"] == "4"
    assert predictions[0]["expected"] == "4"
    metrics = read_json(out_dir / "metrics.json")
    assert metrics["mean_score"] == 0.5
    assert metrics["by_slice"] == {"arithmetic": 0.5}
    manifest = read_json(out_dir / "manifest.json")
    assert manifest["mode"] == "promptfoo_ingest"
    assert manifest["method"] == "candidate"
    assert manifest["model"]["provider"] == "openai"
    assert manifest["model"]["model_id"] == "gpt-4o-mini"
    assert manifest["prompt"]["prompt_id"] == "candidate"
    assert manifest["prompt"]["prompt_hash"].startswith("sha256:")
    assert manifest["source_tool"] == "promptfoo"


def test_ingest_promptfoo_cli_filters_prompt_and_provider(tmp_path: Path) -> None:
    source = tmp_path / "promptfoo-results.json"
    out_dir = tmp_path / "runs" / "filtered"
    payload = _promptfoo_v3_payload()
    payload["results"].append(
        {
            "promptId": "baseline",
            "provider": {"id": "anthropic:claude-sonnet-4-20250514"},
            "testIdx": 0,
            "testCase": {"vars": {"slice": "arithmetic"}, "assert": [{"value": "4"}]},
            "response": {"output": "wrong"},
            "success": False,
            "score": 0,
        }
    )
    payload["prompts"].append({"id": "baseline", "raw": "Answer briefly.", "label": "Baseline"})
    source.write_text(json.dumps(payload), encoding="utf-8")

    assert (
        main(
            [
                "ingest",
                "promptfoo",
                "--input",
                str(source),
                "--out",
                str(out_dir),
                "--prompt-id",
                "candidate",
                "--provider",
                "openai:gpt-4o-mini",
                "--method",
                "candidate",
            ]
        )
        == 0
    )

    predictions = read_jsonl(out_dir / "predictions.jsonl")
    assert len(predictions) == 2
    manifest = read_json(out_dir / "manifest.json")
    assert manifest["promptfoo_filter"] == {
        "prompt_id": "candidate",
        "provider": "openai:gpt-4o-mini",
    }


def test_ingest_promptfoo_requires_filter_for_multiple_prompt_ids(tmp_path: Path) -> None:
    source = tmp_path / "promptfoo-results.json"
    payload = _promptfoo_v3_payload()
    payload["results"].append(
        {
            "promptId": "baseline",
            "provider": {"id": "openai:gpt-4o-mini"},
            "testIdx": 0,
            "testCase": {"assert": [{"value": "4"}]},
            "response": {"output": "wrong"},
            "success": False,
            "score": 0,
        }
    )
    source.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Multiple Promptfoo prompt ids"):
        ingest_promptfoo_results(source_path=source, out_dir=tmp_path / "run")


def test_ingest_promptfoo_v2_table_shape(tmp_path: Path) -> None:
    source = tmp_path / "promptfoo-v2.json"
    out_dir = tmp_path / "runs" / "v2"
    source.write_text(
        json.dumps(
            {
                "version": 2,
                "table": {
                    "body": [
                        {
                            "testIdx": 0,
                            "vars": {"slice": "format"},
                            "test": {"assert": [{"value": "YES"}]},
                            "outputs": [
                                {
                                    "provider": "openai:gpt-4o-mini",
                                    "prompt": "candidate",
                                    "text": "YES",
                                    "pass": True,
                                    "score": 1,
                                }
                            ],
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    ingest_promptfoo_results(source_path=source, out_dir=out_dir)

    predictions = read_jsonl(out_dir / "predictions.jsonl")
    assert predictions[0]["slice"] == "format"
    assert predictions[0]["score"] == 1.0


def test_ingest_langfuse_observations_writes_pcl_run(tmp_path: Path) -> None:
    source = tmp_path / "langfuse-export.json"
    out_dir = tmp_path / "runs" / "from-langfuse"
    source.write_text(json.dumps(_langfuse_payload()), encoding="utf-8")

    payload = ingest_langfuse_results(
        source_path=source,
        out_dir=out_dir,
        name="candidate",
        score_name="exact_match",
    )

    assert payload["count"] == 2
    assert payload["mean_score"] == 0.5
    predictions = read_jsonl(out_dir / "predictions.jsonl")
    assert [item["id"] for item in predictions] == ["obs-1", "obs-2"]
    assert [item["score"] for item in predictions] == [1.0, 0.0]
    assert predictions[0]["output"] == "4"
    assert predictions[0]["expected"] == "4"
    assert predictions[0]["slice"] == "arithmetic"
    metrics = read_json(out_dir / "metrics.json")
    assert metrics["mean_score"] == 0.5
    assert metrics["by_slice"] == {"arithmetic": 0.5}
    manifest = read_json(out_dir / "manifest.json")
    assert manifest["mode"] == "langfuse_ingest"
    assert manifest["method"] == "candidate"
    assert manifest["metric"] == "langfuse_score:exact_match"
    assert manifest["source_tool"] == "langfuse"
    assert manifest["model"]["provider"] == "openai"
    assert manifest["model"]["model_id"] == "gpt-4o-mini"
    assert manifest["langfuse_filter"] == {
        "name": "candidate",
        "score_name": "exact_match",
        "model": "gpt-4o-mini",
        "provider": "openai",
    }


def test_ingest_langfuse_cli_filters_name_score_and_model(tmp_path: Path) -> None:
    source = tmp_path / "langfuse-export.json"
    out_dir = tmp_path / "runs" / "filtered"
    payload = _langfuse_payload()
    payload["observations"].append(
        {
            "id": "obs-3",
            "name": "baseline",
            "type": "GENERATION",
            "input": {"expected": "4", "slice": "arithmetic"},
            "output": "wrong",
            "model": "claude-sonnet-4-20250514",
            "metadata": {"provider": "anthropic"},
            "scores": [{"name": "exact_match", "value": 0}],
        }
    )
    source.write_text(json.dumps(payload), encoding="utf-8")

    assert (
        main(
            [
                "ingest",
                "langfuse",
                "--input",
                str(source),
                "--out",
                str(out_dir),
                "--name",
                "candidate",
                "--score-name",
                "exact_match",
                "--model",
                "gpt-4o-mini",
                "--method",
                "candidate",
            ]
        )
        == 0
    )

    predictions = read_jsonl(out_dir / "predictions.jsonl")
    assert len(predictions) == 2
    manifest = read_json(out_dir / "manifest.json")
    assert manifest["langfuse_filter"] == {
        "name": "candidate",
        "score_name": "exact_match",
        "model": "gpt-4o-mini",
        "provider": "openai",
    }


def test_ingest_langfuse_requires_filter_for_multiple_names(tmp_path: Path) -> None:
    source = tmp_path / "langfuse-export.json"
    payload = _langfuse_payload()
    payload["observations"].append(
        {
            "id": "obs-3",
            "name": "baseline",
            "input": {"expected": "4"},
            "output": "wrong",
            "model": "gpt-4o-mini",
            "metadata": {"provider": "openai"},
            "scores": [{"name": "exact_match", "value": 0}],
        }
    )
    source.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Multiple Langfuse observation names"):
        ingest_langfuse_results(
            source_path=source,
            out_dir=tmp_path / "run",
            score_name="exact_match",
        )


def test_ingest_langsmith_runs_writes_pcl_run(tmp_path: Path) -> None:
    source = tmp_path / "langsmith-runs.json"
    out_dir = tmp_path / "runs" / "from-langsmith"
    source.write_text(json.dumps(_langsmith_payload()), encoding="utf-8")

    payload = ingest_langsmith_results(
        source_path=source,
        out_dir=out_dir,
        experiment="candidate",
        score_name="exact_match",
    )

    assert payload["count"] == 2
    assert payload["mean_score"] == 0.5
    predictions = read_jsonl(out_dir / "predictions.jsonl")
    assert [item["id"] for item in predictions] == ["run-1", "run-2"]
    assert [item["score"] for item in predictions] == [1.0, 0.0]
    assert predictions[0]["output"] == "4"
    assert predictions[0]["expected"] == "4"
    assert predictions[0]["slice"] == "arithmetic"
    manifest = read_json(out_dir / "manifest.json")
    assert manifest["mode"] == "langsmith_ingest"
    assert manifest["method"] == "candidate"
    assert manifest["metric"] == "langsmith_score:exact_match"
    assert manifest["source_tool"] == "langsmith"
    assert manifest["model"]["provider"] == "openai"
    assert manifest["model"]["model_id"] == "gpt-4o-mini"
    assert manifest["langsmith_filter"] == {
        "experiment": "candidate",
        "score_name": "exact_match",
        "model": "gpt-4o-mini",
        "provider": "openai",
    }


def test_ingest_langsmith_cli_filters_experiment_score_and_model(tmp_path: Path) -> None:
    source = tmp_path / "langsmith-runs.json"
    out_dir = tmp_path / "runs" / "filtered"
    payload = _langsmith_payload()
    payload["runs"].append(
        {
            "id": "run-3",
            "experiment_name": "baseline",
            "outputs": {"answer": "wrong"},
            "reference_outputs": {"answer": "4"},
            "feedback_stats": {"exact_match": 0},
            "extra": {
                "metadata": {
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-20250514",
                    "slice": "arithmetic",
                }
            },
        }
    )
    source.write_text(json.dumps(payload), encoding="utf-8")

    assert (
        main(
            [
                "ingest",
                "langsmith",
                "--input",
                str(source),
                "--out",
                str(out_dir),
                "--experiment",
                "candidate",
                "--score-name",
                "exact_match",
                "--model",
                "gpt-4o-mini",
                "--method",
                "candidate",
            ]
        )
        == 0
    )

    predictions = read_jsonl(out_dir / "predictions.jsonl")
    assert len(predictions) == 2
    manifest = read_json(out_dir / "manifest.json")
    assert manifest["langsmith_filter"]["experiment"] == "candidate"
    assert manifest["langsmith_filter"]["model"] == "gpt-4o-mini"


def test_ingest_langsmith_csv_export(tmp_path: Path) -> None:
    source = tmp_path / "langsmith-runs.csv"
    out_dir = tmp_path / "runs" / "csv"
    source.write_text(
        "\n".join(
            [
                "run_id,experiment_name,output,reference_output,exact_match,model,provider,slice",
                "run-1,candidate,YES,YES,1,gpt-4o-mini,openai,format",
                "run-2,candidate,NO,YES,0,gpt-4o-mini,openai,format",
            ]
        ),
        encoding="utf-8",
    )

    ingest_langsmith_results(
        source_path=source,
        out_dir=out_dir,
        experiment="candidate",
        score_name="exact_match",
    )

    metrics = read_json(out_dir / "metrics.json")
    assert metrics["mean_score"] == 0.5
    assert metrics["by_slice"] == {"format": 0.5}


def test_ingest_langsmith_requires_filter_for_multiple_experiments(tmp_path: Path) -> None:
    source = tmp_path / "langsmith-runs.json"
    payload = _langsmith_payload()
    payload["runs"].append(
        {
            "id": "run-3",
            "experiment_name": "baseline",
            "outputs": {"answer": "wrong"},
            "reference_outputs": {"answer": "4"},
            "feedback_stats": {"exact_match": 0},
            "extra": {"metadata": {"model": "gpt-4o-mini", "provider": "openai"}},
        }
    )
    source.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Multiple LangSmith experiments"):
        ingest_langsmith_results(
            source_path=source,
            out_dir=tmp_path / "run",
            score_name="exact_match",
        )


def _promptfoo_v3_payload() -> dict[str, Any]:
    return {
        "version": 3,
        "timestamp": "2026-06-13T00:00:00Z",
        "prompts": [
            {
                "id": "candidate",
                "raw": "Answer with only the final result.",
                "label": "Candidate",
                "provider": "openai:gpt-4o-mini",
            }
        ],
        "results": [
            {
                "promptId": "candidate",
                "provider": {"id": "openai:gpt-4o-mini", "label": "OpenAI mini"},
                "testIdx": 0,
                "testCase": {
                    "vars": {"slice": "arithmetic", "question": "2+2"},
                    "assert": [{"type": "equals", "value": "4"}],
                },
                "response": {"output": "4"},
                "success": True,
                "score": 1,
            },
            {
                "promptId": "candidate",
                "provider": {"id": "openai:gpt-4o-mini", "label": "OpenAI mini"},
                "testIdx": 1,
                "testCase": {
                    "vars": {"slice": "arithmetic", "question": "3+3"},
                    "assert": [{"type": "equals", "value": "6"}],
                },
                "response": {"output": "5"},
                "success": False,
                "score": 0,
            },
        ],
        "stats": {"successes": 1, "failures": 1, "errors": 0},
    }


def _langfuse_payload() -> dict[str, Any]:
    return {
        "observations": [
            {
                "id": "obs-1",
                "name": "candidate",
                "type": "GENERATION",
                "input": {"expected": "4", "slice": "arithmetic", "question": "2+2"},
                "output": "4",
                "model": "gpt-4o-mini",
                "metadata": {"provider": "openai"},
                "scores": [{"name": "exact_match", "value": 1}],
            },
            {
                "id": "obs-2",
                "name": "candidate",
                "type": "GENERATION",
                "input": {"expected": "6", "slice": "arithmetic", "question": "3+3"},
                "output": "5",
                "model": "gpt-4o-mini",
                "metadata": {"provider": "openai"},
                "scores": [{"name": "exact_match", "value": 0}],
            },
        ]
    }


def _langsmith_payload() -> dict[str, Any]:
    return {
        "runs": [
            {
                "id": "run-1",
                "experiment_name": "candidate",
                "inputs": {"question": "2+2"},
                "outputs": {"answer": "4"},
                "reference_outputs": {"answer": "4"},
                "feedback_stats": {"exact_match": 1},
                "extra": {
                    "metadata": {
                        "provider": "openai",
                        "model": "gpt-4o-mini",
                        "slice": "arithmetic",
                    }
                },
            },
            {
                "id": "run-2",
                "experiment_name": "candidate",
                "inputs": {"question": "3+3"},
                "outputs": {"answer": "5"},
                "reference_outputs": {"answer": "6"},
                "feedback_stats": {"exact_match": 0},
                "extra": {
                    "metadata": {
                        "provider": "openai",
                        "model": "gpt-4o-mini",
                        "slice": "arithmetic",
                    }
                },
            },
        ]
    }
