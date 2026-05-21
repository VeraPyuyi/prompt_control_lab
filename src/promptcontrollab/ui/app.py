"""Streamlit app for the local prompt_control_lab dashboard."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any, cast

from promptcontrollab.files import JsonDict
from promptcontrollab.prompt_context import load_prompt_context
from promptcontrollab.prompt_guard import guard_prompt
from promptcontrollab.ui.charts import (
    file_breakdown_bar,
    risk_category_bar,
    score_delta_ci,
    slice_score_heatmap,
)
from promptcontrollab.ui.components import badge, empty_state, metric_cards, prompt_diff
from promptcontrollab.ui.data import list_runs, load_run_detail, model_rows, slice_rows

TEXT = {
    "en": {
        "title": "prompt_control_lab dashboard",
        "subtitle": "Local preflight, provenance, and audit views. No artifacts are uploaded.",
        "runs": "Runs directory",
        "policy": "Guard policy",
        "guard": "Guard Prompt",
        "report": "Run Report",
        "drift": "Model Drift",
        "audit": "Agent Diff Audit",
        "history": "History",
        "prompt": "Prompt",
        "run_guard": "Run guard",
        "selected_run": "Selected run",
        "missing_run": "No run directories found.",
        "empty_run": "This run has no recognized artifacts.",
        "decision": "Decision",
        "risk": "Risk",
        "review": "Required review",
        "categories": "Risk categories",
        "violations": "Policy violations",
        "token_cost": "Estimated token cost",
        "diff": "Prompt diff",
        "recommendation": "Recommendation",
        "gate": "Gate status",
        "candidate_score": "Candidate score",
        "mean_delta": "Mean delta",
        "p_value": "p-value",
        "model_provenance": "Model provenance",
        "drift_risk": "Drift risk",
        "audit_review": "Human review required",
        "dangerous_paths": "Dangerous paths",
        "changed_files": "Changed files",
        "profile": "Profile",
        "mode": "Mode",
        "token_mode": "Token mode",
        "max_tokens": "Max tokens",
        "guarded_prompt": "Guarded prompt",
        "risk_chart": "Risk Categories",
        "count": "count",
        "category": "category",
        "none": "none",
        "score_ci": "Score Delta CI",
        "slice_scores": "Slice Scores",
        "baseline": "baseline",
        "candidate": "candidate",
        "model_timeline": "Model timeline",
        "no_model": "No model provenance recorded.",
        "no_audit": "No audit_result.json found.",
        "public_api": "Public API",
        "tests_passed": "Tests passed",
        "file_breakdown": "Touched Files Breakdown",
        "file_kind": "kind",
        "source_files": "source",
        "test_files": "tests",
        "docs_files": "docs",
        "config_files": "config",
        "path": "path",
        "no_history": "No history_index.json found.",
        "run_timeline": "Run timeline",
        "gate_trend": "Gate trend",
        "score_trend": "Score trend",
        "prompt_identity": "Prompt identity",
        "risk_categories": "Risk categories",
    },
    "zh": {
        "title": "prompt_control_lab 本地仪表盘",
        "subtitle": "本地执行前检查、模型溯源和 agent 审计视图。不会上传 prompt、代码或 artifact。",
        "runs": "Runs 目录",
        "policy": "Guard 策略",
        "guard": "Prompt 守护",
        "report": "运行报告",
        "drift": "模型漂移",
        "audit": "Agent 改动审计",
        "history": "历史",
        "prompt": "提示词",
        "run_guard": "运行守护",
        "selected_run": "选择 run",
        "missing_run": "没有找到 run 目录。",
        "empty_run": "这个 run 没有识别到 artifact。",
        "decision": "决策",
        "risk": "风险",
        "review": "需要人工复核",
        "categories": "风险类别",
        "violations": "策略违规",
        "token_cost": "估算 token 成本",
        "diff": "Prompt 差异",
        "recommendation": "部署建议",
        "gate": "门禁状态",
        "candidate_score": "候选分数",
        "mean_delta": "均值差异",
        "p_value": "p-value",
        "model_provenance": "模型来源",
        "drift_risk": "漂移风险",
        "audit_review": "需要人工复核",
        "dangerous_paths": "危险路径",
        "changed_files": "改动文件",
        "profile": "场景",
        "mode": "模式",
        "token_mode": "Token 模式",
        "max_tokens": "最大 Token",
        "guarded_prompt": "守护后的提示词",
        "risk_chart": "风险类别",
        "count": "数量",
        "category": "类别",
        "none": "无",
        "score_ci": "分数差异置信区间",
        "slice_scores": "任务切片分数",
        "baseline": "基线",
        "candidate": "候选",
        "model_timeline": "模型时间线",
        "no_model": "没有记录模型来源。",
        "no_audit": "没有找到 audit_result.json。",
        "public_api": "公共 API",
        "tests_passed": "测试通过",
        "file_breakdown": "改动文件类型",
        "file_kind": "类型",
        "source_files": "源码",
        "test_files": "测试",
        "docs_files": "文档",
        "config_files": "配置",
        "path": "路径",
        "no_history": "没有找到 history_index.json。",
        "run_timeline": "Run 时间线",
        "gate_trend": "门禁趋势",
        "score_trend": "分数趋势",
        "prompt_identity": "Prompt 身份",
        "risk_categories": "风险类别",
    },
}


def main() -> None:
    """Run the Streamlit dashboard."""

    st = _streamlit()
    st.set_page_config(page_title="prompt_control_lab", layout="wide")
    query = _query_params(st)
    language = _sidebar_language(st, query)
    text = TEXT[language]
    runs_dir = Path(str(st.sidebar.text_input(text["runs"], os.environ.get("PCL_UI_RUNS", "runs"))))
    default_policy = os.environ.get("PCL_UI_POLICY", "")
    policy_raw = st.sidebar.text_input(text["policy"], default_policy)
    policy_path = Path(policy_raw) if policy_raw else None
    st.title(text["title"])
    st.caption(text["subtitle"])

    runs = list_runs(runs_dir)
    detail = _select_run(st, runs, text)
    views = _ordered_views(str(query.get("view", "guard")))
    tabs = st.tabs([text[name] for name in views])
    for tab, name in zip(tabs, views, strict=True):
        with tab:
            _render_view(st, name, text, language, policy_path, detail, query)


def _render_view(
    st: Any,
    name: str,
    text: dict[str, str],
    language: str,
    policy_path: Path | None,
    detail: JsonDict,
    query: JsonDict,
) -> None:
    if name == "guard":
        _render_guard_tab(st, text, language, policy_path, _truthy(query.get("demo")))
    elif name == "report":
        _render_report_tab(st, text, detail)
    elif name == "drift":
        _render_model_drift_tab(st, text, detail)
    elif name == "audit":
        _render_audit_tab(st, text, detail)
    elif name == "history":
        _render_history_tab(st, text, detail)


def _sidebar_language(st: Any, query: JsonDict) -> str:
    default = str(query.get("lang") or os.environ.get("PCL_UI_LANGUAGE", "en"))
    selected = st.sidebar.selectbox(
        "Language / 语言",
        ["English", "中文"],
        index=0 if default == "en" else 1,
    )
    return "zh" if selected == "中文" else "en"


def _query_params(st: Any) -> JsonDict:
    try:
        raw = st.query_params
    except Exception:
        return {}
    if hasattr(raw, "to_dict"):
        raw = raw.to_dict()
    if not isinstance(raw, dict):
        return {}
    return {str(key): _first_query_value(value) for key, value in raw.items()}


def _first_query_value(value: object) -> str:
    if isinstance(value, list) and value:
        return str(value[0])
    return str(value)


def _truthy(value: object) -> bool:
    return str(value).lower() in {"1", "true", "yes", "on"}


def _ordered_views(first: str) -> list[str]:
    views = ["guard", "report", "drift", "audit", "history"]
    if first not in views:
        return views
    return [first, *[view for view in views if view != first]]


def _select_run(st: Any, runs: list[JsonDict], text: dict[str, str]) -> JsonDict:
    if not runs:
        empty_state(
            st,
            text["missing_run"],
            "pcl init --path demo && "
            "pcl analyze --config promptcontrol.example.yaml --out runs/quick",
        )
        return {"has_artifacts": False, "empty_state": text["missing_run"], "name": ""}
    names = [str(item["name"]) for item in runs]
    selected = st.sidebar.selectbox(text["selected_run"], names)
    match = next(item for item in runs if item["name"] == selected)
    return load_run_detail(Path(str(match["path"])))


def _render_guard_tab(
    st: Any,
    text: dict[str, str],
    language: str,
    policy_path: Path | None,
    run_demo: bool = False,
) -> None:
    prompt = st.text_area(
        text["prompt"],
        "Fix this bug in auth/session.py and run tests.",
        height=140,
    )
    columns = st.columns(4)
    profile = columns[0].selectbox(text["profile"], ["coding", "general", "research"])
    mode = columns[1].selectbox(text["mode"], ["suggest", "auto", "gate"])
    token_mode = columns[2].selectbox(text["token_mode"], ["balanced", "aggressive"])
    max_tokens_raw = columns[3].number_input(text["max_tokens"], min_value=0, value=0)
    max_tokens = int(max_tokens_raw) if max_tokens_raw else None
    if st.button(text["run_guard"], type="primary") or run_demo:
        result = guard_prompt(
            prompt,
            context=load_prompt_context(None),
            mode=str(mode),
            profile=str(profile),
            token_mode=str(token_mode),
            max_tokens=max_tokens,
            language=language,
            policy_path=policy_path,
        ).to_json()
        metric_cards(
            st,
            [
                (text["decision"], result.get("action")),
                (text["risk"], result.get("risk_level")),
                (text["review"], result.get("required_review")),
            ],
        )
        st.markdown(badge(text["categories"], ", ".join(_strings(result.get("risk_categories")))))
        st.markdown(badge(text["violations"], len(_list(result.get("policy_violations")))))
        categories = _category_count(_strings(result.get("risk_categories")))
        st.plotly_chart(
            risk_category_bar(
                categories,
                title=text["risk_chart"],
                category_label=text["category"],
                count_label=text["count"],
                none_label=text["none"],
            ),
            use_container_width=True,
        )
        st.subheader(text["token_cost"])
        st.json(result.get("token_report", {}))
        st.subheader(text["diff"])
        st.code(prompt_diff(prompt, str(result.get("improved_prompt", ""))), language="diff")
        st.text_area(text["guarded_prompt"], str(result.get("improved_prompt", "")), height=180)


def _render_report_tab(st: Any, text: dict[str, str], detail: JsonDict) -> None:
    if not detail.get("has_artifacts"):
        empty_state(st, text["empty_run"], str(detail.get("empty_state", "")))
        return
    explanation = _dict(detail.get("explanation"))
    gate = _dict(detail.get("gate"))
    stats = _dict(detail.get("stats"))
    metric_cards(
        st,
        [
            (
                text["recommendation"],
                _recommendation_label(explanation.get("deployment_recommendation")),
            ),
            (text["gate"], gate.get("status", "-")),
            (text["candidate_score"], detail.get("candidate_score")),
        ],
    )
    metric_cards(
        st,
        [
            (text["mean_delta"], stats.get("mean_delta")),
            (text["p_value"], stats.get("permutation_p_value")),
        ],
    )
    if stats:
        st.plotly_chart(
            score_delta_ci(stats, title=text["score_ci"], mean_label=text["mean_delta"]),
            use_container_width=True,
        )
    rows = slice_rows(detail)
    if rows:
        st.plotly_chart(
            slice_score_heatmap(
                rows,
                title=text["slice_scores"],
                baseline_label=text["baseline"],
                candidate_label=text["candidate"],
            ),
            use_container_width=True,
        )
        st.dataframe(rows, use_container_width=True)
    st.subheader(text["model_provenance"])
    rows = model_rows(detail)
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.info(text["no_model"])


def _render_model_drift_tab(st: Any, text: dict[str, str], detail: JsonDict) -> None:
    if not detail.get("has_artifacts"):
        empty_state(st, text["empty_run"], str(detail.get("empty_state", "")))
        return
    drift = _dict(detail.get("model_drift"))
    rows = model_rows(detail)
    metric_cards(st, [(text["drift_risk"], drift.get("risk", "unknown"))])
    if drift:
        st.json(drift)
    else:
        st.code(
            "pcl model-drift --run runs/current --history runs/previous "
            "--out runs/current/model_drift.json",
            language="bash",
        )
    if rows:
        st.dataframe(rows, use_container_width=True)
    history = _dict(detail.get("history_index"))
    runs = history.get("runs")
    if isinstance(runs, list) and runs:
        st.subheader(text["model_timeline"])
        st.dataframe(_history_model_rows(runs), use_container_width=True)


def _render_audit_tab(st: Any, text: dict[str, str], detail: JsonDict) -> None:
    audit = _dict(detail.get("audit"))
    if not audit:
        empty_state(
            st,
            text["no_audit"],
            "pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit",
        )
        return
    metric_cards(
        st,
        [
            (text["changed_files"], audit.get("touched_files")),
            (text["audit_review"], audit.get("human_review_required")),
            (text["public_api"], audit.get("public_api_changed")),
            (text["tests_passed"], audit.get("tests_passed")),
        ],
    )
    st.plotly_chart(
        file_breakdown_bar(
            audit,
            title=text["file_breakdown"],
            kind_label=text["file_kind"],
            count_label=text["count"],
            source_label=text["source_files"],
            tests_label=text["test_files"],
            docs_label=text["docs_files"],
            config_label=text["config_files"],
        ),
        use_container_width=True,
    )
    dangerous = _strings(audit.get("dangerous_paths"))
    if dangerous:
        st.error(text["dangerous_paths"])
        st.dataframe([{text["path"]: path} for path in dangerous], use_container_width=True)
    changed = _strings(audit.get("changed_files"))
    if changed:
        st.dataframe([{text["path"]: path} for path in changed], use_container_width=True)


def _render_history_tab(st: Any, text: dict[str, str], detail: JsonDict) -> None:
    history = _dict(detail.get("history_index"))
    runs = history.get("runs")
    if not isinstance(runs, list) or not runs:
        empty_state(
            st,
            text["no_history"],
            "pcl history index --runs runs/ --out runs/history_index.json",
        )
        return
    rows = [_history_row(item) for item in runs if isinstance(item, dict)]
    st.subheader(text["run_timeline"])
    st.dataframe(rows, use_container_width=True)
    gate_counts = _category_count([str(row.get("gate_status", "unknown")) for row in rows])
    st.plotly_chart(
        risk_category_bar(
            gate_counts,
            title=text["gate_trend"],
            category_label=text["gate"],
            count_label=text["count"],
            none_label=text["none"],
        ),
        use_container_width=True,
    )
    risk_counts: dict[str, int] = {}
    for row in rows:
        for category in _strings(row.get("risk_categories")):
            risk_counts[category] = risk_counts.get(category, 0) + 1
    st.plotly_chart(
        risk_category_bar(
            risk_counts,
            title=text["risk_categories"],
            category_label=text["category"],
            count_label=text["count"],
            none_label=text["none"],
        ),
        use_container_width=True,
    )


def _history_row(item: JsonDict) -> JsonDict:
    model = _dict(item.get("model"))
    prompt = _dict(item.get("prompt_identity"))
    return {
        "run": item.get("run_name"),
        "gate_status": item.get("gate_status"),
        "mean_score": item.get("mean_score"),
        "provider": model.get("provider"),
        "model": model.get("model_id"),
        "prompt_hash": prompt.get("prompt_hash"),
        "risk_categories": item.get("risk_categories", []),
    }


def _history_model_rows(runs: list[object]) -> list[JsonDict]:
    rows: list[JsonDict] = []
    for item in runs:
        if not isinstance(item, dict):
            continue
        rows.append(_history_row(item))
    return rows


def _streamlit() -> Any:
    return cast(Any, importlib.import_module("streamlit"))


def _dict(value: object) -> JsonDict:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _strings(value: object) -> list[str]:
    return [str(item) for item in _list(value)]


def _category_count(items: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return counts


def _recommendation_label(value: object) -> object:
    if isinstance(value, dict):
        return value.get("label") or value.get("recommendation") or value.get("verdict")
    return value


if __name__ == "__main__":
    main()
