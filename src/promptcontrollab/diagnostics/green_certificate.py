"""Finite-dimensional Green response and boundary transversality diagnostics."""

from __future__ import annotations

import csv
import io
import math
from pathlib import Path
from typing import Any, cast

from promptcontrollab.core.files import JsonDict, ensure_dir, read_json, write_json
from promptcontrollab.core.optional import require_module

_NUMERICAL_TOLERANCE = 1e-8
_RECOVERY_TOLERANCE = 1e-8


def analyze_green_certificate(
    *,
    surrogate_path: Path,
    horizons: list[int],
    out_dir: Path,
    premises_path: Path | None = None,
) -> JsonDict:
    """Check hyperbolicity and scaled boundary invertibility on a fixed surrogate."""

    np = cast(Any, require_module("numpy", feature="Green certificate", extra="research"))
    scipy_linalg = cast(
        Any,
        require_module("scipy.linalg", feature="Green certificate", extra="research"),
    )
    normalized_horizons = _normalize_horizons(horizons)
    matrix, b0, bn, graph_s, recurrence_kind = _load_surrogate(np, surrogate_path)
    dimension = int(matrix.shape[0])
    premises = read_json(premises_path) if premises_path is not None else {}
    stable_schur, stable_vectors, stable_dimension = scipy_linalg.schur(
        matrix,
        output="complex",
        sort=lambda eigenvalue: abs(eigenvalue) < 1.0 - _NUMERICAL_TOLERANCE,
    )
    unstable_schur, unstable_vectors, unstable_dimension = scipy_linalg.schur(
        matrix,
        output="complex",
        sort=lambda eigenvalue: abs(eigenvalue) > 1.0 + _NUMERICAL_TOLERANCE,
    )
    stable_dimension = int(stable_dimension)
    unstable_dimension = int(unstable_dimension)
    center_dimension = dimension - stable_dimension - unstable_dimension
    eigenvalues = np.linalg.eigvals(matrix)
    hyperbolicity_margin = float(min(abs(abs(value) - 1.0) for value in eigenvalues))
    expected_stable = _expected_stable_dimension(premises, dimension)
    conditions_not_met: list[str] = []
    if hyperbolicity_margin <= _NUMERICAL_TOLERANCE:
        conditions_not_met.append("unit_circle_spectrum")
    if (
        stable_dimension == 0
        or unstable_dimension == 0
        or stable_dimension != expected_stable
    ):
        conditions_not_met.append("stable_unstable_dimension")

    stable_basis = stable_vectors[:, :stable_dimension]
    unstable_basis = unstable_vectors[:, :unstable_dimension]
    stable_block = stable_schur[:stable_dimension, :stable_dimension]
    unstable_block = unstable_schur[:unstable_dimension, :unstable_dimension]
    stable_invariance_residual = _invariance_residual(
        np,
        matrix,
        stable_basis,
        stable_block,
    )
    unstable_invariance_residual = _invariance_residual(
        np,
        matrix,
        unstable_basis,
        unstable_block,
    )
    if max(stable_invariance_residual, unstable_invariance_residual) > _RECOVERY_TOLERANCE:
        conditions_not_met.append("subspace_invariance")
    horizon_rows: list[JsonDict] = []
    boundary_threshold = max(
        _NUMERICAL_TOLERANCE,
        _positive_premise_number(premises, "uniform_boundary_sigma_min_lower") or 0.0,
    )
    for horizon in normalized_horizons:
        boundary = _scaled_boundary_matrix(
            np,
            b0,
            bn,
            stable_basis,
            unstable_basis,
            stable_block,
            unstable_block,
            horizon,
        )
        singular_values = np.linalg.svd(boundary, compute_uv=False)
        sigma_min = float(min(singular_values)) if singular_values.size else 0.0
        sigma_max = float(max(singular_values)) if singular_values.size else 0.0
        inverse_norm = math.inf if sigma_min <= 0.0 else 1.0 / sigma_min
        condition_number = math.inf if sigma_min <= 0.0 else sigma_max / sigma_min
        recovery_residual = _coefficient_recovery_residual(np, boundary)
        horizon_rows.append(
            {
                "horizon": horizon,
                "boundary_sigma_min": sigma_min,
                "boundary_inverse_norm": inverse_norm,
                "boundary_condition_number": condition_number,
                "coefficient_recovery_residual": recovery_residual,
                "passed": sigma_min >= boundary_threshold
                and recovery_residual <= _RECOVERY_TOLERANCE,
            }
        )
    if any(not bool(row["passed"]) for row in horizon_rows):
        conditions_not_met.append("boundary_transversality")
    declared_margin = _positive_premise_number(premises, "uniform_unit_circle_margin_lower")
    if declared_margin is not None and hyperbolicity_margin < declared_margin:
        conditions_not_met.append("declared_hyperbolicity_margin")
    graph_boundary = _graph_boundary_check(
        np,
        graph_s,
        stable_basis,
        unstable_basis,
        stable_block,
        unstable_block,
        normalized_horizons,
    )
    check_state = "passed" if not conditions_not_met else "conditions_not_met"
    premises_complete, premise_gaps = _complete_green_premises(
        premises,
        minimum_horizon=min(normalized_horizons),
    )
    if check_state != "passed":
        certificate_level = "empirical_only"
    elif premises_complete:
        certificate_level = "certificate_verified"
    else:
        certificate_level = "surrogate_consistent"
    min_sigma = min(float(row["boundary_sigma_min"]) for row in horizon_rows)
    max_recovery = max(float(row["coefficient_recovery_residual"]) for row in horizon_rows)
    stable_rate, unstable_rate = _spectral_rates(eigenvalues)
    payload: JsonDict = {
        "schema": "prompt_control_lab.green_certificate.v1",
        "kind": "green_certificate",
        "source": str(surrogate_path),
        "premises_source": str(premises_path) if premises_path is not None else None,
        "recurrence_kind": recurrence_kind,
        "certificate_level": certificate_level,
        "check_state": check_state,
        "dimension": dimension,
        "stable_dimension": stable_dimension,
        "unstable_dimension": unstable_dimension,
        "center_dimension": center_dimension,
        "expected_stable_dimension": expected_stable,
        "stable_invariance_residual": stable_invariance_residual,
        "unstable_invariance_residual": unstable_invariance_residual,
        "eigenvalue_moduli": [float(abs(value)) for value in eigenvalues],
        "hyperbolicity_margin": hyperbolicity_margin,
        "stable_decay_rate": stable_rate,
        "unstable_backward_decay_rate": unstable_rate,
        "boundary_sigma_min": min_sigma,
        "maximum_recovery_residual": max_recovery,
        "horizons": horizon_rows,
        "graph_boundary": graph_boundary,
        "terminal_only_decay_claim": bool(
            graph_boundary.get("provided")
            and graph_boundary.get("check_state") == "passed"
            and check_state == "passed"
        ),
        "premises_complete": premises_complete,
        "premise_gaps": premise_gaps,
        "verified_scope": (
            str(premises.get("scope")) if certificate_level == "certificate_verified" else None
        ),
        "conditions_not_met": sorted(set(conditions_not_met)),
        "observation": (
            f"The fixed {dimension}-dimensional surrogate has unit-circle margin "
            f"{hyperbolicity_margin:.6g} and sampled boundary sigma_min {min_sigma:.6g}."
        ),
        "explanation": (
            "The sampled surrogate is consistent with a hyperbolic Green-response boundary "
            "decomposition."
            if check_state == "passed"
            else "One or more sampled hyperbolicity or boundary-transversality conditions were "
            "not met."
        ),
        "scope": str(premises.get("scope") or "the supplied fixed-dimensional surrogate"),
        "claim_boundary": (
            "A finite-dimensional floating-point check does not prove the full language model, "
            "global optimality, or nonexistence when conditions are not met. Ordinary mixed "
            "boundaries also do not imply one-sided terminal decay without the graph condition."
        ),
        "next_action": (
            "Retain the controlled premise record and recovery evidence with this surrogate."
            if certificate_level == "certificate_verified"
            else "Inspect the missing premises or failed horizon margins before treating this as "
            "a certificate."
        ),
    }
    ensure_dir(out_dir)
    write_json(out_dir / "green_certificate.json", payload)
    (out_dir / "green_certificate.csv").write_text(
        _render_csv(horizon_rows),
        encoding="utf-8",
    )
    (out_dir / "green_certificate.svg").write_text(
        _render_svg(payload),
        encoding="utf-8",
    )
    return payload


