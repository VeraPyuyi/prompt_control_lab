import base64
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from promptcontrollab.cli import main
from promptcontrollab.report_model import ReportModel
from promptcontrollab.ui import charts
from promptcontrollab.ui.components import (
    dashboard_css,
    evidence_ladder_html,
    research_evidence_map_html,
    stat_card_html,
)
from promptcontrollab.ui.data import (
    audit_detail_sections,
    changed_line_rows,
    claim_check_summary,
    claim_evidence_ladder,
    ecosystem_demo_rows,
    evidence_card_rows,
    evidence_gap_rows,
    external_bridge_summary,
    filter_history_rows,
    first_comparison,
    guard_download_payloads,
    history_rows,
    list_runs,
    load_run_detail,
    research_diagnostic_rows,
    research_evidence_map,
    research_status_counts,
)


def test_cli_ui_help_is_available(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["ui", "--help"])

    assert exc_info.value.code == 0
    assert "pcl ui" in capsys.readouterr().out


def test_cli_ui_reports_missing_streamlit(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import importlib.util

    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)

    assert main(["ui", "--runs", "runs"]) == 2

    stderr = capsys.readouterr().err
    assert "pip install -e \".[ui]\"" in stderr


def test_cli_ui_reports_missing_plotly(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import importlib.util

    def fake_find_spec(name: str) -> object | None:
        return None if name == "plotly" else object()

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)

    assert main(["ui", "--runs", "runs"]) == 2

    stderr = capsys.readouterr().err
    assert "plotly" in stderr
    assert "pandas" not in stderr
    assert "pip install -e \".[ui]\"" in stderr


def test_cli_ui_launches_streamlit_with_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib.util

    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())

    def fake_run(command: list[str], *, env: dict[str, str], check: bool) -> SimpleNamespace:
        calls.append({"command": command, "env": env, "check": check})
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    runs = tmp_path / "runs"
    policy = tmp_path / "guard.policy.yaml"
    assert (
        main(
            [
                "ui",
                "--runs",
                str(runs),
                "--policy",
                str(policy),
                "--host",
                "127.0.0.1",
                "--port",
                "8510",
                "--language",
                "zh",
                "--no-browser",
            ]
        )
        == 0
    )

    assert calls
    command = calls[0]["command"]
    env = calls[0]["env"]
    assert command[:4] == [sys.executable, "-m", "streamlit", "run"]
    assert "--server.address=127.0.0.1" in command
    assert "--server.port=8510" in command
    assert "--server.headless=true" in command
    assert "--browser.gatherUsageStats=false" in command
    assert "--client.toolbarMode=viewer" in command
    assert env["PCL_UI_RUNS"] == str(runs)
    assert env["PCL_UI_POLICY"] == str(policy)
    assert env["PCL_UI_LANGUAGE"] == "zh"


