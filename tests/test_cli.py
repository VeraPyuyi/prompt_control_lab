from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from promptcontrollab.cli import main
from promptcontrollab.files import write_jsonl


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_scored_run(
    run_dir: Path,
    *,
    method: str,
    score: float,
    prompt_id: str,
    split_hash: str | None = "split-123",
    write_split_manifest: bool = False,
) -> None:
    write_jsonl(
        run_dir / "predictions.jsonl",
        [
            {
                "id": f"item-{index}",
                "output": "right" if score else "wrong",
                "expected": "right",
                "score": score,
                "slice": "format" if index % 2 == 0 else "math",
                "method": method,
            }
            for index in range(20)
        ],
    )
    _write_json(
        run_dir / "metrics.json",
        {"count": 20, "mean_score": score, "by_slice": {"format": score, "math": score}},
    )
    manifest = {
        "tool": "promptcontrollab",
        "tool_version": "0.1.0",
        "mode": "langsmith_ingest",
        "method": method,
        "metric": "exact_match",
        "prompt": {"prompt_id": prompt_id},
        "model": {
            "provider": "openai",
            "model_id": "gpt-5.2-20260601",
            "source": "test",
            "confidence": "high",
        },
    }
    if split_hash is not None:
        manifest["split_hash"] = split_hash
    _write_json(run_dir / "manifest.json", manifest)
    if write_split_manifest:
        _write_json(
            run_dir / "splits.json",
            {
                "split_hash": split_hash or "split-from-file",
                "counts": {"train": 10, "val": 5, "withheld": 5},
                "leakage": {"has_leakage": False},
            },
        )


def test_cli_example_flow(tmp_path: Path) -> None:
    demo = tmp_path / "demo"
    assert main(["init", "--path", str(demo)]) == 0
    demo_readme = (demo / "README.md").read_text(encoding="utf-8")
    demo_readme_zh = (demo / "README.zh.md").read_text(encoding="utf-8")
    assert "pcl start --choice demo --out demo" in demo_readme
    assert "pcl start --guide" in demo_readme
    assert "pcl analyze --config promptcontrol.example.yaml --out runs/quick" in demo_readme
    assert "pcl ui --runs runs --policy examples/guard.policy.yaml" in demo_readme
    assert "PromptControlLab 示例项目" in demo_readme_zh
    assert "pcl start --choice demo --language zh --out demo" in demo_readme_zh
    assert "pcl start --guide --language zh" in demo_readme_zh
    assert "pcl analyze --config promptcontrol.example.yaml --out runs/quick" in demo_readme_zh
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


