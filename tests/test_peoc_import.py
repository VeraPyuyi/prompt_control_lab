from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from promptcontrollab.files import JsonDict
from promptcontrollab.peoc_import import (
    HARD_SUMMARY,
    PeocSourceOverrides,
    build_peoc_evidence,
    discover_peoc_sources,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


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


def test_build_peoc_evidence_rejects_malformed_required_hard_summary(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    _write_minimal_bundle(bundle_root)
    _write_json(bundle_root / HARD_SUMMARY, {"metric": "acc_hard_test"})
    manifest = discover_peoc_sources(bundle_root, PeocSourceOverrides())

    with pytest.raises(ValueError, match=r"hard-test summary.*summary"):
        build_peoc_evidence(bundle_root, manifest)
