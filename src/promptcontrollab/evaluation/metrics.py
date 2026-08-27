"""Deterministic judging metrics."""

from __future__ import annotations

import math
import re

from promptcontrollab.core.schemas import MetricSummary, PredictionRecord


def normalize_text(value: str) -> str:
    """Normalize text for exact-match style metrics."""

    return " ".join(value.strip().lower().split())


def score_output(output: str, expected: str, metric: str) -> float:
    """Score one output with a deterministic metric."""

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
    return float(match.group(0))

