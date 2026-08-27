"""Control-certificate validation for post-training checkpoint gates."""

from __future__ import annotations

import math
from typing import cast

from promptcontrollab.core.files import JsonDict
from promptcontrollab.evidence.posttraining.common import (
    _bool,
    _dict,
    _not_applicable_check,
    _optional_float,
    _optional_positive_int,
    _valid_interval,
)
from promptcontrollab.evidence.posttraining.constants import (
    CONTROL_CERTIFICATE_LEVELS,
    CONTROL_CERTIFICATE_NATURAL_MAXIMUM,
    CONTROL_CERTIFICATE_SCHEMAS,
    CONTROL_CERTIFICATE_STATES,
    CONTROL_CERTIFICATES,
    MINIMUM_CONTROL_CERTIFICATE_LEVELS,
)

_CONTROL_CERTIFICATES = CONTROL_CERTIFICATES
_CONTROL_CERTIFICATE_LEVELS = CONTROL_CERTIFICATE_LEVELS
_CONTROL_CERTIFICATE_NATURAL_MAXIMUM = CONTROL_CERTIFICATE_NATURAL_MAXIMUM
_CONTROL_CERTIFICATE_SCHEMAS = CONTROL_CERTIFICATE_SCHEMAS
_CONTROL_CERTIFICATE_STATES = CONTROL_CERTIFICATE_STATES
_MINIMUM_CONTROL_CERTIFICATE_LEVELS = MINIMUM_CONTROL_CERTIFICATE_LEVELS


def _control_certificate_check(
    name: str,
    candidate: JsonDict,
    policy: JsonDict,
    *,
    capability_profile: str,
) -> JsonDict:
    """Evaluate one optional control certificate under gate policy constraints."""

    required_key = _CONTROL_CERTIFICATES[name]
    required = _bool(policy.get(required_key), key=required_key, default=False)
    configured_minimum = _minimum_control_certificate_level(policy)
    minimum = _effective_control_certificate_minimum(name, configured_minimum)
    forced = required or configured_minimum is not None
    if capability_profile == "black-box" and not forced:
        return _not_applicable_check(
            f"{name.replace('_', ' ').title()} requires an open or recorded surrogate."
        )
    diagnostic = _dict(candidate.get(name))
    if not diagnostic:
        if not forced:
            return _not_applicable_check(f"{name.replace('_', ' ').title()} was not recorded.")
        return {
            "passed": False,
            "applicable": True,
            "severity": "insufficient",
            "observed": "missing",
            "evidence_status": "missing",
            "certificate_level": "insufficient_evidence",
            "minimum_certificate_level": minimum,
            "message": f"Required {name.replace('_', ' ')} evidence is missing.",
        }
    check_state = str(diagnostic.get("check_state") or "invalid")
    certificate_level = str(diagnostic.get("certificate_level") or "insufficient_evidence")
    common: JsonDict = {
        "applicable": True,
        "observed": check_state,
        "check_state": check_state,
        "certificate_level": certificate_level,
        "minimum_certificate_level": minimum,
    }
    validation_errors = _control_certificate_validation_errors(name, diagnostic)
    if validation_errors:
        return {
            **common,
            "passed": False,
            "severity": "insufficient",
            "evidence_status": "invalid_certificate_schema",
            "validation_errors": validation_errors,
            "message": (
                f"{name.replace('_', ' ').title()} failed artifact schema and consistency "
                "validation."
            ),
        }
    if check_state == "conditions_not_met":
        return {
            **common,
            "passed": False,
            "severity": "fail",
            "evidence_status": "conditions_not_met",
            "message": (
                f"Recorded {name.replace('_', ' ')} conditions were not met; this triggers hold "
                "but does not prove nonexistence."
            ),
        }
    if check_state in {"missing", "invalid"}:
        return {
            **common,
            "passed": False,
            "severity": "insufficient",
            "evidence_status": check_state,
            "message": f"{name.replace('_', ' ').title()} evidence is {check_state}.",
        }
    if check_state != "passed" or certificate_level not in _CONTROL_CERTIFICATE_LEVELS:
        return {
            **common,
            "passed": False,
            "severity": "insufficient",
            "evidence_status": "invalid_certificate_schema",
            "message": f"{name.replace('_', ' ').title()} has an unsupported result state.",
        }
    if certificate_level == "insufficient_evidence":
        return {
            **common,
            "passed": False,
            "severity": "insufficient",
            "evidence_status": certificate_level,
            "message": f"{name.replace('_', ' ').title()} has insufficient evidence.",
        }
    if certificate_level == "not_applicable":
        if forced:
            return {
                **common,
                "passed": False,
                "severity": "insufficient",
                "evidence_status": certificate_level,
                "message": f"{name.replace('_', ' ').title()} does not satisfy required evidence.",
            }
        return _not_applicable_check(
            f"{name.replace('_', ' ').title()} is not applicable to this checkpoint."
        )
    if minimum is not None and (
        _CONTROL_CERTIFICATE_LEVELS[certificate_level] < _CONTROL_CERTIFICATE_LEVELS[minimum]
    ):
        return {
            **common,
            "passed": False,
            "severity": "insufficient",
            "evidence_status": "below_minimum_certificate_level",
            "message": (
                f"{name.replace('_', ' ').title()} is below the required certificate level."
            ),
        }
    return {
        **common,
        "passed": True,
        "severity": "info",
        "evidence_status": "recorded",
        "message": f"{name.replace('_', ' ').title()} meets the configured evidence policy.",
    }


