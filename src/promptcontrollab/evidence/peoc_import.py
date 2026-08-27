"""Discover source files in a real PEOC evidence bundle."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from contextlib import suppress
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

from promptcontrollab.core.files import JsonDict
from promptcontrollab.core.version import __version__
from promptcontrollab.evidence.peoc.analysis import (
    _build_case_study,
    _build_hard_section,
    _build_soft_section,
    _build_stage_section,
    _build_trajectory_section,
    _finite_json,
    _is_relative_to,
    _manifest_sources,
    _missing_section,
    _relative_path,
    _require_file,
    _resolve_bundle_path,
    _resolve_existing_sibling,
    _source_integrity_error,
    _source_path,
    _source_row,
    _trajectory_role,
    _trajectory_sources,
    _verify_bundle_manifest,
    _warning_sort_key,
)
from promptcontrollab.evidence.peoc.common import (
    PeocSourceOverrides as PeocSourceOverrides,
)
from promptcontrollab.evidence.peoc.common import (
    _file_integrity,
    _strict_json_text,
)
from promptcontrollab.evidence.peoc.constants import (
    CHUNK_SIZE,
    GENERATED_ARTIFACTS,
    MANIFEST,
    PORTABLE_EXTENSIONS,
    REQUIRED_SOURCE_ROLES,
    SEED_PATTERN,
)
from promptcontrollab.evidence.peoc.constants import (
    HARD_SUMMARY as HARD_SUMMARY,
)
from promptcontrollab.evidence.peoc.constants import (
    HETEROGENEITY_SUMMARY as HETEROGENEITY_SUMMARY,
)
from promptcontrollab.evidence.peoc.constants import (
    MAX_PORTABLE_FILE_BYTES as MAX_PORTABLE_FILE_BYTES,
)
from promptcontrollab.evidence.peoc.constants import (
    MAX_PORTABLE_TOTAL_BYTES as MAX_PORTABLE_TOTAL_BYTES,
)
from promptcontrollab.evidence.peoc.constants import (
    SOFT_SUMMARY as SOFT_SUMMARY,
)
from promptcontrollab.evidence.peoc.constants import (
    TRAJECTORY_ROOT as TRAJECTORY_ROOT,
)
from promptcontrollab.evidence.peoc_reporting import (
    render_peoc_case_study_html,
    render_peoc_case_study_markdown,
)

_MANIFEST = MANIFEST
_CHUNK_SIZE = CHUNK_SIZE
_SEED_PATTERN = SEED_PATTERN
_GENERATED_ARTIFACTS = GENERATED_ARTIFACTS
_PORTABLE_EXTENSIONS = PORTABLE_EXTENSIONS
_REQUIRED_SOURCE_ROLES = REQUIRED_SOURCE_ROLES


@dataclass(frozen=True)
class PeocImportOptions:
    """Options for importing a real PEOC evidence bundle."""

    bundle_root: Path
    out_dir: Path
    overrides: PeocSourceOverrides = PeocSourceOverrides()  # noqa: RUF009
    portable: bool = False
    language: str = "en"
    overwrite: bool = False


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
    source_guard: _DirectoryGuard
    move_outcome: str


class _BackupMoveError(Exception):
    def __init__(
        self,
        original: Exception,
        artifact: _BackupArtifact,
    ) -> None:
        super().__init__(str(original))
        self.original = original
        self.artifact = artifact


@dataclass(frozen=True)
class _DirectoryGuard:
    root_resolved: Path
    root_device: int
    root_inode: int
    parent_resolved: Path
    parent_device: int
    parent_inode: int


@dataclass(frozen=True)
class _TrustedDirectoryGuard:
    path: Path
    resolved: Path
    device: int
    inode: int
    parent_resolved: Path
    parent_device: int
    parent_inode: int


@dataclass(frozen=True)
class _TransactionGuard:
    transaction: _TrustedDirectoryGuard
    backup_root: _TrustedDirectoryGuard


def _sha256_file(path: Path) -> str:
    return _file_integrity(path)[1]


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
    previous_portable_targets = _registered_portable_targets(out_dir) if options.overwrite else []

    out_dir.parent.mkdir(parents=True, exist_ok=True)
    transaction_dir = Path(
        tempfile.mkdtemp(
            dir=out_dir.parent,
            prefix=f".{out_dir.name}.peoc-import-",
        )
    )
    backup_root = transaction_dir / "backup"
    try:
        backup_root.mkdir()
        transaction_guard = _capture_transaction_guard(
            transaction_dir,
            backup_root,
        )
    except Exception:
        with suppress(OSError):
            shutil.rmtree(transaction_dir)
        raise
    backups: list[_BackupArtifact] = []
    try:
        staging_dir = transaction_dir / "payload"
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
            backup_root=backup_root,
            transaction_guard=transaction_guard,
            backups=backups,
        )
    except Exception as exc:
        if backups:
            raise _manual_recovery_error(
                exc,
                transaction_dir,
                transaction_guard,
                backups,
            ) from exc
        with suppress(OSError):
            shutil.rmtree(transaction_dir)
        raise
    else:
        try:
            _validate_transaction_guard(transaction_guard)
            shutil.rmtree(transaction_dir)
        except (OSError, ValueError) as exc:
            if backups:
                raise _manual_recovery_error(
                    exc,
                    transaction_dir,
                    transaction_guard,
                    backups,
                    commit_completed=True,
                ) from exc
            raise

    artifact_paths = {name: str(out_dir / name) for name in _GENERATED_ARTIFACTS}
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


def _validate_import_output(
    root: Path,
    out_dir: Path,
    source_manifest: JsonDict,
) -> None:
    if out_dir == root:
        raise ValueError("PEOC import output directory must not be the bundle root")
    if _is_relative_to(out_dir, root):
        raise ValueError("PEOC import output directory must not be inside the source bundle")
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
        str(out_dir / name) for name in _GENERATED_ARTIFACTS if (out_dir / name).is_dir()
    ]
    if directory_collisions:
        joined = ", ".join(directory_collisions)
        raise ValueError(
            "Generated PEOC artifact paths collide with directories and cannot "
            f"be replaced: {joined}"
        )
    existing = [str(out_dir / name) for name in _GENERATED_ARTIFACTS if (out_dir / name).exists()]
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
    backup_root: Path,
    transaction_guard: _TransactionGuard,
    backups: list[_BackupArtifact],
) -> None:
    """Commit a staged PEOC import with rollback-safe destination handling."""

    staged_files = sorted(
        (path for path in staging_dir.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(staging_dir).as_posix(),
    )
    targets = [(source, out_dir / source.relative_to(staging_dir)) for source in staged_files]
    registered_portable_targets = {
        registered.path: registered for registered in previous_portable_targets
    }
    _validate_registered_portable_targets(previous_portable_targets)
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
        if (registered.path.is_file() and registered.path.resolve() not in staged_destinations)
    ]

    placed: list[_PlacedArtifact] = []
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
                    backup_root=backup_root,
                    transaction_guard=transaction_guard,
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
                        backup_root=backup_root,
                        transaction_guard=transaction_guard,
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
        _validate_new_artifacts_for_commit(out_dir, placed)
        _validate_backups_for_cleanup(
            backup_root,
            transaction_guard,
            backups,
        )
    except Exception as exc:
        original_failure = exc
        if isinstance(exc, _BackupMoveError):
            if exc.artifact not in backups:
                backups.append(exc.artifact)
            original_failure = exc.original
        for artifact in reversed(placed):
            with suppress(OSError):
                _unlink_if_owned(artifact)
        for directory in reversed(created_directories):
            with suppress(OSError):
                directory.rmdir()
        if original_failure is exc:
            raise
        raise original_failure from exc
    _prune_empty_output_directories(
        [registered.path.parent for registered in obsolete_targets],
        out_dir,
    )


def _validate_registered_portable_targets(
    targets: list[_RegisteredPortableTarget],
) -> None:
    for registered in targets:
        if not registered.path.exists():
            continue
        identity = _capture_file_identity(registered.path)
        if identity.size != registered.size or identity.sha256 != registered.sha256:
            raise ValueError(
                "Registered portable target was modified and does not match the "
                f"previous source_manifest.json: {registered.path}"
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
    """Load and validate portable targets registered by an earlier import."""

    source_path = out_dir / "source"
    if not source_path.exists():
        return []
    source_root = source_path.resolve()
    if source_path.is_symlink() or not _is_relative_to(source_root, out_dir):
        raise ValueError(f"Existing portable source path resolves outside output: {source_path}")
    if not source_root.is_dir():
        raise ValueError(f"Existing portable source path is not a directory: {source_root}")

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
        if not isinstance(copied_path, str) or not copied_path or "\\" in copied_path:
            raise ValueError("Existing source_manifest.json contains an unsafe copied_path")
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
                f"Existing source_manifest.json contains an unsafe copied_path: {copied_path}"
            )
        if target.is_dir():
            raise ValueError(f"Existing portable copied_path points to a directory: {copied_path}")
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
            raise ValueError(f"PEOC artifact path collides with a directory: {destination}")
        if destination.exists() and not overwrite:
            raise ValueError(
                f"PEOC artifact already exists; pass --overwrite to replace it: {destination}"
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
                raise ValueError(f"PEOC artifact parent path is not a directory: {parent}")
            parent = parent.parent


def _validate_staged_target_path(out_dir: Path, destination: Path) -> None:
    resolved = destination.resolve()
    if not _is_relative_to(resolved, out_dir):
        raise ValueError(f"Staged PEOC artifact escapes output directory: {destination}")


def _capture_directory_guard(
    out_dir: Path,
    destination: Path,
) -> _DirectoryGuard:
    if _path_is_link_or_junction(out_dir):
        raise ValueError(f"PEOC artifact root is a linked directory: {out_dir}")
    root_resolved = out_dir.resolve(strict=True)
    parent_resolved = destination.parent.resolve(strict=True)
    if (
        not out_dir.is_dir()
        or not destination.parent.is_dir()
        or not _is_relative_to(parent_resolved, root_resolved)
    ):
        raise ValueError(f"PEOC artifact parent resolves outside output: {destination.parent}")
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
        raise ValueError(f"Destination parent changed during PEOC import: {destination.parent}")


def _reject_linked_parent_components(out_dir: Path, parent: Path) -> None:
    try:
        relative = parent.relative_to(out_dir)
    except ValueError as exc:
        raise ValueError(f"PEOC artifact parent is outside output: {parent}") from exc
    current = out_dir
    for part in relative.parts:
        current /= part
        if _path_is_link_or_junction(current):
            raise ValueError(f"PEOC artifact parent uses a symbolic link or junction: {current}")


def _path_is_link_or_junction(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(os.path, "isjunction", None)
        return bool(is_junction is not None and is_junction(path))
    except OSError:
        return True


def _capture_trusted_directory(path: Path) -> _TrustedDirectoryGuard:
    parent = path.parent
    if _path_is_link_or_junction(path) or _path_is_link_or_junction(parent):
        raise ValueError(f"PEOC transaction directory is linked: {path}")
    try:
        parent_before = parent.stat()
        path_before = path.stat()
        parent_resolved = parent.resolve(strict=True)
        resolved = path.resolve(strict=True)
        path_after = path.stat()
        parent_after = parent.stat()
    except OSError as exc:
        raise ValueError(f"PEOC transaction directory is unavailable: {path}") from exc
    if not path.is_dir():
        raise ValueError(f"PEOC transaction path is not a directory: {path}")
    if (
        path_before.st_dev != path_after.st_dev
        or path_before.st_ino != path_after.st_ino
        or parent_before.st_dev != parent_after.st_dev
        or parent_before.st_ino != parent_after.st_ino
    ):
        raise ValueError(f"PEOC transaction directory changed: {path}")
    return _TrustedDirectoryGuard(
        path=path,
        resolved=resolved,
        device=path_after.st_dev,
        inode=path_after.st_ino,
        parent_resolved=parent_resolved,
        parent_device=parent_after.st_dev,
        parent_inode=parent_after.st_ino,
    )


def _validate_trusted_directory(expected: _TrustedDirectoryGuard) -> None:
    try:
        observed = _capture_trusted_directory(expected.path)
    except (OSError, ValueError) as exc:
        raise ValueError(
            f"PEOC transaction directory guard is compromised: {expected.path}"
        ) from exc
    if observed != expected:
        raise ValueError(f"PEOC transaction directory guard is compromised: {expected.path}")


def _capture_transaction_guard(
    transaction_dir: Path,
    backup_root: Path,
) -> _TransactionGuard:
    transaction = _capture_trusted_directory(transaction_dir)
    backup = _capture_trusted_directory(backup_root)
    _validate_trusted_directory(transaction)
    _validate_trusted_directory(backup)
    if not _is_relative_to(backup.resolved, transaction.resolved):
        raise ValueError(
            f"PEOC transaction backup root resolves outside the transaction: {backup_root}"
        )
    return _TransactionGuard(transaction=transaction, backup_root=backup)


def _validate_transaction_guard(expected: _TransactionGuard) -> None:
    _validate_trusted_directory(expected.transaction)
    _validate_trusted_directory(expected.backup_root)
    if not _is_relative_to(
        expected.backup_root.resolved,
        expected.transaction.resolved,
    ):
        raise ValueError(
            f"PEOC transaction backup root is outside the transaction: {expected.backup_root.path}"
        )


def _validate_backup_source(
    backup_root: Path,
    transaction_guard: _TransactionGuard,
    artifact: _BackupArtifact,
) -> None:
    _validate_transaction_guard(transaction_guard)
    _validate_directory_guard(
        backup_root,
        artifact.backup,
        artifact.source_guard,
    )
    try:
        resolved = artifact.backup.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"PEOC transaction backup is unavailable: {artifact.backup}") from exc
    if not _is_relative_to(
        resolved,
        transaction_guard.transaction.resolved,
    ) or not _is_relative_to(
        resolved,
        transaction_guard.backup_root.resolved,
    ):
        raise ValueError(f"PEOC transaction backup path is compromised: {artifact.backup}")
    _validate_transaction_guard(transaction_guard)
    _validate_directory_guard(
        backup_root,
        artifact.backup,
        artifact.source_guard,
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
    backup_root: Path,
    transaction_guard: _TransactionGuard,
) -> _BackupArtifact:
    """Move one existing destination to a transaction-scoped backup."""

    directory_guard = _capture_directory_guard(out_dir, destination)
    identity = _capture_file_identity(destination)
    if registered is not None and (
        identity.size != registered.size or identity.sha256 != registered.sha256
    ):
        raise ValueError(
            "Registered portable target was modified and does not match the "
            f"previous source_manifest.json: {destination}"
        )

    _validate_transaction_guard(transaction_guard)
    _validate_staged_target_path(backup_root, backup)
    backup.parent.mkdir(parents=True, exist_ok=True)
    _validate_transaction_guard(transaction_guard)
    source_guard = _capture_directory_guard(backup_root, backup)
    _validate_transaction_guard(transaction_guard)
    _validate_directory_guard(backup_root, backup, source_guard)
    artifact = _BackupArtifact(
        backup=backup,
        destination=destination,
        identity=identity,
        source_guard=source_guard,
        move_outcome="ambiguous",
    )
    try:
        os.replace(destination, backup)
    except Exception as exc:
        raise _BackupMoveError(exc, artifact) from exc
    try:
        _validate_backup_source(backup_root, transaction_guard, artifact)
        backup_matches = _path_matches_file_identity(backup, identity)
        _validate_backup_source(backup_root, transaction_guard, artifact)
        if not backup_matches:
            label = (
                "Registered portable target"
                if registered is not None
                else "Generated PEOC artifact"
            )
            raise ValueError(f"{label} changed during commit while moving to backup: {destination}")
        _validate_directory_guard(out_dir, destination, directory_guard)
    except Exception as exc:
        raise _BackupMoveError(exc, artifact) from exc
    return replace(artifact, move_outcome="verified")


def _validate_backups_for_cleanup(
    backup_root: Path,
    transaction_guard: _TransactionGuard,
    backups: list[_BackupArtifact],
) -> None:
    for artifact in backups:
        _validate_backup_source(backup_root, transaction_guard, artifact)
        backup_matches = _path_matches_file_identity(
            artifact.backup,
            artifact.identity,
        )
        _validate_backup_source(backup_root, transaction_guard, artifact)
        if backup_matches:
            continue
        raise ValueError(
            "PEOC backup changed during commit; racing content remains in the "
            f"transaction at {artifact.backup}"
        )


def _validate_new_artifacts_for_commit(
    out_dir: Path,
    placed: list[_PlacedArtifact],
) -> None:
    for artifact in placed:
        _validate_staged_target_path(out_dir, artifact.path)
        if not _path_matches_file_identity(artifact.path, artifact.identity):
            raise ValueError(
                f"Published PEOC artifact changed before transaction cleanup: {artifact.path}"
            )


def _recorded_backups(
    backups: list[_BackupArtifact],
) -> tuple[_BackupArtifact, ...]:
    unique: dict[Path, _BackupArtifact] = {}
    for artifact in backups:
        unique.setdefault(artifact.backup, artifact)
    return tuple(unique[path] for path in sorted(unique, key=lambda item: item.as_posix()))


def _transaction_guard_status(guard: _TransactionGuard) -> str:
    try:
        _validate_transaction_guard(guard)
    except (OSError, ValueError) as exc:
        return f"compromised ({exc})"
    return "trusted"


def _manual_recovery_error(
    original: Exception,
    transaction_dir: Path,
    transaction_guard: _TransactionGuard,
    backups: list[_BackupArtifact],
    *,
    commit_completed: bool = False,
) -> ValueError:
    recorded = _recorded_backups(backups)
    details = " | ".join(
        (
            f"destination={artifact.destination}; "
            f"backup={artifact.backup}; "
            f"bytes={artifact.identity.size}; "
            f"sha256={artifact.identity.sha256}; "
            f"move_outcome={artifact.move_outcome}"
        )
        for artifact in recorded
    )
    guard_status = _transaction_guard_status(transaction_guard)
    ambiguous_note = ""
    if any(artifact.move_outcome == "ambiguous" for artifact in recorded):
        ambiguous_note = (
            " At least one backup move outcome is ambiguous; manual inspection "
            f"path={transaction_dir}."
        )
    if commit_completed:
        outcome = "PEOC import committed new artifacts but transaction cleanup failed."
    else:
        outcome = (
            f"PEOC import failed safely: {original}. Removal was attempted only for "
            "newly placed artifacts whose destination identity still matched this "
            "transaction."
        )
    return ValueError(
        f"{outcome}{ambiguous_note} No automatic backup restore was attempted; "
        "manual recovery is "
        f"required. transaction_dir={transaction_dir}; "
        f"backup_root={transaction_guard.backup_root.path}; "
        f"transaction_guard={guard_status}; "
        f"recorded_backups={details or '<none>'}"
    )


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
        raise ValueError(f"Portable fallback copy verification failed for {destination}")
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
        raise ValueError(f"Published PEOC artifact changed during commit: {destination}")
    try:
        resolved = destination.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"Published PEOC artifact became unavailable: {destination}") from exc
    if not _is_relative_to(resolved, directory_guard.root_resolved):
        raise ValueError(f"Published PEOC artifact escaped output directory: {destination}")


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
    """Copy allowlisted PEOC sources into a self-contained portable bundle."""

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
                raise ValueError(f"{role} source changed before portable copy: {integrity_error}")
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
            raise ValueError(f"Portable copy verification failed for {relative_path}")
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
