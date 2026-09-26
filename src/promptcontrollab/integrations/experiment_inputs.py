"""Bounded file-to-record conversion shared by the UI and command line."""

from __future__ import annotations

import csv
import io
import json
import math
from typing import Any

MAX_FILE_BYTES = 5_000_000
MAX_RECORDS = 10_000


def _finite_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("JSON numbers must be finite")
    return value


def parse_document(text: str, format: str = "json") -> Any:
    """Read a bounded, finite JSON/JSONL/CSV document with actionable errors."""
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_FILE_BYTES:
        raise ValueError("Input must be UTF-8 text no larger than 5 MB")
    text = text.lstrip("\ufeff")
    if format not in {"csv", "json", "jsonl"}:
        raise ValueError("Choose CSV, JSON, or JSONL")
    if format == "json":
        return json.loads(text, parse_float=_finite_float, parse_constant=_finite_float)
    rows: list[dict[str, Any]] = []
    if format == "csv":
        # The complete upload is already bounded; the stdlib's smaller default
        # cell limit otherwise rejects valid long model outputs in this file.
        if csv.field_size_limit() < MAX_FILE_BYTES:
            csv.field_size_limit(MAX_FILE_BYTES)
        iterator: Any = csv.DictReader(io.StringIO(text), strict=True)
    else:
        iterator = (
            json.loads(line, parse_float=_finite_float, parse_constant=_finite_float)
            for line in text.splitlines()
            if line.strip()
        )
    try:
        for row in iterator:
            if len(rows) >= MAX_RECORDS:
                raise ValueError("Provide at most 10,000 records")
            if format == "csv" and None in row:
                raise ValueError("A CSV row has more fields than the header")
            rows.append(row)
    except csv.Error as exc:
        raise ValueError("CSV could not be parsed; check field quoting and column count") from exc
    return rows


def parse_dataset(
    text: str, format: str = "jsonl", mapping: dict[str, str] | None = None
) -> list[dict[str, Any]]:
    """Parse bounded task records and validate mapped text columns and unique IDs."""
    rows = parse_document(text, format)
    if not isinstance(rows, list) or not rows or len(rows) > 10_000:
        raise ValueError("Provide between 1 and 10,000 task records")
    if mapping is not None and (
        not isinstance(mapping, dict)
        or any(
            name not in {"id", "input", "expected"} or not isinstance(column, str)
            for name, column in mapping.items()
        )
    ):
        raise ValueError("Column mapping must map id, input and expected to column names")
    columns = {"id": "id", "input": "input", "expected": "expected", **(mapping or {})}
    records: list[dict[str, Any]] = []
    seen = set()
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError(f"Row {index} must be an object")
        record: dict[str, Any] = {name: row.get(column) for name, column in columns.items()}
        for name in ("id", "input", "expected"):
            if not isinstance(record.get(name), str) or (
                name != "expected" and not record[name].strip()
            ):
                raise ValueError(f"Row {index}: map a text column to {name}")
        if record["id"] in seen:
            raise ValueError(f"Duplicate task id: {record['id']}")
        seen.add(record["id"])
        record["slice"] = row.get("slice") or "default"
        record["meta"] = dict(row["meta"]) if isinstance(row.get("meta"), dict) else {}
        if row.get("group_id"):
            record["meta"]["group_id"] = row["group_id"]
        records.append(record)
    return records