def _minimum_control_certificate_level(policy: JsonDict) -> str | None:
    value = policy.get("minimum_control_certificate_level")
    if value is None or str(value).strip() == "":
        return None
    normalized = str(value).strip()
    if normalized not in _MINIMUM_CONTROL_CERTIFICATE_LEVELS:
        supported = ", ".join(sorted(_MINIMUM_CONTROL_CERTIFICATE_LEVELS))
        raise ValueError(
            "Policy key `minimum_control_certificate_level` must be one of " + supported
        )
    return normalized


def _effective_control_certificate_minimum(name: str, configured: str | None) -> str | None:
    if configured is None:
        return None
    natural_maximum = _CONTROL_CERTIFICATE_NATURAL_MAXIMUM[name]
    if _CONTROL_CERTIFICATE_LEVELS[configured] <= _CONTROL_CERTIFICATE_LEVELS[natural_maximum]:
        return configured
    return natural_maximum


def _control_certificate_validation_errors(name: str, diagnostic: JsonDict) -> list[str]:
    errors: list[str] = []
    if diagnostic.get("schema") != _CONTROL_CERTIFICATE_SCHEMAS[name]:
        errors.append("schema")
    if diagnostic.get("kind") != name:
        errors.append("kind")
    state = str(diagnostic.get("check_state") or "")
    level = str(diagnostic.get("certificate_level") or "")
    if state not in _CONTROL_CERTIFICATE_STATES:
        errors.append("check_state")
    if (
        level not in _CONTROL_CERTIFICATE_LEVELS
        or _CONTROL_CERTIFICATE_LEVELS[level]
        > _CONTROL_CERTIFICATE_LEVELS[_CONTROL_CERTIFICATE_NATURAL_MAXIMUM[name]]
    ):
        errors.append("certificate_level")
    if state in {"missing", "invalid"}:
        return sorted(set(errors))
    unmet = diagnostic.get("conditions_not_met")
    if state == "conditions_not_met" and (
        not isinstance(unmet, list) or not any(str(item).strip() for item in unmet)
    ):
        errors.append("conditions_not_met")
    if name == "terminal_sensitivity":
        errors.extend(_validate_terminal_sensitivity_certificate(diagnostic, state, level))
    elif name == "green_certificate":
        errors.extend(_validate_green_certificate(diagnostic, state, level))
    else:
        errors.extend(_validate_posterior_certificate(diagnostic, state, level))
    return sorted(set(errors))


