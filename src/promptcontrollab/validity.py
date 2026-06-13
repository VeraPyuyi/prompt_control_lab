"""Prompt-only comparison validity checks."""

from __future__ import annotations

from pathlib import Path

from promptcontrollab.files import JsonDict, read_json, write_json
from promptcontrollab.model_identity import is_alias_model

PROMPT_IDENTITY_KEYS = ["prompt_hash", "prompt_id", "prompt_version", "prompt_file"]


def run_comparison_validity(
    *,
    baseline_dir: Path,
    candidate_dir: Path,
    out_path: Path,
) -> JsonDict:
    """Check whether a baseline/candidate run comparison is clean prompt-only evidence."""

    baseline = _load_run(baseline_dir)
    candidate = _load_run(candidate_dir)
    blocking_issues: list[str] = []
    review_items: list[str] = []

    checks = {
        "prompt_identity": _check_prompt_identity(baseline["prompt"], candidate["prompt"]),
        "model_identity": _check_model_identity(baseline["model"], candidate["model"]),
        "split_identity": _check_split_identity(baseline["split_hash"], candidate["split_hash"]),
        "metric_identity": _check_metric_identity(baseline["metric"], candidate["metric"]),
        "statistical_evidence": _check_statistical_evidence(candidate["comparison"]),
        "slice_regression": _check_slice_regression(
            baseline["metrics"].get("by_slice"),
            candidate["metrics"].get("by_slice"),
        ),
    }
    for check in checks.values():
        issue = check.get("issue")
        if not isinstance(issue, str) or not issue:
            continue
        if check.get("status") == "fail":
            blocking_issues.append(issue)
        elif check.get("status") == "review":
            review_items.append(issue)

    validity = "clean"
    if blocking_issues:
        validity = "invalid"
    elif review_items:
        validity = "needs_review"

    prompt_only: bool | str = True
    if blocking_issues:
        prompt_only = False
    elif any(check.get("status") == "review" for check in checks.values()):
        prompt_only = "unknown"

    payload: JsonDict = {
        "kind": "comparison_validity",
        "baseline_run": str(baseline_dir),
        "candidate_run": str(candidate_dir),
        "validity": validity,
        "prompt_only_comparison": prompt_only,
        "checks": checks,
        "blocking_issues": blocking_issues,
        "review_items": review_items,
        "warnings": [*baseline["warnings"], *candidate["warnings"]],
        "plain_summary": _plain_summary(validity, prompt_only),
        "next_actions": _next_actions(validity, blocking_issues, review_items),
    }
    write_json(out_path, payload)
    _write_markdown(out_path.with_suffix(".md"), payload)
    return payload


def _load_run(run_dir: Path) -> JsonDict:
    manifest = _read_optional(run_dir / "manifest.json")
    metrics = _read_metrics(run_dir)
    stats = _read_optional(run_dir / "stats.json") or _read_optional(run_dir.parent / "stats.json")
    splits = _read_optional(run_dir / "splits.json") or _read_optional(
        run_dir.parent / "splits.json"
    )
    warnings: list[str] = []
    if not manifest:
        warnings.append(f"{run_dir} has no manifest.json.")
    return {
        "manifest": manifest,
        "metrics": metrics,
        "comparison": _first_comparison(stats),
        "prompt": _prompt_identity(manifest),
        "model": _model_identity(manifest),
        "metric": _string_or_none(manifest.get("metric")),
        "split_hash": _split_hash(manifest, splits),
        "warnings": warnings,
    }


def _check_prompt_identity(baseline: JsonDict, candidate: JsonDict) -> JsonDict:
    if not baseline or not candidate:
        return {
            "status": "review",
            "baseline": baseline,
            "candidate": candidate,
            "issue": "Prompt identity is missing on one or both runs.",
            "what_this_means": (
                "The comparison may still be useful, but it cannot prove which prompt changed."
            ),
        }
    if baseline == candidate:
        return {
            "status": "review",
            "baseline": baseline,
            "candidate": candidate,
            "issue": "Baseline and candidate record the same prompt identity.",
            "what_this_means": "This may not be a prompt-change comparison.",
        }
    return {
        "status": "pass",
        "baseline": baseline,
        "candidate": candidate,
        "what_this_means": "Prompt identities are recorded and differ as expected.",
    }


