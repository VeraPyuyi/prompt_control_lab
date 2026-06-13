import json
from pathlib import Path
from typing import Any

import pytest

from promptcontrollab.cli import main
from promptcontrollab.files import read_json, read_jsonl
from promptcontrollab.ingest import ingest_langfuse_results, ingest_promptfoo_results


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
