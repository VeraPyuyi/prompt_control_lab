"""Versioned provider/model/phase price snapshots for experiment budgets."""

from __future__ import annotations

import math
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
    """Estimate cost from reported usage; this is never a provider billing receipt."""
    snapshot = resolve_price_snapshot(budget, provider=provider, model=model, phase=phase)
    if snapshot is None:
        return None
    inputs, outputs = usage.get("input_tokens"), usage.get("output_tokens")
    if (
        not isinstance(inputs, int)
        or not isinstance(outputs, int)
        or isinstance(inputs, bool)
        or isinstance(outputs, bool)
        or inputs < 0
        or outputs < 0
    ):
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


def finite_cost(value: object) -> float | None:
    """Accept only finite nonnegative amounts, preserving an explicitly reported zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) and number >= 0 else None


def cost_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Keep cost kinds separate and aggregate only within an explicit currency."""
    fields = ("reserved_cost", "estimated_cost", "reported_cost", "actual_cost", "charged_cost")
    currencies: dict[str, dict[str, Any]] = {}
    known_count = 0
    bases: set[str] = set()
    for row in rows:
        currency = row.get("cost_currency")
        values = {field: finite_cost(row.get(field)) for field in fields}
        if not isinstance(currency, str) or not currency.strip():
            currency = "unknown"
        for field, value in values.items():
            unit = row.get(f"{field}_currency") or currency
            section = currencies.setdefault(unit, {key: [] for key in (*fields, "known_cost")})
            if value is not None:
                section[field].append(value)
        effective_field = next(
            (
                key
                for key in ("actual_cost", "reported_cost", "estimated_cost")
                if values[key] is not None
            ),
            None,
        )
        effective = values[effective_field] if effective_field else None
        unit = row.get(f"{effective_field}_currency") or currency
        if effective is not None and unit != "unknown":
            currencies[unit]["known_cost"].append(effective)
            known_count += 1
            bases.add(
                "reported"
                if values["reported_cost"] is not None or values["actual_cost"] is not None
                else "estimated"
            )
    totals = {
        currency: {
            field: finite_cost(sum(values)) if values else None for field, values in section.items()
        }
        for currency, section in currencies.items()
    }
    currency = next(iter(totals)) if len(totals) == 1 and "unknown" not in totals else None
    aggregate = totals[currency] if currency else dict.fromkeys((*fields, "known_cost"))
    return {
        **aggregate,
        "cost_currency": currency,
        "cost_by_currency": totals,
        "cost_basis": next(iter(bases)) if len(bases) == 1 else "mixed" if bases else "unknown",
        "cost_known_count": known_count,
        "cost_unknown_count": len(rows) - known_count,
        "cost_status": "known"
        if rows and known_count == len(rows) and aggregate["known_cost"] is not None
        else "unknown",
    }
