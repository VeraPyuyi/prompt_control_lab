from __future__ import annotations

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
from promptcontrollab.ui.data import (
    audit_detail_sections,
    changed_line_rows,
    filter_history_rows,
    first_comparison,
    guard_download_payloads,
    history_rows,
    list_runs,
    load_run_detail,
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
    _write_json(run / "diagnostics" / "trajectory.json", {"drift": 0.1})

    detail = load_run_detail(run)

    assert "diagnostics/trajectory.json" in detail["artifacts"]


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


def test_ui_has_history_view_order_and_text() -> None:
    from promptcontrollab.ui import app

    assert "history" in app.TEXT["en"]
    assert "history" in app.TEXT["zh"]
    assert "tutorial" in app.TEXT["en"]
    assert "tutorial" in app.TEXT["zh"]
    assert "workflows" in app.TEXT["en"]
    assert "workflows" in app.TEXT["zh"]
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
        assert section["command"].startswith("pcl ")
    assert not _contains_replacement_character(app.TEXT["zh"])
    assert not _contains_replacement_character(sections)


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

    assert calls[0]["unsafe"] is True
    assert "中文 prompt_control_lab" in str(calls[0]["body"])


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
