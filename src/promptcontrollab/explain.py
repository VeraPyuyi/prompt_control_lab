"""Plain-language and technical explanations for run artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from promptcontrollab.evaluation import load_scored_predictions
from promptcontrollab.files import JsonDict, read_json, write_json

EXPLAIN_LEVELS = {"plain", "technical"}


def generate_explanation(run_dir: Path, *, level: str) -> JsonDict:
    """Generate ``explanation.json`` for a quick or expert run directory."""

    if level not in EXPLAIN_LEVELS:
        msg = "Explanation level must be `plain` or `technical`"
        raise ValueError(msg)

    baseline_metrics = _read_optional_json(run_dir / "baseline" / "metrics.json")
    candidate_metrics = _read_optional_json(run_dir / "candidate" / "metrics.json")
    if not candidate_metrics:
        candidate_metrics = _read_optional_json(run_dir / "metrics.json")
    stats = _read_optional_json(run_dir / "stats.json")
    splits = _read_optional_json(run_dir / "splits.json")
    diagnostics = _collect_diagnostics(run_dir / "diagnostics")
    comparison = _first_comparison(stats)
    baseline_mean = _float(
        comparison.get("baseline_mean", baseline_metrics.get("mean_score", 0.0))
    )
    candidate_mean = _float(
        comparison.get("candidate_mean", candidate_metrics.get("mean_score", 0.0))
    )
    mean_delta = _float(comparison.get("mean_delta", candidate_mean - baseline_mean))
    verdict = _verdict(mean_delta, comparison)
    payload: JsonDict = {
        "level": level,
        "plain_summary": _plain_summary(verdict, mean_delta),
        "overall_summary": {
            "verdict": verdict,
            "baseline_mean": baseline_mean,
            "candidate_mean": candidate_mean,
            "mean_delta": mean_delta,
            "what_this_means": _summary_sentence(verdict, mean_delta),
        },
        "evidence_strength": _evidence_strength(comparison),
        "data_hygiene": _data_hygiene(splits),
        "failure_slices": _slice_changes(baseline_metrics, candidate_metrics),
        "example_changes": _example_changes(run_dir),
        "deployment_risk": _deployment_risk(diagnostics),
        "next_action": _next_action(verdict, diagnostics),
    }
    payload["deployment_recommendation"] = _deployment_recommendation(payload["next_action"])
    if level == "technical":
        payload["artifact_paths"] = _artifact_paths(run_dir)
        payload["raw_comparison"] = comparison
    write_json(run_dir / "explanation.json", payload)
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


def _float(value: Any) -> float:
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _verdict(mean_delta: float, comparison: JsonDict) -> str:
    interpretation = comparison.get("interpretation")
    if interpretation == "candidate_improved_reliably":
        return "keep"
    if interpretation == "candidate_regressed_reliably" or mean_delta < 0:
        return "hold"
    return "review"


def _summary_sentence(verdict: str, mean_delta: float) -> str:
    if verdict == "keep":
        return "The candidate prompt improved on the paired evaluation and the evidence is strong."
    if verdict == "hold":
        return "The candidate prompt looks worse or risky, so inspect it before keeping it."
    if mean_delta > 0:
        return "The candidate prompt is higher on average, but the evidence should be reviewed."
    return "The candidate prompt does not show a clear improvement yet."


def _plain_summary(verdict: str, mean_delta: float) -> str:
    if verdict == "keep":
        return "The candidate prompt looks better and the evidence supports keeping it."
    if verdict == "hold":
        return "Do not keep this prompt yet. It regressed or triggered risk signals."
    if mean_delta > 0:
        return "The candidate prompt is higher on average, but it still needs review."
    return "There is no clear improvement yet. Review the prompt before using it."


def _evidence_strength(comparison: JsonDict) -> JsonDict:
    if not comparison:
        return {
            "status": "missing_stats",
            "what_this_means": "Run `pcl stats` or `pcl analyze` to compare prompts.",
        }
    return {
        "n": comparison.get("n", 0),
        "bootstrap_ci": comparison.get("bootstrap_ci", []),
        "permutation_p_value": comparison.get("permutation_p_value"),
        "holm_adjusted_p_value": comparison.get("holm_adjusted_p_value"),
        "interpretation": comparison.get("interpretation"),
        "what_this_means": (
            "The confidence interval and p-value show whether the observed score change is "
            "likely to be reliable or still uncertain."
        ),
    }


def _data_hygiene(splits: JsonDict) -> JsonDict:
    leakage = splits.get("leakage", {})
    has_leakage = bool(leakage.get("has_leakage", False)) if isinstance(leakage, dict) else False
    return {
        "split_hash": splits.get("split_hash"),
        "counts": splits.get("counts", {}),
        "has_leakage": has_leakage,
        "what_this_means": (
            "No leakage means train, validation, and withheld ids are separated in the split "
            "manifest. Leakage means the evaluation protocol should be fixed."
        ),
    }


def _slice_changes(baseline_metrics: JsonDict, candidate_metrics: JsonDict) -> JsonDict:
    baseline_slices = baseline_metrics.get("by_slice", {})
    candidate_slices = candidate_metrics.get("by_slice", {})
    if not isinstance(baseline_slices, dict) or not isinstance(candidate_slices, dict):
        return {"regressed": {}, "improved": {}, "unchanged": {}}
    regressed: dict[str, float] = {}
    improved: dict[str, float] = {}
    unchanged: dict[str, float] = {}
    for name in sorted(set(baseline_slices) | set(candidate_slices)):
        delta = _float(candidate_slices.get(name, 0.0)) - _float(baseline_slices.get(name, 0.0))
        if delta < 0:
            regressed[name] = delta
        elif delta > 0:
            improved[name] = delta
        else:
            unchanged[name] = delta
    return {
        "regressed": regressed,
        "improved": improved,
        "unchanged": unchanged,
        "what_this_means": (
            "Slice changes show which task groups improved or regressed instead of hiding "
            "everything inside one average score."
        ),
    }


def _example_changes(run_dir: Path) -> JsonDict:
    baseline_path = run_dir / "baseline" / "predictions.jsonl"
    candidate_path = run_dir / "candidate" / "predictions.jsonl"
    if not baseline_path.exists() or not candidate_path.exists():
        return {"fixed_ids": [], "broken_ids": [], "unchanged_ids": []}
    baseline = {record.id: record for record in load_scored_predictions(baseline_path)}
    candidate = {record.id: record for record in load_scored_predictions(candidate_path)}
    fixed: list[str] = []
    broken: list[str] = []
    unchanged: list[str] = []
    for item_id in sorted(set(baseline) & set(candidate)):
        before = baseline[item_id].score
        after = candidate[item_id].score
        if before <= 0 and after > before:
            fixed.append(item_id)
        elif before > 0 and after < before:
            broken.append(item_id)
        else:
            unchanged.append(item_id)
    return {
        "fixed_ids": fixed,
        "broken_ids": broken,
        "unchanged_ids": unchanged,
        "what_this_means": (
            "Fixed ids became better under the candidate prompt. Broken ids became worse and "
            "should be inspected first."
        ),
    }


def _deployment_risk(diagnostics: dict[str, JsonDict]) -> JsonDict:
    risks: JsonDict = {}
    soft_hard = diagnostics.get("soft_hard", {})
    if soft_hard:
        risks["soft_hard"] = {
            "risk": soft_hard.get("risk", "unknown"),
            "what_this_means": (
                "High projection risk means soft prompt behavior may not survive "
                "hard-token deployment."
            ),
        }
    trajectory = diagnostics.get("trajectory", {})
    if trajectory:
        risks["trajectory"] = {
            "turnpike_like_signal": trajectory.get("turnpike_like_signal"),
            "mean_step_drift": trajectory.get("mean_step_drift"),
            "what_this_means": (
                "High drift or weak decay can mean the hidden trajectory is less stable."
            ),
        }
    riccati = diagnostics.get("riccati", {})
    if riccati:
        risks["riccati"] = {
            "stable_surrogate": riccati.get("stable_surrogate"),
            "what_this_means": (
                "This checks whether the fitted control surrogate is internally stable."
            ),
        }
    return {
        "items": risks,
        "what_this_means": (
            "Deployment diagnostics are optional. They become available after running "
            "`pcl soft-hard`, `pcl trajectory`, or `pcl riccati`."
        ),
    }


def _next_action(verdict: str, diagnostics: dict[str, JsonDict]) -> JsonDict:
    soft_hard = diagnostics.get("soft_hard", {})
    if soft_hard.get("risk") == "high":
        return {
            "recommendation": "inspect_before_keep",
            "reason": "Soft-to-hard projection risk is high.",
        }
    if verdict == "keep":
        return {"recommendation": "keep_candidate", "reason": "Evaluation evidence supports it."}
    if verdict == "hold":
        return {"recommendation": "do_not_keep_yet", "reason": "Regression or risk was detected."}
    return {
        "recommendation": "review_candidate",
        "reason": "The result is promising but uncertain.",
    }


def _deployment_recommendation(next_action: object) -> JsonDict:
    recommendation = next_action.get("recommendation") if isinstance(next_action, dict) else None
    reason = next_action.get("reason") if isinstance(next_action, dict) else ""
    if recommendation == "keep_candidate":
        return {
            "label": "yes",
            "color": "green",
            "what_this_means": (
                "The candidate can be kept if the surrounding product constraints are "
                "acceptable."
            ),
            "reason": reason,
        }
    if recommendation in {"do_not_keep_yet", "inspect_before_keep"}:
        return {
            "label": "no",
            "color": "red",
            "what_this_means": "Do not deploy this prompt until the flagged issue is inspected.",
            "reason": reason,
        }
    return {
        "label": "needs_review",
        "color": "yellow",
        "what_this_means": "A person should review the evidence before using this prompt.",
        "reason": reason,
    }


def _artifact_paths(run_dir: Path) -> JsonDict:
    names = [
        "splits.json",
        "baseline/metrics.json",
        "candidate/metrics.json",
        "stats.json",
        "explanation.json",
        "gate_result.json",
        "report.md",
        "report.html",
    ]
    return {name: str(run_dir / name) for name in names if (run_dir / name).exists()}
