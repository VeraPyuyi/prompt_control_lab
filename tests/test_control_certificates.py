from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from promptcontrollab.cli import main
from promptcontrollab.files import read_json
from promptcontrollab.green_certificate import analyze_green_certificate
from promptcontrollab.posterior_certificate import analyze_posterior_certificate
from promptcontrollab.terminal_sensitivity import analyze_terminal_sensitivity


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def _terminal_rows(*, decay_rate: float) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for seed in (0, 1):
        for horizon in (8, 16, 32, 64):
            sensitivity = math.exp(-decay_rate * horizon) * (1.0 + seed * 0.01)
            rows.append(
                {
                    "intervention_kind": "terminal_objective",
                    "horizon": horizon,
                    "early_step": 0,
                    "perturbation_norm": 2.0,
                    "control_delta_norm": 2.0 * sensitivity,
                    "seed": seed,
                }
            )
    return rows


def test_terminal_sensitivity_recovers_known_exponential_decay(tmp_path: Path) -> None:
    records = tmp_path / "terminal_interventions.jsonl"
    _write_jsonl(records, _terminal_rows(decay_rate=0.08))

    payload = analyze_terminal_sensitivity(records_path=records, out_dir=tmp_path / "out")

    assert payload["schema"] == "prompt_control_lab.terminal_sensitivity.v1"
    assert payload["certificate_level"] == "empirical_only"
    assert payload["check_state"] == "passed"
    assert payload["decay_rate"] == pytest.approx(0.08, abs=0.002)
    assert payload["r_squared"] > 0.99
    assert len(payload["bootstrap_ci"]) == 2
    assert (tmp_path / "out/terminal_sensitivity.csv").is_file()
    assert (tmp_path / "out/terminal_sensitivity.svg").is_file()


@pytest.mark.parametrize(
    ("decay_rate", "expected_state"),
    [(0.0, "conditions_not_met"), (-0.03, "conditions_not_met")],
)
def test_terminal_sensitivity_classifies_flat_and_growing_records(
    tmp_path: Path,
    decay_rate: float,
    expected_state: str,
) -> None:
    records = tmp_path / "records.jsonl"
    _write_jsonl(records, _terminal_rows(decay_rate=decay_rate))

    payload = analyze_terminal_sensitivity(records_path=records, out_dir=tmp_path / "out")

    assert payload["certificate_level"] == "empirical_only"
    assert payload["check_state"] == expected_state


def test_terminal_sensitivity_needs_three_distinct_horizons(tmp_path: Path) -> None:
    records = tmp_path / "records.jsonl"
    _write_jsonl(records, _terminal_rows(decay_rate=0.1)[:2])

    payload = analyze_terminal_sensitivity(records_path=records, out_dir=tmp_path / "out")

    assert payload["certificate_level"] == "insufficient_evidence"
    assert payload["check_state"] == "missing"


def test_terminal_sensitivity_records_zero_response_at_numerical_floor(
    tmp_path: Path,
) -> None:
    records = tmp_path / "records.jsonl"
    rows = _terminal_rows(decay_rate=0.1)
    for row in rows:
        row["control_delta_norm"] = 0.0
    _write_jsonl(records, rows)

    payload = analyze_terminal_sensitivity(records_path=records, out_dir=tmp_path / "out")

    assert payload["check_state"] == "conditions_not_met"
    assert payload["floor_clipped_count"] == len(rows)
    assert payload["decay_rate"] == pytest.approx(0.0, abs=1e-12)


def test_terminal_sensitivity_does_not_turn_group_offsets_into_decay(
    tmp_path: Path,
) -> None:
    records = tmp_path / "records.jsonl"
    rows: list[dict[str, object]] = []
    for horizon in (8, 12, 16):
        rows.append(
            {
                "intervention_kind": "reward_model_a",
                "horizon": horizon,
                "early_step": 0,
                "perturbation_norm": 1.0,
                "control_delta_norm": 1.0,
                "seed": 0,
            }
        )
    for horizon in (32, 48, 64):
        rows.append(
            {
                "intervention_kind": "reward_model_b",
                "horizon": horizon,
                "early_step": 0,
                "perturbation_norm": 1.0,
                "control_delta_norm": 0.01,
                "seed": 0,
            }
        )
    _write_jsonl(records, rows)

    payload = analyze_terminal_sensitivity(records_path=records, out_dir=tmp_path / "out")

    assert payload["check_state"] == "conditions_not_met"
    assert payload["decay_rate"] == pytest.approx(0.0, abs=1e-12)
    assert len(payload["groups"]) == 2
    assert all(group["decay_rate"] == pytest.approx(0.0, abs=1e-12) for group in payload["groups"])


