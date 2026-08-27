"""Validated output ownership and overwrite handling for evidence runs."""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterable
from pathlib import Path

from promptcontrollab.core.files import ensure_dir, read_json


def validate_evidence_destination(
    output: Path,
    *,
    protected_roots: Iterable[Path] = (),
) -> Path:
    """Reject evidence writes that overlap source inputs or protected project roots."""

    expanded = output.expanduser()
    if expanded.is_symlink():
        raise ValueError(f"Evidence output cannot be a symbolic link: {expanded}")
    resolved = expanded.resolve()
    if resolved.parent == resolved:
        raise ValueError(f"Evidence output cannot be a filesystem root: {resolved}")
    if resolved == Path.cwd().resolve():
        raise ValueError("Evidence output cannot replace the current working directory")
    if resolved.is_dir() and (resolved / ".git").exists():
        raise ValueError(f"Evidence output cannot replace a Git repository root: {resolved}")
    for raw in protected_roots:
        protected = raw.expanduser().resolve()
        if protected.is_file():
            if protected == resolved or protected.is_relative_to(resolved):
                raise ValueError(f"Evidence output overlaps an input artifact: {protected}")
            continue
        if resolved.is_relative_to(protected) or protected.is_relative_to(resolved):
            raise ValueError(f"Evidence output overlaps a protected source root: {protected}")
    return resolved


def _prepare_adapter_output(out_dir: Path, *, overwrite: bool) -> None:
    """Prepare an evidence destination without following unsafe output links."""

    resolved = validate_evidence_destination(out_dir)
    if resolved.exists() and not resolved.is_dir():
        raise ValueError(f"Evidence output must be a directory: {resolved}")
    portable_dir = resolved / "portable"
    if portable_dir.is_symlink():
        raise ValueError(f"Portable evidence destination cannot be a symbolic link: {portable_dir}")
    if not resolved.exists() or not any(resolved.iterdir()):
        ensure_dir(resolved)
        return
    if not overwrite:
        raise ValueError(f"Evidence output already exists: {resolved}")

    manifest_path = resolved / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError(
            f"Refusing to overwrite a directory that is not a PromptControlLab evidence run: "
            f"{resolved}"
        )
    try:
        manifest = read_json(manifest_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(
            f"Refusing to overwrite a directory with an invalid evidence sentinel: {resolved}"
        ) from exc
    if manifest.get("schema") not in {
        "prompt_control_lab.evidence_run.v1",
        "prompt_control_lab.evidence_run.v2",
    }:
        raise ValueError(
            f"Refusing to overwrite a directory that is not a PromptControlLab evidence run: "
            f"{resolved}"
        )
    artifact_names = manifest.get("artifacts", [])
    if not isinstance(artifact_names, list) or not all(
        isinstance(name, str) and Path(name).name == name for name in artifact_names
    ):
        raise ValueError("Evidence run sentinel contains unsafe artifact paths")
    known = {
        "manifest.json",
        "source_manifest.json",
        "public_source_manifest.json",
        "source_reconciliation.json",
        "source_gap_report.json",
        "evidence_matrix.json",
        "interpretability_report.json",
        "interpretability_report.html",
        "claim_check.json",
        "portable",
        *artifact_names,
    }
    unknown = sorted(path.name for path in resolved.iterdir() if path.name not in known)
    if unknown:
        raise ValueError(
            "Refusing to overwrite evidence output with unowned files: " + ", ".join(unknown)
        )
    for path in list(resolved.iterdir()):
        if path.name == "portable":
            if path.is_symlink() or not path.is_dir():
                raise ValueError(f"Portable evidence destination is unsafe: {path}")
            shutil.rmtree(path)
        elif path.is_dir():
            raise ValueError(f"Unexpected directory in evidence output: {path}")
        else:
            path.unlink()
    ensure_dir(resolved)
