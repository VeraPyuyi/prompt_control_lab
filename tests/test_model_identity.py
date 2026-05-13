from __future__ import annotations

import json
from pathlib import Path

import pytest

from promptcontrollab.cli import main
from promptcontrollab.files import write_jsonl
from promptcontrollab.model_identity import (
    compare_model_identities,
    detect_model_identity,
)


def test_detect_model_identity_from_openai_response(tmp_path: Path) -> None:
    response = tmp_path / "response.json"
    response.write_text(
        json.dumps({"provider": "openai", "model": "gpt-5.2", "output": []}),
        encoding="utf-8",
    )

    identity = detect_model_identity(response_path=response)

    assert identity.provider == "openai"
    assert identity.model_id == "gpt-5.2"
    assert identity.source == "response.model"
    assert identity.confidence == "high"


def test_detect_model_identity_from_anthropic_nested_response(tmp_path: Path) -> None:
    response = tmp_path / "response.json"
    response.write_text(
        json.dumps({"message": {"model": "claude-sonnet-4-20250514"}}),
        encoding="utf-8",
    )

    identity = detect_model_identity(response_path=response)

    assert identity.provider == "anthropic"
    assert identity.model_id == "claude-sonnet-4-20250514"
    assert identity.source == "response.message.model"


def test_model_detect_cli_writes_json_from_response(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    response = tmp_path / "response.json"
    out = tmp_path / "model_identity.json"
    response.write_text(json.dumps({"model": "gpt-4o"}), encoding="utf-8")

    assert main(["model-detect", "--response", str(response), "--out", str(out)]) == 0

    payload = json.loads(capsys.readouterr().out)
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert payload["model_id"] == "gpt-4o"
    assert saved["provider"] == "openai"


def test_eval_manifest_records_model_from_predictions(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks.jsonl"
    predictions = tmp_path / "predictions.jsonl"
    run = tmp_path / "run"
    write_jsonl(
        tasks,
        [{"id": "one", "input": "1+1", "expected": "2", "slice": "arith"}],
    )
    write_jsonl(
        predictions,
        [{"id": "one", "output": "2", "model": "gpt-5.2", "provider": "openai"}],
    )

    assert (
        main(
            [
                "eval",
                "--data",
                str(tasks),
                "--predictions",
                str(predictions),
                "--out",
                str(run),
            ]
        )
        == 0
    )

    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    scored = [
        json.loads(line)
        for line in (run / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert manifest["model"]["model_id"] == "gpt-5.2"
    assert manifest["model"]["source"] == "predictions.model"
    assert scored[0]["model"]["model_id"] == "gpt-5.2"


def test_compare_model_identities_warns_on_prompt_unclean_comparison() -> None:
    warnings = compare_model_identities(
        {"provider": "openai", "model_id": "gpt-4o"},
        {"provider": "openai", "model_id": "gpt-5.2"},
    )

    assert any("not a clean prompt-only comparison" in warning for warning in warnings)


def test_analyze_report_warns_when_baseline_and_candidate_models_differ(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks.jsonl"
    baseline = tmp_path / "baseline.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    run = tmp_path / "run"
    write_jsonl(tasks, [{"id": "one", "input": "1+1", "expected": "2", "slice": "arith"}])
    write_jsonl(baseline, [{"id": "one", "output": "2", "model": "gpt-4o"}])
    write_jsonl(candidate, [{"id": "one", "output": "2", "model": "gpt-5.2"}])

    assert (
        main(
            [
                "analyze",
                "--data",
                str(tasks),
                "--baseline-predictions",
                str(baseline),
                "--candidate-predictions",
                str(candidate),
                "--out",
                str(run),
                "--bootstrap-samples",
                "5",
                "--permutation-samples",
                "5",
            ]
        )
        == 0
    )

    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    report = (run / "report.md").read_text(encoding="utf-8")
    assert manifest["baseline_model"]["model_id"] == "gpt-4o"
    assert manifest["candidate_model"]["model_id"] == "gpt-5.2"
    assert "Baseline and candidate used different model ids" in report


def test_model_drift_cli_reports_high_risk_model_change(tmp_path: Path) -> None:
    previous = tmp_path / "previous"
    current = tmp_path / "current"
    previous.mkdir()
    current.mkdir()
    (previous / "manifest.json").write_text(
        json.dumps(
            {
                "candidate_model": {
                    "provider": "openai",
                    "model_id": "gpt-4o",
                    "verified": True,
                    "warnings": [],
                }
            }
        ),
        encoding="utf-8",
    )
    (current / "manifest.json").write_text(
        json.dumps(
            {
                "candidate_model": {
                    "provider": "openai",
                    "model_id": "gpt-5.2",
                    "verified": True,
                    "warnings": [],
                }
            }
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "model-drift",
                "--run",
                str(current),
                "--history",
                str(previous),
                "--out",
                str(current / "model_drift.json"),
            ]
        )
        == 0
    )

    payload = json.loads((current / "model_drift.json").read_text(encoding="utf-8"))
    assert payload["previous_model"] == "gpt-4o"
    assert payload["current_model"] == "gpt-5.2"
    assert payload["risk"] == "high"
    assert "confounded by model change" in payload["reason"]


def test_model_drift_cli_reads_windows_bom_manifest(tmp_path: Path) -> None:
    previous = tmp_path / "previous"
    current = tmp_path / "current"
    previous.mkdir()
    current.mkdir()
    (previous / "manifest.json").write_text(
        '{"candidate_model":{"provider":"openai","model_id":"gpt-4o"}}',
        encoding="utf-8-sig",
    )
    (current / "manifest.json").write_text(
        '{"candidate_model":{"provider":"openai","model_id":"gpt-5.2"}}',
        encoding="utf-8-sig",
    )

    assert (
        main(
            [
                "model-drift",
                "--run",
                str(current),
                "--history",
                str(previous),
                "--out",
                str(current / "model_drift.json"),
            ]
        )
        == 0
    )

    payload = json.loads((current / "model_drift.json").read_text(encoding="utf-8"))
    assert payload["risk"] == "high"


def test_model_drift_cli_reports_alias_risk(tmp_path: Path) -> None:
    previous = tmp_path / "previous"
    current = tmp_path / "current"
    previous.mkdir()
    current.mkdir()
    for run in [previous, current]:
        (run / "manifest.json").write_text(
            json.dumps({"candidate_model": {"provider": "openai", "model_id": "gpt-4o"}}),
            encoding="utf-8",
        )

    assert (
        main(
            [
                "model-drift",
                "--run",
                str(current),
                "--history",
                str(previous),
                "--out",
                str(current / "model_drift.json"),
            ]
        )
        == 0
    )

    payload = json.loads((current / "model_drift.json").read_text(encoding="utf-8"))
    assert payload["risk"] == "medium"
    assert "alias" in payload["reason"]
