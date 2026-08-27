"""Terminal-objective sensitivity diagnostics for records and linear BVP surrogates."""

from __future__ import annotations

import csv
import io
import math
from pathlib import Path
from typing import Any, cast

from promptcontrollab.core.files import JsonDict, ensure_dir, read_jsonl, write_json
from promptcontrollab.core.optional import require_module

_NUMERICAL_FLOOR = 1e-15


def analyze_terminal_sensitivity(
    *,
    out_dir: Path,
    records_path: Path | None = None,
    surrogate_path: Path | None = None,
    horizons: list[int] | None = None,
    early_steps: list[int] | None = None,
    bootstrap_samples: int = 1000,
) -> JsonDict:
    """Fit early-control sensitivity against distance from the terminal boundary."""

    if (records_path is None) == (surrogate_path is None):
        raise ValueError("Provide exactly one of --records or --surrogate")
    np = cast(
        Any,
        require_module("numpy", feature="terminal sensitivity diagnostics", extra="research"),
    )
    if records_path is not None:
        raw_records = read_jsonl(records_path)
        source_kind = "intervention_records"
        source = str(records_path)
    else:
        assert surrogate_path is not None
        raw_records = _run_surrogate(
            np,
            surrogate_path,
            horizons=horizons or [],
            early_steps=early_steps or [0],
        )
        source_kind = "linear_bvp_surrogate"
        source = str(surrogate_path)
    records, floor_count = _normalize_records(raw_records)
    _validate_seed_metadata(records)
    distinct_horizons = sorted({int(row["horizon"]) for row in records})
    groups = _group_fits(np, records)
    insufficient_groups = [
        str(group["group_id"])
        for group in groups
        if len(cast(list[object], group["distinct_horizons"])) < 3
    ]
    ensure_dir(out_dir)
    if len(distinct_horizons) < 3 or insufficient_groups:
        unmet = (
            ["minimum_three_distinct_horizons"]
            if len(distinct_horizons) < 3
            else []
        )
        if insufficient_groups:
            unmet.append("minimum_three_distinct_horizons_per_group")
        payload: JsonDict = {
            "schema": "prompt_control_lab.terminal_sensitivity.v1",
            "kind": "terminal_sensitivity",
            "source": source,
            "source_kind": source_kind,
            "certificate_level": "insufficient_evidence",
            "check_state": "missing",
            "record_count": len(records),
            "distinct_horizons": distinct_horizons,
            "floor_clipped_count": floor_count,
            "groups": groups,
            "insufficient_groups": insufficient_groups,
            "records": records,
            "conditions_not_met": unmet,
            "observation": "At least one fitted group has fewer than three distinct horizons.",
            "explanation": (
                "A within-group exponential distance-to-terminal trend cannot be fitted "
                "reliably."
            ),
            "scope": "The supplied intervention records or low-dimensional surrogate.",
            "claim_boundary": (
                "This diagnostic does not prove terminal insensitivity or nonexistence of a "
                "turnpike response when evidence is missing."
            ),
            "next_action": "Record at least three distinct sequence horizons.",
        }
        _write_outputs(out_dir, payload)
        return payload

    fit = _aggregate_group_fits(np, groups)
    bootstrap_ci = _bootstrap_group_decay_ci(
        np,
        records,
        samples=bootstrap_samples,
    )
    point_estimate_passed = all(
        float(group["decay_rate"]) > 1e-10 and float(group["r_squared"]) >= 0.5
        for group in groups
    )
    interval_passed = bootstrap_ci is not None and bootstrap_ci[0] > 0.0
    if bootstrap_ci is None:
        check_state = "missing"
        certificate_level = "insufficient_evidence"
        conditions_not_met = ["bootstrap_interval_unavailable"]
    else:
        passed = point_estimate_passed and interval_passed
        check_state = "passed" if passed else "conditions_not_met"
        certificate_level = "empirical_only"
        conditions_not_met = []
        if not point_estimate_passed:
            conditions_not_met.append("positive_exponential_decay")
        if not interval_passed:
            conditions_not_met.append("positive_bootstrap_decay_interval")
    payload = {
        "schema": "prompt_control_lab.terminal_sensitivity.v1",
        "kind": "terminal_sensitivity",
        "source": source,
        "source_kind": source_kind,
        "certificate_level": certificate_level,
        "check_state": check_state,
        "record_count": len(records),
        "distinct_horizons": distinct_horizons,
        "early_steps": sorted({int(row["early_step"]) for row in records}),
        "intervention_kinds": sorted({str(row["intervention_kind"]) for row in records}),
        "slope": fit["slope"],
        "intercept": fit["intercept"],
        "decay_rate": fit["decay_rate"],
        "r_squared": fit["r_squared"],
        "bootstrap_ci": bootstrap_ci,
        "bootstrap_samples": bootstrap_samples,
        "bootstrap_unit": "seed_trajectory_or_horizon_cluster_within_group",
        "fit_strategy": "within_group_equal_weighted_slopes",
        "floor": _NUMERICAL_FLOOR,
        "floor_clipped_count": floor_count,
        "groups": groups,
        "records": records,
        "conditions_not_met": conditions_not_met,
        "observation": (
            f"Estimated equal-weighted within-group decay alpha={fit['decay_rate']:.6g}; "
            f"the minimum group R^2 is {fit['r_squared']:.4f}."
        ),
        "explanation": (
            "Early control changes become smaller as the terminal boundary moves farther away."
            if check_state == "passed"
            else "The bootstrap interval could not be estimated from the supplied clusters."
            if check_state == "missing"
            else "The supplied records do not show a sufficiently clear positive exponential "
            "decay trend."
        ),
        "scope": "The supplied interventions and sampled horizons.",
        "claim_boundary": (
            "Finite-horizon sensitivity is empirical evidence only. It does not prove a "
            "horizon-uniform Green estimate or a full-model terminal turnpike theorem."
        ),
        "next_action": (
            "Pair this trend with a Green boundary check before making a certificate claim."
            if check_state == "passed"
            else "Add horizons, repeat seeds, and inspect intervention-specific fits."
        ),
    }
    _write_outputs(out_dir, payload)
    return payload


