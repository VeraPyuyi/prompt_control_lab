"""Versioned provider/model/phase price snapshots for experiment budgets."""

from __future__ import annotations

from typing import Any


def _rates(snapshot: dict[str, Any]) -> tuple[float, float]:
    return float(snapshot["input_cost_per_million"]), float(snapshot["output_cost_per_million"])


def resolve_price_snapshot(
    budget: dict[str, Any], *, provider: str, model: str, phase: str
) -> dict[str, Any] | None:
    """Return the provider/model/phase snapshot or a legacy global fallback."""
    snapshots = budget.get("price_snapshots")
    if isinstance(snapshots, list):
        for snapshot in snapshots:
            if (
                isinstance(snapshot, dict)
                and snapshot.get("provider") == provider
                and snapshot.get("model") == model
                and snapshot.get("phase") == phase
            ):
                return snapshot
    if all(
        budget.get(key) is not None for key in ("input_cost_per_million", "output_cost_per_million")
    ):
        return {
            "provider": provider,
            "model": model,
            "phase": phase,
            "currency": budget.get("currency", "legacy"),
            "effective_date": budget.get("effective_date", "legacy"),
            "input_cost_per_million": budget["input_cost_per_million"],
            "output_cost_per_million": budget["output_cost_per_million"],
            "source": "legacy_global_rates",
        }
    return None


def estimate_cost(
    budget: dict[str, Any],
    usage: dict[str, Any],
    *,
    provider: str,
    model: str,
    phase: str,
) -> float | None:
    """Estimate reported cost from known usage and a resolved price snapshot."""
    snapshot = resolve_price_snapshot(budget, provider=provider, model=model, phase=phase)
    if snapshot is None:
        return None
    inputs, outputs = usage.get("input_tokens"), usage.get("output_tokens")
    if not isinstance(inputs, int) or not isinstance(outputs, int):
        return None
    input_rate, output_rate = _rates(snapshot)
    return (inputs * input_rate + outputs * output_rate) / 1_000_000


def reserve_cost(
    budget: dict[str, Any],
    *,
    provider: str,
    model: str,
    phase: str,
    input_tokens: int,
    output_tokens: int,
) -> float | None:
    """Reserve budget cost from an upper-bound token reservation."""
    snapshot = resolve_price_snapshot(budget, provider=provider, model=model, phase=phase)
    if snapshot is None:
        return None
    input_rate, output_rate = _rates(snapshot)
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000
