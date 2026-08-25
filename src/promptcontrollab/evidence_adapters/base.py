"""Shared safe parsing for generic numeric evidence adapters."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from promptcontrollab.files import JsonDict

_STRUCTURED_SUFFIXES = {".json", ".jsonl"}
_BINARY_SUFFIXES = {".npz", ".pt", ".pth", ".pkl", ".pickle"}
_REDACTED_KEYS = {"prompt", "gold", "prediction", "generation"}


@dataclass(frozen=True)
class GenericMetricAdapter:
    """Extract only explicitly allowlisted numeric metrics from structured sources."""

    name: str
    interpretation_role: str
    patterns: tuple[str, ...]
    metric_names: frozenset[str]
    explanation: str
    scope: str
    claim_boundary: str
    next_action: str

    def source_role(self, path: Path) -> str:
        """Return a stable generic source role without inspecting source content."""

        if path.suffix.lower() in _BINARY_SUFFIXES:
            return "binary_support"
        return "numeric_diagnostic"

    def build(self, rows: list[JsonDict]) -> JsonDict:
        """Build a bounded interpretation from verified source rows."""

        values: dict[str, list[float]] = defaultdict(list)
        invalid_count = 0
        structured_count = 0
        binary_count = 0
        conflict = False
        for row in rows:
            if row.get("reconciliation_status") == "requires_reanalysis":
                conflict = True
            path = Path(str(row.get("verified_path", "")))
            suffix = path.suffix.lower()
            if suffix in _BINARY_SUFFIXES:
                binary_count += 1
                continue
            if suffix not in _STRUCTURED_SUFFIXES:
                invalid_count += 1
                continue
            try:
                payloads = _read_structured_payloads(
                    path,
                    row.get("_verified_content"),
                )
            except (OSError, ValueError, json.JSONDecodeError):
                invalid_count += 1
                continue
            structured_count += 1
            before = sum(len(items) for items in values.values())
            for payload in payloads:
                _collect_allowed_metrics(payload, self.metric_names, values)
            if sum(len(items) for items in values.values()) == before:
                invalid_count += 1

        quality_flags: list[str] = []
        if binary_count:
            quality_flags.append("binary_metadata_only")
        if invalid_count:
            quality_flags.append("unsupported_source_format")
        if conflict:
            quality_flags.append("source_conflict")

        if conflict or (rows and not values):
            support_status = "requires_reanalysis"
            confidence = "low"
        elif values:
            support_status = "observed"
            confidence = "medium"
        else:
            support_status = "unavailable"
            confidence = "unknown"

        metrics = {
            name: _numeric_summary(items)
            for name, items in sorted(values.items())
            if items
        }
        if metrics:
            observation = (
                f"Observed {len(metrics)} allowlisted numeric metric(s) across "
                f"{structured_count} structured source(s)."
            )
        elif rows:
            observation = (
                "Sources were discovered, but no supported allowlisted numeric metrics could "
                "be extracted safely."
            )
        else:
            observation = "No matching source was discovered in this evidence snapshot."

        return {
            "id": self.name,
            "adapter": self.name,
            "support_status": support_status,
            "interpretation_role": self.interpretation_role,
            "observation": observation,
            "explanation": self.explanation,
            "confidence": confidence,
            "scope": self.scope,
            "claim_boundary": self.claim_boundary,
            "next_action": self.next_action,
            "metrics": metrics,
            "quality_flags": quality_flags,
            "source_evidence": [_source_reference(row) for row in rows],
            "raw_statistics": [],
        }


def _read_structured_payloads(path: Path, verified_content: object) -> list[object]:
    if not isinstance(verified_content, bytes):
        raise ValueError("Verified structured source bytes are unavailable")
    text = verified_content.decode("utf-8-sig")
    if path.suffix.lower() == ".jsonl":
        payloads: list[object] = []
        for line in text.splitlines():
            if line.strip():
                payloads.append(json.loads(line))
        return payloads
    return [json.loads(text)]


def _collect_allowed_metrics(
    value: object,
    metric_names: frozenset[str],
    values: dict[str, list[float]],
) -> None:
    if isinstance(value, dict):
        for raw_key, item in value.items():
            key = str(raw_key)
            normalized = key.lower()
            if normalized in _REDACTED_KEYS:
                continue
            if normalized in metric_names:
                _append_numeric(item, values[normalized])
            if isinstance(item, dict | list):
                _collect_allowed_metrics(item, metric_names, values)
    elif isinstance(value, list):
        for item in value:
            _collect_allowed_metrics(item, metric_names, values)


def _append_numeric(value: object, destination: list[float]) -> None:
    if (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    ):
        destination.append(float(value))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, int | float) and not isinstance(item, bool):
                number = float(item)
                if math.isfinite(number):
                    destination.append(number)


def _numeric_summary(values: list[float]) -> JsonDict:
    return {
        "count": len(values),
        "mean": sum(values) / len(values),
        "min": min(values),
        "max": max(values),
    }


def _source_reference(row: JsonDict) -> JsonDict:
    relative = str(row.get("relative_path", ""))
    return {
        "role": row.get("role"),
        "source_sha256": row.get("sha256"),
        "canonical_sha256": row.get("canonical_sha256"),
        "source_path_sha256": (
            "sha256:" + hashlib.sha256(relative.encode("utf-8")).hexdigest()
        ),
        "reconciliation_status": row.get("reconciliation_status", "single_source"),
    }
