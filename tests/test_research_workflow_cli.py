from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from promptcontrollab.cli import main
from promptcontrollab.files import read_json, write_json


def test_research_demo_generates_paper_diagnostics(tmp_path: Path) -> None:
    pytest.importorskip("numpy")
    run_dir = tmp_path / "research-demo"

    assert main(["research-demo", "--out", str(run_dir)]) == 0

    assert (run_dir / "inputs" / "soft_prompt.npz").exists()
    assert (run_dir / "inputs" / "vocab_embeddings.npz").exists()
    assert (run_dir / "inputs" / "hidden_states.npz").exists()
    assert (run_dir / "inputs" / "hidden_states.npz.metadata.json").exists()
    assert (run_dir / "inputs" / "surrogate_mats.npz").exists()
    assert (run_dir / "inputs" / "method_predictions.jsonl").exists()

    diagnostics = run_dir / "diagnostics"
    for name in ["soft_hard.json", "trajectory.json", "riccati.json", "tv_soft.json"]:
        assert (diagnostics / name).exists()

    summary = read_json(run_dir / "research_diagnostics.json")
    assert summary["kind"] == "research_diagnostics"
    assert summary["mode"] == "demo"
    assert summary["inputs"]["hidden_states"]["source"] == "synthetic_demo"
    assert summary["inputs"]["hidden_states"]["states_shape"] == [6, 2]
    assert set(summary["diagnostics"]) == {"soft_hard", "trajectory", "riccati", "tv_soft"}
    concept_names = {item["concept"] for item in _mapping(summary)}
    assert "tri-split withheld protocol" in concept_names
    assert "HuggingFace hidden-state extraction" in concept_names
    assert "Riccati surrogate" in concept_names
    assert "time-varying soft-control lane" in concept_names
    assert "prompt optimization evidence card" in concept_names
    report = (run_dir / "research_diagnostics.md").read_text(encoding="utf-8")
    assert "Research Diagnostics Report" in report
    assert "Hidden-state input" in report
    assert "soft-to-hard projection gap" in report
    assert "Riccati surrogate" in report
    evidence = read_json(run_dir / "evidence_card.json")
    assert evidence["kind"] == "prompt_optimization_evidence_card"
    assert evidence["sections"]["hidden_state_diagnostics"]["input_source"] == "synthetic_demo"
    assert (run_dir / "evidence_card.md").exists()
    claim_check = read_json(run_dir / "claim_check.json")
    assert claim_check["requested_claim"] == "full-research"
    assert claim_check["status"] == "pass"
    assert (run_dir / "claim_check.md").exists()


def test_research_demo_generates_complete_evidence_chain(tmp_path: Path) -> None:
    pytest.importorskip("numpy")
    run_dir = tmp_path / "research-demo"

    assert main(["research-demo", "--out", str(run_dir)]) == 0

    for relative_path in [
        "inputs/tasks.jsonl",
        "baseline/predictions.jsonl",
        "baseline/metrics.json",
        "baseline/manifest.json",
        "candidate/predictions.jsonl",
        "candidate/metrics.json",
        "candidate/manifest.json",
        "splits.json",
        "stats.json",
        "comparison_validity.json",
        "comparison_validity.md",
        "metrics.json",
        "manifest.json",
    ]:
        assert (run_dir / relative_path).exists()

    evidence = read_json(run_dir / "evidence_card.json")
    assert evidence["sections"]["protocol_hygiene"]["status"] == "pass"
    assert evidence["sections"]["statistical_evidence"]["status"] == "pass"
    assert evidence["sections"]["comparison_validity"]["status"] == "clean"
    assert evidence["recommendation"] == "supported"
    claim_check = read_json(run_dir / "claim_check.json")
    assert claim_check["evidence_tier"] == "tier_4_full_research_diagnostics"
    assert claim_check["status"] == "pass"
    baseline_manifest = read_json(run_dir / "baseline" / "manifest.json")
    candidate_manifest = read_json(run_dir / "candidate" / "manifest.json")
    assert len(baseline_manifest["prompt"]["prompt_hash"]) == len("sha256:") + 64
    assert len(candidate_manifest["prompt"]["prompt_hash"]) == len("sha256:") + 64


