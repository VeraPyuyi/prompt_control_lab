from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from pytest import CaptureFixture

from promptcontrollab.cli import main
from promptcontrollab.evidence.server_evidence import (
    EvidenceImportOptions,
    import_evidence_manifest,
    scan_evidence_root,
)
from promptcontrollab.files import read_json


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_server_fixture(root: Path) -> None:
    _write_json(
        root / "experiments/turnpike_trace/results_a800/stationary_arith_qwen_s0.json",
        {"alpha_emp_mean": 0.03, "R2_mean": 0.62, "n_streams": 16},
    )
    _write_json(
        root / "experiments/turnpike_trace/results_a800/turnpike_gsm8k_qwen_s0.json",
        {"alpha_emp_mean": 0.002, "R2_mean": 0.09, "n_prompts": 32},
    )
    (root / "experiments/turnpike_trace/results_a800/stationary_arith_qwen_s0.npz").write_bytes(
        b"npz-placeholder"
    )
    _write_json(
        root / "theory/results/ass_hyp_verify_stationary_qwen_s0.json",
        {
            "rho_A_open_subspace": 0.99,
            "ASS_HYP_via_DARE": [{"R_scale": 1.0, "rho_A_cl": 0.81, "success": True}],
        },
    )
    _write_json(
        root / "experiments/redo_a_fair_deployment/REDO_A_REPORT.json",
        {
            "n_seed_rows": 240,
            "n_cells": 48,
            "E2_tv_seg_vs_static_matched": {"mean_diff": -0.02, "p_value": 0.2},
        },
    )
    _write_json(
        root / "experiments/redo_a_fair_deployment/QAT_EXT_REPORT_FINAL.json",
        {
            "n_rows": 240,
            "n_cells": 48,
            "X1_soft_seg_vs_hard_seg": {"mean_diff": 0.01, "ci": [-0.01, 0.03]},
        },
    )
    controls = root / "experiments/redo_a_fair_deployment/artifacts/control.pt"
    controls.parent.mkdir(parents=True, exist_ok=True)
    controls.write_bytes(b"unsafe-pickle-like-placeholder")
    _write_json(
        root
        / "experiments/p0_control_to_deployment/production_v2/audit/P0_CONFIRMATORY_ANALYSIS.json",
        {
            "all_validity_gates_passed": True,
            "interpretation": "CONFIRMATORY_FAIL_CLOSED",
            "n_rows": 72,
            "primary_control_order_interaction": {"p_value": 0.08984375},
        },
    )
    _write_json(
        root
        / "experiments/p0_control_to_deployment/production_v2/audit/FROZEN_VALIDATOR_AUDIT.json",
        {"status": "PASS", "n_cells": 72},
    )
    _write_json(
        root / "experiments/generation_aware_control/run_001/status.json",
        {"status": "PILOT_MIXED_DO_NOT_CLAIM_FIX"},
    )
    _write_json(
        root / "experiments/generation_aware_control/run_002/status.json",
        {"status": "PILOT_NEUTRAL_DO_NOT_CLAIM_FIX"},
    )
    _write_json(
        root / "experiments/p4_selective_risk_seed_holdout/p4_selective_risk_report.json",
        {
            "status": "SELECTIVE_RISK_PASS",
            "n_seed_rows": 360,
            "observed_aurc": 0.2969,
            "random_mean_aurc": 0.4098,
            "accuracy_at_20pct": 0.7826,
        },
    )
    _write_json(
        root / "verifiable-dynamics-workspace/schemas/repair_episode.schema.json",
        {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RepairEpisode"},
    )


def test_scan_evidence_root_is_deterministic_and_records_all_adapters(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    _write_server_fixture(root)

    first = scan_evidence_root(root=root, profile="peoc-server")
    second = scan_evidence_root(root=root, profile="peoc-server")

    assert first == second
    assert first["schema"] == "prompt_control_lab.server_evidence_manifest.v1"
    assert first["profile"] == "peoc-server"
    assert {row["adapter"] for row in first["sources"]} == {
        "agent_episode",
        "deployment_gate",
        "generation_aware",
        "riccati_ass_hyp",
        "selective_risk",
        "soft_hard_tv",
        "turnpike_a800",
    }
    assert [row["relative_path"] for row in first["sources"]] == sorted(
        row["relative_path"] for row in first["sources"]
    )
    for row in first["sources"]:
        source = root / row["relative_path"]
        assert row["sha256"] == f"sha256:{hashlib.sha256(source.read_bytes()).hexdigest()}"
    pt_source = next(row for row in first["sources"] if row["relative_path"].endswith(".pt"))
    npz_source = next(row for row in first["sources"] if row["relative_path"].endswith(".npz"))
    assert pt_source["load_policy"] == "metadata_only_weights_only_required"
    assert npz_source["load_policy"] == "hash_only_by_default"


def test_scan_snapshot_identity_is_portable_across_root_locations(tmp_path: Path) -> None:
    first_root = tmp_path / "first/projects"
    second_root = tmp_path / "second/projects"
    _write_server_fixture(first_root)
    shutil.copytree(first_root, second_root)

    first = scan_evidence_root(root=first_root, profile="peoc-server")
    second = scan_evidence_root(root=second_root, profile="peoc-server")

    assert first["snapshot_sha256"] == second["snapshot_sha256"]


def test_import_rejects_tampered_manifest_identity(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    _write_server_fixture(root)
    manifest = scan_evidence_root(root=root, profile="peoc-server")
    manifest["sources"][0]["role"] = "tampered-role"
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="snapshot_sha256"):
        import_evidence_manifest(
            EvidenceImportOptions(manifest_path=manifest_path, out_dir=tmp_path / "run")
        )


def test_legacy_evidence_overwrite_refuses_current_or_unowned_output(
    tmp_path: Path,
) -> None:
    root = tmp_path / "projects"
    _write_server_fixture(root)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(scan_evidence_root(root=root, profile="peoc-server")),
        encoding="utf-8",
    )
    out_dir = tmp_path / "user-owned"
    out_dir.mkdir()
    marker = out_dir / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="not a PromptControlLab evidence run"):
        import_evidence_manifest(
            EvidenceImportOptions(
                manifest_path=manifest_path,
                out_dir=out_dir,
                overwrite=True,
            )
        )

    assert marker.read_text(encoding="utf-8") == "keep"


