"""Atomic local persistence and cross-process single-active-job leases."""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from promptcontrollab.core.files import stable_digest
from promptcontrollab.integrations.providers import _redact_persisted_text

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}\Z")
_LOCK = threading.RLock()


def experiments_dir(root: Path) -> Path:
    """Resolve the experiment storage directory within the requested workspace."""
    workspace = Path(root).resolve()
    directory = workspace / ".pcl" / "experiments"
    if not directory.resolve().is_relative_to(workspace):
        raise ValueError("Experiment storage cannot escape its workspace")
    return directory


def job_directory(root: Path, job_id: str) -> Path:
    """Validate a job identifier and resolve its contained storage directory."""
    if not isinstance(job_id, str) or not _ID.fullmatch(job_id):
        raise ValueError("Invalid experiment ID")
    parent = experiments_dir(root)
    target = parent / job_id
    if target.is_symlink() or target.resolve().parent != parent.resolve():
        raise ValueError("Experiment directory cannot escape its workspace")
    return target


def write_json(path: Path, value: object) -> None:
    """Atomically replace a JSON file using a short temporary basename on Windows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Keep the temporary basename short on Windows, including for retry IDs.
    temporary = path.with_name(f".pcl-{uuid.uuid4().hex[:12]}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path: Path) -> dict[str, Any]:
    """Read a UTF-8 JSON object and reject non-object roots."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path.name}")
    return value


def redact(value: object, secrets: list[str] | None = None) -> Any:
    """Recursively redact configured credentials and recognizable secret assignments."""
    if isinstance(value, str):
        text = value
        for secret in secrets or []:
            if secret:
                text = text.replace(secret, "[redacted]")
        return _redact_persisted_text(text, "\x00__NO_SECRET__\x00")
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    if isinstance(value, dict):
        return {
            str(key): (
                "[redacted]"
                if str(key).lower()
                in {"api_key", "authorization", "access_token", "password", "secret", "credential"}
                else redact(item, secrets)
            )
            for key, item in value.items()
        }
    return value


def configured_secrets(spec: dict[str, Any]) -> list[str]:
    """Read configured credential values solely for removing them from persisted artifacts."""
    from promptcontrollab.integrations.providers import list_providers

    defaults = {item["id"]: item["api_key_env"] for item in list_providers()}
    configs = [spec["baseline"], spec["candidate"], spec["optimization"].get("reflection", {})]
    secrets = []
    for config in configs:
        key = config.get("api_key_env", defaults.get(config.get("provider", ""), ""))
        if key and os.environ.get(key):
            secrets.append(os.environ[key])
    return secrets


def event(path: Path, kind: str, **details: object) -> None:
    """Append and flush one redacted JSON event under the local event-writing lock."""
    payload = {"time": time.time(), "type": kind, **details}
    with _LOCK, (path / "events.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(redact(payload), ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def alive(pid: object) -> bool:
    """Probe process existence without sending a termination signal on Windows."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        # os.kill(pid, 0) is not a portable existence probe on Windows: use
        # a query-only process handle and never send a signal to another job.
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.GetExitCodeProcess.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() == 5  # Access denied: assume it is alive.
        try:
            code = wintypes.DWORD()
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value == 259)
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def active_job(root: Path) -> dict[str, Any] | None:
    """Return a live lease owner or report malformed lease state without modifying it."""
    path = experiments_dir(root) / "active.lock"
    try:
        state = read_json(path)
    except FileNotFoundError:
        return None
    except (ValueError, json.JSONDecodeError):
        raise RuntimeError(
            "Experiment active lock is unreadable; inspect it before recovery"
        ) from None
    return state if alive(state.get("pid")) else None


class JobLock:
    """Hold the workspace single-active-job lease until outstanding transports exit."""

    def __init__(self, root: Path, job_id: str):
        self.path = experiments_dir(root) / "active.lock"
        self.token = uuid.uuid4().hex
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            for _ in range(3):
                try:
                    descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                except FileExistsError:
                    existing = read_json(self.path)
                    if alive(existing.get("pid")):
                        raise RuntimeError(
                            f"Experiment {existing.get('id', 'unknown')} is already active"
                        ) from None
                    # Serialize dead-owner recovery across processes. A new
                    # owner's lease must never be removed by a second recoverer.
                    guard = self.path.with_name("recovery.lock")
                    try:
                        recovery = os.open(guard, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                    except FileExistsError:
                        raise RuntimeError(
                            "Experiment lock recovery is already in progress"
                        ) from None
                    try:
                        os.close(recovery)
                        current = read_json(self.path)
                        if current == existing and not alive(current.get("pid")):
                            self.path.unlink(missing_ok=True)
                    except FileNotFoundError:
                        pass
                    finally:
                        guard.unlink(missing_ok=True)
                    continue
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    json.dump(
                        {
                            "id": job_id,
                            "pid": os.getpid(),
                            "token": self.token,
                            "created_at": time.time(),
                        },
                        stream,
                    )
                break
            else:
                raise RuntimeError("Could not acquire experiment lock")

    def release(self) -> None:
        """Remove this lease only when its ownership token still matches."""
        with _LOCK:
            try:
                if read_json(self.path).get("token") == self.token:
                    self.path.unlink(missing_ok=True)
            except FileNotFoundError:
                pass


def snapshot_hash(spec: dict[str, Any]) -> str:
    """Hash a canonical JSON snapshot for later integrity checks."""
    return stable_digest(spec)
