"""Pure cost accounting and label-free decisions for a bounded research case.

The fixed score queues and externally frozen forecasts are inputs. This module
does not train, estimate forecasts from behavior labels, or certify control theory.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from fractions import Fraction
from typing import Any

from .common import evidence

SCORES = ("loss", "primary", "norm")
STRATEGIES = ("direct", *SCORES)
EVIDENCE_STATUSES = ("historical_observation", "locked_prediction", "independent_confirmation")


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")
    return value


def _number(value: Any, name: str, *, nonnegative: bool = True) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite numeric value")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite or (nonnegative and value < 0):
        raise ValueError(f"{name} must be finite and {'nonnegative' if nonnegative else 'numeric'}")
    # Interpret JSON decimal values exactly; 0.1 + 0.2 fits a 0.3-second budget.
    return Fraction(str(value))


def _finite_output(value: Fraction, name: str) -> float:
    try:
        number = float(value)
    except OverflowError as error:
        raise ValueError(f"{name} aggregate cannot be represented as a finite number") from error
    if not math.isfinite(number):
        raise ValueError(f"{name} aggregate cannot be represented as a finite number")
    return number


def _vector(value: Any, size: int, name: str, *, nonnegative: bool = True) -> list[Fraction]:
    if not isinstance(value, list) or len(value) != size:
        raise ValueError(f"{name} must be an aligned array of length {size}")
    return [
        _number(item, f"{name}[{index}]", nonnegative=nonnegative)
        for index, item in enumerate(value)
    ]


def _ids(case: Mapping[str, Any]) -> list[str]:
    values = case.get("item_ids")
    if not isinstance(values, list) or not values:
        raise ValueError("item_ids must be a nonempty array")
    result = [_text(item, "item_ids entry") for item in values]
    if len(set(result)) != len(result):
        raise ValueError("item_ids must be unique within each model/pair")
    return result


def fixed_order(case: Mapping[str, Any], strategy: str) -> list[str]:
    """Return a label-free, cost-free queue for one predeclared fixed strategy."""
    ids = _ids(case)
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown fixed strategy: {strategy}")
    values = [Fraction(0)] * len(ids)
    if strategy != "direct":
        scores = _mapping(case.get("scores"), "scores")
        values = _vector(scores.get(strategy), len(ids), f"scores.{strategy}", nonnegative=False)
    indices = sorted(
        range(len(ids)),
        key=lambda index: (
            -values[index],
            hashlib.sha256(ids[index].encode("utf-8")).hexdigest(),
            ids[index],
        ),
    )
    return [ids[index] for index in indices]


def _validated_case(case: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a measurement case and normalize its exact cost accounting."""
    model, pair = _text(case.get("model"), "model"), _text(case.get("pair"), "pair")
    ids = _ids(case)
    orders = {strategy: fixed_order(case, strategy) for strategy in STRATEGIES}
    behavior = _mapping(case.get("behavior"), "behavior")
    labels = {}
    for name in ("risk_source", "risk_target"):
        values = _vector(behavior.get(name), len(ids), f"behavior.{name}")
        if any(value not in (0, 1) for value in values):
            raise ValueError(f"behavior.{name} must contain binary 0/1 labels")
        labels[name] = dict(zip(ids, map(int, values), strict=True))
    costs = _mapping(case.get("costs"), "costs")
    allowed_costs = {
        "generation_pair_seconds",
        "budget_seconds",
        "direct_sort_seconds",
        "scan_seconds",
        "sort_seconds",
        "probe_seconds",
        "selection_seconds",
        "transmission_seconds",
        "transmission_pair_seconds",
    }
    if set(costs) - allowed_costs:
        raise ValueError(f"unknown costs: {sorted(set(costs) - allowed_costs)}")
    budget = _number(costs.get("budget_seconds"), "budget_seconds")
    generation = _vector(costs.get("generation_pair_seconds"), len(ids), "generation_pair_seconds")
    transmission = _vector(
        costs.get("transmission_pair_seconds", [0] * len(ids)),
        len(ids),
        "transmission_pair_seconds",
    )
    generation = [a + b for a, b in zip(generation, transmission, strict=True)]
    overhead = {"direct": _number(costs.get("direct_sort_seconds"), "direct_sort_seconds")}
    for name in ("scan_seconds", "sort_seconds"):
        score_costs = _mapping(costs.get(name), name)
        if set(score_costs) != set(SCORES):
            raise ValueError(f"{name} must contain exactly loss, primary, norm")
        for strategy in SCORES:
            overhead[strategy] = overhead.get(strategy, Fraction(0)) + _number(
                score_costs[strategy],
                f"{name}.{strategy}",
            )
    paid_fields = ("probe_seconds" in costs, "selection_seconds" in costs)
    if paid_fields[0] != paid_fields[1]:
        raise ValueError("probe_seconds and selection_seconds must be supplied together")
    paid = None
    if all(paid_fields):
        paid = _number(costs["probe_seconds"], "probe_seconds") + _number(
            costs["selection_seconds"], "selection_seconds"
        )
    if "transmission_seconds" in costs:
        transmission_cost = _number(costs["transmission_seconds"], "transmission_seconds")
        overhead = {name: value + transmission_cost for name, value in overhead.items()}
    return {
        "model": model,
        "pair": pair,
        "orders": orders,
        "labels": labels,
        "budget": budget,
        "generation": dict(zip(ids, generation, strict=True)),
        "overhead": overhead,
        "paid": paid,
    }


