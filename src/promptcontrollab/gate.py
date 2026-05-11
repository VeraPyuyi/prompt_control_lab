"""Policy gates for prompt analysis runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from promptcontrollab.config import read_simple_yaml
from promptcontrollab.files import JsonDict, read_json, write_json


def run_gate(run_dir: Path, *, policy_path: Path) -> JsonDict:
    """Evaluate a run against a simple threshold policy."""

    policy = read_simple_yaml(policy_path)
    candidate_metrics = _read_optional_json(run_dir / "candidate" / "metrics.json")
    if not candidate_metrics:
        candidate_metrics = _read_optional_json(run_dir / "metrics.json")
    stats = _read_optional_json(run_dir / "stats.json")
    diagnostics = _collect_diagnostics(run_dir / "diagnostics")
    comparison = _first_comparison(stats)
    checks: JsonDict = {
        "candidate_score": _candidate_score_check(candidate_metrics, policy),
        "regression": _regression_check(comparison, policy),
        "statistical_evidence": _p_value_check(comparison, policy),
        "soft_hard_risk": _soft_hard_check(diagnostics, policy),
    }
    hard_fail = any(
        isinstance(check, dict) and check.get("severity") == "fail" and not check.get("passed")
        for check in checks.values()
    )
    needs_review = any(
        isinstance(check, dict)
        and check.get("severity") == "review"
        and not check.get("passed", True)
        for check in checks.values()
    )
    if hard_fail:
        status = "fail"
    elif needs_review:
        status = "needs_review"
    else:
        status = "pass"
    payload: JsonDict = {
        "status": status,
        "policy_path": str(policy_path),
        "checks": checks,
        "plain_summary": _plain_summary(status),
        "what_this_means": _status_sentence(status),
    }
    write_json(run_dir / "gate_result.json", payload)
    return payload


def _read_optional_json(path: Path) -> JsonDict:
    if not path.exists():
        return {}
    return read_json(path)


def _collect_diagnostics(path: Path) -> dict[str, JsonDict]:
    if not path.exists():
        return {}
    return {item.stem: read_json(item) for item in sorted(path.glob("*.json"))}


def _first_comparison(stats: JsonDict) -> JsonDict:
    comparisons = stats.get("comparisons", [])
    if isinstance(comparisons, list) and comparisons and isinstance(comparisons[0], dict):
        return comparisons[0]
    return {}


def _candidate_score_check(metrics: JsonDict, policy: JsonDict) -> JsonDict:
    threshold = _optional_float(policy.get("min_candidate_score"))
    score = _float(metrics.get("mean_score"))
    if threshold is None:
        return {"passed": True, "severity": "info", "message": "No candidate score threshold set."}
    passed = score >= threshold
    return {
        "passed": passed,
        "severity": "fail",
        "observed": score,
        "threshold": threshold,
        "message": (
            "Candidate mean score meets the minimum."
            if passed
            else "Candidate mean score is too low."
        ),
    }


def _regression_check(comparison: JsonDict, policy: JsonDict) -> JsonDict:
    threshold = _optional_float(policy.get("max_regression"))
    delta = _float(comparison.get("mean_delta"))
    if threshold is None:
        return {"passed": True, "severity": "info", "message": "No regression threshold set."}
    passed = delta >= -threshold
    return {
        "passed": passed,
        "severity": "fail",
        "observed_delta": delta,
        "max_regression": threshold,
        "message": (
            "Candidate does not exceed the allowed regression."
            if passed
            else "Candidate regressed too much."
        ),
    }


def _p_value_check(comparison: JsonDict, policy: JsonDict) -> JsonDict:
    threshold = _optional_float(policy.get("require_adjusted_p_below"))
    p_value = _optional_float(comparison.get("holm_adjusted_p_value"))
    if threshold is None:
        return {"passed": True, "severity": "info", "message": "No adjusted p-value threshold set."}
    if p_value is None:
        return {
            "passed": False,
            "severity": "review",
            "message": "No adjusted p-value is available.",
        }
    passed = p_value <= threshold
    return {
        "passed": passed,
        "severity": "review",
        "observed": p_value,
        "threshold": threshold,
        "message": (
            "Adjusted p-value meets the policy."
            if passed
            else "Statistical evidence is not strong enough."
        ),
    }


def _soft_hard_check(diagnostics: dict[str, JsonDict], policy: JsonDict) -> JsonDict:
    threshold = policy.get("max_soft_hard_risk")
    if threshold is None:
        return {"passed": True, "severity": "info", "message": "No soft-hard risk threshold set."}
    if not isinstance(threshold, str):
        msg = "Policy key `max_soft_hard_risk` must be a string"
        raise ValueError(msg)
    risk = diagnostics.get("soft_hard", {}).get("risk", "unknown")
    passed = _risk_rank(str(risk)) <= _risk_rank(threshold)
    return {
        "passed": passed,
        "severity": "review",
        "observed": risk,
        "threshold": threshold,
        "message": "Soft-hard risk meets the policy." if passed else "Soft-hard risk needs review.",
    }


def _status_sentence(status: str) -> str:
    if status == "pass":
        return "The run meets the configured policy thresholds."
    if status == "fail":
        return "At least one required threshold failed."
    return "The run did not hard-fail, but one or more checks need review."


def _plain_summary(status: str) -> str:
    if status == "pass":
        return "Deployment recommendation: yes. The configured checks passed."
    if status == "fail":
        return "Deployment recommendation: no. At least one required check failed."
    return (
        "Deployment recommendation: needs human review. No hard failure was found, "
        "but one or more checks need attention."
    )


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return _float(value)


def _float(value: Any) -> float:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            pass
    msg = f"Expected numeric value, got {value!r}"
    raise ValueError(msg)


def _risk_rank(value: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(value, 3)
