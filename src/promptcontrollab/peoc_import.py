"""Discover source files in a real PEOC evidence bundle."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from promptcontrollab.files import JsonDict

HARD_SUMMARY = Path(
    "experiments/redesign_v2/results_server_pull_20260524/"
    "strong_main_grid/summary_acc_hard_test.json"
)
SOFT_SUMMARY = Path(
    "experiments/redesign_v2/results_server_pull_20260524/"
    "strong_main_grid/summary_soft_segmented.json"
)
HETEROGENEITY_SUMMARY = Path("experiments/redesign_v2/stage_heterogeneity/shi_r27_summary.json")
TRAJECTORY_ROOT = Path("experiments/turnpike_trace/results_a800")

_MANIFEST = Path("README_MANIFEST.md")
_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class PeocSourceOverrides:
    """Optional source selections within a PEOC bundle."""

    hard_summary: Path | None = None
    trajectory_files: tuple[Path, ...] = ()
    heterogeneity_summary: Path | None = None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(_CHUNK_SIZE):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def discover_peoc_sources(
    bundle_root: Path,
    overrides: PeocSourceOverrides,
) -> JsonDict:
    """Discover and hash the selected sources in a PEOC evidence bundle."""

    root = bundle_root.resolve()
    if not root.is_dir():
        msg = f"PEOC bundle root is not a directory: {root}"
        raise ValueError(msg)

    manifest_path = _resolve_bundle_path(root, _MANIFEST, label="bundle manifest")
    _require_file(manifest_path, label="bundle manifest README_MANIFEST.md")

    sources: list[JsonDict] = [
        _source_row(
            root,
            manifest_path,
            role="bundle_manifest",
            media_type="text/markdown",
            selection="required",
        )
    ]

    hard_selection = overrides.hard_summary or HARD_SUMMARY
    hard_path = _resolve_bundle_path(root, hard_selection, label="hard-test summary")
    _require_file(hard_path, label="hard-test summary")
    sources.append(
        _source_row(
            root,
            hard_path,
            role="hard_test_summary",
            media_type="application/json",
            selection="override" if overrides.hard_summary is not None else "default",
        )
    )

    soft_path = _resolve_bundle_path(root, SOFT_SUMMARY, label="soft segmented summary")
    if soft_path.is_file():
        sources.append(
            _source_row(
                root,
                soft_path,
                role="soft_segmented_summary",
                media_type="application/json",
                selection="default",
            )
        )

    heterogeneity_selection = overrides.heterogeneity_summary or HETEROGENEITY_SUMMARY
    heterogeneity_path = _resolve_bundle_path(
        root,
        heterogeneity_selection,
        label="stage heterogeneity summary",
    )
    if overrides.heterogeneity_summary is not None:
        _require_file(heterogeneity_path, label="stage heterogeneity summary")
    if heterogeneity_path.is_file():
        sources.append(
            _source_row(
                root,
                heterogeneity_path,
                role="stage_heterogeneity",
                media_type="application/json",
                selection=(
                    "override" if overrides.heterogeneity_summary is not None else "default"
                ),
            )
        )

    trajectory_paths, trajectory_selection = _trajectory_sources(root, overrides)
    for trajectory_path in trajectory_paths:
        sources.append(
            _source_row(
                root,
                trajectory_path,
                role=_trajectory_role(trajectory_path),
                media_type="application/json",
                selection=trajectory_selection,
            )
        )
    for trajectory_path in trajectory_paths:
        binary_path = _resolve_existing_sibling(root, trajectory_path.with_suffix(".npz"))
        if binary_path is not None:
            sources.append(
                _source_row(
                    root,
                    binary_path,
                    role="trajectory_binary",
                    media_type="application/octet-stream",
                    selection="sibling",
                )
            )

    return {
        "schema": "prompt_control_lab.peoc_source_manifest.v1",
        "bundle": {
            "resolved_path": str(root),
            "manifest_relative_path": _MANIFEST.as_posix(),
            "manifest_sha256": _sha256_file(manifest_path),
        },
        "sources": sources,
        "warnings": [],
    }


def _trajectory_sources(
    root: Path,
    overrides: PeocSourceOverrides,
) -> tuple[list[Path], str]:
    if overrides.trajectory_files:
        paths = [
            _resolve_bundle_path(root, path, label="trajectory override")
            for path in overrides.trajectory_files
        ]
        for path in paths:
            _require_file(path, label="trajectory override")
            _trajectory_role(path)
        return paths, "override"

    trajectory_root = _resolve_bundle_path(root, TRAJECTORY_ROOT, label="trajectory root")
    if not trajectory_root.is_dir():
        return [], "default_glob"

    paths = [
        *trajectory_root.glob("stationary_arith_*.json"),
        *trajectory_root.glob("turnpike_gsm8k_*.json"),
    ]
    resolved_paths = [_resolve_bundle_path(root, path, label="trajectory source") for path in paths]
    resolved_paths.sort(key=lambda path: path.relative_to(root).as_posix())
    return resolved_paths, "default_glob"


def _trajectory_role(path: Path) -> str:
    if path.name.startswith("stationary_arith_"):
        return "trajectory_stationary"
    if path.name.startswith("turnpike_gsm8k_"):
        return "trajectory_heterogeneous"
    msg = f"Trajectory source filename must start with stationary_arith_ or turnpike_gsm8k_: {path}"
    raise ValueError(msg)


def _resolve_existing_sibling(root: Path, path: Path) -> Path | None:
    if not path.is_file():
        return None
    return _resolve_bundle_path(root, path, label="trajectory binary")


def _resolve_bundle_path(root: Path, path: Path, *, label: str) -> Path:
    candidate = path if path.is_absolute() else root / path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        msg = f"{label} must resolve inside PEOC bundle root {root}: {path}"
        raise ValueError(msg) from None
    return resolved


def _require_file(path: Path, *, label: str) -> None:
    if not path.is_file():
        msg = f"Missing required {label}: {path}"
        raise ValueError(msg)


def _source_row(
    root: Path,
    path: Path,
    *,
    role: str,
    media_type: str,
    selection: str,
) -> JsonDict:
    return {
        "role": role,
        "relative_path": path.relative_to(root).as_posix(),
        "resolved_path": str(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
        "media_type": media_type,
        "selection": selection,
        "copied_path": None,
    }
