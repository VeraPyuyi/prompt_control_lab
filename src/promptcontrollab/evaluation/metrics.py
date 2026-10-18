"""Deterministic judging metrics."""

from __future__ import annotations

import json
import math
import re
from typing import Any

from promptcontrollab.core.schemas import MetricSummary, PredictionRecord


def normalize_text(value: str) -> str:
    """Normalize text for exact-match style metrics."""

    return " ".join(value.strip().lower().split())


def score_output(output: str, expected: str, metric: str) -> float:
    """Score one output with a deterministic metric."""

    if metric in {"json_valid@1", "json_schema@1"}:
        return float(score_details(output, expected, metric)["score"])
    if metric == "exact_match":
        return 1.0 if normalize_text(output) == normalize_text(expected) else 0.0
    if metric == "contains":
        return 1.0 if normalize_text(expected) in normalize_text(output) else 0.0
    if metric == "regex":
        return 1.0 if re.search(expected, output) is not None else 0.0
    if metric.startswith("numeric_tolerance"):
        tolerance = _parse_tolerance(metric)
        return 1.0 if _numeric_match(output, expected, tolerance) else 0.0
    if metric == "classification_accuracy":
        return 1.0 if output.strip() == expected.strip() else 0.0
    if metric == "format_error":
        return 0.0 if output.strip() else 1.0
    msg = f"Unsupported metric `{metric}`"
    raise ValueError(msg)


def _strict_json(text: str) -> Any:
    def reject(value: str) -> None:
        raise ValueError(f"Nonfinite JSON: {value}")

    value = json.loads(text, parse_constant=reject)
    # Overflowing JSON numbers must also remain invalid.
    json.dumps(value, allow_nan=False)
    return value


def _schema_check(schema: Any) -> None:
    if not isinstance(schema, dict) or set(schema) - {
        "type",
        "properties",
        "required",
        "enum",
        "items",
        "additionalProperties",
    }:
        raise ValueError("Invalid JSON schema: unsupported structure or keyword")
    if "type" in schema and schema["type"] not in {
        "object",
        "array",
        "string",
        "integer",
        "number",
        "boolean",
        "null",
    }:
        raise ValueError("Invalid JSON schema: unsupported type")
    if "required" in schema and (
        not isinstance(schema["required"], list)
        or any(not isinstance(key, str) for key in schema["required"])
    ):
        raise ValueError("Invalid JSON schema: required must contain property names")
    if "enum" in schema and (not isinstance(schema["enum"], list) or not schema["enum"]):
        raise ValueError("Invalid JSON schema: enum must be nonempty")
    if "properties" in schema:
        if not isinstance(schema["properties"], dict):
            raise ValueError("Invalid JSON schema: properties must be an object")
        for child in schema["properties"].values():
            _schema_check(child)
    if "items" in schema:
        _schema_check(schema["items"])
    if "additionalProperties" in schema and not isinstance(schema["additionalProperties"], bool):
        raise ValueError("Invalid JSON schema: additionalProperties must be boolean")


def _schema_failure(value: Any, schema: dict[str, Any], path: str = "$") -> str | None:
    kinds = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "boolean": isinstance(value, bool),
        "null": value is None,
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
    }
    if "type" in schema and not kinds[schema["type"]]:
        return f"type:{path}"
    if "enum" in schema and not any(
        value == choice and isinstance(value, bool) == isinstance(choice, bool)
        for choice in schema["enum"]
    ):
        return f"enum:{path}"
    if isinstance(value, dict):
        for key in sorted(schema.get("required", [])):
            if key not in value:
                return f"required:{path}.{key}"
        properties = schema.get("properties", {})
        for key in sorted(value):
            if key in properties:
                failure = _schema_failure(value[key], properties[key], f"{path}.{key}")
                if failure:
                    return failure
            elif schema.get("additionalProperties") is False:
                return f"additional_property:{path}.{key}"
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            failure = _schema_failure(item, schema["items"], f"{path}[{index}]")
            if failure:
                return failure
    return None


def score_details(output: str, expected: str, metric: str) -> dict[str, Any]:
    """Return stable scorer identity and a deterministic, field-local failure reason."""
    schema = None
    if metric == "json_schema@1":
        try:
            schema = _strict_json(expected)
            _schema_check(schema)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid JSON schema: {exc}") from exc
    reason = None
    if metric in {"json_valid@1", "json_schema@1"}:
        if not output.strip():
            reason = "missing_output"
        else:
            try:
                value = _strict_json(output)
            except ValueError:
                reason = "invalid_json"
            else:
                if schema is not None:
                    reason = _schema_failure(value, schema)
        score = 0.0 if reason else 1.0
    else:
        score = score_output(output, expected, metric)
    return {
        "score": score,
        "metric_id": metric.split("@")[0],
        "metric_version": "1",
        "direction": "lower_is_better" if metric == "format_error" else "higher_is_better",
        "failure_reason": reason,
    }


def summarize_predictions(records: list[PredictionRecord]) -> MetricSummary:
    """Compute mean score overall and per slice."""

    if not records:
        return MetricSummary(count=0, mean_score=0.0, by_slice={})
    total = sum(record.score for record in records)
    by_slice_values: dict[str, list[float]] = {}
    for record in records:
        by_slice_values.setdefault(record.slice, []).append(record.score)
    by_slice = {
        name: sum(values) / len(values)
        for name, values in sorted(by_slice_values.items(), key=lambda item: item[0])
    }
    return MetricSummary(count=len(records), mean_score=total / len(records), by_slice=by_slice)


def _parse_tolerance(metric: str) -> float:
    parts = metric.split(":", maxsplit=1)
    if len(parts) == 1:
        return 0.0
    try:
        return float(parts[1])
    except ValueError as exc:
        msg = f"Invalid numeric tolerance metric `{metric}`"
        raise ValueError(msg) from exc


def _numeric_match(output: str, expected: str, tolerance: float) -> bool:
    output_number = _first_number(output)
    expected_number = _first_number(expected)
    if output_number is None or expected_number is None:
        return False
    return math.isclose(output_number, expected_number, abs_tol=tolerance)


def _first_number(value: str) -> float | None:
    match = re.search(r"[-+]?(?:\d*\.\d+|\d+)", value)
    if match is None:
        return None
    number = float(match.group(0))
    return number if math.isfinite(number) else None
