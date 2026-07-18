from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from promptcontrollab.peoc_import import (
    HARD_SUMMARY,
    PeocSourceOverrides,
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
    _write_json(results_root / "summary_acc_hard_test.json", {"accuracy": 0.75})
    _write_json(results_root / "summary_soft_segmented.json", {"accuracy": 0.8})
    _write_json(
        root / "experiments" / "redesign_v2" / "stage_heterogeneity" / "shi_r27_summary.json",
        {
            "held_spearman_rho": 0.6,
            "held_bootstrap_ci": [0.4, 0.8],
        },
    )

    trajectory_root = root / "experiments" / "turnpike_trace" / "results_a800"
    stationary = trajectory_root / "stationary_arith_Qwen2.5-7B-Instruct_s0.json"
    heterogeneous = trajectory_root / "turnpike_gsm8k_Qwen2.5-7B-Instruct_s0.json"
    _write_json(
        stationary,
        {
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "trajectory": [{"step": 0, "score": 0.5}],
        },
    )
    _write_json(
        heterogeneous,
        {
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "trajectory": [{"step": 0, "score": 0.4}],
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
