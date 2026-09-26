"""Measured batch policy accounting with explicit unknown costs and atomic completion."""

from __future__ import annotations

from fractions import Fraction

from .common import JsonDict, number, text
from .v2_common import (
    binary_vector,
    boolean,
    header,
    identifiers,
    integer,
    mapping,
    records,
    saved_summary,
)

COST_COMPONENTS = ("load", "probe", "score", "sort", "transfer", "serialization", "failed")


def _seconds(value: object, name: str) -> Fraction | None:
    if value is None:
        return None
    number(value, name, nonnegative=True)
    return Fraction(str(value))


def _policy(policy: JsonDict, item_ids: list[str], labels: list[int]) -> JsonDict:
    """Validate recorded policy operations, costs and batch completion evidence."""
    strategy = text(policy.get("strategy"), "strategy")
    size = integer(policy.get("actual_batch_size"), "actual_batch_size", minimum=1)
    costs = mapping(policy.get("costs"), "costs")
    if set(costs) - set(COST_COMPONENTS):
        raise ValueError("Costs accept load/probe/score/sort/transfer/serialization/failed only")
    components = {name: _seconds(costs.get(name), f"costs.{name}") for name in COST_COMPONENTS}
    timing_scope = policy.get("timing_scope")
    if timing_scope not in ("measured_full_policy", "primitive_operations"):
        raise ValueError(
            "timing_scope must distinguish measured_full_policy from primitive_operations"
        )
    if timing_scope == "measured_full_policy":
        text(policy.get("run_id"), "measured full policy run_id")
    seen_ids: set[str] = set()
    seen_batches: set[str] = set()
    label_lookup = dict(zip(item_ids, labels, strict=True))
    batches = []
    for batch in records(policy.get("batches"), "batches", empty=True):
        batch_id = text(batch.get("batch_id"), "batch_id")
        if batch_id in seen_batches:
            raise ValueError("batch_id must be unique per policy")
        seen_batches.add(batch_id)
        ids = identifiers(batch.get("item_ids"), "batch.item_ids")
        if len(ids) > size:
            raise ValueError("Recorded batch exceeds actual_batch_size")
        if set(ids) - set(item_ids):
            raise ValueError("Every batch identity must belong to the fixed case panel")
        completed = boolean(batch.get("completed"), "batch.completed")
        if completed and seen_ids & set(ids):
            raise ValueError("Completed batches must not count the same item twice")
        if completed:
            seen_ids.update(ids)
        duration = _seconds(batch.get("elapsed_seconds"), "batch.elapsed_seconds")
        batches.append(
            {
                "batch_id": batch_id,
                "item_ids": ids,
                "completed": completed,
                "duration": duration,
                "changes": sum(label_lookup[item] for item in ids),
            }
        )
    return {
        "strategy": strategy,
        "actual_batch_size": size,
        "components": components,
        "batches": batches,
        "timing_scope": timing_scope,
        "run_id": policy.get("run_id"),
    }


def _cutoff(policy: JsonDict, budget: Fraction) -> JsonDict:
    """Account for observed policy work under a specified budget cutoff."""
    components = policy["components"]
    missing = [key for key, value in components.items() if value is None]
    unknown_batches = [
        batch["batch_id"] for batch in policy["batches"] if batch["duration"] is None
    ]
    upfront = sum(components.values(), Fraction(0)) if not missing else None
    result: JsonDict = {
        "strategy": policy["strategy"],
        "actual_batch_size": policy["actual_batch_size"],
        "budget_seconds": float(budget),
        "timing_scope": policy["timing_scope"],
        "run_id": policy["run_id"],
        "cost_components_seconds": {
            key: float(value) if value is not None else None for key, value in components.items()
        },
        "unknown_cost_components": missing,
        "unknown_batch_timings": unknown_batches,
        "upfront_seconds": float(upfront) if upfront is not None else None,
        "K": None,
        "Y": None,
        "delta_Y": None,
        "completed_batch_ids": [],
        "excluded_batches": [],
        "observed_spend_within_cutoff_seconds": None,
        "observed_elapsed_through_cutoff_batch_seconds": None,
        "measured_overrun_seconds": None,
        "gain_status": "unknown_costs" if missing or unknown_batches else "not_compared",
    }
    if missing or unknown_batches:
        return result
    assert upfront is not None
    spent = upfront
    completed_count, changes = 0, 0
    crossed = spent > budget
    for batch in policy["batches"]:
        if crossed or (spent == budget and batch["duration"] > 0):
            result["excluded_batches"].append(
                {"batch_id": batch["batch_id"], "reason": "budget_cutoff"}
            )
            crossed = True
            continue
        finish = spent + batch["duration"]
        spent = finish
        if finish > budget:
            # A started batch consumes time up to the cutoff even when it receives
            # no discovery credit. Retain the measured tail as a separate overrun.
            result["excluded_batches"].append(
                {"batch_id": batch["batch_id"], "reason": "budget_cutoff"}
            )
            crossed = True
            continue
        if batch["completed"]:
            result["completed_batch_ids"].append(batch["batch_id"])
            completed_count += len(batch["item_ids"])
            changes += batch["changes"]
        else:
            result["excluded_batches"].append(
                {"batch_id": batch["batch_id"], "reason": "incomplete_batch"}
            )
    result.update(
        K=completed_count,
        Y=changes,
        observed_spend_within_cutoff_seconds=float(min(spent, budget)),
        observed_elapsed_through_cutoff_batch_seconds=float(spent),
        measured_overrun_seconds=float(max(spent - budget, Fraction(0))),
        upfront_exceeds_budget=upfront > budget,
        gain_status="not_compared",
    )
    return result


