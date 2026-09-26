"""Short cross-process state transitions; never lock while computing a suite."""

from __future__ import annotations

import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def state_lock(directory: Path) -> Iterator[None]:
    """OS-owned byte lock, released automatically after an abrupt process exit."""
    if not directory.is_dir():
        raise FileNotFoundError("Research job does not exist")
    path = directory / "state.lock"
    if path.is_symlink() or path.resolve().parent != directory.resolve():
        raise ValueError("Research state lock escapes job")
    with path.open("a+b") as stream:
        if path.stat().st_size == 0:
            stream.write(b"\0")
            stream.flush()
        if sys.platform == "win32":
            import msvcrt

            while True:
                stream.seek(0)
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.01)
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