def test_cli_ui_uses_project_config_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib.util

    calls: list[dict[str, Any]] = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())

    def fake_run(command: list[str], *, env: dict[str, str], check: bool) -> SimpleNamespace:
        calls.append({"command": command, "env": env, "check": check})
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    (tmp_path / ".promptcontrol.yaml").write_text(
        "\n".join(
            [
                "runs_dir: local-runs",
                "guard_policy: policies/guard.policy.yaml",
                "ui.default_view: history",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert main(["ui", "--no-browser"]) == 0

    env = calls[0]["env"]
    assert env["PCL_UI_RUNS"] == str(tmp_path / "local-runs")
    assert env["PCL_UI_POLICY"] == str(tmp_path / "policies" / "guard.policy.yaml")
    assert env["PCL_UI_DEFAULT_VIEW"] == "history"
    assert env["PCL_UI_CONFIG"] == str(tmp_path / ".promptcontrol.yaml")


def test_ui_data_loads_run_artifacts(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "quick"
    _write_json(
        run / "manifest.json",
        {
            "candidate_model": {"provider": "openai", "model_id": "gpt-5.2"},
            "baseline_model": {"provider": "openai", "model_id": "gpt-4o"},
        },
    )
    _write_json(run / "candidate" / "metrics.json", {"mean_score": 0.9})
    _write_json(
        run / "stats.json",
        {"mean_delta": 0.2, "bootstrap_ci": [0.1, 0.3], "permutation_p_value": 0.01},
    )
    _write_json(run / "gate_result.json", {"status": "needs_review"})
    _write_json(run / "model_drift.json", {"risk": "high", "reason": "model changed"})
    _write_json(
        run / "audit_result.json",
        {
            "touched_files": 3,
            "source_files_changed": 2,
            "test_files_changed": 1,
            "docs_files_changed": 0,
            "config_files_changed": 0,
            "dangerous_paths": ["auth/session.py"],
            "human_review_required": True,
        },
    )
    _write_json(run / "agent_run.json", {"agent": "codex", "model": "gpt-5.2"})
    _write_json(
        run / "history_index.json",
        {
            "runs": [
                {
                    "run_name": "quick",
                    "gate_status": "needs_review",
                    "mean_score": 0.9,
                    "model": {"provider": "openai", "model_id": "gpt-5.2"},
                    "prompt_identity": {"prompt_hash": "sha256:abc"},
                    "risk_categories": ["dangerous_path"],
                }
            ]
        },
    )

    assert [item["name"] for item in list_runs(tmp_path / "runs")] == ["quick"]
    detail = load_run_detail(run)

    assert detail["name"] == "quick"
    assert detail["has_artifacts"] is True
    assert detail["candidate_score"] == 0.9
    assert detail["stats"]["mean_delta"] == 0.2
    assert detail["gate"]["status"] == "needs_review"
    assert detail["model_drift"]["risk"] == "high"
    assert detail["audit"]["dangerous_paths"] == ["auth/session.py"]
    assert detail["agent_run"]["agent"] == "codex"
    assert detail["history_index"]["runs"][0]["run_name"] == "quick"


def test_report_model_preserves_zero_candidate_score(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "quick"
    _write_json(run / "metrics.json", {"mean_score": 0.8})
    _write_json(run / "candidate" / "metrics.json", {"mean_score": 0.0})

    detail = load_run_detail(run)

    assert detail["candidate_score"] == 0.0


def test_report_model_lists_diagnostic_artifacts(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "quick"
    _write_json(run / "manifest.json", {"mode": "quick"})
    _write_json(run / "research_diagnostics.json", {"inputs": {"hidden_states": {"source": "hf"}}})
    _write_json(run / "diagnostics" / "trajectory.json", {"drift": 0.1})

    detail = load_run_detail(run)

    assert detail["research_diagnostics"]["inputs"]["hidden_states"]["source"] == "hf"
    assert "diagnostics/trajectory.json" in detail["artifacts"]
    assert "research_diagnostics.json" in detail["artifacts"]
    assert detail["diagnostics"]["trajectory"]["drift"] == 0.1


def test_report_model_and_ui_detail_read_evidence_card(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "research-demo"
    _write_json(
        run / "evidence_card.json",
        {
            "kind": "prompt_optimization_evidence_card",
            "recommendation": "supported",
            "summary": "Recorded artifacts support the candidate.",
            "sections": {
                "statistical_evidence": {"status": "pass", "mean_delta": 0.2},
                "riccati_surrogate": {"status": "pass", "stable_surrogate": True},
            },
        },
    )
    _write_json(
        run / "claim_check.json",
        {
            "kind": "prompt_optimization_claim_check",
            "requested_claim": "full-research",
            "status": "pass",
            "evidence_tier": "tier_4_full_research_diagnostics",
            "safe_claim": "Full research diagnostic claim is supported.",
            "reason": "All paper-derived diagnostics are present.",
            "next_tier_missing": [],
        },
    )

    model = ReportModel.from_run(run)
    detail = load_run_detail(run)
    rows = evidence_card_rows(detail)
    claim = claim_check_summary(detail)
    ladder = claim_evidence_ladder(detail)

    assert model.evidence_card["recommendation"] == "supported"
    assert model.claim_check["status"] == "pass"
    assert "evidence_card.json" in model.artifacts
    assert "claim_check.json" in model.artifacts
    assert detail["evidence_card"]["summary"] == "Recorded artifacts support the candidate."
    assert detail["claim_check"]["requested_claim"] == "full-research"
    assert {row["section"] for row in rows} == {"statistical evidence", "riccati surrogate"}
    assert rows[0]["status"] == "pass"
    assert claim["status"] == "pass"
    assert claim["safe_claim"] == "Full research diagnostic claim is supported."
    assert [row["claim"] for row in ladder] == ["paired", "partial-research", "full-research"]
    assert all(row["status"] == "supported" for row in ladder)
    assert ladder[-1]["requested"] is True


def test_report_model_and_ui_detail_read_external_bridge_artifacts(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "from-promptfoo-evidence"
    _write_json(
        run / "evidence_from_result.json",
        {
            "kind": "external_evidence",
            "tool": "promptfoo",
            "detected_tools": ["promptfoo"],
        },
    )
    _write_json(
        run / "bridge_summary.json",
        {
            "kind": "external_bridge_summary",
            "detected_tools": ["promptfoo"],
            "pcl_added_evidence": [
                "paired_bootstrap_confidence_interval",
                "prompt_only_comparison_validity",
                "claim_scope_check",
            ],
            "recommendation": "supported",
            "evidence_tier": "tier_2_paired_comparison",
            "validity": "clean",
            "claim_check_status": "pass",
            "claim_check_requested_claim": "paired",
            "missing_evidence": ["hidden_state_diagnostics"],
            "next_actions": ["Run diagnose with hidden states for full research diagnostics."],
        },
    )
    (run / "bridge_summary.md").write_text("# bridge\n", encoding="utf-8")

    model = ReportModel.from_run(run)
    detail = load_run_detail(run)
    bridge = external_bridge_summary(detail)

    assert "evidence_from_result.json" in model.artifacts
    assert "bridge_summary.json" in model.artifacts
    assert "bridge_summary.md" in model.artifacts
    assert model.external_evidence["tool"] == "promptfoo"
    assert detail["bridge_summary"]["validity"] == "clean"
    assert bridge["detected_tools"] == ["promptfoo"]
    assert bridge["pcl_added_count"] == 3
    assert bridge["missing_evidence"] == ["hidden_state_diagnostics"]


def test_ui_recognizes_ecosystem_demo_root_and_summarizes_tools(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    demo = root / "ecosystem-demo"
    _write_json(
        demo / "ecosystem_demo.json",
        {
            "kind": "ecosystem_demo",
            "runs": [
                {
                    "tool": "promptfoo",
                    "validity": "clean",
                    "evidence_tier": "tier_2_paired_comparison",
                    "claim_check_status": "pass",
                    "bridge_summary_path": "promptfoo/bridge_summary.md",
                },
                {
                    "tool": "langfuse",
                    "validity": "needs_review",
                    "evidence_tier": "tier_1_scored_runs",
                    "claim_check_status": "needs_review",
                    "bridge_summary_path": "langfuse/bridge_summary.md",
                },
                {
                    "tool": "langsmith",
                    "validity": "clean",
                    "evidence_tier": "tier_2_paired_comparison",
                    "claim_check_status": "pass",
                    "bridge_summary_path": "langsmith/bridge_summary.md",
                },
            ],
        },
    )

    assert list_runs(root) == [{"name": "ecosystem-demo", "path": str(demo)}]
    detail = load_run_detail(demo)
    rows = ecosystem_demo_rows(detail)

    assert "ecosystem_demo.json" in detail["artifacts"]
    assert [row["tool"] for row in rows] == ["promptfoo", "langfuse", "langsmith"]
    assert rows[0]["open_first"] == "promptfoo/bridge_summary.md"


def test_ui_summarizes_external_evidence_gap_diagnostics(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "ecosystem-demo"
    _write_json(
        run / "research_diagnostics.json",
        {
            "kind": "research_diagnostics",
            "diagnostic_type": "external_evidence_gap",
            "diagnostics": {
                "ecosystem_bridge": {
                    "tool_count": 2,
                    "runs": [
                        {
                            "tool": "promptfoo",
                            "display_name": "Promptfoo",
                            "validity": "needs_review",
                            "evidence_tier": "tier_2_paired_comparison",
                            "claim_check_status": "needs_review",
                            "missing_paper_diagnostics": [
                                "soft-to-hard projection gap",
                                "hidden-state trajectory",
                            ],
                            "bridge_summary_path": "promptfoo/bridge_summary.md",
                        },
                        {
                            "tool": "langsmith",
                            "display_name": "LangSmith",
                            "validity": "clean",
                            "evidence_tier": "tier_2_paired_comparison",
                            "claim_check_status": "pass",
                            "missing_paper_diagnostics": ["Riccati surrogate"],
                            "bridge_summary_path": "langsmith/bridge_summary.md",
                        },
                    ],
                }
            },
        },
    )

    rows = evidence_gap_rows(load_run_detail(run))

    assert [row["tool"] for row in rows] == ["Promptfoo", "LangSmith"]
    assert rows[0]["missing_count"] == 2
    assert rows[0]["missing_paper_diagnostics"] == (
        "soft-to-hard projection gap, hidden-state trajectory"
    )
    assert rows[1]["open_first"] == "langsmith/bridge_summary.md"


def test_ui_summarizes_single_external_evidence_gap_diagnostic(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "from-promptfoo"
    _write_json(
        run / "research_diagnostics.json",
        {
            "kind": "research_diagnostics",
            "diagnostic_type": "external_evidence_gap",
            "diagnostics": {
                "external_bridge": {
                    "tool": "promptfoo",
                    "display_name": "Promptfoo",
                    "validity": "needs_review",
                    "evidence_tier": "tier_2_paired_comparison",
                    "claim_check_status": "needs_review",
                    "missing_paper_diagnostics": ["time-varying soft-control lane"],
                    "bridge_summary_path": "bridge_summary.md",
                }
            },
        },
    )

    rows = evidence_gap_rows(load_run_detail(run))

    assert rows == [
        {
            "tool": "Promptfoo",
            "validity": "needs_review",
            "evidence_tier": "tier_2_paired_comparison",
            "claim_check_status": "needs_review",
            "missing_count": 1,
            "missing_paper_diagnostics": "time-varying soft-control lane",
            "open_first": "bridge_summary.md",
            "report_html": "",
        }
    ]


def test_research_diagnostic_rows_summarize_paper_artifacts(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "research-demo"
    _write_json(run / "diagnostics" / "soft_hard.json", {"risk": "medium"})
    _write_json(
        run / "diagnostics" / "trajectory.json",
        {"turnpike_like_signal": True, "log_decay_slope": -0.42},
    )
    _write_json(
        run / "diagnostics" / "riccati.json",
        {"stable_surrogate": True, "closed_loop_spectral_radius": 0.73},
    )
    _write_json(
        run / "diagnostics" / "tv_soft.json",
        {"delta_vs_baseline": {"time_varying": 0.2}},
    )

    detail = load_run_detail(run)
    rows = research_diagnostic_rows(detail)

    assert [row["diagnostic"] for row in rows] == [
        "soft-hard gap",
        "hidden-state input",
        "trajectory",
        "Riccati surrogate",
        "tv-soft lane",
    ]
    assert all(row["status"] == "available" for row in rows)
    assert research_status_counts(detail) == {"available": 5}


def test_research_evidence_map_links_protocol_diagnostics_and_claim(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "research-demo"
    _write_json(run / "splits.json", {"split_hash": "abc"})
    _write_json(run / "stats.json", {"comparisons": [{"mean_delta": 0.2}]})
    _write_json(run / "comparison_validity.json", {"validity": "clean"})
    _write_json(run / "diagnostics" / "soft_hard.json", {"risk": "low"})
    _write_json(run / "diagnostics" / "trajectory.json", {"turnpike_like_signal": True})
    _write_json(run / "diagnostics" / "riccati.json", {"stable_surrogate": True})
    _write_json(run / "diagnostics" / "tv_soft.json", {"delta_vs_baseline": {"time_varying": 0.1}})
    _write_json(
        run / "claim_check.json",
        {
            "requested_claim": "full-research",
            "status": "pass",
            "evidence_tier": "tier_4_full_research_diagnostics",
        },
    )

    rows = research_evidence_map(load_run_detail(run))
    rendered = research_evidence_map_html(rows)

    assert [row["key"] for row in rows] == [
        "tri_split",
        "paired_stats",
        "comparison_validity",
        "soft_hard",
        "trajectory",
        "riccati",
        "tv_soft",
        "claim_check",
    ]
    assert all(row["status"] == "ready" for row in rows)
    assert rows[-1]["summary"] == "full-research: pass"
    assert "pcl-evidence-map" in rendered
    assert "pcl-map-node ready" in rendered


def test_research_diagnostic_chart_and_design_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        {"diagnostic": "trajectory", "status": "available", "signal": "turnpike-like"},
        {"diagnostic": "Riccati surrogate", "status": "missing", "signal": "not run"},
    ]
    captured: dict[str, object] = {}

    def fake_bar(
        chart_rows: list[dict[str, object]],
        *,
        x: str,
        y: str,
        color: str,
        title: str,
    ) -> SimpleNamespace:
        captured.update({"rows": chart_rows, "x": x, "y": y, "color": color, "title": title})
        return SimpleNamespace(layout=SimpleNamespace(title=SimpleNamespace(text=title)))

    monkeypatch.setattr(charts, "_plotly_express", lambda: SimpleNamespace(bar=fake_bar))

    figure = charts.research_diagnostic_bar(rows, title="Research coverage")

    assert figure.layout.title.text == "Research coverage"
    assert captured["color"] == "status"
    assert "--pcl-bg" in dashboard_css()
    assert ".pcl-evidence-ladder" in dashboard_css()
    assert "pcl-stat-card" in stat_card_html("Trajectory", "available", "turnpike-like")


def test_claim_evidence_ladder_marks_missing_and_requested_claim(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "comparison"
    _write_json(
        run / "evidence_card.json",
        {
            "recommendation": "supported",
            "evidence_tier": "tier_2_paired_comparison",
        },
    )
    _write_json(
        run / "claim_check.json",
        {
            "requested_claim": "full-research",
            "status": "fail",
            "evidence_tier": "tier_2_paired_comparison",
            "recommendation": "supported",
            "next_tier_missing": ["soft-hard", "trajectory", "Riccati", "tv-soft"],
        },
    )

    rows = claim_evidence_ladder(load_run_detail(run))
    rendered = evidence_ladder_html(rows)

    assert rows[0]["status"] == "supported"
    assert rows[1]["status"] == "missing"
    assert rows[2]["status"] == "missing"
    assert rows[2]["requested"] is True
    assert "pcl-ladder-item supported" in rendered
    assert "pcl-ladder-item missing requested" in rendered


def test_report_model_exposes_primary_comparison_fields(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "quick"
    _write_json(
        run / "stats.json",
        {
            "comparisons": [
                {
                    "mean_delta": 0.0,
                    "bootstrap_ci": [-0.1, 0.2],
                    "permutation_p_value": 1.0,
                    "holm_adjusted_p_value": 1.0,
                }
            ],
            "holm_family_size": 1,
        },
    )

    model = ReportModel.from_run(run)

    assert model.first_comparison["mean_delta"] == 0.0
    assert model.mean_delta == 0.0
    assert model.bootstrap_ci == [-0.1, 0.2]
    assert model.permutation_p_value == 1.0
    assert model.holm_adjusted_p_value == 1.0


def test_first_comparison_reads_stats_json_and_legacy_shape() -> None:
    stats = {
        "comparisons": [
            {"mean_delta": 0.25, "bootstrap_ci": [0.1, 0.4], "permutation_p_value": 0.02}
        ],
        "holm_family_size": 1,
    }
    legacy = {"mean_delta": 0.1, "bootstrap_ci": [0.0, 0.2], "permutation_p_value": 0.5}

    assert first_comparison(stats)["mean_delta"] == 0.25
    assert first_comparison(legacy)["mean_delta"] == 0.1


def test_history_rows_normalize_trend_fields() -> None:
    detail = {
        "history_index": {
            "runs": [
                {
                    "run_name": "old",
                    "mean_score": 0.8,
                    "gate_status": "pass",
                    "risk_level": "low",
                    "review_required": False,
                    "model": {"provider": "openai", "model_id": "gpt-4o"},
                    "prompt_identity": {"prompt_hash": "sha256:old"},
                    "risk_categories": [],
                },
                {
                    "run_name": "new",
                    "mean_score": 0.7,
                    "gate_status": "needs_review",
                    "risk_level": "high",
                    "review_required": True,
                    "model": {"provider": "anthropic", "model_id": "claude-sonnet"},
                    "prompt_identity": {"prompt_hash": "sha256:new"},
                    "risk_categories": ["secret"],
                },
            ]
        }
    }

    rows = history_rows(detail)

    assert rows == [
        {
            "order": 1,
            "run": "old",
            "gate_status": "pass",
            "mean_score": 0.8,
            "risk_level": "low",
            "review_required": False,
            "provider": "openai",
            "model": "gpt-4o",
            "prompt_hash": "sha256:old",
            "risk_categories": [],
        },
        {
            "order": 2,
            "run": "new",
            "gate_status": "needs_review",
            "mean_score": 0.7,
            "risk_level": "high",
            "review_required": True,
            "provider": "anthropic",
            "model": "claude-sonnet",
            "prompt_hash": "sha256:new",
            "risk_categories": ["secret"],
        },
    ]


def test_filter_history_rows_supports_risky_and_model_filters() -> None:
    rows = [
        {
            "run": "old",
            "risk_level": "low",
            "review_required": False,
            "provider": "openai",
            "model": "gpt-4o",
        },
        {
            "run": "new",
            "risk_level": "high",
            "review_required": True,
            "provider": "anthropic",
            "model": "claude-sonnet",
        },
    ]

    assert [row["run"] for row in filter_history_rows(rows, only_review_required=True)] == ["new"]
    assert [row["run"] for row in filter_history_rows(rows, only_high_risk=True)] == ["new"]
    assert [row["run"] for row in filter_history_rows(rows, provider="openai")] == ["old"]
    assert [row["run"] for row in filter_history_rows(rows, model="sonnet")] == ["new"]


def test_audit_detail_sections_expose_high_signal_fields() -> None:
    audit = {
        "secret_findings": [{"path": "src/app.py", "kind": "token", "redacted": "***"}],
        "dependency_files_changed": ["pyproject.toml"],
        "lockfiles_changed": ["uv.lock"],
        "workflow_files_changed": [".github/workflows/ci.yml"],
        "deleted_test_files": ["tests/test_old.py"],
        "unexpected_files": ["auth/session.py"],
        "test_results": [{"command": "pytest", "returncode": 1, "stderr": "failed"}],
    }

    sections = audit_detail_sections(audit)

    assert sections["secret_findings"][0]["path"] == "src/app.py"
    assert sections["dependency_files_changed"] == [{"path": "pyproject.toml"}]
    assert sections["lockfiles_changed"] == [{"path": "uv.lock"}]
    assert sections["workflow_files_changed"] == [{"path": ".github/workflows/ci.yml"}]
    assert sections["deleted_test_files"] == [{"path": "tests/test_old.py"}]
    assert sections["unexpected_files"] == [{"path": "auth/session.py"}]
    assert sections["test_results"][0]["stderr"] == "failed"


def test_changed_line_rows_mark_file_risks() -> None:
    audit = {
        "changed_lines": {
            "src/app.py": {"added": 2, "deleted": 1},
            ".github/workflows/ci.yml": {"added": 5, "deleted": 0},
            "pyproject.toml": {"added": 1, "deleted": 0},
            "auth/session.py": {"added": 1, "deleted": 0},
        },
        "secret_findings": [{"path": "src/app.py", "kind": "token"}],
        "workflow_files_changed": [".github/workflows/ci.yml"],
        "dependency_files_changed": ["pyproject.toml"],
        "dangerous_paths": ["auth/session.py"],
    }

    rows = changed_line_rows(audit)

    assert rows[0]["file"] == ".github/workflows/ci.yml"
    by_file = {row["file"]: row for row in rows}
    assert by_file["src/app.py"]["risk"] == "secret"
    assert by_file[".github/workflows/ci.yml"]["risk"] == "workflow"
    assert by_file["pyproject.toml"]["risk"] == "dependency"
    assert by_file["auth/session.py"]["risk"] == "dangerous_path"


def test_guard_download_payloads_return_json_and_text() -> None:
    payloads = guard_download_payloads({"action": "suggest", "improved_prompt": "Do X"})

    assert payloads["guard_result.json"].startswith("{")
    assert '"action": "suggest"' in payloads["guard_result.json"]
    assert payloads["improved_prompt.txt"] == "Do X\n"


def test_ui_list_runs_prefers_child_runs_when_root_has_history_index(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _write_json(runs / "history_index.json", {"runs": []})
    _write_json(runs / "quick" / "manifest.json", {"mode": "quick"})
    _write_json(runs / "audit" / "audit_result.json", {"touched_files": 1})
    (runs / "scratch").mkdir()

    rows = list_runs(runs)

    assert [row["name"] for row in rows] == ["audit", "quick"]


def test_ui_list_runs_prefers_child_runs_when_root_has_claim_check(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _write_json(runs / "claim_check.json", {"status": "pass"})
    _write_json(runs / "quick" / "manifest.json", {"mode": "quick"})
    _write_json(runs / "research-demo" / "claim_check.json", {"status": "pass"})

    rows = list_runs(runs)

    assert [row["name"] for row in rows] == ["quick", "research-demo"]


def test_ui_list_runs_keeps_current_run_when_it_has_manifest(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "quick"
    _write_json(run / "manifest.json", {"mode": "quick"})
    _write_json(run / "baseline" / "metrics.json", {"mean_score": 0.5})
    _write_json(run / "candidate" / "metrics.json", {"mean_score": 0.75})

    rows = list_runs(run)

    assert rows == [{"name": "quick", "path": str(run)}]


def test_ui_loads_comparison_validity_artifact(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "quick"
    _write_json(run / "comparison_validity.json", {"validity": "clean"})

    assert list_runs(tmp_path / "runs") == [{"name": "quick", "path": str(run)}]
    detail = load_run_detail(run)
    assert detail["comparison_validity"]["validity"] == "clean"
    assert "comparison_validity.json" in detail["artifacts"]


def test_ui_has_history_view_order_and_text() -> None:
    from promptcontrollab.ui import app

    assert "research" in app.TEXT["en"]
    assert "research" in app.TEXT["zh"]
    assert "history" in app.TEXT["en"]
    assert "history" in app.TEXT["zh"]
    assert "tutorial" in app.TEXT["en"]
    assert "tutorial" in app.TEXT["zh"]
    assert "workflows" in app.TEXT["en"]
    assert "workflows" in app.TEXT["zh"]
    assert "comparison_validity" in app.TEXT["en"]
    assert "comparison_validity" in app.TEXT["zh"]
    assert "prompt_only" in app.TEXT["en"]
    assert "prompt_only" in app.TEXT["zh"]
    assert app._ordered_views("research")[0] == "research"
    assert app._ordered_views("workflows")[0] == "workflows"
    assert app._ordered_views("history")[0] == "history"
    assert app._ordered_views("tutorial")[0] == "tutorial"


def test_ui_choice_labels_are_localized_but_keep_internal_values() -> None:
    from promptcontrollab.ui import app

    assert app._choice_labels("execution_mode", "zh") == [
        "确认后执行",
        "自动执行",
        "只生成命令",
    ]
    assert app._choice_value("execution_mode", "确认后执行", "zh") == "confirm"
    assert app._choice_value("profile", "编程", "zh") == "coding"
    assert app._choice_value("guard_mode", "给出建议", "zh") == "suggest"
    assert app._choice_value("token_mode", "平衡省 token", "zh") == "balanced"
    assert app._choice_value("tests_passed", "未知", "zh") == "unknown"
    assert app._choice_labels("profile", "en") == ["coding", "general", "research"]


def test_ui_tutorial_sections_are_complete_and_localized() -> None:
    from promptcontrollab.ui import app

    expected_ids = {
        "guard",
        "workflows",
        "report",
        "drift",
        "audit",
        "history",
        "project_defaults",
        "export_pr",
    }
    sections = app.tutorial_sections("zh")

    assert {section["id"] for section in sections} == expected_ids
    for section in sections:
        assert section["operation"]
        assert section["result"]
        assert section["meaning"]
        assert section["next_step"]
        assert section["screenshot"]
        assert section["steps"]
        assert section["command"].startswith("pcl ")
    assert not _contains_replacement_character(app.TEXT["zh"])
    assert not _contains_replacement_character(sections)
    assert "Deploy" not in str(app.TEXT["zh"])
    assert "三点菜单" not in str(app.TEXT["zh"])


def test_ui_tutorial_gallery_exposes_visible_images() -> None:
    from promptcontrollab.ui import app

    gallery = app.tutorial_gallery_items("zh")

    assert [item["image"] for item in gallery] == [
        "workflows",
        "guard",
        "report",
        "model_drift",
        "audit",
        "history",
    ]
    assert all(item["title"] for item in gallery)


def test_tutorial_screenshot_assets_exist() -> None:
    assets = [
        "tutorial_workflows.en.png",
        "tutorial_workflows.zh.png",
        "tutorial_guard.en.png",
        "tutorial_guard.zh.png",
        "tutorial_report.en.png",
        "tutorial_report.zh.png",
        "tutorial_model_drift.en.png",
        "tutorial_model_drift.zh.png",
        "tutorial_audit.en.png",
        "tutorial_audit.zh.png",
        "tutorial_history.en.png",
        "tutorial_history.zh.png",
    ]
    for name in assets:
        path = Path("docs") / "assets" / name
        assert path.exists(), name
        assert path.stat().st_size > 10_000, name


def test_tutorial_svg_assets_exist_and_use_prompt_control_lab() -> None:
    assets = [
        "tutorial_overview.svg",
        "tutorial_overview.zh.svg",
        "tutorial_guard.svg",
        "tutorial_guard.zh.svg",
        "tutorial_report.svg",
        "tutorial_report.zh.svg",
        "tutorial_audit_history.svg",
        "tutorial_audit_history.zh.svg",
    ]
    for name in assets:
        path = Path("docs") / "assets" / name
        assert path.exists(), name
        text = path.read_text(encoding="utf-8")
        assert "prompt_control_lab" in text
        assert "promptcontrollab" not in text
        assert 'viewBox="0 0 ' in text


def test_tutorial_svg_renderer_reads_utf8_svg(tmp_path: Path) -> None:
    from promptcontrollab.ui import app

    svg = tmp_path / "tutorial.zh.svg"
    svg.write_text(
        '<svg viewBox="0 0 100 40"><text>中文 prompt_control_lab</text></svg>',
        encoding="utf-8",
    )
    calls: list[dict[str, object]] = []

    class FakeStreamlit:
        def markdown(self, body: str, *, unsafe_allow_html: bool = False) -> None:
            calls.append({"body": body, "unsafe": unsafe_allow_html})

    app._render_svg(FakeStreamlit(), svg)

    body = str(calls[0]["body"])
    encoded = body.split("base64,", 1)[1].split('"', 1)[0]

    assert calls[0]["unsafe"] is True
    assert "中文 prompt_control_lab" in base64.b64decode(encoded).decode("utf-8")


def test_tutorial_svg_renderer_uses_data_uri_not_raw_svg(tmp_path: Path) -> None:
    from promptcontrollab.ui import app

    svg = tmp_path / "tutorial.zh.svg"
    svg.write_text(
        '<svg viewBox="0 0 100 40"><text>中文 prompt_control_lab</text></svg>',
        encoding="utf-8",
    )
    calls: list[dict[str, object]] = []

    class FakeStreamlit:
        def markdown(self, body: str, *, unsafe_allow_html: bool = False) -> None:
            calls.append({"body": body, "unsafe": unsafe_allow_html})

    app._render_svg(FakeStreamlit(), svg)

    body = str(calls[0]["body"])
    assert body.startswith('<img src="data:image/svg+xml;base64,')
    assert "<svg" not in body


def test_tutorial_png_renderer_uses_data_uri(tmp_path: Path) -> None:
    from promptcontrollab.ui import app

    png = tmp_path / "tutorial.zh.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    calls: list[dict[str, object]] = []

    class FakeStreamlit:
        def markdown(self, body: str, *, unsafe_allow_html: bool = False) -> None:
            calls.append({"body": body, "unsafe": unsafe_allow_html})

    app._render_image(FakeStreamlit(), png)

    body = str(calls[0]["body"])
    assert calls[0]["unsafe"] is True
    assert body.startswith('<img src="data:image/png;base64,')


def test_ui_hides_streamlit_native_chrome() -> None:
    from promptcontrollab.ui import app

    calls: list[dict[str, object]] = []

    class FakeStreamlit:
        def markdown(self, body: str, *, unsafe_allow_html: bool = False) -> None:
            calls.append({"body": body, "unsafe": unsafe_allow_html})

    app._hide_streamlit_chrome(FakeStreamlit())

    body = str(calls[0]["body"])
    assert calls[0]["unsafe"] is True
    assert "#MainMenu" in body
    assert '[data-testid="stToolbar"]' in body


def _contains_replacement_character(value: object) -> bool:
    if isinstance(value, str):
        return "\ufffd" in value
    if isinstance(value, dict):
        return any(_contains_replacement_character(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_replacement_character(item) for item in value)
    return False


def test_ui_data_handles_missing_artifacts(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "empty"
    run.mkdir(parents=True)

    assert list_runs(tmp_path / "runs") == [{"name": "empty", "path": str(run)}]
    detail = load_run_detail(run)

    assert detail["has_artifacts"] is False
    assert detail["candidate_score"] is None
    assert "Run `pcl analyze`" in detail["empty_state"]


def test_score_delta_ci_uses_upper_and_lower_error_bars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeBar:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    class FakeFigure:
        def add_trace(self, trace: object) -> None:
            captured["trace"] = trace

        def add_hline(self, **kwargs: object) -> None:
            captured["hline"] = kwargs

        def update_layout(self, **kwargs: object) -> None:
            captured["layout"] = kwargs

    fake_go = SimpleNamespace(Bar=FakeBar, Figure=FakeFigure)
    monkeypatch.setattr(charts, "_plotly_graph_objects", lambda: fake_go)

    charts.score_delta_ci({"mean_delta": 0.2, "bootstrap_ci": [0.1, 0.35]})

    assert captured["error_y"] == {
        "type": "data",
        "array": [0.14999999999999997],
        "arrayminus": [0.1],
    }


def test_score_delta_ci_accepts_stats_json_comparisons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeBar:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    class FakeFigure:
        def add_trace(self, trace: object) -> None:
            captured["trace"] = trace

        def add_hline(self, **kwargs: object) -> None:
            captured["hline"] = kwargs

        def update_layout(self, **kwargs: object) -> None:
            captured["layout"] = kwargs

    fake_go = SimpleNamespace(Bar=FakeBar, Figure=FakeFigure)
    monkeypatch.setattr(charts, "_plotly_graph_objects", lambda: fake_go)

    charts.score_delta_ci(
        {
            "comparisons": [
                {"mean_delta": 0.0, "bootstrap_ci": [-0.2, 0.3], "permutation_p_value": 1.0}
            ]
        }
    )

    assert captured["y"] == [0.0]
    assert captured["error_y"] == {
        "type": "data",
        "array": [0.3],
        "arrayminus": [0.2],
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
