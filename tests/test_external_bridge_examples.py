from __future__ import annotations

import json
from pathlib import Path

import pytest

from promptcontrollab.cli import main
from promptcontrollab.files import read_json


@pytest.mark.parametrize(
    ("tool", "source_name", "extra_args"),
    [
        (
            "promptfoo",
            "promptfoo_results.json",
            [
                "--baseline-prompt-id",
                "baseline",
                "--candidate-prompt-id",
                "candidate",
                "--provider",
                "openai:gpt-4o-mini-20260601",
            ],
        ),
        (
            "langfuse",
            "langfuse_export.json",
            [
                "--baseline-name",
                "baseline",
                "--candidate-name",
                "candidate",
                "--score-name",
                "exact_match",
                "--model",
                "gpt-4o-mini-20260601",
                "--provider",
                "openai",
            ],
        ),
        (
            "langsmith",
            "langsmith_runs.csv",
            [
                "--baseline-experiment",
                "baseline",
                "--candidate-experiment",
                "candidate",
                "--score-name",
                "exact_match",
                "--model",
                "gpt-4o-mini-20260601",
                "--provider",
                "openai",
            ],
        ),
    ],
)
def test_packaged_external_examples_run_evidence_from(
    tmp_path: Path,
    tool: str,
    source_name: str,
    extra_args: list[str],
) -> None:
    source = Path("examples") / "external" / source_name
    out_dir = tmp_path / "runs" / f"from-{tool}"

    assert (
        main(
            [
                "evidence-from",
                "--tool",
                tool,
                "--baseline-input",
                str(source),
                "--candidate-input",
                str(source),
                "--split-hash",
                "external-demo-split",
                "--bootstrap-samples",
                "20",
                "--permutation-samples",
                "100",
                "--out",
                str(out_dir),
                *extra_args,
            ]
        )
        == 0
    )

    stats = read_json(out_dir / "comparison" / "stats.json")
    assert stats["comparisons"][0]["n"] == 4
    assert stats["comparisons"][0]["mean_delta"] == 0.75
    assert (out_dir / "evidence_card.md").exists()
    assert (out_dir / "evidence_card.html").exists()
    assert (out_dir / "claim_check.html").exists()
    assert (out_dir / "report.html").exists()
    assert (out_dir / "bridge_summary.md").exists()
    assert (out_dir / "bridge_summary.html").exists()
    bridge = read_json(out_dir / "bridge_summary.json")
    assert tool in bridge["detected_tools"]
    assert bridge["validity"] == "needs_review"
    assert bridge["evidence_tier"] == "tier_2_paired_comparison"
    integrity = bridge["research_bundle_integrity"]
    assert integrity["status"] == "hashed"
    assert integrity["hashed_artifact_count"] > 0
    assert integrity["present_artifact_count"] > 0
    assert integrity["verification_status"] == "not_checked"
    bridge_markdown = (out_dir / "bridge_summary.md").read_text(encoding="utf-8")
    assert "Bundle integrity" in bridge_markdown
    assert "Bundle verification" in bridge_markdown


def test_packaged_promptfoo_example_runs_evidence_audit(tmp_path: Path) -> None:
    source = Path("examples") / "external" / "promptfoo_results.json"
    out_dir = tmp_path / "runs" / "from-promptfoo-audit"

    assert (
        main(
            [
                "evidence-audit",
                "--tool",
                "promptfoo",
                "--baseline-input",
                str(source),
                "--candidate-input",
                str(source),
                "--baseline-prompt-id",
                "baseline",
                "--candidate-prompt-id",
                "candidate",
                "--provider",
                "openai:gpt-4o-mini-20260601",
                "--split-hash",
                "external-demo-split",
                "--bootstrap-samples",
                "20",
                "--permutation-samples",
                "100",
                "--out",
                str(out_dir),
            ]
        )
        == 0
    )

    result = read_json(out_dir / "evidence_audit_result.json")
    assert result["kind"] == "external_evidence_audit"
    assert result["gap_status"]["status"] == "needs_work"
    assert result["bundle_verification"]["status"] == "pass"
    assert result["markdown_path"].endswith("evidence_audit_result.md")
    assert result["html_path"].endswith("evidence_audit_result.html")
    assert (out_dir / "evidence_audit_result.md").exists()
    assert (out_dir / "evidence_audit_result.html").exists()
    audit_markdown = (out_dir / "evidence_audit_result.md").read_text(encoding="utf-8")
    assert "External Evidence Audit Summary" in audit_markdown
    audit_html = (out_dir / "evidence_audit_result.html").read_text(encoding="utf-8")
    assert "External Evidence Audit Summary" in audit_html
    assert "Bridge summary" in audit_html
    bundle = read_json(out_dir / "research_bundle.json")
    artifact_rows = {item["path"]: item for item in bundle["artifacts"]}
    assert artifact_rows["evidence_audit_result.html"]["hash_status"] == (
        "audit_summary_not_hashed"
    )
    assert (out_dir / "research_gap_status.html").exists()
    assert (out_dir / "research_bundle_verification.html").exists()
    assert (out_dir / "bridge_summary.html").exists()
    bridge = read_json(out_dir / "bridge_summary.json")
    assert bridge["research_bundle_integrity"]["verification_status"] == "pass"
    bridge_markdown = (out_dir / "bridge_summary.md").read_text(encoding="utf-8")
    assert "Bundle verification: `pass`" in bridge_markdown
    bridge_html = (out_dir / "bridge_summary.html").read_text(encoding="utf-8")
    assert "External Evidence Bridge Summary" in bridge_html
    assert "Research bundle" in bridge_html


