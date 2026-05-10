from __future__ import annotations

import json
from pathlib import Path

from promptcontrollab.cli import main
from promptcontrollab.files import write_jsonl


def test_cli_example_flow(tmp_path: Path) -> None:
    demo = tmp_path / "demo"
    assert main(["init", "--path", str(demo)]) == 0
    assert (
        main(
            [
                "split",
                "--data",
                str(demo / "examples" / "tasks.jsonl"),
                "--out",
                str(demo / "runs" / "candidate"),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "eval",
                "--data",
                str(demo / "examples" / "tasks.jsonl"),
                "--predictions",
                str(demo / "examples" / "predictions_baseline.jsonl"),
                "--out",
                str(demo / "runs" / "baseline"),
                "--method",
                "baseline",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "eval",
                "--data",
                str(demo / "examples" / "tasks.jsonl"),
                "--predictions",
                str(demo / "examples" / "predictions_candidate.jsonl"),
                "--out",
                str(demo / "runs" / "candidate"),
                "--method",
                "candidate",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "stats",
                "--baseline",
                str(demo / "runs" / "baseline" / "predictions.jsonl"),
                "--candidate",
                str(demo / "runs" / "candidate" / "predictions.jsonl"),
                "--out",
                str(demo / "runs" / "candidate" / "stats.json"),
                "--bootstrap-samples",
                "10",
                "--permutation-samples",
                "10",
            ]
        )
        == 0
    )
    assert main(["report", "--run", str(demo / "runs" / "candidate")]) == 0
    assert (demo / "runs" / "candidate" / "report.md").exists()


def test_cli_quick_analyze_explain_and_report(tmp_path: Path) -> None:
    demo = tmp_path / "demo"
    run = demo / "runs" / "quick"
    assert main(["init", "--path", str(demo)]) == 0

    assert (
        main(
            [
                "analyze",
                "--data",
                str(demo / "examples" / "tasks.jsonl"),
                "--baseline-predictions",
                str(demo / "examples" / "predictions_baseline.jsonl"),
                "--candidate-predictions",
                str(demo / "examples" / "predictions_candidate.jsonl"),
                "--metric",
                "exact_match",
                "--out",
                str(run),
                "--bootstrap-samples",
                "10",
                "--permutation-samples",
                "10",
                "--explain-level",
                "plain",
            ]
        )
        == 0
    )

    expected_files = [
        "splits.json",
        "baseline/metrics.json",
        "candidate/metrics.json",
        "stats.json",
        "explanation.json",
        "report.md",
        "report.html",
    ]
    for relative_path in expected_files:
        assert (run / relative_path).exists()

    explanation = json.loads((run / "explanation.json").read_text(encoding="utf-8"))
    assert explanation["level"] == "plain"
    assert explanation["overall_summary"]["verdict"] in {"keep", "review", "hold"}
    assert explanation["data_hygiene"]["has_leakage"] is False
    assert explanation["example_changes"]["fixed_ids"] == ["arith-2"]

    report = (run / "report.md").read_text(encoding="utf-8")
    assert "Quick Mode Explanation" in report
    assert "What this means" in report

    assert main(["explain", "--run", str(run), "--level", "technical"]) == 0
    technical = json.loads((run / "explanation.json").read_text(encoding="utf-8"))
    assert technical["level"] == "technical"
    assert "artifact_paths" in technical


def test_cli_gate_uses_policy_thresholds(tmp_path: Path) -> None:
    demo = tmp_path / "demo"
    run = demo / "runs" / "quick"
    policy = demo / "gate.policy.yaml"
    assert main(["init", "--path", str(demo)]) == 0
    assert (
        main(
            [
                "analyze",
                "--data",
                str(demo / "examples" / "tasks.jsonl"),
                "--baseline-predictions",
                str(demo / "examples" / "predictions_baseline.jsonl"),
                "--candidate-predictions",
                str(demo / "examples" / "predictions_candidate.jsonl"),
                "--out",
                str(run),
                "--bootstrap-samples",
                "10",
                "--permutation-samples",
                "10",
            ]
        )
        == 0
    )
    policy.write_text(
        "\n".join(
            [
                "min_candidate_score: 0.9",
                "max_regression: 0.0",
                "require_adjusted_p_below: 1.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert main(["gate", "--run", str(run), "--policy", str(policy)]) == 0
    gate = json.loads((run / "gate_result.json").read_text(encoding="utf-8"))
    assert gate["status"] == "pass"
    assert gate["checks"]["candidate_score"]["passed"] is True


def test_cli_analyze_reads_example_config(tmp_path: Path) -> None:
    demo = tmp_path / "demo"
    run = demo / "runs" / "from-config"
    assert main(["init", "--path", str(demo)]) == 0

    assert (
        main(
            [
                "analyze",
                "--config",
                str(demo / "promptcontrol.example.yaml"),
                "--out",
                str(run),
                "--bootstrap-samples",
                "10",
                "--permutation-samples",
                "10",
            ]
        )
        == 0
    )

    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == "quick"
    assert manifest["metric"] == "exact_match"


def test_cli_analyze_uses_configured_out_and_explain_level(tmp_path: Path) -> None:
    demo = tmp_path / "demo"
    assert main(["init", "--path", str(demo)]) == 0
    config = demo / "promptcontrol.technical.yaml"
    config.write_text(
        "\n".join(
            [
                "mode: quick",
                "data: examples/tasks.jsonl",
                "metric: exact_match",
                "baseline_predictions: examples/predictions_baseline.jsonl",
                "candidate_predictions: examples/predictions_candidate.jsonl",
                "out: runs/configured",
                "explain_level: technical",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "analyze",
                "--config",
                str(config),
                "--bootstrap-samples",
                "10",
                "--permutation-samples",
                "10",
            ]
        )
        == 0
    )

    explanation = json.loads(
        (demo / "runs" / "configured" / "explanation.json").read_text(encoding="utf-8")
    )
    assert explanation["level"] == "technical"
    assert "artifact_paths" in explanation


def test_cli_diagnostic_command_can_refresh_technical_explanation(tmp_path: Path) -> None:
    run = tmp_path / "run"
    predictions = tmp_path / "methods.jsonl"
    write_jsonl(
        predictions,
        [
            {
                "id": "a",
                "output": "x",
                "expected": "x",
                "score": 0.5,
                "slice": "s",
                "method": "static",
            },
            {
                "id": "b",
                "output": "x",
                "expected": "x",
                "score": 1.0,
                "slice": "s",
                "method": "time_varying",
            },
        ],
    )

    assert (
        main(
            [
                "tv-soft",
                "--predictions",
                str(predictions),
                "--out",
                str(run / "diagnostics"),
                "--explain-level",
                "technical",
            ]
        )
        == 0
    )

    explanation = json.loads((run / "explanation.json").read_text(encoding="utf-8"))
    assert explanation["level"] == "technical"
    assert "deployment_risk" in explanation
