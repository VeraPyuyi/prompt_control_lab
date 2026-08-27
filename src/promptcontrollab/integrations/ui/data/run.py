"""Run discovery and top-level artifact loading for the dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from promptcontrollab.core.files import JsonDict, read_json
from promptcontrollab.evaluation.report_model import ReportModel
from promptcontrollab.integrations.ui.data.constants import (
    _INTERNAL_RUN_DIRECTORIES,
    CONTROL_ARTIFACTS,
    RUN_ARTIFACTS,
    RUN_LEVEL_ARTIFACTS,
)
from promptcontrollab.integrations.ui.data.control import (
    _load_prompt_reach_artifacts,
    _read_control_json,
    load_jsonl_safe,
    redact_for_display,
)


def list_runs(runs_dir: Path) -> list[JsonDict]:
    """List run directories under ``runs_dir``."""

    if not runs_dir.exists():
        return []
    runs: list[JsonDict] = []
    for child in sorted(runs_dir.iterdir(), key=lambda path: path.name):
        if not child.is_dir() or child.name in _INTERNAL_RUN_DIRECTORIES:
            continue
        case = _featured_case_run(child)
        if case:
            runs.append(case)
        elif _has_any_artifact(child):
            runs.append({"name": child.name, "path": str(child)})
    if runs:
        return sorted(runs, key=_run_sort_key)
    current_case = _featured_case_run(runs_dir)
    if current_case:
        return [current_case]
    if _has_run_level_artifact(runs_dir):
        return [{"name": runs_dir.name, "path": str(runs_dir)}]
    if _has_any_artifact(runs_dir):
        return [{"name": runs_dir.name, "path": str(runs_dir)}]
    for child in sorted(runs_dir.iterdir(), key=lambda path: path.name):
        if child.is_dir():
            runs.append({"name": child.name, "path": str(child)})
    return runs


def _featured_case_run(case_dir: Path) -> JsonDict:
    """Return one curated case row when its nested review is valid and bounded."""

    manifest_path = case_dir / "case_manifest.json"
    if not manifest_path.is_file():
        return {}
    try:
        manifest = read_json(manifest_path)
    except (OSError, ValueError):
        return {}
    display = manifest.get("display")
    if not isinstance(display, dict):
        return {}
    review_name = display.get("review_path", "review")
    if not isinstance(review_name, str) or not review_name:
        return {}
    relative = Path(review_name)
    if relative.is_absolute() or ".." in relative.parts:
        return {}
    review_dir = (case_dir / relative).resolve(strict=False)
    case_root = case_dir.resolve(strict=False)
    if case_root not in review_dir.parents or not _has_any_artifact(review_dir):
        return {}
    title = _localized_mapping(display.get("title"))
    summary = _localized_mapping(display.get("summary"))
    boundary = _localized_mapping(display.get("boundary"))
    row: JsonDict = {
        "name": case_dir.name,
        "path": str(review_dir),
        "featured": display.get("featured") is True,
        "order": _case_order(display.get("order")),
    }
    for key, value in (
        ("title", title),
        ("summary", summary),
        ("boundary", boundary),
        ("category", display.get("category")),
        ("evidence_level", display.get("evidence_level")),
        ("technical_change_kind", display.get("technical_change_kind")),
        ("decision", manifest.get("decision")),
    ):
        if value not in ({}, None, ""):
            row[key] = value
    return row


def _localized_mapping(value: object) -> JsonDict:
    """Keep only bounded English and Chinese strings from display metadata."""

    if not isinstance(value, dict):
        return {}
    return {
        language: text
        for language in ("en", "zh")
        if isinstance((text := value.get(language)), str) and text
    }


def _case_order(value: object) -> int:
    """Normalize a public case order without accepting booleans or negative values."""

    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return 10_000


def _run_sort_key(row: JsonDict) -> tuple[int, int, str]:
    """Place featured cases first while preserving deterministic run ordering."""

    return (
        0 if row.get("featured") is True else 1,
        _case_order(row.get("order")),
        str(row.get("name") or ""),
    )


def load_run_detail(run_dir: Path) -> JsonDict:
    """Load all known artifacts for one run directory."""

    model = ReportModel.from_run(run_dir)
    control_run = _read_control_json(run_dir / "control_run.json")
    events = load_jsonl_safe(run_dir / "events.jsonl")
    preflight = _read_control_json(run_dir / "preflight.json")
    attribution = model.attribution
    stability = model.stability
    decision = _read_control_json(run_dir / "decision.json")
    provider_result = _read_control_json(run_dir / "provider_result.json")
    audit = cast(JsonDict, redact_for_display(model.audit))
    prompt_reach_artifacts, prompt_reach_paths = _load_prompt_reach_artifacts(run_dir)
    decision_trace = model.decision_trace
    control_artifacts = [name for name in CONTROL_ARTIFACTS if (run_dir / name).exists()]
    artifacts = [*model.artifacts]
    artifacts.extend(name for name in control_artifacts if name not in artifacts)
    artifacts.extend(name for name in prompt_reach_paths if name not in artifacts)
    if decision_trace and "decision_trace.json" not in artifacts:
        artifacts.append("decision_trace.json")
    return {
        "name": run_dir.name,
        "path": str(run_dir),
        "has_artifacts": model.has_artifacts or bool(control_artifacts),
        "artifacts": artifacts,
        "control_run": control_run,
        "events": events,
        "preflight": preflight,
        "attribution": attribution,
        "stability": stability,
        "decision": decision,
        "provider_result": provider_result,
        "audit_result": audit,
        "manifest": model.manifest,
        "source_manifest": model.source_manifest,
        "evidence_matrix": model.evidence_matrix,
        "interpretability_report": model.interpretability_report,
        "peoc_evidence": model.peoc_evidence,
        "peoc_case_study": model.peoc_case_study,
        "stats": model.stats,
        "splits": model.splits,
        "gate": model.gate,
        "change_review": model.change_review,
        "comparison_validity": model.comparison_validity,
        "human_feedback": model.human_feedback,
        "trace_import": model.trace_import,
        "explanation": model.explanation,
        "model_drift": model.model_drift,
        "audit": audit,
        "history_index": model.history_index,
        "history_compare": model.history_compare,
        "agent_run": model.agent_run,
        "posttrain_gate": model.posttrain_gate,
        "checkpoint_comparison": model.checkpoint_comparison,
        "mechanism_attribution": model.mechanism_attribution,
        "prompt_reach_artifacts": prompt_reach_artifacts,
        "decision_trace": decision_trace,
        "research_diagnostics": model.research_diagnostics,
        "research_gap_plan": model.research_gap_plan,
        "research_gap_status": model.research_gap_status,
        "evidence_card": model.evidence_card,
        "evidence_gate": model.evidence_gate,
        "claim_check": model.claim_check,
        "external_evidence": model.external_evidence,
        "bridge_summary": model.bridge_summary,
        "ecosystem_demo": model.ecosystem_demo,
        "ecosystem_scorecard": model.ecosystem_scorecard,
        "prompt_assets": model.prompt_assets,
        "prompt_optimizer_gap_plan": model.prompt_optimizer_gap_plan,
        "scaffold_check": model.scaffold_check,
        "diagnostics": model.diagnostics,
        "baseline_metrics": model.baseline_metrics,
        "candidate_metrics": model.candidate_metrics,
        "metrics": model.metrics,
        "candidate_score": model.candidate_score,
        "baseline_score": model.baseline_score,
        "first_comparison": model.first_comparison,
        "mean_delta": model.mean_delta,
        "bootstrap_ci": model.bootstrap_ci,
        "permutation_p_value": model.permutation_p_value,
        "holm_adjusted_p_value": model.holm_adjusted_p_value,
        "empty_state": (
            "Run `pcl analyze` with a config, for example "
            "`pcl analyze --config promptcontrol.example.yaml --out runs/quick`, "
            "or select a run directory with PromptControlLab artifacts."
        ),
    }


def first_comparison(stats: JsonDict) -> JsonDict:
    """Return the primary comparison from a stats artifact.

    Current ``stats.json`` files store comparison metrics in ``comparisons[0]``.
    Older UI fixtures used top-level comparison fields, so keep that shape
    readable for existing artifacts.
    """

    comparisons = stats.get("comparisons")
    if isinstance(comparisons, list) and comparisons and isinstance(comparisons[0], dict):
        return comparisons[0]
    if any(
        key in stats
        for key in [
            "mean_delta",
            "bootstrap_ci",
            "permutation_p_value",
            "holm_adjusted_p_value",
        ]
    ):
        return stats
    return {}


def _has_any_artifact(path: Path) -> bool:
    """Normalize has any artifact values for dashboard use."""
    return any((path / name).exists() for name in RUN_ARTIFACTS)


def _has_run_level_artifact(path: Path) -> bool:
    """Normalize has run level artifact values for dashboard use."""
    return any((path / name).exists() for name in RUN_LEVEL_ARTIFACTS)
