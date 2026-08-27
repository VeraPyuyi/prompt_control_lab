"""Local read-only API for the React workflow cockpit."""
# ruff: noqa: RUF001

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from promptcontrollab.core.files import JsonDict
from promptcontrollab.diagnostics.presentation import diagnostic_catalog
from promptcontrollab.evaluation.history import summarize_run
from promptcontrollab.integrations.ui.data import (
    control_certificate_interpretation_rows,
    list_runs,
    load_run_detail,
)


def create_app(
    *,
    runs_dir: Path | None = None,
    language: str | None = None,
    static_dir: Path | None = None,
) -> Any:
    """Create the local FastAPI application without importing it at package import time.

    Args:
        runs_dir: Root containing PromptControlLab run directories.
        language: Initial display language.
        static_dir: Optional built React asset directory.

    Returns:
        A configured FastAPI application.

    Notes:
        The API is intentionally read-only and only exposes normalized summaries from
        recognized run directories below ``runs_dir``.
    """

    from fastapi import FastAPI, HTTPException, Query
    from fastapi.staticfiles import StaticFiles

    root = (runs_dir or Path(os.environ.get("PCL_UI_RUNS", "runs"))).resolve(strict=False)
    initial_language = _language(language or os.environ.get("PCL_UI_LANGUAGE") or "en")
    assets = static_dir or Path(__file__).with_name("web_static")
    app = FastAPI(title="PromptControlLab Workflow Cockpit", version="1")

    @app.get("/api/health")
    def health() -> JsonDict:
        return {
            "status": "ok",
            "mode": "local_read_only",
            "runs_configured": True,
        }

    @app.get("/api/runs")
    def runs() -> JsonDict:
        return {"runs": [_run_projection(item) for item in list_runs(root)]}

    @app.get("/api/history")
    def history() -> JsonDict:
        rows = []
        for item in list_runs(root):
            selected = _select_run(root, str(item.get("name") or ""))
            if selected is not None:
                projection = _history_projection(summarize_run(selected))
                projection["run_name"] = item.get("name")
                rows.append(projection)
        return {"runs": rows}

    @app.get("/api/runs/{run_name}")
    def run_detail(run_name: str, language: str = Query(initial_language)) -> JsonDict:
        selected = _select_run(root, run_name)
        if selected is None:
            raise HTTPException(status_code=404, detail="Run was not found under the runs root")
        return _overview_payload(selected, _language(language), run_name=run_name)

    @app.get("/api/overview")
    def overview(
        run: str | None = Query(default=None),
        language: str = Query(initial_language),
    ) -> JsonDict:
        selected = _select_run(root, run) if run else _first_run(root)
        if run and selected is None:
            raise HTTPException(status_code=404, detail="Run was not found under the runs root")
        if selected is None:
            return {
                "has_run": False,
                "next_action": (
                    "Create or import a run, then use `pcl review --baseline ... "
                    "--candidate ... --out runs/change-review`."
                ),
            }
        display_name = run or _display_name_for_path(root, selected)
        return _overview_payload(selected, _language(language), run_name=display_name)

    @app.get("/api/diagnostics/catalog")
    def diagnostics_catalog(
        run: str | None = Query(default=None),
        language: str = Query(initial_language),
    ) -> dict[str, JsonDict]:
        selected = _select_run(root, run) if run else _first_run(root)
        if run and selected is None:
            raise HTTPException(status_code=404, detail="Run was not found under the runs root")
        return _diagnostic_catalog_with_evidence(selected, _language(language))

    if (assets / "index.html").is_file():
        app.mount("/", StaticFiles(directory=assets, html=True), name="cockpit")
    else:

        @app.get("/")
        def root_message() -> JsonDict:
            return {
                "name": "PromptControlLab Workflow Cockpit",
                "status": "frontend_not_built",
                "next_action": "Build the frontend bundle or use `pcl ui --legacy-streamlit`.",
            }

    return app


def _select_run(root: Path, name: str | None) -> Path | None:
    """Resolve a run only when it is returned by the bounded run discovery API."""

    if not name or any(marker in name for marker in ("/", "\\", "..")):
        return None
    for row in list_runs(root):
        if row.get("name") != name:
            continue
        path = Path(str(row.get("path") or "")).resolve(strict=False)
        if path == root or root in path.parents:
            return path
    return None


