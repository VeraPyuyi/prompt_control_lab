"""Bounded, non-executable imports of saved scientific evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import shutil
import stat
import time
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, cast

from promptcontrollab.core.errors import OptionalDependencyError
from promptcontrollab.core.files import absolute_path
from promptcontrollab.core.optional import require_module
from promptcontrollab.evaluation.experiments.storage import read_json, write_json

from .models import ResearchBundle

MAX_UPLOAD = 64 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024
MAX_FILES = 10_000
DATA_SUFFIXES = {".json", ".csv", ".npz"}
_ID = re.compile(r"[a-f0-9]{24}\Z")
_RESERVED = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.I)
_SCHEMAS = {
    "readout-sensitivity": "readout",
    "response-profile": "response",
    "measurement-value": "measurement-value",
    "control-transfer": "transfer",
    "research-replay": "replay",
    "execution-sensitivity": "readout",
}


def storage_directory(root: Path, group: str) -> Path:
    """Resolve a research storage area without following links outside the workspace."""
    workspace = absolute_path(root)
    directory = workspace / ".pcl" / "research" / group
    if not directory.resolve().is_relative_to(workspace):
        raise ValueError("Research storage escapes workspace")
    return directory


def contained_directory(root: Path, group: str, identifier: str) -> Path:
    """Validate an opaque record identity and resolve its owned directory."""
    if not isinstance(identifier, str) or not _ID.fullmatch(identifier):
        raise ValueError("Invalid research identifier")
    parent = storage_directory(root, group)
    path = parent / identifier
    if path.is_symlink() or path.resolve().parent != parent.resolve():
        raise ValueError("Research directory escapes workspace")
    return path


def bundle_directory(root: Path, identifier: str) -> Path:
    """Resolve the owned directory of an imported research bundle."""
    return contained_directory(root, "bundles", identifier)


def safe_relative(name: str) -> str:
    """Validate a portable archive member path before accessing its contents."""
    if not isinstance(name, str) or not name or "\\" in name or ":" in name or "\0" in name:
        raise ValueError("Unsafe archive path")
    path = PurePosixPath(name)
    if path.is_absolute() or any(
        part in {"", ".", ".."} or part.endswith((".", " ")) or _RESERVED.match(part)
        for part in name.rstrip("/").split("/")
    ):
        raise ValueError("Unsafe archive path")
    return path.as_posix()


def data_path(directory: Path, relative: str) -> Path:
    """Resolve a validated relative data path inside its declared root."""
    path = directory / safe_relative(relative)
    if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
        raise ValueError("Research data path escapes bundle")
    return path


def sha256(path: Path) -> str:
    """Stream a file into a SHA-256 content digest."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _constant(value: str) -> Any:
    raise ValueError(f"Non-finite JSON value {value}")


def _no_credentials(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if (
                str(key).lower().replace("-", "_")
                in {
                    "api_key",
                    "apikey",
                    "authorization",
                    "password",
                    "access_token",
                    "refresh_token",
                    "client_secret",
                    "credentials",
                }
                and item
            ):
                raise ValueError("Remove credentials before importing research data")
            _no_credentials(item)
    elif isinstance(value, list):
        for item in value:
            _no_credentials(item)
    elif isinstance(value, str) and re.search(r"\bsk-[A-Za-z0-9_-]{16,}", value):
        raise ValueError("Remove credentials before importing research data")
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Non-finite research JSON value")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate research JSON key")
        result[key] = value
    return result


def json_value(path: Path) -> Any:
    """Read bounded UTF-8 JSON while rejecting duplicate keys and nonfinite values."""
    try:
        value = json.loads(
            path.read_text(encoding="utf-8-sig"),
            parse_constant=_constant,
            object_pairs_hook=_unique_object,
        )
        _no_credentials(value)
        return value
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError("Invalid UTF-8 research JSON") from error


