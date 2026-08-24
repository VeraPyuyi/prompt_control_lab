"""Riccati surrogate diagnostics."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from promptcontrollab.files import JsonDict, ensure_dir, write_json
from promptcontrollab.optional import require_module


def analyze_riccati(
    *,
    out_dir: Path,
    matrices_path: Path | None = None,
    trajectory_path: Path | None = None,
    iterations: int = 200,
) -> JsonDict:
    """Run a finite-dimensional surrogate Riccati diagnostic."""

    np = require_module("numpy", feature="Riccati diagnostics", extra="research")
    if matrices_path is not None:
        a_matrix, b_matrix, q_matrix, r_matrix = _load_matrices(np, matrices_path)
        source = str(matrices_path)
    elif trajectory_path is not None:
        a_matrix = _fit_linear_surrogate(np, trajectory_path)
        dim = int(a_matrix.shape[0])
        b_matrix = np.eye(dim)
        q_matrix = np.eye(dim)
        r_matrix = np.eye(dim)
        source = str(trajectory_path)
    else:
        msg = "Provide either --matrices or --trajectory"
        raise ValueError(msg)

    solution = _solve_dare(np, a_matrix, b_matrix, q_matrix, r_matrix, iterations=iterations)
    gain = np.linalg.solve(
        r_matrix + b_matrix.T @ solution @ b_matrix,
        b_matrix.T @ solution @ a_matrix,
    )
    closed_loop = a_matrix - b_matrix @ gain
    radius = float(max(abs(np.linalg.eigvals(closed_loop))))
    payload: JsonDict = {
        "kind": "riccati",
        "source": source,
        "dimension": int(a_matrix.shape[0]),
        "closed_loop_spectral_radius": radius,
        "theory_decay_rate": float(-np.log(max(radius, 1e-12))),
        "stable_surrogate": radius < 1.0,
        "interpretation": (
            "This is a diagnostic on a fitted finite-dimensional surrogate. It checks whether "
            "that surrogate is internally stable; it is not a proof about the full language model."
        ),
    }
    ensure_dir(out_dir)
    write_json(out_dir / "riccati.json", payload)
    return payload


def _load_matrices(np: Any, path: Path) -> tuple[Any, Any, Any, Any]:
    data = cast(Any, np.load(path, allow_pickle=False))
    required = ["A", "B", "Q", "R"]
    missing = [name for name in required if name not in data]
    if missing:
        msg = f"{path} is missing arrays: {', '.join(missing)}"
        raise ValueError(msg)
    return (data["A"], data["B"], data["Q"], data["R"])


def _fit_linear_surrogate(np: Any, path: Path) -> Any:
    data = cast(Any, np.load(path, allow_pickle=False))
    if "states" not in data:
        msg = f"{path} must contain an array named `states`"
        raise ValueError(msg)
    states = data["states"]
    if len(states.shape) != 2 or states.shape[0] < 3:
        msg = "`states` must be shaped [steps, hidden_dim] with at least three steps"
        raise ValueError(msg)
    x_matrix = states[:-1].T
    y_matrix = states[1:].T
    return y_matrix @ np.linalg.pinv(x_matrix)


def _solve_dare(
    np: Any,
    a_matrix: Any,
    b_matrix: Any,
    q_matrix: Any,
    r_matrix: Any,
    *,
    iterations: int,
) -> Any:
    solution = q_matrix.copy()
    for _ in range(iterations):
        middle = r_matrix + b_matrix.T @ solution @ b_matrix
        gain_term = (
            a_matrix.T
            @ solution
            @ b_matrix
            @ np.linalg.solve(middle, b_matrix.T @ solution @ a_matrix)
        )
        next_solution = a_matrix.T @ solution @ a_matrix - gain_term + q_matrix
        if float(np.linalg.norm(next_solution - solution)) < 1e-10:
            return next_solution
        solution = next_solution
    return solution