def _check_model_identity(baseline: JsonDict, candidate: JsonDict) -> JsonDict:
    baseline_id = _string_or_none(baseline.get("model_id"))
    candidate_id = _string_or_none(candidate.get("model_id"))
    baseline_provider = _string_or_none(baseline.get("provider"))
    candidate_provider = _string_or_none(candidate.get("provider"))
    payload: JsonDict = {
        "baseline": baseline,
        "candidate": candidate,
        "baseline_provenance_level": baseline.get("provenance_level"),
        "candidate_provenance_level": candidate.get("provenance_level"),
    }
    if not baseline_id or not candidate_id:
        return {
            **payload,
            "status": "review",
            "issue": "Model identity is missing on one or both runs.",
            "what_this_means": (
                "Prompt-only comparison validity is uncertain without model records."
            ),
        }
    if baseline_id != candidate_id or baseline_provider != candidate_provider:
        return {
            **payload,
            "status": "fail",
            "issue": "Baseline and candidate used different model identities.",
            "what_this_means": "The result is confounded by model/provider change.",
        }
    if is_alias_model(candidate_id):
        return {
            **payload,
            "status": "review",
            "issue": "The compared model id looks like an alias rather than a pinned model.",
            "what_this_means": "Alias model ids can drift over time; pin a dated id if possible.",
        }
    return {
        **payload,
        "status": "pass",
        "what_this_means": "Baseline and candidate used the same recorded model identity.",
    }


def _check_split_identity(baseline: str | None, candidate: str | None) -> JsonDict:
    if not baseline or not candidate:
        return {
            "status": "review",
            "baseline_split_hash": baseline,
            "candidate_split_hash": candidate,
            "issue": "Split identity is missing on one or both runs.",
            "what_this_means": "Train/val/withheld comparability cannot be audited from artifacts.",
        }
    if baseline != candidate:
        return {
            "status": "fail",
            "baseline_split_hash": baseline,
            "candidate_split_hash": candidate,
            "issue": "Baseline and candidate used different split hashes.",
            "what_this_means": "The score change may come from data split changes.",
        }
    return {
        "status": "pass",
        "baseline_split_hash": baseline,
        "candidate_split_hash": candidate,
        "what_this_means": "Both runs report the same split hash.",
    }


def _check_metric_identity(baseline: str | None, candidate: str | None) -> JsonDict:
    if not baseline or not candidate:
        return {
            "status": "review",
            "baseline_metric": baseline,
            "candidate_metric": candidate,
            "issue": "Metric identity is missing on one or both runs.",
            "what_this_means": "Score comparability is weaker without metric provenance.",
        }
    if baseline != candidate:
        return {
            "status": "fail",
            "baseline_metric": baseline,
            "candidate_metric": candidate,
            "issue": "Baseline and candidate used different metrics.",
            "what_this_means": "The reported delta is not a single-metric comparison.",
        }
    return {
        "status": "pass",
        "baseline_metric": baseline,
        "candidate_metric": candidate,
        "what_this_means": "Both runs report the same metric.",
    }


def _check_statistical_evidence(comparison: JsonDict) -> JsonDict:
    if not comparison:
        return {
            "status": "review",
            "issue": "No paired statistical comparison was found.",
            "what_this_means": "Run `pcl stats` or `pcl analyze` before trusting the score delta.",
        }
    mean_delta = _optional_float(comparison.get("mean_delta"))
    ci = comparison.get("bootstrap_ci")
    p_value = _optional_float(
        comparison.get("holm_adjusted_p_value", comparison.get("permutation_p_value"))
    )
    payload: JsonDict = {
        "status": "pass",
        "mean_delta": mean_delta,
        "bootstrap_ci": ci,
        "permutation_p_value": comparison.get("permutation_p_value"),
        "holm_adjusted_p_value": comparison.get("holm_adjusted_p_value"),
        "what_this_means": "Paired statistics are present for the candidate run.",
    }
    if mean_delta is not None and mean_delta < 0:
        return {
            **payload,
            "status": "fail",
            "issue": "Candidate mean delta is negative.",
            "what_this_means": "The candidate regressed on the recorded metric.",
        }
    if _ci_crosses_zero(ci):
        return {
            **payload,
            "status": "review",
            "issue": "Bootstrap confidence interval crosses zero.",
            "what_this_means": "The improvement is uncertain under the recorded CI.",
        }
    if p_value is not None and p_value > 0.05:
        return {
            **payload,
            "status": "review",
            "issue": "Adjusted or permutation p-value is above 0.05.",
            "what_this_means": "The improvement may not be statistically reliable.",
        }
    return payload


