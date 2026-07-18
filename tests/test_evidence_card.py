from __future__ import annotations

import json
from pathlib import Path

from promptcontrollab.cli import main
from promptcontrollab.evidence_card import (
    build_evidence_card,
    render_evidence_card_html,
    render_evidence_card_markdown,
)
from promptcontrollab.files import read_json
from promptcontrollab.report_model import ReportModel


def test_evidence_card_summarizes_research_and_validity_artifacts(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "candidate"
    _write_json(
        run / "splits.json",
        {
            "split_hash": "sha256:split",
            "counts": {"train": 6, "val": 2, "withheld": 2},
            "leakage": {"has_leakage": False},
        },
    )
    _write_json(
        run / "stats.json",
        {
            "comparisons": [
                {
                    "mean_delta": 0.18,
                    "bootstrap_ci": [0.05, 0.31],
                    "permutation_p_value": 0.01,
                    "holm_adjusted_p_value": 0.01,
                }
            ]
        },
    )
    _write_json(
        run / "comparison_validity.json",
        {
            "validity": "clean",
            "prompt_only_comparison": True,
            "blocking_issues": [],
            "review_items": [],
        },
    )
    _write_json(
        run / "diagnostics" / "soft_hard.json",
        {"risk": "low", "mean_projection_distance": 0.08, "max_projection_distance": 0.2},
    )
    _write_json(
        run / "research_diagnostics.json",
        {
            "inputs": {
                "hidden_states": {
                    "source": "huggingface_extraction",
                    "model_id": "Qwen/Qwen2.5-0.5B",
                    "states_shape": [32, 896],
                    "pool": "last-token",
                }
            }
        },
    )
    _write_json(
        run / "diagnostics" / "trajectory.json",
        {"turnpike_like_signal": True, "log_decay_slope": -0.42, "decay_r2": 0.93},
    )
    _write_json(
        run / "diagnostics" / "riccati.json",
        {"stable_surrogate": True, "closed_loop_spectral_radius": 0.71},
    )
    _write_json(
        run / "diagnostics" / "tv_soft.json",
        {
            "method_means": {"static": 0.52, "time_varying": 0.71},
            "delta_vs_baseline": {"time_varying": 0.19, "shuffled_tv": 0.02},
        },
    )

    card = build_evidence_card(run)

    assert card["kind"] == "prompt_optimization_evidence_card"
    assert card["recommendation"] == "supported"
    assert card["evidence_tier"] == "tier_4_full_research_diagnostics"
    assert "paper-derived deployment" in card["claim_scope"]
    assert card["next_tier_missing"] == []
    assert card["sections"]["protocol_hygiene"]["status"] == "pass"
    assert card["sections"]["statistical_evidence"]["mean_delta"] == 0.18
    assert card["sections"]["comparison_validity"]["status"] == "clean"
    assert card["sections"]["deployment_diagnostics"]["soft_hard_risk"] == "low"
    assert card["sections"]["hidden_state_diagnostics"]["input_source"] == "huggingface_extraction"
    assert card["sections"]["hidden_state_diagnostics"]["states_shape"] == [32, 896]
    assert card["sections"]["riccati_surrogate"]["stable_surrogate"] is True
    assert card["sections"]["time_varying_control"]["best_delta_method"] == "time_varying"
    assert card["sections"]["paper_replication_evidence"]["status"] == "skipped"
    assert "paper_replication_evidence" not in card["missing_artifacts"]

    markdown = render_evidence_card_markdown(card)
    assert "# Prompt Optimization Evidence Card" in markdown
    assert "Recommendation: `supported`" in markdown
    assert "Evidence tier: `tier_4_full_research_diagnostics`" in markdown
    assert "Hidden-state diagnostics" in markdown
    assert "Riccati surrogate" in markdown
    html = render_evidence_card_html(card)
    assert "Prompt Optimization Evidence Card" in html
    assert "tier_4_full_research_diagnostics" in html
    assert "Hidden-state diagnostics" in html


def test_cli_evidence_card_writes_json_and_markdown(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "candidate"
    _write_json(run / "stats.json", {"comparisons": [{"mean_delta": 0.0}]})
    json_out = tmp_path / "evidence_card.json"
    markdown_out = tmp_path / "evidence_card.md"

    assert (
        main(
            [
                "evidence-card",
                "--run",
                str(run),
                "--out",
                str(markdown_out),
                "--json-out",
                str(json_out),
            ]
        )
        == 0
    )

    payload = read_json(json_out)
    assert payload["kind"] == "prompt_optimization_evidence_card"
    assert payload["recommendation"] == "needs_review"
    assert payload["evidence_tier"] == "tier_1_incomplete_comparison"
    assert "not as evidence" in payload["claim_language"]
    assert payload["html_path"] == str(markdown_out.with_suffix(".html"))
    assert markdown_out.exists()
    html_out = markdown_out.with_suffix(".html")
    assert html_out.exists()
    assert "Statistical evidence" in markdown_out.read_text(encoding="utf-8")
    assert "Prompt Optimization Evidence Card" in html_out.read_text(encoding="utf-8")


def test_evidence_card_surfaces_prompt_optimizer_scaffold_readiness(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "from-prompt-optimizer"
    _write_json(
        run / "prompt_assets.json",
        {
            "schema": "prompt_control_lab.prompt_assets.v1",
            "source_tool": "prompt-optimizer",
            "artifact_type": "prompt_assets",
            "evaluation_status": "not_scored",
            "asset_count": 1,
            "assets": [],
        },
    )
    _write_json(
        run / "eval_scaffold" / "scaffold_check.json",
        {
            "status": "needs_input",
            "task_count": 2,
            "baseline_prediction_count": 2,
            "candidate_prediction_count": 2,
            "prompt_file_count": 1,
            "issues": [{"code": "placeholder_value"}],
        },
    )

    card = build_evidence_card(run)

    scaffold = card["sections"]["prompt_optimizer_scaffold"]
    assert card["recommendation"] == "needs_review"
    assert scaffold["status"] == "review"
    assert scaffold["scaffold_status"] == "needs_input"
    assert scaffold["issue_count"] == 1
    markdown = render_evidence_card_markdown(card)
    html = render_evidence_card_html(card)
    assert "Prompt optimizer eval scaffold" in markdown
    assert "Prompt optimizer eval scaffold" in html
    assert "Scaffold must be completed" in markdown

    _write_json(
        run / "eval_scaffold" / "scaffold_check.json",
        {
            "status": "pass",
            "task_count": 2,
            "baseline_prediction_count": 2,
            "candidate_prediction_count": 2,
            "prompt_file_count": 1,
            "issues": [],
        },
    )
    passed = build_evidence_card(run)
    assert passed["sections"]["prompt_optimizer_scaffold"]["status"] == "pass"
    assert passed["sections"]["prompt_optimizer_scaffold"]["issue_count"] == 0


def test_report_model_loads_and_recognizes_peoc_artifacts(tmp_path: Path) -> None:
    run = tmp_path / "peoc-run"
    _write_peoc_run(run)

    model = ReportModel.from_run(run)

    assert model.manifest["adapter"] == "peoc"
    assert model.source_manifest["schema"] == "prompt_control_lab.peoc_source_manifest.v1"
    assert model.peoc_evidence["schema"] == "prompt_control_lab.peoc_evidence.v1"
    assert model.peoc_case_study["schema"] == "prompt_control_lab.peoc_case_study.v1"
    assert model.artifacts.count("manifest.json") == 1
    assert {
        "manifest.json",
        "source_manifest.json",
        "peoc_evidence.json",
        "research_case_study.json",
        "research_case_study.md",
        "research_case_study.html",
    } <= set(model.artifacts)


def test_evidence_card_fail_closes_real_peoc_replication_evidence(tmp_path: Path) -> None:
    run = tmp_path / "peoc-run"
    _write_peoc_run(run)

    card = build_evidence_card(run)

    paper = card["sections"]["paper_replication_evidence"]
    assert paper["origin"] == "real"
    assert paper["status"] == "not_supported"
    assert paper["available_count"] == 2
    assert paper["partial_count"] == 0
    assert paper["unusable_count"] == 1
    assert paper["failed_validation_count"] == 1
    assert paper["missing_count"] == 2
    assert paper["section_statuses"] == {
        "hard_evaluation": "available",
        "riccati": "missing",
        "soft_evaluation": "unusable",
        "soft_hard": "missing",
        "stage_heterogeneity": "failed_validation",
        "trajectory": "available",
    }
    assert paper["safe_claim"] == (
        "This <bounded> real PEOC case study reports aggregate results only. "
        "Stage heterogeneity failed validation."
    )
    assert "failed validation" in paper["reason"].lower()
    assert card["recommendation"] == "not_supported"
    assert card["evidence_tier"] != "tier_4_full_research_diagnostics"
    assert "full support" not in card["claim_language"].lower()

    hidden = card["sections"]["hidden_state_diagnostics"]
    assert hidden["status"] == "review"
    assert hidden["input_source"] == "peoc_nmi_replication_bundle"
    assert hidden["selected_pair"]["model"] == "Qwen/Qwen2.5-7B-Instruct"
    assert hidden["status"] != "pass"

    time_varying = card["sections"]["time_varying_control"]
    assert time_varying["status"] == "review"
    assert time_varying["evidence_kind"] == "aggregate_summary"
    assert "tv_pmp" in time_varying["methods"]
    assert "best_delta_method" not in time_varying
    assert time_varying["status"] != "pass"

    markdown = render_evidence_card_markdown(card)
    rendered_html = render_evidence_card_html(card)
    assert markdown.index("## Paper replication evidence") < markdown.index(
        "## Hidden-state diagnostics"
    )
    assert "&lt;bounded&gt;" in markdown
    assert "<bounded>" not in markdown
    assert "Paper replication evidence" in rendered_html
    assert "&lt;bounded&gt;" in rendered_html
    assert "<bounded>" not in rendered_html
    source_bundle_path = r"D:\private\PEOC\<unsafe-source>"
    assert source_bundle_path not in json.dumps(card)
    assert source_bundle_path not in markdown
    assert source_bundle_path not in rendered_html


def test_peoc_boundary_caps_otherwise_full_research_card(tmp_path: Path) -> None:
    run = tmp_path / "peoc-with-local-diagnostics"
    _write_full_research_run(run)
    _write_peoc_run(run)

    card = build_evidence_card(run)

    assert card["evidence_tier"] != "tier_4_full_research_diagnostics"
    assert card["recommendation"] in {"needs_review", "not_supported"}
    assert "full support" not in card["claim_language"].lower()


def test_false_peoc_boundary_rejects_affirmative_case_study_claim(tmp_path: Path) -> None:
    run = tmp_path / "unsafe-claim"
    _write_peoc_run(run)
    case_study = read_json(run / "research_case_study.json")
    case_study["safe_claim"] = (
        "This does not support one edge case, but fully supports every research claim."
    )
    _write_json(run / "research_case_study.json", case_study)

    card = build_evidence_card(run)

    paper = card["sections"]["paper_replication_evidence"]
    assert paper["full_research_support"] is False
    assert "fully supports" not in paper["safe_claim"].lower()
    assert "fully supports" not in card["claim_language"].lower()
    assert "bounded" in paper["safe_claim"].lower()


def test_orphan_peoc_case_study_does_not_supply_time_varying_evidence(
    tmp_path: Path,
) -> None:
    run = tmp_path / "orphan-case-study"
    control = tmp_path / "paired-control"
    _write_clean_paired_run(run)
    _write_clean_paired_run(control)
    _write_peoc_run(run)
    (run / "peoc_evidence.json").unlink()

    card = build_evidence_card(run)
    control_card = build_evidence_card(control)

    assert card["sections"]["paper_replication_evidence"]["status"] == "skipped"
    assert card["sections"]["time_varying_control"]["status"] == "missing"
    assert card["evidence_tier"] == control_card["evidence_tier"]
    assert card["recommendation"] == control_card["recommendation"]


def test_true_peoc_boundary_cannot_override_incomplete_sections(tmp_path: Path) -> None:
    run = tmp_path / "inconsistent-full-boundary"
    _write_full_research_run(run)
    _write_peoc_run(run)
    evidence = read_json(run / "peoc_evidence.json")
    sections = evidence["sections"]
    assert isinstance(sections, dict)
    for name in ["soft_evaluation", "stage_heterogeneity"]:
        section = sections[name]
        assert isinstance(section, dict)
        section["status"] = "available"
    boundary = evidence["claim_boundary"]
    assert isinstance(boundary, dict)
    boundary["full_research_support"] = True
    boundary["status"] = "supported"
    _write_json(run / "peoc_evidence.json", evidence)

    card = build_evidence_card(run)

    paper = card["sections"]["paper_replication_evidence"]
    assert paper["missing_count"] == 2
    assert paper["full_research_support"] is False
    assert card["evidence_tier"] != "tier_4_full_research_diagnostics"
    assert card["recommendation"] in {"needs_review", "not_supported"}


def test_empty_peoc_evidence_artifact_fails_closed(tmp_path: Path) -> None:
    run = tmp_path / "empty-peoc-evidence"
    _write_full_research_run(run)
    _write_json(run / "peoc_evidence.json", {})

    card = build_evidence_card(run)

    paper = card["sections"]["paper_replication_evidence"]
    assert paper["origin"] == "real"
    assert paper["status"] in {"review", "not_supported"}
    assert paper["available_count"] == 0
    assert paper["missing_count"] == 6
    assert card["evidence_tier"] != "tier_4_full_research_diagnostics"
    assert card["recommendation"] in {"needs_review", "not_supported"}
    assert "full support" not in card["claim_language"].lower()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_clean_paired_run(run: Path) -> None:
    _write_json(
        run / "splits.json",
        {
            "split_hash": "sha256:split",
            "counts": {"train": 6, "val": 2, "withheld": 2},
            "leakage": {"has_leakage": False},
        },
    )
    _write_json(
        run / "stats.json",
        {
            "comparisons": [
                {
                    "mean_delta": 0.18,
                    "bootstrap_ci": [0.05, 0.31],
                    "permutation_p_value": 0.01,
                    "holm_adjusted_p_value": 0.01,
                }
            ]
        },
    )
    _write_json(
        run / "comparison_validity.json",
        {
            "validity": "clean",
            "prompt_only_comparison": True,
            "blocking_issues": [],
            "review_items": [],
        },
    )


def _write_full_research_run(run: Path) -> None:
    _write_clean_paired_run(run)
    _write_json(run / "diagnostics" / "soft_hard.json", {"risk": "low"})
    _write_json(run / "diagnostics" / "trajectory.json", {"turnpike_like_signal": True})
    _write_json(run / "diagnostics" / "riccati.json", {"stable_surrogate": True})
    _write_json(
        run / "diagnostics" / "tv_soft.json",
        {"delta_vs_baseline": {"time_varying": 0.2}},
    )


def _write_peoc_run(run: Path) -> None:
    claim_boundary = {
        "full_research_support": False,
        "status": "not_supported",
        "blocking_sections": [
            {"section": "soft_evaluation", "status": "unusable"},
            {"section": "stage_heterogeneity", "status": "failed_validation"},
            {"section": "riccati", "status": "missing"},
            {"section": "soft_hard", "status": "missing"},
        ],
        "statement": "The imported bundle does not support the complete research capability set.",
    }
    selected_pair = {
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "seed": 0,
        "stationary": {"status": "available", "alpha_emp_mean": 0.0247},
        "heterogeneous": {"status": "available", "alpha_emp_mean": 0.00174},
    }
    hard_rows = [
        {
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "task": "bbh3",
            "method": "pez",
            "mean": 0.6,
            "n": 10,
        },
        {
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "task": "bbh3",
            "method": "tv_pmp",
            "mean": 0.69,
            "n": 10,
        },
    ]
    sections = {
        "hard_evaluation": {
            "origin": "real",
            "status": "available",
            "observations": {"methods": ["pez", "tv_pmp"], "rows": hard_rows},
        },
        "soft_evaluation": {
            "origin": "real",
            "status": "unusable",
            "observations": {"valid_row_count": 0, "zero_count_row_count": 2},
        },
        "trajectory": {
            "origin": "real",
            "status": "available",
            "observations": {"headline_pair": selected_pair},
        },
        "stage_heterogeneity": {
            "origin": "real",
            "status": "failed_validation",
            "observations": {"verdict": "FAIL"},
        },
        "riccati": {"origin": "none", "status": "missing", "observations": {}},
        "soft_hard": {"origin": "none", "status": "missing", "observations": {}},
    }
    _write_json(
        run / "manifest.json",
        {
            "mode": "research_import",
            "adapter": "peoc",
            "evidence_origin": "real",
        },
    )
    _write_json(
        run / "source_manifest.json",
        {
            "schema": "prompt_control_lab.peoc_source_manifest.v1",
            "bundle": {"resolved_path": r"D:\private\PEOC\<unsafe-source>"},
            "sources": [],
        },
    )
    _write_json(
        run / "peoc_evidence.json",
        {
            "schema": "prompt_control_lab.peoc_evidence.v1",
            "sections": sections,
            "claim_boundary": claim_boundary,
        },
    )
    _write_json(
        run / "research_case_study.json",
        {
            "schema": "prompt_control_lab.peoc_case_study.v1",
            "evidence_origin": "real",
            "safe_claim": (
                "This <bounded> real PEOC case study reports aggregate results only. "
                "Stage heterogeneity failed validation."
            ),
            "selected_trajectory_pair": selected_pair,
            "hard_summary": {"methods": ["pez", "tv_pmp"]},
            "hard_method_rows": hard_rows,
            "claim_boundary": claim_boundary,
        },
    )
    (run / "research_case_study.md").write_text("# PEOC case study\n", encoding="utf-8")
    (run / "research_case_study.html").write_text(
        "<h1>PEOC case study</h1>\n",
        encoding="utf-8",
    )
