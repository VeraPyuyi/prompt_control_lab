"""Paired effects and separate evidence-quality conclusions."""

from __future__ import annotations

import math
import unicodedata
from collections import Counter
from typing import Any

from promptcontrollab.evaluation.statistics import paired_compare

from .models import ComparisonAssessment


def _finite_measurement(value: object, *, tokens: bool = False) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if tokens and not isinstance(value, int):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) and number >= 0 else None


def _practical_assessment(
    spec: dict[str, Any],
    baseline: list[dict[str, Any]],
    candidate: list[dict[str, Any]],
    left: dict[str, float],
    right: dict[str, float],
    matched: list[str],
    *,
    scope: str,
    total: int,
    comparability: str,
    coverage: str,
    effect: str,
    dependent: bool,
) -> dict[str, Any]:
    """Summarize resource measurements and choose a next action bounded by current evidence."""
    rates = [
        _finite_measurement(spec["budget"].get(key))
        for key in ("input_cost_per_million", "output_cost_per_million")
    ]
    prices_known = all(rate is not None for rate in rates)

    def arm_summary(rows: list[dict[str, Any]], scores: dict[str, float]) -> dict[str, Any]:
        """Summarize one arm while retaining missing measurement counts and known zero values."""
        usable = {
            row["id"]: row for row in rows if isinstance(row.get("id"), str) and row["id"] in scores
        }
        paired = [usable[item] for item in matched]
        summary: dict[str, Any] = {
            "matched_count": len(matched),
            "score_mean": sum(scores[item] for item in matched) / len(matched) if matched else None,
            "quality_observed_count": len(usable),
            "parse_error_count": sum(
                row.get("output_status") == "parse_error" for row in usable.values()
            ),
            "empty_output_count": sum(
                row.get("output_status") == "empty_output" for row in usable.values()
            ),
            "format_error_count": sum(
                row.get("output_status") in {"empty_output", "format_error"}
                or (spec["metric"] == "format_error" and scores[item] > 0)
                for item, row in usable.items()
            ),
            "unavailable_count": total - len(usable),
        }
        latencies = [_finite_measurement(row.get("latency_ms")) for row in paired]
        finite_latencies = [value for value in latencies if value is not None]
        summary["latency_known_count"] = len(finite_latencies)
        summary["mean_latency_ms"] = (
            sum(value / len(finite_latencies) for value in finite_latencies)
            if finite_latencies
            else None
        )
        usage_values: dict[str, list[float | None]] = {}
        for field in ("input_tokens", "output_tokens"):
            values = []
            for row in paired:
                usage = row.get("usage")
                values.append(
                    _finite_measurement(usage.get(field), tokens=True)
                    if isinstance(usage, dict)
                    else None
                )
            usage_values[field] = values
            known = [value for value in values if value is not None]
            summary[f"{field}_known_count"] = len(known)
            summary[f"known_{field}"] = _finite_measurement(sum(known)) if known else None
            summary[f"mean_{field}"] = sum(value / len(known) for value in known) if known else None
        costs = []
        for index, row in enumerate(paired):
            cost = _finite_measurement(row.get("actual_cost")) if prices_known else None
            inputs = usage_values["input_tokens"][index]
            outputs = usage_values["output_tokens"][index]
            if cost is None and prices_known and inputs is not None and outputs is not None:
                input_rate, output_rate = rates
                assert input_rate is not None and output_rate is not None
                cost = _finite_measurement(
                    (inputs * input_rate + outputs * output_rate) / 1_000_000
                )
            costs.append(cost)
        known_costs = [value for value in costs if value is not None]
        known_cost_total = _finite_measurement(sum(known_costs)) if known_costs else None
        summary.update(
            known_cost=known_cost_total,
            cost_known_count=len(known_costs),
            cost_unknown_count=len(matched) - len(known_costs),
            cost_status="known"
            if matched and len(known_costs) == len(matched) and known_cost_total is not None
            else "unknown",
        )
        return summary

    base, cand = arm_summary(baseline, left), arm_summary(candidate, right)
    delta: dict[str, Any] = {
        "score_mean": cand["score_mean"] - base["score_mean"] if matched else None,
        "mean_latency_ms": None,
        "mean_input_tokens": None,
        "mean_output_tokens": None,
        "cost": None,
    }
    for field, count_field in (
        ("mean_latency_ms", "latency_known_count"),
        ("mean_input_tokens", "input_tokens_known_count"),
        ("mean_output_tokens", "output_tokens_known_count"),
    ):
        if matched and base[count_field] == cand[count_field] == len(matched):
            delta[field] = cand[field] - base[field]
    if base["cost_status"] == cand["cost_status"] == "known":
        delta["cost"] = cand["known_cost"] - base["known_cost"]
    if comparability == "invalid_records":
        action = (
            "repair_records",
            "Repair or re-import invalid records before comparing prompts.",
            "先修复或重新导入无效记录, 再比较提示词。",
        )
    elif coverage != "complete":
        action = (
            "complete_coverage",
            "Resolve missing outputs and service errors, then compare the complete paired set.",
            "先处理缺失输出和服务错误, 再比较完整的配对样本。",
        )
    elif comparability == "confounded":
        action = (
            "align_settings",
            "Repeat with the same model and decoding settings to isolate the prompt change.",
            "使用相同模型和解码设置重新比较, 以判断提示词修改本身的效果。",
        )
    elif spec.get("synthetic"):
        action = (
            "run_real_evaluation",
            "Run this comparison on real task data and provider outputs before choosing a prompt.",
            "选择提示词前, 使用真实任务数据和模型输出完成比较。",
        )
    elif dependent:
        action = (
            "evaluate_independent_groups",
            "Evaluate independent groups or use group-aware inference before selecting a prompt.",
            "选择提示词前, 评估独立分组, 或采用考虑分组依赖的统计方法。",
        )
    elif effect == "regressed":
        action = (
            "retain_baseline",
            "Retain the baseline and revise the candidate using observed failures.",
            "保留基线提示词, 并根据观察到的失败样本修改候选提示词。",
        )
    elif effect == "improved" and scope != "withheld":
        action = (
            "confirm_on_new_data",
            "Confirm the improvement on untouched task data before adopting the candidate.",
            "采用候选提示词前, 先在未参与修改的新任务数据上确认改善。",
        )
    elif effect == "improved" and (
        base["cost_status"] != "known"
        or cand["cost_status"] != "known"
        or delta["mean_latency_ms"] is None
    ):
        action = (
            "measure_operating_cost",
            "Measure missing latency, usage and prices before deciding "
            "whether the observed gain is worth its cost.",
            "补齐延迟、用量和价格记录, 再判断观察到的改善是否值得相应成本。",
        )
    elif effect == "improved":
        action = (
            "review_candidate",
            "Review the held-out gain, latency and cost changes before a controlled adoption.",
            "结合留出集改善、延迟和成本变化进行审核, 再考虑受控采用候选提示词。",
        )
    else:
        action = (
            "retain_baseline_and_gather_evidence",
            "Retain the baseline while gathering more independent paired evidence; "
            "a higher mean alone does not establish improvement.",
            "暂时保留基线并收集更多独立配对证据。平均分较高本身不足以确认改善。",
        )
    evidence = {
        "scope": scope,
        "matched": len(matched),
        "total": total,
        "en": (
            f"Score and resource comparisons use {len(matched)} matched completed pairs "
            f"out of {total} tasks in the {scope} scope. "
            "Resource means use reported finite values only; quality counts "
            "include all valid completed outputs in this scope."
        ),
        "zh": (
            f"分数和资源比较基于 {scope} 范围内 {total} 个任务中的 {len(matched)} 对完整输出。"
            "资源均值仅使用已报告的有限数值, 质量计数涵盖该范围内所有有效的已完成输出。"
        ),
    }
    return {
        "baseline": base,
        "candidate": cand,
        "delta": delta,
        "score_direction": "lower_is_better"
        if spec["metric"] == "format_error"
        else "higher_is_better",
        "cost_basis": "configured_prices_and_reported_usage",
        "evidence_range": evidence,
        "next_action": {"code": action[0], "en": action[1], "zh": action[2]},
    }


