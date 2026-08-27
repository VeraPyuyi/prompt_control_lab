"""Build the minimal, curated bundle uploaded to a Hugging Face Space."""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import re
import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from promptcontrollab.core.files import JsonDict

_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"$', re.MULTILINE)
_FORBIDDEN_BUNDLE_SUFFIXES = frozenset({".mp4", ".pt", ".pth", ".pkl", ".pickle", ".npz"})
_SPACE_SOURCE_FILES = ("Dockerfile", "app.py", "README.md", "README.zh.md")
_SPACE_SOURCE_ENTRIES = frozenset({*_SPACE_SOURCE_FILES, "demo_runs", "space_manifest.json"})
_STRIPPED_WHEEL_PREFIXES = ("promptcontrollab/template_data/",)


def build_space_bundle(
    *,
    project_root: Path,
    output_dir: Path,
    wheel_path: Path,
    source_commit: str,
    force: bool = False,
) -> JsonDict:
    """Create a deployable Space directory from an explicit allowlisted source tree."""

    root = project_root.resolve(strict=True)
    source = root / "deploy" / "huggingface"
    if not source.is_dir():
        msg = f"Hugging Face deployment source does not exist: {source}"
        raise ValueError(msg)
    source_manifest = _load_source_manifest(source)
    declared_demo_files = _declared_demo_files(source_manifest)
    _validate_source_tree(source, declared_demo_files)
    wheel = wheel_path.resolve(strict=True)
    if wheel.suffix != ".whl":
        msg = f"Expected a wheel file, got: {wheel}"
        raise ValueError(msg)
    output = output_dir.resolve(strict=False)
    if output.exists():
        if not force:
            msg = f"Space bundle output already exists: {output}"
            raise ValueError(msg)
        shutil.rmtree(output)
    output.mkdir(parents=True)
    for name in _SPACE_SOURCE_FILES:
        shutil.copyfile(source / name, output / name)
    for relative in declared_demo_files:
        origin = source / relative
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, target)
    wheels_dir = output / "wheels"
    wheels_dir.mkdir()
    deployed_wheel = wheels_dir / wheel.name
    _write_space_runtime_wheel(wheel, deployed_wheel)
    _validate_bundle_files(output)
    package_version = _project_version(root / "pyproject.toml")
    demo_files = [
        path.relative_to(output).as_posix()
        for path in sorted((output / "demo_runs").rglob("*"), key=lambda item: item.as_posix())
        if path.is_file()
    ]
    manifest: JsonDict = {
        "schema": "prompt_control_lab.huggingface_space.v1",
        "source_repository": "https://github.com/VeraPyuyi/prompt_control_lab",
        "source_commit": source_commit,
        "package_version": package_version,
        "demo_data_version": str(source_manifest["demo_data_version"]),
        "deployment_mode": "hf_demo",
        "wheel": {
            "file": f"wheels/{wheel.name}",
            "sha256": f"sha256:{_file_sha256(deployed_wheel)}",
        },
        "demo_files": demo_files,
    }
    (output / "space_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def _load_source_manifest(source: Path) -> JsonDict:
    path = source / "space_manifest.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        msg = f"Invalid Hugging Face source manifest: {path}"
        raise ValueError(msg) from exc
    if not isinstance(value, dict) or not isinstance(value.get("demo_data_version"), str):
        msg = "Hugging Face source manifest must declare demo_data_version."
        raise ValueError(msg)
    return value


def _declared_demo_files(manifest: JsonDict) -> tuple[Path, ...]:
    raw = manifest.get("demo_files")
    if not isinstance(raw, list) or not raw:
        msg = "Hugging Face source manifest must declare a non-empty demo_files list."
        raise ValueError(msg)
    declared: list[Path] = []
    for item in raw:
        if not isinstance(item, str):
            msg = "Hugging Face source manifest demo_files entries must be strings."
            raise ValueError(msg)
        relative = Path(item)
        if relative.is_absolute() or ".." in relative.parts or relative.parts[:1] != ("demo_runs",):
            msg = f"Unsafe demo file declaration: {item}"
            raise ValueError(msg)
        declared.append(relative)
    if len(set(declared)) != len(declared):
        msg = "Hugging Face source manifest contains duplicate demo_files entries."
        raise ValueError(msg)
    return tuple(sorted(declared, key=lambda path: path.as_posix()))


def _validate_source_tree(source: Path, declared_demo_files: tuple[Path, ...]) -> None:
    actual_entries = {item.name for item in source.iterdir()}
    unexpected_entries = sorted(actual_entries - _SPACE_SOURCE_ENTRIES)
    missing_entries = sorted(_SPACE_SOURCE_ENTRIES - actual_entries)
    if unexpected_entries or missing_entries:
        msg = (
            "Hugging Face source entries do not match the allowlist; "
            f"unexpected={unexpected_entries}, missing={missing_entries}."
        )
        raise ValueError(msg)
    for item in source.iterdir():
        _reject_symlink(item, source)
    demo_root = source / "demo_runs"
    actual_demo_files = {
        path.relative_to(source)
        for path in demo_root.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    declared_set = set(declared_demo_files)
    unexpected = sorted(
        (path.as_posix() for path in actual_demo_files - declared_set),
    )
    missing = sorted(
        (path.as_posix() for path in declared_set - actual_demo_files),
    )
    if unexpected or missing:
        msg = (
            "Hugging Face demo files are not declared by the source manifest; "
            f"unexpected={unexpected}, missing={missing}."
        )
        raise ValueError(msg)
    for relative in declared_demo_files:
        path = source / relative
        _reject_symlink(path, source)
        if path.suffix.lower() not in {".json", ".jsonl", ".md"}:
            msg = f"Unsupported curated demo file type: {relative.as_posix()}"
            raise ValueError(msg)


def _reject_symlink(path: Path, root: Path) -> None:
    current = path
    while current != root:
        if current.is_symlink():
            msg = f"Hugging Face deployment source cannot contain symlinks: {path}"
            raise ValueError(msg)
        current = current.parent


def _write_space_runtime_wheel(source: Path, destination: Path) -> None:
    """Write a valid runtime wheel without installable plugin templates."""

    with ZipFile(source, "r") as incoming:
        infos = [
            info
            for info in incoming.infolist()
            if not any(info.filename.startswith(prefix) for prefix in _STRIPPED_WHEEL_PREFIXES)
        ]
        record_names = [
            info.filename for info in infos if info.filename.endswith(".dist-info/RECORD")
        ]
        if len(record_names) != 1:
            msg = "Deployment wheel must contain exactly one dist-info/RECORD file."
            raise ValueError(msg)
        record_name = record_names[0]
        rows: list[tuple[str, str, str]] = []
        with ZipFile(destination, "w", compression=ZIP_DEFLATED) as outgoing:
            for info in infos:
                if info.filename == record_name or info.is_dir():
                    continue
                data = incoming.read(info.filename)
                outgoing.writestr(_normalized_zip_info(info), data)
                rows.append((info.filename, _wheel_hash(data), str(len(data))))
            rows.append((record_name, "", ""))
            record_buffer = io.StringIO(newline="")
            csv.writer(record_buffer, lineterminator="\n").writerows(rows)
            outgoing.writestr(record_name, record_buffer.getvalue().encode("utf-8"))


def _normalized_zip_info(info: ZipInfo) -> ZipInfo:
    normalized = ZipInfo(info.filename, date_time=info.date_time)
    normalized.compress_type = ZIP_DEFLATED
    normalized.external_attr = info.external_attr
    normalized.create_system = info.create_system
    return normalized


def _wheel_hash(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    encoded = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return f"sha256={encoded}"


def _project_version(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = _VERSION_RE.search(text)
    if match is None:
        msg = f"Could not read project version from {path}"
        raise ValueError(msg)
    return match.group(1)


def _validate_bundle_files(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_symlink():
            msg = f"Space bundle cannot contain symlinks: {path}"
            raise ValueError(msg)
        if path.is_file() and path.suffix.lower() in _FORBIDDEN_BUNDLE_SUFFIXES:
            msg = f"Space bundle contains forbidden artifact type: {path.name}"
            raise ValueError(msg)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