def test_diagnose_reuses_research_demo_inputs(tmp_path: Path) -> None:
    pytest.importorskip("numpy")
    run_dir = tmp_path / "research-demo"
    assert main(["research-demo", "--out", str(run_dir)]) == 0
    for path in (run_dir / "diagnostics").glob("*.json"):
        path.unlink()
    (run_dir / "research_diagnostics.json").unlink()
    (run_dir / "research_diagnostics.md").unlink()

    assert main(["diagnose", "--run", str(run_dir)]) == 0

    summary = read_json(run_dir / "research_diagnostics.json")
    assert summary["mode"] == "diagnose"
    assert summary["diagnostics"]["trajectory"]["turnpike_like_signal"] is True
    assert (run_dir / "diagnostics" / "soft_hard.json").exists()
    assert (run_dir / "diagnostics" / "tv_soft.json").exists()
    assert (run_dir / "evidence_card.json").exists()
    assert (run_dir / "claim_check.json").exists()


def test_diagnose_summarizes_ecosystem_demo_evidence_gaps(tmp_path: Path) -> None:
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

    assert main(["diagnose", "--run", str(out)]) == 0

    summary = read_json(out / "research_diagnostics.json")
    ecosystem = summary["diagnostics"]["ecosystem_bridge"]
    assert ecosystem["tool_count"] == 3
    assert [item["tool"] for item in ecosystem["runs"]] == [
        "promptfoo",
        "langfuse",
        "langsmith",
    ]
    assert "hidden-state trajectory" in ecosystem["runs"][0]["missing_paper_diagnostics"]
    remediation = ecosystem["paper_gap_remediation"]
    assert any(item["concept"] == "hidden-state trajectory" for item in remediation)
    assert any("pcl trajectory" in item["command"] for item in remediation)
    report = (out / "research_diagnostics.md").read_text(encoding="utf-8")
    assert "Ecosystem evidence gap diagnosis" in report
    assert "How to close these gaps" in report
    assert "pcl extract-hidden" in report
    gap_plan = read_json(out / "research_gap_plan.json")
    assert gap_plan["kind"] == "research_gap_plan"
    assert any("pcl trajectory" in item["command"] for item in gap_plan["actions"])
    assert "pcl extract-hidden" in (out / "research_gap_plan.md").read_text(encoding="utf-8")
    assert "exit 1" in (out / "research_gap_commands.ps1").read_text(encoding="utf-8")
    assert "Promptfoo" in report
    assert "Risk: `None`" not in report
    assert "Turnpike-like signal: `None`" not in report


def test_diagnose_summarizes_single_external_evidence_bundle(tmp_path: Path) -> None:
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

    assert main(["diagnose", "--run", str(out / "promptfoo")]) == 0

    summary = read_json(out / "promptfoo" / "research_diagnostics.json")
    bridge = summary["diagnostics"]["external_bridge"]
    assert bridge["tool"] == "promptfoo"
    assert bridge["validity"] == "needs_review"
    assert "soft-to-hard projection gap" in bridge["missing_paper_diagnostics"]
    assert bridge["paper_gap_remediation"][0]["command"]
    assert (out / "promptfoo" / "research_gap_plan.md").exists()


def test_gap_status_checks_expected_research_artifacts(tmp_path: Path) -> None:
    run = tmp_path / "run"
    write_json(
        run / "research_gap_plan.json",
        {
            "kind": "research_gap_plan",
            "actions": [
                {
                    "step": 1,
                    "concept": "soft-to-hard projection gap",
                    "artifact": "diagnostics/soft_hard.json",
                    "command": (
                        "pcl soft-hard --soft inputs/soft_prompt.npz "
                        "--vocab inputs/vocab_embeddings.npz --out diagnostics"
                    ),
                },
                {
                    "step": 2,
                    "concept": "hidden-state trajectory",
                    "artifact": "diagnostics/trajectory.json",
                    "command": "pcl trajectory --states inputs/hidden_states.npz --out diagnostics",
                },
            ],
        },
    )
    write_json(run / "diagnostics" / "soft_hard.json", {"risk": "low"})

    assert main(["gap-status", "--run", str(run)]) == 0

    status = read_json(run / "research_gap_status.json")
    assert status["status"] == "needs_work"
    assert status["complete_count"] == 1
    assert status["missing_count"] == 1
    assert status["actions"][0]["status"] == "present"
    assert status["actions"][1]["status"] == "missing"
    assert "hidden-state trajectory" in (run / "research_gap_status.md").read_text(
        encoding="utf-8"
    )


def test_diagnose_requires_enough_inputs(tmp_path: Path) -> None:
    assert main(["diagnose", "--out", str(tmp_path / "diag")]) == 2


def _mapping(summary: dict[str, Any]) -> list[dict[str, str]]:
    value = summary["paper_mapping"]
    assert isinstance(value, list)
    return value
