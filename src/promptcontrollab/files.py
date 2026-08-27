"""Backward-compatible facade for :mod:`promptcontrollab.core.files`."""

from promptcontrollab.core.files import (
    JsonDict,
    ensure_dir,
    read_json,
    read_jsonl,
    stable_digest,
    write_json,
    write_jsonl,
)

__all__ = [
    "JsonDict",
    "ensure_dir",
    "read_json",
    "read_jsonl",
    "stable_digest",
    "write_json",
    "write_jsonl",
]
