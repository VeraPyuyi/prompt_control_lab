"""Policy gates for prompt analysis runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from promptcontrollab.config import read_simple_yaml
from promptcontrollab.files import JsonDict, read_json, write_json
from promptcontrollab.model_identity import is_alias_model


def run_gate(run_dir: Path, *, policy_path: Path) -> JsonDict:
    """Evaluate a run against a simple threshold policy."""

    policy = read_simple_yaml(policy_path)
    candidate_metrics = _read_optional_json(run_dir / "candidate" / "metrics.json")
    if not candidate_metrics:
        candidate_metrics = _read_optional_json(run_dir / "metrics.json")
    stats = _read_optional_json(run_dir / "stats.json")
    diagnostics = _collect_diagnostics(run_dir / "diagnostics")
    manifest = _read_optional_json(run_dir / "manifest.json")
    comparison_validity = _read_optional_json(run_dir / "comparison_validity.json")
    comparison = _first_comparison(stats)
    checks: JsonDict = {
        "candidate_score": _candidate_score_check(candidate_metrics, policy),
        "regression": _regression_check(comparison, policy),
        "statistical_evidence": _p_value_check(comparison, policy),
        "soft_hard_risk": _soft_hard_check(diagnostics, policy),
        "model_provenance": _model_provenance_check(manifest, policy),
        "comparison_validity": _comparison_validity_check(comparison_validity),
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
    if threshold is None:
        return {"passed": True, "severity": "info", "message": "No regression threshold set."}
    delta = _float(comparison.get("mean_delta"))
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


def _model_provenance_check(manifest: JsonDict, policy: JsonDict) -> JsonDict:
    baseline = _model_dict(manifest.get("baseline_model"))
    candidate = _model_dict(manifest.get("candidate_model"))
    single = _model_dict(manifest.get("model"))
    models = [item for item in [baseline, candidate] if item]
    if not models and single:
        models = [single]
    has_policy = any(
        key in policy
        for key in [
            "allowed_models",
            "allowed_providers",
            "block_if_model_unknown",
            "block_if_model_mismatch",
            "block_if_alias_model",
            "require_model_verified",
        ]
    )
    if not has_policy:
        return {"passed": True, "severity": "info", "message": "No model policy set."}

    violations: list[str] = []
    allowed_models = set(_split_list(policy.get("allowed_models")))
    allowed_providers = set(_split_list(policy.get("allowed_providers")))
    unknown = not models or any(_model_id(model) == "unknown" for model in models)
    mismatch = bool(baseline and candidate and _model_key(baseline) != _model_key(candidate))
    alias = any(is_alias_model(_model_id(model)) for model in models)
    unverified = any(model.get("verified") is not True for model in models)

    if unknown and (
        _bool(policy.get("block_if_model_unknown"))
        or bool(allowed_models)
        or bool(allowed_providers)
        or _bool(policy.get("require_model_verified"))
    ):
        violations.append("model_unknown")
    if mismatch and _bool(policy.get("block_if_model_mismatch")):
        violations.append("model_mismatch")
    if alias and _bool(policy.get("block_if_alias_model")):
        violations.append("alias_model")
    if unverified and _bool(policy.get("require_model_verified")):
        violations.append("model_unverified")
    if allowed_models:
        for model in models:
            if _model_id(model) not in allowed_models:
                violations.append("model_not_allowed")
                break
    if allowed_providers:
        for model in models:
            if _provider(model) not in allowed_providers:
                violations.append("provider_not_allowed")
                break

    passed = not violations
    return {
        "passed": passed,
        "severity": "fail" if not passed else "info",
        "violations": violations,
        "baseline_model": baseline,
        "candidate_model": candidate,
        "message": "Model provenance meets the policy." if passed else "Model policy failed.",
    }


def _comparison_validity_check(payload: JsonDict) -> JsonDict:
    if not payload:
        return {
            "passed": True,
            "severity": "info",
            "message": "No comparison validity artifact was found.",
        }
    validity = payload.get("validity")
    if validity == "invalid":
        return {
            "passed": False,
            "severity": "fail",
            "observed": validity,
            "prompt_only_comparison": payload.get("prompt_only_comparison"),
            "blocking_issues": payload.get("blocking_issues", []),
            "review_items": payload.get("review_items", []),
            "message": "Comparison validity failed; prompt-only evidence is confounded.",
        }
    if validity == "needs_review":
        return {
            "passed": False,
            "severity": "review",
            "observed": validity,
            "prompt_only_comparison": payload.get("prompt_only_comparison"),
            "blocking_issues": payload.get("blocking_issues", []),
            "review_items": payload.get("review_items", []),
            "message": "Comparison validity needs review before treating this as prompt-only.",
        }
    return {
        "passed": True,
        "severity": "info",
        "observed": validity or "unknown",
        "prompt_only_comparison": payload.get("prompt_only_comparison"),
        "message": "Comparison validity does not require gate action.",
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


def _split_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).replace("|", ",").split(",") if item.strip()]


def _bool(value: object) -> bool:
    return value is True or (isinstance(value, str) and value.lower() == "true")


def _model_dict(value: object) -> JsonDict:
    return value if isinstance(value, dict) else {}


def _model_id(model: JsonDict) -> str:
    value = model.get("model_id")
    return value if isinstance(value, str) and value else "unknown"


def _provider(model: JsonDict) -> str:
    value = model.get("provider")
    return value if isinstance(value, str) and value else "unknown"


def _model_key(model: JsonDict) -> tuple[str, str]:
    return (_provider(model), _model_id(model))
