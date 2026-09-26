"""Shared version-two contracts, without inferring missing measurements or provenance."""

from __future__ import annotations

from typing import Any, cast

from .common import JsonDict, canonical, digest, evidence, number, text

SCHEMAS = {
    "readout": "readout-sensitivity",
    "response": "response-profile",
    "measurement-value": "measurement-value",
    "transfer": "control-transfer",
    "replay": "research-replay",
}


def mapping(value: Any, name: str) -> JsonDict:
    """Require an object for a named protocol field."""
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return cast(JsonDict, value)


def records(value: Any, name: str, *, empty: bool = False) -> list[JsonDict]:
    """Validate a list of record objects with an explicit empty-list policy."""
    if not isinstance(value, list) or (not value and not empty):
        raise ValueError(f"{name} must be a {'possibly empty' if empty else 'nonempty'} list")
    return [mapping(row, name) for row in value]


def identifiers(value: Any, name: str, *, empty: bool = False) -> list[str]:
    """Validate unique nonempty string identities without inventing missing coordinates."""
    if not isinstance(value, list) or (not value and not empty):
        raise ValueError(f"{name} requires an explicit list of identities")
    result = [text(item, name) for item in value]
    if len(set(result)) != len(result):
        raise ValueError(f"{name} identities must be unique")
    return result


def integer(value: Any, name: str, *, minimum: int = 0) -> int:
    """Require an integer at or above the declared lower bound."""
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def boolean(value: Any, name: str) -> bool:
    """Require a Boolean without coercing strings or numeric flags."""
    if type(value) is not bool:
        raise ValueError(f"{name} must be an explicit Boolean")
    return value


def numeric_vector(value: Any, name: str, size: int | None = None) -> list[float]:
    """Validate a finite numeric vector and its optional expected length."""
    if not isinstance(value, list) or not value or (size is not None and len(value) != size):
        raise ValueError(f"{name} must be a nonempty aligned numeric vector")
    return [number(item, name) for item in value]


def score_number(value: Any, name: str) -> float:
    """Validate finite scores without rounding integer order through a float cast."""
    number(value, name)
    if isinstance(value, (int, float)):
        return value
    raise ValueError(f"{name} must be a finite numeric score")


def score_vector(value: Any, name: str, size: int) -> list[float]:
    """Validate finite aligned scores while preserving integer ranking precision."""
    if not isinstance(value, list) or len(value) != size or not value:
        raise ValueError(f"{name} must be a nonempty aligned score vector")
    return [score_number(item, name) for item in value]


def binary_vector(value: Any, name: str, size: int) -> list[int]:
    """Validate aligned binary labels without coercing arbitrary numeric values."""
    result = numeric_vector(value, name, size)
    if any(item not in (0, 1) for item in result):
        raise ValueError(f"{name} must contain only binary 0/1 values")
    return [int(item) for item in result]


def average(values: list[float]) -> float | None:
    """Return a finite arithmetic mean or an undefined result for an empty sample."""
    import math

    return number(math.fsum(value / len(values) for value in values), "mean") if values else None


def header(document: JsonDict, kind: str) -> JsonDict:
    """Validate version-two metadata and separate evidence labels from verified chronology."""
    schema = SCHEMAS[kind]
    if document.get("schema_version") not in (f"pcl.{schema}/v2", f"{schema}/v2"):
        raise ValueError(f"schema_version must be pcl.{schema}/v2")
    canonical(document)
    synthetic = boolean(document.get("synthetic"), "synthetic")
    provenance = mapping(document.get("provenance"), "provenance")
    text(provenance.get("description"), "provenance.description")
    representation = document.get("representation")
    if representation not in ("raw_records", "saved_summary"):
        raise ValueError("representation must be raw_records or saved_summary")
    receipt = evidence(document)
    # Input labels and internally linked dates never authenticate prospective isolation.
    receipt["effective_claim"] = "historical_observation"
    receipt["source_labels_authorize_confirmation"] = False
    return {
        "schema_version": f"pcl.{schema}-result/v2",
        "kind": kind,
        "synthetic": synthetic,
        "representation": representation,
        "provenance": provenance,
        "input_canonical_sha256": digest(document),
        "evidence": receipt,
        "raw_recomputation": representation == "raw_records",
        "computation": "raw_record_recomputation"
        if representation == "raw_records"
        else "saved_summary_only",
        "claim_scope": "Supplied records and local assumptions only; no model-global claim.",
    }


def saved_summary(document: JsonDict, result: JsonDict) -> JsonDict | None:
    """Expose supplied summaries without claiming reconstruction from raw records."""
    if result["representation"] != "saved_summary":
        return None
    summary = document.get("summaries")
    if not isinstance(summary, (dict, list)) or not summary:
        raise ValueError("saved_summary requires nonempty summaries")
    result.update(
        summaries=summary,
        numerical_status="not_recomputed_from_raw_records",
        summary_source_sha256=digest(summary),
        interpretation="Saved summaries inspected only; raw records were not reconstructed.",
    )
    return result


def aggregate_status(statuses: list[str]) -> str:
    """Combine component checks without upgrading missing or partial evidence."""
    if "failed" in statuses:
        return "failed"
    if statuses and all(status == "passed" for status in statuses):
        return "passed"
    if not statuses or all(status == "not_supplied" for status in statuses):
        return "not_supplied"
    return "partial"