def _validate_terminal_sensitivity_certificate(
    diagnostic: JsonDict,
    state: str,
    level: str,
) -> list[str]:
    """Validate terminal-sensitivity evidence without promoting empirical fits to proofs."""

    errors: list[str] = []
    decay = _optional_float(diagnostic.get("decay_rate"))
    r_squared = _optional_float(diagnostic.get("r_squared"))
    interval = diagnostic.get("bootstrap_ci")
    interval_lower = (
        _optional_float(interval[0]) if isinstance(interval, list) and len(interval) == 2 else None
    )
    records = diagnostic.get("records")
    horizons = diagnostic.get("distinct_horizons")
    floor = _optional_float(diagnostic.get("floor"))
    if floor is None:
        floor = 1e-15
    if floor <= 0.0:
        errors.append("floor")
    if decay is None:
        errors.append("decay_rate")
    if r_squared is None:
        errors.append("r_squared")
    if not _valid_interval(interval):
        errors.append("bootstrap_ci")
    if (
        not isinstance(records, list)
        or not records
        or any(not _valid_terminal_record(row, floor=floor) for row in records)
    ):
        errors.append("records")
    horizon_values = _positive_ints(horizons) if isinstance(horizons, list) else []
    if (
        not isinstance(horizons, list)
        or len(set(horizon_values)) < 3
        or (
            isinstance(records, list)
            and sorted(set(_terminal_record_horizons(records))) != sorted(set(horizon_values))
        )
    ):
        errors.append("distinct_horizons")
    record_count = diagnostic.get("record_count")
    if (
        isinstance(record_count, bool)
        or not isinstance(record_count, int)
        or not isinstance(records, list)
        or record_count != len(records)
    ):
        errors.append("record_count")
    if level != "empirical_only":
        errors.append("certificate_level")
    if isinstance(records, list) and records:
        recomputed = _recompute_terminal_summary(records)
        if recomputed is None:
            errors.append("records")
        else:
            if decay is None or not _close(decay, recomputed["decay_rate"]):
                errors.append("decay_rate")
            if r_squared is None or not _close(r_squared, recomputed["r_squared"]):
                errors.append("r_squared")
            if recomputed["seed_metadata_consistent"] is not True:
                errors.append("seed_metadata")
            recomputed_groups = recomputed["groups"]
            if state == "passed" and (
                not isinstance(recomputed_groups, list)
                or any(
                    int(group["distinct_horizon_count"]) < 3
                    or float(group["decay_rate"]) <= 1e-10
                    or float(group["r_squared"]) < 0.5
                    for group in recomputed_groups
                )
            ):
                errors.append("group_pass_conditions")
    if _valid_interval(interval) and decay is not None:
        assert isinstance(interval, list)
        lower = _optional_float(interval[0])
        upper = _optional_float(interval[1])
        if lower is None or upper is None or not lower <= decay <= upper:
            errors.append("bootstrap_ci")
    if state == "passed" and (
        decay is None
        or decay <= 1e-10
        or r_squared is None
        or r_squared < 0.5
        or not _valid_interval(interval)
        or interval_lower is None
        or interval_lower <= 0.0
    ):
        errors.append("passed_conditions")
    return errors