def _run_surrogate(
    np: Any,
    path: Path,
    *,
    horizons: list[int],
    early_steps: list[int],
) -> list[JsonDict]:
    if len(set(horizons)) < 1:
        raise ValueError("--surrogate requires at least one --horizon")
    if any(not isinstance(value, int) or value <= 0 for value in horizons):
        raise ValueError("Each --horizon must be a positive integer")
    if any(not isinstance(value, int) or value < 0 for value in early_steps):
        raise ValueError("Each --early-step must be a non-negative integer")
    with np.load(path, allow_pickle=False) as data:
        required = ["M", "B0", "BN", "terminal_perturbations", "control_readout"]
        missing = [name for name in required if name not in data]
        if missing:
            raise ValueError(f"{path} is missing arrays: {', '.join(missing)}")
        matrix = np.asarray(data["M"], dtype=float)
        b0 = np.asarray(data["B0"], dtype=float)
        bn = np.asarray(data["BN"], dtype=float)
        perturbations = np.asarray(data["terminal_perturbations"], dtype=float)
        readout = np.asarray(data["control_readout"], dtype=float)
    _validate_square_matrix(np, matrix, "M")
    dimension = int(matrix.shape[0])
    if b0.shape != (dimension, dimension) or bn.shape != (dimension, dimension):
        raise ValueError("B0 and BN must be square matrices matching M")
    if perturbations.ndim == 1:
        perturbations = perturbations.reshape(1, -1)
    if perturbations.ndim != 2 or perturbations.shape[1] != dimension:
        raise ValueError("terminal_perturbations must be shaped [records, state_dim]")
    if readout.ndim == 1:
        readout = readout.reshape(1, -1)
    if readout.ndim != 2 or readout.shape[1] != dimension:
        raise ValueError("control_readout must be shaped [control_dim, state_dim]")
    if not all(np.isfinite(value).all() for value in (b0, bn, perturbations, readout)):
        raise ValueError("Surrogate arrays must contain only finite values")

    rows: list[JsonDict] = []
    for horizon in sorted(set(horizons)):
        boundary = b0 + bn @ np.linalg.matrix_power(matrix, horizon)
        for perturbation_index, perturbation in enumerate(perturbations):
            try:
                initial_delta = np.linalg.solve(boundary, perturbation)
            except np.linalg.LinAlgError as exc:
                raise ValueError(
                    f"Boundary system is singular for horizon {horizon}"
                ) from exc
            relative_residual = float(
                np.linalg.norm(boundary @ initial_delta - perturbation)
                / max(float(np.linalg.norm(perturbation)), _NUMERICAL_FLOOR)
            )
            if relative_residual > 1e-8:
                raise ValueError(
                    f"Boundary recovery residual is too large for horizon {horizon}"
                )
            for early_step in sorted(set(early_steps)):
                if early_step >= horizon:
                    raise ValueError("Each --early-step must be smaller than every --horizon")
                state_delta = np.linalg.matrix_power(matrix, early_step) @ initial_delta
                control_delta = readout @ state_delta
                rows.append(
                    {
                        "intervention_kind": "terminal_objective",
                        "horizon": horizon,
                        "early_step": early_step,
                        "perturbation_norm": float(np.linalg.norm(perturbation)),
                        "control_delta_norm": float(np.linalg.norm(control_delta)),
                        "seed": perturbation_index,
                        "surrogate_recovery_residual": relative_residual,
                    }
                )
    return rows