def test_cli_init_prints_beginner_next_steps(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    demo = tmp_path / "demo"

    assert main(["init", "--path", str(demo)]) == 0

    output = capsys.readouterr().out
    assert f"Created PromptControlLab example at {demo}" in output
    assert "Next steps:" in output
    assert f"cd {demo}" in output
    assert "pcl start --guide" in output
    assert "pcl analyze --config promptcontrol.example.yaml --out runs/quick" in output
    assert "pcl ui --runs runs --policy examples/guard.policy.yaml" in output
    assert "Open README.md" in output
    assert "README.zh.md" in output


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
        "evidence_card.json",
        "evidence_card.md",
        "evidence_card.html",
        "claim_check.json",
        "claim_check.md",
        "claim_check.html",
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
    assert "Deployment Recommendation" in report
    assert "Prompt Optimization Evidence Card" in report
    assert "Prompt Optimization Claim Check" in report
    assert "Recommendation:" in report
    assert "Quick Mode Explanation" in report
    assert "What this means" in report
    html = (run / "report.html").read_text(encoding="utf-8")
    assert "recommendation-card" in html
    assert "dashboard-card" in html
    assert "Prompt-only comparison validity" in html
    assert "Gate failures/review items" in html
    assert "Full Markdown Audit" in html
    assert "Sample changes" in html
    assert "arith-2" in html

    assert main(["explain", "--run", str(run), "--level", "technical"]) == 0
    technical = json.loads((run / "explanation.json").read_text(encoding="utf-8"))
    assert technical["level"] == "technical"
    assert "artifact_paths" in technical


def test_cli_compare_runs_generates_stats_validity_and_report(tmp_path: Path) -> None:
    baseline = tmp_path / "runs" / "from-langsmith-baseline"
    candidate = tmp_path / "runs" / "from-langsmith-candidate"
    out = tmp_path / "runs" / "comparison"
    write_jsonl(
        baseline / "predictions.jsonl",
        [
            {
                "id": f"item-{index}",
                "output": "wrong",
                "expected": "right",
                "score": 0.0,
                "slice": "format" if index % 2 == 0 else "math",
                "method": "baseline",
            }
            for index in range(20)
        ],
    )
    write_jsonl(
        candidate / "predictions.jsonl",
        [
            {
                "id": f"item-{index}",
                "output": "right",
                "expected": "right",
                "score": 1.0,
                "slice": "format" if index % 2 == 0 else "math",
                "method": "candidate",
            }
            for index in range(20)
        ],
    )
    _write_json(
        baseline / "metrics.json",
        {"count": 20, "mean_score": 0.0, "by_slice": {"format": 0.0, "math": 0.0}},
    )
    _write_json(
        candidate / "metrics.json",
        {"count": 20, "mean_score": 1.0, "by_slice": {"format": 1.0, "math": 1.0}},
    )
    common_model = {
        "provider": "openai",
        "model_id": "gpt-5.2-20260601",
        "source": "test",
        "confidence": "high",
    }
    _write_json(
        baseline / "manifest.json",
        {
            "tool": "promptcontrollab",
            "tool_version": "0.1.0",
            "mode": "langsmith_ingest",
            "method": "baseline",
            "metric": "exact_match",
            "split_hash": "split-123",
            "prompt": {"prompt_id": "baseline-prompt"},
            "model": common_model,
        },
    )
    _write_json(
        candidate / "manifest.json",
        {
            "tool": "promptcontrollab",
            "tool_version": "0.1.0",
            "mode": "langsmith_ingest",
            "method": "candidate",
            "metric": "exact_match",
            "split_hash": "split-123",
            "prompt": {"prompt_id": "candidate-prompt"},
            "model": common_model,
        },
    )

    assert (
        main(
            [
                "compare-runs",
                "--baseline",
                str(baseline),
                "--candidate",
                str(candidate),
                "--out",
                str(out),
                "--title",
                "Imported Comparison",
                "--bootstrap-samples",
                "20",
                "--permutation-samples",
                "100",
            ]
        )
        == 0
    )

    for relative_path in [
        "baseline/predictions.jsonl",
        "candidate/predictions.jsonl",
        "baseline/metrics.json",
        "candidate/metrics.json",
        "metrics.json",
        "manifest.json",
        "stats.json",
        "comparison_validity.json",
        "comparison_validity.md",
        "evidence_card.json",
        "evidence_card.md",
        "evidence_card.html",
        "claim_check.json",
        "claim_check.md",
        "claim_check.html",
        "report.md",
        "report.html",
    ]:
        assert (out / relative_path).exists()
    stats = json.loads((out / "stats.json").read_text(encoding="utf-8"))
    assert stats["comparisons"][0]["mean_delta"] == 1.0
    validity = json.loads((out / "comparison_validity.json").read_text(encoding="utf-8"))
    assert validity["validity"] == "clean"
    evidence = json.loads((out / "evidence_card.json").read_text(encoding="utf-8"))
    assert evidence["kind"] == "prompt_optimization_evidence_card"
    assert evidence["sections"]["comparison_validity"]["status"] == "clean"
    claim_check = json.loads((out / "claim_check.json").read_text(encoding="utf-8"))
    assert claim_check["requested_claim"] == "paired"
    assert claim_check["status"] == "pass"
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == "run_comparison"
    assert manifest["baseline_run"] == str(baseline)
    assert manifest["candidate_run"] == str(candidate)
    compare_result = json.loads((out / "compare_runs_result.json").read_text(encoding="utf-8"))
    assert compare_result["evidence_card_html_path"] == str(out / "evidence_card.html")
    assert compare_result["claim_check_html_path"] == str(out / "claim_check.html")
    report = (out / "report.md").read_text(encoding="utf-8")
    assert "Imported Comparison" in report
    assert "Comparison Validity" in report
    assert "Prompt Optimization Evidence Card" in report
    html = (out / "report.html").read_text(encoding="utf-8")
    assert "recommendation-card" in html
    assert "dashboard-card" in html
    assert "Prompt-only comparison validity" in html
    assert "Full Markdown Audit" in html


def test_cli_ecosystem_demo_runs_all_external_bridge_examples(tmp_path: Path) -> None:
    demo = tmp_path / "demo"
    out = demo / "runs" / "ecosystem-demo"
    assert main(["init", "--path", str(demo)]) == 0

    assert (
        main(
            [
                "ecosystem-demo",
                "--examples",
                str(demo / "examples" / "external"),
                "--out",
                str(out),
                "--bootstrap-samples",
                "10",
                "--permutation-samples",
                "20",
            ]
        )
        == 0
    )

    summary = json.loads((out / "ecosystem_demo.json").read_text(encoding="utf-8"))
    assert summary["kind"] == "ecosystem_demo"
    assert summary["research_diagnostic_type"] == "external_evidence_gap"
    assert summary["ecosystem_scorecard_path"] == str(out / "ecosystem_scorecard.json")
    assert summary["ecosystem_scorecard_md_path"] == str(out / "ecosystem_scorecard.md")
    assert summary["ecosystem_scorecard_html_path"] == str(out / "ecosystem_scorecard.html")
    assert (out / "research_diagnostics.json").exists()
    assert (out / "research_diagnostics.md").exists()
    assert (out / "research_bundle.html").exists()
    assert (out / "ecosystem_scorecard.json").exists()
    assert (out / "ecosystem_scorecard.md").exists()
    assert (out / "ecosystem_scorecard.html").exists()
    scorecard = json.loads((out / "ecosystem_scorecard.json").read_text(encoding="utf-8"))
    assert scorecard["kind"] == "ecosystem_scorecard"
    assert [item["tool"] for item in scorecard["rows"]] == [
        "promptfoo",
        "langfuse",
        "langsmith",
        "deepeval",
        "prompt-optimizer",
    ]
    assert scorecard["rows"][0]["gap_status"] == "not_checked"
    assert scorecard["rows"][0]["research_bundle_integrity"]["status"] == "hashed"
    assert scorecard["rows"][0]["research_bundle_integrity"]["hashed_artifact_count"] > 0
    assert (
        scorecard["rows"][0]["research_bundle_integrity"]["verification_status"]
        == "not_checked"
    )
    matrix = scorecard["pcl_evidence_matrix"]
    assert [item["tool"] for item in matrix] == [
        "promptfoo",
        "langfuse",
        "langsmith",
        "deepeval",
        "prompt-optimizer",
    ]
    assert matrix[0]["evidence_card"] == "present"
    assert matrix[0]["claim_check"] == "needs_review"
    assert matrix[0]["research_bundle"] == "present"
    assert matrix[0]["bundle_verification"] == "not_checked"
    assert matrix[0]["missing_paper_diagnostic_count"] > 0
    promptfoo_links = scorecard["rows"][0]["artifact_links"]
    assert {"label": "Bridge summary", "path": "promptfoo/bridge_summary.html"} in promptfoo_links
    assert {"label": "Research bundle", "path": "promptfoo/research_bundle.html"} in promptfoo_links
    assert {"label": "Evidence card", "path": "promptfoo/evidence_card.html"} in promptfoo_links
    assert {"label": "Claim check", "path": "promptfoo/claim_check.html"} in promptfoo_links
    assert {"label": "HTML report", "path": "promptfoo/report.html"} in promptfoo_links
    prompt_optimizer_row = next(
        item for item in scorecard["rows"] if item["tool"] == "prompt-optimizer"
    )
    assert prompt_optimizer_row["validity"] == "not_scored"
    assert prompt_optimizer_row["evidence_tier"] == "asset_bridge"
    assert prompt_optimizer_row["claim_check_status"] == "not_applicable"
    assert prompt_optimizer_row["recommendation"] == (
        "score_imported_assets_before_claiming_improvement"
    )
    assert {
        "label": "Prompt assets",
        "path": "prompt-optimizer/prompt_assets.html",
    } in prompt_optimizer_row["artifact_links"]
    assert {
        "label": "Prompt-optimizer gap plan",
        "path": "prompt-optimizer/prompt_optimizer_gap_plan.html",
    } in prompt_optimizer_row["artifact_links"]
    prompt_optimizer_matrix = next(
        item for item in matrix if item["tool"] == "prompt-optimizer"
    )
    assert prompt_optimizer_matrix["prompt_only_validity"] == "not_scored"
    assert prompt_optimizer_matrix["paired_stats"] == "unknown"
    assert prompt_optimizer_matrix["evidence_card"] == "missing"
    scorecard_markdown = (out / "ecosystem_scorecard.md").read_text(encoding="utf-8")
    assert "research evidence layer" in scorecard_markdown
    assert "PCL-added evidence matrix" in scorecard_markdown
    assert "Prompt-only validity" in scorecard_markdown
    assert "pcl gap-status" in scorecard_markdown
    assert "Bundle integrity" in scorecard_markdown
    assert "hashed; present" in scorecard_markdown
    assert "verify not_checked" in scorecard_markdown
    assert "promptfoo/bridge_summary.html" in scorecard_markdown
    assert "[Research bundle](promptfoo/research_bundle.html)" in scorecard_markdown
    assert "[Evidence card](promptfoo/evidence_card.html)" in scorecard_markdown
    assert "[Claim check](promptfoo/claim_check.html)" in scorecard_markdown
    scorecard_html = (out / "ecosystem_scorecard.html").read_text(encoding="utf-8")
    assert "Ecosystem Scorecard" in scorecard_html
    assert "PCL-added evidence matrix" in scorecard_html
    assert "Prompt-only validity" in scorecard_html
    assert "DeepEval" in scorecard_html
    assert "prompt-optimizer" in scorecard_html
    assert "prompt-optimizer/prompt_assets.html" in scorecard_html
    assert "prompt-optimizer/prompt_optimizer_gap_plan.html" in scorecard_html
    assert "promptfoo/bridge_summary.html" in scorecard_html
    assert "Bundle integrity" in scorecard_html
    assert "hashed; present" in scorecard_html
    assert "verify not_checked" in scorecard_html
    assert "promptfoo/research_bundle.html" in scorecard_html
    assert "promptfoo/evidence_card.html" in scorecard_html
    assert "promptfoo/claim_check.html" in scorecard_html
    assert "promptfoo/report.html" in scorecard_html
    assert main(["gap-status", "--run", str(out / "promptfoo")]) == 0
    assert main(["research-bundle", "--run", str(out / "promptfoo"), "--verify"]) == 0
    (out / "ecosystem_scorecard.json").unlink()
    (out / "ecosystem_scorecard.md").unlink()
    (out / "ecosystem_scorecard.html").unlink()
    assert main(["ecosystem-scorecard", "--run", str(out)]) == 0
    refreshed = json.loads((out / "ecosystem_scorecard.json").read_text(encoding="utf-8"))
    assert refreshed["kind"] == "ecosystem_scorecard"
    assert refreshed["json_path"] == str(out / "ecosystem_scorecard.json")
    assert refreshed["markdown_path"] == str(out / "ecosystem_scorecard.md")
    assert refreshed["html_path"] == str(out / "ecosystem_scorecard.html")
    promptfoo_row = next(item for item in refreshed["rows"] if item["tool"] == "promptfoo")
    assert promptfoo_row["gap_status"] == "needs_work"
    assert promptfoo_row["research_bundle_integrity"]["verification_status"] == "pass"
    assert promptfoo_row["research_bundle_integrity"]["verification_mismatch_count"] == 0
    assert promptfoo_row["gap_missing_count"] > 0
    assert promptfoo_row["gap_status_path"] == "promptfoo/research_gap_status.html"
    assert "promptfoo/bridge_summary.html" in (out / "ecosystem_scorecard.md").read_text(
        encoding="utf-8"
    )
    assert "needs_work" in (out / "ecosystem_scorecard.md").read_text(encoding="utf-8")
    assert "verify pass" in (out / "ecosystem_scorecard.md").read_text(encoding="utf-8")
    assert "needs_work" in (out / "ecosystem_scorecard.html").read_text(encoding="utf-8")
    assert "verify pass" in (out / "ecosystem_scorecard.html").read_text(encoding="utf-8")
    scorecard_dir = tmp_path / "scorecard-out"
    assert main(["ecosystem-scorecard", "--run", str(out), "--out", str(scorecard_dir)]) == 0
    assert (scorecard_dir / "ecosystem_scorecard.json").exists()
    assert (scorecard_dir / "ecosystem_scorecard.md").exists()
    assert (scorecard_dir / "ecosystem_scorecard.html").exists()
    assert [item["tool"] for item in summary["runs"]] == [
        "promptfoo",
        "langfuse",
        "langsmith",
        "deepeval",
        "prompt-optimizer",
    ]
    for tool in ["promptfoo", "langfuse", "langsmith", "deepeval"]:
        tool_dir = out / tool
        assert (tool_dir / "evidence_from_result.json").exists()
        assert (tool_dir / "bridge_summary.md").exists()
        assert (tool_dir / "bridge_summary.html").exists()
        assert (tool_dir / "claim_check.md").exists()
        assert (tool_dir / "claim_check.html").exists()
        assert (tool_dir / "evidence_card.html").exists()
        assert (tool_dir / "research_bundle.html").exists()
        assert (tool_dir / "report.html").exists()
    prompt_optimizer_dir = out / "prompt-optimizer"
    assert (prompt_optimizer_dir / "prompt_assets.json").exists()
    assert (prompt_optimizer_dir / "prompt_assets.html").exists()
    assert (prompt_optimizer_dir / "prompt_optimizer_gap_plan.json").exists()
    assert (prompt_optimizer_dir / "prompt_optimizer_gap_plan.html").exists()
    assert (prompt_optimizer_dir / "bridge_summary.md").exists()
    assert (prompt_optimizer_dir / "bridge_summary.html").exists()
    assert "prompt optimization evidence auditor" in (out / "README.md").read_text(
        encoding="utf-8"
    )
    assert "research_bundle.html" in (out / "README.md").read_text(encoding="utf-8")


def test_cli_compare_runs_rejects_output_inside_source_run(tmp_path: Path) -> None:
    baseline = tmp_path / "runs" / "baseline"
    candidate = tmp_path / "runs" / "candidate"
    _write_scored_run(baseline, method="baseline", score=0.0, prompt_id="baseline-prompt")
    _write_scored_run(candidate, method="candidate", score=1.0, prompt_id="candidate-prompt")

    assert (
        main(
            [
                "compare-runs",
                "--baseline",
                str(baseline),
                "--candidate",
                str(candidate),
                "--out",
                str(baseline / "comparison"),
            ]
        )
        == 2
    )
    assert not (baseline / "comparison").exists()


def test_cli_compare_runs_rejects_non_empty_output_directory(tmp_path: Path) -> None:
    baseline = tmp_path / "runs" / "baseline"
    candidate = tmp_path / "runs" / "candidate"
    out = tmp_path / "runs" / "comparison"
    _write_scored_run(baseline, method="baseline", score=0.0, prompt_id="baseline-prompt")
    _write_scored_run(candidate, method="candidate", score=1.0, prompt_id="candidate-prompt")
    _write_json(out / "splits.json", {"split_hash": "stale"})

    assert (
        main(
            [
                "compare-runs",
                "--baseline",
                str(baseline),
                "--candidate",
                str(candidate),
                "--out",
                str(out),
            ]
        )
        == 2
    )
    assert not (out / "stats.json").exists()


def test_cli_compare_runs_preserves_source_split_manifests(tmp_path: Path) -> None:
    baseline = tmp_path / "runs" / "baseline"
    candidate = tmp_path / "runs" / "candidate"
    out = tmp_path / "runs" / "comparison"
    _write_scored_run(
        baseline,
        method="baseline",
        score=0.0,
        prompt_id="baseline-prompt",
        split_hash=None,
        write_split_manifest=True,
    )
    _write_scored_run(
        candidate,
        method="candidate",
        score=1.0,
        prompt_id="candidate-prompt",
        split_hash=None,
        write_split_manifest=True,
    )

    assert (
        main(
            [
                "compare-runs",
                "--baseline",
                str(baseline),
                "--candidate",
                str(candidate),
                "--out",
                str(out),
                "--bootstrap-samples",
                "20",
                "--permutation-samples",
                "100",
            ]
        )
        == 0
    )

    assert (out / "baseline" / "splits.json").exists()
    assert (out / "candidate" / "splits.json").exists()
    validity = json.loads((out / "comparison_validity.json").read_text(encoding="utf-8"))
    assert validity["checks"]["split_identity"]["status"] == "pass"
    assert validity["validity"] == "clean"


def test_cli_gate_reviews_uncertain_validity_even_when_thresholds_pass(tmp_path: Path) -> None:
    demo = tmp_path / "demo"
    run = demo / "runs" / "quick"
    policy = demo / "gate.policy.yaml"
    prompt_file = demo / "prompt.txt"
    assert main(["init", "--path", str(demo)]) == 0
    prompt_file.write_text("Answer exactly.\n", encoding="utf-8")
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
                "--prompt-id",
                "demo-prompt-v1",
                "--prompt-file",
                str(prompt_file),
                "--prompt-version",
                "v1",
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
    assert gate["status"] == "needs_review"
    assert gate["plain_summary"].startswith("Deployment recommendation:")
    assert gate["checks"]["candidate_score"]["passed"] is True
    assert gate["checks"]["comparison_validity"]["severity"] == "review"


def test_cli_analyze_accepts_paired_prompt_identity_for_clean_validity(
    tmp_path: Path,
) -> None:
    data = tmp_path / "tasks.jsonl"
    baseline_predictions = tmp_path / "baseline.jsonl"
    candidate_predictions = tmp_path / "candidate.jsonl"
    baseline_prompt = tmp_path / "baseline_prompt.txt"
    candidate_prompt = tmp_path / "candidate_prompt.txt"
    run = tmp_path / "runs" / "quick"
    records = [
        {"id": "arith-1", "input": "1 + 1", "expected": "2", "slice": "arith"},
        {"id": "arith-2", "input": "2 + 2", "expected": "4", "slice": "arith"},
        {"id": "arith-3", "input": "3 + 3", "expected": "6", "slice": "arith"},
        {"id": "arith-4", "input": "4 + 4", "expected": "8", "slice": "arith"},
        {"id": "logic-1", "input": "yes or no?", "expected": "yes", "slice": "logic"},
        {"id": "logic-2", "input": "true?", "expected": "yes", "slice": "logic"},
        {"id": "format-1", "input": "label A", "expected": "A", "slice": "format"},
        {"id": "format-2", "input": "label B", "expected": "B", "slice": "format"},
    ]
    write_jsonl(data, records)
    write_jsonl(
        baseline_predictions,
        [
            {"id": item["id"], "output": "wrong"}
            for item in records
        ],
    )
    write_jsonl(
        candidate_predictions,
        [
            {"id": item["id"], "output": item["expected"]}
            for item in records
        ],
    )
    baseline_prompt.write_text("Answer briefly.\n", encoding="utf-8")
    candidate_prompt.write_text("Answer exactly with the expected label.\n", encoding="utf-8")

    assert (
        main(
            [
                "analyze",
                "--data",
                str(data),
                "--baseline-predictions",
                str(baseline_predictions),
                "--candidate-predictions",
                str(candidate_predictions),
                "--out",
                str(run),
                "--baseline-provider",
                "anthropic",
                "--candidate-provider",
                "anthropic",
                "--baseline-model",
                "claude-sonnet-4-20250514",
                "--candidate-model",
                "claude-sonnet-4-20250514",
                "--baseline-prompt-id",
                "baseline-v1",
                "--baseline-prompt-file",
                str(baseline_prompt),
                "--baseline-prompt-version",
                "v1",
                "--candidate-prompt-id",
                "candidate-v2",
                "--candidate-prompt-file",
                str(candidate_prompt),
                "--candidate-prompt-version",
                "v2",
                "--bootstrap-samples",
                "10",
                "--permutation-samples",
                "1000",
            ]
        )
        == 0
    )

    validity = json.loads((run / "comparison_validity.json").read_text(encoding="utf-8"))
    assert validity["validity"] == "clean"
    assert validity["prompt_only_comparison"] is True
    assert validity["checks"]["prompt_identity"]["status"] == "pass"
    assert validity["checks"]["model_identity"]["status"] == "pass"
    baseline_manifest = json.loads((run / "baseline" / "manifest.json").read_text(encoding="utf-8"))
    candidate_manifest = json.loads(
        (run / "candidate" / "manifest.json").read_text(encoding="utf-8")
    )
    assert baseline_manifest["prompt"]["prompt_id"] == "baseline-v1"
    assert candidate_manifest["prompt"]["prompt_id"] == "candidate-v2"
    top_manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    assert top_manifest["baseline_prompt"]["prompt_id"] == "baseline-v1"
    assert top_manifest["candidate_prompt"]["prompt_id"] == "candidate-v2"


def test_cli_gate_passes_clean_comparison_validity(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _write_json(run / "metrics.json", {"count": 1, "mean_score": 1.0})
    _write_json(
        run / "comparison_validity.json",
        {
            "validity": "clean",
            "prompt_only_comparison": True,
            "blocking_issues": [],
            "review_items": [],
        },
    )
    policy = tmp_path / "gate.policy.yaml"
    policy.write_text("min_candidate_score: 0.9\n", encoding="utf-8")

    assert main(["gate", "--run", str(run), "--policy", str(policy)]) == 0

    gate = json.loads((run / "gate_result.json").read_text(encoding="utf-8"))
    assert gate["status"] == "pass"
    assert gate["checks"]["comparison_validity"]["passed"] is True


def test_cli_gate_blocks_invalid_comparison_validity(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _write_json(run / "metrics.json", {"count": 1, "mean_score": 1.0})
    _write_json(
        run / "comparison_validity.json",
        {
            "validity": "invalid",
            "prompt_only_comparison": False,
            "blocking_issues": ["Baseline and candidate used different model identities."],
            "review_items": [],
        },
    )
    policy = tmp_path / "gate.policy.yaml"
    policy.write_text("min_candidate_score: 0.9\n", encoding="utf-8")

    assert main(["gate", "--run", str(run), "--policy", str(policy)]) == 0

    gate = json.loads((run / "gate_result.json").read_text(encoding="utf-8"))
    assert gate["status"] == "fail"
    assert gate["checks"]["comparison_validity"]["passed"] is False
    assert gate["checks"]["comparison_validity"]["severity"] == "fail"


def test_cli_gate_reviews_uncertain_comparison_validity(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _write_json(run / "metrics.json", {"count": 1, "mean_score": 1.0})
    _write_json(
        run / "comparison_validity.json",
        {
            "validity": "needs_review",
            "prompt_only_comparison": "unknown",
            "blocking_issues": [],
            "review_items": ["Prompt identity is missing."],
        },
    )
    policy = tmp_path / "gate.policy.yaml"
    policy.write_text("min_candidate_score: 0.9\n", encoding="utf-8")

    assert main(["gate", "--run", str(run), "--policy", str(policy)]) == 0

    gate = json.loads((run / "gate_result.json").read_text(encoding="utf-8"))
    assert gate["status"] == "needs_review"
    assert gate["checks"]["comparison_validity"]["passed"] is False
    assert gate["checks"]["comparison_validity"]["severity"] == "review"


def test_cli_gate_blocks_model_mismatch_when_policy_requires_it(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    (run / "manifest.json").write_text(
        json.dumps(
            {
                "baseline_model": {
                    "provider": "openai",
                    "model_id": "gpt-4o",
                    "verified": True,
                    "warnings": [],
                },
                "candidate_model": {
                    "provider": "openai",
                    "model_id": "gpt-5.2",
                    "verified": True,
                    "warnings": [],
                },
            }
        ),
        encoding="utf-8",
    )
    (run / "candidate").mkdir()
    (run / "candidate" / "metrics.json").write_text(
        json.dumps({"count": 1, "mean_score": 1.0, "by_slice": {"default": 1.0}}),
        encoding="utf-8",
    )
    policy = tmp_path / "gate.policy.yaml"
    policy.write_text(
        "\n".join(
            [
                "min_candidate_score: 0.9",
                "allowed_models: gpt-4o,gpt-5.2",
                "allowed_providers: openai",
                "block_if_model_mismatch: true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert main(["gate", "--run", str(run), "--policy", str(policy)]) == 0

    gate = json.loads((run / "gate_result.json").read_text(encoding="utf-8"))
    assert gate["status"] == "fail"
    assert gate["checks"]["model_provenance"]["passed"] is False
    assert "model_mismatch" in gate["checks"]["model_provenance"]["violations"]


def test_cli_gate_blocks_unknown_model_when_allow_list_is_set(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    (run / "manifest.json").write_text(json.dumps({"method": "candidate"}), encoding="utf-8")
    (run / "metrics.json").write_text(
        json.dumps({"count": 1, "mean_score": 1.0, "by_slice": {"default": 1.0}}),
        encoding="utf-8",
    )
    policy = tmp_path / "gate.policy.yaml"
    policy.write_text("allowed_models: gpt-5.2\n", encoding="utf-8")

    assert main(["gate", "--run", str(run), "--policy", str(policy)]) == 0

    gate = json.loads((run / "gate_result.json").read_text(encoding="utf-8"))
    assert gate["status"] == "fail"
    assert "model_unknown" in gate["checks"]["model_provenance"]["violations"]


def test_cli_gate_uses_project_config_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = tmp_path / "run"
    run.mkdir()
    (run / "manifest.json").write_text(
        json.dumps({"method": "candidate", "candidate_model": {"model_id": "gpt-4o"}}),
        encoding="utf-8",
    )
    (run / "metrics.json").write_text(
        json.dumps({"count": 1, "mean_score": 1.0, "by_slice": {"default": 1.0}}),
        encoding="utf-8",
    )
    policy = tmp_path / "gate.policy.yaml"
    policy.write_text("allowed_models: gpt-5.2\n", encoding="utf-8")
    (tmp_path / ".promptcontrol.yaml").write_text(
        f"gate_policy: {policy.name}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert main(["gate", "--run", str(run)]) == 0

    gate = json.loads((run / "gate_result.json").read_text(encoding="utf-8"))
    assert gate["status"] == "fail"
    assert "model_not_allowed" in gate["checks"]["model_provenance"]["violations"]


def test_cli_analyze_reads_example_config(tmp_path: Path) -> None:
    demo = tmp_path / "demo"
    run = demo / "runs" / "from-config"
    assert main(["init", "--path", str(demo)]) == 0
    project_config = (demo / ".promptcontrol.yaml").read_text(encoding="utf-8")
    assert "guard_policy: examples/guard.policy.yaml" in project_config
    assert "gate_policy: examples/gate.policy.yaml" in project_config

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
    validity = json.loads((run / "comparison_validity.json").read_text(encoding="utf-8"))
    assert validity["kind"] == "comparison_validity"
    assert validity["checks"]["model_identity"]["status"] in {"pass", "review"}
    assert "Comparison Validity" in (run / "report.md").read_text(encoding="utf-8")


def test_cli_start_analyze_passes_policy_to_analyze(tmp_path: Path) -> None:
    demo = tmp_path / "demo"
    assert main(["init", "--path", str(demo)]) == 0
    config = demo / "promptcontrol.fast.yaml"
    config.write_text(
        "\n".join(
            [
                "mode: quick",
                "data: examples/tasks.jsonl",
                "metric: exact_match",
                "baseline_predictions: examples/predictions_baseline.jsonl",
                "candidate_predictions: examples/predictions_candidate.jsonl",
                "out: runs/start-analyze",
                "bootstrap_samples: 10",
                "permutation_samples: 10",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    policy = demo / "examples" / "gate.strict.yaml"
    policy.write_text("allowed_models: gpt-5.2\n", encoding="utf-8")

    assert (
        main(
            [
                "start",
                "--choice",
                "analyze",
                "--config",
                str(config),
                "--policy",
                str(policy),
            ]
        )
        == 0
    )

    gate = json.loads((demo / "runs" / "start-analyze" / "gate_result.json").read_text())
    assert gate["status"] == "fail"
    assert "model_not_allowed" in gate["checks"]["model_provenance"]["violations"]


def test_cli_guard_uses_project_config_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    policy = tmp_path / "guard.policy.yaml"
    policy.write_text(
        "\n".join(
            [
                "block_at: high",
                "review_at: medium",
                "rule.danger.severity: high",
                "rule.danger.category: destructive_change",
                "rule.danger.patterns: delete database",
                "rule.danger.message: Do not send destructive prompts without review.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / ".promptcontrol.yaml").write_text(
        f"guard_policy: {policy.name}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert main(["guard", "--prompt", "delete database", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["risk_level"] == "high"
    assert any(item["id"] == "danger" for item in payload["policy_violations"])


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


def test_cli_improve_prompt_string_outputs_plain_optimized_prompt(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["improve", "--prompt", "回答下面的问题"]) == 0
    captured = capsys.readouterr()
    assert "Optimized prompt:" in captured.out
    assert "请准确回答下面的问题" in captured.out
    assert "Why it changed:" in captured.out


def test_cli_improve_prompt_file_and_out_writes_artifacts(tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompt.txt"
    out_dir = tmp_path / "improve"
    prompt_file.write_text("Answer the user question.", encoding="utf-8")

    assert main(["improve", "--prompt-file", str(prompt_file), "--out", str(out_dir)]) == 0

    improved = (out_dir / "improved_prompt.txt").read_text(encoding="utf-8")
    payload = json.loads((out_dir / "prompt_improvement.json").read_text(encoding="utf-8"))
    diff = (out_dir / "prompt_diff.md").read_text(encoding="utf-8")
    assert "Please answer the user question accurately." in improved
    assert payload["plain_summary"].startswith("This rewrite")
    assert payload["language"] == "en"
    assert payload["original_prompt"] == "Answer the user question."
    assert "Added a clear task goal" in diff


def test_cli_improve_records_balanced_token_report(tmp_path: Path) -> None:
    out_dir = tmp_path / "improve"

    assert main(["improve", "--prompt", "Answer the user question.", "--out", str(out_dir)]) == 0

    payload = json.loads((out_dir / "prompt_improvement.json").read_text(encoding="utf-8"))
    token_report = payload["token_report"]
    assert token_report["token_mode"] == "balanced"
    assert token_report["original_estimated_tokens"] > 0
    assert token_report["improved_estimated_tokens"] > 0
    assert token_report["compression_applied"] is True
    assert token_report["estimate_note"] == "Estimated with a dependency-free heuristic."


def test_cli_improve_aggressive_max_tokens_makes_prompt_shorter(tmp_path: Path) -> None:
    balanced_dir = tmp_path / "balanced"
    aggressive_dir = tmp_path / "aggressive"

    assert (
        main(["improve", "--prompt", "Answer the user question.", "--out", str(balanced_dir)])
        == 0
    )
    assert (
        main(
            [
                "improve",
                "--prompt",
                "Answer the user question.",
                "--token-mode",
                "aggressive",
                "--max-tokens",
                "35",
                "--out",
                str(aggressive_dir),
            ]
        )
        == 0
    )

    balanced = json.loads((balanced_dir / "prompt_improvement.json").read_text(encoding="utf-8"))
    aggressive = json.loads(
        (aggressive_dir / "prompt_improvement.json").read_text(encoding="utf-8")
    )
    balanced_tokens = balanced["token_report"]["improved_estimated_tokens"]
    aggressive_report = aggressive["token_report"]
    assert aggressive_report["token_mode"] == "aggressive"
    assert aggressive_report["max_tokens"] == 35
    assert aggressive_report["within_budget"] is True
    assert aggressive_report["improved_estimated_tokens"] <= balanced_tokens
    assert "Reduced prompt length to lower estimated token cost." in aggressive["changes"]


def test_cli_improve_uses_run_context(tmp_path: Path) -> None:
    run = tmp_path / "run"
    (run / "diagnostics").mkdir(parents=True)
    (run / "explanation.json").write_text(
        json.dumps(
            {
                "failure_slices": {
                    "regressed": {"arithmetic": -0.25},
                    "improved": {},
                    "unchanged": {},
                },
                "example_changes": {
                    "fixed_ids": [],
                    "broken_ids": ["arith-2"],
                    "unchanged_ids": [],
                },
                "deployment_risk": {
                    "items": {"trajectory": {"mean_step_drift": 2.0}},
                },
            }
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "improve",
                "--prompt",
                "回答下面的问题",
                "--run",
                str(run),
                "--out",
                str(tmp_path / "improve"),
            ]
        )
        == 0
    )

    improved = (tmp_path / "improve" / "improved_prompt.txt").read_text(encoding="utf-8")
    assert "arithmetic" in improved
    assert "arith-2" in improved


def test_cli_improve_validates_prompt_source(tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("Answer the question.", encoding="utf-8")
    assert main(["improve"]) == 2
    assert main(["improve", "--prompt", "x", "--prompt-file", str(prompt_file)]) == 2


def test_cli_guard_json_suggests_improved_prompt(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["guard", "--prompt", "Fix this bug", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["action"] == "suggest"
    assert payload["risk_level"] in {"low", "medium", "high"}
    assert payload["profile"] == "general"
    assert "improved_prompt" in payload
    assert payload["improved_prompt"] != payload["original_prompt"]
    assert "plain_summary" in payload
    assert "add" in payload["plain_summary"].lower()
    assert payload["token_report"]["token_mode"] == "balanced"
    assert payload["reasons"]


def test_cli_guard_policy_blocks_destructive_coding_prompt(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    policy = tmp_path / "guard.policy.yaml"
    policy.write_text(
        "\n".join(
            [
                "profile: coding",
                "block_at: high",
                "review_at: medium",
                "required_fields: target_files,failing_behavior,test_plan,acceptance_criteria",
                "rule.destructive_action.severity: high",
                "rule.destructive_action.patterns: delete database|drop table|remove auth",
                "rule.destructive_action.message: Dangerous destructive request.",
                "rule.destructive_action.category: destructive_change",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "guard",
                "--prompt",
                "Delete database and remove auth",
                "--profile",
                "coding",
                "--mode",
                "gate",
                "--policy",
                str(policy),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["action"] == "block"
    assert payload["risk_level"] == "high"
    assert payload["required_review"] is True
    assert "destructive_change" in payload["risk_categories"]
    assert any(
        violation["id"] == "destructive_action" for violation in payload["policy_violations"]
    )


def test_cli_guard_nested_policy_blocks_destructive_coding_prompt(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    policy = tmp_path / "guard.policy.yaml"
    policy.write_text(
        "\n".join(
            [
                "profile: coding",
                "block_at: high",
                "review_at: medium",
                "required_fields:",
                "  - target_files",
                "  - test_plan",
                "rules:",
                "  - id: destructive_action",
                "    severity: high",
                "    message: Dangerous destructive request.",
                "    category: destructive_change",
                "    patterns:",
                "      - delete database",
                "      - remove auth",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "guard",
                "--prompt",
                "Delete database and remove auth",
                "--profile",
                "coding",
                "--mode",
                "gate",
                "--policy",
                str(policy),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["action"] == "block"
    assert payload["risk_level"] == "high"
    assert any(
        violation["id"] == "destructive_action" for violation in payload["policy_violations"]
    )


def test_cli_guard_invalid_nested_policy_reports_clear_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    policy = tmp_path / "guard.policy.yaml"
    policy.write_text(
        "\n".join(
            [
                "profile: coding",
                "rules:",
                "  - destructive_action",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "guard",
                "--prompt",
                "Fix this bug",
                "--profile",
                "coding",
                "--policy",
                str(policy),
                "--json",
            ]
        )
        == 2
    )
    assert "Supported guard policy formats" in capsys.readouterr().err


def test_cli_guard_builtin_dangerous_prompt_requires_review(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "guard",
                "--prompt",
                "Drop table users in prod and print env secrets",
                "--profile",
                "coding",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["risk_level"] == "high"
    assert payload["required_review"] is True
    assert "destructive_change" in payload["risk_categories"]
    assert "security" in payload["risk_categories"]


def test_cli_guard_chinese_destructive_prompt_requires_review(
    capsys: pytest.CaptureFixture[str],
) -> None:
    prompt = "\u5220\u9664\u6570\u636e\u5e93\u5e76\u79fb\u9664\u767b\u5f55\u9a8c\u8bc1"
    assert (
        main(
            [
                "guard",
                "--prompt",
                prompt,
                "--profile",
                "coding",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["risk_level"] == "high"
    assert payload["required_review"] is True
    assert "destructive_change" in payload["risk_categories"]
    assert "security" in payload["risk_categories"]


def test_cli_guard_safe_coding_prompt_remains_low_risk(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "guard",
                "--prompt",
                "Update docs/usage.md to clarify install steps and run pytest tests/test_cli.py.",
                "--profile",
                "coding",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["risk_level"] == "low"
    assert payload["required_review"] is False
    assert payload["policy_violations"] == []


def test_cli_guard_docs_deployment_prompt_does_not_trigger_high_production_risk(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "guard",
                "--prompt",
                "Update docs/deployment.md to clarify production deployment notes "
                "and run pytest tests/test_docs.py.",
                "--profile",
                "coding",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["risk_level"] == "low"
    assert "production_path" not in payload["risk_categories"]


def test_cli_guard_ignores_policy_rule_without_patterns(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    policy = tmp_path / "guard.policy.yaml"
    policy.write_text(
        "\n".join(
            [
                "profile: coding",
                "rule.incomplete_rule.severity: high",
                "rule.incomplete_rule.message: This should not match every prompt.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "guard",
                "--prompt",
                "Update docs/usage.md to clarify install steps and run pytest tests/test_cli.py.",
                "--profile",
                "coding",
                "--policy",
                str(policy),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["risk_level"] == "low"
    assert not any(
        violation["id"] == "incomplete_rule" for violation in payload["policy_violations"]
    )


def test_cli_guard_default_output_is_human_readable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["guard", "--prompt", "Fix this bug", "--profile", "coding"]) == 0
    output = capsys.readouterr().out
    assert "PromptControlLab Guard" in output
    assert "Decision:" in output
    assert "Risk:" in output
    assert "Why:" in output
    assert "Suggested prompt:" in output
    assert "Next steps:" in output
    assert "Add target files" in output


def test_cli_guard_chinese_prompt_uses_chinese_profile_hint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "guard",
                "--prompt",
                "修复这个 bug",
                "--profile",
                "coding",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert "目标文件" in payload["plain_summary"]
    assert "Focus on precise code changes" not in payload["improved_prompt"]
    assert "影响文件" in payload["improved_prompt"]


def test_cli_start_choice_improve_outputs_beginner_prompt(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["start", "--choice", "improve", "--prompt", "Answer the question"]) == 0
    output = capsys.readouterr().out
    assert "Beginner mode: improve a prompt" in output
    assert "Optimized prompt:" in output


def test_cli_start_choice_demo_creates_runnable_project(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    demo = tmp_path / "demo"

    assert main(["start", "--choice", "demo", "--out", str(demo)]) == 0

    output = capsys.readouterr().out
    assert "Beginner mode: create a runnable demo project and quick report" in output
    assert "Generated quick report:" in output
    assert "Generated gate result:" in output
    assert "Generated history index:" in output
    assert "Demo result summary:" in output
    assert "- Gate:" in output
    assert "- Candidate score:" in output
    assert "- Mean delta:" in output
    assert "Open runs/quick/report.html in your browser" in output
    assert (demo / "README.md").exists()
    assert (demo / "promptcontrol.example.yaml").exists()
    assert (demo / "examples" / "guard.policy.yaml").exists()
    assert (demo / "runs" / "quick" / "report.html").exists()
    assert (demo / "runs" / "quick" / "gate_result.json").exists()
    assert (demo / "runs" / "history_index.json").exists()


def test_cli_start_guide_prints_goal_based_paths(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["start", "--guide"]) == 0
    output = capsys.readouterr().out

    assert "PromptControlLab beginner guide" in output
    assert "See the product first" in output
    assert "pcl start --choice demo --out demo" in output
    assert "open `runs/quick/report.html`" in output
    assert "paper-derived prompt optimization diagnostics" in output
    assert "Compare adjacent tools and PCL-added evidence" in output
    assert "pcl start --choice ecosystem --out runs/ecosystem-demo" in output
    assert "Import external eval results as evidence" in output
    assert "pcl start --choice import --tool auto --input results.json" in output
    assert "Guard a coding-agent prompt" in output
    assert "Audit what an agent changed" in output
    assert "Ecosystem choice map" in output
    assert "Promptfoo -> eval / CI / red-team" in output
    assert "DeepEval -> Pytest-style LLM tests" in output
    assert "prompt-optimizer -> prompt writing" in output
    assert "pcl start" in output


def test_cli_start_guide_supports_chinese(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["start", "--guide", "--language", "zh"]) == 0
    output = capsys.readouterr().out

    assert "PromptControlLab 新手路径指南" in output
    assert "先看产品长什么样" in output
    assert "pcl start --choice demo --language zh --out demo" in output
    assert "打开 `runs/quick/report.html`" in output
    assert "运行论文里的 prompt optimization 诊断" in output
    assert "把外部评测结果导入成证据" in output
    assert "pcl start --choice import --tool auto --input results.json" in output
    assert "在 coding agent 执行前守护 prompt" in output
    assert "审计 agent 到底改了什么" in output
    assert "生态选择地图" in output
    assert "Promptfoo -> eval / CI / red-team" in output
    assert "DeepEval -> Pytest-style LLM tests" in output
    assert "prompt-optimizer -> prompt 写作" in output
    assert "pcl start --language zh" in output


def test_cli_start_interactive_guard_menu(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("5\nFix this bug\n"))
    assert main(["start"]) == 0
    output = capsys.readouterr().out
    assert "What do you want to do?" in output
    assert "1) Create a runnable demo project" in output
    assert "2) Run a paper-style prompt optimization research demo" in output
    assert "3) Import external eval results as evidence" in output
    assert "7) Generate an ecosystem comparison demo" in output
    assert "pcl start --guide" in output
    assert "Beginner mode: guard a prompt" in output
    assert "Plain summary:" in output


def test_cli_start_interactive_import_menu_prints_bridge_commands(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("3\n"))
    assert main(["start"]) == 0
    output = capsys.readouterr().out
    assert "Beginner mode: import external eval results as evidence" in output
    assert "pcl start --choice import --tool auto --input results.json" in output
    assert "prompt-optimizer favorites" in output
    assert "pcl evidence-audit" in output


def test_cli_start_choice_ecosystem_writes_comparison_demo(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = tmp_path / "runs" / "ecosystem-demo"

    assert main(["start", "--choice", "ecosystem", "--out", str(out)]) == 0
    output = capsys.readouterr().out

    assert "Beginner mode: compare adjacent ecosystem tools" in output
    assert "Generated ecosystem comparison demo" in output
    assert "Open first:" in output
    assert (out / "ecosystem_demo.json").exists()
    assert (out / "ecosystem_scorecard.html").exists()
    assert (out / "research_bundle.html").exists()


def test_cli_start_choice_ecosystem_supports_chinese_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = tmp_path / "runs" / "ecosystem-demo-zh"

    assert main(["start", "--choice", "ecosystem", "--language", "zh", "--out", str(out)]) == 0
    output = capsys.readouterr().out

    assert "新手模式: 对比相邻生态工具" in output
    assert "已生成生态对比 demo" in output
    assert "Beginner mode: compare adjacent ecosystem tools" not in output
    assert (out / "ecosystem_scorecard.html").exists()


def test_cli_start_choice_ecosystem_works_without_repo_examples(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cwd = tmp_path / "empty-project"
    cwd.mkdir()
    out = tmp_path / "runs" / "ecosystem-demo"
    monkeypatch.chdir(cwd)

    assert main(["start", "--choice", "ecosystem", "--out", str(out)]) == 0
    output = capsys.readouterr().out

    assert "Generated ecosystem comparison demo" in output
    assert not (cwd / "examples" / "external").exists()
    source_examples = tmp_path / "runs" / "ecosystem-demo_source_examples"
    demo = json.loads((out / "ecosystem_demo.json").read_text(encoding="utf-8"))
    assert Path(str(demo["examples_dir"])) == source_examples
    assert source_examples.exists()
    assert all(Path(str(row["source"])).exists() for row in demo["runs"])
    assert (out / "ecosystem_demo.json").exists()
    assert (out / "ecosystem_scorecard.html").exists()
    assert (out / "research_bundle.html").exists()


def test_cli_start_choice_import_promptfoo_writes_run(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "promptfoo-results.json"
    out_dir = tmp_path / "runs" / "from-promptfoo"
    _write_json(
        source,
        {
            "version": 3,
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
                    "provider": {"id": "openai:gpt-4o-mini"},
                    "testIdx": 0,
                    "testCase": {
                        "vars": {"slice": "arithmetic"},
                        "assert": [{"type": "equals", "value": "4"}],
                    },
                    "response": {"output": "4"},
                    "success": True,
                    "score": 1,
                },
                {
                    "promptId": "candidate",
                    "provider": {"id": "openai:gpt-4o-mini"},
                    "testIdx": 1,
                    "testCase": {
                        "vars": {"slice": "arithmetic"},
                        "assert": [{"type": "equals", "value": "6"}],
                    },
                    "response": {"output": "5"},
                    "success": False,
                    "score": 0,
                },
            ],
        },
    )

    assert (
        main(
            [
                "start",
                "--choice",
                "import",
                "--tool",
                "promptfoo",
                "--input",
                str(source),
                "--out",
                str(out_dir),
                "--prompt-id",
                "candidate",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "Beginner mode: import external eval results as evidence" in output
    assert "- Source tool: promptfoo" in output
    assert f"- Output directory: {out_dir}" in output
    assert (out_dir / "predictions.jsonl").exists()
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_tool"] == "promptfoo"


def test_cli_start_interactive_menu_supports_chinese(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("1\n"))
    assert main(["start", "--language", "zh", "--out", str(tmp_path / "research-demo")]) == 0
    output = capsys.readouterr().out
    assert "你想先做什么?" in output
    assert "创建一个可直接运行的 demo 项目" in output
    assert "7) 生成生态对比 demo" in output
    assert "新手模式: 创建可运行 demo 项目并生成 quick report" in output
    assert "已创建 PromptControlLab 示例项目" in output
    assert "已生成 quick report:" in output
    assert "已生成 gate result:" in output
    assert "已生成 history index:" in output
    assert "Demo 结果摘要:" in output
    assert "- Gate:" in output
    assert "- Candidate score:" in output
    assert "- Mean delta:" in output
    assert "下一步:" in output
    assert "打开 runs/quick/report.html 查看报告" in output
    assert "README.zh.md" in output
    assert (tmp_path / "research-demo" / "README.md").exists()
    assert (tmp_path / "research-demo" / "README.zh.md").exists()
    assert (tmp_path / "research-demo" / "runs" / "quick" / "report.html").exists()
    assert (tmp_path / "research-demo" / "runs" / "quick" / "gate_result.json").exists()
    assert (tmp_path / "research-demo" / "runs" / "history_index.json").exists()


def test_cli_start_guard_passes_policy(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    policy = tmp_path / "guard.policy.yaml"
    policy.write_text(
        "\n".join(
            [
                "block_at: high",
                "review_at: medium",
                "rule.danger.severity: high",
                "rule.danger.category: destructive_change",
                "rule.danger.patterns: delete database",
                "rule.danger.message: Do not send destructive prompts without review.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "start",
                "--choice",
                "guard",
                "--prompt",
                "delete database",
                "--policy",
                str(policy),
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "Policy violations:" in output
    assert "danger" in output


def test_cli_guard_gate_blocks_over_budget_prompt(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("Answer the user question."))
    assert (
        main(
            [
                "guard",
                "--stdin",
                "--mode",
                "gate",
                "--max-tokens",
                "8",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["action"] == "block"
    assert payload["within_budget"] is False
    assert "token_budget" in payload["risk_categories"]
    assert any("token budget" in reason for reason in payload["reasons"])


def test_claude_code_hook_emits_additional_context() -> None:
    hook = Path("plugins/claude-code/hooks/prompt_guard.py")
    event = {
        "hook_event_name": "UserPromptSubmit",
        "prompt": "Fix this bug",
    }
    completed = subprocess.run(
        [
            sys.executable,
            str(hook),
            "--mode",
            "suggest",
            "--profile",
            "coding",
        ],
        input=json.dumps(event),
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(completed.stdout)
    assert "additionalContext" in payload
    assert "prompt_control_lab" in payload["additionalContext"]
    assert "Coding profile adds file, test, and verification focus." in payload["additionalContext"]


def test_claude_code_hook_can_block_over_budget_prompt() -> None:
    hook = Path("plugins/claude-code/hooks/prompt_guard.py")
    event = {
        "hook_event_name": "UserPromptSubmit",
        "prompt": "Answer the user question.",
    }
    completed = subprocess.run(
        [
            sys.executable,
            str(hook),
            "--mode",
            "gate",
            "--max-tokens",
            "8",
        ],
        input=json.dumps(event),
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "block"
    assert "token budget" in payload["reason"]


def test_claude_code_hook_passes_policy_to_guard(tmp_path: Path) -> None:
    hook = Path("plugins/claude-code/hooks/prompt_guard.py")
    policy = tmp_path / "guard.policy.yaml"
    policy.write_text(
        "\n".join(
            [
                "profile: coding",
                "block_at: high",
                "rule.destructive_action.severity: high",
                "rule.destructive_action.patterns: delete database|remove auth",
                "rule.destructive_action.message: Dangerous destructive request.",
                "rule.destructive_action.category: destructive_change",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    event = {"hook_event_name": "UserPromptSubmit", "prompt": "Delete database and remove auth"}
    completed = subprocess.run(
        [
            sys.executable,
            str(hook),
            "--mode",
            "gate",
            "--policy",
            str(policy),
        ],
        input=json.dumps(event),
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "block"
    assert "Dangerous destructive request" in payload["reason"]


def test_cursor_mcp_server_lists_and_calls_guard_prompt() -> None:
    server = Path("plugins/cursor/mcp_server.py")
    requests = "\n".join(
        [
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "guard_prompt",
                        "arguments": {
                            "prompt": "Fix this bug",
                            "profile": "coding",
                            "token_mode": "balanced",
                        },
                    },
                }
            ),
        ]
    )
    completed = subprocess.run(
        [sys.executable, str(server)],
        input=requests + "\n",
        text=True,
        capture_output=True,
        check=True,
    )
    responses = [json.loads(line) for line in completed.stdout.splitlines()]
    assert responses[1]["result"]["tools"][0]["name"] == "guard_prompt"
    assert "policy" in responses[1]["result"]["tools"][0]["inputSchema"]["properties"]
    tool_result = responses[2]["result"]["content"][0]["text"]
    assert "plain_summary" in tool_result
    assert "target files" in tool_result


def test_cursor_mcp_server_passes_policy_to_guard_prompt(tmp_path: Path) -> None:
    server = Path("plugins/cursor/mcp_server.py")
    policy = tmp_path / "guard.policy.yaml"
    policy.write_text(
        "\n".join(
            [
                "profile: coding",
                "block_at: high",
                "rule.destructive_action.severity: high",
                "rule.destructive_action.patterns: delete database|remove auth",
                "rule.destructive_action.message: Dangerous destructive request.",
                "rule.destructive_action.category: destructive_change",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    requests = "\n".join(
        [
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "guard_prompt",
                        "arguments": {
                            "prompt": "Delete database and remove auth",
                            "profile": "coding",
                            "mode": "gate",
                            "policy": str(policy),
                        },
                    },
                }
            ),
        ]
    )
    completed = subprocess.run(
        [sys.executable, str(server)],
        input=requests + "\n",
        text=True,
        capture_output=True,
        check=True,
    )
    responses = [json.loads(line) for line in completed.stdout.splitlines()]
    tool_result = responses[1]["result"]["content"][0]["text"]
    assert "Dangerous destructive request" in tool_result
    assert '"action": "block"' in tool_result