def _first_run(root: Path) -> Path | None:
    runs = list_runs(root)
    if not runs:
        return None
    path = Path(str(runs[0].get("path") or "")).resolve(strict=False)
    return path if path == root or root in path.parents else None


def _overview_payload(
    run_dir: Path,
    language: str,
    *,
    run_name: str | None = None,
) -> JsonDict:
    """Return a bounded reviewer-facing projection of one run."""

    detail = load_run_detail(run_dir)
    review = _bounded_review(_dict(detail.get("change_review")))
    feedback = _dict(detail.get("human_feedback"))
    feedback_answers = _dict(feedback.get("answers"))
    attribution = _dict(detail.get("attribution"))
    gate = _dict(detail.get("gate"))
    decision = _dict(detail.get("decision"))
    conclusion = str(
        review.get("decision")
        or decision.get("decision")
        or gate.get("status")
        or "insufficient_evidence"
    )
    next_action = _display_next_action(review, language)
    likely_causes = _likely_causes(attribution, review, language)
    observations = _observations(feedback_answers, detail, review, language)
    return {
        "has_run": True,
        "ui_language": language,
        "run": {"name": run_name or run_dir.name},
        "conclusion": conclusion,
        "change_kind": review.get("change_kind"),
        "likely_causes": likely_causes,
        "risk": _decision_risk(conclusion),
        "evidence_coverage": (
            review.get("coverage") if isinstance(review.get("coverage"), dict) else {}
        ),
        "observations": observations,
        "change_review": review,
        "comparison_validity": _dict(detail.get("comparison_validity")),
        "attribution": attribution,
        "stability": _dict(detail.get("stability")),
        "decision": decision,
        "gate": gate,
        "scores": {
            "baseline": detail.get("baseline_score"),
            "candidate": detail.get("candidate_score"),
            "mean_delta": detail.get("mean_delta"),
            "bootstrap_ci": detail.get("bootstrap_ci"),
            "permutation_p_value": detail.get("permutation_p_value"),
        },
        "diagnostics": control_certificate_interpretation_rows(detail, language),
        "audit": _audit_summary(_dict(detail.get("audit"))),
        "coverage": review.get("coverage") if isinstance(review.get("coverage"), dict) else {},
        "claim_boundary": review.get("claim_boundary"),
        "next_action": next_action,
    }


def _run_projection(item: JsonDict) -> JsonDict:
    """Expose curated case metadata without returning local filesystem paths."""

    projection: JsonDict = {"name": item.get("name")}
    for key in (
        "title",
        "category",
        "decision",
        "evidence_level",
        "featured",
        "order",
        "summary",
        "boundary",
        "technical_change_kind",
    ):
        value = item.get(key)
        if value not in (None, "", {}):
            projection[key] = value
    return projection


def _display_name_for_path(root: Path, selected: Path) -> str:
    """Recover the public run name for a selected internal review directory."""

    resolved = selected.resolve(strict=False)
    for row in list_runs(root):
        if Path(str(row.get("path") or "")).resolve(strict=False) == resolved:
            return str(row.get("name") or selected.name)
    return selected.name


def _likely_causes(
    attribution: JsonDict,
    review: JsonDict,
    language: str,
) -> list[str]:
    """Return bounded explanatory factors, falling back to recorded review reasons."""

    causes: list[str] = []
    factors = attribution.get("factors")
    if isinstance(factors, list):
        for factor in factors:
            if not isinstance(factor, dict) or factor.get("changed") is not True:
                continue
            name = factor.get("factor") or factor.get("name")
            impact = factor.get("impact")
            if name:
                causes.append(_localized_factor(str(name), impact, language))
    reasons = review.get("reasons")
    if not causes and isinstance(reasons, list):
        causes.extend(_localized_reason(str(item), review, language) for item in reasons if item)
    return causes


