from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from promptcontrollab.cli import main
from promptcontrollab.ui.data import list_runs, load_run_detail


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
    assert env["PCL_UI_RUNS"] == str(runs)
    assert env["PCL_UI_POLICY"] == str(policy)
    assert env["PCL_UI_LANGUAGE"] == "zh"


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

    assert [item["name"] for item in list_runs(tmp_path / "runs")] == ["quick"]
    detail = load_run_detail(run)

    assert detail["name"] == "quick"
    assert detail["has_artifacts"] is True
    assert detail["candidate_score"] == 0.9
    assert detail["stats"]["mean_delta"] == 0.2
    assert detail["gate"]["status"] == "needs_review"
    assert detail["model_drift"]["risk"] == "high"
    assert detail["audit"]["dangerous_paths"] == ["auth/session.py"]


def test_ui_data_handles_missing_artifacts(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "empty"
    run.mkdir(parents=True)

    assert list_runs(tmp_path / "runs") == [{"name": "empty", "path": str(run)}]
    detail = load_run_detail(run)

    assert detail["has_artifacts"] is False
    assert detail["candidate_score"] is None
    assert "Run `pcl analyze`" in detail["empty_state"]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