def _compare(policies: list[JsonDict]) -> None:
    direct = next(row for row in policies if row["strategy"] == "direct")
    for policy in policies:
        if policy["Y"] is None or direct["Y"] is None:
            policy["gain_status"] = "unknown_costs"
        elif (
            policy["timing_scope"] != "measured_full_policy"
            or direct["timing_scope"] != "measured_full_policy"
        ):
            policy["gain_status"] = "not_measured_full_policy"
        else:
            policy["delta_Y"] = policy["Y"] - direct["Y"]
            policy["gain_status"] = "measured_full_policy"


def analyze_document(document: JsonDict) -> JsonDict:
    """Compare measurement policies while retaining incomplete and unknown cost components."""
    result = header(document, "measurement-value")
    summary = saved_summary(document, result)
    if summary is not None:
        return summary
    cases, seen = [], set()
    for case in records(document.get("cases"), "cases"):
        cid = text(case.get("case_id"), "case_id")
        if cid in seen:
            raise ValueError("case_id must be unique")
        seen.add(cid)
        model, pair = text(case.get("model"), "model"), text(case.get("pair_id"), "pair_id")
        ids = identifiers(case.get("item_ids"), "item_ids")
        labels = binary_vector(case.get("labels"), "labels", len(ids))
        budget = _seconds(case.get("budget_seconds"), "budget_seconds")
        if budget is None:
            raise ValueError("The actual budget cutoff must be supplied")
        checked = [
            _policy(policy, ids, labels) for policy in records(case.get("policies"), "policies")
        ]
        strategies = [policy["strategy"] for policy in checked]
        if len(set(strategies)) != len(strategies) or "direct" not in strategies:
            raise ValueError("Unique policy strategies including direct are required")
        policies = [_cutoff(policy, budget) for policy in checked]
        _compare(policies)
        grid = case.get("budget_grid_seconds", [float(budget)])
        if not isinstance(grid, list) or not grid:
            raise ValueError("budget_grid_seconds must be a nonempty numeric list")
        curves = []
        for value in grid:
            boundary = _seconds(value, "budget_grid_seconds")
            if boundary is None:
                raise ValueError("Budget curve cutoffs cannot be unknown")
            rows = [_cutoff(policy, boundary) for policy in checked]
            _compare(rows)
            curves.append({"budget_seconds": float(boundary), "policies": rows})
        cases.append(
            {
                "case_id": cid,
                "model": model,
                "pair_id": pair,
                "item_count": len(ids),
                "budget_seconds": float(budget),
                "policies": policies,
                "budget_curves": curves,
            }
        )
    primitives = []
    for row in records(document.get("primitive_timings", []), "primitive_timings", empty=True):
        scope = text(row.get("operation"), "operation")
        elapsed = _seconds(row.get("elapsed_seconds"), "elapsed_seconds")
        primitives.append(
            {
                "operation": scope,
                "elapsed_seconds": float(elapsed) if elapsed is not None else None,
                "model": text(row.get("model"), "primitive timing model"),
                "scope": "primitive_operation_only",
                "policy_gain": None,
            }
        )
    result.update(
        cases=cases,
        primitive_timings=primitives,
        scale_extrapolation="not_supported",
        cost_accounting={
            "components": list(COST_COMPONENTS),
            "missing_costs": "unknown; never assumed zero",
            "batch_elapsed_seconds": (
                "Measured serial elapsed generation time; includes batch failures."
            ),
            "failed_component": (
                "Failed work outside recorded generation batches only; avoid double counting."
            ),
            "cutoff": (
                "Only complete observed batches finishing at or before budget receive credit."
            ),
            "cutoff_elapsed_scope": (
                "Elapsed time includes the started crossing batch; within-cutoff consumption "
                "is capped at budget and the observed tail is reported as overrun. "
                "Later batches do not start in this cutoff replay."
            ),
            "policy_scope": (
                "Measured supplied run, batch size, and model only; "
                "no small-to-large extrapolation."
            ),
        },
    )
    return result
