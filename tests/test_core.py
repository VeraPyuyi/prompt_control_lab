from __future__ import annotations

import json
from pathlib import Path

from promptcontrollab.evaluation import run_import_eval
from promptcontrollab.files import read_json, write_json
from promptcontrollab.reporting import generate_report
from promptcontrollab.splitting import load_tasks, make_split, write_split
from promptcontrollab.statistics import compare_prediction_files


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_split_is_reproducible_and_has_no_leakage(tmp_path: Path) -> None:
    data = tmp_path / "tasks.jsonl"
    _write(
        data,
        "\n".join(
            [
                '{"id":"a","input":"a","expected":"a","slice":"s1"}',
                '{"id":"b","input":"b","expected":"b","slice":"s1"}',
                '{"id":"c","input":"c","expected":"c","slice":"s2"}',
                '{"id":"d","input":"d","expected":"d","slice":"s2"}',
            ]
        )
        + "\n",
    )
    tasks = load_tasks(data)
    split_a = make_split(tasks, train_ratio=0.5, val_ratio=0.25, seed=7)
    split_b = make_split(tasks, train_ratio=0.5, val_ratio=0.25, seed=7)
    assert split_a.split_hash == split_b.split_hash
    payload = split_a.to_json()
    leakage = payload["leakage"]
    assert isinstance(leakage, dict)
    assert leakage["has_leakage"] is False
    write_split(tmp_path / "splits.json", split_a)
    assert read_json(tmp_path / "splits.json")["split_hash"] == split_a.split_hash


def test_eval_stats_and_report_roundtrip(tmp_path: Path) -> None:
    data = tmp_path / "tasks.jsonl"
    baseline = tmp_path / "baseline_raw.jsonl"
    candidate = tmp_path / "candidate_raw.jsonl"
    _write(
        data,
        "\n".join(
            [
                '{"id":"a","input":"2+2","expected":"4","slice":"arith"}',
                '{"id":"b","input":"3+3","expected":"6","slice":"arith"}',
            ]
        )
        + "\n",
    )
    _write(baseline, '{"id":"a","output":"4"}\n{"id":"b","output":"5"}\n')
    _write(candidate, '{"id":"a","output":"4"}\n{"id":"b","output":"6"}\n')

    run_import_eval(
        data_path=data,
        predictions_path=baseline,
        out_dir=tmp_path / "runs" / "baseline",
        metric="exact_match",
        method="baseline",
    )
    run_import_eval(
        data_path=data,
        predictions_path=candidate,
        out_dir=tmp_path / "runs" / "candidate",
        metric="exact_match",
        method="candidate",
    )
    stats = compare_prediction_files(
        baseline_path=tmp_path / "runs" / "baseline" / "predictions.jsonl",
        candidate_path=tmp_path / "runs" / "candidate" / "predictions.jsonl",
        out_path=tmp_path / "runs" / "candidate" / "stats.json",
        seed=0,
        bootstrap_samples=50,
        permutation_samples=50,
    )
    comparison = stats["comparisons"][0]
    assert isinstance(comparison, dict)
    assert comparison["mean_delta"] == 0.5

    md_path, html_path = generate_report(tmp_path / "runs" / "candidate", title="Test Report")
    assert "What To Check Next" in md_path.read_text(encoding="utf-8")
    assert "Test Report" in html_path.read_text(encoding="utf-8")


def test_report_renders_comparison_validity(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "candidate"
    write_json(run / "manifest.json", {"method": "candidate", "metric": "exact_match"})
    write_json(
        run / "comparison_validity.json",
        {
            "validity": "invalid",
            "prompt_only_comparison": False,
            "plain_summary": "The comparison is confounded by model change.",
            "blocking_issues": ["Baseline and candidate used different model identities."],
            "review_items": [],
            "next_actions": ["Re-run with the same model."],
        },
    )

    md_path, html_path = generate_report(run, title="Validity Report")
    markdown = md_path.read_text(encoding="utf-8")
    html = html_path.read_text(encoding="utf-8")

    assert "## Comparison Validity" in markdown
    assert "invalid" in markdown
    assert "Baseline and candidate used different model identities." in markdown
    assert "Prompt-only comparison validity" in html


def test_report_renders_prompt_optimization_evidence_card(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "candidate"
    write_json(
        run / "evidence_card.json",
        {
            "kind": "prompt_optimization_evidence_card",
            "recommendation": "supported",
            "summary": "Recorded artifacts support the candidate.",
            "missing_artifacts": [],
            "sections": {
                "statistical_evidence": {"status": "pass"},
                "comparison_validity": {"status": "clean"},
            },
        },
    )

    md_path, html_path = generate_report(run, title="Evidence Report")
    markdown = md_path.read_text(encoding="utf-8")
    html = html_path.read_text(encoding="utf-8")

    assert "## Prompt Optimization Evidence Card" in markdown
    assert "Evidence recommendation: `supported`" in markdown
    assert "Recorded artifacts support the candidate." in markdown
    assert "Prompt optimization evidence" in html


def test_metrics_json_is_plain_json(tmp_path: Path) -> None:
    data = tmp_path / "tasks.jsonl"
    predictions = tmp_path / "predictions.jsonl"
    _write(data, '{"id":"a","input":"x","expected":"x","slice":"s"}\n')
    _write(predictions, '{"id":"a","output":"x"}\n')
    run_import_eval(
        data_path=data,
        predictions_path=predictions,
        out_dir=tmp_path / "run",
        metric="exact_match",
        method="candidate",
    )
    payload = json.loads((tmp_path / "run" / "metrics.json").read_text(encoding="utf-8"))
    assert payload["count"] == 1
    assert payload["mean_score"] == 1.0