def test_evidence_scan_cli_rejects_writing_inside_the_source_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "projects"
    _write_server_fixture(root)

    result = main(
        [
            "evidence",
            "scan",
            "--root",
            str(root),
            "--profile",
            "peoc-server",
            "--out",
            str(root / "manifest.json"),
        ]
    )

    assert result == 2
    assert not (root / "manifest.json").exists()


def test_import_evidence_manifest_builds_interpretability_outputs_without_copying_pt(
    tmp_path: Path,
) -> None:
    root = tmp_path / "projects"
    _write_server_fixture(root)
    manifest_path = tmp_path / "server_evidence_manifest.json"
    manifest_path.write_text(
        json.dumps(scan_evidence_root(root=root, profile="peoc-server")), encoding="utf-8"
    )

    out_dir = tmp_path / "run"
    result = import_evidence_manifest(
        EvidenceImportOptions(manifest_path=manifest_path, out_dir=out_dir, portable=True)
    )

    assert result["output_dir"] == str(out_dir.resolve())
    matrix = read_json(out_dir / "evidence_matrix.json")
    assert matrix["status_counts"]["observed"] >= 1
    assert matrix["status_counts"]["inconclusive"] >= 1
    assert {row["adapter"] for row in matrix["diagnostics"]} == {
        "agent_episode",
        "deployment_gate",
        "generation_aware",
        "riccati_ass_hyp",
        "selective_risk",
        "soft_hard_tv",
        "turnpike_a800",
    }

    report = read_json(out_dir / "interpretability_report.json")
    assert all(
        {
            "interpretation_role",
            "observation",
            "explanation",
            "confidence",
            "scope",
            "claim_boundary",
            "next_action",
        }
        <= set(entry)
        for entry in report["findings"]
    )
    deployment = next(
        entry for entry in report["findings"] if entry["adapter"] == "deployment_gate"
    )
    assert deployment["raw_status"] == "CONFIRMATORY_FAIL_CLOSED"
    assert deployment["interpretation_role"] == "decision"
    assert "negative" not in deployment["explanation"].lower()

    claim = read_json(out_dir / "claim_check.json")
    assert claim["universal_improvement_supported"] is False
    assert claim["mechanism_interpretation_available"] is True
    private_manifest = read_json(out_dir / "source_manifest.json")
    public_manifest = read_json(out_dir / "public_source_manifest.json")
    assert private_manifest["classification"] == "private_local"
    assert public_manifest["classification"] == "public_derived"
    assert "root" not in public_manifest
    assert all(
        "relative_path" not in row and "resolved_path" not in row
        for row in public_manifest["sources"]
    )
    portable_dir = out_dir / "portable"
    assert {path.name for path in portable_dir.iterdir()} == {
        "claim_check.json",
        "evidence_matrix.json",
        "interpretability_report.html",
        "interpretability_report.json",
        "public_source_manifest.json",
    }
    portable_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in portable_dir.iterdir()
        if path.suffix in {".json", ".html"}
    )
    assert str(root.resolve()) not in portable_text
    assert not (out_dir / "sources").exists()
    assert (out_dir / "interpretability_report.html").is_file()

    soft_hard = next(entry for entry in report["findings"] if entry["adapter"] == "soft_hard_tv")
    raw_statistics = soft_hard["raw_statistics"]
    assert any(row["field"] == "p_value" and row["value"] == 0.2 for row in raw_statistics)
    assert any(row["field"] == "ci" and row["value"] == [-0.01, 0.03] for row in raw_statistics)
    assert all("source_sha256" in row and "source_path" not in row for row in raw_statistics)


