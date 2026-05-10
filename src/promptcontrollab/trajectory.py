"""Hidden-state trajectory diagnostics."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from promptcontrollab.files import JsonDict, ensure_dir, write_json
from promptcontrollab.optional import require_module


def analyze_trajectory(*, states_path: Path, out_dir: Path, tail: int = 3) -> JsonDict:
    """Analyze drift and log-decay slope from a hidden-state trajectory artifact."""

    np = require_module("numpy", feature="trajectory diagnostics", extra="research")
    data = cast(Any, np.load(states_path, allow_pickle=True))
    if "states" not in data:
        msg = f"{states_path} must contain an array named `states`"
        raise ValueError(msg)
    states = cast(Any, data["states"])
    if len(states.shape) != 2:
        msg = "`states` must be a rank-2 array shaped [steps, hidden_dim]"
        raise ValueError(msg)
    if states.shape[0] < 3:
        msg = "Trajectory diagnostics need at least three steps"
        raise ValueError(msg)
    tail_count = min(max(tail, 1), int(states.shape[0]))
    x_inf = np.mean(states[-tail_count:], axis=0)
    distances = cast(Any, np.linalg.norm(states - x_inf, axis=1))
    drift = cast(Any, np.linalg.norm(states[1:] - states[:-1], axis=1))
    slope, r2 = _fit_log_decay(np, distances)
    payload: JsonDict = {
        "kind": "trajectory",
        "states_path": str(states_path),
        "steps": int(states.shape[0]),
        "hidden_dim": int(states.shape[1]),
        "mean_step_drift": float(np.mean(drift)),
        "max_step_drift": float(np.max(drift)),
        "log_decay_slope": slope,
        "decay_r2": r2,
        "turnpike_like_signal": slope < 0 and r2 >= 0.5,
        "interpretation": (
            "A negative log-decay slope with reasonable fit quality suggests a trajectory that "
            "moves toward a stable region. Weak fit or high drift suggests heterogeneous or "
            "unstable behavior."
        ),
    }
    ensure_dir(out_dir)
    write_json(out_dir / "trajectory.json", payload)
    return payload


def _fit_log_decay(np: Any, distances: Any) -> tuple[float, float]:
    eps = 1e-12
    y = np.log(np.maximum(distances, eps))
    x = np.arange(len(y), dtype=float)
    x_mean = float(np.mean(x))
    y_mean = float(np.mean(y))
    denom = float(np.sum((x - x_mean) ** 2))
    if denom == 0.0:
        return (0.0, 0.0)
    slope = float(np.sum((x - x_mean) * (y - y_mean)) / denom)
    intercept = y_mean - slope * x_mean
    pred = slope * x + intercept
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y_mean) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return (slope, r2)