def _validate_npz(path: Path, remaining: int) -> dict[str, Any]:
    np = require_module("numpy", feature="research array import", extra="research")
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        expanded = sum(x.file_size for x in members)
        if len(members) > MAX_FILES or expanded > remaining:
            raise ValueError("NPZ expanded size exceeds limit")
        names: set[str] = set()
        for info in members:
            name = safe_relative(info.orig_filename)
            if name.casefold() in names:
                raise ValueError("Duplicate NPZ array")
            names.add(name.casefold())
            with archive.open(info) as stream:
                version = np.lib.format.read_magic(stream)
                if version == (1, 0):
                    shape, _, dtype = np.lib.format.read_array_header_1_0(stream)
                elif version in {(2, 0), (3, 0)}:
                    shape, _, dtype = np.lib.format.read_array_header_2_0(stream)
                else:
                    raise ValueError("Unsupported NPY version")
                if dtype.hasobject:
                    raise ValueError("Object arrays and pickle are forbidden")
                size = int(dtype.itemsize)
                for dimension in shape:
                    if dimension < 0:
                        raise ValueError("Invalid research array shape")
                    size *= int(dimension)
                if size > MAX_EXPANDED or size != info.file_size - stream.tell():
                    raise ValueError("Array shape exceeds stored data or size limit")
    arrays = []
    with np.load(path, allow_pickle=False) as stored:
        for name in stored.files:
            _no_credentials({name: True})
            array = stored[name]
            if array.dtype.hasobject:
                raise ValueError("Object arrays and pickle are forbidden")
            if array.dtype.kind not in "biufUS":
                raise ValueError("Unsupported research array type")
            if array.dtype.kind in "US":
                for item in array.flat:
                    text = item.decode("utf-8") if isinstance(item, bytes) else str(item)
                    _no_credentials(text)
            arrays.append({"name": name, "shape": list(array.shape), "dtype": str(array.dtype)})
    return {"arrays": arrays, "expanded_bytes": expanded}


def _validate_file(path: Path, remaining: int) -> dict[str, Any]:
    if path.suffix.lower() == ".json":
        value = json_value(path)
        return (
            {"schema_version": value.get("schema_version", value.get("schema"))}
            if isinstance(value, dict)
            else {}
        )
    if path.suffix.lower() == ".npz":
        return _validate_npz(path, remaining)
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = csv.reader(stream)
            columns = next(rows, [])
            if not columns or len(set(columns)) != len(columns):
                raise ValueError("CSV needs unique nonempty column names")
            count = 0
            for row in rows:
                if not row:
                    continue
                if len(row) != len(columns):
                    raise ValueError("CSV rows must align with column names")
                _no_credentials(dict(zip(columns, row, strict=True)))
                count += 1
        return {"columns": columns, "rows": count}
    except csv.Error as error:
        raise ValueError("Research CSV field is too large or malformed") from error
    except UnicodeError as error:
        raise ValueError("Research CSV must be UTF-8") from error


