"""Artifact readers for the local Streamlit dashboard."""

from __future__ import annotations

from pathlib import Path

from promptcontrollab.files import JsonDict, read_json

RUN_ARTIFACTS = [
    "manifest.json",
    "stats.json",
    "gate_result.json",
    "explanation.json",
    "model_drift.json",
    "audit_result.json",
    "history_index.json",
    "history_compare.json",
]


def list_runs(runs_dir: Path) -> list[JsonDict]:
    """List run directories under ``runs_dir``."""

    if not runs_dir.exists():
        return []
    if _has_any_artifact(runs_dir):
        return [{"name": runs_dir.name, "path": str(runs_dir)}]
    runs: list[JsonDict] = []
    for child in sorted(runs_dir.iterdir(), key=lambda path: path.name):
        if child.is_dir():
            runs.append({"name": child.name, "path": str(child)})
    return runs


def load_run_detail(run_dir: Path) -> JsonDict:
    """Load all known artifacts for one run directory."""

    manifest = _read_optional(run_dir / "manifest.json")
    stats = _read_optional(run_dir / "stats.json")
    gate = _read_optional(run_dir / "gate_result.json")
    explanation = _read_optional(run_dir / "explanation.json")
    model_drift = _read_optional(run_dir / "model_drift.json")
    audit = _read_optional(run_dir / "audit_result.json")
    history_index = _read_optional(run_dir / "history_index.json")
    history_compare = _read_optional(run_dir / "history_compare.json")
    baseline_metrics = _read_optional(run_dir / "baseline" / "metrics.json")
    candidate_metrics = _read_optional(run_dir / "candidate" / "metrics.json")
    root_metrics = _read_optional(run_dir / "metrics.json")
    artifacts = [name for name in RUN_ARTIFACTS if (run_dir / name).exists()]
    if (run_dir / "baseline" / "metrics.json").exists():
        artifacts.append("baseline/metrics.json")
    if (run_dir / "candidate" / "metrics.json").exists():
        artifacts.append("candidate/metrics.json")
    candidate_score = _score(candidate_metrics) or _score(root_metrics)
    return {
        "name": run_dir.name,
        "path": str(run_dir),
        "has_artifacts": bool(artifacts),
        "artifacts": artifacts,
        "manifest": manifest,
        "stats": stats,
        "gate": gate,
        "explanation": explanation,
        "model_drift": model_drift,
        "audit": audit,
        "history_index": history_index,
        "history_compare": history_compare,
        "baseline_metrics": baseline_metrics,
        "candidate_metrics": candidate_metrics,
        "metrics": root_metrics,
        "candidate_score": candidate_score,
        "baseline_score": _score(baseline_metrics),
        "empty_state": (
            "Run `pcl analyze` with a config, for example "
            "`pcl analyze --config promptcontrol.example.yaml --out runs/quick`, "
            "or select a run directory with PromptControlLab artifacts."
        ),
    }


def risk_category_counts(detail: JsonDict) -> dict[str, int]:
    """Return risk category counts from guard/gate-style artifacts."""

    counts: dict[str, int] = {}
    for category in _extract_categories(detail.get("gate")):
        counts[category] = counts.get(category, 0) + 1
    for category in _extract_categories(detail.get("audit")):
        counts[category] = counts.get(category, 0) + 1
    return counts


def model_rows(detail: JsonDict) -> list[JsonDict]:
    """Return model provenance rows for display."""

    manifest = detail.get("manifest")
    if not isinstance(manifest, dict):
        return []
    rows: list[JsonDict] = []
    for label, key in [("baseline", "baseline_model"), ("candidate", "candidate_model")]:
        model = manifest.get(key)
        if isinstance(model, dict) and model:
            rows.append({"role": label, **model})
    model = manifest.get("model")
    if isinstance(model, dict) and model:
        rows.append({"role": "run", **model})
    return rows


def slice_rows(detail: JsonDict) -> list[JsonDict]:
    """Return baseline/candidate slice rows."""

    baseline = _by_slice(detail.get("baseline_metrics"))
    candidate = _by_slice(detail.get("candidate_metrics"))
    rows: list[JsonDict] = []
    for name in sorted(set(baseline) | set(candidate)):
        rows.append(
            {
                "slice": name,
                "baseline": baseline.get(name),
                "candidate": candidate.get(name),
            }
        )
    return rows


def _read_optional(path: Path) -> JsonDict:
    if not path.exists():
        return {}
    return read_json(path)


def _has_any_artifact(path: Path) -> bool:
    return any((path / name).exists() for name in RUN_ARTIFACTS)


def _score(value: JsonDict) -> float | None:
    raw = value.get("mean_score")
    if isinstance(raw, int | float):
        return float(raw)
    return None


def _by_slice(value: object) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    raw = value.get("by_slice")
    if not isinstance(raw, dict):
        return {}
    result: dict[str, float] = {}
    for key, score in raw.items():
        if isinstance(score, int | float):
            result[str(key)] = float(score)
    return result


def _extract_categories(value: object) -> list[str]:
    if not isinstance(value, dict):
        return []
    categories: list[str] = []
    raw_categories = value.get("risk_categories")
    if isinstance(raw_categories, list):
        categories.extend(str(item) for item in raw_categories)
    checks = value.get("checks")
    if isinstance(checks, dict):
        for check in checks.values():
            if isinstance(check, dict):
                raw = check.get("risk_categories") or check.get("violations")
                if isinstance(raw, list):
                    categories.extend(str(item) for item in raw)
    if value.get("dangerous_paths"):
        categories.append("dangerous_path")
    if value.get("public_api_changed"):
        categories.append("public_api")
    return categories
