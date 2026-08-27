"""Security boundaries for the public, stateless Hugging Face demo."""

from __future__ import annotations

import json
import math
import re
import shutil
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, cast

from promptcontrollab.core.files import JsonDict

HF_DEMO_MODE = "hf_demo"
HF_DEMO_MAX_UPLOAD_BYTES = 5 * 1024 * 1024
HF_DEMO_MAX_JSON_DEPTH = 20
HF_DEMO_MAX_JSON_RECORDS = 5_000
HF_DEMO_MAX_JSON_NODES = 50_000
HF_DEMO_SESSION_TTL_SECONDS = 6 * 60 * 60
HF_DEMO_MAX_SESSION_FILES = 64
HF_DEMO_MAX_SESSION_BYTES = 25 * 1024 * 1024
HF_DEMO_MAX_GLOBAL_BYTES = 256 * 1024 * 1024
HF_DEMO_MAX_SESSIONS = 128
HF_DEMO_ALLOWED_WORKFLOWS = frozenset({"guard"})

_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_ALLOWED_UPLOAD_SUFFIXES = frozenset({".json", ".jsonl"})
_ALLOWED_ARTIFACT_NAMES = frozenset(
    {
        "agent_run.json",
        "attribution.json",
        "audit_result.json",
        "checkpoint_comparison.json",
        "claim_check.json",
        "comparison_validity.json",
        "control_run.json",
        "decision.json",
        "decision_trace.json",
        "events.jsonl",
        "evidence_matrix.json",
        "explanation.json",
        "gate_result.json",
        "green_certificate.json",
        "history_compare.json",
        "history_index.json",
        "interpretability_report.json",
        "manifest.json",
        "mechanism_attribution.json",
        "metrics.json",
        "model_drift.json",
        "posterior_certificate.json",
        "posttrain_gate.json",
        "preflight.json",
        "provider_result.json",
        "stability.json",
        "stats.json",
        "terminal_sensitivity.json",
    }
)
_FORBIDDEN_DEMO_SUFFIXES = frozenset(
    {".zip", ".pkl", ".pickle", ".pt", ".pth", ".npz", ".mp4"}
)
_SESSION_MARKER = ".pcl-hf-session.json"
_STORAGE_LOCK = threading.Lock()


@dataclass(frozen=True)
class DemoSession:
    """Filesystem locations owned by one browser session."""

    session_id: str
    root: Path
    runs_dir: Path
    uploads_dir: Path
    outputs_dir: Path


def is_hf_demo(deployment_mode: str | None = None) -> bool:
    """Return whether the current process is running the restricted public demo."""

    if deployment_mode is None:
        import os

        deployment_mode = os.environ.get("PCL_DEPLOYMENT_MODE", "")
    return deployment_mode.strip().lower() == HF_DEMO_MODE


def prepare_demo_session(
    base_dir: Path,
    *,
    seed_runs: Path | None = None,
    session_id: str | None = None,
) -> DemoSession:
    """Create an isolated session and copy only trusted, curated demo artifacts."""

    identifier = uuid.uuid4().hex if session_id is None else session_id
    _validate_identifier(identifier, label="session id")
    base = base_dir.resolve(strict=False)
    cleanup_expired_sessions(base)
    root = (base / "sessions" / identifier).resolve(strict=False)
    _require_within(root, base / "sessions", label="session directory")
    if not root.exists() and _active_session_count(base) >= HF_DEMO_MAX_SESSIONS:
        msg = "The public demo has reached its active-session capacity; try again later."
        raise ValueError(msg)
    runs_dir = root / "runs"
    uploads_dir = root / "uploads"
    outputs_dir = root / "outputs"
    for path in (runs_dir, uploads_dir, outputs_dir):
        path.mkdir(parents=True, exist_ok=True)
    if seed_runs is not None:
        _copy_curated_demo_tree(seed_runs, runs_dir)
    marker = root / _SESSION_MARKER
    marker.write_text(
        json.dumps({"schema": "prompt_control_lab.hf_demo_session.v1", "session_id": identifier})
        + "\n",
        encoding="utf-8",
    )
    return DemoSession(
        session_id=identifier,
        root=root,
        runs_dir=runs_dir,
        uploads_dir=uploads_dir,
        outputs_dir=outputs_dir,
    )


def cleanup_expired_sessions(
    base_dir: Path,
    *,
    max_age_seconds: int = HF_DEMO_SESSION_TTL_SECONDS,
    now: float | None = None,
) -> list[Path]:
    """Remove only marked, expired demo sessions below ``base_dir/sessions``."""

    if max_age_seconds < 0:
        msg = "max_age_seconds must be non-negative."
        raise ValueError(msg)
    current_time = time.time() if now is None else now
    sessions_dir = base_dir.resolve(strict=False) / "sessions"
    if not sessions_dir.is_dir():
        return []
    removed: list[Path] = []
    for candidate in sorted(sessions_dir.iterdir(), key=lambda item: item.name):
        marker = candidate / _SESSION_MARKER
        if not candidate.is_dir() or candidate.is_symlink() or not marker.is_file():
            continue
        age = current_time - marker.stat().st_mtime
        if age <= max_age_seconds:
            continue
        _require_within(candidate.resolve(strict=False), sessions_dir, label="session directory")
        shutil.rmtree(candidate)
        removed.append(candidate)
    return removed


