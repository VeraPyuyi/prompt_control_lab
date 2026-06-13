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
    assert (out_dir / "report.html").exists()
    assert (out_dir / "bridge_summary.md").exists()
    bridge = read_json(out_dir / "bridge_summary.json")
    assert tool in bridge["detected_tools"]
    assert bridge["validity"] == "needs_review"


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


def test_init_project_writes_external_bridge_examples(tmp_path: Path) -> None:
    demo = tmp_path / "demo"
    assert main(["init", "--path", str(demo)]) == 0

    external_dir = demo / "examples" / "external"
    assert (external_dir / "promptfoo_results.json").exists()
    assert (external_dir / "langfuse_export.json").exists()
    assert (external_dir / "langsmith_runs.csv").exists()

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