def _observations(
    feedback_answers: JsonDict,
    detail: JsonDict,
    review: JsonDict,
    language: str,
) -> list[str]:
    """Return concise observations without exposing raw events or prompt content."""

    recorded = _dict(review.get("observations"))
    baseline = recorded.get("baseline_score", detail.get("baseline_score"))
    candidate = recorded.get("candidate_score", detail.get("candidate_score"))
    stability = recorded.get("stability_state")
    gate = recorded.get("candidate_gate")
    observations: list[str] = []
    if isinstance(baseline, int | float) and isinstance(candidate, int | float):
        if language == "zh":
            text = f"记录分数从 {baseline:.6g} 变为 {candidate:.6g}"
            if stability:
                text += f"；稳定性状态为 {_localized_state(str(stability), language)}"
            if gate:
                text += f"；Candidate 门禁为 {_localized_state(str(gate), language)}"
            observations.append(text + "。")
        else:
            text = f"Recorded score changed from {baseline:.6g} to {candidate:.6g}"
            if stability:
                text += f"; stability={stability}"
            if gate:
                text += f"; candidate gate={gate}"
            observations.append(text + ".")
    observations.extend(_metric_delta_observations(recorded.get("metric_deltas"), language))
    if observations:
        return observations
    value = feedback_answers.get("What was observed?")
    if isinstance(value, str) and value:
        return [value]
    if review.get("decision"):
        decision = _localized_state(str(review["decision"]), language)
        observations.append(
            f"记录的审查决策为 {decision}。"
            if language == "zh"
            else f"Recorded review decision: {decision}."
        )
    return observations


def _metric_delta_observations(value: object, language: str) -> list[str]:
    """Render bounded execution-metric deltas without exposing raw run content."""

    if not isinstance(value, dict):
        return []
    labels = {
        "tests_pass_rate": "测试通过率",
        "mean_total_tokens": "完整运行 Token",
        "mean_tool_calls": "平均工具调用次数",
        "mean_touched_files": "平均改动文件数",
        "mean_unnecessary_file_edits": "平均非必要文件改动数",
        "mean_duration_seconds": "平均运行时长（秒）",
        "mean_tokens": "平均 Token",
        "mean_latency_ms": "平均延迟（毫秒）",
        "generation_mismatch": "生成阶段错配",
        "selective_aurc": "选择性风险 AURC",
        "trajectory_drift": "轨迹漂移",
    }
    result: list[str] = []
    for name, item in value.items():
        if name in {"mean_score", "score", "accuracy"} or not isinstance(item, dict):
            continue
        baseline = item.get("baseline")
        candidate = item.get("candidate")
        direction = str(item.get("direction") or "")
        if not isinstance(baseline, int | float) or not isinstance(candidate, int | float):
            continue
        if language == "zh":
            direction_text = {
                "increase": "增加",
                "decrease": "减少",
                "unchanged": "保持不变",
            }.get(direction, "变化")
            label = labels.get(str(name), str(name))
            result.append(
                f"{label}{direction_text}：{float(baseline):.6g} → {float(candidate):.6g}。"
            )
        else:
            verb = {
                "increase": "increased",
                "decrease": "decreased",
                "unchanged": "stayed unchanged",
            }.get(direction, "changed")
            result.append(
                f"{name} {verb}: {float(baseline):.6g} → {float(candidate):.6g}."
            )
        if len(result) == 4:
            break
    return result


def _display_next_action(review: JsonDict, language: str) -> str:
    """Return a localized action while keeping the raw artifact unchanged."""

    decision = str(review.get("decision") or "")
    if language == "zh":
        return {
            "hold": "在晋级前检查 Candidate 门禁的决策轨迹并处理触发项。",
            "needs_review": "先解决列出的证据缺口或混杂因素，再决定是否晋级。",
            "insufficient_evidence": "补充评测指标或执行事件后重新运行 Change Review。",
            "pass": "将本次 Change Review 与发布决策一并保存。",
        }.get(decision, "生成 Change Review，将当前 run 与 baseline 进行比较。")
    value = review.get("next_action")
    return (
        str(value)
        if value
        else "Generate a Change Review to compare this run with a baseline."
    )


def _localized_reason(reason: str, review: JsonDict, language: str) -> str:
    """Translate stable generated review reasons without rewriting arbitrary evidence."""

    if language != "zh":
        return reason
    if (
        review.get("decision") == "hold"
        and "candidate" in reason.lower()
        and "gate" in reason.lower()
    ):
        return "Candidate 已记录的后训练门禁或部署门禁要求暂缓。"
    if (
        review.get("decision") == "needs_review"
        and "candidate" in reason.lower()
        and "gate" in reason.lower()
        and "review" in reason.lower()
    ):
        return "Candidate 门禁要求人工复核。"
    return reason


def _localized_factor(name: str, impact: object, language: str) -> str:
    """Render stable attribution factor identifiers for the selected language."""

    labels = {
        "prompt": "Prompt",
        "model": "模型",
        "agent": "Agent",
        "checkpoint": "Checkpoint",
        "policy": "策略",
        "tools": "工具",
    }
    display = labels.get(name, name) if language == "zh" else name
    return f"{display}: {impact}" if impact else display


