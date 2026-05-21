"""Run history indexing and comparison helpers."""

from __future__ import annotations

from pathlib import Path

from promptcontrollab.files import JsonDict, read_json, write_json

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

    manifest = _read_optional_json(run_dir / "manifest.json")
    metrics = _read_metrics(run_dir)
    gate = _read_optional_json(run_dir / "gate_result.json")
    agent_run = _read_optional_json(run_dir / "agent_run.json")
    artifacts = [
        name
        for name in [
            "manifest.json",
            "metrics.json",
            "candidate/metrics.json",
            "stats.json",
            "gate_result.json",
            "explanation.json",
            "report.md",
            "report.html",
            "agent_run.json",
        ]
        if (run_dir / name).exists()
    ]
    warnings: list[str] = []
    if not manifest and artifacts:
        warnings.append(f"{run_dir} has artifacts but no manifest.json.")
    return {
        "run_name": run_dir.name,
        "path": str(run_dir),
        "artifacts": artifacts,
        "method": manifest.get("method"),
        "metric": manifest.get("metric"),
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
        "risk_categories": _risk_categories(gate),
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