def _normalize_horizons(horizons: list[int]) -> list[int]:
    if not horizons:
        raise ValueError("Provide at least one --horizon")
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value <= 0
        for value in horizons
    ):
        raise ValueError("Each --horizon must be a positive integer")
    return sorted(set(horizons))


def _load_surrogate(np: Any, path: Path) -> tuple[Any, Any, Any, Any | None, str]:
    with np.load(path, allow_pickle=False) as data:
        if "M" in data:
            matrix = np.asarray(data["M"], dtype=float)
            recurrence_kind = "M"
        elif "L" in data and "N" in data:
            left = np.asarray(data["L"], dtype=float)
            right = np.asarray(data["N"], dtype=float)
            _validate_square(np, left, "L")
            _validate_square(np, right, "N")
            if left.shape != right.shape:
                raise ValueError("L and N must have matching shapes")
            try:
                matrix = np.linalg.solve(left, right)
            except np.linalg.LinAlgError as exc:
                raise ValueError("L must be invertible for the generalized recurrence") from exc
            recurrence_kind = "generalized_LN"
        else:
            raise ValueError(f"{path} must contain M or both L and N")
        if "B0" not in data or "BN" not in data:
            raise ValueError(f"{path} must contain B0 and BN")
        b0 = np.asarray(data["B0"], dtype=float)
        bn = np.asarray(data["BN"], dtype=float)
        graph_s = np.asarray(data["graph_S"], dtype=float) if "graph_S" in data else None
    _validate_square(np, matrix, "M")
    dimension = int(matrix.shape[0])
    if b0.shape != (dimension, dimension) or bn.shape != (dimension, dimension):
        raise ValueError("B0 and BN must be square matrices matching the recurrence dimension")
    if not np.isfinite(b0).all() or not np.isfinite(bn).all():
        raise ValueError("B0 and BN must contain only finite values")
    return matrix, b0, bn, graph_s, recurrence_kind