def _validate_square_matrix(np: Any, value: Any, name: str) -> None:
    if value.ndim != 2 or value.shape[0] != value.shape[1] or value.shape[0] < 1:
        raise ValueError(f"{name} must be a non-empty square matrix")
    if not np.isfinite(value).all():
        raise ValueError(f"{name} must contain only finite values")


def _normalize_records(records: list[JsonDict]) -> tuple[list[JsonDict], int]:
    normalized: list[JsonDict] = []
    floor_count = 0
    for index, raw in enumerate(records, start=1):
        horizon = _integer(raw, "horizon", index=index, minimum=1)
        early_step = _integer(raw, "early_step", index=index, minimum=0)
        if early_step >= horizon:
            raise ValueError(f"Record {index}: early_step must be smaller than horizon")
        perturbation = _finite_number(raw, "perturbation_norm", index=index)
        delta = _finite_number(raw, "control_delta_norm", index=index)
        if perturbation <= 0.0:
            raise ValueError(f"Record {index}: perturbation_norm must be positive")
        if delta < 0.0:
            raise ValueError(f"Record {index}: control_delta_norm must be non-negative")
        sensitivity = delta / max(perturbation, _NUMERICAL_FLOOR)
        clipped = sensitivity <= _NUMERICAL_FLOOR
        if clipped:
            floor_count += 1
        record: JsonDict = {
            "intervention_kind": str(raw.get("intervention_kind") or "terminal_objective"),
            "horizon": horizon,
            "early_step": early_step,
            "distance_to_terminal": horizon - early_step,
            "perturbation_norm": perturbation,
            "control_delta_norm": delta,
            "sensitivity": sensitivity,
            "log_sensitivity": math.log(max(sensitivity, _NUMERICAL_FLOOR)),
            "floor_clipped": clipped,
        }
        for key in ("seed", "checkpoint", "model", "surrogate_recovery_residual"):
            if key in raw:
                record[key] = raw[key]
        normalized.append(record)
    return normalized, floor_count


def _integer(payload: JsonDict, key: str, *, index: int, minimum: int) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"Record {index}: {key} must be an integer >= {minimum}")
    return value


def _finite_number(payload: JsonDict, key: str, *, index: int) -> float:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"Record {index}: {key} must be a finite number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"Record {index}: {key} must be a finite number")
    return converted


