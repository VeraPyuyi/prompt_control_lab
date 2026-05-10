"""Typed records and schema conversion helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

from promptcontrollab.files import JsonDict


def _string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        msg = f"Expected string field `{field_name}`"
        raise ValueError(msg)
    return value


def _optional_string(value: object, default: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        msg = "Expected optional string field"
        raise ValueError(msg)
    return value


@dataclass(frozen=True)
class TaskRecord:
    """One evaluation item."""

    id: str
    input: str
    expected: str
    slice: str = "default"
    meta: JsonDict = field(default_factory=dict)

    @classmethod
    def from_json(cls, value: JsonDict) -> TaskRecord:
        known = {"id", "input", "expected", "slice", "meta"}
        meta_value = value.get("meta", {})
        if not isinstance(meta_value, dict):
            msg = "Task field `meta` must be an object when provided"
            raise ValueError(msg)
        extra = {key: item for key, item in value.items() if key not in known}
        merged_meta: JsonDict = {**meta_value, **extra}
        return cls(
            id=_string(value.get("id"), "id"),
            input=_string(value.get("input"), "input"),
            expected=_string(value.get("expected"), "expected"),
            slice=_optional_string(value.get("slice"), "default"),
            meta=merged_meta,
        )

    def to_json(self) -> JsonDict:
        return {
            "id": self.id,
            "input": self.input,
            "expected": self.expected,
            "slice": self.slice,
            "meta": self.meta,
        }


@dataclass(frozen=True)
class PredictionRecord:
    """One model output and its deterministic score."""

    id: str
    output: str
    expected: str
    score: float
    slice: str = "default"
    method: str = "candidate"
    error: str | None = None

    def to_json(self) -> JsonDict:
        return {
            "id": self.id,
            "output": self.output,
            "expected": self.expected,
            "score": self.score,
            "slice": self.slice,
            "method": self.method,
            "error": self.error,
        }

    @classmethod
    def from_json(cls, value: JsonDict) -> PredictionRecord:
        raw_score = value.get("score")
        if not isinstance(raw_score, int | float):
            msg = "Prediction field `score` must be numeric"
            raise ValueError(msg)
        error = value.get("error")
        if error is not None and not isinstance(error, str):
            msg = "Prediction field `error` must be a string or null"
            raise ValueError(msg)
        return cls(
            id=_string(value.get("id"), "id"),
            output=_string(value.get("output"), "output"),
            expected=_string(value.get("expected"), "expected"),
            score=float(raw_score),
            slice=_optional_string(value.get("slice"), "default"),
            method=_optional_string(value.get("method"), "candidate"),
            error=error,
        )


@dataclass(frozen=True)
class MetricSummary:
    """Aggregate metric summary."""

    count: int
    mean_score: float
    by_slice: dict[str, float]

    def to_json(self) -> JsonDict:
        return {
            "count": self.count,
            "mean_score": self.mean_score,
            "by_slice": self.by_slice,
        }