def _validate_square(np: Any, value: Any, name: str) -> None:
    if value.ndim != 2 or value.shape[0] != value.shape[1] or value.shape[0] < 1:
        raise ValueError(f"{name} must be a non-empty square matrix")
    if not np.isfinite(value).all():
        raise ValueError(f"{name} must contain only finite values")


def _expected_stable_dimension(premises: JsonDict, dimension: int) -> int:
    configured = premises.get("expected_stable_dimension")
    if isinstance(configured, int) and not isinstance(configured, bool):
        if not 0 <= configured <= dimension:
            raise ValueError("expected_stable_dimension must be within the surrogate dimension")
        return configured
    return dimension // 2


def _scaled_boundary_matrix(
    np: Any,
    b0: Any,
    bn: Any,
    stable_basis: Any,
    unstable_basis: Any,
    stable_block: Any,
    unstable_block: Any,
    horizon: int,
) -> Any:
    stable_power = np.linalg.matrix_power(stable_block, horizon)
    if unstable_block.shape[0]:
        try:
            unstable_inverse = np.linalg.inv(unstable_block)
        except np.linalg.LinAlgError as exc:
            raise ValueError("The unstable Schur block must be invertible") from exc
        unstable_backward = np.linalg.matrix_power(unstable_inverse, horizon)
    else:
        unstable_backward = unstable_block
    stable_columns = b0 @ stable_basis + bn @ stable_basis @ stable_power
    unstable_columns = b0 @ unstable_basis @ unstable_backward + bn @ unstable_basis
    return np.concatenate([stable_columns, unstable_columns], axis=1)