def _fit_log_sensitivity(np: Any, records: list[JsonDict]) -> JsonDict:
    x_values = np.asarray([float(row["distance_to_terminal"]) for row in records])
    y_values = np.asarray([float(row["log_sensitivity"]) for row in records])
    design = np.column_stack([np.ones_like(x_values), x_values])
    coefficients, _, _, _ = np.linalg.lstsq(design, y_values, rcond=None)
    intercept = float(coefficients[0])
    slope = float(coefficients[1])
    predicted = design @ coefficients
    residual_sum = float(np.sum((y_values - predicted) ** 2))
    total_sum = float(np.sum((y_values - np.mean(y_values)) ** 2))
    r_squared = 1.0 if total_sum <= 1e-24 and residual_sum <= 1e-24 else (
        0.0 if total_sum <= 1e-24 else 1.0 - residual_sum / total_sum
    )
    return {
        "intercept": intercept,
        "slope": slope,
        "decay_rate": -slope,
        "r_squared": float(r_squared),
    }


def _bootstrap_group_decay_ci(
    np: Any,
    records: list[JsonDict],
    *,
    samples: int,
) -> list[float] | None:
    if samples < 1:
        raise ValueError("bootstrap_samples must be positive")
    rng = np.random.default_rng(0)
    estimates: list[float] = []
    grouped = _grouped_records(records)
    for _ in range(samples):
        group_estimates: list[float] = []
        for group_rows in grouped.values():
            sample = _resample_group_clusters(np, rng, group_rows)
            if len({int(row["horizon"]) for row in sample}) < 2:
                break
            fit = _fit_log_sensitivity(np, _aggregate_distance_records(sample))
            group_estimates.append(float(fit["decay_rate"]))
        if len(group_estimates) == len(grouped):
            estimates.append(float(np.mean(np.asarray(group_estimates))))
    if not estimates:
        return None
    lower, upper = np.percentile(np.asarray(estimates), [2.5, 97.5])
    return [float(lower), float(upper)]


def _group_fits(np: Any, records: list[JsonDict]) -> list[JsonDict]:
    grouped = _grouped_records(records)
    result: list[JsonDict] = []
    for (kind, early_step, checkpoint, model), rows in sorted(grouped.items()):
        aggregated = _aggregate_distance_records(rows)
        fit = _fit_log_sensitivity(np, aggregated) if len(aggregated) >= 2 else {}
        result.append(
            {
                "group_id": "|".join(
                    [kind, f"t={early_step}", checkpoint or "-", model or "-"]
                ),
                "intervention_kind": kind,
                "early_step": early_step,
                "checkpoint": checkpoint or None,
                "model": model or None,
                "record_count": len(rows),
                "seed_count": len({str(row.get("seed")) for row in rows if "seed" in row}),
                "distinct_horizons": sorted({int(row["horizon"]) for row in rows}),
                **fit,
            }
        )
    return result


def _grouped_records(
    records: list[JsonDict],
) -> dict[tuple[str, int, str, str], list[JsonDict]]:
    grouped: dict[tuple[str, int, str, str], list[JsonDict]] = {}
    for row in records:
        key = (
            str(row["intervention_kind"]),
            int(row["early_step"]),
            str(row.get("checkpoint") or ""),
            str(row.get("model") or ""),
        )
        grouped.setdefault(key, []).append(row)
    return grouped


def _validate_seed_metadata(records: list[JsonDict]) -> None:
    for rows in _grouped_records(records).values():
        seeded = ["seed" in row for row in rows]
        if any(seeded) and not all(seeded):
            raise ValueError(
                "Each terminal-sensitivity fit group must use consistent seed metadata"
            )


def _aggregate_distance_records(records: list[JsonDict]) -> list[JsonDict]:
    grouped: dict[int, list[float]] = {}
    for row in records:
        distance = int(row["distance_to_terminal"])
        grouped.setdefault(distance, []).append(float(row["log_sensitivity"]))
    return [
        {
            "distance_to_terminal": distance,
            "log_sensitivity": sum(values) / len(values),
        }
        for distance, values in sorted(grouped.items())
    ]


def _aggregate_group_fits(np: Any, groups: list[JsonDict]) -> JsonDict:
    decays = np.asarray([float(group["decay_rate"]) for group in groups])
    slopes = np.asarray([float(group["slope"]) for group in groups])
    intercepts = np.asarray([float(group["intercept"]) for group in groups])
    return {
        "intercept": float(np.mean(intercepts)),
        "slope": float(np.mean(slopes)),
        "decay_rate": float(np.mean(decays)),
        "r_squared": min(float(group["r_squared"]) for group in groups),
    }