def validate_uploaded_artifact(filename: str, content: bytes) -> JsonDict:
    """Validate one bounded JSON or JSONL artifact without executing its contents."""

    _validate_plain_filename(filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_UPLOAD_SUFFIXES:
        msg = "The public demo accepts JSON or JSONL files only."
        raise ValueError(msg)
    if filename not in _ALLOWED_ARTIFACT_NAMES:
        msg = "Upload a recognized PromptControlLab artifact filename."
        raise ValueError(msg)
    if len(content) > HF_DEMO_MAX_UPLOAD_BYTES:
        msg = "The upload exceeds the 5 MB public-demo limit."
        raise ValueError(msg)
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        msg = "Uploaded artifacts must use UTF-8 encoding."
        raise ValueError(msg) from exc
    value: object
    if suffix == ".jsonl":
        value = _parse_jsonl(text)
        record_count = len(value)
        artifact_format = "jsonl"
    else:
        value = _load_strict_json(text, context=filename)
        record_count = len(value) if isinstance(value, list) else 1
        artifact_format = "json"
    if record_count > HF_DEMO_MAX_JSON_RECORDS:
        msg = f"Uploaded artifact exceeds the {HF_DEMO_MAX_JSON_RECORDS} record limit."
        raise ValueError(msg)
    _validate_json_shape(value)
    _validate_artifact_schema(filename, value)
    return {
        "name": filename,
        "format": artifact_format,
        "record_count": record_count,
        "size_bytes": len(content),
        "value": value,
    }


def store_uploaded_artifact(
    session: DemoSession,
    *,
    run_name: str,
    filename: str,
    content: bytes,
) -> Path:
    """Validate and normalize an uploaded artifact inside one session run."""

    _validate_identifier(run_name, label="run name")
    artifact = validate_uploaded_artifact(filename, content)
    output = (session.runs_dir / run_name / filename).resolve(strict=False)
    _require_within(output, session.runs_dir, label="upload output")
    output.parent.mkdir(parents=True, exist_ok=True)
    value = artifact["value"]
    if artifact["format"] == "jsonl":
        records = cast(list[object], value)
        rendered = "".join(
            json.dumps(record, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
            for record in records
        )
    else:
        rendered = (
            json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
            + "\n"
        )
    encoded = rendered.encode("utf-8")
    with _STORAGE_LOCK:
        _enforce_storage_quotas(session, output=output, incoming_bytes=len(encoded))
        output.write_bytes(encoded)
    return output


def require_hf_demo_workflow(
    workflow_name: str,
    *,
    outputs: list[Path],
    safe_root: Path | None,
) -> None:
    """Reject direct backend calls that exceed the public demo capability set."""

    if workflow_name not in HF_DEMO_ALLOWED_WORKFLOWS:
        msg = f"Workflow `{workflow_name}` is disabled in the Hugging Face demo."
        raise ValueError(msg)
    if safe_root is None:
        msg = "The Hugging Face demo requires an isolated session runs directory."
        raise ValueError(msg)
    root = safe_root.resolve(strict=False)
    for output in outputs:
        resolved = output.resolve(strict=False)
        if not _is_relative_to(resolved, root):
            msg = "Hugging Face demo output is outside the session runs directory."
            raise ValueError(msg)


def _parse_jsonl(text: str) -> list[JsonDict]:
    records: list[JsonDict] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if len(records) >= HF_DEMO_MAX_JSON_RECORDS:
            msg = f"Uploaded artifact exceeds the {HF_DEMO_MAX_JSON_RECORDS} record limit."
            raise ValueError(msg)
        value = _load_strict_json(stripped, context=f"line {line_number}")
        if not isinstance(value, dict):
            msg = f"JSONL line {line_number} must contain an object."
            raise ValueError(msg)
        records.append(cast(JsonDict, value))
    return records


def _load_strict_json(text: str, *, context: str) -> object:
    try:
        return json.loads(text, parse_constant=_reject_non_finite)
    except json.JSONDecodeError as exc:
        msg = f"Invalid JSON in {context}: {exc.msg}."
        raise ValueError(msg) from exc


def _reject_non_finite(value: str) -> NoReturn:
    msg = f"JSON numbers must be finite; found {value}."
    raise ValueError(msg)


def _validate_json_shape(value: object) -> None:
    stack: list[tuple[object, int]] = [(value, 1)]
    nodes = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if nodes > HF_DEMO_MAX_JSON_NODES:
            msg = f"Uploaded artifact exceeds the {HF_DEMO_MAX_JSON_NODES} node limit."
            raise ValueError(msg)
        if depth > HF_DEMO_MAX_JSON_DEPTH:
            msg = f"Uploaded artifact exceeds the {HF_DEMO_MAX_JSON_DEPTH} nesting depth limit."
            raise ValueError(msg)
        if isinstance(item, float) and not math.isfinite(item):
            msg = "JSON numbers must be finite."
            raise ValueError(msg)
        if isinstance(item, dict):
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)


def _validate_artifact_schema(filename: str, value: object) -> None:
    if filename == "events.jsonl":
        if not isinstance(value, list):
            msg = "events.jsonl must contain object records."
            raise ValueError(msg)
        return
    if not isinstance(value, dict):
        msg = f"{filename} must contain a JSON object."
        raise ValueError(msg)
    if filename == "stats.json":
        comparisons = value.get("comparisons")
        old_shape = any(
            key in value for key in ("mean_delta", "bootstrap_ci", "permutation_p_value")
        )
        if not isinstance(comparisons, list) and not old_shape:
            msg = "stats.json must contain a comparisons list or legacy comparison fields."
            raise ValueError(msg)
    if filename == "history_index.json" and not isinstance(value.get("runs"), list):
        msg = "history_index.json must contain a runs list."
        raise ValueError(msg)


def _copy_curated_demo_tree(source: Path, destination: Path) -> None:
    source_root = source.resolve(strict=True)
    if not source_root.is_dir():
        msg = f"Demo source is not a directory: {source}"
        raise ValueError(msg)
    for path in sorted(source_root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            msg = f"Curated demo assets cannot contain symlinks: {path}"
            raise ValueError(msg)
        relative = path.relative_to(source_root)
        target = (destination / relative).resolve(strict=False)
        _require_within(target, destination, label="curated demo target")
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if path.suffix.lower() in _FORBIDDEN_DEMO_SUFFIXES:
            msg = f"Forbidden file type in curated demo assets: {path.name}"
            raise ValueError(msg)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)


def _validate_plain_filename(filename: str) -> None:
    if not filename or Path(filename).name != filename or "/" in filename or "\\" in filename:
        msg = "Uploads must use a plain filename without directories."
        raise ValueError(msg)


def _validate_identifier(value: str, *, label: str) -> None:
    if not _SESSION_ID_RE.fullmatch(value):
        msg = f"Invalid {label}; use 1-64 letters, numbers, underscores, or hyphens."
        raise ValueError(msg)


def _require_within(path: Path, root: Path, *, label: str) -> None:
    resolved_root = root.resolve(strict=False)
    if not _is_relative_to(path.resolve(strict=False), resolved_root):
        msg = f"Unsafe {label}: path escapes its configured root."
        raise ValueError(msg)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _active_session_count(base_dir: Path) -> int:
    sessions_dir = base_dir / "sessions"
    if not sessions_dir.is_dir():
        return 0
    return sum(
        1
        for candidate in sessions_dir.iterdir()
        if candidate.is_dir()
        and not candidate.is_symlink()
        and (candidate / _SESSION_MARKER).is_file()
    )


def _enforce_storage_quotas(
    session: DemoSession,
    *,
    output: Path,
    incoming_bytes: int,
) -> None:
    base_dir = session.root.parent.parent
    cleanup_expired_sessions(base_dir)
    session_files, session_bytes = _storage_usage(session.root)
    _global_files, global_bytes = _storage_usage(session.root.parent)
    existing_size = output.stat().st_size if output.is_file() else 0
    projected_files = session_files + (0 if output.exists() else 1)
    projected_session_bytes = session_bytes - existing_size + incoming_bytes
    projected_global_bytes = global_bytes - existing_size + incoming_bytes
    if projected_files > HF_DEMO_MAX_SESSION_FILES:
        msg = f"The session file quota is {HF_DEMO_MAX_SESSION_FILES} files."
        raise ValueError(msg)
    if projected_session_bytes > HF_DEMO_MAX_SESSION_BYTES:
        msg = f"The session byte quota is {HF_DEMO_MAX_SESSION_BYTES} bytes."
        raise ValueError(msg)
    if projected_global_bytes > HF_DEMO_MAX_GLOBAL_BYTES:
        msg = "The public demo has reached its global storage quota; try again later."
        raise ValueError(msg)


def _storage_usage(root: Path) -> tuple[int, int]:
    if not root.is_dir():
        return 0, 0
    files = 0
    total_bytes = 0
    for path in root.rglob("*"):
        if path.is_symlink():
            continue
        if path.is_file():
            files += 1
            total_bytes += path.stat().st_size
    return files, total_bytes