def _coefficient_recovery_residual(np: Any, boundary: Any) -> float:
    dimension = int(boundary.shape[1])
    coefficients = np.linspace(0.5, 1.5, dimension).astype(complex)
    target = boundary @ coefficients
    recovered, _, _, _ = np.linalg.lstsq(boundary, target, rcond=None)
    return float(
        np.linalg.norm(recovered - coefficients)
        / max(float(np.linalg.norm(coefficients)), _NUMERICAL_TOLERANCE)
    )


def _invariance_residual(np: Any, matrix: Any, basis: Any, block: Any) -> float:
    if basis.shape[1] == 0:
        return 0.0
    propagated = matrix @ basis
    residual = propagated - basis @ block
    return float(
        np.linalg.norm(residual)
        / max(float(np.linalg.norm(propagated)), _NUMERICAL_TOLERANCE)
    )


def _graph_boundary_check(
    np: Any,
    graph_s: Any | None,
    stable_basis: Any,
    unstable_basis: Any,
    stable_block: Any,
    unstable_block: Any,
    horizons: list[int],
) -> JsonDict:
    """Evaluate the optional terminal graph-boundary condition on the surrogate."""

    if graph_s is None:
        return {
            "provided": False,
            "check_state": "missing",
            "claim": "terminal_only_decay_not_checked",
        }
    dimension = int(stable_basis.shape[0])
    if dimension % 2 != 0:
        return {
            "provided": True,
            "check_state": "invalid",
            "reason": "graph_boundary_requires_even_state_costate_dimension",
        }
    half = dimension // 2
    if graph_s.shape != (half, half) or not np.isfinite(graph_s).all():
        return {
            "provided": True,
            "check_state": "invalid",
            "reason": "graph_S_shape_or_finiteness",
        }
    if stable_basis.shape[1] != half or unstable_basis.shape[1] != half:
        return {
            "provided": True,
            "check_state": "conditions_not_met",
            "reason": "graph_boundary_requires_balanced_splitting",
        }
    xs, ps = stable_basis[:half, :], stable_basis[half:, :]
    xu, pu = unstable_basis[:half, :], unstable_basis[half:, :]
    rows: list[JsonDict] = []
    for horizon in horizons:
        ds_power = np.linalg.matrix_power(stable_block, horizon)
        try:
            du_backward = np.linalg.matrix_power(np.linalg.inv(unstable_block), horizon)
        except np.linalg.LinAlgError:
            return {
                "provided": True,
                "check_state": "invalid",
                "reason": "noninvertible_unstable_block",
            }
        upper = np.concatenate([xs, xu @ du_backward], axis=1)
        lower = np.concatenate([(ps - graph_s @ xs) @ ds_power, pu - graph_s @ xu], axis=1)
        matrix = np.concatenate([upper, lower], axis=0)
        singular_values = np.linalg.svd(matrix, compute_uv=False)
        sigma_min = float(min(singular_values)) if singular_values.size else 0.0
        rows.append({"horizon": horizon, "sigma_min": sigma_min})
    passed = all(float(row["sigma_min"]) > _NUMERICAL_TOLERANCE for row in rows)
    return {
        "provided": True,
        "check_state": "passed" if passed else "conditions_not_met",
        "horizons": rows,
        "minimum_sigma_min": min(float(row["sigma_min"]) for row in rows),
        "claim": "terminal_only_graph_boundary_checked",
    }