def assess(
    spec: dict[str, Any],
    baseline: list[dict[str, Any]],
    candidate: list[dict[str, Any]],
    *,
    expected_ids: list[str],
    scope: str,
    budget: dict[str, Any],
    selected_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assess paired effects, coverage, comparability, costs, and practical next steps."""
    expected = set(expected_ids)
    if len(expected) != len(expected_ids) or expected - {task["id"] for task in spec["data"]}:
        raise ValueError(
            "Assessment scope must contain unique IDs from the immutable task snapshot"
        )
    invalid_records: list[dict[str, str]] = []

    def valid(records: list[dict[str, Any]], arm: str) -> dict[str, float]:
        counts = Counter(row.get("id") for row in records if isinstance(row.get("id"), str))
        result = {}
        for row in records:
            item_id = row.get("id")
            reason = ""
            if not isinstance(item_id, str) or item_id not in expected:
                reason = "outside_evaluation_scope"
            elif counts[item_id] != 1:
                reason = "duplicate_id"
            elif row.get("status") == "invalid_record":
                reason = "record_integrity_error"
            elif row.get("status") == "completed":
                score = row.get("score")
                if (
                    isinstance(score, bool)
                    or not isinstance(score, (int, float))
                    or not 0 <= score <= 1
                    or not math.isfinite(score)
                ):
                    reason = "invalid_score"
                else:
                    result[item_id] = float(score)
            if reason:
                invalid_records.append({"arm": arm, "id": str(item_id), "reason": reason})
        return result

    left, right = valid(baseline, "baseline"), valid(candidate, "candidate")
    matched = sorted(set(left) & set(right))
    stats = (
        paired_compare(
            left, right, seed=spec["seed"], bootstrap_samples=2000, permutation_samples=2000
        ).to_json()
        if matched
        else None
    )
    direction = "lower_is_better" if spec["metric"] == "format_error" else "higher_is_better"
    effect_status = "insufficient_data"
    if stats:
        lo, hi = stats["bootstrap_ci"]
        delta = stats["mean_delta"]
        adjusted = stats["holm_adjusted_p_value"]
        if direction == "lower_is_better":
            lo, hi, delta = -hi, -lo, -delta
        effect_status = (
            "improved"
            if lo > 0 and adjusted < 0.05
            else "regressed"
            if hi < 0 and adjusted < 0.05
            else "uncertain"
            if delta
            else "no_observed_change"
        )
        if direction == "lower_is_better":
            from promptcontrollab.evaluation.statistics import interpret_delta

            stats["interpretation"] = interpret_delta(delta, (lo, hi), adjusted)
    tasks = spec["data"]
    parents = list(range(len(tasks)))

    def find(index: int) -> int:
        while index != parents[index]:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    seen_groups: dict[tuple[str, str], int] = {}
    dependence_fields: set[str] = set()
    for index, task in enumerate(tasks):
        normalized = " ".join(unicodedata.normalize("NFKC", task["input"]).casefold().split())
        tokens = [("normalized_input", normalized)]
        for key in ("group", "group_id", "sample_id", "source_id", "document_id"):
            value = task.get("meta", {}).get(key)
            if value is not None:
                tokens.append(("group" if key in {"group", "group_id"} else key, str(value)))
        for token in tokens:
            if token in seen_groups:
                parents[find(index)] = find(seen_groups[token])
            seen_groups[token] = index
    matched_components = [find(index) for index, task in enumerate(tasks) if task["id"] in matched]
    if len(set(matched_components)) != len(matched_components):
        dependence_fields.add("full_snapshot_connected_components")
    if stats:
        stats["inference_status"] = "iid_assumed"
        if dependence_fields:
            # Keep the raw resampling output only as explicitly invalidated
            # diagnostics; do not report row-wise intervals as group evidence.
            stats["iid_diagnostics"] = {
                key: stats[key]
                for key in ("bootstrap_ci", "permutation_p_value", "holm_adjusted_p_value")
            }
            for key in ("bootstrap_ci", "permutation_p_value", "holm_adjusted_p_value"):
                stats[key] = None
            stats["inference_status"] = "descriptive_only_nonindependent_rows"
            stats["dependence_fields"] = sorted(dependence_fields)
            stats["interpretation"] = "descriptive_delta_without_independent_inference"
            effect_status = "uncertain" if stats["mean_delta"] else "no_observed_change"
    selected = selected_config or spec["candidate"]

    def settings(config: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in config.items()
            if key not in {"prompt", "api_key_env", "timeout"}
        }

    differing = sorted(
        key
        for key in set(settings(spec["baseline"])) | set(settings(selected))
        if settings(spec["baseline"]).get(key) != settings(selected).get(key)
    )
    observed_left = {
        row["observed_model"]
        for row in baseline
        if isinstance(row.get("observed_model"), str) and row["observed_model"]
    }
    observed_right = {
        row["observed_model"]
        for row in candidate
        if isinstance(row.get("observed_model"), str) and row["observed_model"]
    }
    if observed_left and observed_right and observed_left != observed_right:
        differing.append("observed_model")
    paired_rows = [
        {row["id"]: row for row in rows if isinstance(row.get("id"), str) and row["id"] in scores}
        for rows, scores in ((baseline, left), (candidate, right))
    ]
    observed_fields = {
        "model",
        "provider",
        "base_url",
        "temperature",
        "top_p",
        "seed",
        "max_output_tokens",
        "stop",
        "thinking",
    }
    for item in matched:
        conditions = []
        for rows in paired_rows:
            row = rows[item]
            values = row.get("observed_settings")
            known = dict(values) if isinstance(values, dict) else {}
            for key in ("model", "provider"):
                if isinstance(row.get(f"observed_{key}"), str) and row[f"observed_{key}"]:
                    known.setdefault(key, row[f"observed_{key}"])
            conditions.append(known)
        for key in observed_fields:
            if (
                conditions[0].get(key) is not None
                and conditions[1].get(key) is not None
                and conditions[0][key] != conditions[1][key]
            ):
                differing.append(f"observed_{key}")
    differing = sorted(set(differing))
    complete = set(matched) == expected and not invalid_records
    imported = spec["operation"] == "import"
    comparability = {
        "status": "invalid_records"
        if invalid_records
        else "confounded"
        if differing
        else "declared_only"
        if imported
        else "comparable",
        "scope": scope,
        "differing_settings": differing,
        "paired_design": True,
        "metric": spec["metric"],
        "provenance": "user_supplied_predictions" if imported else "local_call_ledger",
        "limitations": (
            ["Imported model and prompt provenance is user-declared"] if imported else []
        )
        + (
            ["Different model or decoding settings prevent isolating prompt effects"]
            if differing
            else []
        ),
    }
    if scope != "withheld":
        comparability["limitations"].append(
            "Evaluation-only comparison; no untouched generalization claim"
        )
    if not complete:
        comparability["limitations"].append(
            "Effect estimates use only successfully matched pairs; missingness may bias them"
        )
    if invalid_records:
        comparability["limitations"].append("Invalid or out-of-scope records were excluded")
        if stats:
            effect_status = "uncertain"
    prices_known = all(
        spec["budget"].get(key) is not None
        for key in ("input_cost_per_million", "output_cost_per_million")
    )
    cost_status = (
        "unknown"
        if imported or not prices_known or budget.get("unknown_cost_calls", 0)
        else "known"
    )
    if dependence_fields:
        comparability["limitations"].append(
            "Matched rows share inputs or sample/group metadata; inferential claims are disabled"
        )
    coverage = {
        "status": "complete" if complete else "partial" if matched else "none",
        "total": len(expected_ids),
        "matched": len(matched),
        "matched_fraction": len(matched) / len(expected_ids) if expected_ids else 0,
        "baseline_completed": len(left),
        "candidate_completed": len(right),
        "missing_baseline_ids": sorted(set(expected_ids) - set(left)),
        "missing_candidate_ids": sorted(set(expected_ids) - set(right)),
        "baseline_statuses": dict(Counter(row["status"] for row in baseline)),
        "candidate_statuses": dict(Counter(row["status"] for row in candidate)),
        "invalid_records": invalid_records,
    }
    by_slice = {}
    slices = {row["id"]: row.get("slice", "default") for row in baseline + candidate}
    for name in sorted(set(slices.values())):
        ids = [item for item in matched if slices.get(item) == name]
        if ids:
            by_slice[name] = {
                "matched": len(ids),
                "baseline_mean": sum(left[item] for item in ids) / len(ids),
                "candidate_mean": sum(right[item] for item in ids) / len(ids),
                "mean_delta": sum(right[item] - left[item] for item in ids) / len(ids),
            }
    practical = _practical_assessment(
        spec,
        baseline,
        candidate,
        left,
        right,
        matched,
        scope=scope,
        total=len(expected_ids),
        comparability=comparability["status"],
        coverage=str(coverage["status"]),
        effect=effect_status,
        dependent=bool(dependence_fields),
    )
    return ComparisonAssessment(
        {
            "schema_version": "comparison-assessment/v1",
            "comparability": comparability,
            "effect": {
                "status": effect_status,
                "direction": direction,
                "statistics": stats,
                "matched_ids": matched,
                "by_slice": by_slice,
                "claim_scope": "matched_completed_pairs_only",
            },
            "coverage": coverage,
            "cost": {"status": cost_status, **budget},
            "practical": practical,
            "next_action": practical["next_action"],
            "evidence_range": practical["evidence_range"],
        }
    ).to_json()
