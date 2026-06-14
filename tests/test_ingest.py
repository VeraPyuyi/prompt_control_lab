import json
from pathlib import Path
from typing import Any

import pytest

from promptcontrollab.cli import main
from promptcontrollab.files import read_json, read_jsonl
from promptcontrollab.ingest import (
    ingest_auto_results,
    ingest_deepeval_results,
    ingest_langfuse_results,
    ingest_langsmith_results,
    ingest_prompt_optimizer_assets,
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


def test_import_alias_matches_ingest_cli(tmp_path: Path) -> None:
    source = tmp_path / "promptfoo-results.json"
    out_dir = tmp_path / "runs" / "import-alias"
    source.write_text(json.dumps(_promptfoo_v3_payload()), encoding="utf-8")

    assert (
        main(
            [
                "import",
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

    predictions = read_jsonl(out_dir / "predictions.jsonl")
    assert len(predictions) == 2
    manifest = read_json(out_dir / "manifest.json")
    assert manifest["mode"] == "promptfoo_ingest"
    assert manifest["source_tool"] == "promptfoo"


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


def test_ingest_auto_detects_promptfoo_json(tmp_path: Path) -> None:
    source = tmp_path / "promptfoo-results.json"
    out_dir = tmp_path / "runs" / "auto-promptfoo"
    source.write_text(json.dumps(_promptfoo_v3_payload()), encoding="utf-8")

    payload = ingest_auto_results(source_path=source, out_dir=out_dir)

    assert payload["source_tool"] == "promptfoo"
    manifest = read_json(out_dir / "manifest.json")
    assert manifest["mode"] == "promptfoo_ingest"
    assert manifest["source_tool"] == "promptfoo"


def test_ingest_prompt_optimizer_favorites_write_prompt_assets(tmp_path: Path) -> None:
    source = tmp_path / "prompt-optimizer-favorites.json"
    out_dir = tmp_path / "runs" / "from-prompt-optimizer"
    source.write_text(json.dumps(_prompt_optimizer_favorites_payload()), encoding="utf-8")

    payload = ingest_prompt_optimizer_assets(source_path=source, out_dir=out_dir)

    assert payload["artifact_type"] == "prompt_assets"
    assert payload["asset_count"] == 2
    assert payload["evaluation_status"] == "not_scored"
    assets = read_json(out_dir / "prompt_assets.json")
    assert assets["source_tool"] == "prompt-optimizer"
    assert assets["asset_count"] == 2
    assert assets["assets"][0]["content_hash"].startswith("sha256:")
    assert assets["assets"][0]["metadata_summary"]["version_count"] == 1
    assert assets["assets"][0]["has_original_content"] is True
    manifest = read_json(out_dir / "manifest.json")
    assert manifest["mode"] == "prompt_optimizer_asset_import"
    assert manifest["evaluation_status"] == "not_scored"
    assert not (out_dir / "predictions.jsonl").exists()
    assert not (out_dir / "metrics.json").exists()
    assert "does not prove" in (out_dir / "prompt_assets.md").read_text(encoding="utf-8")
    assert "Missing evidence" in (
        out_dir / "prompt_optimizer_gap_plan.md"
    ).read_text(encoding="utf-8")


def test_import_prompt_optimizer_cli_filters_asset(tmp_path: Path) -> None:
    source = tmp_path / "prompt-optimizer-favorites.json"
    out_dir = tmp_path / "runs" / "filtered-prompt-optimizer"
    source.write_text(json.dumps(_prompt_optimizer_favorites_payload()), encoding="utf-8")

    assert (
        main(
            [
                "import",
                "prompt-optimizer",
                "--input",
                str(source),
                "--out",
                str(out_dir),
                "--asset-id",
                "strict-format",
            ]
        )
        == 0
    )

    assets = read_json(out_dir / "prompt_assets.json")
    assert assets["asset_count"] == 1
    assert assets["assets"][0]["id"] == "strict-format"
    manifest = read_json(out_dir / "manifest.json")
    assert manifest["asset_filter"] == "strict-format"


def test_ingest_auto_detects_prompt_optimizer_favorites(tmp_path: Path) -> None:
    source = tmp_path / "prompt-optimizer-favorites.json"
    out_dir = tmp_path / "runs" / "auto-prompt-optimizer"
    source.write_text(json.dumps(_prompt_optimizer_favorites_payload()), encoding="utf-8")

    payload = ingest_auto_results(source_path=source, out_dir=out_dir)

    assert payload["source_tool"] == "prompt-optimizer"
    assert payload["artifact_type"] == "prompt_assets"
    manifest = read_json(out_dir / "manifest.json")
    assert manifest["mode"] == "prompt_optimizer_asset_import"


def test_ingest_prompt_optimizer_template_export(tmp_path: Path) -> None:
    source = tmp_path / "template-export.json"
    out_dir = tmp_path / "runs" / "template"
    source.write_text(json.dumps(_prompt_optimizer_template_payload()), encoding="utf-8")

    ingest_prompt_optimizer_assets(source_path=source, out_dir=out_dir)

    assets = read_json(out_dir / "prompt_assets.json")
    assert assets["asset_count"] == 1
    assert assets["assets"][0]["source_type"] == "template"
    assert "[system]" in assets["assets"][0]["content"]
    assert assets["assets"][0]["variables"] == {"topic": "control"}


def test_ingest_deepeval_test_run_writes_pcl_run(tmp_path: Path) -> None:
    source = tmp_path / "deepeval-test-run.json"
    out_dir = tmp_path / "runs" / "from-deepeval"
    source.write_text(json.dumps(_deepeval_payload()), encoding="utf-8")

    payload = ingest_deepeval_results(
        source_path=source,
        out_dir=out_dir,
        score_name="exact_match",
    )

    assert payload["count"] == 2
    assert payload["mean_score"] == 0.5
    predictions = read_jsonl(out_dir / "predictions.jsonl")
    assert [item["id"] for item in predictions] == ["case-1", "case-2"]
    assert [item["score"] for item in predictions] == [1.0, 0.0]
    assert predictions[0]["output"] == "4"
    assert predictions[0]["expected"] == "4"
    assert predictions[1]["error"] == "wrong answer"
    manifest = read_json(out_dir / "manifest.json")
    assert manifest["mode"] == "deepeval_ingest"
    assert manifest["method"] == "candidate"
    assert manifest["source_tool"] == "deepeval"
    assert manifest["metric"] == "deepeval_metric:exact_match"
    assert manifest["model"]["provider"] == "openai"
    assert manifest["model"]["model_id"] == "gpt-4o-mini"


def test_ingest_deepeval_cli_filters_model(tmp_path: Path) -> None:
    source = tmp_path / "deepeval-test-run.json"
    out_dir = tmp_path / "runs" / "filtered"
    payload = _deepeval_payload()
    payload["test_cases"].append(
        {
            "id": "case-3",
            "actual_output": "wrong",
            "expected_output": "safe",
            "metadata": {
                "example_id": "case-3",
                "slice": "safety",
                "model": "claude-sonnet-4-20250514",
                "provider": "anthropic",
            },
            "metrics": [{"name": "exact_match", "score": 0}],
        }
    )
    source.write_text(json.dumps(payload), encoding="utf-8")

    assert (
        main(
            [
                "ingest",
                "deepeval",
                "--input",
                str(source),
                "--out",
                str(out_dir),
                "--score-name",
                "exact_match",
                "--model",
                "gpt-4o-mini",
                "--provider",
                "openai",
            ]
        )
        == 0
    )

    predictions = read_jsonl(out_dir / "predictions.jsonl")
    assert len(predictions) == 2
    manifest = read_json(out_dir / "manifest.json")
    assert manifest["deepeval_filter"] == {
        "score_name": "exact_match",
        "model": "gpt-4o-mini",
        "provider": "openai",
    }


def test_ingest_deepeval_requires_score_name_for_multiple_metrics(tmp_path: Path) -> None:
    source = tmp_path / "deepeval-test-run.json"
    payload = _deepeval_payload()
    payload["test_cases"][0]["metrics"].append({"name": "faithfulness", "score": 1})
    source.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Multiple DeepEval metric names"):
        ingest_deepeval_results(source_path=source, out_dir=tmp_path / "run")


def test_ingest_auto_detects_deepeval_json(tmp_path: Path) -> None:
    source = tmp_path / "deepeval-test-run.json"
    out_dir = tmp_path / "runs" / "auto-deepeval"
    source.write_text(json.dumps(_deepeval_payload()), encoding="utf-8")

    payload = ingest_auto_results(
        source_path=source,
        out_dir=out_dir,
        score_name="exact_match",
    )

    assert payload["source_tool"] == "deepeval"
    manifest = read_json(out_dir / "manifest.json")
    assert manifest["mode"] == "deepeval_ingest"
    assert manifest["source_tool"] == "deepeval"


def test_evidence_from_promptfoo_generates_comparison_bundle(tmp_path: Path) -> None:
    source = tmp_path / "promptfoo-results.json"
    out_dir = tmp_path / "runs" / "external-evidence"
    source.write_text(json.dumps(_paired_promptfoo_payload(count=20)), encoding="utf-8")

    assert (
        main(
            [
                "evidence-from",
                "--tool",
                "promptfoo",
                "--baseline-input",
                str(source),
                "--candidate-input",
                str(source),
                "--out",
                str(out_dir),
                "--baseline-prompt-id",
                "baseline",
                "--candidate-prompt-id",
                "candidate",
                "--provider",
                "openai:gpt-4o-mini-20260601",
                "--split-hash",
                "split-demo-123",
                "--bootstrap-samples",
                "20",
                "--permutation-samples",
                "100",
            ]
        )
        == 0
    )

    for relative_path in [
        "imports/baseline/predictions.jsonl",
        "imports/candidate/predictions.jsonl",
        "comparison/stats.json",
        "comparison/comparison_validity.json",
        "comparison/evidence_card.json",
        "comparison/evidence_card.html",
        "comparison/claim_check.json",
        "comparison/claim_check.html",
        "comparison/report.html",
        "bridge_summary.json",
        "bridge_summary.md",
        "bridge_summary.html",
        "claim_check.json",
        "claim_check.md",
        "claim_check.html",
        "evidence_card.md",
        "evidence_card.html",
        "report.html",
        "evidence_from_result.json",
        "research_bundle.json",
        "research_bundle.html",
        "research_diagnostics.json",
        "research_diagnostics.md",
        "research_diagnostics.html",
        "research_gap_plan.html",
    ]:
        assert (out_dir / relative_path).exists()
    stats = read_json(out_dir / "comparison" / "stats.json")
    assert stats["comparisons"][0]["mean_delta"] == 1.0
    validity = read_json(out_dir / "comparison" / "comparison_validity.json")
    assert validity["validity"] == "clean"
    evidence = read_json(out_dir / "evidence_card.json")
    assert evidence["sections"]["comparison_validity"]["status"] == "clean"
    claim_check = read_json(out_dir / "claim_check.json")
    assert claim_check["requested_claim"] == "paired"
    assert claim_check["status"] == "pass"
    result = read_json(out_dir / "evidence_from_result.json")
    assert result["kind"] == "external_evidence"
    assert result["tool"] == "promptfoo"
    assert len(result["source_inputs"]) == 2
    assert result["source_inputs"][0]["role"] == "baseline"
    assert result["source_inputs"][0]["sha256"].startswith("sha256:")
    assert result["source_inputs"][0]["bytes"] > 0
    assert result["bridge_summary"]["recommendation"] == "supported"
    assert result["bridge_summary"]["evidence_tier"] == "tier_2_paired_comparison"
    assert result["research_diagnostic_type"] == "external_evidence_gap"
    assert result["research_bundle_html_path"] == str(out_dir / "research_bundle.html")
    assert any("research_bundle.html" in action for action in result["next_actions"])
    assert any("research_diagnostics.html" in action for action in result["next_actions"])
    assert result["research_gap_plan_md_path"] == str(out_dir / "research_gap_plan.md")
    assert result["research_gap_plan_html_path"] == str(out_dir / "research_gap_plan.html")
    assert (out_dir / "research_gap_commands.ps1").exists()
    research = read_json(out_dir / "research_diagnostics.json")
    assert research["diagnostics"]["external_bridge"]["tool"] == "promptfoo"
    assert research["artifacts"]["research_gap_plan"] == str(out_dir / "research_gap_plan.json")
    assert "soft-to-hard projection gap" in (
        out_dir / "research_diagnostics.md"
    ).read_text(encoding="utf-8")
    bridge = read_json(out_dir / "bridge_summary.json")
    assert bridge["kind"] == "external_bridge_summary"
    assert bridge["detected_tools"] == ["promptfoo"]
    assert bridge["source_inputs"][0]["sha256"] == result["source_inputs"][0]["sha256"]
    assert "paired_bootstrap_confidence_interval" in bridge["pcl_added_evidence"]
    assert "claim_scope_check" in bridge["pcl_added_evidence"]
    assert "paper_evidence_gap_diagnosis" in bridge["pcl_added_evidence"]
    assert bridge["research_diagnostic_type"] == "external_evidence_gap"
    assert bridge["research_bundle_html_path"] == str(out_dir / "research_bundle.html")
    assert bridge["research_diagnostics_md_path"] == str(out_dir / "research_diagnostics.md")
    assert bridge["research_diagnostics_html_path"] == str(out_dir / "research_diagnostics.html")
    assert bridge["research_gap_plan_md_path"] == str(out_dir / "research_gap_plan.md")
    assert bridge["research_gap_plan_html_path"] == str(out_dir / "research_gap_plan.html")
    assert "soft-to-hard projection gap" in bridge["missing_paper_diagnostics"]
    assert any("pcl soft-hard" in row["command"] for row in bridge["paper_gap_remediation"])
    assert bridge["validity"] == "clean"
    assert bridge["evidence_tier"] == "tier_2_paired_comparison"
    assert bridge["claim_check_status"] == "pass"
    assert bridge["claim_check_requested_claim"] == "paired"
    assert "paired comparison claim only" in bridge["claim_language"]
    assert "hidden_state_diagnostics" in bridge["next_tier_missing"]
    assert bridge["paired_n"] == 20
    bridge_markdown = (out_dir / "bridge_summary.md").read_text(encoding="utf-8")
    assert "Promptfoo" in bridge_markdown
    assert "Source input provenance" in bridge_markdown
    assert "sha256:" in bridge_markdown
    assert "Research diagnostics" in bridge_markdown
    assert "research_bundle.html" in bridge_markdown
    assert "research_diagnostics.html" in bridge_markdown
    assert "research_gap_plan.html" in bridge_markdown
    assert "pcl soft-hard" in bridge_markdown
    bridge_html = (out_dir / "bridge_summary.html").read_text(encoding="utf-8")
    assert "External Evidence Bridge Summary" in bridge_html
    assert "Promptfoo" in bridge_html
    assert "Source Input Provenance" in bridge_html
    assert "research_bundle.html" in bridge_html


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


def test_ingest_auto_detects_langfuse_json(tmp_path: Path) -> None:
    source = tmp_path / "langfuse-export.json"
    out_dir = tmp_path / "runs" / "auto-langfuse"
    source.write_text(json.dumps(_langfuse_payload()), encoding="utf-8")

    assert (
        main(
            [
                "ingest",
                "auto",
                "--input",
                str(source),
                "--out",
                str(out_dir),
                "--name",
                "candidate",
                "--score-name",
                "exact_match",
            ]
        )
        == 0
    )

    manifest = read_json(out_dir / "manifest.json")
    assert manifest["mode"] == "langfuse_ingest"
    assert manifest["source_tool"] == "langfuse"


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


def test_ingest_auto_detects_langsmith_csv(tmp_path: Path) -> None:
    source = tmp_path / "langsmith-runs.csv"
    out_dir = tmp_path / "runs" / "auto-langsmith"
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

    payload = ingest_auto_results(
        source_path=source,
        out_dir=out_dir,
        experiment="candidate",
        score_name="exact_match",
    )

    assert payload["source_tool"] == "langsmith"
    manifest = read_json(out_dir / "manifest.json")
    assert manifest["mode"] == "langsmith_ingest"
    assert manifest["source_tool"] == "langsmith"


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


def _paired_promptfoo_payload(*, count: int) -> dict[str, Any]:
    provider = "openai:gpt-4o-mini-20260601"
    results: list[dict[str, Any]] = []
    for index in range(count):
        expected = str(index + 1)
        test_case = {
            "vars": {"slice": "demo", "question": f"{index}+1"},
            "assert": [{"type": "equals", "value": expected}],
        }
        results.append(
            {
                "promptId": "baseline",
                "provider": {"id": provider, "label": "OpenAI mini pinned"},
                "testIdx": index,
                "testCase": test_case,
                "response": {"output": "wrong"},
                "success": False,
                "score": 0,
            }
        )
        results.append(
            {
                "promptId": "candidate",
                "provider": {"id": provider, "label": "OpenAI mini pinned"},
                "testIdx": index,
                "testCase": test_case,
                "response": {"output": expected},
                "success": True,
                "score": 1,
            }
        )
    return {
        "version": 3,
        "timestamp": "2026-06-13T00:00:00Z",
        "prompts": [
            {"id": "baseline", "raw": "Answer the question.", "label": "Baseline"},
            {
                "id": "candidate",
                "raw": "Answer with only the final result.",
                "label": "Candidate",
            },
        ],
        "results": results,
    }


def _prompt_optimizer_favorites_payload() -> dict[str, Any]:
    return {
        "version": "1.0",
        "favorites": [
            {
                "id": "strict-format",
                "title": "Strict format answer",
                "content": "Answer with exactly one JSON object and no markdown.",
                "description": "A deployment-oriented answer format prompt.",
                "createdAt": "2026-06-14T00:00:00.000Z",
                "updatedAt": "2026-06-14T00:00:00.000Z",
                "tags": ["format", "deployment"],
                "category": "qa",
                "useCount": 3,
                "functionMode": "basic",
                "optimizationMode": "system",
                "metadata": {
                    "originalContent": "Answer the question.",
                    "sourceHistoryId": "hist-1",
                    "modelKey": "openai",
                    "modelName": "gpt-4o-mini",
                    "templateId": "tmpl-format",
                    "promptAsset": {
                        "schemaVersion": "1.0",
                        "currentVersionId": "v1",
                        "versions": [{"id": "v1", "content": "Answer with JSON."}],
                        "examples": [{"input": "2+2", "output": "{\"answer\":\"4\"}"}],
                    },
                },
            },
            {
                "id": "arithmetic-check",
                "title": "Arithmetic checker",
                "content": "Solve the arithmetic problem and verify the final number.",
                "tags": ["math"],
                "functionMode": "context",
                "useCount": 1,
            },
        ],
    }


def _prompt_optimizer_template_payload() -> dict[str, Any]:
    return {
        "template": {
            "id": "tmpl-control",
            "name": "Control explanation",
            "messages": [
                {"role": "system", "content": "Explain {topic} in precise terms."},
                {"role": "user", "content": "Use one short example."},
            ],
        },
        "variables": {"topic": "control"},
        "export_info": {
            "format": "template",
            "exported_at": "2026-06-14T00:00:00Z",
            "variable_count": 1,
        },
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


def _deepeval_payload() -> dict[str, Any]:
    return {
        "tool": "deepeval",
        "run_name": "candidate",
        "hyperparameters": {
            "model": "gpt-4o-mini",
            "provider": "openai",
            "temperature": 0,
        },
        "test_cases": [
            {
                "id": "case-1",
                "input": "2+2",
                "actual_output": "4",
                "expected_output": "4",
                "metadata": {"example_id": "case-1", "slice": "arithmetic"},
                "metrics": [{"name": "exact_match", "score": 1, "reason": "matches"}],
            },
            {
                "id": "case-2",
                "input": "3+3",
                "actual_output": "5",
                "expected_output": "6",
                "metadata": {"example_id": "case-2", "slice": "arithmetic"},
                "metrics": [
                    {"name": "exact_match", "score": 0, "reason": "wrong answer"}
                ],
            },
        ],
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
