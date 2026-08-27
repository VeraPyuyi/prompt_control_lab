"""Prompt identity helpers for reproducible run manifests."""

from __future__ import annotations

import hashlib
from pathlib import Path

from promptcontrollab.core.files import JsonDict


def build_prompt_identity(
    *,
    prompt_id: str | None = None,
    prompt_file: Path | None = None,
    prompt_version: str | None = None,
) -> JsonDict:
    """Build a prompt identity object from optional user-supplied fields."""

    identity: JsonDict = {}
    if prompt_id:
        identity["prompt_id"] = prompt_id
    if prompt_file is not None:
        resolved = prompt_file.resolve()
        identity["prompt_file"] = str(resolved)
        identity["prompt_hash"] = "sha256:" + hashlib.sha256(resolved.read_bytes()).hexdigest()
    if prompt_version:
        identity["prompt_version"] = prompt_version
    return identity