def _prefix(case: Mapping[str, Any], strategy: str, *, paid: bool) -> dict[str, Any]:
    upfront = case["overhead"][strategy] + (case["paid"] if paid else 0)
    budget, audit = case["budget"], Fraction(0)
    completed: list[str] = []
    if upfront <= budget:
        for item_id in case["orders"][strategy]:
            cost = case["generation"][item_id]
            if upfront + audit + cost > budget:
                break
            audit += cost
            completed.append(item_id)
    source, target = case["labels"]["risk_source"], case["labels"]["risk_target"]
    increases = sum(target[item] > source[item] for item in completed)
    decreases = sum(target[item] < source[item] for item in completed)
    count, discoveries = len(completed), increases + decreases
    return {
        "model": case["model"],
        "pair": case["pair"],
        "strategy": f"paid_{strategy}" if paid else strategy,
        "K": count,
        "Y": discoveries,
        "p": discoveries / count if count else None,
        "risk_increases": increases,
        "risk_decreases": decreases,
        "budget_seconds": float(budget),
        "upfront_seconds": _finite_output(upfront, "upfront_seconds"),
        "audit_seconds": _finite_output(audit, "audit_seconds"),
        "required_seconds": _finite_output(upfront + audit, "required_seconds"),
        "unspent_seconds": _finite_output(
            max(Fraction(0), budget - upfront - audit),
            "unspent_seconds",
        ),
        "overhead_exceeds_budget": upfront > budget,
        "completed_item_ids": completed,
    }


def _compare(row: dict[str, Any], direct: Mapping[str, Any]) -> None:
    count, discoveries = row["K"], row["Y"]
    base_count, base_discoveries = direct["K"], direct["Y"]
    delta = discoveries - base_discoveries
    row.update(
        {
            "K_0": base_count,
            "Y_0": base_discoveries,
            "p_0": direct["p"],
            "delta_Y": delta,
            "precision_threshold": float(Fraction(base_discoveries, count)) if count else None,
            "precision_threshold_gt_one": base_discoveries > count if count else None,
        }
    )
    gain, capacity = None, None
    status = "undefined_baseline_precision"
    if base_count:
        base_precision = Fraction(base_discoveries, base_count)
        # This count form also defines the zero-audit extension without inventing p_s.
        gain = Fraction(discoveries) - count * base_precision
        capacity = (base_count - count) * base_precision
        if gain - capacity != delta:
            raise ArithmeticError("cost decomposition identity failed")
        status = "defined" if count else "count_extension"
    row["decomposition"] = {
        "status": status,
        "precision_gain": str(gain) if gain is not None else None,
        "capacity_loss": str(capacity) if capacity is not None else None,
        "difference": delta,
    }


