"""Per-model price snapshots must not backfill unknown costs."""

from pathlib import Path
from typing import Any

from promptcontrollab.evaluation.experiments import create_experiment, run_experiment
from promptcontrollab.evaluation.experiments.storage import job_directory


def _provider(**kwargs: Any) -> dict[str, Any]:
    model = kwargs["model"]
    return {
        "output_text": "yes",
        "model_id": model,
        "usage": {"input_tokens": 1000, "output_tokens": 100},
    }


def test_mixed_model_costs_use_phase_snapshots(tmp_path: Path) -> None:
    spec = {
        "operation": "run",
        "data": [{"id": "a", "input": "task", "expected": "yes"}],
        "baseline": {"provider": "openai", "model": "base", "prompt": "baseline"},
        "candidate": {"provider": "openai", "model": "cand", "prompt": "candidate"},
        "budget": {
            "max_calls": 10,
            "max_output_tokens": 10000,
            "max_seconds": 30,
            "price_snapshots": [
                {
                    "provider": "openai",
                    "model": "base",
                    "phase": "evaluation",
                    "currency": "USD",
                    "effective_date": "2026-01-01",
                    "input_cost_per_million": 1,
                    "output_cost_per_million": 2,
                },
                {
                    "provider": "openai",
                    "model": "cand",
                    "phase": "evaluation",
                    "currency": "USD",
                    "effective_date": "2026-01-01",
                    "input_cost_per_million": 3,
                    "output_cost_per_million": 4,
                },
            ],
        },
    }
    job = run_experiment(tmp_path, create_experiment(tmp_path, spec)["id"], _provider)
    records = sorted((job_directory(tmp_path, job["id"]) / "records").glob("*.json"))
    costs = sorted(
        float(__import__("json").loads(path.read_text())["estimated_cost"]) for path in records
    )
    assert costs == [0.0012, 0.0034]
    budget = job["budget"]
    assert budget["reported_cost"] is None
    assert budget["actual_cost"] is None
    assert all(
        __import__("json").loads(path.read_text())["actual_cost"] is None for path in records
    )
    assert budget["estimated_cost"] == 0.0046
    assert budget["cost_currency"] == "USD"
    assert budget["reserved_cost"] >= budget["estimated_cost"]
