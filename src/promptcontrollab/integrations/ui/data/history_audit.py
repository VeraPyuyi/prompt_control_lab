"""History, audit, model, and slice data readers."""

from __future__ import annotations

import json
from pathlib import Path

from promptcontrollab.core.files import JsonDict, read_json


def history_rows(detail: JsonDict) -> list[JsonDict]:
    """Return normalized history rows for tables and trend charts."""

    history = detail.get("history_index")
    if not isinstance(history, dict):
        return []
    runs = history.get("runs")
    if not isinstance(runs, list):
        return []
    rows: list[JsonDict] = []
    for index, item in enumerate(runs, start=1):
        if not isinstance(item, dict):
            continue
        model = item.get("model")
        model_dict = model if isinstance(model, dict) else {}
        prompt = item.get("prompt_identity")
        prompt_dict = prompt if isinstance(prompt, dict) else {}
        rows.append(
            {
                "order": index,
                "run": item.get("run_name"),
                "gate_status": item.get("gate_status"),
                "mean_score": item.get("mean_score"),
                "risk_level": item.get("risk_level"),
                "review_required": item.get("review_required"),
                "provider": model_dict.get("provider"),
                "model": model_dict.get("model_id"),
                "prompt_hash": prompt_dict.get("prompt_hash"),
                "risk_categories": item.get("risk_categories", []),
            }
        )
    return rows


def filter_history_rows(
    rows: list[JsonDict],
    *,
    only_review_required: bool = False,
    only_high_risk: bool = False,
    provider: str = "",
    model: str = "",
) -> list[JsonDict]:
    """Filter normalized history rows for dashboard views."""

    provider_filter = provider.strip().lower()
    model_filter = model.strip().lower()
    filtered: list[JsonDict] = []
    for row in rows:
        if only_review_required and not row.get("review_required"):
            continue
        if only_high_risk and row.get("risk_level") != "high":
            continue
        if provider_filter and provider_filter not in str(row.get("provider") or "").lower():
            continue
        if model_filter and model_filter not in str(row.get("model") or "").lower():
            continue
        filtered.append(row)
    return filtered


def audit_detail_sections(audit: JsonDict) -> dict[str, list[JsonDict]]:
    """Return high-signal audit detail sections for display."""

    return {
        "secret_findings": _dict_rows(audit.get("secret_findings")),
        "secret_scanner": [{"value": str(audit.get("secret_scanner", "builtin"))}],
        "sarif_path": [{"path": str(audit.get("sarif_path", ""))}]
        if audit.get("sarif_path")
        else [],
        "dependency_files_changed": _path_rows(audit.get("dependency_files_changed")),
        "lockfiles_changed": _path_rows(audit.get("lockfiles_changed")),
        "workflow_files_changed": _path_rows(audit.get("workflow_files_changed")),
        "deleted_test_files": _path_rows(audit.get("deleted_test_files")),
        "unexpected_files": _path_rows(audit.get("unexpected_files")),
        "test_results": _dict_rows(audit.get("test_results")),
    }


def changed_line_rows(audit: JsonDict) -> list[JsonDict]:
    """Return changed-line rows annotated with the highest visible audit risk."""

    changed_lines = audit.get("changed_lines")
    if not isinstance(changed_lines, dict):
        return []
    secret_paths = _paths_from_findings(audit.get("secret_findings"))
    workflow_paths = set(_strings(audit.get("workflow_files_changed")))
    dependency_paths = set(_strings(audit.get("dependency_files_changed")))
    lockfile_paths = set(_strings(audit.get("lockfiles_changed")))
    deleted_test_paths = set(_strings(audit.get("deleted_test_files")))
    dangerous_paths = set(_strings(audit.get("dangerous_paths")))
    rows: list[JsonDict] = []
    for path in sorted(str(item) for item in changed_lines):
        counts = changed_lines.get(path)
        counts_dict = counts if isinstance(counts, dict) else {}
        rows.append(
            {
                "file": path,
                "added": counts_dict.get("added", 0),
                "deleted": counts_dict.get("deleted", 0),
                "risk": _file_risk(
                    path,
                    secret_paths=secret_paths,
                    workflow_paths=workflow_paths,
                    dependency_paths=dependency_paths,
                    lockfile_paths=lockfile_paths,
                    deleted_test_paths=deleted_test_paths,
                    dangerous_paths=dangerous_paths,
                ),
            }
        )
    return rows


def guard_download_payloads(result: JsonDict) -> dict[str, str]:
    """Return text payloads for Guard tab download buttons."""

    return {
        "guard_result.json": json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        "improved_prompt.txt": str(result.get("improved_prompt", "")) + "\n",
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
    """Read optional data without exposing unsafe content."""
    if not path.exists():
        return {}
    return read_json(path)


def _by_slice(value: object) -> dict[str, float]:
    """Normalize by slice values for dashboard use."""
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
    """Normalize extract categories values for dashboard use."""
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


def _path_rows(value: object) -> list[JsonDict]:
    """Normalize path rows values for dashboard use."""
    if not isinstance(value, list):
        return []
    return [{"path": str(item)} for item in value]


def _dict_rows(value: object) -> list[JsonDict]:
    """Normalize dict rows values for dashboard use."""
    if not isinstance(value, list):
        return []
    rows: list[JsonDict] = []
    for item in value:
        if isinstance(item, dict):
            rows.append(dict(item))
        else:
            rows.append({"value": str(item)})
    return rows


def _strings(value: object) -> list[str]:
    """Normalize strings values for dashboard use."""
    return [str(item) for item in value] if isinstance(value, list) else []


def _paths_from_findings(value: object) -> set[str]:
    """Normalize paths from findings values for dashboard use."""
    paths: set[str] = set()
    if not isinstance(value, list):
        return paths
    for item in value:
        if isinstance(item, dict) and item.get("path"):
            paths.add(str(item["path"]))
    return paths


def _file_risk(
    path: str,
    *,
    secret_paths: set[str],
    workflow_paths: set[str],
    dependency_paths: set[str],
    lockfile_paths: set[str],
    deleted_test_paths: set[str],
    dangerous_paths: set[str],
) -> str:
    """Normalize file risk values for dashboard use."""
    if path in secret_paths:
        return "secret"
    if path in dangerous_paths:
        return "dangerous_path"
    if path in workflow_paths:
        return "workflow"
    if path in dependency_paths:
        return "dependency"
    if path in lockfile_paths:
        return "lockfile"
    if path in deleted_test_paths:
        return "deleted_test"
    return "normal"