def _localized_state(value: str, language: str) -> str:
    """Translate stable decision and stability values for display."""

    if language != "zh":
        return value
    return {
        "hold": "暂缓",
        "pass": "可以继续",
        "needs_review": "需要复核",
        "insufficient_evidence": "证据不足",
        "converging": "正在收敛",
        "stalled": "进展停滞",
        "oscillating": "反复震荡",
        "diverging": "正在发散",
    }.get(value, value)


def _decision_risk(decision: str) -> str:
    """Map a review decision to a conservative display risk."""

    if decision in {"hold", "fail", "failed"}:
        return "high"
    if decision in {"needs_review", "review", "insufficient_evidence"}:
        return "medium"
    return "low" if decision in {"pass", "passed"} else "unknown"


def _diagnostic_catalog_with_evidence(
    selected: Path | None,
    language: str,
) -> dict[str, JsonDict]:
    """Overlay selected-run diagnostic values onto the shared display catalog."""

    catalog = diagnostic_catalog(language)
    if selected is None:
        return catalog
    detail = load_run_detail(selected)
    diagnostics = _dict(detail.get("diagnostics"))
    interpretations = {
        str(row.get("adapter")): row
        for row in control_certificate_interpretation_rows(detail, language)
        if row.get("adapter")
    }
    metric_keys = {
        "terminal_sensitivity": ("decay_rate", "r_squared"),
        "green_certificate": ("hyperbolicity_margin", "boundary_sigma_min"),
        "posterior_certificate": ("h", "existence_radius", "neighborhood_margin"),
    }
    for name, keys in metric_keys.items():
        payload = _dict(diagnostics.get(name))
        if not payload:
            continue
        entry = catalog.setdefault(name, {})
        entry["status"] = payload.get("certificate_level") or payload.get("check_state")
        entry["certificate_level"] = payload.get("certificate_level")
        entry["metrics"] = {key: payload[key] for key in keys if key in payload}
        interpretation = interpretations.get(name)
        if interpretation:
            entry["observation"] = interpretation.get("observed")
            entry["meaning"] = interpretation.get("explains")
            entry["claim_boundary"] = interpretation.get("does_not_prove")
            entry["next_action"] = interpretation.get("next_action")
    return catalog


def _audit_summary(audit: JsonDict) -> JsonDict:
    """Expose diff-level counts and findings without raw patches or test output."""

    keys = (
        "touched_files",
        "source_files_changed",
        "test_files_changed",
        "dangerous_paths",
        "public_api_changed",
        "tests_passed",
        "human_review_required",
        "dependency_files_changed",
        "workflow_files_changed",
        "deleted_test_files",
        "secret_findings",
    )
    return {key: audit[key] for key in keys if key in audit}


def _bounded_review(review: JsonDict) -> JsonDict:
    """Remove local source paths from the browser-facing review payload."""

    return {
        key: value
        for key, value in review.items()
        if key not in {"baseline_run", "candidate_run"}
    }


def _history_projection(summary: JsonDict) -> JsonDict:
    """Expose only fields used by the cockpit history without local file paths."""

    keys = (
        "run_name",
        "created_at",
        "mean_score",
        "gate_status",
        "risk_level",
        "review_required",
        "human_review_required",
        "change_decision",
        "change_kind",
        "stability_state",
        "prompt_identity",
        "model",
    )
    projected: JsonDict = {key: summary.get(key) for key in keys if key in summary}
    agent_run = summary.get("agent_run")
    if isinstance(agent_run, dict):
        model = projected.get("model")
        if not isinstance(model, dict) or not model:
            projected["model"] = {
                key: value
                for key, value in {
                    "provider": agent_run.get("provider"),
                    "model_id": agent_run.get("model"),
                }.items()
                if value
            }
        prompt = projected.get("prompt_identity")
        if not isinstance(prompt, dict) or not prompt:
            prompt_hash = agent_run.get("prompt_hash")
            projected["prompt_identity"] = (
                {"prompt_hash": prompt_hash} if prompt_hash else {}
            )
    return projected


def _dict(value: object) -> JsonDict:
    return value if isinstance(value, dict) else {}


def _language(value: str) -> str:
    return "zh" if value == "zh" else "en"