def test_evidence_from_langfuse_pairs_by_example_id(tmp_path: Path) -> None:
    source = tmp_path / "langfuse-export.json"
    source.write_text(json.dumps(_langfuse_paired_payload()), encoding="utf-8")
    out_dir = tmp_path / "runs" / "from-langfuse"

    assert (
        main(
            [
                "evidence-from",
                "--tool",
                "langfuse",
                "--baseline-input",
                str(source),
                "--candidate-input",
                str(source),
                "--baseline-name",
                "baseline",
                "--candidate-name",
                "candidate",
                "--score-name",
                "exact_match",
                "--model",
                "gpt-4o-mini-20260601",
                "--provider",
                "openai",
                "--split-hash",
                "external-demo-split",
                "--bootstrap-samples",
                "20",
                "--permutation-samples",
                "100",
                "--out",
                str(out_dir),
            ]
        )
        == 0
    )

    stats = read_json(out_dir / "comparison" / "stats.json")
    assert stats["comparisons"][0]["n"] == 4
    assert stats["comparisons"][0]["mean_delta"] == 0.75
    validity = read_json(out_dir / "comparison" / "comparison_validity.json")
    assert validity["validity"] == "needs_review"
    assert "Adjusted or permutation p-value is above 0.05." in validity["review_items"]