def _extract(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(source) as archive:
        members = archive.infolist()
        if len(members) > MAX_FILES or sum(x.file_size for x in members) > MAX_EXPANDED:
            raise ValueError("Archive expanded size or file count exceeds limit")
        seen: set[str] = set()
        for info in members:
            name = safe_relative(info.orig_filename)
            if name.casefold() in seen:
                raise ValueError("Duplicate archive path")
            seen.add(name.casefold())
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ValueError("Archive links are forbidden")
            if info.flag_bits & 1:
                raise ValueError("Encrypted archives are unsupported")
            if info.is_dir() or PurePosixPath(name).suffix.lower() not in DATA_SUFFIXES:
                continue
            if info.file_size > MAX_UPLOAD:
                raise ValueError("Research file exceeds limit")
            target = data_path(destination, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as incoming, target.open("xb") as outgoing:
                total = 0
                while block := incoming.read(1024 * 1024):
                    total += len(block)
                    if total > info.file_size or total > MAX_UPLOAD:
                        raise ValueError("Research file exceeds declared size")
                    outgoing.write(block)


def _describe(
    directory: Path, files: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    """Classify supplied evidence and expose only supported analysis capabilities."""
    analyses: list[dict[str, Any]] = []
    capabilities: list[dict[str, Any]] = []
    synthetic_flags = []
    for row in files:
        value = (
            json_value(data_path(directory, row["path"]))
            if row["path"].lower().endswith(".json")
            else None
        )
        synthetic_flags.append(isinstance(value, dict) and value.get("synthetic") is True)
        declared = str(row.get("schema_version", ""))
        schema, _, version = declared.removeprefix("pcl.").partition("/")
        kind = _SCHEMAS.get(schema)
        if kind and not row["path"].startswith(("paper/", "bootstrap_replay/")):
            if version not in {"v1", "v2"}:
                capabilities.append(
                    {
                        "kind": kind,
                        "level": "unsupported_protocol",
                        "input": row["path"],
                        "reason": "This analysis protocol version is not supported.",
                    }
                )
                continue
            document = json_value(data_path(directory, row["path"]))
            if document.get("evidence_status") in {
                "independent_confirmation",
                "locked_prediction",
            } and not document.get("evidence_receipts"):
                capabilities.append(
                    {
                        "kind": kind,
                        "level": "provenance_missing",
                        "input": row["path"],
                        "reason": "Declared prediction provenance needs linked original receipts. "
                        "A supported statistical replay can still compute from saved scores.",
                    }
                )
                continue
            analyses.append({"kind": kind, "input": row["path"]})
            level = (
                "summary_only"
                if document.get("representation") == "saved_summary"
                else "saved_measurements"
            )
            capabilities.append({"kind": kind, "level": level, "input": row["path"]})
    if (directory / "bootstrap_replay" / "inputs").is_dir():
        from promptcontrollab.diagnostics.research_replay import describe_bundle

        description = describe_bundle(directory)
        for entry in description.get("analyses", []):
            analyses.append({"kind": "bootstrap", "suite": entry["suite"]})
            capabilities.append(
                {"kind": "bootstrap", "level": "saved_scores", "suite": entry["suite"]}
            )
        synthetic_flags.append(False)
    # Recognized retained tables are display-only. Their presence never selects
    # a numerical protocol or executes the archive's supporting-analysis code.
    table_groups: dict[str, list[str]] = {}
    for row in files:
        relative = row["path"]
        if not relative.startswith("supporting_analysis/data/"):
            continue
        name = PurePosixPath(relative).name
        if name.startswith(("probe_", "rank_", "logit_", "scalar_", "selection_")):
            tool = "response"
        elif "cost" in name or name.startswith("batch_"):
            tool = "measurement-value"
        elif name.startswith(("directional_", "old_pairing_", "fixed_constant_")):
            tool = "transfer"
        else:
            tool = "readout"
        table_groups.setdefault(tool, []).append(relative)
    for tool, inputs in table_groups.items():
        analyses.append({"kind": "saved-summary", "tool": tool, "inputs": inputs})
        capabilities.append({"kind": tool, "level": "summary_only", "files": len(inputs)})
    if not analyses:
        analyses = [{"kind": "inventory"}]
        capabilities += [
            {
                "kind": "inventory",
                "level": "summary_only",
                "reason": "No supported paired measurement or statistical protocol was found.",
            }
        ]
    return analyses, capabilities, bool(synthetic_flags) and all(synthetic_flags)


def _check_supplied_manifest(directory: Path) -> dict[str, Any] | None:
    path = directory / "research-bundle.json"
    if not path.is_file():
        return None
    manifest = json_value(path)
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "pcl.research-bundle/v1":
        raise ValueError("Unknown research manifest")
    rows = manifest.get("files")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Research manifest needs an input inventory")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid research manifest")
        source = data_path(directory, row.get("path", ""))
        if row["path"] in seen:
            raise ValueError("Duplicate research manifest input")
        seen.add(row["path"])
        if not source.is_file() or sha256(source) != row.get("sha256"):
            raise ValueError("Research manifest hash mismatch")
    path.unlink()  # The verified descriptor is replaced with a local inventory.
    return cast(dict[str, Any], manifest)


def import_bundle(root: Path, source: Path, *, title: str | None = None) -> ResearchBundle:
    """Copy and validate data only; never write into the supplied artifact."""
    source = Path(source)
    source = absolute_path(source.parent) / source.name
    if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_UPLOAD:
        raise ValueError("Choose a regular research file of at most 64 MiB")
    identifier = uuid.uuid4().hex[:24]
    final = bundle_directory(root, identifier)
    temporary = final.with_name(f".import-{identifier}")
    data = temporary / "data"
    data.mkdir(parents=True)
    try:
        if source.suffix.lower() == ".zip":
            _extract(source, data)
        elif source.suffix.lower() in DATA_SUFFIXES:
            shutil.copyfile(source, data / safe_relative(source.name))
        else:
            raise ValueError("Choose JSON, CSV, NPZ or ZIP research data")
        supplied = _check_supplied_manifest(data)
        allowed = {row["path"] for row in supplied["files"]} if supplied else None
        files = []
        expanded = 0
        for path in sorted(data.rglob("*")):
            if path.is_file():
                if allowed is not None and path.relative_to(data).as_posix() not in allowed:
                    path.unlink()  # Ignore previous reports as analysis inputs.
                    continue
                description = _validate_file(path, MAX_EXPANDED - expanded)
                expanded += description.get("expanded_bytes", path.stat().st_size)
                if expanded > MAX_EXPANDED:
                    raise ValueError("Aggregate research expansion exceeds limit")
                files.append(
                    {
                        "path": path.relative_to(data).as_posix(),
                        "sha256": sha256(path),
                        "bytes": path.stat().st_size,
                        **description,
                    }
                )
        if not files:
            raise ValueError("Archive contains no supported research data")
        analyses, capabilities, synthetic = _describe(data, files)
        if supplied and "analyses" in supplied:
            selected = supplied["analyses"]
            if (
                not isinstance(selected, list)
                or not selected
                or any(x not in analyses for x in selected)
            ):
                raise ValueError("Portable analysis specification is unsupported")
            analyses = selected
        name = title or source.name
        _no_credentials(name)
        bundle: ResearchBundle = {
            "schema_version": "pcl.research-bundle/v1",
            "id": identifier,
            "created_at": time.time(),
            "title": name[:160],
            "synthetic": synthetic,
            "files": files,
            "capabilities": capabilities,
            "analyses": analyses,
            "integrity": {"imported_files_hashed": True, "historical_chronology_verified": False},
        }
        write_json(temporary / "bundle.json", bundle)
        temporary.rename(final)
        return bundle
    except (zipfile.BadZipFile, EOFError) as error:
        raise ValueError("Invalid research ZIP or NPZ archive") from error
    except OptionalDependencyError as error:
        raise ValueError(str(error)) from error
    finally:
        # Only the explicitly created contained staging directory is removed.
        if temporary.exists() and temporary.resolve().parent == final.parent.resolve():
            shutil.rmtree(temporary)


def get_bundle(root: Path, identifier: str) -> ResearchBundle:
    """Read the stored inventory for an imported research bundle."""
    return cast(ResearchBundle, read_json(bundle_directory(root, identifier) / "bundle.json"))


def list_bundles(root: Path) -> list[ResearchBundle]:
    """List imported bundle inventories in reverse creation order."""
    directory = storage_directory(root, "bundles")
    if not directory.exists():
        return []
    bundles = [
        get_bundle(root, p.name)
        for p in directory.iterdir()
        if _ID.fullmatch(p.name) and (p / "bundle.json").is_file()
    ]
    return sorted(bundles, key=lambda item: item["created_at"], reverse=True)


def verify_bundle(root: Path, identifier: str) -> ResearchBundle:
    """Check every inventoried input against its recorded size and content digest."""
    bundle = get_bundle(root, identifier)
    directory = bundle_directory(root, identifier) / "data"
    for row in bundle["files"]:
        path = data_path(directory, row["path"])
        if (
            not path.is_file()
            or path.stat().st_size != row["bytes"]
            or sha256(path) != row["sha256"]
        ):
            raise ValueError("Research input integrity check failed")
    return bundle


def bundle_zip(root: Path, identifier: str, destination: Path) -> None:
    """Export exactly the verified data inventory with relative paths."""
    bundle = verify_bundle(root, identifier)
    directory = bundle_directory(root, identifier) / "data"
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        portable = {key: bundle[key] for key in ("schema_version", "title", "synthetic", "files")}
        archive.writestr("research-bundle.json", json.dumps(portable, ensure_ascii=False))
        for row in bundle["files"]:
            archive.write(data_path(directory, row["path"]), row["path"])
