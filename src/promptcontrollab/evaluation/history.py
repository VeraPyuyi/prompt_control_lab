"""Run history indexing and comparison helpers."""

from __future__ import annotations

from pathlib import Path

from promptcontrollab.core.files import JsonDict, read_json, write_json

PROMPT_IDENTITY_KEYS = ["prompt_hash", "prompt_id", "prompt_version", "prompt_file"]


def index_history(*, runs_dir: Path, out_path: Path) -> JsonDict:
    """Index PromptControlLab run directories."""

    runs: list[JsonDict] = []
    warnings: list[str] = []
    children = sorted(runs_dir.iterdir(), key=lambda path: path.name) if runs_dir.exists() else []
    for child in children:
        if not child.is_dir():
            continue
        summary = summarize_run(child)
        if not summary["artifacts"]:
            warnings.append(f"Skipped {child}: no run artifacts found.")
            continue
        runs.append(summary)
    payload: JsonDict = {"runs_dir": str(runs_dir), "runs": runs, "warnings": warnings}
    write_json(out_path, payload)
    return payload


def compare_history(*, a_dir: Path, b_dir: Path, out_path: Path) -> JsonDict:
    """Compare two PromptControlLab runs."""

    a = summarize_run(a_dir)
    b = summarize_run(b_dir)
    a_score = _optional_float(a.get("mean_score"))
    b_score = _optional_float(b.get("mean_score"))
    metric_delta = (
        round(b_score - a_score, 10)
        if a_score is not None and b_score is not None
        else None
    )
    payload: JsonDict = {
        "a": str(a_dir),
        "b": str(b_dir),
        "prompt_same": _same_or_unknown(a["prompt_identity"], b["prompt_identity"]),
        "model_same": _same_or_unknown(a["model"], b["model"]),
        "metric_delta": metric_delta,
        "gate_status_change": {"a": a.get("gate_status"), "b": b.get("gate_status")},
        "regressed_slices": _regressed_slices(a.get("by_slice"), b.get("by_slice")),
        "new_risk_categories": sorted(set(b["risk_categories"]) - set(a["risk_categories"])),
        "resolved_risk_categories": sorted(set(a["risk_categories"]) - set(b["risk_categories"])),
        "warnings": [*a["warnings"], *b["warnings"]],
    }
    write_json(out_path, payload)
    return payload


def summarize_run(run_dir: Path) -> JsonDict:
    """Return a compact run summary."""

    manifest_artifact = _read_optional_json(run_dir / "manifest.json")
    control_run = _read_optional_json(run_dir / "control_run.json")
    manifest = manifest_artifact or control_run
    metrics = _read_metrics(run_dir)
    gate = _read_optional_json(run_dir / "gate_result.json")
    audit = _read_optional_json(run_dir / "audit_result.json")
    agent_run = _read_optional_json(run_dir / "agent_run.json")
    change_review = _read_optional_json(run_dir / "change_review.json")
    stability = _read_optional_json(run_dir / "stability.json")
    artifacts = [
        name
        for name in [
            "manifest.json",
            "metrics.json",
            "candidate/metrics.json",
            "stats.json",
            "gate_result.json",
            "explanation.json",
            "audit_result.json",
            "report.md",
            "report.html",
            "agent_run.json",
            "control_run.json",
            "trace_import.json",
            "change_review.json",
            "comparison_validity.json",
            "attribution.json",
            "stability.json",
            "decision_trace.json",
            "human_feedback.json",
        ]
        if (run_dir / name).exists()
    ]
    warnings: list[str] = []
    if not manifest_artifact and not control_run and artifacts:
        warnings.append(f"{run_dir} has artifacts but no manifest.json.")
    return {
        "run_name": run_dir.name,
        "path": str(run_dir),
        "artifacts": artifacts,
        "method": manifest.get("method"),
        "metric": manifest.get("metric"),
        "created_at": manifest.get("created_at"),
        "prompt_identity": _prompt_identity(manifest),
        "model": _model_identity(manifest),
        "baseline_model": (
            manifest.get("baseline_model")
            if isinstance(manifest.get("baseline_model"), dict)
            else {}
        ),
        "candidate_model": (
            manifest.get("candidate_model")
            if isinstance(manifest.get("candidate_model"), dict)
            else {}
        ),
        "mean_score": metrics.get("mean_score"),
        "by_slice": metrics.get("by_slice") if isinstance(metrics.get("by_slice"), dict) else {},
        "gate_status": gate.get("status"),
        "risk_categories": _combined_risk_categories(gate, audit),
        "risk_level": _risk_level(gate, audit, agent_run, change_review, stability),
        "review_required": _review_required(
            gate, audit, agent_run, change_review, stability
        ),
        "human_review_required": _review_required(
            gate, audit, agent_run, change_review, stability
        ),
        "change_kind": change_review.get("change_kind"),
        "change_decision": change_review.get("decision"),
        "stability_state": stability.get("state"),
        "agent_run": agent_run,
        "warnings": warnings,
    }


