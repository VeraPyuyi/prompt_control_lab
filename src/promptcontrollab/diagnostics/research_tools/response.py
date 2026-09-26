"""Finite-dimensional response profiles from saved scalar and vector inputs."""

from __future__ import annotations

import math

from .common import JsonDict, evidence, number, require_document, text


def _vector(value: object, name: str, size: int | None = None) -> list[float]:
    if not isinstance(value, list) or not value or (size is not None and len(value) != size):
        raise ValueError(f"{name} must be a nonempty vector with aligned dimensions")
    return [number(x, name) for x in value]


def _norm(vector: list[float]) -> float:
    return number(math.hypot(*vector), "vector norm")


def _dot(a: list[float], b: list[float]) -> float:
    return number(math.fsum(x * y for x, y in zip(a, b, strict=True)), "inner product")


def analyze_document(document: JsonDict) -> JsonDict:
    """Recompute response geometry from finite saved scalar and tensor inputs."""
    require_document(document, "response-profile/v1")
    metadata = document.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("readout, gold-label, and calibration metadata are required")
    for key in ("readout_definition", "gold_label_usage", "calibration_source"):
        text(metadata.get(key), f"metadata.{key}")
    if type(metadata.get("calibration_disjoint")) is not bool:
        raise ValueError("metadata.calibration_disjoint must be declared explicitly")
    records = document.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("records must be nonempty")
    rows, seen = [], set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("record must be an object")
        rid = text(record.get("record_id"), "record_id")
        if rid in seen:
            raise ValueError("record_id must be unique")
        seen.add(rid)
        before = _vector(record.get("control_before"), "control_before")
        after = _vector(record.get("control_after"), "control_after", len(before))
        state = _vector(record.get("response_before"), "response_before")
        changed = _vector(record.get("response_after"), "response_after", len(state))
        gradient = _vector(record.get("readout_gradient"), "readout_gradient", len(state))
        du, dy = (
            [b - a for a, b in zip(before, after, strict=True)],
            [b - a for a, b in zip(state, changed, strict=True)],
        )
        unorm, ynorm, gnorm = _norm(du), _norm(dy), _norm(gradient)
        alignment = (
            _dot([x / ynorm for x in dy], [x / gnorm for x in gradient])
            if ynorm and gnorm
            else None
        )
        basis = record.get("subspace_basis")
        fraction = None
        if basis is not None:
            if not isinstance(basis, list) or len(basis) > len(state):
                raise ValueError("subspace_basis must have at most response dimension rows")
            basis = [_vector(row, "subspace_basis", len(state)) for row in basis]
            for i, vector in enumerate(basis):
                if abs(_norm(vector) - 1) > 1e-7 or any(
                    abs(_dot(vector, other)) > 1e-7 for other in basis[:i]
                ):
                    raise ValueError("subspace_basis rows must be orthonormal")
            fraction = (
                math.fsum(_dot([x / ynorm for x in dy], row) ** 2 for row in basis)
                if ynorm
                else None
            )
        approximation = record.get("linear_response_matrix")
        residual, relative_residual = None, None
        if approximation is not None:
            if not isinstance(approximation, list) or len(approximation) != len(state):
                raise ValueError("linear_response_matrix output dimension mismatch")
            matrix = [_vector(row, "linear_response_matrix", len(before)) for row in approximation]
            predicted = [_dot(row, du) for row in matrix]
            residual = _norm([actual - pred for actual, pred in zip(dy, predicted, strict=True)])
            relative_residual = residual / ynorm if ynorm else None
        rows.append(
            {
                "record_id": rid,
                "loss_delta": number(
                    number(record.get("loss_after"), "loss_after")
                    - number(record.get("loss_before"), "loss_before"),
                    "loss_delta",
                ),
                "control_displacement": unorm,
                "response_displacement": ynorm,
                "response_gain": ynorm / unorm if unorm else None,
                "readout_alignment": alignment,
                "readout_linear_delta": _dot(gradient, dy),
                "subspace_fraction": fraction,
                "approximation_residual": residual,
                "relative_approximation_residual": relative_residual,
            }
        )
    return {
        "schema_version": "response-profile-result/v1",
        "kind": "response",
        "synthetic": document["synthetic"],
        "metadata": metadata,
        "evidence": evidence(document),
        "rows": rows,
        "formulae": {
            "loss_delta": "loss_after - loss_before",
            "response_gain": "norm(response_delta) / norm(control_delta)",
            "readout_alignment": "cosine(response_delta, readout_gradient)",
            "subspace_fraction": "squared orthogonal projection / squared response norm",
            "approximation_residual": (
                "norm(response_delta - linear_response_matrix @ control_delta)"
            ),
        },
        "claim_scope": (
            "Saved finite-dimensional local response; calibration separation is declared, "
            "not inferred."
        ),
    }