def test_evidence_from_langsmith_csv_pairs_by_example_id(tmp_path: Path) -> None:
    source = tmp_path / "langsmith-runs.csv"
    source.write_text(
        "\n".join(
            [
                "run_id,example_id,experiment_name,output,reference_output,exact_match,model,provider,slice",
                "base-run-1,case-1,baseline,wrong,4,0,gpt-4o-mini-20260601,openai,arithmetic",
                "base-run-2,case-2,baseline,NO,YES,0,gpt-4o-mini-20260601,openai,format",
                "base-run-3,case-3,baseline,blue,blue,1,gpt-4o-mini-20260601,openai,classification",
                "base-run-4,case-4,baseline,maybe,safe,0,gpt-4o-mini-20260601,openai,safety",
                "cand-run-1,case-1,candidate,4,4,1,gpt-4o-mini-20260601,openai,arithmetic",
                "cand-run-2,case-2,candidate,YES,YES,1,gpt-4o-mini-20260601,openai,format",
                "cand-run-3,case-3,candidate,blue,blue,1,gpt-4o-mini-20260601,openai,classification",
                "cand-run-4,case-4,candidate,safe,safe,1,gpt-4o-mini-20260601,openai,safety",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "runs" / "from-langsmith"

    assert (
        main(
            [
                "evidence-from",
                "--tool",
                "langsmith",
                "--baseline-input",
                str(source),
                "--candidate-input",
                str(source),
                "--baseline-experiment",
                "baseline",
                "--candidate-experiment",
                "candidate",
                "--score-name",
                "exact_match",
                "--model",
                "gpt-4o-mini-20260601",
                "--provider",
                "openai",
                "--split-hash",
                "external-demo-split",
                "--bootstrap-samples",
                "20",
                "--permutation-samples",
                "100",
                "--out",
                str(out_dir),
            ]
        )
        == 0
    )

    stats = read_json(out_dir / "comparison" / "stats.json")
    assert stats["comparisons"][0]["n"] == 4
    assert stats["comparisons"][0]["mean_delta"] == 0.75
    validity = read_json(out_dir / "comparison" / "comparison_validity.json")
    assert validity["validity"] == "needs_review"
    assert "Adjusted or permutation p-value is above 0.05." in validity["review_items"]


def test_evidence_from_deepeval_pairs_by_example_id(tmp_path: Path) -> None:
    baseline = tmp_path / "deepeval-baseline.json"
    candidate = tmp_path / "deepeval-candidate.json"
    baseline.write_text(
        (Path("examples") / "external" / "deepeval_baseline.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    candidate.write_text(
        (Path("examples") / "external" / "deepeval_candidate.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    out_dir = tmp_path / "runs" / "from-deepeval"

    assert (
        main(
            [
                "evidence-from",
                "--tool",
                "deepeval",
                "--baseline-input",
                str(baseline),
                "--candidate-input",
                str(candidate),
                "--score-name",
                "exact_match",
                "--model",
                "gpt-4o-mini-20260601",
                "--provider",
                "openai",
                "--split-hash",
                "external-demo-split",
                "--bootstrap-samples",
                "20",
                "--permutation-samples",
                "100",
                "--out",
                str(out_dir),
            ]
        )
        == 0
    )

    stats = read_json(out_dir / "comparison" / "stats.json")
    assert stats["comparisons"][0]["n"] == 4
    assert stats["comparisons"][0]["mean_delta"] == 0.75
    bridge = read_json(out_dir / "bridge_summary.json")
    assert bridge["detected_tools"] == ["deepeval"]
    assert bridge["source_tool_roles"][0]["display_name"] == "DeepEval"
    assert "paper_evidence_gap_diagnosis" in bridge["pcl_added_evidence"]


def test_init_project_writes_external_bridge_examples(tmp_path: Path) -> None:
    demo = tmp_path / "demo"
    assert main(["init", "--path", str(demo)]) == 0

    external_dir = demo / "examples" / "external"
    assert (external_dir / "promptfoo_results.json").exists()
    assert (external_dir / "langfuse_export.json").exists()
    assert (external_dir / "langsmith_runs.csv").exists()
    assert (external_dir / "deepeval_baseline.json").exists()
    assert (external_dir / "deepeval_candidate.json").exists()

    out_dir = demo / "runs" / "from-promptfoo-evidence"
    assert (
        main(
            [
                "evidence-from",
                "--tool",
                "promptfoo",
                "--baseline-input",
                str(external_dir / "promptfoo_results.json"),
                "--candidate-input",
                str(external_dir / "promptfoo_results.json"),
                "--baseline-prompt-id",
                "baseline",
                "--candidate-prompt-id",
                "candidate",
                "--provider",
                "openai:gpt-4o-mini-20260601",
                "--split-hash",
                "external-demo-split",
                "--bootstrap-samples",
                "20",
                "--permutation-samples",
                "100",
                "--out",
                str(out_dir),
            ]
        )
        == 0
    )
    assert (out_dir / "evidence_card.md").exists()
    assert (out_dir / "evidence_card.html").exists()


def _langfuse_paired_payload() -> dict[str, object]:
    return {
        "observations": [
            _langfuse_observation(
                "obs-base-1", "case-1", "baseline", "wrong", "4", 0, "arithmetic"
            ),
            _langfuse_observation("obs-base-2", "case-2", "baseline", "NO", "YES", 0, "format"),
            _langfuse_observation(
                "obs-base-3", "case-3", "baseline", "blue", "blue", 1, "classification"
            ),
            _langfuse_observation("obs-base-4", "case-4", "baseline", "maybe", "safe", 0, "safety"),
            _langfuse_observation("obs-cand-1", "case-1", "candidate", "4", "4", 1, "arithmetic"),
            _langfuse_observation("obs-cand-2", "case-2", "candidate", "YES", "YES", 1, "format"),
            _langfuse_observation(
                "obs-cand-3", "case-3", "candidate", "blue", "blue", 1, "classification"
            ),
            _langfuse_observation("obs-cand-4", "case-4", "candidate", "safe", "safe", 1, "safety"),
        ]
    }


def _langfuse_observation(
    observation_id: str,
    example_id: str,
    name: str,
    output: str,
    expected: str,
    score: float,
    slice_name: str,
) -> dict[str, object]:
    return {
        "id": observation_id,
        "name": name,
        "type": "GENERATION",
        "input": {"expected": expected, "slice": slice_name, "question": example_id},
        "output": output,
        "model": "gpt-4o-mini-20260601",
        "metadata": {
            "provider": "openai",
            "example_id": example_id,
            "slice": slice_name,
        },
        "scores": [{"name": "exact_match", "value": score}],
    }