def _resample_group_clusters(np: Any, rng: Any, rows: list[JsonDict]) -> list[JsonDict]:
    seed_groups: dict[str, list[JsonDict]] = {}
    for row in rows:
        if "seed" in row:
            seed_groups.setdefault(str(row["seed"]), []).append(row)
    if len(seed_groups) >= 2:
        clusters = list(seed_groups.values())
    else:
        horizon_groups: dict[int, list[JsonDict]] = {}
        for row in rows:
            horizon_groups.setdefault(int(row["horizon"]), []).append(row)
        clusters = list(horizon_groups.values())
    indices = rng.integers(0, len(clusters), size=len(clusters))
    return [row for index in indices for row in clusters[int(index)]]


def _write_outputs(out_dir: Path, payload: JsonDict) -> None:
    write_json(out_dir / "terminal_sensitivity.json", payload)
    records = payload.get("records")
    rows = records if isinstance(records, list) else []
    (out_dir / "terminal_sensitivity.csv").write_text(
        _render_csv([row for row in rows if isinstance(row, dict)]),
        encoding="utf-8",
    )
    (out_dir / "terminal_sensitivity.svg").write_text(
        _render_svg([row for row in rows if isinstance(row, dict)], payload),
        encoding="utf-8",
    )


def _render_csv(rows: list[JsonDict]) -> str:
    fields = [
        "intervention_kind",
        "horizon",
        "early_step",
        "distance_to_terminal",
        "perturbation_norm",
        "control_delta_norm",
        "sensitivity",
        "log_sensitivity",
        "floor_clipped",
        "seed",
        "checkpoint",
        "model",
    ]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def _render_svg(rows: list[JsonDict], payload: JsonDict) -> str:
    width, height = 960, 540
    left, right, top, bottom = 90, 40, 70, 80
    if rows:
        xs = [float(row["distance_to_terminal"]) for row in rows]
        ys = [float(row["log_sensitivity"]) for row in rows]
    else:
        xs, ys = [0.0, 1.0], [0.0, 1.0]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    if xmax <= xmin:
        xmax = xmin + 1.0
    if ymax <= ymin:
        ymax = ymin + 1.0

    def sx(value: float) -> float:
        return left + (value - xmin) / (xmax - xmin) * (width - left - right)

    def sy(value: float) -> float:
        return height - bottom - (value - ymin) / (ymax - ymin) * (height - top - bottom)

    points = "".join(
        f'<circle cx="{sx(float(row["distance_to_terminal"])):.2f}" '
        f'cy="{sy(float(row["log_sensitivity"])):.2f}" r="5" fill="#2563eb"/>'
        for row in rows
    )
    fit_line = ""
    slope = payload.get("slope")
    intercept = payload.get("intercept")
    if isinstance(slope, int | float) and isinstance(intercept, int | float):
        y0 = float(intercept) + float(slope) * xmin
        y1 = float(intercept) + float(slope) * xmax
        fit_line = (
            f'<line x1="{sx(xmin):.2f}" y1="{sy(y0):.2f}" x2="{sx(xmax):.2f}" '
            f'y2="{sy(y1):.2f}" stroke="#dc2626" stroke-width="4"/>'
        )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
viewBox="0 0 {width} {height}" role="img" aria-label="Terminal sensitivity decay">
<rect width="100%" height="100%" fill="#f8fafc"/><text x="48" y="38" font-family="Arial"
font-size="24" font-weight="700" fill="#0f172a">Terminal sensitivity vs. boundary distance</text>
<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}"
stroke="#64748b"/><line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}"
stroke="#64748b"/>{fit_line}{points}<text x="{width/2}" y="{height-24}" text-anchor="middle"
font-family="Arial" font-size="18">N - t</text><text x="24" y="{height/2}"
transform="rotate(-90 24 {height/2})" text-anchor="middle" font-family="Arial"
font-size="18">log sensitivity</text></svg>"""