def _check_slice_regression(baseline: object, candidate: object) -> JsonDict:
    regressions: list[JsonDict] = []
    if isinstance(baseline, dict) and isinstance(candidate, dict):
        for name in sorted(set(baseline) & set(candidate)):
            old = _optional_float(baseline.get(name))
            new = _optional_float(candidate.get(name))
            if old is None or new is None:
                continue
            delta = round(new - old, 10)
            if delta < 0:
                regressions.append(
                    {"slice": str(name), "baseline": old, "candidate": new, "delta": delta}
                )
    if regressions:
        return {
            "status": "review",
            "regressed_slices": regressions,
            "issue": "One or more task slices regressed.",
            "what_this_means": "Overall gains may hide weaker behavior on specific slices.",
        }
    return {
        "status": "pass",
        "regressed_slices": [],
        "what_this_means": "No slice regression was found in shared slice metrics.",
    }


def _read_optional(path: Path) -> JsonDict:
    if not path.exists():
        return {}
    return read_json(path)


def _read_metrics(run_dir: Path) -> JsonDict:
    root = _read_optional(run_dir / "metrics.json")
    if root:
        return root
    return _read_optional(run_dir / "candidate" / "metrics.json")


def _first_comparison(stats: JsonDict) -> JsonDict:
    comparisons = stats.get("comparisons")
    if isinstance(comparisons, list) and comparisons and isinstance(comparisons[0], dict):
        return comparisons[0]
    if any(key in stats for key in ["mean_delta", "bootstrap_ci", "permutation_p_value"]):
        return stats
    return {}


def _prompt_identity(manifest: JsonDict) -> JsonDict:
    identity: JsonDict = {}
    for key in PROMPT_IDENTITY_KEYS:
        value = manifest.get(key)
        if isinstance(value, str) and value:
            identity[key] = value
    prompt = manifest.get("prompt")
    if isinstance(prompt, dict):
        for key in PROMPT_IDENTITY_KEYS:
            value = prompt.get(key)
            if isinstance(value, str) and value:
                identity[key] = value
    return identity


def _model_identity(manifest: JsonDict) -> JsonDict:
    for key in ["candidate_model", "model", "baseline_model"]:
        value = manifest.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _split_hash(manifest: JsonDict, splits: JsonDict) -> str | None:
    for payload in [splits, manifest]:
        value = payload.get("split_hash")
        if isinstance(value, str) and value:
            return value
    split = manifest.get("split")
    if isinstance(split, dict):
        value = split.get("split_hash")
        if isinstance(value, str) and value:
            return value
    return None


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_float(value: object) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    return None


def _ci_crosses_zero(value: object) -> bool:
    if not isinstance(value, list | tuple) or len(value) < 2:
        return False
    lower = _optional_float(value[0])
    upper = _optional_float(value[1])
    return lower is not None and upper is not None and lower <= 0 <= upper


def _plain_summary(validity: str, prompt_only: bool | str) -> str:
    if validity == "clean":
        return "The comparison looks like clean prompt-only evidence from the recorded artifacts."
    if validity == "invalid":
        return "The comparison is confounded by blocking provenance or protocol issues."
    return (
        "The comparison needs review before treating it as prompt-only evidence "
        f"({prompt_only})."
    )


def _next_actions(validity: str, blocking: list[str], review: list[str]) -> list[str]:
    if validity == "clean":
        return [
            "Keep the comparison artifact with the run report.",
            "Use slice metrics and qualitative examples before deploying the prompt.",
        ]
    actions: list[str] = []
    if blocking:
        actions.append("Re-run baseline and candidate with the same model, metric, and split.")
    if review:
        actions.append("Record missing prompt, model, split, or statistical provenance.")
    actions.append("Regenerate `comparison_validity.json` after the run artifacts are complete.")
    return actions


def _write_markdown(path: Path, payload: JsonDict) -> None:
    rows = [
        "| Check | Status | Meaning |",
        "|---|---|---|",
    ]
    checks = payload.get("checks")
    if isinstance(checks, dict):
        for name, check in checks.items():
            if not isinstance(check, dict):
                continue
            rows.append(
                f"| `{name}` | `{check.get('status')}` | {check.get('what_this_means', '')} |"
            )
    lines = [
        "# Prompt-Only Comparison Validity",
        "",
        f"- Validity: `{payload.get('validity')}`",
        f"- Prompt-only comparison: `{payload.get('prompt_only_comparison')}`",
        f"- Summary: {payload.get('plain_summary')}",
        "",
        "## Checks",
        "",
        *rows,
        "",
        "## Blocking Issues",
        "",
        *_markdown_items(payload.get("blocking_issues")),
        "",
        "## Review Items",
        "",
        *_markdown_items(payload.get("review_items")),
        "",
        "## Next Actions",
        "",
        *_markdown_items(payload.get("next_actions")),
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _markdown_items(value: object) -> list[str]:
    if not isinstance(value, list) or not value:
        return ["- None."]
    return [f"- {item}" for item in value]