def test_import_rejects_preexisting_portable_symlink(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    _write_server_fixture(root)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(scan_evidence_root(root=root, profile="peoc-server")), encoding="utf-8"
    )
    out_dir = tmp_path / "run"
    out_dir.mkdir()
    target = tmp_path / "outside"
    target.mkdir()
    try:
        (out_dir / "portable").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks are not available in this Windows environment")

    with pytest.raises(ValueError, match="symbolic link"):
        import_evidence_manifest(
            EvidenceImportOptions(
                manifest_path=manifest_path,
                out_dir=out_dir,
                portable=True,
            )
        )


def test_evidence_cli_scan_and_import(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    root = tmp_path / "projects"
    _write_server_fixture(root)
    manifest_path = tmp_path / "manifest.json"
    out_dir = tmp_path / "run"

    assert (
        main(
            [
                "evidence",
                "scan",
                "--root",
                str(root),
                "--profile",
                "peoc-server",
                "--out",
                str(manifest_path),
            ]
        )
        == 0
    )
    assert (
        main(["evidence", "import", "--manifest", str(manifest_path), "--out", str(out_dir)]) == 0
    )
    assert manifest_path.is_file()
    assert (out_dir / "evidence_matrix.json").is_file()
    output = capsys.readouterr().out
    assert '"source_count"' in output
    assert '"snapshot_sha256"' in output
    assert '"sources"' not in output


def test_public_server_case_is_derived_and_path_free() -> None:
    case_root = Path("docs/case_studies/server_evidence")
    matrix = read_json(case_root / "evidence_matrix.json")
    report = read_json(case_root / "interpretability_report.json")
    claim = read_json(case_root / "claim_check.json")
    pilot = read_json(case_root / "sft_pilot_status.json")

    assert matrix["snapshot_sha256"].startswith("sha256:")
    assert sum(int(row["source_count"]) for row in matrix["diagnostics"]) == 911
    assert len(report["findings"]) == 7
    assert all("source_paths" not in finding for finding in report["findings"])
    serialized = json.dumps([matrix, report, claim], ensure_ascii=False)
    assert "/root/" not in serialized
    assert claim["universal_improvement_supported"] is False
    assert pilot["execution_status"] == "complete"
    assert pilot["gpu_work_started"] is True
    assert pilot["checkpoint_runs"] == 9
    assert pilot["gate_count"] == 6
    assert pilot["decision"] == "hold"


def test_evidence_import_normalizes_non_finite_metrics_to_null(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    _write_server_fixture(root)
    selective = root / "experiments/p4_selective_risk_seed_holdout/p4_selective_risk_report.json"
    _write_json(
        selective,
        {
            "status": "SELECTIVE_RISK_PASS",
            "n_seed_rows": 1,
            "observed_aurc": float("nan"),
            "random_mean_aurc": float("inf"),
        },
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(scan_evidence_root(root=root, profile="peoc-server")), encoding="utf-8"
    )

    import_evidence_manifest(
        EvidenceImportOptions(manifest_path=manifest_path, out_dir=tmp_path / "run")
    )

    report_path = tmp_path / "run/interpretability_report.json"
    assert "NaN" not in report_path.read_text(encoding="utf-8")
    assert "Infinity" not in report_path.read_text(encoding="utf-8")
    report = read_json(report_path)
    finding = next(row for row in report["findings"] if row["adapter"] == "selective_risk")
    assert finding["metrics"]["observed_aurc"] is None
    assert finding["metrics"]["random_mean_aurc"] is None


def test_invalid_adapter_payload_requires_reanalysis(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    _write_server_fixture(root)
    _write_json(
        root
        / "experiments/p0_control_to_deployment/production_v2/audit/P0_CONFIRMATORY_ANALYSIS.json",
        {"interpretation": "CONFIRMATORY_PASS"},
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(scan_evidence_root(root=root, profile="peoc-server")), encoding="utf-8"
    )

    import_evidence_manifest(
        EvidenceImportOptions(manifest_path=manifest_path, out_dir=tmp_path / "run")
    )

    report = read_json(tmp_path / "run/interpretability_report.json")
    finding = next(row for row in report["findings"] if row["adapter"] == "deployment_gate")
    assert finding["support_status"] == "requires_reanalysis"
    assert finding["confidence"] == "low"
    assert finding["metrics"]["invalid_source_count"] >= 1


@pytest.mark.parametrize(
    ("relative_path", "payload", "adapter"),
    [
        (
            "experiments/p0_control_to_deployment/production_v2/audit/"
            "P0_CONFIRMATORY_ANALYSIS.json",
            {
                "interpretation": "CONFIRMATORY_PASS",
                "n_rows": -1,
                "all_validity_gates_passed": True,
            },
            "deployment_gate",
        ),
        (
            "experiments/p4_selective_risk_seed_holdout/p4_selective_risk_report.json",
            {
                "status": "SELECTIVE_RISK_PASS",
                "n_seed_rows": 10,
                "observed_aurc": -3.0,
                "random_mean_aurc": 2.0,
            },
            "selective_risk",
        ),
        (
            "theory/results/ass_hyp_verify_stationary_qwen_s0.json",
            {"ASS_HYP_via_DARE": ["not-a-record"]},
            "riccati_ass_hyp",
        ),
    ],
)
def test_semantically_impossible_adapter_payload_requires_reanalysis(
    tmp_path: Path,
    relative_path: str,
    payload: object,
    adapter: str,
) -> None:
    root = tmp_path / "projects"
    _write_server_fixture(root)
    _write_json(root / relative_path, payload)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(scan_evidence_root(root=root, profile="peoc-server")), encoding="utf-8"
    )

    import_evidence_manifest(
        EvidenceImportOptions(manifest_path=manifest_path, out_dir=tmp_path / "run")
    )

    report = read_json(tmp_path / "run/interpretability_report.json")
    finding = next(row for row in report["findings"] if row["adapter"] == adapter)
    assert finding["support_status"] == "requires_reanalysis"
    assert finding["metrics"]["invalid_source_count"] >= 1
