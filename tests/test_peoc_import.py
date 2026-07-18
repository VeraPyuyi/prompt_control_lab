from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, NoReturn

import pytest

import promptcontrollab.peoc_import as peoc_import_module
from promptcontrollab.files import JsonDict, read_json
from promptcontrollab.peoc_import import (
    HARD_SUMMARY,
    PeocImportOptions,
    PeocSourceOverrides,
    build_peoc_evidence,
    discover_peoc_sources,
    import_peoc_bundle,
)
from promptcontrollab.peoc_reporting import (
    render_peoc_case_study_html,
    render_peoc_case_study_markdown,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _recovery_files_with_content(out_dir: Path, content: str) -> list[Path]:
    recovery_root = out_dir / ".peoc-recovery"
    if not recovery_root.is_dir():
        return []
    return [
        path
        for path in recovery_root.rglob("*")
        if path.is_file() and path.read_text(encoding="utf-8") == content
    ]


def _write_minimal_bundle(root: Path) -> None:
    (root / "README_MANIFEST.md").parent.mkdir(parents=True, exist_ok=True)
    (root / "README_MANIFEST.md").write_text("# PEOC evidence bundle\n", encoding="utf-8")

    results_root = (
        root / "experiments" / "redesign_v2" / "results_server_pull_20260524" / "strong_main_grid"
    )
    _write_json(
        results_root / "summary_acc_hard_test.json",
        {
            "metric": "acc_hard_test",
            "summary": [
                {
                    "model": "Qwen/Qwen2.5-7B-Instruct",
                    "task": "bbh3",
                    "T": 8,
                    "L0": 4,
                    "budget": 128,
                    "method": "pez",
                    "metric": "acc_hard_test",
                    "mean": 0.6,
                    "sd": 0.04,
                    "n": 10,
                },
                {
                    "model": "Qwen/Qwen2.5-7B-Instruct",
                    "task": "bbh3",
                    "T": 8,
                    "L0": 4,
                    "budget": 128,
                    "method": "tv_pmp",
                    "metric": "acc_hard_test",
                    "mean": 0.69,
                    "sd": 0.05,
                    "n": 10,
                },
                {
                    "model": "Qwen/Qwen2.5-7B-Instruct",
                    "task": "gsm8k",
                    "T": 8,
                    "L0": 4,
                    "budget": 128,
                    "method": "tv_pmp",
                    "metric": "acc_hard_test",
                    "mean": float("nan"),
                    "sd": float("nan"),
                    "n": 0,
                },
            ],
            "tests": [
                {
                    "model": "Qwen/Qwen2.5-7B-Instruct",
                    "task": "bbh3",
                    "contrast": "tv_pmp-pez",
                    "mean_diff": 0.09,
                    "n_pairs": 10,
                    "p": 0.01,
                    "p_holm": 0.03,
                }
            ],
        },
    )
    _write_json(
        results_root / "summary_soft_segmented.json",
        {
            "metric": "acc_soft_segmented_test",
            "summary": [
                {
                    "model": "Qwen/Qwen2.5-7B-Instruct",
                    "task": "bbh3",
                    "method": "pez",
                    "metric": "acc_soft_segmented_test",
                    "mean": float("nan"),
                    "sd": float("nan"),
                    "n": 0,
                },
                {
                    "model": "Qwen/Qwen2.5-7B-Instruct",
                    "task": "bbh3",
                    "method": "tv_pmp",
                    "metric": "acc_soft_segmented_test",
                    "mean": float("nan"),
                    "sd": float("nan"),
                    "n": 0,
                },
            ],
            "tests": [],
        },
    )
    _write_json(
        root / "experiments" / "redesign_v2" / "stage_heterogeneity" / "shi_r27_summary.json",
        {
            "round": 27,
            "variant": "shi_model_normalized",
            "held_spearman_rho": -0.54,
            "held_bootstrap_ci": [-1.0, 0.64],
            "verdict": "FAIL",
            "cells": [
                {
                    "key": "Qwen/Qwen2.5-7B-Instruct__gsm8k",
                    "model": "Qwen/Qwen2.5-7B-Instruct",
                    "task": "gsm8k",
                    "split": "held",
                    "delta_tv_static_mean": -0.004,
                }
            ],
        },
    )

    trajectory_root = root / "experiments" / "turnpike_trace" / "results_a800"
    stationary = trajectory_root / "stationary_arith_Qwen2.5-7B-Instruct_s0.json"
    heterogeneous = trajectory_root / "turnpike_gsm8k_Qwen2.5-7B-Instruct_s0.json"
    _write_json(
        stationary,
        {
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "n_streams": 16,
            "n_subtasks": 48,
            "K_min": 48,
            "hidden_dim": 3584,
            "alpha_emp_mean": 0.0247,
            "alpha_emp_std": 0.0071,
            "R2_mean": 0.602,
            "R2_std": 0.155,
            "per_stream_alphas": [0.025, 0.022],
            "per_stream_R2": [0.78, 0.55],
        },
    )
    _write_json(
        heterogeneous,
        {
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "task": "gsm8k",
            "n_prompts": 32,
            "max_steps": 96,
            "min_T": 96,
            "hidden_dim": 3584,
            "alpha_emp_mean": 0.00174,
            "alpha_emp_std": 0.0019,
            "R2_mean": 0.088,
            "R2_std": 0.127,
            "alpha_theory_upper_bound": float("nan"),
            "per_prompt_alphas": [0.0018, 0.0015],
            "per_prompt_R2": [0.077, 0.09],
        },
    )
    stationary.with_suffix(".npz").write_bytes(b"stationary-npz")
    heterogeneous.with_suffix(".npz").write_bytes(b"heterogeneous-npz")


def test_discover_peoc_sources_records_stable_provenance(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    _write_minimal_bundle(bundle_root)

    manifest = discover_peoc_sources(bundle_root, PeocSourceOverrides())

    assert manifest["schema"] == "prompt_control_lab.peoc_source_manifest.v1"
    bundle = manifest["bundle"]
    manifest_path = bundle_root / "README_MANIFEST.md"
    manifest_digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    assert bundle == {
        "resolved_path": str(bundle_root.resolve()),
        "manifest_relative_path": "README_MANIFEST.md",
        "manifest_sha256": f"sha256:{manifest_digest}",
    }

    sources = manifest["sources"]
    assert [row["role"] for row in sources] == [
        "bundle_manifest",
        "hard_test_summary",
        "soft_segmented_summary",
        "stage_heterogeneity",
        "trajectory_stationary",
        "trajectory_heterogeneous",
        "trajectory_binary",
        "trajectory_binary",
    ]
    assert all(
        set(row)
        == {
            "role",
            "relative_path",
            "resolved_path",
            "bytes",
            "sha256",
            "media_type",
            "selection",
            "copied_path",
        }
        for row in sources
    )
    assert all("\\" not in row["relative_path"] for row in sources)
    assert all(row["copied_path"] is None for row in sources)
    assert all(
        row["sha256"]
        == f"sha256:{hashlib.sha256(Path(row['resolved_path']).read_bytes()).hexdigest()}"
        for row in sources
    )
    assert manifest["warnings"] == []


def test_discover_peoc_sources_requires_bundle_manifest(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    _write_minimal_bundle(bundle_root)
    (bundle_root / "README_MANIFEST.md").unlink()

    with pytest.raises(ValueError, match=r"README_MANIFEST\.md"):
        discover_peoc_sources(bundle_root, PeocSourceOverrides())


def test_discover_peoc_sources_requires_hard_test_summary(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    _write_minimal_bundle(bundle_root)
    (bundle_root / HARD_SUMMARY).unlink()

    with pytest.raises(ValueError, match="hard-test summary"):
        discover_peoc_sources(bundle_root, PeocSourceOverrides())


def _build_fixture_evidence(bundle_root: Path) -> JsonDict:
    manifest = discover_peoc_sources(bundle_root, PeocSourceOverrides())
    return build_peoc_evidence(bundle_root, manifest)


def _contains_non_finite(value: object) -> bool:
    if isinstance(value, float):
        return value != value or value in {float("inf"), float("-inf")}
    if isinstance(value, dict):
        return any(_contains_non_finite(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_non_finite(item) for item in value)
    return False


def _reject_non_standard_json_constant(value: str) -> NoReturn:
    raise AssertionError(f"Strict JSON artifact contains non-standard constant {value}")


def test_build_peoc_evidence_preserves_real_negative_and_unavailable_results(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    _write_minimal_bundle(bundle_root)

    evidence = _build_fixture_evidence(bundle_root)

    assert evidence["schema"] == "prompt_control_lab.peoc_evidence.v1"
    sections = evidence["sections"]
    assert sections["hard_evaluation"]["origin"] == "real"
    assert sections["hard_evaluation"]["status"] == "available"
    assert sections["soft_evaluation"]["origin"] == "real"
    assert sections["soft_evaluation"]["status"] == "unusable"
    assert sections["stage_heterogeneity"]["origin"] == "real"
    assert sections["stage_heterogeneity"]["status"] == "failed_validation"
    assert sections["stage_heterogeneity"]["observations"]["verdict"] == "FAIL"
    assert sections["riccati"]["origin"] == "none"
    assert sections["riccati"]["status"] == "missing"
    assert sections["soft_hard"]["origin"] == "none"
    assert sections["soft_hard"]["status"] == "missing"
    assert evidence["claim_boundary"]["full_research_support"] is False

    for section in sections.values():
        assert {
            "origin",
            "status",
            "display_status",
            "source_roles",
            "observations",
            "limitations",
        } <= set(section)


def test_build_peoc_evidence_normalizes_non_finite_values_and_warns(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    _write_minimal_bundle(bundle_root)

    evidence = _build_fixture_evidence(bundle_root)

    assert not _contains_non_finite(evidence)
    warnings = evidence["warnings"]
    assert any(warning["code"] == "non_finite_value" for warning in warnings)
    soft_rows = evidence["sections"]["soft_evaluation"]["observations"]["rows"]
    assert soft_rows[0]["mean"] is None
    trajectory = evidence["sections"]["trajectory"]["observations"]
    heterogeneous = trajectory["headline_pair"]["heterogeneous"]["summary"]
    assert heterogeneous["alpha_theory_upper_bound"] is None


def test_build_peoc_evidence_normalizes_non_finite_source_metadata(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    _write_minimal_bundle(bundle_root)
    manifest = discover_peoc_sources(bundle_root, PeocSourceOverrides())
    hard_source = next(
        source for source in manifest["sources"] if source["role"] == "hard_test_summary"
    )
    hard_source["bytes"] = float("inf")

    evidence = build_peoc_evidence(bundle_root, manifest)

    json.dumps(evidence, allow_nan=False)
    hard_reference = evidence["sections"]["hard_evaluation"]["observations"]["source"]
    assert hard_reference["bytes"] is None
    assert any(
        warning["code"] == "non_finite_value"
        and warning["json_path"].endswith(".bytes")
        for warning in evidence["warnings"]
    )


def test_build_peoc_evidence_requires_bundle_manifest_source_row(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    _write_minimal_bundle(bundle_root)
    manifest = discover_peoc_sources(bundle_root, PeocSourceOverrides())
    manifest["sources"] = [
        source for source in manifest["sources"] if source["role"] != "bundle_manifest"
    ]

    with pytest.raises(ValueError, match=r"bundle manifest source"):
        build_peoc_evidence(bundle_root, manifest)


def test_build_peoc_evidence_rejects_missing_bundle_manifest_file(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    _write_minimal_bundle(bundle_root)
    manifest = discover_peoc_sources(bundle_root, PeocSourceOverrides())
    (bundle_root / "README_MANIFEST.md").unlink()

    with pytest.raises(
        ValueError,
        match=r"bundle manifest source changed after discovery",
    ):
        build_peoc_evidence(bundle_root, manifest)


def test_build_peoc_evidence_rejects_same_length_bundle_manifest_tamper(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    _write_minimal_bundle(bundle_root)
    manifest = discover_peoc_sources(bundle_root, PeocSourceOverrides())
    manifest_path = bundle_root / "README_MANIFEST.md"
    original = manifest_path.read_bytes()
    tampered = original.replace(b"PEOC", b"XEOC", 1)
    assert tampered != original
    assert len(tampered) == len(original)
    manifest_path.write_bytes(tampered)

    with pytest.raises(
        ValueError,
        match=r"bundle manifest source changed after discovery.*sha256",
    ):
        build_peoc_evidence(bundle_root, manifest)


def test_build_peoc_evidence_rejects_stale_bundle_level_manifest_hash(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    _write_minimal_bundle(bundle_root)
    manifest = discover_peoc_sources(bundle_root, PeocSourceOverrides())
    manifest["bundle"]["manifest_sha256"] = "sha256:" + ("0" * 64)

    with pytest.raises(ValueError, match=r"bundle manifest hash changed after discovery"):
        build_peoc_evidence(bundle_root, manifest)


def test_build_peoc_evidence_rejects_same_length_required_hard_tamper(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    _write_minimal_bundle(bundle_root)
    manifest = discover_peoc_sources(bundle_root, PeocSourceOverrides())
    hard_path = bundle_root / HARD_SUMMARY
    original = hard_path.read_bytes()
    tampered = original.replace(b'"mean": 0.6', b'"mean": 0.7', 1)
    assert tampered != original
    assert len(tampered) == len(original)
    hard_path.write_bytes(tampered)

    with pytest.raises(
        ValueError,
        match=r"hard-test summary source changed after discovery.*sha256",
    ):
        build_peoc_evidence(bundle_root, manifest)


def test_build_peoc_evidence_retains_changed_optional_json_as_unusable(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    _write_minimal_bundle(bundle_root)
    manifest = discover_peoc_sources(bundle_root, PeocSourceOverrides())
    soft_path = (
        bundle_root
        / "experiments"
        / "redesign_v2"
        / "results_server_pull_20260524"
        / "strong_main_grid"
        / "summary_soft_segmented.json"
    )
    soft_path.write_text(soft_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    evidence = build_peoc_evidence(bundle_root, manifest)

    soft = evidence["sections"]["soft_evaluation"]
    assert soft["origin"] == "real"
    assert soft["status"] == "unusable"
    assert "source changed after discovery" in soft["observations"]["error"]
    assert any(
        warning["code"] == "source_integrity_mismatch"
        and warning["source_role"] == "soft_segmented_summary"
        for warning in evidence["warnings"]
    )


def test_build_peoc_evidence_retains_malformed_optional_source_as_unusable(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    _write_minimal_bundle(bundle_root)
    soft_path = (
        bundle_root
        / "experiments"
        / "redesign_v2"
        / "results_server_pull_20260524"
        / "strong_main_grid"
        / "summary_soft_segmented.json"
    )
    soft_path.write_text("{not-json", encoding="utf-8")

    evidence = _build_fixture_evidence(bundle_root)

    soft = evidence["sections"]["soft_evaluation"]
    assert soft["origin"] == "real"
    assert soft["status"] == "unusable"
    assert soft["source_roles"] == ["soft_segmented_summary"]
    assert soft["observations"]["source"]["relative_path"].endswith(
        "summary_soft_segmented.json"
    )
    assert any(
        warning["code"] == "invalid_optional_source"
        and warning["source_role"] == "soft_segmented_summary"
        for warning in evidence["warnings"]
    )


def test_build_peoc_evidence_retains_malformed_stage_source_as_unusable(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    _write_minimal_bundle(bundle_root)
    stage_path = (
        bundle_root
        / "experiments"
        / "redesign_v2"
        / "stage_heterogeneity"
        / "shi_r27_summary.json"
    )
    stage_path.write_text("{not-json", encoding="utf-8")

    evidence = _build_fixture_evidence(bundle_root)

    stage = evidence["sections"]["stage_heterogeneity"]
    assert stage["origin"] == "real"
    assert stage["status"] == "unusable"
    assert stage["source_roles"] == ["stage_heterogeneity"]
    assert any(
        warning["code"] == "invalid_optional_source"
        and warning["source_role"] == "stage_heterogeneity"
        for warning in evidence["warnings"]
    )


def test_build_peoc_evidence_retains_malformed_trajectory_source_as_unusable(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    _write_minimal_bundle(bundle_root)
    stationary_path = (
        bundle_root
        / "experiments"
        / "turnpike_trace"
        / "results_a800"
        / "stationary_arith_Qwen2.5-7B-Instruct_s0.json"
    )
    stationary_path.write_text("{not-json", encoding="utf-8")

    evidence = _build_fixture_evidence(bundle_root)

    trajectory = evidence["sections"]["trajectory"]
    assert trajectory["origin"] == "real"
    assert trajectory["status"] == "unusable"
    invalid_entries = [
        entry
        for entry in trajectory["observations"]["entries"]
        if entry["status"] == "unusable"
    ]
    assert len(invalid_entries) == 1
    assert invalid_entries[0]["role"] == "trajectory_stationary"
    assert any(
        warning["code"] == "invalid_optional_source"
        and warning["source_role"] == "trajectory_stationary"
        for warning in evidence["warnings"]
    )


def test_build_peoc_evidence_marks_mixed_valid_and_invalid_trajectory_partial(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    _write_minimal_bundle(bundle_root)
    malformed = (
        bundle_root
        / "experiments"
        / "turnpike_trace"
        / "results_a800"
        / "stationary_arith_Mistral-7B-Instruct_s1.json"
    )
    malformed.write_text("{not-json", encoding="utf-8")

    evidence = _build_fixture_evidence(bundle_root)

    trajectory = evidence["sections"]["trajectory"]
    assert trajectory["status"] == "partial"
    assert trajectory["observations"]["headline_pair"]["seed"] == 0
    assert any(
        entry["status"] == "unusable"
        and entry["source"]["relative_path"].endswith(
            "stationary_arith_Mistral-7B-Instruct_s1.json"
        )
        for entry in trajectory["observations"]["entries"]
    )


def test_build_peoc_evidence_excludes_same_length_tampered_binary_reference(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    _write_minimal_bundle(bundle_root)
    manifest = discover_peoc_sources(bundle_root, PeocSourceOverrides())
    binary_path = (
        bundle_root
        / "experiments"
        / "turnpike_trace"
        / "results_a800"
        / "stationary_arith_Qwen2.5-7B-Instruct_s0.npz"
    )
    original = binary_path.read_bytes()
    tampered = bytes([original[0] ^ 1, *original[1:]])
    assert tampered != original
    assert len(tampered) == len(original)
    binary_path.write_bytes(tampered)

    evidence = build_peoc_evidence(bundle_root, manifest)

    trajectory = evidence["sections"]["trajectory"]
    assert trajectory["status"] == "partial"
    stationary = trajectory["observations"]["headline_pair"]["stationary"]
    assert stationary["binary_references"] == []
    assert len(stationary["invalid_binary_references"]) == 1
    invalid_binary = stationary["invalid_binary_references"][0]
    assert invalid_binary["origin"] == "real"
    assert invalid_binary["status"] == "unusable"
    assert any(
        warning["code"] == "source_integrity_mismatch"
        and warning["source_role"] == "trajectory_binary"
        for warning in evidence["warnings"]
    )


def test_build_peoc_evidence_pairs_trajectories_and_infers_filename_seed(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    _write_minimal_bundle(bundle_root)

    evidence = _build_fixture_evidence(bundle_root)

    trajectory = evidence["sections"]["trajectory"]
    assert trajectory["status"] == "available"
    headline = trajectory["observations"]["headline_pair"]
    assert headline["model"] == "Qwen/Qwen2.5-7B-Instruct"
    assert headline["seed"] == 0
    assert headline["stationary"]["seed_source"] == "filename"
    assert headline["heterogeneous"]["seed_source"] == "filename"
    assert len(headline["stationary"]["binary_references"]) == 1
    assert len(headline["heterogeneous"]["binary_references"]) == 1
    assert headline["stationary"]["binary_references"][0]["sha256"].startswith("sha256:")


def test_build_peoc_evidence_retains_zero_count_hard_row_as_excluded(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    _write_minimal_bundle(bundle_root)

    evidence = _build_fixture_evidence(bundle_root)

    hard = evidence["sections"]["hard_evaluation"]["observations"]
    assert hard["valid_row_count"] == 2
    assert hard["excluded_row_count"] == 1
    assert hard["excluded_rows"][0]["reason"] == "non_positive_n"
    assert hard["excluded_rows"][0]["row"]["n"] == 0


def test_build_peoc_evidence_accepts_very_large_positive_sample_count(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    _write_minimal_bundle(bundle_root)
    hard_path = bundle_root / HARD_SUMMARY
    hard_payload = json.loads(hard_path.read_text(encoding="utf-8"))
    huge_n = 10**400
    hard_payload["summary"].append(
        {
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "task": "svamp",
            "method": "static_autograd",
            "metric": "acc_hard_test",
            "mean": 0.5,
            "sd": 0.01,
            "n": huge_n,
        }
    )
    _write_json(hard_path, hard_payload)

    evidence = _build_fixture_evidence(bundle_root)

    hard = evidence["sections"]["hard_evaluation"]["observations"]
    assert hard["valid_row_count"] == 3
    assert any(row["n"] == huge_n for row in hard["rows"])


def test_build_peoc_evidence_rejects_malformed_required_hard_summary(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    _write_minimal_bundle(bundle_root)
    _write_json(bundle_root / HARD_SUMMARY, {"metric": "acc_hard_test"})
    manifest = discover_peoc_sources(bundle_root, PeocSourceOverrides())

    with pytest.raises(ValueError, match=r"hard-test summary.*summary"):
        build_peoc_evidence(bundle_root, manifest)


def test_import_peoc_bundle_writes_strict_self_contained_case_study(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    out_dir = tmp_path / "run"
    _write_minimal_bundle(bundle_root)

    result = import_peoc_bundle(
        PeocImportOptions(
            bundle_root=bundle_root,
            out_dir=out_dir,
            language="en",
        )
    )

    artifact_names = [
        "manifest.json",
        "source_manifest.json",
        "peoc_evidence.json",
        "research_case_study.json",
        "research_case_study.md",
        "research_case_study.html",
    ]
    assert result["kind"] == "peoc_research_import"
    assert result["status_counts"] == {
        "available": 2,
        "failed_validation": 1,
        "missing": 2,
        "partial": 0,
        "unusable": 1,
    }
    assert result["claim_boundary"]["full_research_support"] is False
    assert sorted(result["artifacts"]) == sorted(artifact_names)
    assert all((out_dir / name).is_file() for name in artifact_names)

    for name in artifact_names[:4]:
        text = (out_dir / name).read_text(encoding="utf-8")
        assert text.endswith("\n")
        json.loads(
            text,
            parse_constant=_reject_non_standard_json_constant,
        )

    manifest = read_json(out_dir / "manifest.json")
    assert manifest["tool"] == "prompt_control_lab"
    assert manifest["mode"] == "research_import"
    assert manifest["adapter"] == "peoc"
    assert manifest["language"] == "en"
    case_study = read_json(out_dir / "research_case_study.json")
    assert case_study["evidence_source"] == "REAL PEOC BUNDLE"
    assert case_study["stage_validation"]["verdict"] == "FAIL"
    assert case_study["claim_boundary"]["full_research_support"] is False
    assert all(
        set(source) == {"bytes", "relative_path", "role", "sha256"}
        for source in case_study["source_inventory"]
    )

    bundle_path = str(bundle_root.resolve())
    case_json = (out_dir / "research_case_study.json").read_text(encoding="utf-8")
    case_markdown = (out_dir / "research_case_study.md").read_text(encoding="utf-8")
    case_html = (out_dir / "research_case_study.html").read_text(encoding="utf-8")
    assert bundle_path not in case_json
    assert bundle_path not in case_markdown
    assert bundle_path not in case_html
    assert "FAILED_VALIDATION" in case_html
    assert "UNUSABLE" in case_html


def test_import_requires_overwrite_and_preserves_unrelated_files(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    out_dir = tmp_path / "run"
    _write_minimal_bundle(bundle_root)
    import_peoc_bundle(PeocImportOptions(bundle_root=bundle_root, out_dir=out_dir))
    unrelated = out_dir / "notes.txt"
    unrelated.write_text("keep me", encoding="utf-8")

    with pytest.raises(ValueError, match="--overwrite"):
        import_peoc_bundle(PeocImportOptions(bundle_root=bundle_root, out_dir=out_dir))

    result = import_peoc_bundle(
        PeocImportOptions(
            bundle_root=bundle_root,
            out_dir=out_dir,
            overwrite=True,
        )
    )

    assert result["kind"] == "peoc_research_import"
    assert unrelated.read_text(encoding="utf-8") == "keep me"


def test_import_failure_does_not_replace_existing_artifacts_or_copy_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_root = tmp_path / "bundle"
    out_dir = tmp_path / "run"
    _write_minimal_bundle(bundle_root)
    import_peoc_bundle(PeocImportOptions(bundle_root=bundle_root, out_dir=out_dir))
    original_artifacts = {
        path.name: path.read_bytes()
        for path in out_dir.iterdir()
        if path.is_file()
    }

    hard_path = bundle_root / HARD_SUMMARY
    hard_payload = read_json(hard_path)
    hard_payload["summary"][0]["mean"] = 0.11
    _write_json(hard_path, hard_payload)
    original_writer = peoc_import_module._write_strict_json

    def fail_during_staged_write(path: Path, payload: JsonDict) -> None:
        if path.name == "peoc_evidence.json":
            raise OSError("simulated write failure")
        original_writer(path, payload)

    monkeypatch.setattr(
        peoc_import_module,
        "_write_strict_json",
        fail_during_staged_write,
    )

    with pytest.raises(OSError, match="simulated write failure"):
        import_peoc_bundle(
            PeocImportOptions(
                bundle_root=bundle_root,
                out_dir=out_dir,
                portable=True,
                overwrite=True,
            )
        )

    assert {
        path.name: path.read_bytes()
        for path in out_dir.iterdir()
        if path.is_file()
    } == original_artifacts
    assert not (out_dir / "source").exists()


def test_import_commit_failure_removes_new_output_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_root = tmp_path / "bundle"
    out_dir = tmp_path / "run"
    _write_minimal_bundle(bundle_root)

    def fail_on_portable_destination(
        source: Path,
        destination: Path,
        source_identity: Any,
    ) -> NoReturn:
        raise OSError("simulated commit failure")

    monkeypatch.setattr(
        peoc_import_module,
        "_publish_new_portable",
        fail_on_portable_destination,
    )

    with pytest.raises(OSError, match="simulated commit failure"):
        import_peoc_bundle(
            PeocImportOptions(
                bundle_root=bundle_root,
                out_dir=out_dir,
                portable=True,
            )
        )

    assert not out_dir.exists()


def test_portable_import_copies_small_json_and_csv_but_never_npz(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_root = tmp_path / "bundle"
    out_dir = tmp_path / "portable"
    _write_minimal_bundle(bundle_root)
    csv_path = bundle_root / "tables" / "paired_results.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_text("method,score\npez,0.6\n", encoding="utf-8")
    original_discover = discover_peoc_sources

    def discover_with_csv(
        root: Path,
        overrides: PeocSourceOverrides,
    ) -> JsonDict:
        manifest = original_discover(root, overrides)
        payload = csv_path.read_bytes()
        manifest["sources"].append(
            {
                "role": "supporting_csv",
                "relative_path": "tables/paired_results.csv",
                "resolved_path": str(csv_path.resolve()),
                "bytes": len(payload),
                "sha256": f"sha256:{hashlib.sha256(payload).hexdigest()}",
                "media_type": "text/csv",
                "selection": "test",
                "copied_path": None,
            }
        )
        return manifest

    monkeypatch.setattr(
        peoc_import_module,
        "discover_peoc_sources",
        discover_with_csv,
    )

    import_peoc_bundle(
        PeocImportOptions(
            bundle_root=bundle_root,
            out_dir=out_dir,
            portable=True,
        )
    )

    manifest = read_json(out_dir / "source_manifest.json")
    source_root = out_dir / "source"
    assert any(source_root.rglob("*.json"))
    assert any(source_root.rglob("*.csv"))
    assert not any(source_root.rglob("*.npz"))
    binary_rows = [
        row for row in manifest["sources"] if row["role"] == "trajectory_binary"
    ]
    assert len(binary_rows) == 2
    assert all(row["copied_path"] is None for row in binary_rows)
    assert all(
        row.get("copied_path") is None
        or (
            str(row["copied_path"]).startswith("source/")
            and "\\" not in str(row["copied_path"])
        )
        for row in manifest["sources"]
    )
    assert any(
        row["role"] == "supporting_csv"
        and row["copied_path"] == "source/tables/paired_results.csv"
        for row in manifest["sources"]
    )
    assert any(
        row["role"] == "trajectory_binary"
        and row["sha256"].startswith("sha256:")
        for row in manifest["sources"]
    )


def test_portable_import_falls_back_when_hard_links_are_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_root = tmp_path / "bundle"
    out_dir = tmp_path / "portable"
    _write_minimal_bundle(bundle_root)

    def hard_links_unavailable(source: Path, destination: Path) -> None:
        raise OSError("hard links are unavailable")

    monkeypatch.setattr(os, "link", hard_links_unavailable)

    import_peoc_bundle(
        PeocImportOptions(
            bundle_root=bundle_root,
            out_dir=out_dir,
            portable=True,
        )
    )

    copied_hard = out_dir / "source" / HARD_SUMMARY
    assert copied_hard.read_bytes() == (bundle_root / HARD_SUMMARY).read_bytes()


def test_portable_overwrite_rejects_unregistered_existing_destination(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    out_dir = tmp_path / "run"
    _write_minimal_bundle(bundle_root)
    import_peoc_bundle(PeocImportOptions(bundle_root=bundle_root, out_dir=out_dir))
    original_manifest = (out_dir / "manifest.json").read_bytes()
    collision = out_dir / "source" / HARD_SUMMARY
    collision.parent.mkdir(parents=True, exist_ok=True)
    collision.write_text("user-owned content", encoding="utf-8")

    with pytest.raises(ValueError, match=r"not registered|unregistered"):
        import_peoc_bundle(
            PeocImportOptions(
                bundle_root=bundle_root,
                out_dir=out_dir,
                portable=True,
                overwrite=True,
            )
        )

    assert collision.read_text(encoding="utf-8") == "user-owned content"
    assert (out_dir / "manifest.json").read_bytes() == original_manifest


def test_portable_overwrite_replaces_registered_copies_and_preserves_unrelated(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    out_dir = tmp_path / "run"
    _write_minimal_bundle(bundle_root)
    import_peoc_bundle(
        PeocImportOptions(
            bundle_root=bundle_root,
            out_dir=out_dir,
            portable=True,
        )
    )
    copied_hard = out_dir / "source" / HARD_SUMMARY
    previous_copy = copied_hard.read_bytes()
    unrelated = out_dir / "source" / "user-notes.txt"
    unrelated.write_text("keep me", encoding="utf-8")
    hard_path = bundle_root / HARD_SUMMARY
    hard_payload = read_json(hard_path)
    hard_payload["summary"][0]["mean"] = 0.13
    _write_json(hard_path, hard_payload)

    import_peoc_bundle(
        PeocImportOptions(
            bundle_root=bundle_root,
            out_dir=out_dir,
            portable=True,
            overwrite=True,
        )
    )

    assert copied_hard.read_bytes() == hard_path.read_bytes()
    assert copied_hard.read_bytes() != previous_copy
    assert unrelated.read_text(encoding="utf-8") == "keep me"


def test_portable_overwrite_rejects_modified_registered_copy(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    out_dir = tmp_path / "run"
    _write_minimal_bundle(bundle_root)
    import_peoc_bundle(
        PeocImportOptions(
            bundle_root=bundle_root,
            out_dir=out_dir,
            portable=True,
        )
    )
    copied_hard = out_dir / "source" / HARD_SUMMARY
    copied_hard.write_text("user-modified registered copy", encoding="utf-8")
    unrelated = out_dir / "source" / "user-notes.txt"
    unrelated.write_text("keep me", encoding="utf-8")
    original_manifest = (out_dir / "manifest.json").read_bytes()

    with pytest.raises(ValueError, match=r"modified|does not match"):
        import_peoc_bundle(
            PeocImportOptions(
                bundle_root=bundle_root,
                out_dir=out_dir,
                portable=True,
                overwrite=True,
            )
        )

    assert copied_hard.read_text(encoding="utf-8") == "user-modified registered copy"
    assert unrelated.read_text(encoding="utf-8") == "keep me"
    assert (out_dir / "manifest.json").read_bytes() == original_manifest


def test_registered_replacement_rejects_destination_created_after_backup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_root = tmp_path / "bundle"
    out_dir = tmp_path / "run"
    _write_minimal_bundle(bundle_root)
    import_peoc_bundle(
        PeocImportOptions(
            bundle_root=bundle_root,
            out_dir=out_dir,
            portable=True,
        )
    )
    copied_hard = out_dir / "source" / HARD_SUMMARY
    unrelated = out_dir / "source" / "user-notes.txt"
    unrelated.write_text("keep me", encoding="utf-8")
    original_manifest = (out_dir / "manifest.json").read_bytes()
    original_replace = os.replace
    injected = False

    def create_racer_after_backup(source: Path, destination: Path) -> None:
        nonlocal injected
        original_replace(source, destination)
        if not injected and Path(source) == copied_hard:
            copied_hard.write_text("racing writer content", encoding="utf-8")
            injected = True

    monkeypatch.setattr(os, "replace", create_racer_after_backup)

    with pytest.raises(ValueError, match=r"appeared during commit|refusing to overwrite"):
        import_peoc_bundle(
            PeocImportOptions(
                bundle_root=bundle_root,
                out_dir=out_dir,
                portable=True,
                overwrite=True,
            )
        )

    assert injected is True
    assert copied_hard.read_text(encoding="utf-8") == "racing writer content"
    assert unrelated.read_text(encoding="utf-8") == "keep me"
    assert (out_dir / "manifest.json").read_bytes() == original_manifest


def test_obsolete_cleanup_rejects_file_changed_after_identity_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_root = tmp_path / "bundle"
    out_dir = tmp_path / "run"
    _write_minimal_bundle(bundle_root)
    import_peoc_bundle(
        PeocImportOptions(
            bundle_root=bundle_root,
            out_dir=out_dir,
            portable=True,
        )
    )
    copied_hard = out_dir / "source" / HARD_SUMMARY
    unrelated = out_dir / "source" / "user-notes.txt"
    unrelated.write_text("keep me", encoding="utf-8")
    original_manifest = (out_dir / "manifest.json").read_bytes()
    original_replace = os.replace
    injected = False

    def replace_registered_file_during_move(source: Path, destination: Path) -> None:
        nonlocal injected
        if not injected and Path(source) == copied_hard:
            copied_hard.write_text("obsolete cleanup racer", encoding="utf-8")
            injected = True
        original_replace(source, destination)

    monkeypatch.setattr(os, "replace", replace_registered_file_during_move)

    with pytest.raises(ValueError, match=r"changed during commit|does not match"):
        import_peoc_bundle(
            PeocImportOptions(
                bundle_root=bundle_root,
                out_dir=out_dir,
                portable=False,
                overwrite=True,
            )
        )

    assert injected is True
    assert copied_hard.read_text(encoding="utf-8") == "obsolete cleanup racer"
    assert unrelated.read_text(encoding="utf-8") == "keep me"
    assert (out_dir / "manifest.json").read_bytes() == original_manifest


def test_registered_replacement_restores_raced_content_without_hard_links(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_root = tmp_path / "bundle"
    out_dir = tmp_path / "run"
    _write_minimal_bundle(bundle_root)
    import_peoc_bundle(
        PeocImportOptions(
            bundle_root=bundle_root,
            out_dir=out_dir,
            portable=True,
        )
    )
    copied_hard = out_dir / "source" / HARD_SUMMARY
    unrelated = out_dir / "source" / "user-notes.txt"
    unrelated.write_text("keep me", encoding="utf-8")
    original_replace = os.replace
    raced_content = "registered replacement fallback racer"
    injected = False

    def hard_links_unavailable(source: Path, destination: Path) -> None:
        raise OSError("hard links are unavailable")

    def replace_registered_file_during_move(source: Path, destination: Path) -> None:
        nonlocal injected
        if not injected and Path(source) == copied_hard:
            copied_hard.write_text(raced_content, encoding="utf-8")
            injected = True
        original_replace(source, destination)

    monkeypatch.setattr(os, "link", hard_links_unavailable)
    monkeypatch.setattr(os, "replace", replace_registered_file_during_move)

    with pytest.raises(ValueError, match=r"changed during commit|does not match"):
        import_peoc_bundle(
            PeocImportOptions(
                bundle_root=bundle_root,
                out_dir=out_dir,
                portable=True,
                overwrite=True,
            )
        )

    assert injected is True
    assert copied_hard.read_text(encoding="utf-8") == raced_content
    assert unrelated.read_text(encoding="utf-8") == "keep me"


def test_obsolete_cleanup_restores_raced_content_without_hard_links(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_root = tmp_path / "bundle"
    out_dir = tmp_path / "run"
    _write_minimal_bundle(bundle_root)
    import_peoc_bundle(
        PeocImportOptions(
            bundle_root=bundle_root,
            out_dir=out_dir,
            portable=True,
        )
    )
    copied_hard = out_dir / "source" / HARD_SUMMARY
    unrelated = out_dir / "source" / "user-notes.txt"
    unrelated.write_text("keep me", encoding="utf-8")
    original_replace = os.replace
    raced_content = "obsolete cleanup fallback racer"
    injected = False

    def hard_links_unavailable(source: Path, destination: Path) -> None:
        raise OSError("hard links are unavailable")

    def replace_registered_file_during_move(source: Path, destination: Path) -> None:
        nonlocal injected
        if not injected and Path(source) == copied_hard:
            copied_hard.write_text(raced_content, encoding="utf-8")
            injected = True
        original_replace(source, destination)

    monkeypatch.setattr(os, "link", hard_links_unavailable)
    monkeypatch.setattr(os, "replace", replace_registered_file_during_move)

    with pytest.raises(ValueError, match=r"changed during commit|does not match"):
        import_peoc_bundle(
            PeocImportOptions(
                bundle_root=bundle_root,
                out_dir=out_dir,
                portable=False,
                overwrite=True,
            )
        )

    assert injected is True
    assert copied_hard.read_text(encoding="utf-8") == raced_content
    assert unrelated.read_text(encoding="utf-8") == "keep me"


def test_rollback_preserves_backup_racer_when_destination_reappears(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_root = tmp_path / "bundle"
    out_dir = tmp_path / "run"
    _write_minimal_bundle(bundle_root)
    import_peoc_bundle(
        PeocImportOptions(
            bundle_root=bundle_root,
            out_dir=out_dir,
            portable=True,
        )
    )
    copied_hard = out_dir / "source" / HARD_SUMMARY
    original_replace = os.replace
    backup_racer = "raced content moved to backup"
    destination_racer = "independent destination racer"
    injected = False

    def hard_links_unavailable(source: Path, destination: Path) -> None:
        raise OSError("hard links are unavailable")

    def race_both_sides_of_backup_move(source: Path, destination: Path) -> None:
        nonlocal injected
        if not injected and Path(source) == copied_hard:
            copied_hard.write_text(backup_racer, encoding="utf-8")
            original_replace(source, destination)
            copied_hard.write_text(destination_racer, encoding="utf-8")
            injected = True
            return
        original_replace(source, destination)

    monkeypatch.setattr(os, "link", hard_links_unavailable)
    monkeypatch.setattr(os, "replace", race_both_sides_of_backup_move)

    with pytest.raises(ValueError, match=r"changed during commit|does not match"):
        import_peoc_bundle(
            PeocImportOptions(
                bundle_root=bundle_root,
                out_dir=out_dir,
                portable=True,
                overwrite=True,
            )
        )

    assert injected is True
    assert copied_hard.read_text(encoding="utf-8") == destination_racer
    assert _recovery_files_with_content(out_dir, backup_racer)


def test_portable_commit_rejects_unregistered_destination_created_after_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_root = tmp_path / "bundle"
    out_dir = tmp_path / "run"
    _write_minimal_bundle(bundle_root)
    import_peoc_bundle(PeocImportOptions(bundle_root=bundle_root, out_dir=out_dir))
    original_manifest = (out_dir / "manifest.json").read_bytes()
    collision = out_dir / "source" / HARD_SUMMARY
    original_preflight = peoc_import_module._preflight_staged_targets

    def preflight_then_create_collision(
        output_dir: Path,
        targets: list[tuple[Path, Path]],
        *,
        overwrite: bool,
        registered_portable_targets: set[Path],
    ) -> None:
        original_preflight(
            output_dir,
            targets,
            overwrite=overwrite,
            registered_portable_targets=registered_portable_targets,
        )
        collision.parent.mkdir(parents=True, exist_ok=True)
        collision.write_text("race-created content", encoding="utf-8")

    monkeypatch.setattr(
        peoc_import_module,
        "_preflight_staged_targets",
        preflight_then_create_collision,
    )

    with pytest.raises(ValueError, match=r"not registered|unregistered"):
        import_peoc_bundle(
            PeocImportOptions(
                bundle_root=bundle_root,
                out_dir=out_dir,
                portable=True,
                overwrite=True,
            )
        )

    assert collision.read_text(encoding="utf-8") == "race-created content"
    assert (out_dir / "manifest.json").read_bytes() == original_manifest


def test_commit_rollback_preserves_portable_file_replaced_after_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_root = tmp_path / "bundle"
    out_dir = tmp_path / "run"
    _write_minimal_bundle(bundle_root)
    import_peoc_bundle(PeocImportOptions(bundle_root=bundle_root, out_dir=out_dir))
    original_manifest = (out_dir / "manifest.json").read_bytes()
    original_publish = peoc_import_module._publish_new_portable
    original_validate = peoc_import_module._validate_published_artifact
    raced_path: Path | None = None
    portable_publications = 0

    def fail_second_portable_publication(
        source: Path,
        destination: Path,
        source_identity: Any,
    ) -> Any:
        nonlocal portable_publications
        portable_publications += 1
        if portable_publications == 2:
            raise OSError("simulated later commit failure")
        return original_publish(source, destination, source_identity)

    def validate_then_replace(
        output_dir: Path,
        destination: Path,
        guard: Any,
        placed: Any,
    ) -> None:
        nonlocal raced_path
        original_validate(output_dir, destination, guard, placed)
        if raced_path is None and "source" in destination.relative_to(out_dir).parts:
            destination.unlink()
            destination.write_text("external replacement", encoding="utf-8")
            raced_path = destination

    monkeypatch.setattr(
        peoc_import_module,
        "_publish_new_portable",
        fail_second_portable_publication,
    )
    monkeypatch.setattr(
        peoc_import_module,
        "_validate_published_artifact",
        validate_then_replace,
    )

    with pytest.raises(OSError, match="simulated later commit failure"):
        import_peoc_bundle(
            PeocImportOptions(
                bundle_root=bundle_root,
                out_dir=out_dir,
                portable=True,
                overwrite=True,
            )
        )

    assert raced_path is not None
    assert raced_path.read_text(encoding="utf-8") == "external replacement"
    assert (out_dir / "manifest.json").read_bytes() == original_manifest


def test_directory_guard_rejects_parent_replaced_after_validation(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "run"
    parent = out_dir / "source" / "nested"
    parent.mkdir(parents=True)
    destination = parent / "artifact.json"
    guard = peoc_import_module._capture_directory_guard(out_dir, destination)
    moved_parent = parent.with_name("nested-before-race")
    parent.rename(moved_parent)
    parent.mkdir()

    with pytest.raises(ValueError, match=r"changed during PEOC import"):
        peoc_import_module._validate_directory_guard(
            out_dir,
            destination,
            guard,
        )


def test_overwrite_removes_only_previously_registered_portable_copies(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    out_dir = tmp_path / "run"
    _write_minimal_bundle(bundle_root)
    import_peoc_bundle(
        PeocImportOptions(
            bundle_root=bundle_root,
            out_dir=out_dir,
            portable=True,
        )
    )
    portable_manifest = read_json(out_dir / "source_manifest.json")
    copied_paths = [
        out_dir / str(row["copied_path"])
        for row in portable_manifest["sources"]
        if row.get("copied_path")
    ]
    assert copied_paths
    assert all(path.is_file() for path in copied_paths)
    unrelated = out_dir / "source" / "user-notes.txt"
    unrelated.write_text("keep me", encoding="utf-8")

    import_peoc_bundle(
        PeocImportOptions(
            bundle_root=bundle_root,
            out_dir=out_dir,
            portable=False,
            overwrite=True,
        )
    )

    assert all(not path.exists() for path in copied_paths)
    assert unrelated.read_text(encoding="utf-8") == "keep me"
    manifest = read_json(out_dir / "source_manifest.json")
    assert all(row.get("copied_path") is None for row in manifest["sources"])


def test_overwrite_commit_failure_restores_registered_portable_copies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_root = tmp_path / "bundle"
    out_dir = tmp_path / "run"
    _write_minimal_bundle(bundle_root)
    import_peoc_bundle(
        PeocImportOptions(
            bundle_root=bundle_root,
            out_dir=out_dir,
            portable=True,
        )
    )
    original_files = {
        path.relative_to(out_dir).as_posix(): path.read_bytes()
        for path in out_dir.rglob("*")
        if path.is_file()
    }
    hard_path = bundle_root / HARD_SUMMARY
    hard_payload = read_json(hard_path)
    hard_payload["summary"][0]["mean"] = 0.12
    _write_json(hard_path, hard_payload)
    original_replace = os.replace
    failed = False

    def fail_once_during_commit(source: Path, destination: Path) -> None:
        nonlocal failed
        target = Path(destination)
        if (
            not failed
            and target.parent == out_dir
            and target.name == "peoc_evidence.json"
        ):
            failed = True
            raise OSError("simulated overwrite commit failure")
        original_replace(source, destination)

    monkeypatch.setattr(os, "replace", fail_once_during_commit)

    with pytest.raises(OSError, match="simulated overwrite commit failure"):
        import_peoc_bundle(
            PeocImportOptions(
                bundle_root=bundle_root,
                out_dir=out_dir,
                portable=False,
                overwrite=True,
            )
        )

    assert {
        path.relative_to(out_dir).as_posix(): path.read_bytes()
        for path in out_dir.rglob("*")
        if path.is_file()
    } == original_files


def test_rollback_does_not_overwrite_racing_generated_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_root = tmp_path / "bundle"
    out_dir = tmp_path / "run"
    _write_minimal_bundle(bundle_root)
    import_peoc_bundle(PeocImportOptions(bundle_root=bundle_root, out_dir=out_dir))
    original_validate = peoc_import_module._validate_published_artifact
    original_replace = os.replace
    injected = False
    failed = False

    def validate_then_create_racer(
        output_dir: Path,
        destination: Path,
        guard: Any,
        placed: Any,
    ) -> None:
        nonlocal injected
        original_validate(output_dir, destination, guard, placed)
        if not injected and destination == out_dir / "manifest.json":
            destination.unlink()
            destination.write_text("racing generated artifact", encoding="utf-8")
            injected = True

    def fail_later_generated_publication(source: Path, destination: Path) -> None:
        nonlocal failed
        if (
            not failed
            and Path(destination) == out_dir / "peoc_evidence.json"
            and Path(source).parent.name == "payload"
        ):
            failed = True
            raise OSError("simulated later generated commit failure")
        original_replace(source, destination)

    monkeypatch.setattr(
        peoc_import_module,
        "_validate_published_artifact",
        validate_then_create_racer,
    )
    monkeypatch.setattr(os, "replace", fail_later_generated_publication)

    with pytest.raises(OSError, match="simulated later generated commit failure"):
        import_peoc_bundle(
            PeocImportOptions(
                bundle_root=bundle_root,
                out_dir=out_dir,
                overwrite=True,
            )
        )

    assert injected is True
    assert (out_dir / "manifest.json").read_text(
        encoding="utf-8"
    ) == "racing generated artifact"
    assert (out_dir / "peoc_evidence.json").is_file()


def test_portable_import_records_deterministic_file_and_total_limit_warnings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_root = tmp_path / "bundle"
    _write_minimal_bundle(bundle_root)

    monkeypatch.setattr(peoc_import_module, "MAX_PORTABLE_FILE_BYTES", 64)
    file_limited_out = tmp_path / "file-limited"
    import_peoc_bundle(
        PeocImportOptions(
            bundle_root=bundle_root,
            out_dir=file_limited_out,
            portable=True,
        )
    )
    file_manifest = read_json(file_limited_out / "source_manifest.json")
    file_warnings = [
        warning
        for warning in file_manifest["warnings"]
        if warning["code"] == "portable_file_too_large"
    ]
    assert file_warnings
    assert file_warnings == sorted(
        file_warnings,
        key=lambda warning: (
            warning["code"],
            warning["source_role"],
            warning["relative_path"],
        ),
    )

    monkeypatch.setattr(peoc_import_module, "MAX_PORTABLE_FILE_BYTES", 10**9)
    hard_size = (bundle_root / HARD_SUMMARY).stat().st_size
    monkeypatch.setattr(peoc_import_module, "MAX_PORTABLE_TOTAL_BYTES", hard_size)
    total_limited_out = tmp_path / "total-limited"
    import_peoc_bundle(
        PeocImportOptions(
            bundle_root=bundle_root,
            out_dir=total_limited_out,
            portable=True,
        )
    )
    total_manifest = read_json(total_limited_out / "source_manifest.json")
    total_warnings = [
        warning
        for warning in total_manifest["warnings"]
        if warning["code"] == "portable_total_limit_exceeded"
    ]
    assert total_warnings
    assert next(
        row
        for row in total_manifest["sources"]
        if row["role"] == "hard_test_summary"
    )["copied_path"] == f"source/{HARD_SUMMARY.as_posix()}"


def test_import_rejects_invalid_language_and_unsafe_output_paths(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    _write_minimal_bundle(bundle_root)

    with pytest.raises(ValueError, match=r"language.*en.*zh"):
        import_peoc_bundle(
            PeocImportOptions(
                bundle_root=bundle_root,
                out_dir=tmp_path / "bad-language",
                language="fr",
            )
        )

    with pytest.raises(ValueError, match="output"):
        import_peoc_bundle(
            PeocImportOptions(bundle_root=bundle_root, out_dir=bundle_root)
        )

    with pytest.raises(ValueError, match=r"inside.*bundle"):
        import_peoc_bundle(
            PeocImportOptions(
                bundle_root=bundle_root,
                out_dir=bundle_root / "generated-report",
            )
        )

    with pytest.raises(ValueError, match="source"):
        import_peoc_bundle(
            PeocImportOptions(
                bundle_root=bundle_root,
                out_dir=(bundle_root / HARD_SUMMARY).parent,
            )
        )


def test_case_study_renderers_escape_source_values_and_support_both_languages() -> None:
    payload: JsonDict = {
        "evidence_source": "REAL PEOC BUNDLE",
        "manifest_hash": "sha256:manifest",
        "status_counts": {
            "available": 1,
            "failed_validation": 1,
            "missing": 1,
            "partial": 0,
            "unusable": 1,
        },
        "hard_method_rows": [
            {
                "model": "<script>alert(1)</script>",
                "task": "a|b",
                "method": "tv_pmp",
                "mean": 0.6,
                "sd": 0.1,
                "n": 10,
            }
        ],
        "hard_summary": {
            "metric": "acc_hard_test",
            "valid_row_count": 1,
            "excluded_row_count": 0,
        },
        "selected_trajectory_pair": {
            "model": "Qwen/<unsafe>",
            "seed": 0,
            "stationary": {"alpha_emp_mean": 0.02, "R2_mean": 0.6},
            "heterogeneous": {"alpha_emp_mean": 0.001, "R2_mean": 0.08},
        },
        "stage_validation": {
            "status": "failed_validation",
            "verdict": "FAIL",
            "held_spearman_rho": -0.5,
            "held_bootstrap_ci": [-1.0, 0.6],
        },
        "limited_sections": [
            {
                "section": "soft_evaluation",
                "origin": "real",
                "status": "unusable",
                "limitation": "<img src=x onerror=alert(1)>",
            }
        ],
        "source_inventory": [
            {
                "role": "hard_test_summary",
                "relative_path": "![remote](https://example.invalid/a.png)`break`.json",
                "sha256": "sha256:<hash>",
                "bytes": 12,
            }
        ],
        "safe_claim": "[unsafe link](https://example.invalid)<b>bounded claim</b>",
        "limitations": ["<svg onload=alert(1)>"],
        "claim_boundary": {"full_research_support": False},
    }

    english = render_peoc_case_study_html(payload, language="en")
    chinese = render_peoc_case_study_html(payload, language="zh")
    markdown_en = render_peoc_case_study_markdown(payload, language="en")
    markdown_zh = render_peoc_case_study_markdown(payload, language="zh")

    assert "Real PEOC Evidence Case Study" in english
    assert "真实 PEOC 证据案例" in chinese
    assert "Real PEOC Evidence Case Study" in markdown_en
    assert "真实 PEOC 证据案例" in markdown_zh
    assert "<script>alert(1)</script>" not in english
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in english
    assert "<img src=x onerror=alert(1)>" not in english
    assert "<svg onload=alert(1)>" not in english
    assert "repeat(auto-fit, minmax(210px, 1fr))" in english
    assert "![remote](https://example.invalid/a.png)" not in markdown_en
    assert "[unsafe link](https://example.invalid)" not in markdown_en
    assert "`break`" not in markdown_en

    with pytest.raises(ValueError, match="language"):
        render_peoc_case_study_html(payload, language="fr")
    with pytest.raises(ValueError, match="language"):
        render_peoc_case_study_markdown(payload, language="fr")


def test_import_outputs_are_deterministic_across_equivalent_runs(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    first_out = tmp_path / "first"
    second_out = tmp_path / "second"
    _write_minimal_bundle(bundle_root)

    first = import_peoc_bundle(
        PeocImportOptions(bundle_root=bundle_root, out_dir=first_out)
    )
    second = import_peoc_bundle(
        PeocImportOptions(bundle_root=bundle_root, out_dir=second_out)
    )

    for name in first["artifacts"]:
        assert (first_out / name).read_bytes() == (second_out / name).read_bytes()
    assert first["status_counts"] == second["status_counts"]
    assert first["claim_boundary"] == second["claim_boundary"]