def test_terminal_sensitivity_requires_positive_cluster_bootstrap_interval(
    tmp_path: Path,
) -> None:
    records = tmp_path / "records.jsonl"
    rows: list[dict[str, object]] = []
    for seed, decay_rate in ((0, 0.2), (1, -0.1)):
        for horizon in (8, 16, 32, 64):
            sensitivity = math.exp(-decay_rate * horizon)
            rows.append(
                {
                    "intervention_kind": "terminal_objective",
                    "horizon": horizon,
                    "early_step": 0,
                    "perturbation_norm": 1.0,
                    "control_delta_norm": sensitivity,
                    "seed": seed,
                }
            )
    _write_jsonl(records, rows)

    payload = analyze_terminal_sensitivity(records_path=records, out_dir=tmp_path / "out")

    assert payload["decay_rate"] == pytest.approx(0.05, abs=1e-10)
    assert payload["bootstrap_ci"][0] < 0.0
    assert payload["check_state"] == "conditions_not_met"
    assert "positive_bootstrap_decay_interval" in payload["conditions_not_met"]


def test_terminal_sensitivity_rejects_partial_seed_metadata(tmp_path: Path) -> None:
    records = tmp_path / "records.jsonl"
    rows = _terminal_rows(decay_rate=0.08)
    rows[0].pop("seed")
    _write_jsonl(records, rows)

    with pytest.raises(ValueError, match="seed metadata"):
        analyze_terminal_sensitivity(records_path=records, out_dir=tmp_path / "out")


def test_terminal_sensitivity_rejects_invalid_records(tmp_path: Path) -> None:
    records = tmp_path / "records.jsonl"
    _write_jsonl(
        records,
        [
            {
                "intervention_kind": "terminal_objective",
                "horizon": 8,
                "early_step": 8,
                "perturbation_norm": 0.0,
                "control_delta_norm": float("nan"),
            }
        ],
    )

    with pytest.raises(ValueError, match=r"early_step|perturbation_norm|finite"):
        analyze_terminal_sensitivity(records_path=records, out_dir=tmp_path / "out")