def _validate_green_certificate(
    diagnostic: JsonDict,
    state: str,
    level: str,
) -> list[str]:
    """Validate Green-certificate structure for the named low-dimensional surrogate."""

    errors: list[str] = []
    dimension = _optional_positive_int(diagnostic.get("dimension"))
    stable = _optional_nonnegative_int(diagnostic.get("stable_dimension"))
    unstable = _optional_nonnegative_int(diagnostic.get("unstable_dimension"))
    hyperbolicity = _optional_float(diagnostic.get("hyperbolicity_margin"))
    sigma_min = _optional_float(diagnostic.get("boundary_sigma_min"))
    recovery = _optional_float(diagnostic.get("maximum_recovery_residual"))
    horizons = diagnostic.get("horizons")
    moduli = diagnostic.get("eigenvalue_moduli")
    if (
        dimension is None
        or stable is None
        or unstable is None
        or stable > dimension
        or unstable > dimension
        or stable + unstable > dimension
    ):
        errors.append("stable_unstable_dimension")
    if hyperbolicity is None:
        errors.append("hyperbolicity_margin")
    modulus_values = _finite_nonnegative_values(moduli)
    if modulus_values is None or not modulus_values:
        errors.append("eigenvalue_moduli")
    else:
        recomputed_margin = min(abs(value - 1.0) for value in modulus_values)
        if hyperbolicity is None or not _close(hyperbolicity, recomputed_margin):
            errors.append("hyperbolicity_margin")
        if dimension is None or len(modulus_values) != dimension:
            errors.append("eigenvalue_moduli")
        else:
            tolerance = 1e-8
            derived_stable = sum(value < 1.0 - tolerance for value in modulus_values)
            derived_unstable = sum(value > 1.0 + tolerance for value in modulus_values)
            derived_center = dimension - derived_stable - derived_unstable
            if (
                stable != derived_stable
                or unstable != derived_unstable
                or (state == "passed" and derived_center != 0)
            ):
                errors.append("stable_unstable_dimension")
    if sigma_min is None:
        errors.append("boundary_sigma_min")
    if recovery is None or recovery < 0.0:
        errors.append("maximum_recovery_residual")
    horizon_sigmas: list[float] = []
    horizon_recoveries: list[float] = []
    horizon_passes: list[bool] = []
    if not isinstance(horizons, list) or not horizons:
        errors.append("horizons")
    else:
        for row in horizons:
            if not isinstance(row, dict):
                errors.append("horizons")
                break
            row_sigma = _optional_float(row.get("boundary_sigma_min"))
            row_recovery = _optional_float(row.get("coefficient_recovery_residual"))
            row_passed = row.get("passed")
            if (
                _optional_positive_int(row.get("horizon")) is None
                or row_sigma is None
                or row_sigma < 0.0
                or row_recovery is None
                or row_recovery < 0.0
                or not isinstance(row_passed, bool)
            ):
                errors.append("horizons")
                break
            horizon_sigmas.append(row_sigma)
            horizon_recoveries.append(row_recovery)
            horizon_passes.append(row_passed)
    if horizon_sigmas and (sigma_min is None or not _close(sigma_min, min(horizon_sigmas))):
        errors.append("boundary_sigma_min")
    if horizon_recoveries and (recovery is None or not _close(recovery, max(horizon_recoveries))):
        errors.append("maximum_recovery_residual")
    if state == "passed" and horizon_passes and not all(horizon_passes):
        errors.append("horizons")
    if state == "passed" and (
        hyperbolicity is None
        or hyperbolicity <= 1e-8
        or stable is None
        or stable < 1
        or unstable is None
        or unstable < 1
        or dimension is None
        or stable + unstable != dimension
        or sigma_min is None
        or sigma_min <= 1e-8
        or recovery is None
        or recovery > 1e-8
        or not horizon_passes
        or not all(horizon_passes)
    ):
        errors.append("passed_conditions")
    if level == "certificate_verified" and (
        diagnostic.get("premises_complete") is not True
        or not str(diagnostic.get("verified_scope") or "").strip()
    ):
        errors.append("verified_provenance")
    if state == "passed" and level not in {"surrogate_consistent", "certificate_verified"}:
        errors.append("certificate_level")
    if state == "conditions_not_met" and level != "empirical_only":
        errors.append("certificate_level")
    return errors


