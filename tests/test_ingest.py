import json
from pathlib import Path
from typing import Any

import pytest

from promptcontrollab.cli import main
from promptcontrollab.files import read_json, read_jsonl
from promptcontrollab.ingest import ingest_promptfoo_results


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
