from __future__ import annotations

import json
from pathlib import Path

from promptcontrollab.cli import build_parser
from promptcontrollab.version import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_v02_alpha_version_and_readmes_are_consistent() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    english = (ROOT / "README.md").read_text(encoding="utf-8")
    chinese = (ROOT / "README.zh.md").read_text(encoding="utf-8")

    assert __version__ == "0.2.0a1"
    assert 'version = "0.2.0a1"' in pyproject
    assert "promptcontrollab 0.2.0a1" in english
    assert "promptcontrollab 0.2.0a1" in chinese
    assert "PromptControlLab 2.0" not in english
    assert "PromptControlLab 2.0" not in chinese


def test_alpha_quickstarts_and_pilot_prepare_match_real_cli() -> None:
    english = (ROOT / "docs/quickstart.en.md").read_text(encoding="utf-8")
    chinese = (ROOT / "docs/quickstart.zh.md").read_text(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(["posttrain-pilot-prepare", "--out", "demo"])

    assert "pcl quickstart --out demo --open-report" in english
    assert "pcl quickstart --out demo --open-report" in chinese
    assert args.command == "posttrain-pilot-prepare"
    assert "datasets>=2.19" in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_pilot_status_records_completed_bounded_checkpoint_evidence() -> None:
    path = ROOT / "docs/case_studies/server_evidence/sft_pilot_status.json"
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["execution_status"] == "complete"
    assert payload["gpu_work_started"] is True
    assert payload["seeds"] == [0, 1, 2]
    assert payload["checkpoint_runs"] == 9
    assert payload["gate_count"] == 6
    assert payload["decision"] == "hold"
    assert payload["model_revision"] == "7ae557604adf67be50417f59c2c2f167def9a775"
    assert payload["dataset_revision"] == "740312add88f781978c0658806c59bc2815b9866"
    assert "does not establish" in payload["claim_boundary"]
    assert payload["public_case"] == "../sft_checkpoint_pilot/README.md"
    assert payload["observed"]["initial_mean_score"] == 0.088541666667
    assert payload["observed"]["final_mean_score"] == 0.194444444444


def test_harness_status_separates_integration_wiring_from_live_acceptance() -> None:
    path = ROOT / "docs/case_studies/deepseek_harness/live_session_status.json"
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["integration_evidence"]["typescript_contract_tests_passed"] == 27
    assert payload["integration_evidence"]["machine_acceptance_enforced"] is True
    assert (
        payload["integration_evidence"]["fixture_replay_rejected_from_live_acceptance"]
        is True
    )
    assert payload["integration_evidence"]["persistent_bridge_started"] is True
    assert payload["live_acceptance"]["credential_available"] is False
    assert payload["live_acceptance"]["model_request_observed"] is False
    assert payload["live_acceptance"]["provider_request_id_recorded"] is False
    assert payload["live_acceptance"]["accepted"] is False
    assert "not a real DeepSeek Harness" in payload["claim_boundary"]
    persisted = path.read_text(encoding="utf-8")
    assert "D:\\" not in persisted
    assert "/root/" not in persisted
    assert "session-" not in persisted