def _validate_posterior_certificate(
    diagnostic: JsonDict,
    state: str,
    level: str,
) -> list[str]:
    """Validate local posterior-certificate bounds and their provenance."""

    errors: list[str] = []
    epsilon = _optional_float(diagnostic.get("residual_norm_upper"))
    beta = _optional_float(diagnostic.get("jacobian_inverse_norm_upper"))
    lipschitz = _optional_float(diagnostic.get("jacobian_lipschitz_upper"))
    radius = _optional_float(diagnostic.get("neighborhood_radius"))
    eta = _optional_float(diagnostic.get("eta"))
    contraction = _optional_float(diagnostic.get("K"))
    h_value = _optional_float(diagnostic.get("h"))
    existence_radius = _optional_float(diagnostic.get("existence_radius"))
    h_margin = _optional_float(diagnostic.get("h_margin"))
    neighborhood_margin = _optional_float(diagnostic.get("neighborhood_margin"))
    if epsilon is None or epsilon < 0.0:
        errors.append("residual_norm_upper")
    if beta is None or beta <= 0.0:
        errors.append("jacobian_inverse_norm_upper")
    if lipschitz is None or lipschitz < 0.0:
        errors.append("jacobian_lipschitz_upper")
    if radius is None or radius <= 0.0:
        errors.append("neighborhood_radius")
    if eta is None or beta is None or epsilon is None or not _close(eta, beta * epsilon):
        errors.append("eta")
    if (
        contraction is None
        or beta is None
        or lipschitz is None
        or not _close(contraction, beta * lipschitz)
    ):
        errors.append("K")
    if (
        h_value is None
        or eta is None
        or contraction is None
        or not _close(h_value, eta * contraction)
    ):
        errors.append("h")
    expected_radius: float | None = None
    if eta is not None and contraction is not None and h_value is not None and h_value <= 0.5:
        expected_radius = (
            eta
            if contraction == 0.0
            else 2.0 * eta / (1.0 + math.sqrt(max(0.0, 1.0 - 2.0 * h_value)))
        )
        if existence_radius is None or not _close(existence_radius, expected_radius):
            errors.append("existence_radius")
    if h_value is None or h_margin is None or not _close(h_margin, 0.5 - h_value):
        errors.append("h_margin")
    if expected_radius is None:
        if existence_radius is not None or neighborhood_margin is not None:
            errors.append("neighborhood_margin")
    elif (
        radius is None
        or existence_radius is None
        or neighborhood_margin is None
        or not _close(neighborhood_margin, radius - existence_radius)
    ):
        errors.append("neighborhood_margin")
    if state == "passed" and (
        h_value is None
        or h_value > 0.5
        or existence_radius is None
        or radius is None
        or existence_radius > radius
    ):
        errors.append("passed_conditions")
    if level == "certificate_verified":
        provenance = _dict(diagnostic.get("bound_provenance"))
        if (
            diagnostic.get("provenance_complete") is not True
            or provenance.get("kind") != "certified_bounds"
            or provenance.get("conservative") is not True
            or not str(provenance.get("scope") or "").strip()
            or not str(provenance.get("source") or "").strip()
        ):
            errors.append("verified_provenance")
    if state == "passed" and level not in {
        "surrogate_consistent",
        "certificate_verified",
        "insufficient_evidence",
    }:
        errors.append("certificate_level")
    if state == "conditions_not_met" and level not in {
        "surrogate_consistent",
        "insufficient_evidence",
    }:
        errors.append("certificate_level")
    return errors


def _positive_ints(values: list[object]) -> list[int]:
    return [
        value
        for value in values
        if isinstance(value, int) and not isinstance(value, bool) and value > 0
    ]


def _finite_nonnegative_values(value: object) -> list[float] | None:
    if not isinstance(value, list):
        return None
    converted = [_optional_float(item) for item in value]
    if any(item is None or item < 0.0 for item in converted):
        return None
    return [cast(float, item) for item in converted]


