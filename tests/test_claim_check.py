from __future__ import annotations

import json
from pathlib import Path

from promptcontrollab.claim_check import render_claim_check_html, run_claim_check
from promptcontrollab.cli import main
from promptcontrollab.files import read_json


def test_claim_check_passes_full_research_when_all_diagnostics_exist(tmp_path: Path) -> None:
    run = _full_research_run(tmp_path)

    payload = run_claim_check(run, claim="full-research")

    assert payload["kind"] == "prompt_optimization_claim_check"
    assert payload["requested_claim"] == "full-research"
    assert payload["status"] == "pass"
    assert payload["evidence_tier"] == "tier_4_full_research_diagnostics"
    assert "Recorded artifacts support" in payload["safe_claim"]
    assert payload["next_tier_missing"] == []
    html = render_claim_check_html(payload)
    assert "Prompt Optimization Claim Check" in html
    assert "full-research" in html
    assert "pass" in html


def test_claim_check_rejects_full_research_for_paired_only_evidence(tmp_path: Path) -> None:
    run = _paired_only_run(tmp_path)

    paired = run_claim_check(run, claim="paired")
    full = run_claim_check(run, claim="full-research")

    assert paired["status"] == "pass"
    assert paired["evidence_tier"] == "tier_2_paired_comparison"
    assert full["status"] == "fail"
    assert "does not support the requested full-research claim" in full["reason"]
    assert "paired comparison claim only" in full["safe_claim"]
    assert "deployment_diagnostics" in full["next_tier_missing"]


def test_claim_check_fails_when_core_comparison_is_incomplete(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _write_json(run / "stats.json", {"comparisons": [{"mean_delta": 0.0}]})

    payload = run_claim_check(run, claim="paired")

    assert payload["status"] == "fail"
    assert payload["evidence_tier"] == "tier_1_incomplete_comparison"
    assert "does not support the requested paired claim" in payload["reason"]
    assert "not as evidence" in payload["safe_claim"]


def test_claim_check_rejects_full_research_when_peoc_boundary_is_fail_closed(
    tmp_path: Path,
) -> None:
    run = _full_research_run(tmp_path)
    statuses = {
        "hard_evaluation": "available",
        "soft_evaluation": "available",
        "trajectory": "partial",
        "stage_heterogeneity": "available",
        "riccati": "available",
        "soft_hard": "available",
    }
    _write_json(
        run / "peoc_evidence.json",
        {
            "schema": "prompt_control_lab.peoc_evidence.v1",
            "sections": {
                name: {"origin": "real", "status": status, "observations": {}}
                for name, status in statuses.items()
            },
            "claim_boundary": {
                "full_research_support": False,
                "status": "not_supported",
                "blocking_sections": [{"section": "trajectory", "status": "partial"}],
            },
        },
    )
    _write_json(
        run / "research_case_study.json",
        {
            "schema": "prompt_control_lab.peoc_case_study.v1",
            "safe_claim": "The imported PEOC evidence supports a bounded partial result only.",
        },
    )

    payload = run_claim_check(run, claim="full-research")

    assert payload["status"] == "fail"
    assert payload["evidence_tier"] == "tier_3_partial_research_diagnostics"
    assert payload["recommendation"] == "needs_review"
    assert payload["safe_claim"] == (
        "The imported PEOC evidence supports a bounded partial result only."
    )
    assert "full support" not in payload["safe_claim"].lower()
    assert "paper_replication_evidence" in payload["next_tier_missing"]


def test_cli_claim_check_writes_json_and_markdown(tmp_path: Path) -> None:
    run = _paired_only_run(tmp_path)
    out = tmp_path / "claim_check.json"

    assert main(["claim-check", "--run", str(run), "--claim", "paired", "--out", str(out)]) == 0

    payload = read_json(out)
    assert payload["status"] == "pass"
    assert payload["requested_claim"] == "paired"
    assert payload["html_path"] == str(out.with_suffix(".html"))
    markdown = out.with_suffix(".md")
    html = out.with_suffix(".html")
    assert markdown.exists()
    assert html.exists()
    text = markdown.read_text(encoding="utf-8")
    assert "# Prompt Optimization Claim Check" in text
    assert "Safe claim" in text
    assert "Prompt Optimization Claim Check" in html.read_text(encoding="utf-8")


def _paired_only_run(tmp_path: Path) -> Path:
    run = tmp_path / "paired"
    _write_json(
        run / "stats.json",
        {
            "comparisons": [
                {
                    "mean_delta": 0.2,
                    "bootstrap_ci": [0.04, 0.36],
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
    return run


def _full_research_run(tmp_path: Path) -> Path:
    run = _paired_only_run(tmp_path)
    _write_json(
        run / "splits.json",
        {
            "split_hash": "sha256:split",
            "counts": {"train": 6, "val": 2, "withheld": 2},
            "leakage": {"has_leakage": False},
        },
    )
    _write_json(
        run / "diagnostics" / "soft_hard.json",
        {"risk": "low", "mean_projection_distance": 0.05, "max_projection_distance": 0.13},
    )
    _write_json(
        run / "research_diagnostics.json",
        {
            "inputs": {
                "hidden_states": {
                    "source": "huggingface_extraction",
                    "model_id": "Qwen/Qwen2.5-0.5B",
                    "states_shape": [16, 896],
                    "pool": "last-token",
                }
            }
        },
    )
    _write_json(
        run / "diagnostics" / "trajectory.json",
        {"turnpike_like_signal": True, "log_decay_slope": -0.4, "decay_r2": 0.91},
    )
    _write_json(
        run / "diagnostics" / "riccati.json",
        {"stable_surrogate": True, "closed_loop_spectral_radius": 0.7},
    )
    _write_json(
        run / "diagnostics" / "tv_soft.json",
        {
            "method_means": {"static": 0.5, "time_varying": 0.7},
            "delta_vs_baseline": {"time_varying": 0.2},
        },
    )
    return run


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
