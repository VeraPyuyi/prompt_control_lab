"""Append-only storage for versioned control events."""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from promptcontrollab.control_protocol import ControlEvent
from promptcontrollab.files import JsonDict, ensure_dir

_PROCESS_LOCKS: dict[str, threading.RLock] = {}
_PROCESS_LOCKS_GUARD = threading.Lock()


@contextmanager
def run_lifecycle_lock(
    run_dir: Path,
    *,
    lock_timeout: float = 10.0,
    stale_after: float = 120.0,
) -> Iterator[None]:
    """Serialize lifecycle transitions and status-checked event appends."""

    with _locked_path(
        run_dir / ".control-lifecycle.lock",
        lock_timeout=lock_timeout,
        stale_after=stale_after,
        label="control lifecycle",
    ):
        yield


class EventLog:
    """Store one run's events as validated append-only JSONL."""

    def __init__(
        self,
        path: Path,
        *,
        run_id: str,
        lock_timeout: float = 10.0,
        stale_after: float = 120.0,
    ) -> None:
        if lock_timeout <= 0:
            raise ValueError("Event log lock_timeout must be positive")
        if stale_after <= 0:
            raise ValueError("Event log stale_after must be positive")
        self.path = path
        self.run_id = run_id
        self.lock_timeout = lock_timeout
        self.stale_after = stale_after
        self.lock_path = path.with_name(path.name + ".lock")

    def read(self) -> list[ControlEvent]:
        with self._locked():
            return self._read_unlocked()

    def append(self, event: ControlEvent) -> bool:
        with self._locked():
            existing = self._read_unlocked()
            return self._append_unlocked(event, existing)

    def append_new(
        self,
        *,
        event_type: str,
        payload: JsonDict,
        idempotency_key: str | None = None,
        sequence: int | None = None,
        timestamp: str | None = None,
    ) -> tuple[ControlEvent, bool]:
        """Create and append an event while sequence assignment remains locked."""

        with self._locked():
            existing = self._read_unlocked()
            keyed = _find_by_idempotency_key(existing, idempotency_key)
            if keyed is not None:
                retry = ControlEvent.create(
                    run_id=self.run_id,
                    sequence=sequence or keyed.sequence,
                    event_type=event_type,
                    timestamp=timestamp or keyed.timestamp,
                    payload=payload,
                    idempotency_key=idempotency_key,
                )
                if (
                    retry.event_id == keyed.event_id
                    and retry.event_type == keyed.event_type
                    and retry.payload == keyed.payload
                ):
                    return keyed, False
                msg = (
                    f"Idempotency key `{idempotency_key}` was reused "
                    "with changed event content"
                )
                raise ValueError(msg)

            resolved_sequence = sequence or len(existing) + 1
            event = ControlEvent.create(
                run_id=self.run_id,
                sequence=resolved_sequence,
                event_type=event_type,
                timestamp=timestamp,
                payload=payload,
                idempotency_key=idempotency_key,
            )
            appended = self._append_unlocked(event, existing)
            return event, appended

    def replay(self, events: list[ControlEvent]) -> int:
        """Append unseen events and return how many records were added."""

        with self._locked():
            existing = self._read_unlocked()
            appended = 0
            for event in events:
                if self._append_unlocked(event, existing):
                    existing.append(event)
                    appended += 1
            return appended

    def next_sequence(self) -> int:
        with self._locked():
            return len(self._read_unlocked()) + 1

    def _read_unlocked(self) -> list[ControlEvent]:
        if not self.path.exists():
            return []
        events: list[ControlEvent] = []
        for line_number, line in enumerate(
            self.path.read_text(encoding="utf-8-sig").splitlines(), start=1
        ):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                msg = f"Expected object on {self.path}:{line_number}"
                raise ValueError(msg)
            event = ControlEvent.from_json(value)
            self._validate_run(event)
            expected = len(events) + 1
            if event.sequence != expected:
                msg = f"Invalid event sequence in {self.path}: expected sequence {expected}"
                raise ValueError(msg)
            events.append(event)
        return events

    def _append_unlocked(
        self,
        event: ControlEvent,
        existing: list[ControlEvent],
    ) -> bool:
        self._validate_run(event)
        keyed = _find_by_idempotency_key(existing, event.idempotency_key)
        if keyed is not None:
            if (
                keyed.event_id == event.event_id
                and keyed.event_type == event.event_type
                and keyed.payload == event.payload
            ):
                return False
            msg = (
                f"Idempotency key `{event.idempotency_key}` was reused "
                "with changed event content"
            )
            raise ValueError(msg)
        matching = next((item for item in existing if item.event_id == event.event_id), None)
        if matching is not None:
            if matching == event:
                return False
            msg = f"Event {event.event_id} conflicts with an existing event"
            raise ValueError(msg)
        expected = len(existing) + 1
        if event.sequence != expected:
            msg = f"Cannot append event: expected sequence {expected}, got {event.sequence}"
            raise ValueError(msg)
        ensure_dir(self.path.parent)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event.to_json(), sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return True

    @contextmanager
    def _locked(self) -> Iterator[None]:
        with _locked_path(
            self.lock_path,
            lock_timeout=self.lock_timeout,
            stale_after=self.stale_after,
            label="event log",
        ):
            yield

    def _validate_run(self, event: ControlEvent) -> None:
        if event.run_id != self.run_id:
            msg = f"Event run_id `{event.run_id}` does not match `{self.run_id}`"
            raise ValueError(msg)


def _find_by_idempotency_key(
    events: list[ControlEvent],
    idempotency_key: str | None,
) -> ControlEvent | None:
    if idempotency_key is None:
        return None
    return next(
        (item for item in events if item.idempotency_key == idempotency_key),
        None,
    )


def _process_lock_for(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _PROCESS_LOCKS_GUARD:
        lock = _PROCESS_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _PROCESS_LOCKS[key] = lock
        return lock


@contextmanager
def _locked_path(
    lock_path: Path,
    *,
    lock_timeout: float,
    stale_after: float,
    label: str,
) -> Iterator[None]:
    if lock_timeout <= 0:
        raise ValueError(f"{label.capitalize()} lock_timeout must be positive")
    if stale_after <= 0:
        raise ValueError(f"{label.capitalize()} stale_after must be positive")
    ensure_dir(lock_path.parent)
    with _process_lock_for(lock_path):
        token = f"{os.getpid()}:{threading.get_ident()}:{time.time_ns()}"
        deadline = time.monotonic() + lock_timeout
        while True:
            try:
                descriptor = os.open(
                    lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
            except (FileExistsError, PermissionError):
                # Windows can report an exclusive-create collision as EACCES while
                # another process owns the sibling lock file.
                if time.monotonic() >= deadline:
                    msg = f"Timed out acquiring {label} lock: {lock_path}"
                    raise TimeoutError(msg) from None
                if _remove_stale_lock(lock_path, stale_after=stale_after):
                    continue
                time.sleep(0.01)
                continue
            try:
                os.write(descriptor, token.encode("utf-8"))
            finally:
                os.close(descriptor)
            break
        try:
            yield
        finally:
            _release_lock(lock_path, token)


def _remove_stale_lock(lock_path: Path, *, stale_after: float) -> bool:
    try:
        age = time.time() - lock_path.stat().st_mtime
        if age <= stale_after:
            return False
        lock_path.unlink()
        return True
    except FileNotFoundError:
        return True


def _release_lock(lock_path: Path, token: str) -> None:
    try:
        if lock_path.read_text(encoding="utf-8") == token:
            lock_path.unlink()
    except FileNotFoundError:
        return