def _optional_nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _valid_terminal_record(value: object, *, floor: float) -> bool:
    if not isinstance(value, dict):
        return False
    horizon = _optional_positive_int(value.get("horizon"))
    early_step = _optional_nonnegative_int(value.get("early_step"))
    distance = _optional_positive_int(value.get("distance_to_terminal"))
    perturbation = _optional_float(value.get("perturbation_norm"))
    control_delta = _optional_float(value.get("control_delta_norm"))
    sensitivity = _optional_float(value.get("sensitivity"))
    log_sensitivity = _optional_float(value.get("log_sensitivity"))
    shape_valid = bool(
        horizon is not None
        and early_step is not None
        and early_step < horizon
        and distance == horizon - early_step
        and perturbation is not None
        and perturbation > 0.0
        and control_delta is not None
        and control_delta >= 0.0
        and sensitivity is not None
        and sensitivity >= 0.0
        and log_sensitivity is not None
    )
    if not shape_valid:
        return False
    assert perturbation is not None
    assert control_delta is not None
    assert sensitivity is not None
    assert log_sensitivity is not None
    expected_sensitivity = control_delta / perturbation
    return _close(sensitivity, expected_sensitivity) and _close(
        log_sensitivity,
        math.log(max(expected_sensitivity, floor)),
    )


def _terminal_record_horizons(records: list[object]) -> list[int]:
    return [
        value
        for row in records
        if isinstance(row, dict)
        for value in [_optional_positive_int(row.get("horizon"))]
        if value is not None
    ]


def _recompute_terminal_summary(records: list[object]) -> JsonDict | None:
    grouped: dict[tuple[str, int, str, str], dict[int, list[float]]] = {}
    seed_presence: dict[tuple[str, int, str, str], list[bool]] = {}
    for raw in records:
        if not isinstance(raw, dict):
            return None
        horizon = _optional_positive_int(raw.get("horizon"))
        early_step = _optional_nonnegative_int(raw.get("early_step"))
        log_sensitivity = _optional_float(raw.get("log_sensitivity"))
        if horizon is None or early_step is None or log_sensitivity is None:
            return None
        key = (
            str(raw.get("intervention_kind") or "terminal_objective"),
            early_step,
            str(raw.get("checkpoint") or ""),
            str(raw.get("model") or ""),
        )
        seed_presence.setdefault(key, []).append("seed" in raw)
        grouped.setdefault(key, {}).setdefault(horizon - early_step, []).append(log_sensitivity)
    fits: list[JsonDict] = []
    for distance_rows in grouped.values():
        points = [
            (float(distance), sum(values) / len(values))
            for distance, values in sorted(distance_rows.items())
        ]
        fit = _fit_line(points)
        if fit is None:
            return None
        fit["distinct_horizon_count"] = len(points)
        fits.append(fit)
    if not fits:
        return None
    return {
        "decay_rate": sum(float(fit["decay_rate"]) for fit in fits) / len(fits),
        "r_squared": min(float(fit["r_squared"]) for fit in fits),
        "groups": fits,
        "seed_metadata_consistent": all(
            not any(values) or all(values) for values in seed_presence.values()
        ),
    }


def _fit_line(points: list[tuple[float, float]]) -> JsonDict | None:
    if len(points) < 2:
        return None
    mean_x = sum(point[0] for point in points) / len(points)
    mean_y = sum(point[1] for point in points) / len(points)
    denominator = sum((point[0] - mean_x) ** 2 for point in points)
    if denominator <= 0.0:
        return None
    slope = sum((point[0] - mean_x) * (point[1] - mean_y) for point in points) / denominator
    intercept = mean_y - slope * mean_x
    residual = sum((point[1] - (intercept + slope * point[0])) ** 2 for point in points)
    total = sum((point[1] - mean_y) ** 2 for point in points)
    r_squared = (
        1.0
        if total <= 1e-24 and residual <= 1e-24
        else (0.0 if total <= 1e-24 else 1.0 - residual / total)
    )
    return {"decay_rate": -slope, "r_squared": r_squared}


def _close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-8, abs_tol=1e-12)
