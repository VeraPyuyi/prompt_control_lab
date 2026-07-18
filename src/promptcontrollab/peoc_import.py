"""Discover source files in a real PEOC evidence bundle."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import TypeGuard, cast

from promptcontrollab.files import JsonDict
from promptcontrollab.peoc_reporting import (
    render_peoc_case_study_html,
    render_peoc_case_study_markdown,
)
from promptcontrollab.version import __version__

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

MAX_PORTABLE_FILE_BYTES = 10 * 1024 * 1024
MAX_PORTABLE_TOTAL_BYTES = 50 * 1024 * 1024

_MANIFEST = Path("README_MANIFEST.md")
_CHUNK_SIZE = 1024 * 1024
_SEED_PATTERN = re.compile(r"_s(-?\d+)\.json$")
_GENERATED_ARTIFACTS = (
    "manifest.json",
    "source_manifest.json",
    "peoc_evidence.json",
    "research_case_study.json",
    "research_case_study.md",
    "research_case_study.html",
)
_PORTABLE_EXTENSIONS = {".csv", ".json"}
_REQUIRED_SOURCE_ROLES = {"bundle_manifest", "hard_test_summary"}
_RECOVERY_DIRECTORY = ".peoc-recovery"
_MAX_RECOVERY_SNAPSHOTS = 8


@dataclass(frozen=True)
class PeocSourceOverrides:
    """Optional source selections within a PEOC bundle."""

    hard_summary: Path | None = None
    trajectory_files: tuple[Path, ...] = ()
    heterogeneity_summary: Path | None = None


@dataclass(frozen=True)
class PeocImportOptions:
    """Options for importing a real PEOC evidence bundle."""

    bundle_root: Path
    out_dir: Path
    overrides: PeocSourceOverrides = PeocSourceOverrides()
    portable: bool = False
    language: str = "en"
    overwrite: bool = False


@dataclass(frozen=True)
class _TrajectoryBinaryResults:
    valid: dict[str, list[JsonDict]]
    invalid: dict[str, list[JsonDict]]
    all_valid: list[JsonDict]
    all_invalid: list[JsonDict]


@dataclass(frozen=True)
class _FileIdentity:
    device: int
    inode: int
    size: int
    sha256: str


@dataclass(frozen=True)
class _PlacedArtifact:
    path: Path
    identity: _FileIdentity


@dataclass(frozen=True)
class _RegisteredPortableTarget:
    path: Path
    size: int
    sha256: str


@dataclass(frozen=True)
class _BackupArtifact:
    backup: Path
    destination: Path
    identity: _FileIdentity


@dataclass(frozen=True)
class _DirectoryGuard:
    root_resolved: Path
    root_device: int
    root_inode: int
    parent_resolved: Path
    parent_device: int
    parent_inode: int


def _sha256_file(path: Path) -> str:
    return _file_integrity(path)[1]


def _file_integrity(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(_CHUNK_SIZE):
            size += len(chunk)
            digest.update(chunk)
    return size, f"sha256:{digest.hexdigest()}"


def _sha256_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


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


def import_peoc_bundle(options: PeocImportOptions) -> JsonDict:
    """Import real PEOC evidence and generate reviewer-facing artifacts."""

    if options.language not in {"en", "zh"}:
        raise ValueError("PEOC import language must be 'en' or 'zh'")

    root = options.bundle_root.resolve()
    out_dir = options.out_dir.resolve()
    source_manifest = discover_peoc_sources(root, options.overrides)
    _validate_import_output(root, out_dir, source_manifest)
    _check_generated_artifacts(out_dir, overwrite=options.overwrite)
    previous_portable_targets = (
        _registered_portable_targets(out_dir)
        if options.overwrite
        else []
    )

    out_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        dir=out_dir.parent,
        prefix=f".{out_dir.name}.peoc-import-",
    ) as temporary:
        staging_dir = Path(temporary) / "payload"
        staging_dir.mkdir()
        if options.portable:
            _copy_portable_sources(
                root,
                staging_dir,
                source_manifest,
                overwrite=True,
            )

        evidence = build_peoc_evidence(root, source_manifest)
        case_study = _build_case_study(source_manifest, evidence)
        manifest: JsonDict = {
            "schema": "prompt_control_lab.research_import_manifest.v1",
            "tool": "prompt_control_lab",
            "tool_version": __version__,
            "mode": "research_import",
            "adapter": "peoc",
            "source_manifest": "source_manifest.json",
            "evidence": "peoc_evidence.json",
            "case_study": "research_case_study.json",
            "case_study_markdown": "research_case_study.md",
            "case_study_html": "research_case_study.html",
            "evidence_origin": "real",
            "portable": options.portable,
            "language": options.language,
        }
        markdown = render_peoc_case_study_markdown(
            case_study,
            language=options.language,
        )
        rendered_html = render_peoc_case_study_html(
            case_study,
            language=options.language,
        )

        _write_strict_json(staging_dir / "manifest.json", manifest)
        _write_strict_json(staging_dir / "source_manifest.json", source_manifest)
        _write_strict_json(staging_dir / "peoc_evidence.json", evidence)
        _write_strict_json(staging_dir / "research_case_study.json", case_study)
        (staging_dir / "research_case_study.md").write_text(
            markdown,
            encoding="utf-8",
        )
        (staging_dir / "research_case_study.html").write_text(
            rendered_html,
            encoding="utf-8",
        )
        _commit_staged_import(
            staging_dir,
            out_dir,
            overwrite=options.overwrite,
            previous_portable_targets=previous_portable_targets,
        )

    artifact_paths = {
        name: str(out_dir / name)
        for name in _GENERATED_ARTIFACTS
    }
    return {
        "kind": "peoc_research_import",
        "output_dir": str(out_dir),
        "artifacts": artifact_paths,
        "source_count": len(_manifest_sources(source_manifest)),
        "status_counts": case_study["status_counts"],
        "claim_boundary": case_study["claim_boundary"],
        "warning_count": len(case_study["warnings"]),
    }


def build_peoc_evidence(bundle_root: Path, source_manifest: JsonDict) -> JsonDict:
    """Normalize discovered PEOC sources into fail-closed research evidence."""

    root = bundle_root.resolve()
    if not root.is_dir():
        msg = f"PEOC bundle root is not a directory: {root}"
        raise ValueError(msg)

    warnings: list[JsonDict] = []
    finite_manifest = cast(
        JsonDict,
        _finite_json(
            source_manifest,
            warnings,
            source_role="source_manifest",
            relative_path=None,
        ),
    )
    sources = _manifest_sources(finite_manifest)
    _verify_bundle_manifest(root, sources, finite_manifest)
    hard = _build_hard_section(root, sources, warnings)
    soft = _build_soft_section(root, sources, warnings)
    trajectory = _build_trajectory_section(root, sources, warnings)
    stage = _build_stage_section(root, sources, warnings)
    riccati = _missing_section(
        "No Riccati/DARE diagnostic source was discovered in this PEOC bundle."
    )
    soft_hard = _missing_section(
        "No soft-to-hard projection diagnostic source was discovered in this PEOC bundle."
    )
    sections: JsonDict = {
        "hard_evaluation": hard,
        "soft_evaluation": soft,
        "trajectory": trajectory,
        "stage_heterogeneity": stage,
        "riccati": riccati,
        "soft_hard": soft_hard,
    }
    blocking_sections = [
        {"section": name, "status": section["status"]}
        for name, section in sections.items()
        if isinstance(section, dict) and section.get("status") != "available"
    ]
    warnings.sort(key=_warning_sort_key)

    return {
        "schema": "prompt_control_lab.peoc_evidence.v1",
        "bundle": finite_manifest.get("bundle", {}),
        "source_manifest": finite_manifest,
        "warnings": warnings,
        "sections": sections,
        "claim_boundary": {
            "full_research_support": not blocking_sections,
            "status": "supported" if not blocking_sections else "not_supported",
            "blocking_sections": blocking_sections,
            "statement": (
                "Evidence supports the complete research capability set."
                if not blocking_sections
                else "The imported bundle does not support the complete research capability set."
            ),
        },
    }


def _write_strict_json(path: Path, payload: JsonDict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_strict_json_text(payload), encoding="utf-8")


def _strict_json_text(payload: JsonDict) -> str:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )


def _validate_import_output(
    root: Path,
    out_dir: Path,
    source_manifest: JsonDict,
) -> None:
    if out_dir == root:
        raise ValueError("PEOC import output directory must not be the bundle root")
    if _is_relative_to(out_dir, root):
        raise ValueError(
            "PEOC import output directory must not be inside the source bundle"
        )
    if out_dir.exists() and not out_dir.is_dir():
        raise ValueError(f"PEOC import output path is not a directory: {out_dir}")

    for source in _manifest_sources(source_manifest):
        source_path = _source_path(
            root,
            source,
            label=str(source.get("role", "selected source")),
        )
        if (
            source_path == out_dir
            or _is_relative_to(source_path, out_dir)
            or _is_relative_to(out_dir, source_path)
        ):
            msg = (
                "PEOC import output directory collides with selected source "
                f"{_relative_path(source)}: {out_dir}"
            )
            raise ValueError(msg)


def _check_generated_artifacts(out_dir: Path, *, overwrite: bool) -> None:
    directory_collisions = [
        str(out_dir / name)
        for name in _GENERATED_ARTIFACTS
        if (out_dir / name).is_dir()
    ]
    if directory_collisions:
        joined = ", ".join(directory_collisions)
        raise ValueError(
            "Generated PEOC artifact paths collide with directories and cannot "
            f"be replaced: {joined}"
        )
    existing = [
        str(out_dir / name)
        for name in _GENERATED_ARTIFACTS
        if (out_dir / name).exists()
    ]
    if existing and not overwrite:
        joined = ", ".join(existing)
        raise ValueError(
            "Generated PEOC artifacts already exist; pass --overwrite to replace "
            f"only those artifacts: {joined}"
        )


def _commit_staged_import(
    staging_dir: Path,
    out_dir: Path,
    *,
    overwrite: bool,
    previous_portable_targets: list[_RegisteredPortableTarget],
) -> None:
    staged_files = sorted(
        (path for path in staging_dir.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(staging_dir).as_posix(),
    )
    targets = [
        (source, out_dir / source.relative_to(staging_dir))
        for source in staged_files
    ]
    registered_portable_targets = {
        registered.path: registered
        for registered in previous_portable_targets
    }
    _preflight_staged_targets(
        out_dir,
        targets,
        overwrite=overwrite,
        registered_portable_targets=set(registered_portable_targets),
    )
    staged_destinations = {destination.resolve() for _, destination in targets}
    obsolete_targets = [
        registered
        for registered in previous_portable_targets
        if (
            registered.path.is_file()
            and registered.path.resolve() not in staged_destinations
        )
    ]

    backup_root = staging_dir.parent / "backup"
    placed: list[_PlacedArtifact] = []
    backups: list[_BackupArtifact] = []
    created_directories: list[Path] = []
    try:
        _mkdir_with_tracking(out_dir, created_directories)
        for obsolete_registered in obsolete_targets:
            destination = obsolete_registered.path
            relative = destination.relative_to(out_dir)
            backup_path = backup_root / relative
            backups.append(
                _move_to_backup(
                    out_dir,
                    destination,
                    backup_path,
                    registered=obsolete_registered,
                )
            )
        for source, destination in targets:
            _mkdir_with_tracking(destination.parent, created_directories)
            _validate_staged_target_path(out_dir, destination)
            directory_guard = _capture_directory_guard(out_dir, destination)
            portable_target = _is_portable_target(out_dir, destination)
            registered_target = registered_portable_targets.get(destination)
            if destination.exists():
                if portable_target and registered_target is None:
                    raise ValueError(
                        "Portable destination exists but is not registered by the "
                        f"previous source_manifest.json: {destination}"
                    )
                relative = destination.relative_to(out_dir)
                backup_path = backup_root / relative
                backups.append(
                    _move_to_backup(
                        out_dir,
                        destination,
                        backup_path,
                        registered=registered_target if portable_target else None,
                    )
                )
                directory_guard = _capture_directory_guard(out_dir, destination)
            source_identity = _capture_file_identity(source)
            if portable_target:
                artifact = _publish_new_portable(
                    source,
                    destination,
                    source_identity,
                )
                placed.append(artifact)
                _validate_published_artifact(
                    out_dir,
                    destination,
                    directory_guard,
                    artifact,
                )
                source.unlink()
            else:
                os.replace(source, destination)
                artifact = _PlacedArtifact(destination, source_identity)
                placed.append(artifact)
                _validate_published_artifact(
                    out_dir,
                    destination,
                    directory_guard,
                    artifact,
                )
        _validate_backups_for_cleanup(out_dir, backups)
    except Exception as exc:
        for artifact in reversed(placed):
            _unlink_if_owned(artifact)
        recovery_paths: list[Path] = []
        for backup_artifact in reversed(backups):
            recovery_path = _restore_backup_no_clobber(
                out_dir,
                backup_artifact,
            )
            if recovery_path is not None:
                recovery_paths.append(recovery_path)
        for directory in reversed(created_directories):
            with suppress(OSError):
                directory.rmdir()
        if recovery_paths:
            raise _error_with_recovery_paths(exc, recovery_paths) from exc
        raise
    _prune_empty_output_directories(
        [registered.path.parent for registered in obsolete_targets],
        out_dir,
    )


def _mkdir_with_tracking(path: Path, created_directories: list[Path]) -> None:
    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    path.mkdir(parents=True, exist_ok=True)
    created_directories.extend(reversed(missing))


def _prune_empty_output_directories(
    directories: list[Path],
    out_dir: Path,
) -> None:
    ordered = sorted(
        set(directories),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for directory in ordered:
        current = directory
        while current != out_dir:
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent


def _registered_portable_targets(
    out_dir: Path,
) -> list[_RegisteredPortableTarget]:
    source_path = out_dir / "source"
    if not source_path.exists():
        return []
    source_root = source_path.resolve()
    if source_path.is_symlink() or not _is_relative_to(source_root, out_dir):
        raise ValueError(
            f"Existing portable source path resolves outside output: {source_path}"
        )
    if not source_root.is_dir():
        raise ValueError(
            f"Existing portable source path is not a directory: {source_root}"
        )

    manifest_path = out_dir / "source_manifest.json"
    if not manifest_path.is_file():
        raise ValueError(
            "Cannot safely replace existing portable sources without "
            f"source_manifest.json: {source_root}"
        )
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            "Cannot safely replace existing portable sources because "
            f"source_manifest.json is unreadable: {exc}"
        ) from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("sources"), list):
        raise ValueError(
            "Cannot safely replace existing portable sources because "
            "source_manifest.json has no sources list"
        )

    targets: dict[Path, _RegisteredPortableTarget] = {}
    for row in payload["sources"]:
        if not isinstance(row, dict):
            continue
        copied_path = row.get("copied_path")
        if copied_path is None:
            continue
        if (
            not isinstance(copied_path, str)
            or not copied_path
            or "\\" in copied_path
        ):
            raise ValueError(
                "Existing source_manifest.json contains an unsafe copied_path"
            )
        relative = Path(copied_path)
        target = out_dir / relative
        resolved_target = target.resolve()
        if (
            relative.is_absolute()
            or relative.as_posix() != copied_path
            or any(part in {".", ".."} for part in relative.parts)
            or not copied_path.startswith("source/")
            or not _is_relative_to(resolved_target, source_root)
            or resolved_target == source_root
            or target.is_symlink()
        ):
            raise ValueError(
                "Existing source_manifest.json contains an unsafe copied_path: "
                f"{copied_path}"
            )
        if target.is_dir():
            raise ValueError(
                "Existing portable copied_path points to a directory: "
                f"{copied_path}"
            )
        declared_size = row.get("bytes")
        declared_sha256 = row.get("sha256")
        if (
            not isinstance(declared_size, int)
            or isinstance(declared_size, bool)
            or declared_size < 0
            or not isinstance(declared_sha256, str)
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", declared_sha256)
        ):
            raise ValueError(
                "Existing source_manifest.json contains incomplete integrity "
                f"metadata for copied_path: {copied_path}"
            )
        registered = _RegisteredPortableTarget(
            path=target,
            size=declared_size,
            sha256=declared_sha256,
        )
        previous = targets.get(target)
        if previous is not None and previous != registered:
            raise ValueError(
                "Existing source_manifest.json contains conflicting integrity "
                f"metadata for copied_path: {copied_path}"
            )
        targets[target] = registered
    return sorted(
        targets.values(),
        key=lambda registered: registered.path.relative_to(out_dir).as_posix(),
    )


def _preflight_staged_targets(
    out_dir: Path,
    targets: list[tuple[Path, Path]],
    *,
    overwrite: bool,
    registered_portable_targets: set[Path],
) -> None:
    for _, destination in targets:
        _validate_staged_target_path(out_dir, destination)
        if destination.is_dir():
            raise ValueError(
                f"PEOC artifact path collides with a directory: {destination}"
            )
        if destination.exists() and not overwrite:
            raise ValueError(
                "PEOC artifact already exists; pass --overwrite to replace it: "
                f"{destination}"
            )
        if (
            destination.exists()
            and _is_portable_target(out_dir, destination)
            and destination not in registered_portable_targets
        ):
            raise ValueError(
                "Portable destination exists but is not registered by the previous "
                f"source_manifest.json: {destination}"
            )
        parent = destination.parent
        while parent != out_dir:
            if parent.exists() and not parent.is_dir():
                raise ValueError(
                    f"PEOC artifact parent path is not a directory: {parent}"
                )
            parent = parent.parent


def _validate_staged_target_path(out_dir: Path, destination: Path) -> None:
    resolved = destination.resolve()
    if not _is_relative_to(resolved, out_dir):
        raise ValueError(
            f"Staged PEOC artifact escapes output directory: {destination}"
        )


def _capture_directory_guard(
    out_dir: Path,
    destination: Path,
) -> _DirectoryGuard:
    root_resolved = out_dir.resolve(strict=True)
    parent_resolved = destination.parent.resolve(strict=True)
    if (
        not out_dir.is_dir()
        or not destination.parent.is_dir()
        or not _is_relative_to(parent_resolved, root_resolved)
    ):
        raise ValueError(
            f"PEOC artifact parent resolves outside output: {destination.parent}"
        )
    _reject_linked_parent_components(out_dir, destination.parent)
    root_stat = out_dir.stat()
    parent_stat = destination.parent.stat()
    return _DirectoryGuard(
        root_resolved=root_resolved,
        root_device=root_stat.st_dev,
        root_inode=root_stat.st_ino,
        parent_resolved=parent_resolved,
        parent_device=parent_stat.st_dev,
        parent_inode=parent_stat.st_ino,
    )


def _validate_directory_guard(
    out_dir: Path,
    destination: Path,
    expected: _DirectoryGuard,
) -> None:
    try:
        observed = _capture_directory_guard(out_dir, destination)
    except (OSError, ValueError) as exc:
        raise ValueError(
            f"Destination parent changed during PEOC import: {destination.parent}"
        ) from exc
    if observed != expected:
        raise ValueError(
            f"Destination parent changed during PEOC import: {destination.parent}"
        )


def _reject_linked_parent_components(out_dir: Path, parent: Path) -> None:
    try:
        relative = parent.relative_to(out_dir)
    except ValueError as exc:
        raise ValueError(
            f"PEOC artifact parent is outside output: {parent}"
        ) from exc
    current = out_dir
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError(
                f"PEOC artifact parent uses a symbolic link: {current}"
            )


def _capture_file_identity(path: Path) -> _FileIdentity:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"PEOC staged artifact is not a regular file: {path}")
    before = path.stat()
    size, sha256 = _file_integrity(path)
    after = path.stat()
    if (
        before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or after.st_size != size
    ):
        raise ValueError(f"PEOC staged artifact changed while reading: {path}")
    return _FileIdentity(
        device=after.st_dev,
        inode=after.st_ino,
        size=size,
        sha256=sha256,
    )


def _move_to_backup(
    out_dir: Path,
    destination: Path,
    backup: Path,
    *,
    registered: _RegisteredPortableTarget | None,
) -> _BackupArtifact:
    directory_guard = _capture_directory_guard(out_dir, destination)
    identity = _capture_file_identity(destination)
    if registered is not None and (
        identity.size != registered.size
        or identity.sha256 != registered.sha256
    ):
        raise ValueError(
            "Registered portable target was modified and does not match the "
            f"previous source_manifest.json: {destination}"
        )

    backup.parent.mkdir(parents=True, exist_ok=True)
    os.replace(destination, backup)
    artifact = _BackupArtifact(
        backup=backup,
        destination=destination,
        identity=identity,
    )
    try:
        if not _path_matches_file_identity(backup, identity):
            label = (
                "Registered portable target"
                if registered is not None
                else "Generated PEOC artifact"
            )
            raise ValueError(
                f"{label} changed during commit while moving to backup: "
                f"{destination}"
            )
        _validate_directory_guard(out_dir, destination, directory_guard)
    except Exception as exc:
        recovery_path = _restore_backup_no_clobber(out_dir, artifact)
        if recovery_path is not None:
            raise _error_with_recovery_paths(exc, [recovery_path]) from exc
        raise
    return artifact


def _restore_backup_no_clobber(
    out_dir: Path,
    artifact: _BackupArtifact,
) -> Path | None:
    if not artifact.backup.is_file():
        return None
    try:
        actual_identity = _capture_file_identity(artifact.backup)
    except (OSError, ValueError):
        return _preserve_backup_without_identity(out_dir, artifact)
    if os.path.lexists(artifact.destination):
        return _preserve_unresolved_backup(
            out_dir,
            artifact,
            actual_identity,
        )
    try:
        _validate_staged_target_path(out_dir, artifact.destination)
        directory_guard = _capture_directory_guard(out_dir, artifact.destination)
        restored = _publish_new_portable(
            artifact.backup,
            artifact.destination,
            actual_identity,
        )
        _validate_published_artifact(
            out_dir,
            artifact.destination,
            directory_guard,
            restored,
        )
    except (OSError, ValueError):
        return _preserve_current_backup(out_dir, artifact)
    if not _path_has_same_content(restored.path, actual_identity):
        return _preserve_current_backup(out_dir, artifact)
    _unlink_if_owned(_PlacedArtifact(artifact.backup, actual_identity))
    if not artifact.backup.is_file():
        return None
    try:
        remaining_identity = _capture_file_identity(artifact.backup)
    except (OSError, ValueError):
        return _preserve_backup_without_identity(out_dir, artifact)
    if _same_file_content(remaining_identity, actual_identity):
        return None
    return _preserve_unresolved_backup(
        out_dir,
        artifact,
        remaining_identity,
    )


def _validate_backups_for_cleanup(
    out_dir: Path,
    backups: list[_BackupArtifact],
) -> None:
    for artifact in backups:
        if not artifact.backup.is_file():
            continue
        actual_identity = _capture_file_identity(artifact.backup)
        if _same_file_content(actual_identity, artifact.identity):
            continue
        preserved = _preserve_unresolved_backup(
            out_dir,
            artifact,
            actual_identity,
        )
        raise ValueError(
            "PEOC backup changed during commit; racing content was preserved at "
            f"{preserved}"
        )


def _preserve_current_backup(
    out_dir: Path,
    artifact: _BackupArtifact,
) -> Path:
    if not artifact.backup.is_file():
        raise ValueError(f"PEOC backup became unavailable: {artifact.backup}")
    try:
        actual_identity = _capture_file_identity(artifact.backup)
    except (OSError, ValueError):
        return _preserve_backup_without_identity(out_dir, artifact)
    return _preserve_unresolved_backup(out_dir, artifact, actual_identity)


def _preserve_unresolved_backup(
    out_dir: Path,
    artifact: _BackupArtifact,
    initial_identity: _FileIdentity,
) -> Path:
    identity = initial_identity
    last_preserved: Path | None = None
    for _ in range(_MAX_RECOVERY_SNAPSHOTS):
        last_preserved = _publish_recovery_snapshot(
            out_dir,
            artifact,
            identity,
        )
        if _path_matches_file_identity(artifact.backup, identity):
            return last_preserved
        identity = _capture_file_identity(artifact.backup)
    raise ValueError(
        "PEOC backup kept changing while preserving racing content; "
        f"latest stable snapshot: {last_preserved}"
    )


def _publish_recovery_snapshot(
    out_dir: Path,
    artifact: _BackupArtifact,
    identity: _FileIdentity,
) -> Path:
    relative = artifact.destination.relative_to(out_dir)
    digest = identity.sha256.removeprefix("sha256:")[:16]
    recovery_parent = out_dir / _RECOVERY_DIRECTORY / relative.parent
    base_name = f"{relative.name}.{digest}.recovered"

    for collision_index in range(1000):
        suffix = "" if collision_index == 0 else f".{collision_index}"
        candidate = recovery_parent / f"{base_name}{suffix}"
        _validate_staged_target_path(out_dir, candidate)
        recovery_parent.mkdir(parents=True, exist_ok=True)
        directory_guard = _capture_directory_guard(out_dir, candidate)
        if os.path.lexists(candidate):
            if _path_has_same_content(candidate, identity):
                return candidate
            continue
        try:
            preserved = _publish_new_portable(
                artifact.backup,
                candidate,
                identity,
            )
        except ValueError:
            if os.path.lexists(candidate):
                continue
            raise
        _validate_published_artifact(
            out_dir,
            candidate,
            directory_guard,
            preserved,
        )
        return candidate
    raise ValueError(
        "Could not allocate an exclusive recovery path for PEOC backup: "
        f"{artifact.destination}"
    )


def _preserve_backup_without_identity(
    out_dir: Path,
    artifact: _BackupArtifact,
) -> Path:
    relative = artifact.destination.relative_to(out_dir)
    recovery_parent = out_dir / _RECOVERY_DIRECTORY / relative.parent
    base_name = f"{relative.name}.unverified.recovered"

    for collision_index in range(1000):
        suffix = "" if collision_index == 0 else f".{collision_index}"
        candidate = recovery_parent / f"{base_name}{suffix}"
        _validate_staged_target_path(out_dir, candidate)
        recovery_parent.mkdir(parents=True, exist_ok=True)
        directory_guard = _capture_directory_guard(out_dir, candidate)
        if os.path.lexists(candidate):
            continue
        created_token: tuple[int, int] | None = None
        try:
            try:
                os.link(artifact.backup, candidate)
            except FileExistsError:
                continue
            except OSError:
                with (
                    artifact.backup.open("rb") as input_stream,
                    candidate.open("xb") as output_stream,
                ):
                    created_stat = os.fstat(output_stream.fileno())
                    created_token = (created_stat.st_dev, created_stat.st_ino)
                    shutil.copyfileobj(input_stream, output_stream, _CHUNK_SIZE)
                    output_stream.flush()
            _validate_directory_guard(out_dir, candidate, directory_guard)
            if candidate.is_symlink() or not candidate.is_file():
                raise ValueError(
                    f"Unverified PEOC recovery is not a regular file: {candidate}"
                )
        except FileExistsError:
            continue
        except Exception:
            if created_token is not None:
                _unlink_if_file_token(candidate, created_token)
            raise
        return candidate
    raise ValueError(
        "Could not allocate an exclusive unverified recovery path for PEOC "
        f"backup: {artifact.destination}"
    )


def _error_with_recovery_paths(
    original: Exception,
    recovery_paths: list[Path],
) -> Exception:
    paths = ", ".join(
        str(path)
        for path in sorted(set(recovery_paths), key=lambda item: item.as_posix())
    )
    message = f"{original} Recovery backup path(s): {paths}"
    if isinstance(original, OSError):
        return OSError(message)
    if isinstance(original, ValueError):
        return ValueError(message)
    return RuntimeError(message)


def _same_file_content(left: _FileIdentity, right: _FileIdentity) -> bool:
    return left.size == right.size and left.sha256 == right.sha256


def _path_has_same_content(path: Path, expected: _FileIdentity) -> bool:
    try:
        observed = _capture_file_identity(path)
    except (OSError, ValueError):
        return False
    return _same_file_content(observed, expected)


def _publish_new_portable(
    source: Path,
    destination: Path,
    source_identity: _FileIdentity,
) -> _PlacedArtifact:
    try:
        # Staging shares the output volume, so linking publishes the complete
        # file atomically without replacing a racing writer.
        os.link(source, destination)
        return _PlacedArtifact(destination, source_identity)
    except FileExistsError as exc:
        raise _portable_destination_collision(destination) from exc
    except OSError:
        # Some writable filesystems do not support hard links. Exclusive creation
        # keeps the no-clobber guarantee while providing a portable copy fallback.
        pass

    created_token: tuple[int, int] | None = None
    try:
        with source.open("rb") as input_stream, destination.open("xb") as output_stream:
            created_stat = os.fstat(output_stream.fileno())
            created_token = (created_stat.st_dev, created_stat.st_ino)
            shutil.copyfileobj(input_stream, output_stream, _CHUNK_SIZE)
            output_stream.flush()
        copied_identity = _capture_file_identity(destination)
    except FileExistsError as exc:
        raise _portable_destination_collision(destination) from exc
    except Exception:
        if created_token is not None:
            _unlink_if_file_token(destination, created_token)
        raise

    if (
        copied_identity.device != created_token[0]
        or copied_identity.inode != created_token[1]
        or copied_identity.size != source_identity.size
        or copied_identity.sha256 != source_identity.sha256
    ):
        _unlink_if_file_token(destination, created_token)
        raise ValueError(
            f"Portable fallback copy verification failed for {destination}"
        )
    return _PlacedArtifact(destination, copied_identity)


def _portable_destination_collision(destination: Path) -> ValueError:
    return ValueError(
        "Portable destination appeared during commit; refusing to overwrite "
        f"the racing file: {destination}"
    )


def _unlink_if_file_token(path: Path, expected: tuple[int, int]) -> None:
    try:
        if path.is_symlink() or not path.is_file():
            return
        observed = path.stat()
        if (observed.st_dev, observed.st_ino) == expected:
            path.unlink()
    except OSError:
        return


def _path_matches_file_identity(path: Path, expected: _FileIdentity) -> bool:
    try:
        if path.is_symlink() or not path.is_file():
            return False
        before = path.stat()
        if (
            before.st_dev != expected.device
            or before.st_ino != expected.inode
            or before.st_size != expected.size
        ):
            return False
        size, sha256 = _file_integrity(path)
        after = path.stat()
    except OSError:
        return False
    return (
        before.st_dev == after.st_dev == expected.device
        and before.st_ino == after.st_ino == expected.inode
        and before.st_size == after.st_size == size == expected.size
        and sha256 == expected.sha256
    )


def _validate_published_artifact(
    out_dir: Path,
    destination: Path,
    directory_guard: _DirectoryGuard,
    artifact: _PlacedArtifact,
) -> None:
    _validate_directory_guard(out_dir, destination, directory_guard)
    if not _path_matches_file_identity(destination, artifact.identity):
        raise ValueError(
            f"Published PEOC artifact changed during commit: {destination}"
        )
    try:
        resolved = destination.resolve(strict=True)
    except OSError as exc:
        raise ValueError(
            f"Published PEOC artifact became unavailable: {destination}"
        ) from exc
    if not _is_relative_to(resolved, directory_guard.root_resolved):
        raise ValueError(
            f"Published PEOC artifact escaped output directory: {destination}"
        )


def _unlink_if_owned(artifact: _PlacedArtifact) -> None:
    if _path_matches_file_identity(artifact.path, artifact.identity):
        artifact.path.unlink()


def _is_portable_target(out_dir: Path, destination: Path) -> bool:
    try:
        relative = destination.relative_to(out_dir)
    except ValueError:
        return False
    return len(relative.parts) > 1 and relative.parts[0] == "source"


def _copy_portable_sources(
    root: Path,
    out_dir: Path,
    source_manifest: JsonDict,
    *,
    overwrite: bool,
) -> None:
    sources = _manifest_sources(source_manifest)
    warnings = source_manifest.get("warnings")
    if not isinstance(warnings, list):
        warnings = []
        source_manifest["warnings"] = warnings
    total_bytes = 0

    for source in sources:
        source["copied_path"] = None
        relative_path = _relative_path(source)
        suffix = Path(relative_path).suffix.lower()
        if suffix == ".npz":
            continue
        if suffix not in _PORTABLE_EXTENSIONS:
            warnings.append(
                _portable_warning(
                    source,
                    code="portable_unsupported_extension",
                    message=(
                        "Portable mode references this source without copying it "
                        f"because {suffix or '<no extension>'} is unsupported."
                    ),
                )
            )
            continue

        declared_size = source.get("bytes")
        if (
            not isinstance(declared_size, int)
            or isinstance(declared_size, bool)
            or declared_size < 0
        ):
            warnings.append(
                _portable_warning(
                    source,
                    code="portable_invalid_size",
                    message="Portable mode skipped a source with invalid byte metadata.",
                )
            )
            continue
        if declared_size > MAX_PORTABLE_FILE_BYTES:
            warnings.append(
                _portable_warning(
                    source,
                    code="portable_file_too_large",
                    message=(
                        f"Portable mode skipped {declared_size} bytes; per-file limit "
                        f"is {MAX_PORTABLE_FILE_BYTES} bytes."
                    ),
                )
            )
            continue
        if total_bytes + declared_size > MAX_PORTABLE_TOTAL_BYTES:
            warnings.append(
                _portable_warning(
                    source,
                    code="portable_total_limit_exceeded",
                    message=(
                        f"Portable mode skipped {declared_size} bytes; total limit "
                        f"is {MAX_PORTABLE_TOTAL_BYTES} bytes."
                    ),
                )
            )
            continue

        source_path = _source_path(
            root,
            source,
            label=str(source.get("role", "portable source")),
        )
        observed_size, observed_sha256 = _file_integrity(source_path)
        integrity_error = _source_integrity_error(
            source,
            observed_size,
            observed_sha256,
        )
        if integrity_error is not None:
            role = str(source.get("role", "portable source"))
            if role in _REQUIRED_SOURCE_ROLES:
                raise ValueError(
                    f"{role} source changed before portable copy: {integrity_error}"
                )
            warnings.append(
                _portable_warning(
                    source,
                    code="portable_source_integrity_mismatch",
                    message=(
                        "Portable mode skipped an optional source whose content "
                        f"changed after discovery: {integrity_error}"
                    ),
                )
            )
            continue

        copied_relative = Path("source") / Path(relative_path)
        destination = (out_dir / copied_relative).resolve()
        source_root = (out_dir / "source").resolve()
        if not _is_relative_to(destination, source_root):
            raise ValueError(
                f"Portable source destination escapes output directory: {relative_path}"
            )
        if destination.exists() and not overwrite:
            raise ValueError(
                "Portable source artifact already exists; pass --overwrite to replace it: "
                f"{destination}"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination)
        copied_size, copied_sha256 = _file_integrity(destination)
        if copied_size != observed_size or copied_sha256 != observed_sha256:
            raise ValueError(
                f"Portable copy verification failed for {relative_path}"
            )
        source["copied_path"] = copied_relative.as_posix()
        total_bytes += observed_size

    warnings.sort(key=_warning_sort_key)


def _portable_warning(
    source: JsonDict,
    *,
    code: str,
    message: str,
) -> JsonDict:
    return {
        "code": code,
        "source_role": str(source.get("role", "portable_source")),
        "relative_path": _relative_path(source),
        "message": message,
    }


def _build_case_study(
    source_manifest: JsonDict,
    evidence: JsonDict,
) -> JsonDict:
    sections = evidence.get("sections")
    section_rows = sections if isinstance(sections, dict) else {}
    status_counts = _status_counts(section_rows)
    hard = _section_dict(section_rows, "hard_evaluation")
    hard_observations = _dict_value(hard.get("observations"))
    trajectory = _section_dict(section_rows, "trajectory")
    trajectory_observations = _dict_value(trajectory.get("observations"))
    stage = _section_dict(section_rows, "stage_heterogeneity")
    stage_observations = _dict_value(stage.get("observations"))
    bundle = _dict_value(source_manifest.get("bundle"))
    source_inventory = [
        {
            "role": str(source.get("role", "")),
            "relative_path": _relative_path(source),
            "sha256": source.get("sha256"),
            "bytes": source.get("bytes"),
        }
        for source in sorted(
            _manifest_sources(source_manifest),
            key=lambda row: (_relative_path(row), str(row.get("role", ""))),
        )
    ]
    limited_sections = _limited_sections(section_rows)
    claim_boundary = _public_json(evidence.get("claim_boundary"))
    if not isinstance(claim_boundary, dict):
        claim_boundary = {}
    warnings = [
        item
        for item in [
            *_warning_rows(source_manifest.get("warnings")),
            *_warning_rows(evidence.get("warnings")),
        ]
    ]
    warnings.sort(key=_warning_sort_key)
    hard_rows = [
        cast(JsonDict, _public_json(row))
        for row in _dict_rows(hard_observations.get("rows"))
    ]
    selected_pair = _trajectory_case_pair(
        _dict_value(trajectory_observations.get("headline_pair"))
    )
    limitations = _case_limitations(section_rows)

    return {
        "schema": "prompt_control_lab.peoc_case_study.v1",
        "evidence_source": "REAL PEOC BUNDLE",
        "evidence_origin": "real",
        "manifest_hash": bundle.get("manifest_sha256"),
        "source_manifest_sha256": _sha256_bytes(
            _strict_json_text(source_manifest).encode("utf-8")
        ),
        "status_counts": status_counts,
        "hard_summary": {
            "status": hard.get("status"),
            "metric": hard_observations.get("metric"),
            "row_count": hard_observations.get("row_count"),
            "valid_row_count": hard_observations.get("valid_row_count"),
            "excluded_row_count": hard_observations.get("excluded_row_count"),
            "models": hard_observations.get("models", []),
            "tasks": hard_observations.get("tasks", []),
            "methods": hard_observations.get("methods", []),
        },
        "hard_method_rows": hard_rows,
        "selected_trajectory_pair": selected_pair,
        "stage_validation": {
            "status": stage.get("status"),
            "display_status": stage.get("display_status"),
            "verdict": stage_observations.get("verdict"),
            "held_spearman_rho": stage_observations.get("held_spearman_rho"),
            "held_bootstrap_ci": stage_observations.get("held_bootstrap_ci"),
            "source": _case_source(
                _dict_value(stage_observations.get("source"))
            ),
        },
        "limited_sections": limited_sections,
        "source_inventory": source_inventory,
        "safe_claim": _safe_claim(section_rows, selected_pair),
        "safe_claim_zh": _safe_claim_zh(section_rows, selected_pair),
        "limitations": limitations,
        "limitations_zh": _case_limitations_zh(section_rows),
        "warnings": [_public_json(warning) for warning in warnings],
        "claim_boundary": claim_boundary,
    }


def _status_counts(sections: JsonDict) -> JsonDict:
    counts: JsonDict = {
        "available": 0,
        "failed_validation": 0,
        "missing": 0,
        "partial": 0,
        "unusable": 0,
    }
    for section in sections.values():
        if not isinstance(section, dict):
            continue
        status = str(section.get("status", "unusable"))
        counts[status] = int(counts.get(status, 0)) + 1
    return counts


def _limited_sections(sections: JsonDict) -> list[JsonDict]:
    rows: list[JsonDict] = []
    for name, value in sorted(sections.items()):
        if not isinstance(value, dict) or value.get("status") == "available":
            continue
        limitations = value.get("limitations")
        limitation_values = limitations if isinstance(limitations, list) else []
        status = str(value.get("status", "unusable"))
        rows.append(
            {
                "section": name,
                "origin": value.get("origin"),
                "status": status,
                "display_status": value.get("display_status"),
                "limitation": (
                    str(limitation_values[0])
                    if limitation_values
                    else "This evidence section is not available for a positive claim."
                ),
                "limitation_zh": _status_limitation_zh(status),
            }
        )
    return rows


def _trajectory_case_pair(pair: JsonDict) -> JsonDict:
    if not pair:
        return {}
    return {
        "model": pair.get("model"),
        "normalized_model": pair.get("normalized_model"),
        "seed": pair.get("seed"),
        "stationary": _trajectory_case_arm(
            _dict_value(pair.get("stationary"))
        ),
        "heterogeneous": _trajectory_case_arm(
            _dict_value(pair.get("heterogeneous"))
        ),
    }


def _trajectory_case_arm(entry: JsonDict) -> JsonDict:
    if not entry:
        return {}
    summary = _dict_value(entry.get("summary"))
    source = _case_source(_dict_value(entry.get("source")))
    return {
        "status": entry.get("status"),
        "relative_path": source.get("relative_path"),
        "sha256": source.get("sha256"),
        "bytes": source.get("bytes"),
        "hidden_dim": summary.get("hidden_dim"),
        "alpha_emp_mean": summary.get("alpha_emp_mean"),
        "alpha_emp_std": summary.get("alpha_emp_std"),
        "R2_mean": summary.get("R2_mean"),
        "R2_std": summary.get("R2_std"),
        "n_streams": summary.get("n_streams"),
        "n_prompts": summary.get("n_prompts"),
        "binary_references": [
            _case_source(reference)
            for reference in _dict_rows(entry.get("binary_references"))
        ],
    }


def _case_source(source: JsonDict) -> JsonDict:
    return {
        "role": source.get("role"),
        "relative_path": source.get("relative_path"),
        "sha256": source.get("sha256"),
        "bytes": source.get("bytes"),
    }


def _safe_claim(sections: JsonDict, pair: JsonDict) -> str:
    statements = [
        (
            "This bounded case study reports the imported PEOC measurements and "
            "their recorded limitations; it is not a universal benchmark."
        )
    ]
    hard = _section_dict(sections, "hard_evaluation")
    if hard.get("status") == "available":
        statements.append(
            "The hard-test summary contains task-, model-, and method-specific results."
        )
    stationary = _dict_value(pair.get("stationary"))
    heterogeneous = _dict_value(pair.get("heterogeneous"))
    stationary_alpha = stationary.get("alpha_emp_mean")
    heterogeneous_alpha = heterogeneous.get("alpha_emp_mean")
    if (
        _is_number(stationary_alpha)
        and _is_number(heterogeneous_alpha)
        and stationary_alpha > heterogeneous_alpha
    ):
        statements.append(
            "For the selected paired summaries, stationary arithmetic traces report "
            "a stronger fitted decay signature than heterogeneous GSM8K traces."
        )
    stage = _section_dict(sections, "stage_heterogeneity")
    if stage.get("status") == "failed_validation":
        statements.append("The stage-heterogeneity validation reported FAIL.")
    soft = _section_dict(sections, "soft_evaluation")
    if soft.get("status") == "unusable":
        statements.append("The segmented soft summary is unusable for a positive claim.")
    return " ".join(statements)


def _safe_claim_zh(sections: JsonDict, pair: JsonDict) -> str:
    statements = [
        "本案例只报告导入的 PEOC 测量结果及其限制, 不代表通用基准结论。"
    ]
    if _section_dict(sections, "hard_evaluation").get("status") == "available":
        statements.append("Hard-test 汇总提供了任务、模型和方法层面的具体结果。")
    stationary = _dict_value(pair.get("stationary"))
    heterogeneous = _dict_value(pair.get("heterogeneous"))
    stationary_alpha = stationary.get("alpha_emp_mean")
    heterogeneous_alpha = heterogeneous.get("alpha_emp_mean")
    if (
        _is_number(stationary_alpha)
        and _is_number(heterogeneous_alpha)
        and stationary_alpha > heterogeneous_alpha
    ):
        statements.append(
            "在选中的配对汇总中, 平稳算术轨迹的拟合衰减信号强于异质 GSM8K 轨迹。"
        )
    if _section_dict(sections, "stage_heterogeneity").get("status") == (
        "failed_validation"
    ):
        statements.append("阶段异质性验证的记录结果为 FAIL。")
    if _section_dict(sections, "soft_evaluation").get("status") == "unusable":
        statements.append("分段 soft 汇总不能用于支持正向结论。")
    return "".join(statements)


def _case_limitations(sections: JsonDict) -> list[str]:
    values = [
        "The import packages existing evidence; it introduces no new scientific result.",
        (
            "Diagnostics are bounded to the imported tasks, models, seeds, "
            "and recorded protocol."
        ),
        (
            "Trajectory decay is diagnostic evidence, not proof of universal "
            "turnpike behavior or operational stability."
        ),
    ]
    for section in sections.values():
        if not isinstance(section, dict):
            continue
        limitations = section.get("limitations")
        if not isinstance(limitations, list):
            continue
        values.extend(str(value) for value in limitations)
    return list(dict.fromkeys(values))


def _case_limitations_zh(sections: JsonDict) -> list[str]:
    values = [
        "该导入流程只整理已有证据, 不产生新的科学结果。",
        "诊断结论只适用于导入记录中的任务、模型、随机种子和实验协议。",
        "轨迹衰减属于诊断信号, 不等于普遍 turnpike 规律或运行稳定性的证明。",
    ]
    values.extend(
        _status_limitation_zh(str(section.get("status", "unusable")))
        for section in sections.values()
        if isinstance(section, dict) and section.get("status") != "available"
    )
    return list(dict.fromkeys(values))


def _status_limitation_zh(status: str) -> str:
    return {
        "failed_validation": "该部分的真实验证结果未通过, 不能作为正向证据。",
        "missing": "导入的 PEOC bundle 中没有发现该部分的证据。",
        "partial": "该部分只有部分证据可用, 仍需人工检查缺失或损坏来源。",
        "unusable": "该部分虽然有真实来源, 但当前数据不可用于支持正向结论。",
    }.get(status, "该证据部分当前不能用于支持正向结论。")


def _section_dict(sections: JsonDict, name: str) -> JsonDict:
    return _dict_value(sections.get(name))


def _dict_value(value: object) -> JsonDict:
    return value if isinstance(value, dict) else {}


def _dict_rows(value: object) -> list[JsonDict]:
    if not isinstance(value, list):
        return []
    return [cast(JsonDict, row) for row in value if isinstance(row, dict)]


def _warning_rows(value: object) -> list[JsonDict]:
    return _dict_rows(value)


def _public_json(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): _public_json(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) != "resolved_path"
        }
    if isinstance(value, list):
        return [_public_json(item) for item in value]
    return value


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _build_hard_section(
    root: Path,
    sources: list[JsonDict],
    warnings: list[JsonDict],
) -> JsonDict:
    source = _first_source(sources, "hard_test_summary")
    if source is None:
        raise ValueError("Missing required hard-test summary source in source manifest")
    raw = _read_required_json(root, source, label="hard-test summary")
    if not isinstance(raw, dict) or not isinstance(raw.get("summary"), list):
        path = _source_path(root, source, label="hard-test summary")
        msg = f"Invalid required hard-test summary {path}: expected top-level summary list"
        raise ValueError(msg)

    relative_path = _relative_path(source)
    normalized = _finite_json(
        raw,
        warnings,
        source_role="hard_test_summary",
        relative_path=relative_path,
    )
    payload = cast(JsonDict, normalized)
    summary = cast(list[object], payload["summary"])
    valid_rows: list[JsonDict] = []
    excluded_rows: list[JsonDict] = []
    for index, row in enumerate(summary):
        normalized_row = row if isinstance(row, dict) else {"value": row}
        raw_row = raw["summary"][index]
        reason = _summary_row_exclusion_reason(raw_row, normalized_row)
        if reason is None:
            valid_rows.append(cast(JsonDict, normalized_row))
        else:
            excluded_rows.append(
                {
                    "index": index,
                    "reason": reason,
                    "row": normalized_row,
                }
            )

    tests = payload.get("tests")
    source_tests = tests if isinstance(tests, list) else []
    status = "available" if valid_rows else "unusable"
    limitations = [
        "Aggregate hard-test results do not establish universal prompt superiority."
    ]
    if excluded_rows:
        limitations.append("Rows without a finite mean and positive sample count were excluded.")
    return _section(
        origin="real",
        status=status,
        source_roles=["hard_test_summary"],
        observations={
            "source": _source_reference(source),
            "metric": payload.get("metric"),
            "row_count": len(summary),
            "valid_row_count": len(valid_rows),
            "excluded_row_count": len(excluded_rows),
            "models": _distinct_strings(valid_rows, "model"),
            "tasks": _distinct_strings(valid_rows, "task"),
            "methods": _distinct_strings(valid_rows, "method"),
            "rows": valid_rows,
            "excluded_rows": excluded_rows,
            "source_tests": source_tests,
        },
        limitations=limitations,
    )


def _build_soft_section(
    root: Path,
    sources: list[JsonDict],
    warnings: list[JsonDict],
) -> JsonDict:
    source = _first_source(sources, "soft_segmented_summary")
    if source is None:
        return _missing_section(
            "No segmented soft-evaluation summary was discovered in this PEOC bundle."
        )
    raw, error, warning_code = _read_optional_json(root, source)
    if error is not None or not isinstance(raw, dict) or not isinstance(raw.get("summary"), list):
        return _invalid_optional_section(
            source,
            warnings,
            error or "expected top-level summary list",
            warning_code=warning_code or "invalid_optional_source",
        )

    normalized = _finite_json(
        raw,
        warnings,
        source_role="soft_segmented_summary",
        relative_path=_relative_path(source),
    )
    payload = cast(JsonDict, normalized)
    summary = cast(list[object], payload["summary"])
    valid_rows: list[JsonDict] = []
    excluded_rows: list[JsonDict] = []
    zero_count_rows = 0
    for index, row in enumerate(summary):
        normalized_row = row if isinstance(row, dict) else {"value": row}
        raw_row = raw["summary"][index]
        reason = _summary_row_exclusion_reason(raw_row, normalized_row)
        if reason is None:
            valid_rows.append(cast(JsonDict, normalized_row))
        else:
            if reason == "non_positive_n":
                zero_count_rows += 1
            excluded_rows.append({"index": index, "reason": reason, "row": normalized_row})

    status = "available" if valid_rows else "unusable"
    limitations = [
        "Segmented soft evaluation is unusable when no row has a positive sample count."
        if not valid_rows
        else "Soft evaluation remains specific to the imported tasks, models, and protocol."
    ]
    return _section(
        origin="real",
        status=status,
        source_roles=["soft_segmented_summary"],
        observations={
            "source": _source_reference(source),
            "metric": payload.get("metric"),
            "summary_row_count": len(summary),
            "valid_row_count": len(valid_rows),
            "zero_count_row_count": zero_count_rows,
            "rows": summary,
            "valid_rows": valid_rows,
            "excluded_rows": excluded_rows,
            "source_tests": payload.get("tests") if isinstance(payload.get("tests"), list) else [],
        },
        limitations=limitations,
    )


def _build_trajectory_section(
    root: Path,
    sources: list[JsonDict],
    warnings: list[JsonDict],
) -> JsonDict:
    trajectory_sources = [
        source
        for source in sources
        if source.get("role") in {"trajectory_stationary", "trajectory_heterogeneous"}
    ]
    binary_sources = [
        source for source in sources if source.get("role") == "trajectory_binary"
    ]
    if not trajectory_sources:
        return _missing_section("No trajectory summary was discovered in this PEOC bundle.")

    entries: list[JsonDict] = []
    grouped: dict[tuple[str, int], dict[str, JsonDict]] = {}
    binary_results = _verify_trajectory_binaries(root, binary_sources, warnings)
    for source in trajectory_sources:
        role = str(source.get("role"))
        binary_key = Path(_relative_path(source)).as_posix()
        binary_references = binary_results.valid.get(binary_key, [])
        invalid_binary_references = binary_results.invalid.get(binary_key, [])
        raw, error, warning_code = _read_optional_json(root, source)
        if error is not None or not isinstance(raw, dict):
            entries.append(
                _invalid_trajectory_entry(
                    source,
                    warnings,
                    error or "expected a JSON object",
                    warning_code=warning_code or "invalid_optional_source",
                    binary_references=binary_references,
                    invalid_binary_references=invalid_binary_references,
                )
            )
            continue
        normalized = _finite_json(
            raw,
            warnings,
            source_role=role,
            relative_path=_relative_path(source),
        )
        payload = cast(JsonDict, normalized)
        model = payload.get("model")
        seed, seed_source = _trajectory_seed(payload, source)
        if not isinstance(model, str) or not model.strip() or seed is None:
            entries.append(
                _invalid_trajectory_entry(
                    source,
                    warnings,
                    "trajectory summary requires a model and integer seed or _s<seed> filename",
                    warning_code="invalid_optional_source",
                    binary_references=binary_references,
                    invalid_binary_references=invalid_binary_references,
                )
            )
            continue
        normalized_model = _normalize_model_id(model)
        entry: JsonDict = {
            "origin": "real",
            "status": "available",
            "display_status": _display_status("real", "available"),
            "role": role,
            "source": _source_reference(source),
            "model": model,
            "normalized_model": normalized_model,
            "seed": seed,
            "seed_source": seed_source,
            "summary": payload,
            "binary_references": binary_references,
            "invalid_binary_references": invalid_binary_references,
        }
        entries.append(entry)
        grouped.setdefault((normalized_model, seed), {})[role] = entry

    pairs: list[JsonDict] = []
    for (normalized_model, seed), pair_entries in sorted(grouped.items()):
        stationary = pair_entries.get("trajectory_stationary")
        heterogeneous = pair_entries.get("trajectory_heterogeneous")
        if stationary is None or heterogeneous is None:
            continue
        pairs.append(
            {
                "model": stationary["model"],
                "normalized_model": normalized_model,
                "seed": seed,
                "stationary": stationary,
                "heterogeneous": heterogeneous,
            }
        )
    headline_pair = _headline_trajectory_pair(pairs)
    has_unusable_source = any(entry.get("status") != "available" for entry in entries)
    invalid_binary_references = binary_results.all_invalid
    if headline_pair is None:
        status = "unusable"
    elif has_unusable_source or invalid_binary_references:
        status = "partial"
    else:
        status = "available"
    limitations = [
        "Trajectory decay is a diagnostic signal, not proof of operational model stability.",
        "Sibling NPZ files are referenced and hashed only; they are not loaded or copied.",
    ]
    if headline_pair is None:
        limitations.append("No complete stationary/heterogeneous model-and-seed pair was usable.")
    elif status == "partial":
        limitations.append(
            "A complete pair is available, but at least one discovered trajectory source "
            "or binary reference is unusable."
        )
    return _section(
        origin="real",
        status=status,
        source_roles=sorted(
            {str(source.get("role")) for source in trajectory_sources}
        ),
        observations={
            "entries": entries,
            "pairs": pairs,
            "headline_pair": headline_pair,
            "binary_references": binary_results.all_valid,
            "invalid_binary_references": invalid_binary_references,
        },
        limitations=limitations,
    )


def _build_stage_section(
    root: Path,
    sources: list[JsonDict],
    warnings: list[JsonDict],
) -> JsonDict:
    source = _first_source(sources, "stage_heterogeneity")
    if source is None:
        return _missing_section(
            "No stage-heterogeneity validation summary was discovered in this PEOC bundle."
        )
    raw, error, warning_code = _read_optional_json(root, source)
    if error is not None or not isinstance(raw, dict):
        return _invalid_optional_section(
            source,
            warnings,
            error or "expected a JSON object",
            warning_code=warning_code or "invalid_optional_source",
        )
    normalized = _finite_json(
        raw,
        warnings,
        source_role="stage_heterogeneity",
        relative_path=_relative_path(source),
    )
    payload = cast(JsonDict, normalized)
    verdict = payload.get("verdict")
    normalized_verdict = verdict.upper() if isinstance(verdict, str) else ""
    if normalized_verdict == "FAIL":
        status = "failed_validation"
    elif normalized_verdict == "PASS":
        status = "available"
    else:
        status = "unusable"
    return _section(
        origin="real",
        status=status,
        source_roles=["stage_heterogeneity"],
        observations={
            "source": _source_reference(source),
            "verdict": verdict,
            "held_spearman_rho": payload.get("held_spearman_rho"),
            "held_bootstrap_ci": payload.get("held_bootstrap_ci"),
            "cells": payload.get("cells"),
            "observed_keys": sorted(payload),
            "data": payload,
        },
        limitations=[
            (
                "A failed validation verdict is retained as negative evidence "
                "and does not support the diagnostic."
            )
            if status == "failed_validation"
            else "Stage-heterogeneity results apply only to the imported validation design."
        ],
    )


def _section(
    *,
    origin: str,
    status: str,
    source_roles: list[str],
    observations: JsonDict,
    limitations: list[str],
) -> JsonDict:
    return {
        "origin": origin,
        "status": status,
        "display_status": _display_status(origin, status),
        "source_roles": source_roles,
        "observations": observations,
        "limitations": limitations,
    }


def _missing_section(limitation: str) -> JsonDict:
    return _section(
        origin="none",
        status="missing",
        source_roles=[],
        observations={},
        limitations=[limitation, "No synthetic substitute was created."],
    )


def _invalid_optional_section(
    source: JsonDict,
    warnings: list[JsonDict],
    error: str,
    *,
    warning_code: str,
) -> JsonDict:
    role = str(source.get("role", "optional_source"))
    _append_optional_warning(warnings, source, error, code=warning_code)
    return _section(
        origin="real",
        status="unusable",
        source_roles=[role],
        observations={"source": _source_reference(source), "error": error},
        limitations=[
            "The real source was discovered but could not be parsed as usable evidence.",
            "No positive evidence was inferred from the invalid source.",
        ],
    )


def _invalid_trajectory_entry(
    source: JsonDict,
    warnings: list[JsonDict],
    error: str,
    *,
    warning_code: str,
    binary_references: list[JsonDict],
    invalid_binary_references: list[JsonDict],
) -> JsonDict:
    _append_optional_warning(warnings, source, error, code=warning_code)
    return {
        "origin": "real",
        "status": "unusable",
        "display_status": _display_status("real", "unusable"),
        "role": source.get("role"),
        "source": _source_reference(source),
        "error": error,
        "binary_references": binary_references,
        "invalid_binary_references": invalid_binary_references,
    }


def _append_optional_warning(
    warnings: list[JsonDict],
    source: JsonDict,
    error: str,
    *,
    code: str,
) -> None:
    warnings.append(
        {
            "code": code,
            "source_role": str(source.get("role", "optional_source")),
            "relative_path": _relative_path(source),
            "json_path": "$",
            "message": error,
        }
    )


def _manifest_sources(source_manifest: JsonDict) -> list[JsonDict]:
    sources = source_manifest.get("sources")
    if not isinstance(sources, list):
        raise ValueError("PEOC source manifest must contain a sources list")
    return [cast(JsonDict, source) for source in sources if isinstance(source, dict)]


def _first_source(sources: list[JsonDict], role: str) -> JsonDict | None:
    return next((source for source in sources if source.get("role") == role), None)


def _verify_bundle_manifest(
    root: Path,
    sources: list[JsonDict],
    source_manifest: JsonDict,
) -> None:
    source = _first_source(sources, "bundle_manifest")
    if source is None:
        raise ValueError("Missing required bundle manifest source row")
    relative_path = _relative_path(source)
    if relative_path != _MANIFEST.as_posix():
        msg = (
            "Bundle manifest source must reference README_MANIFEST.md, "
            f"not {relative_path or '<missing>'}"
        )
        raise ValueError(msg)
    path = _source_path(root, source, label="bundle manifest")
    try:
        observed_size, observed_sha256 = _file_integrity(path)
    except OSError as exc:
        msg = f"bundle manifest source changed after discovery: {path}: {exc}"
        raise ValueError(msg) from exc
    integrity_error = _source_integrity_error(
        source,
        observed_size,
        observed_sha256,
    )
    if integrity_error is not None:
        msg = f"bundle manifest source changed after discovery: {path}: {integrity_error}"
        raise ValueError(msg)

    bundle = source_manifest.get("bundle")
    if not isinstance(bundle, dict):
        raise ValueError("PEOC source manifest must contain bundle metadata")
    manifest_relative_path = bundle.get("manifest_relative_path")
    if manifest_relative_path != _MANIFEST.as_posix():
        msg = (
            "Bundle metadata must reference README_MANIFEST.md, "
            f"not {manifest_relative_path or '<missing>'}"
        )
        raise ValueError(msg)
    declared_sha256 = bundle.get("manifest_sha256")
    if declared_sha256 != observed_sha256:
        msg = (
            "bundle manifest hash changed after discovery: "
            f"expected {declared_sha256}, observed {observed_sha256}"
        )
        raise ValueError(msg)


def _read_required_json(root: Path, source: JsonDict, *, label: str) -> object:
    path = _source_path(root, source, label=label)
    try:
        data = path.read_bytes()
    except OSError as exc:
        msg = f"{label} source changed after discovery: {path}: {exc}"
        raise ValueError(msg) from exc
    integrity_error = _source_integrity_error(source, len(data), _sha256_bytes(data))
    if integrity_error is not None:
        msg = f"{label} source changed after discovery: {path}: {integrity_error}"
        raise ValueError(msg)
    try:
        return json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        msg = f"Invalid required {label} {path}: {exc}"
        raise ValueError(msg) from exc


def _read_optional_json(
    root: Path,
    source: JsonDict,
) -> tuple[object | None, str | None, str | None]:
    role = str(source.get("role", "optional source"))
    try:
        path = _source_path(root, source, label=role)
    except ValueError as exc:
        return None, str(exc), "invalid_optional_source"
    try:
        data = path.read_bytes()
    except OSError as exc:
        message = (
            f"{role} source changed after discovery: {_relative_path(source)}: "
            f"{type(exc).__name__}"
        )
        return None, message, "source_integrity_mismatch"
    integrity_error = _source_integrity_error(source, len(data), _sha256_bytes(data))
    if integrity_error is not None:
        message = (
            f"{role} source changed after discovery: {_relative_path(source)}: "
            f"{integrity_error}"
        )
        return None, message, "source_integrity_mismatch"
    try:
        return json.loads(data.decode("utf-8-sig")), None, None
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, str(exc), "invalid_optional_source"


def _source_path(root: Path, source: JsonDict, *, label: str) -> Path:
    relative_path = source.get("relative_path")
    if not isinstance(relative_path, str) or not relative_path:
        msg = f"{label} source is missing relative_path"
        raise ValueError(msg)
    return _resolve_bundle_path(root, Path(relative_path), label=label)


def _relative_path(source: JsonDict) -> str:
    value = source.get("relative_path")
    return str(value) if value is not None else ""


def _source_reference(source: JsonDict) -> JsonDict:
    keys = (
        "role",
        "relative_path",
        "resolved_path",
        "bytes",
        "sha256",
        "media_type",
        "selection",
        "copied_path",
    )
    return {key: source.get(key) for key in keys}


def _source_integrity_error(
    source: JsonDict,
    observed_size: int,
    observed_sha256: str,
) -> str | None:
    differences: list[str] = []
    expected_size = source.get("bytes")
    if isinstance(expected_size, int) and not isinstance(expected_size, bool):
        if expected_size != observed_size:
            differences.append(f"bytes expected {expected_size}, observed {observed_size}")
    elif expected_size is not None:
        differences.append(f"bytes metadata is invalid: {expected_size!r}")

    expected_sha256 = source.get("sha256")
    if not isinstance(expected_sha256, str) or not expected_sha256:
        differences.append("sha256 metadata is unavailable")
    elif expected_sha256 != observed_sha256:
        differences.append(
            f"sha256 expected {expected_sha256}, observed {observed_sha256}"
        )
    return "; ".join(differences) if differences else None


def _finite_json(
    value: object,
    warnings: list[JsonDict],
    *,
    source_role: str,
    relative_path: str | None,
    json_path: str = "$",
) -> object:
    if isinstance(value, float) and not math.isfinite(value):
        warnings.append(
            {
                "code": "non_finite_value",
                "source_role": source_role,
                "relative_path": relative_path,
                "json_path": json_path,
                "message": "Non-finite numeric value was normalized to null.",
            }
        )
        return None
    if isinstance(value, dict):
        return {
            str(key): _finite_json(
                item,
                warnings,
                source_role=source_role,
                relative_path=relative_path,
                json_path=f"{json_path}.{key}",
            )
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, list):
        return [
            _finite_json(
                item,
                warnings,
                source_role=source_role,
                relative_path=relative_path,
                json_path=f"{json_path}[{index}]",
            )
            for index, item in enumerate(value)
        ]
    return value


def _summary_row_exclusion_reason(raw_row: object, normalized_row: object) -> str | None:
    if not isinstance(raw_row, dict) or not isinstance(normalized_row, dict):
        return "row_not_object"
    raw_n = raw_row.get("n")
    n = normalized_row.get("n")
    if isinstance(raw_n, float) and not math.isfinite(raw_n):
        return "non_finite_n"
    if not _is_number(n):
        return "invalid_n"
    if n <= 0:
        return "non_positive_n"
    raw_mean = raw_row.get("mean")
    mean = normalized_row.get("mean")
    if isinstance(raw_mean, float) and not math.isfinite(raw_mean):
        return "non_finite_mean"
    if not _is_number(mean):
        return "invalid_mean"
    return None


def _is_number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _distinct_strings(rows: list[JsonDict], key: str) -> list[str]:
    return sorted(
        {
            value
            for row in rows
            if isinstance((value := row.get(key)), str) and value
        }
    )


def _trajectory_seed(payload: JsonDict, source: JsonDict) -> tuple[int | None, str | None]:
    value = payload.get("seed")
    if isinstance(value, int) and not isinstance(value, bool):
        return value, "json"
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value), "json"
    match = _SEED_PATTERN.search(Path(_relative_path(source)).name)
    if match is not None:
        return int(match.group(1)), "filename"
    return None, None


def _normalize_model_id(model: str) -> str:
    return model.strip().replace("__", "/").lower()


def _verify_trajectory_binaries(
    root: Path,
    binary_sources: list[JsonDict],
    warnings: list[JsonDict],
) -> _TrajectoryBinaryResults:
    valid: dict[str, list[JsonDict]] = {}
    invalid: dict[str, list[JsonDict]] = {}
    all_valid: list[JsonDict] = []
    all_invalid: list[JsonDict] = []
    ordered_sources = sorted(
        binary_sources,
        key=lambda source: _relative_path(source),
    )
    for source in ordered_sources:
        owner = Path(_relative_path(source)).with_suffix(".json").as_posix()
        try:
            path = _source_path(root, source, label="trajectory binary")
            observed_size, observed_sha256 = _file_integrity(path)
            integrity_error = _source_integrity_error(
                source,
                observed_size,
                observed_sha256,
            )
        except (OSError, ValueError) as exc:
            integrity_error = f"{type(exc).__name__}: source could not be read or resolved"
        if integrity_error is None:
            reference = _source_reference(source)
            valid.setdefault(owner, []).append(reference)
            all_valid.append(reference)
            continue

        error = (
            "trajectory binary source changed after discovery: "
            f"{_relative_path(source)}: "
            f"{integrity_error}"
        )
        _append_optional_warning(
            warnings,
            source,
            error,
            code="source_integrity_mismatch",
        )
        unusable_reference: JsonDict = {
            "origin": "real",
            "status": "unusable",
            "display_status": _display_status("real", "unusable"),
            "source": _source_reference(source),
            "error": error,
        }
        invalid.setdefault(owner, []).append(unusable_reference)
        all_invalid.append(unusable_reference)
    return _TrajectoryBinaryResults(
        valid=valid,
        invalid=invalid,
        all_valid=all_valid,
        all_invalid=all_invalid,
    )


def _headline_trajectory_pair(pairs: list[JsonDict]) -> JsonDict | None:
    preferred = next(
        (
            pair
            for pair in pairs
            if pair.get("seed") == 0
            and "qwen2.5-7b-instruct" in str(pair.get("normalized_model", ""))
        ),
        None,
    )
    return preferred or (pairs[0] if pairs else None)


def _display_status(origin: str, status: str) -> str:
    if origin == "none":
        return status.upper().replace("_", " ")
    return f"{origin.upper()} / {status.upper().replace('_', ' ')}"


def _warning_sort_key(warning: JsonDict) -> tuple[str, str, str, str, str]:
    return (
        str(warning.get("code", "")),
        str(warning.get("source_role", "")),
        str(warning.get("relative_path", "")),
        str(warning.get("json_path", "")),
        str(warning.get("message", "")),
    )


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
    size, sha256 = _file_integrity(path)
    return {
        "role": role,
        "relative_path": path.relative_to(root).as_posix(),
        "resolved_path": str(path),
        "bytes": size,
        "sha256": sha256,
        "media_type": media_type,
        "selection": selection,
        "copied_path": None,
    }
