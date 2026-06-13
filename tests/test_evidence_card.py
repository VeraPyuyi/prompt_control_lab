from __future__ import annotations

import json
from pathlib import Path

from promptcontrollab.cli import main
from promptcontrollab.evidence_card import build_evidence_card, render_evidence_card_markdown
from promptcontrollab.files import read_json


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
    assert card["sections"]["protocol_hygiene"]["status"] == "pass"
    assert card["sections"]["statistical_evidence"]["mean_delta"] == 0.18
    assert card["sections"]["comparison_validity"]["status"] == "clean"
    assert card["sections"]["deployment_diagnostics"]["soft_hard_risk"] == "low"
    assert card["sections"]["hidden_state_diagnostics"]["input_source"] == "huggingface_extraction"
    assert card["sections"]["hidden_state_diagnostics"]["states_shape"] == [32, 896]
    assert card["sections"]["riccati_surrogate"]["stable_surrogate"] is True
    assert card["sections"]["time_varying_control"]["best_delta_method"] == "time_varying"

    markdown = render_evidence_card_markdown(card)
    assert "# Prompt Optimization Evidence Card" in markdown
    assert "Recommendation: `supported`" in markdown
    assert "Hidden-state diagnostics" in markdown
    assert "Riccati surrogate" in markdown


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
    assert markdown_out.exists()
    assert "Statistical evidence" in markdown_out.read_text(encoding="utf-8")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
