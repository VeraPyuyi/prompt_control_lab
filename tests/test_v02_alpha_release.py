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


def test_harness_status_records_public_safe_live_acceptance() -> None:
    path = ROOT / "docs/case_studies/deepseek_harness/live_session_status.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    evidence_path = ROOT / "docs/case_studies/deepseek_harness/live_session_evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    assert payload["integration_evidence"]["typescript_contract_tests_passed"] == 28
    assert payload["integration_evidence"]["machine_acceptance_enforced"] is True
    assert (
        payload["integration_evidence"]["fixture_replay_rejected_from_live_acceptance"]
        is True
    )
    assert payload["integration_evidence"]["persistent_bridge_started"] is True
    assert payload["evidence"] == "live_session_evidence.json"
    assert evidence["source"]["session_origin"] == "live_cordis"
    assert evidence["source"]["transport"] == "persistent_stdio"
    assert evidence["source"]["provider_request_id_recorded"] is False
    assert evidence["credential_scan"]["supplied_ephemerally"] is True
    assert evidence["credential_scan"]["scan_type"] == "credential_shape_regex"
    assert evidence["credential_scan"]["findings"] == 0
    assert len(evidence["credential_scan"]["scope"]) == 3
    assert evidence["credential_scan"]["scope_results"] == {
        "disposable_task_worktree": {"files_scanned": 10, "findings": 0},
        "prompt_control_lab_control_artifacts": {"files_scanned": 11, "findings": 0},
        "deepseek_harness_session_artifacts": {"files_scanned": 1, "findings": 0},
    }
    assert payload["live_acceptance"]["model_request_observed"] is True
    assert payload["live_acceptance"] == {
        "model_request_observed": True,
        **evidence["lifecycle"],
    }
    assert evidence["lifecycle"]["model_request_response_pairs"] == 4
    assert evidence["lifecycle"]["unique_tool_calls"] == 4
    assert evidence["lifecycle"]["operations"] == {
        "file_read": 2,
        "file_write": 1,
        "test_execution": 1,
    }
    assert evidence["lifecycle"]["test_execution_exit_codes"] == [0]
    assert evidence["lifecycle"]["tests_passed"] == 3
    assert evidence["lifecycle"]["tests_total"] == 3
    assert evidence["lifecycle"]["changed_files"] == ["src/math_utils.py"]
    assert evidence["lifecycle"]["changed_lines"] == {"added": 1, "deleted": 1}
    assert evidence["usage"] == {
        "source": "captured_harness_metadata",
        "input_tokens": 13401,
        "output_tokens": 619,
        "cache_tokens_recorded": False,
    }
    assert payload["diagnostic_result"] == evidence["control"]
    assert evidence["control"]["preflight_decision"] == "suggest"
    assert evidence["control"]["preflight_risk"] == "low"
    assert evidence["control"]["final_control_decision"] == "suggest"
    assert evidence["control"]["stability_state"] == "converging"
    assert evidence["control"]["stability_evidence"] == "terminal_test_exit_code_0"
    assert "real model-backed Harness lifecycle" in payload["claim_boundary"]
    assert "does not prove" in payload["claim_boundary"]
    persisted = path.read_text(encoding="utf-8") + evidence_path.read_text(encoding="utf-8")
    assert "D:\\" not in persisted
    assert "/root/" not in persisted
    assert "session-" not in persisted
    assert "DEEPSEEK_API_KEY" not in persisted
    assert "sk-" not in persisted.lower()
    assert evidence["derivation"]["raw_prompt_published"] is False
    assert evidence["derivation"]["raw_model_response_published"] is False
    assert "raw_prompt_body" not in persisted.lower()