def _complete_green_premises(
    premises: JsonDict,
    *,
    minimum_horizon: int,
) -> tuple[bool, list[str]]:
    required_true = [
        "fixed_dimension",
        "existing_local_branch",
        "interior_control",
        "uniform_c3_neighborhood",
    ]
    gaps = [key for key in required_true if premises.get(key) is not True]
    for key in (
        "uniform_control_hessian_inverse_bound",
        "uniform_unit_circle_margin_lower",
        "uniform_boundary_sigma_min_lower",
    ):
        if _positive_premise_number(premises, key) is None:
            gaps.append(key)
    horizon_family = premises.get("horizon_family")
    family = horizon_family if isinstance(horizon_family, dict) else {}
    if family.get("uniform") is not True:
        gaps.append("horizon_family.uniform")
    family_minimum = family.get("minimum")
    if (
        isinstance(family_minimum, bool)
        or not isinstance(family_minimum, int)
        or family_minimum <= 0
        or family_minimum > minimum_horizon
    ):
        gaps.append("horizon_family.minimum")
    provenance = premises.get("provenance")
    provenance_dict = provenance if isinstance(provenance, dict) else {}
    if provenance_dict.get("kind") != "controlled_bound_record":
        gaps.append("provenance.kind")
    if provenance_dict.get("conservative") is not True:
        gaps.append("provenance.conservative")
    if not str(provenance_dict.get("source") or "").strip():
        gaps.append("provenance.source")
    if premises.get("source_kind") != "certified_bounds":
        gaps.append("source_kind")
    if not str(premises.get("scope") or "").strip():
        gaps.append("scope")
    return not gaps, gaps


def _positive_premise_number(premises: JsonDict, key: str) -> float | None:
    value = premises.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    converted = float(value)
    return converted if math.isfinite(converted) and converted > 0.0 else None


def _spectral_rates(eigenvalues: Any) -> tuple[float | None, float | None]:
    stable = [float(abs(value)) for value in eigenvalues if abs(value) < 1.0]
    unstable = [float(abs(value)) for value in eigenvalues if abs(value) > 1.0]
    stable_rate = -math.log(max(stable)) if stable else None
    unstable_rate = math.log(min(unstable)) if unstable else None
    return stable_rate, unstable_rate


def _render_csv(rows: list[JsonDict]) -> str:
    fields = [
        "horizon",
        "boundary_sigma_min",
        "boundary_inverse_norm",
        "boundary_condition_number",
        "coefficient_recovery_residual",
        "passed",
    ]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def _render_svg(payload: JsonDict) -> str:
    rows = payload.get("horizons")
    horizon_rows = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    width, height = 960, 540
    left, right, top, bottom = 90, 40, 70, 80
    horizons = [float(row["horizon"]) for row in horizon_rows] or [0.0, 1.0]
    sigmas = [float(row["boundary_sigma_min"]) for row in horizon_rows] or [0.0, 1.0]
    xmin, xmax = min(horizons), max(horizons)
    ymin, ymax = 0.0, max(sigmas)
    if xmax <= xmin:
        xmax = xmin + 1.0
    if ymax <= ymin:
        ymax = 1.0

    def sx(value: float) -> float:
        return left + (value - xmin) / (xmax - xmin) * (width - left - right)

    def sy(value: float) -> float:
        return height - bottom - (value - ymin) / (ymax - ymin) * (height - top - bottom)

    points = "".join(
        f'<circle cx="{sx(float(row["horizon"])):.2f}" '
        f'cy="{sy(float(row["boundary_sigma_min"])):.2f}" r="6" fill="#0f766e"/>'
        for row in horizon_rows
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
viewBox="0 0 {width} {height}" role="img" aria-label="Green boundary singular values">
<rect width="100%" height="100%" fill="#f8fafc"/><text x="48" y="38" font-family="Arial"
font-size="24" font-weight="700" fill="#0f172a">Green boundary transversality</text>
<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}"
stroke="#64748b"/><line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}"
stroke="#64748b"/>{points}<text x="{width/2}" y="{height-24}" text-anchor="middle"
font-family="Arial" font-size="18">Horizon N</text><text x="24" y="{height/2}"
transform="rotate(-90 24 {height/2})" text-anchor="middle" font-family="Arial"
font-size="18">boundary sigma_min</text></svg>"""