def test_terminal_surrogate_uses_the_standard_record_schema(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    surrogate = tmp_path / "terminal_surrogate.npz"
    np.savez(
        surrogate,
        M=np.diag([0.7, 1.4]),
        B0=np.eye(2),
        BN=np.zeros((2, 2)),
        terminal_perturbations=np.array([[1.0, 0.0], [0.0, 1.0]]),
        control_readout=np.eye(2),
    )

    payload = analyze_terminal_sensitivity(
        surrogate_path=surrogate,
        horizons=[8, 16, 32],
        early_steps=[0, 1],
        out_dir=tmp_path / "out",
    )

    assert payload["source_kind"] == "linear_bvp_surrogate"
    assert payload["record_count"] == 12
    assert all(
        {"horizon", "early_step", "perturbation_norm", "control_delta_norm"}
        <= set(row)
        for row in payload["records"]
    )


def _write_green_surrogate(path: Path, *, matrix: object, b0: object, bn: object) -> None:
    np = pytest.importorskip("numpy")
    np.savez(path, M=np.asarray(matrix, dtype=float), B0=b0, BN=bn)


def test_green_certificate_accepts_hyperbolic_well_conditioned_surrogate(
    tmp_path: Path,
) -> None:
    np = pytest.importorskip("numpy")
    surrogate = tmp_path / "green.npz"
    _write_green_surrogate(
        surrogate,
        matrix=np.diag([0.5, 2.0]),
        b0=np.array([[1.0, 0.0], [0.0, 0.0]]),
        bn=np.array([[0.0, 0.0], [0.0, 1.0]]),
    )

    payload = analyze_green_certificate(
        surrogate_path=surrogate,
        horizons=[8, 16, 32],
        out_dir=tmp_path / "out",
    )

    assert payload["certificate_level"] == "surrogate_consistent"
    assert payload["check_state"] == "passed"
    assert payload["stable_dimension"] == 1
    assert payload["unstable_dimension"] == 1
    assert payload["hyperbolicity_margin"] == pytest.approx(0.5)
    assert min(row["boundary_sigma_min"] for row in payload["horizons"]) > 0.9
    assert payload["terminal_only_decay_claim"] is False


@pytest.mark.parametrize(
    ("matrix", "expected_reason"),
    [
        ([[1.0, 0.0], [0.0, 2.0]], "unit_circle_spectrum"),
        ([[0.5, 0.0], [0.0, 0.7]], "stable_unstable_dimension"),
    ],
)
def test_green_certificate_reports_conditions_not_met(
    tmp_path: Path,
    matrix: list[list[float]],
    expected_reason: str,
) -> None:
    np = pytest.importorskip("numpy")
    surrogate = tmp_path / "green.npz"
    _write_green_surrogate(
        surrogate,
        matrix=matrix,
        b0=np.eye(2),
        bn=np.eye(2),
    )

    payload = analyze_green_certificate(
        surrogate_path=surrogate,
        horizons=[8, 16, 32],
        out_dir=tmp_path / "out",
    )

    assert payload["check_state"] == "conditions_not_met"
    assert expected_reason in payload["conditions_not_met"]
    assert "does not prove" in payload["claim_boundary"].lower()


def test_green_certificate_rejects_near_singular_scaled_boundary(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    surrogate = tmp_path / "green.npz"
    _write_green_surrogate(
        surrogate,
        matrix=np.diag([0.5, 2.0]),
        b0=np.array([[1e-12, 0.0], [0.0, 0.0]]),
        bn=np.array([[0.0, 0.0], [0.0, 1.0]]),
    )

    payload = analyze_green_certificate(
        surrogate_path=surrogate,
        horizons=[8, 16, 32],
        out_dir=tmp_path / "out",
    )

    assert payload["check_state"] == "conditions_not_met"
    assert "boundary_transversality" in payload["conditions_not_met"]
    assert payload["boundary_sigma_min"] < 1e-8


def test_green_certificate_checks_declared_uniform_margin(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    surrogate = tmp_path / "green.npz"
    _write_green_surrogate(
        surrogate,
        matrix=np.diag([0.5, 2.0]),
        b0=np.array([[1.0, 0.0], [0.0, 0.0]]),
        bn=np.array([[0.0, 0.0], [0.0, 1.0]]),
    )
    premises = tmp_path / "premises.json"
    _write_json(premises, {"uniform_unit_circle_margin_lower": 0.6})

    payload = analyze_green_certificate(
        surrogate_path=surrogate,
        horizons=[8, 16, 32],
        premises_path=premises,
        out_dir=tmp_path / "out",
    )

    assert payload["check_state"] == "conditions_not_met"
    assert "declared_hyperbolicity_margin" in payload["conditions_not_met"]


def test_green_certificate_handles_nonnormal_hyperbolic_surrogate(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    surrogate = tmp_path / "green.npz"
    _write_green_surrogate(
        surrogate,
        matrix=np.array([[0.5, 0.25], [0.0, 2.0]]),
        b0=np.eye(2),
        bn=np.eye(2),
    )

    payload = analyze_green_certificate(
        surrogate_path=surrogate,
        horizons=[8, 16, 32],
        out_dir=tmp_path / "out",
    )

    assert payload["stable_dimension"] == 1
    assert payload["unstable_dimension"] == 1
    assert math.isfinite(payload["hyperbolicity_margin"])
    assert payload["stable_invariance_residual"] < 1e-10
    assert payload["unstable_invariance_residual"] < 1e-10
    assert all(math.isfinite(row["boundary_sigma_min"]) for row in payload["horizons"])


def test_green_certificate_supports_generalized_recurrence_and_graph_boundary(
    tmp_path: Path,
) -> None:
    np = pytest.importorskip("numpy")
    surrogate = tmp_path / "green.npz"
    np.savez(
        surrogate,
        L=np.eye(2),
        N=np.diag([0.5, 2.0]),
        B0=np.array([[1.0, 0.0], [0.0, 0.0]]),
        BN=np.array([[0.0, 0.0], [0.0, 1.0]]),
        graph_S=np.array([[0.0]]),
    )

    payload = analyze_green_certificate(
        surrogate_path=surrogate,
        horizons=[8, 16, 32],
        out_dir=tmp_path / "out",
    )

    assert payload["recurrence_kind"] == "generalized_LN"
    assert payload["graph_boundary"]["provided"] is True
    assert "check_state" in payload["graph_boundary"]


def test_green_certificate_only_verifies_complete_conservative_premises(
    tmp_path: Path,
) -> None:
    np = pytest.importorskip("numpy")
    surrogate = tmp_path / "green.npz"
    _write_green_surrogate(
        surrogate,
        matrix=np.diag([0.5, 2.0]),
        b0=np.array([[1.0, 0.0], [0.0, 0.0]]),
        bn=np.array([[0.0, 0.0], [0.0, 1.0]]),
    )
    premises = tmp_path / "premises.json"
    _write_json(
        premises,
        {
            "schema": "prompt_control_lab.green_premises.v1",
            "source_kind": "certified_bounds",
            "scope": "fixed two-dimensional surrogate family",
            "fixed_dimension": True,
            "existing_local_branch": True,
            "interior_control": True,
            "uniform_c3_neighborhood": True,
            "uniform_control_hessian_inverse_bound": 2.0,
            "uniform_unit_circle_margin_lower": 0.4,
            "uniform_boundary_sigma_min_lower": 0.9,
            "horizon_family": {"minimum": 8, "uniform": True},
            "provenance": {
                "kind": "controlled_bound_record",
                "conservative": True,
                "source": "unit-test fixture",
            },
        },
    )

    payload = analyze_green_certificate(
        surrogate_path=surrogate,
        horizons=[8, 16, 32],
        premises_path=premises,
        out_dir=tmp_path / "out",
    )

    assert payload["certificate_level"] == "certificate_verified"
    assert payload["verified_scope"] == "fixed two-dimensional surrogate family"


def test_green_certificate_requires_positive_horizon_family_minimum(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    surrogate = tmp_path / "green.npz"
    _write_green_surrogate(
        surrogate,
        matrix=np.diag([0.5, 2.0]),
        b0=np.array([[1.0, 0.0], [0.0, 0.0]]),
        bn=np.array([[0.0, 0.0], [0.0, 1.0]]),
    )
    premises = tmp_path / "premises.json"
    source = {
        "schema": "prompt_control_lab.green_premises.v1",
        "source_kind": "certified_bounds",
        "scope": "fixed two-dimensional surrogate family",
        "fixed_dimension": True,
        "existing_local_branch": True,
        "interior_control": True,
        "uniform_c3_neighborhood": True,
        "uniform_control_hessian_inverse_bound": 2.0,
        "uniform_unit_circle_margin_lower": 0.4,
        "uniform_boundary_sigma_min_lower": 0.9,
        "horizon_family": {"minimum": 0, "uniform": True},
        "provenance": {
            "kind": "controlled_bound_record",
            "conservative": True,
            "source": "unit-test fixture",
        },
    }
    _write_json(premises, source)

    payload = analyze_green_certificate(
        surrogate_path=surrogate,
        horizons=[8, 16, 32],
        premises_path=premises,
        out_dir=tmp_path / "out",
    )

    assert payload["certificate_level"] == "surrogate_consistent"
    assert "horizon_family.minimum" in payload["premise_gaps"]


def _posterior_input(
    *,
    epsilon: float = 0.1,
    beta: float = 1.0,
    lipschitz: float = 1.0,
    radius: float = 1.0,
    certified: bool = False,
) -> dict[str, object]:
    return {
        "schema": "prompt_control_lab.posterior_bounds.v1",
        "residual_norm_upper": epsilon,
        "jacobian_inverse_norm_upper": beta,
        "jacobian_lipschitz_upper": lipschitz,
        "neighborhood_radius": radius,
        "bound_provenance": {
            "kind": "certified_bounds" if certified else "estimated_bounds",
            "conservative": certified,
            "scope": "fixed local surrogate neighborhood",
            "source": "unit-test fixture",
        },
    }


def test_posterior_certificate_passes_bounded_local_check(tmp_path: Path) -> None:
    input_path = tmp_path / "posterior.json"
    _write_json(input_path, _posterior_input())

    payload = analyze_posterior_certificate(input_path=input_path, out_dir=tmp_path / "out")

    assert payload["certificate_level"] == "surrogate_consistent"
    assert payload["check_state"] == "passed"
    assert payload["h"] == pytest.approx(0.1)
    assert payload["existence_radius"] < 1.0
    assert (tmp_path / "out/posterior_certificate.json").is_file()


@pytest.mark.parametrize(
    ("epsilon", "radius", "expected_condition"),
    [(0.6, 1.0, "kantorovich_h"), (0.1, 0.01, "neighborhood_radius")],
)
def test_posterior_certificate_records_unmet_conditions_without_nonexistence_claim(
    tmp_path: Path,
    epsilon: float,
    radius: float,
    expected_condition: str,
) -> None:
    input_path = tmp_path / "posterior.json"
    _write_json(input_path, _posterior_input(epsilon=epsilon, radius=radius))

    payload = analyze_posterior_certificate(input_path=input_path, out_dir=tmp_path / "out")

    assert payload["check_state"] == "conditions_not_met"
    assert expected_condition in payload["conditions_not_met"]
    assert "does not prove" in payload["claim_boundary"].lower()


def test_posterior_certificate_handles_linear_case_and_verified_bounds(tmp_path: Path) -> None:
    input_path = tmp_path / "posterior.json"
    _write_json(
        input_path,
        _posterior_input(epsilon=0.2, beta=2.0, lipschitz=0.0, radius=0.5, certified=True),
    )

    payload = analyze_posterior_certificate(input_path=input_path, out_dir=tmp_path / "out")

    assert payload["certificate_level"] == "certificate_verified"
    assert payload["check_state"] == "passed"
    assert payload["existence_radius"] == pytest.approx(0.4)


def test_posterior_certificate_accepts_exact_kantorovich_boundary(tmp_path: Path) -> None:
    input_path = tmp_path / "posterior.json"
    _write_json(
        input_path,
        _posterior_input(epsilon=0.5, beta=1.0, lipschitz=1.0, radius=1.0),
    )

    payload = analyze_posterior_certificate(input_path=input_path, out_dir=tmp_path / "out")

    assert payload["h"] == pytest.approx(0.5)
    assert payload["existence_radius"] == pytest.approx(1.0)
    assert payload["check_state"] == "passed"
    assert payload["certificate_level"] == "surrogate_consistent"


def test_posterior_certificate_uses_stable_radius_for_tiny_h(tmp_path: Path) -> None:
    input_path = tmp_path / "posterior.json"
    _write_json(
        input_path,
        _posterior_input(
            epsilon=1e-20,
            beta=1.0,
            lipschitz=1.0,
            radius=1e-25,
            certified=True,
        ),
    )

    payload = analyze_posterior_certificate(input_path=input_path, out_dir=tmp_path / "out")

    assert payload["existence_radius"] == pytest.approx(1e-20, rel=1e-12, abs=0.0)
    assert payload["check_state"] == "conditions_not_met"
    assert payload["certificate_level"] != "certificate_verified"


@pytest.mark.parametrize(
    ("field", "value"),
    [("jacobian_inverse_norm_upper", 0.0), ("neighborhood_radius", 0.0)],
)
def test_posterior_certificate_requires_positive_inverse_and_radius(
    tmp_path: Path,
    field: str,
    value: float,
) -> None:
    input_path = tmp_path / "posterior.json"
    source = _posterior_input()
    source[field] = value
    _write_json(input_path, source)

    with pytest.raises(ValueError, match=field):
        analyze_posterior_certificate(input_path=input_path, out_dir=tmp_path / "out")


def test_posterior_certificate_rejects_nonfinite_derived_bounds(tmp_path: Path) -> None:
    input_path = tmp_path / "posterior.json"
    _write_json(
        input_path,
        _posterior_input(epsilon=1e308, beta=1e308, lipschitz=1.0),
    )

    with pytest.raises(ValueError, match="derived"):
        analyze_posterior_certificate(input_path=input_path, out_dir=tmp_path / "out")


def test_posterior_certificate_without_provenance_is_insufficient(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "posterior.json"
    source = _posterior_input()
    source.pop("bound_provenance")
    _write_json(input_path, source)

    payload = analyze_posterior_certificate(input_path=input_path, out_dir=tmp_path / "out")

    assert payload["check_state"] == "passed"
    assert payload["certificate_level"] == "insufficient_evidence"
    assert payload["provenance_complete"] is False


@pytest.mark.parametrize("field", ["residual_norm_upper", "jacobian_inverse_norm_upper"])
def test_posterior_certificate_rejects_negative_or_nonfinite_bounds(
    tmp_path: Path,
    field: str,
) -> None:
    payload = _posterior_input()
    payload[field] = -1.0 if field == "residual_norm_upper" else float("nan")
    input_path = tmp_path / "posterior.json"
    _write_json(input_path, payload)

    with pytest.raises(ValueError, match=field):
        analyze_posterior_certificate(input_path=input_path, out_dir=tmp_path / "out")


def test_posterior_estimates_never_become_verified(tmp_path: Path) -> None:
    input_path = tmp_path / "posterior.json"
    estimated = _posterior_input(certified=False)
    estimated["certificate_verified"] = True
    _write_json(input_path, estimated)

    payload = analyze_posterior_certificate(input_path=input_path, out_dir=tmp_path / "out")

    assert payload["certificate_level"] == "surrogate_consistent"
    saved = read_json(tmp_path / "out/posterior_certificate.json")
    assert saved["certificate_level"] == "surrogate_consistent"


def test_control_certificate_cli_commands_write_expected_artifacts(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    records = tmp_path / "terminal.jsonl"
    _write_jsonl(records, _terminal_rows(decay_rate=0.08))
    terminal_out = tmp_path / "terminal-out"
    assert main(
        [
            "terminal-sensitivity",
            "--records",
            str(records),
            "--out",
            str(terminal_out),
            "--bootstrap-samples",
            "50",
        ]
    ) == 0
    assert (terminal_out / "terminal_sensitivity.json").is_file()

    green_path = tmp_path / "green.npz"
    _write_green_surrogate(
        green_path,
        matrix=np.diag([0.5, 2.0]),
        b0=np.array([[1.0, 0.0], [0.0, 0.0]]),
        bn=np.array([[0.0, 0.0], [0.0, 1.0]]),
    )
    green_out = tmp_path / "green-out"
    assert main(
        [
            "green-certificate",
            "--surrogate",
            str(green_path),
            "--horizon",
            "8",
            "--horizon",
            "16",
            "--out",
            str(green_out),
        ]
    ) == 0
    assert (green_out / "green_certificate.json").is_file()

    posterior_path = tmp_path / "posterior.json"
    _write_json(posterior_path, _posterior_input())
    posterior_out = tmp_path / "posterior-out"
    assert main(
        [
            "posterior-certificate",
            "--input",
            str(posterior_path),
            "--out",
            str(posterior_out),
        ]
    ) == 0
    assert (posterior_out / "posterior_certificate.json").is_file()


def test_repository_certificate_examples_are_runnable_and_not_overclaimed(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]

    terminal = analyze_terminal_sensitivity(
        records_path=repo_root / "examples/terminal_interventions.jsonl",
        out_dir=tmp_path / "terminal",
    )
    posterior = analyze_posterior_certificate(
        input_path=repo_root / "examples/posterior_bounds.json",
        out_dir=tmp_path / "posterior",
    )
    premises = json.loads(
        (repo_root / "examples/green_premises.json").read_text(encoding="utf-8")
    )

    assert terminal["certificate_level"] == "empirical_only"
    assert terminal["check_state"] == "passed"
    assert posterior["certificate_level"] == "surrogate_consistent"
    assert premises["source_kind"] == "estimated_bounds"
