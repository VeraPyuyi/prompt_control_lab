"""Runtime setup for the PromptControlLab command line."""

from __future__ import annotations

import os
import sys


def ensure_utf8_for_windows_pipes() -> None:
    """Make redirected Windows CLI output readable in UTF-8 based tools."""

    _reconfigure_windows_pipe(sys.stdout)
    _reconfigure_windows_pipe(sys.stderr)


def _reconfigure_windows_pipe(stream: object, *, os_name: str | None = None) -> bool:
    """Reconfigure a redirected Windows stream as UTF-8 when supported."""

    if (os_name or os.name) != "nt":
        return False
    encoding = str(getattr(stream, "encoding", "") or "").lower().replace("_", "-")
    if "utf-8" in encoding or "utf8" in encoding:
        return False
    isatty = getattr(stream, "isatty", None)
    try:
        if callable(isatty) and isatty():
            return False
    except OSError:
        return False
    reconfigure = getattr(stream, "reconfigure", None)
    if not callable(reconfigure):
        return False
    try:
        reconfigure(encoding="utf-8", errors="replace")
    except (TypeError, ValueError, OSError):
        return False
    return True