def analyze_document(document: Mapping[str, Any]) -> dict[str, Any]:
    """Replay full paired prefixes under B, preserving the declared evidence status."""
    if document.get("schema_version") != "measurement-value/v1":
        raise ValueError("schema_version must be measurement-value/v1")
    status = document.get("evidence_status")
    if status not in EVIDENCE_STATUSES:
        raise ValueError(f"evidence_status must explicitly be one of {EVIDENCE_STATUSES}")
    if not isinstance(document.get("synthetic"), bool):
        raise ValueError("synthetic must be explicitly true or false")
    if status == "independent_confirmation" or "evidence_receipts" in document:
        evidence(dict(document))
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("cases must be a nonempty array")
    validated = [_validated_case(_mapping(case, "case")) for case in cases]
    coordinates = [(case["model"], case["pair"]) for case in validated]
    if len(set(coordinates)) != len(coordinates):
        raise ValueError("model/pair coordinates must be unique")
    rows, summaries = [], []
    for case in sorted(validated, key=lambda case: (case["model"], case["pair"])):
        direct = _prefix(case, "direct", paid=False)
        for paid in [False] if case["paid"] is None else [False, True]:
            for strategy in STRATEGIES:
                row = _prefix(case, strategy, paid=paid)
                _compare(row, direct)
                rows.append(row)
        summaries.append(
            {
                "model": case["model"],
                "pair": case["pair"],
                "orders": case["orders"],
                "paid_cost_status": "not_supplied" if case["paid"] is None else "supplied",
            }
        )
    return {
        "schema_version": "measurement-value-result/v1",
        "evidence_status": status,
        "synthetic": document["synthetic"],
        "provenance": document.get("provenance", {}),
        "discovery_rule": "abs(risk_target-risk_source) for binary risk labels",
        "future_case_guarantee": False,
        "cases": summaries,
        "rows": rows,
    }


def _valid_control_diagnostics(diagnostics: Any, context: Mapping[str, Any]) -> bool:
    if not isinstance(diagnostics, Mapping) or set(diagnostics) != {
        "status",
        "validity_scope",
        "features",
    }:
        return False
    if diagnostics["status"] != "valid" or diagnostics["validity_scope"] != dict(context):
        return False
    features = diagnostics["features"]
    if not isinstance(features, Mapping) or not features:
        return False
    try:
        for name, value in features.items():
            _text(name, "control feature name")
            _number(value, f"control_diagnostics.features.{name}", nonnegative=False)
    except ValueError:
        return False
    return True


def _frozen_uniform_action(forecast: Any, context: Mapping[str, Any]) -> str | None:
    if not isinstance(forecast, Mapping) or forecast.get("frozen") is not True:
        return None
    if forecast.get("validity_scope") != dict(context):
        return None
    action = forecast.get("uniform_action")
    if action not in STRATEGIES:
        return None
    try:
        _text(forecast.get("freeze_id"), "forecast.freeze_id")
    except ValueError:
        return None
    return str(action)


