from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from promptcontrollab.cli import main
from promptcontrollab.files import read_json, write_json


def test_start_research_runs_paper_diagnostics_demo(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pytest.importorskip("numpy")
    run_dir = tmp_path / "research-start"

    assert main(["start", "--choice", "research", "--out", str(run_dir), "--seed", "7"]) == 0

    out = capsys.readouterr().out
    assert "Beginner mode: run the paper-style research diagnostics demo" in out
    assert f"Open first: {run_dir / 'research_bundle.html'}" in out
    assert "At a glance: diagnostics=4/4; claim=pass" in out
    assert "Next action: Share the research bundle" in out
    assert "Evidence card:" in out
    assert "Claim check:" in out
    assert f"UI: pcl ui --runs {tmp_path}" in out
    assert (run_dir / "research_diagnostics.html").exists()
    assert (run_dir / "evidence_card.html").exists()
    assert (run_dir / "claim_check.html").exists()
    assert (run_dir / "diagnostics" / "soft_hard.json").exists()
    assert (run_dir / "diagnostics" / "trajectory.json").exists()
    assert (run_dir / "diagnostics" / "riccati.json").exists()
    assert (run_dir / "diagnostics" / "tv_soft.json").exists()


def test_research_demo_generates_paper_diagnostics(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pytest.importorskip("numpy")
    run_dir = tmp_path / "research-demo"

    assert main(["research-demo", "--out", str(run_dir)]) == 0
    out = capsys.readouterr().out
    assert f"Open first: {run_dir / 'research_bundle.html'}" in out
    assert "At a glance: diagnostics=4/4; claim=pass" in out
    assert f"Open first from summary: {run_dir / 'research_bundle.html'}" in out
    assert "Next action: Share the research bundle" in out
    assert f"UI: pcl ui --runs {tmp_path}" in out

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
    assert summary["plain_language_insights"][0]["diagnostic"] == "Soft-to-hard gap"
    assert summary["plain_language_insights"][0]["next_action"]
    assert summary["at_a_glance"]["diagnostics_ready"] == "4/4"
    assert summary["at_a_glance"]["open_first"] == "research_bundle.html"
    assert summary["at_a_glance"]["claim_status"] == "pass"
    concept_names = {item["concept"] for item in _mapping(summary)}
    assert "tri-split withheld protocol" in concept_names
    assert "HuggingFace hidden-state extraction" in concept_names
    assert "Riccati surrogate" in concept_names
    assert "time-varying soft-control lane" in concept_names
    assert "prompt optimization evidence card" in concept_names
    report = (run_dir / "research_diagnostics.md").read_text(encoding="utf-8")
    assert "Research Diagnostics Report" in report
    assert "## At a glance" in report
    assert "| diagnostics ready | 4/4 |" in report
    assert "![Research overview](research_overview.svg)" in report
    assert "## Plain-language interpretation" in report
    assert "| Diagnostic | Checks | Result | Interpretation | Next action |" in report
    assert "Hidden-state input" in report
    assert "soft-to-hard projection gap" in report
    assert "Riccati surrogate" in report
    report_html = (run_dir / "research_diagnostics.html").read_text(encoding="utf-8")
    assert "Research Diagnostics Report" in report_html
    assert "At a Glance" in report_html
    assert "research_bundle.html" in report_html
    assert 'src="research_overview.svg"' in report_html
    assert "Plain-language Interpretation" in report_html
    assert "Next action" in report_html
    assert "Hidden-state Trajectory" in report_html
    overview_svg = (run_dir / "research_overview.svg").read_text(encoding="utf-8")
    assert "Paper-derived prompt-control evidence" in overview_svg
    assert "Soft-to-hard gap" in overview_svg
    assert "Riccati surrogate" in overview_svg
    assert "ready" in overview_svg
    bundle = read_json(run_dir / "research_bundle.json")
    assert bundle["kind"] == "research_bundle_index"
    assert bundle["status"] == "supported"
    assert bundle["present_artifact_count"] > 0
    assert bundle["hashed_artifact_count"] > 0
    diagnostics_artifact = _artifact(bundle, "research_diagnostics.html")
    assert diagnostics_artifact["bytes"] > 0
    assert diagnostics_artifact["sha256"].startswith("sha256:")
    overview_artifact = _artifact(bundle, "research_overview.svg")
    assert overview_artifact["bytes"] > 0
    assert overview_artifact["sha256"].startswith("sha256:")
    assert (run_dir / "research_bundle.html").exists()
    assert "Research Evidence Bundle" in (run_dir / "research_bundle.html").read_text(
        encoding="utf-8"
    )
    assert main(["research-bundle", "--run", str(run_dir)]) == 0
    refreshed_bundle = read_json(run_dir / "research_bundle.json")
    assert refreshed_bundle["hashed_artifact_count"] >= bundle["hashed_artifact_count"]
    assert main(["research-bundle", "--run", str(run_dir), "--verify"]) == 0
    verification = read_json(run_dir / "research_bundle_verification.json")
    assert verification["status"] == "pass"
    assert verification["mismatch_count"] == 0
    evidence = read_json(run_dir / "evidence_card.json")
    assert evidence["kind"] == "prompt_optimization_evidence_card"
    assert evidence["sections"]["hidden_state_diagnostics"]["input_source"] == "synthetic_demo"
    assert (run_dir / "evidence_card.md").exists()
    assert (run_dir / "evidence_card.html").exists()
    claim_check = read_json(run_dir / "claim_check.json")
    assert claim_check["requested_claim"] == "full-research"
    assert claim_check["status"] == "pass"
    assert (run_dir / "claim_check.md").exists()
    assert (run_dir / "claim_check.html").exists()


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


def test_evidence_gate_accepts_research_demo_without_external_source_by_default(
    tmp_path: Path,
) -> None:
    pytest.importorskip("numpy")
    run_dir = tmp_path / "research-demo"
    assert main(["research-demo", "--out", str(run_dir)]) == 0

    assert main(["evidence-gate", "--run", str(run_dir), "--strict"]) == 0
    gate = read_json(run_dir / "evidence_gate_result.json")
    assert gate["status"] == "pass"
    assert gate["required_checks"]["source_inputs"]["status"] == "skipped"
    assert gate["required_checks"]["research_bundle"]["status"] == "pass"

    assert main(["evidence-gate", "--run", str(run_dir), "--require-source"]) == 0
    require_source_gate = read_json(run_dir / "evidence_gate_result.json")
    assert require_source_gate["status"] == "fail"
    assert require_source_gate["required_checks"]["source_inputs"]["status"] == "fail"
    assert main(["evidence-gate", "--run", str(run_dir), "--require-source", "--strict"]) == 2


def test_research_bundle_refresh_writes_hashes(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "research_diagnostics.html").write_text("<h1>diagnostics</h1>", encoding="utf-8")
    (run_dir / "evidence_card.json").write_text('{"recommendation": "review"}', encoding="utf-8")

    assert main(["research-bundle", "--run", str(run_dir)]) == 0

    bundle = read_json(run_dir / "research_bundle.json")
    assert bundle["kind"] == "research_bundle_index"
    assert bundle["artifact_count"] >= bundle["present_artifact_count"]
    assert bundle["hashed_artifact_count"] == 2
    diagnostics_artifact = _artifact(bundle, "research_diagnostics.html")
    assert diagnostics_artifact["bytes"] == len("<h1>diagnostics</h1>")
    assert diagnostics_artifact["sha256"].startswith("sha256:")
    self_artifact = _artifact(bundle, "research_bundle.json")
    assert self_artifact["generated_index_artifact"] is True
    assert self_artifact["hash_status"] in {
        "generated_during_refresh",
        "self_index_not_hashed",
    }
    assert (run_dir / "research_bundle.html").exists()
    assert main(["research-bundle", "--run", str(run_dir), "--verify"]) == 0
    verification = read_json(run_dir / "research_bundle_verification.json")
    assert verification["status"] == "pass"
    assert verification["checked_count"] == 2
    assert (run_dir / "research_bundle_verification.md").exists()
    assert (run_dir / "research_bundle_verification.html").exists()
    assert main(["research-bundle", "--run", str(run_dir), "--verify", "--strict"]) == 0
    assert main(["research-bundle", "--run", str(run_dir), "--strict"]) == 2

    (run_dir / "evidence_card.json").write_text('{"recommendation": "changed"}', encoding="utf-8")
    assert main(["research-bundle", "--run", str(run_dir), "--verify"]) == 0
    changed = read_json(run_dir / "research_bundle_verification.json")
    assert changed["status"] == "fail"
    assert changed["mismatch_count"] == 1
    assert _verification_result(changed, "evidence_card.json")["status"] == "mismatch"
    assert main(["research-bundle", "--run", str(run_dir), "--verify", "--strict"]) == 2


def test_research_bundle_indexes_prompt_optimizer_eval_scaffold(tmp_path: Path) -> None:
    run_dir = tmp_path / "from-prompt-optimizer"
    scaffold_dir = run_dir / "eval_scaffold"
    prompts_dir = scaffold_dir / "prompts"
    prompts_dir.mkdir(parents=True)
    files = {
        "eval_scaffold/README.md": "# scaffold\n",
        "eval_scaffold/prompt_optimizer_eval_scaffold.json": (
            '{"kind":"prompt_optimizer_eval_scaffold"}'
        ),
        "eval_scaffold/promptcontrol.prompt_optimizer.example.yaml": "metric: exact_match\n",
        "eval_scaffold/tasks.template.jsonl": (
            '{"id":"1","input":"x","expected":"y","slice":"demo"}\n'
        ),
        "eval_scaffold/baseline_predictions.template.jsonl": (
            '{"id":"1","output":"x","provider":"demo","model":"demo"}\n'
        ),
        "eval_scaffold/candidate_predictions.template.jsonl": (
            '{"id":"1","output":"y","provider":"demo","model":"demo"}\n'
        ),
        "eval_scaffold/scaffold_check.html": "<h1>check</h1>\n",
        "eval_scaffold/scaffold_check.md": "# check\n",
        "eval_scaffold/scaffold_check.json": '{"status":"pass"}',
        "eval_scaffold/prompts/strict-format.txt": "Answer with JSON only.\n",
    }
    for relative, content in files.items():
        path = run_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    assert main(["research-bundle", "--run", str(run_dir)]) == 0

    bundle = read_json(run_dir / "research_bundle.json")
    for relative in files:
        row = _artifact(bundle, relative)
        assert row["exists"] is True
        assert row["hash_status"] == "hashed"
        assert row["sha256"].startswith("sha256:")

    assert main(["research-bundle", "--run", str(run_dir), "--verify", "--strict"]) == 0
    verification = read_json(run_dir / "research_bundle_verification.json")
    assert verification["status"] == "pass"
    assert verification["checked_count"] >= len(files)


def test_diagnose_reuses_research_demo_inputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pytest.importorskip("numpy")
    run_dir = tmp_path / "research-demo"
    assert main(["research-demo", "--out", str(run_dir)]) == 0
    for path in (run_dir / "diagnostics").glob("*.json"):
        path.unlink()
    (run_dir / "research_diagnostics.json").unlink()
    (run_dir / "research_diagnostics.md").unlink()

    assert main(["diagnose", "--run", str(run_dir)]) == 0
    out = capsys.readouterr().out

    summary = read_json(run_dir / "research_diagnostics.json")
    assert summary["mode"] == "diagnose"
    assert "At a glance: diagnostics=4/4; claim=pass" in out
    assert f"Open first from summary: {run_dir / 'research_bundle.html'}" in out
    assert "Next action: Share the research bundle" in out
    assert summary["diagnostics"]["trajectory"]["turnpike_like_signal"] is True
    assert (run_dir / "diagnostics" / "soft_hard.json").exists()
    assert (run_dir / "diagnostics" / "tv_soft.json").exists()
    assert (run_dir / "evidence_card.json").exists()
    assert (run_dir / "evidence_card.html").exists()
    assert (run_dir / "claim_check.json").exists()
    assert (run_dir / "claim_check.html").exists()
    assert (run_dir / "research_diagnostics.html").exists()
    assert (run_dir / "research_overview.svg").exists()
    assert (run_dir / "research_bundle.html").exists()


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
    assert ecosystem["tool_count"] == 4
    assert [item["tool"] for item in ecosystem["runs"]] == [
        "promptfoo",
        "langfuse",
        "langsmith",
        "deepeval",
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
    assert "Research Evidence Gap Plan" in (out / "research_gap_plan.html").read_text(
        encoding="utf-8"
    )
    assert "Research Diagnostics Report" in (out / "research_diagnostics.html").read_text(
        encoding="utf-8"
    )
    assert "Research Evidence Bundle" in (out / "research_bundle.html").read_text(
        encoding="utf-8"
    )
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
    assert (out / "promptfoo" / "research_gap_plan.html").exists()
    assert (out / "promptfoo" / "research_bundle.html").exists()


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
    assert "Research Evidence Gap Status" in (run / "research_gap_status.html").read_text(
        encoding="utf-8"
    )
    assert read_json(run / "research_gap_status.json")["html_path"] == str(
        run / "research_gap_status.html"
    )
    assert (run / "research_bundle.html").exists()
    assert read_json(run / "research_bundle.json")["gap_status"] == "needs_work"


def test_diagnose_requires_enough_inputs(tmp_path: Path) -> None:
    assert main(["diagnose", "--out", str(tmp_path / "diag")]) == 2


def _mapping(summary: dict[str, Any]) -> list[dict[str, str]]:
    value = summary["paper_mapping"]
    assert isinstance(value, list)
    return value


def _artifact(bundle: dict[str, Any], path: str) -> dict[str, Any]:
    artifacts = bundle.get("artifacts")
    assert isinstance(artifacts, list)
    for artifact in artifacts:
        if isinstance(artifact, dict) and artifact.get("path") == path:
            return artifact
    raise AssertionError(f"missing artifact {path}")


def _verification_result(payload: dict[str, Any], path: str) -> dict[str, Any]:
    results = payload.get("results")
    assert isinstance(results, list)
    for result in results:
        if isinstance(result, dict) and result.get("path") == path:
            return result
    raise AssertionError(f"missing verification result {path}")