def _read_optional_json(path: Path) -> JsonDict:
    if not path.exists():
        return {}
    return read_json(path)


def _read_metrics(run_dir: Path) -> JsonDict:
    metrics = _read_optional_json(run_dir / "metrics.json")
    if metrics:
        return metrics
    return _read_optional_json(run_dir / "candidate" / "metrics.json")


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
    model = manifest.get("model")
    provider = manifest.get("provider")
    if isinstance(model, str) and model:
        return {
            key: value
            for key, value in {"provider": provider, "model_id": model}.items()
            if isinstance(value, str) and value
        }
    return {}


def _risk_categories(gate: JsonDict) -> list[str]:
    categories: list[str] = []
    checks = gate.get("checks")
    if not isinstance(checks, dict):
        return categories
    for check in checks.values():
        if not isinstance(check, dict):
            continue
        for key in ["risk_categories", "violations"]:
            values = check.get(key)
            if isinstance(values, list):
                categories.extend(str(item) for item in values)
    return sorted(set(categories))


def _combined_risk_categories(gate: JsonDict, audit: JsonDict) -> list[str]:
    categories = _risk_categories(gate)
    if audit.get("dangerous_paths"):
        categories.append("dangerous_path")
    if audit.get("public_api_changed"):
        categories.append("public_api")
    if audit.get("secret_findings"):
        categories.append("secret")
    if audit.get("dependency_files_changed"):
        categories.append("dependency")
    if audit.get("lockfiles_changed"):
        categories.append("lockfile")
    if audit.get("workflow_files_changed"):
        categories.append("workflow")
    if audit.get("deleted_test_files"):
        categories.append("deleted_test")
    if audit.get("unexpected_files"):
        categories.append("unexpected_file")
    return sorted(set(categories))


def _risk_level(
    gate: JsonDict,
    audit: JsonDict,
    agent_run: JsonDict,
    change_review: JsonDict | None = None,
    stability: JsonDict | None = None,
) -> str | None:
    review = change_review or {}
    stability_payload = stability or {}
    observed: list[str] = []
    agent_risk = agent_run.get("risk_level")
    if agent_risk in {"low", "medium", "high"}:
        observed.append(str(agent_risk))
    if (
        audit.get("secret_findings")
        or audit.get("dangerous_paths")
        or audit.get("workflow_files_changed")
        or audit.get("deleted_test_files")
    ):
        observed.append("high")
    if gate.get("status") == "fail" or review.get("decision") == "hold":
        observed.append("high")
    if stability_payload.get("state") == "diverging":
        observed.append("high")
    if (
        gate.get("status") == "needs_review"
        or review.get("decision") in {"needs_review", "insufficient_evidence"}
        or audit.get("human_review_required")
        or stability_payload.get("state") in {"stalled", "oscillating"}
    ):
        observed.append("medium")
    if gate.get("status") == "pass" or review.get("decision") == "pass":
        observed.append("low")
    if not observed:
        return None
    rank = {"low": 0, "medium": 1, "high": 2}
    return max(observed, key=rank.__getitem__)


def _review_required(
    gate: JsonDict,
    audit: JsonDict,
    agent_run: JsonDict,
    change_review: JsonDict | None = None,
    stability: JsonDict | None = None,
) -> bool:
    review = change_review or {}
    stability_payload = stability or {}
    return bool(
        gate.get("status") in {"fail", "needs_review"}
        or review.get("decision") in {"hold", "needs_review", "insufficient_evidence"}
        or audit.get("human_review_required")
        or agent_run.get("review_required")
        or agent_run.get("human_review_required")
        or stability_payload.get("state") in {"diverging", "stalled", "oscillating"}
        or _risk_level(gate, audit, agent_run, review, stability_payload)
        in {"high", "medium"}
    )


def _same_or_unknown(a: object, b: object) -> bool | str:
    if not a or not b:
        return "unknown"
    return a == b


def _optional_float(value: object) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    return None


def _regressed_slices(a: object, b: object) -> list[JsonDict]:
    if not isinstance(a, dict) or not isinstance(b, dict):
        return []
    regressions: list[JsonDict] = []
    for slice_name in sorted(set(a) & set(b)):
        a_value = _optional_float(a.get(slice_name))
        b_value = _optional_float(b.get(slice_name))
        if a_value is None or b_value is None:
            continue
        delta = round(b_value - a_value, 10)
        if delta < 0:
            regressions.append(
                {"slice": str(slice_name), "a": a_value, "b": b_value, "delta": delta}
            )
    return regressions