def locked_decision(request: Mapping[str, Any]) -> dict[str, Any]:
    """Choose from externally frozen full-cost forecasts without inspecting labels."""
    if request.get("schema_version") != "measurement-value-decision/v1":
        raise ValueError("schema_version must be measurement-value-decision/v1")
    phase = request.get("phase")
    if phase not in ("before_probe", "after_probe"):
        raise ValueError("phase must be before_probe or after_probe")
    allowed = {"schema_version", "phase", "evidence_status", "context", "forecast", "behavior"}
    if phase == "after_probe":
        allowed.update({"control_diagnostics", "incurred_costs"})
    extra = set(request) - allowed
    if extra:
        raise ValueError(f"{phase} rejects control or unknown fields: {sorted(extra)}")
    status = request.get("evidence_status")
    if status not in EVIDENCE_STATUSES:
        raise ValueError("evidence_status must be explicitly declared")
    context = _mapping(request.get("context"), "context")
    if set(context) != {"model", "pair", "decode_cap", "budget_seconds"}:
        raise ValueError("context requires exactly model, pair, decode_cap, budget_seconds")
    _text(context["model"], "context.model")
    _text(context["pair"], "context.pair")
    budget = _number(context["budget_seconds"], "context.budget_seconds")
    cap = context["decode_cap"]
    if isinstance(cap, bool) or not isinstance(cap, int) or cap <= 0:
        raise ValueError("context.decode_cap must be a positive integer")
    result: dict[str, Any] = {
        "schema_version": "measurement-value-decision-result/v1",
        "phase": phase,
        "evidence_status": status,
        "selected_strategy": "paid_direct" if phase == "after_probe" else "direct",
        "decision": "insufficient_evidence",
        "reason": "unusable_frozen_forecast",
        "future_case_guarantee": False,
    }
    if phase == "after_probe":
        ledger = _mapping(request.get("incurred_costs"), "incurred_costs")
        if not {"probe_seconds", "selection_seconds"} <= set(ledger) or set(ledger) - {
            "probe_seconds",
            "selection_seconds",
            "transmission_seconds",
        }:
            raise ValueError(
                "incurred_costs requires probe_seconds and selection_seconds; "
                "optional transmission_seconds"
            )
        costs = {name: _number(value, f"incurred_costs.{name}") for name, value in ledger.items()}
        result["incurred_costs"] = {name: float(value) for name, value in costs.items()}
        incurred = sum(costs.values(), Fraction(0))
        remaining = budget - incurred
        result.update(
            {
                "incurred_seconds": _finite_output(incurred, "incurred_seconds"),
                "budget_seconds": float(budget),
                "remaining_budget_seconds": _finite_output(remaining, "remaining_budget_seconds"),
                "budget_status": (
                    "available" if remaining > 0 else "exhausted" if remaining == 0 else "exceeded"
                ),
                "further_evaluation_allowed": remaining > 0,
            }
        )
        if remaining <= 0:
            result["reason"] = (
                "incurred_cost_exhausts_budget"
                if remaining == 0
                else "incurred_cost_exceeds_budget"
            )
            return result
    forecast = request.get("forecast")
    if phase == "after_probe":
        requires_controls = (
            forecast.get("requires_control_diagnostics", True)
            if isinstance(forecast, Mapping)
            else True
        )
        if not isinstance(requires_controls, bool):
            return {**result, "reason": "invalid_control_dependency_declaration"}
        check_controls = requires_controls or "control_diagnostics" in request
        if check_controls and not _valid_control_diagnostics(
            request.get("control_diagnostics"),
            context,
        ):
            result.update(
                {
                    "control_diagnostics_status": "invalid",
                    "reason": "unusable_control_diagnostics",
                }
            )
            uniform = _frozen_uniform_action(forecast, context)
            if uniform is not None and status == "locked_prediction":
                result.update(
                    {
                        "selected_strategy": f"paid_{uniform}",
                        "decision": "fallback_uniform",
                        "uniform_action": uniform,
                    }
                )
            return result
        result["control_diagnostics_status"] = "valid" if check_controls else "not_required"
    if not isinstance(forecast, Mapping) or status != "locked_prediction":
        return result
    forecast_fields = {
        "freeze_id",
        "frozen",
        "basis",
        "validity_scope",
        "uniform_action",
        "baseline_discoveries",
        "paid_discoveries",
        "status",
        "requires_control_diagnostics",
    }
    if set(forecast) - forecast_fields:
        raise ValueError(f"{phase} rejects unknown forecast fields")
    if forecast.get("frozen") is not True or forecast.get("status", "valid") != "valid":
        return result
    if forecast.get("validity_scope") != dict(context):
        return {**result, "reason": "unsupported_validity_scope"}
    if forecast.get("basis") != "full_cost_net_discoveries":
        return {**result, "reason": "forecast_does_not_include_full_cost"}
    if forecast.get("uniform_action") not in STRATEGIES:
        return {**result, "reason": "uniform_action_not_frozen"}
    try:
        freeze_id = _text(forecast.get("freeze_id"), "forecast.freeze_id")
        baselines = _mapping(forecast.get("baseline_discoveries"), "baseline_discoveries")
        paid = _mapping(forecast.get("paid_discoveries"), "paid_discoveries")
        if set(baselines) != {"direct", "loss", "uniform"} or set(paid) != set(STRATEGIES):
            return result
        baseline_values = {name: _number(value, name) for name, value in baselines.items()}
        paid_values = {name: _number(value, name) for name, value in paid.items()}
    except ValueError:
        return result
    best_baseline = max(baseline_values.values())
    threshold = best_baseline * Fraction(105, 100) if best_baseline else Fraction(1)
    best_paid = max(paid_values.values())
    winners = [name for name, value in paid_values.items() if value == best_paid]
    result.update(
        {
            "decision": "prefer_direct",
            "freeze_id": freeze_id,
            "uniform_action": forecast["uniform_action"],
            "best_baseline_discoveries": float(best_baseline),
            "required_paid_discoveries": float(threshold),
            "best_paid_discoveries": float(best_paid),
        }
    )
    if len(winners) != 1:
        result["reason"] = "paid_forecast_tie"
    elif best_paid < threshold:
        result["reason"] = "paid_forecast_below_required_gain"
    else:
        result.update(
            {
                "selected_strategy": f"paid_{winners[0]}",
                "decision": "use_paid_strategy",
                "reason": "unique_paid_forecast_meets_required_gain",
            }
        )
    return result
