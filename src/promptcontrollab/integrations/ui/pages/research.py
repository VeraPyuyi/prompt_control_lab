"""Research, evidence, ecosystem, and tool-choice dashboard pages."""
# ruff: noqa: E501,RUF001

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from promptcontrollab.core.files import JsonDict
from promptcontrollab.integrations.ui.charts import research_diagnostic_bar
from promptcontrollab.integrations.ui.components import (
    badge,
    empty_state,
    evidence_ladder_html,
    metric_cards,
    paper_card_html,
    research_evidence_map_html,
    stat_card_html,
)
from promptcontrollab.integrations.ui.data import (
    claim_check_summary,
    claim_evidence_ladder,
    ecosystem_demo_rows,
    ecosystem_evidence_matrix_rows,
    ecosystem_market_map_rows,
    ecosystem_market_readiness,
    ecosystem_scorecard_rows,
    evidence_card_rows,
    evidence_gap_action_rows,
    evidence_gap_rows,
    evidence_gate_rows,
    evidence_gate_summary,
    external_bridge_summary,
    peoc_limitation_rows,
    peoc_method_rows,
    peoc_status_summary,
    peoc_trajectory_rows,
    prompt_asset_rows,
    prompt_asset_summary,
    prompt_optimizer_gap_rows,
    research_at_a_glance_rows,
    research_diagnostic_rows,
    research_evidence_map,
    research_gap_plan_rows,
    research_gap_script_rows,
    research_gap_status_rows,
    research_insight_rows,
    research_overview_path,
    research_status_counts,
    scaffold_check_action_rows,
    scaffold_check_issue_rows,
    scaffold_check_summary,
)
from promptcontrollab.integrations.ui.navigation import adoption_path_rows
from promptcontrollab.integrations.ui.pages.tutorial import _render_svg
from promptcontrollab.integrations.ui.shared import _strings
from promptcontrollab.preflight.tool_choice import (
    choose_tool_for_need,
    market_gap_action_rows,
    render_tool_choice_markdown,
)


def _render_peoc_evidence_section(
    st: Any,
    text: dict[str, str],
    detail: JsonDict,
    language: str,
) -> bool:
    """Render imported PEOC evidence without treating it as a fresh run."""

    summary = peoc_status_summary(detail, language)
    if not summary.get("has_real_evidence"):
        return False

    st.markdown(
        f'<div class="pcl-section-title">{html.escape(text["peoc_real_title"])}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(badge(text["peoc_real_badge"], "verified import"))
    manifest_hash = str(summary.get("manifest_sha256") or "unknown")
    st.caption(f'{text["peoc_manifest"]}: {manifest_hash}')
    st.info(text["peoc_imported_note"])

    metric_cards(
        st,
        [
            (text["peoc_available"], summary.get("available", 0)),
            (text["peoc_partial"], summary.get("partial", 0)),
            (text["peoc_failed"], summary.get("failed_validation", 0)),
            (text["peoc_unusable"], summary.get("unusable", 0)),
            (text["peoc_missing"], summary.get("missing", 0)),
        ],
    )
    claim = claim_check_summary(detail)
    evidence = detail.get("evidence_card")
    evidence_dict = evidence if isinstance(evidence, dict) else {}
    full_support = summary.get("full_research_support") is True
    metric_cards(
        st,
        [
            (
                text["peoc_full_support"],
                text["peoc_yes"] if full_support else text["peoc_no"],
            ),
            (text["peoc_claim_scope"], claim.get("status") or summary.get("claim_status")),
            (
                text["peoc_recommendation"],
                evidence_dict.get("recommendation") or summary.get("claim_status"),
            ),
        ],
    )
    statement = str(summary.get("statement") or "")
    if full_support:
        st.info(statement)
    else:
        st.warning(statement)

    method_rows = peoc_method_rows(detail)
    if method_rows:
        st.markdown(
            f'<div class="pcl-section-title">{html.escape(text["peoc_hard_methods"])}</div>',
            unsafe_allow_html=True,
        )
        st.caption(_peoc_hard_methods_note(text["peoc_hard_methods_note"], method_rows))
        _peoc_table_clearance(st)
        st.dataframe(
            _peoc_table_rows(method_rows, "methods", language),
            use_container_width=True,
        )

    trajectory_rows = peoc_trajectory_rows(detail)
    if trajectory_rows:
        st.markdown(
            f'<div class="pcl-section-title">{html.escape(text["peoc_trajectory"])}</div>',
            unsafe_allow_html=True,
        )
        st.caption(text["peoc_trajectory_note"])
        _peoc_table_clearance(st)
        st.dataframe(
            _peoc_table_rows(trajectory_rows, "trajectory", language),
            use_container_width=True,
        )

    stage = _peoc_stage_validation(detail)
    if stage:
        st.markdown(
            f'<div class="pcl-section-title">{html.escape(text["peoc_stage_validation"])}</div>',
            unsafe_allow_html=True,
        )
        if str(stage.get("status")) == "failed_validation" or str(
            stage.get("verdict")
        ).upper() == "FAIL":
            st.warning(text["peoc_stage_failed"])
        st.dataframe(
            _peoc_table_rows([stage], "stage", language),
            use_container_width=True,
        )

    limitation_rows = peoc_limitation_rows(detail, language)
    if limitation_rows:
        st.markdown(
            f'<div class="pcl-section-title">{html.escape(text["peoc_limitations"])}</div>',
            unsafe_allow_html=True,
        )
        st.dataframe(
            _peoc_table_rows(limitation_rows, "limitations", language),
            use_container_width=True,
        )

    run_path = detail.get("path")
    if isinstance(run_path, str) and run_path:
        report_path = (Path(run_path) / "research_case_study.html").resolve()
        if report_path.exists():
            st.markdown(
                f'<div class="pcl-section-title">{html.escape(text["peoc_report"])}</div>',
                unsafe_allow_html=True,
            )
            st.caption(text["peoc_report_guidance"])
            st.markdown(f'[{text["peoc_report"]}]({report_path.as_uri()})')
            st.code(str(report_path))
    return True


def _peoc_stage_validation(detail: JsonDict) -> JsonDict:
    """Normalize peoc stage validation values for the dashboard."""
    evidence = detail.get("peoc_evidence")
    evidence_dict = evidence if isinstance(evidence, dict) else {}
    stage_dict: JsonDict = {}
    if evidence_dict:
        sections = evidence_dict.get("sections")
        sections_dict = sections if isinstance(sections, dict) else {}
        stage = sections_dict.get("stage_heterogeneity")
        stage_dict = stage if isinstance(stage, dict) else {}
    else:
        case = detail.get("peoc_case_study")
        case_dict = case if isinstance(case, dict) else {}
        stage = case_dict.get("stage_validation")
        stage_dict = stage if isinstance(stage, dict) else {}
    if not stage_dict:
        return {}
    observations = stage_dict.get("observations")
    observations_dict = observations if isinstance(observations, dict) else {}
    data = observations_dict.get("data")
    data_dict = data if isinstance(data, dict) else {}
    result: JsonDict = {
        "status": stage_dict.get("status") or "unknown",
        "verdict": _first_not_none(
            stage_dict.get("verdict"),
            observations_dict.get("verdict"),
            data_dict.get("verdict"),
            "unknown",
        ),
        "held_spearman_rho": _first_not_none(
            stage_dict.get("held_spearman_rho"),
            observations_dict.get("held_spearman_rho"),
            data_dict.get("held_spearman_rho"),
        ),
        "held_bootstrap_ci": _first_not_none(
            stage_dict.get("held_bootstrap_ci"),
            observations_dict.get("held_bootstrap_ci"),
            data_dict.get("held_bootstrap_ci"),
        ),
        "n_calib": _first_not_none(
            stage_dict.get("n_calib"),
            observations_dict.get("n_calib"),
            data_dict.get("n_calib"),
        ),
        "n_held": _first_not_none(
            stage_dict.get("n_held"),
            observations_dict.get("n_held"),
            data_dict.get("n_held"),
        ),
    }
    return {key: value for key, value in result.items() if value is not None}


def _peoc_hard_methods_note(template: str, rows: list[JsonDict]) -> str:
    """Normalize peoc hard methods note values for the dashboard."""
    return template.format(
        row_count=len(rows),
        model_count=len({str(row.get("model")) for row in rows if row.get("model")}),
        task_count=len({str(row.get("task")) for row in rows if row.get("task")}),
        method_count=len({str(row.get("method")) for row in rows if row.get("method")}),
    )


def _first_not_none(*values: object) -> object:
    """Normalize first not none values for the dashboard."""
    return next((value for value in values if value is not None), None)


def _peoc_table_clearance(st: Any) -> None:
    """Normalize peoc table clearance values for the dashboard."""
    st.markdown(
        "<style>"
        ".pcl-table-clearance{height:4px;}"
        "@media(max-width:640px){.pcl-table-clearance{height:48px;}}"
        "</style><div class=\"pcl-table-clearance\"></div>",
        unsafe_allow_html=True,
    )


def _peoc_table_rows(rows: list[JsonDict], kind: str, language: str) -> list[JsonDict]:
    """Normalize peoc table rows values for the dashboard."""
    labels: dict[str, dict[str, str]] = {
        "methods": {
            "model": "模型" if language == "zh" else "Model",
            "task": "任务" if language == "zh" else "Task",
            "method": "方法" if language == "zh" else "Method",
            "n": "样本数" if language == "zh" else "N",
            "mean": "平均准确率" if language == "zh" else "Mean accuracy",
            "sd": "标准差" if language == "zh" else "SD",
            "budget": "预算" if language == "zh" else "Budget",
            "T": "T",
            "L0": "L0",
        },
        "trajectory": {
            "lane": "任务类型" if language == "zh" else "Lane",
            "model": "模型" if language == "zh" else "Model",
            "seed": "随机种子" if language == "zh" else "Seed",
            "alpha_emp_mean": "经验衰减率" if language == "zh" else "Empirical decay",
            "R2_mean": "平均 R²" if language == "zh" else "Mean R²",
            "hidden_dim": "隐藏维度" if language == "zh" else "Hidden dimension",
            "samples": "轨迹数" if language == "zh" else "Traces",
            "source": "来源" if language == "zh" else "Source",
        },
        "stage": {
            "status": "状态" if language == "zh" else "Status",
            "verdict": "结论" if language == "zh" else "Verdict",
            "held_spearman_rho": "留出集 Spearman rho" if language == "zh" else "Held Spearman rho",
            "held_bootstrap_ci": "留出集 bootstrap CI" if language == "zh" else "Held bootstrap CI",
            "n_calib": "校准单元数" if language == "zh" else "Calibration cells",
            "n_held": "留出单元数" if language == "zh" else "Held cells",
        },
        "limitations": {
            "section": "研究部分" if language == "zh" else "Section",
            "status": "状态" if language == "zh" else "Status",
            "origin": "证据来源" if language == "zh" else "Origin",
            "limitation": "为什么不能支持结论" if language == "zh" else "Why it cannot support the claim",
        },
    }
    selected = labels.get(kind, {})
    return [
        {selected.get(key, key): value for key, value in row.items()}
        for row in rows
    ]


def _render_research_overview_tab(
    st: Any,
    text: dict[str, str],
    detail: JsonDict,
    language: str,
) -> None:
    """Render research overview tab content without changing dashboard state."""
    st.markdown(f'<div class="pcl-section-title">{html.escape(text["research_title"])}</div>', unsafe_allow_html=True)
    st.caption(text["research_subtitle"])
    _render_peoc_evidence_section(st, text, detail, language)
    _render_tool_choice_advisor(st, text, language)

    diagnostics = detail.get("diagnostics")
    has_diagnostics = isinstance(diagnostics, dict) and bool(diagnostics)
    if not detail.get("has_artifacts") and not has_diagnostics:
        empty_state(st, text["research_empty"], text["research_demo_command"])
        return

    rows = research_diagnostic_rows(detail, language)
    counts = research_status_counts(detail)
    available = counts.get("available", 0)
    artifacts = detail.get("artifacts")
    artifact_count = len(artifacts) if isinstance(artifacts, list) else 0
    protocol_ready = "yes" if detail.get("splits") or detail.get("manifest") else "partial"
    stats_ready = "yes" if detail.get("first_comparison") or detail.get("stats") else "missing"
    evidence_card = detail.get("evidence_card")
    evidence_dict = evidence_card if isinstance(evidence_card, dict) else {}
    evidence_recommendation = evidence_dict.get("recommendation", "missing")
    evidence_gate = evidence_gate_summary(detail)
    evidence_gate_status = evidence_gate.get("status", "missing")
    claim_check = claim_check_summary(detail)
    claim_status = claim_check.get("status", "missing")
    claim_ladder = claim_evidence_ladder(detail)
    bridge = external_bridge_summary(detail)
    scorecard_rows = ecosystem_scorecard_rows(detail)
    scorecard_matrix_rows = ecosystem_evidence_matrix_rows(detail)
    scorecard_market_rows = ecosystem_market_map_rows(detail)
    scorecard_market_readiness = ecosystem_market_readiness(detail)
    ecosystem_rows = ecosystem_demo_rows(detail)
    asset_summary = prompt_asset_summary(detail)
    asset_rows = prompt_asset_rows(detail)
    asset_gap_rows = prompt_optimizer_gap_rows(detail)
    scaffold_summary = scaffold_check_summary(detail)
    scaffold_issue_rows = scaffold_check_issue_rows(detail)
    scaffold_action_rows = scaffold_check_action_rows(detail)
    gap_rows = evidence_gap_rows(detail)
    gap_action_rows = evidence_gap_action_rows(detail)
    gap_plan_rows = research_gap_plan_rows(detail)
    gap_script_rows = research_gap_script_rows(detail)
    gap_status_rows = research_gap_status_rows(detail)
    evidence_map = research_evidence_map(detail)

    st.markdown(
        '<div class="pcl-grid">'
        + stat_card_html(text["paper_protocol"], protocol_ready, text["tri_split"])
        + stat_card_html(
            text["diagnostic_coverage"],
            f"{available}/{len(rows)}",
            text["research_diagnostics"],
        )
        + stat_card_html(text["artifact_evidence"], artifact_count, "JSON / HTML / Markdown")
        + stat_card_html(text["paired_stats"], stats_ready, "bootstrap CI / p-value")
        + stat_card_html(
            text["evidence_recommendation"],
            evidence_recommendation,
            text["evidence_card"],
        )
        + stat_card_html(
            text["evidence_gate_status"],
            str(evidence_gate_status),
            text["evidence_gate_required"],
        )
        + stat_card_html(
            text["claim_check_status"],
            str(claim_status),
            str(claim_check.get("requested_claim") or text["claim_check"]),
        )
        + stat_card_html(
            text["ecosystem_bridge"],
            str(bridge.get("tool") or "none"),
            f"{bridge.get('pcl_added_count', 0)} {text['pcl_added_evidence']}",
        )
        + stat_card_html(
            text["prompt_assets"],
            str(asset_summary.get("asset_count", 0) if asset_summary else 0),
            str(asset_summary.get("evaluation_status") or text["prompt_assets_missing"]),
        )
        + "</div>",
        unsafe_allow_html=True,
    )
    glance_rows = research_at_a_glance_rows(detail, language)
    if glance_rows:
        st.markdown(
            f'<div class="pcl-section-title">{html.escape(text["research_at_a_glance"])}</div>',
            unsafe_allow_html=True,
        )
        st.dataframe(glance_rows, use_container_width=True)
    overview_path = research_overview_path(detail)
    if overview_path is not None:
        st.markdown(
            f'<div class="pcl-section-title">{html.escape(text["research_overview_graphic"])}</div>',
            unsafe_allow_html=True,
        )
        _render_svg(st, overview_path)
    insight_rows = research_insight_rows(detail, language)
    if insight_rows:
        st.markdown(
            f'<div class="pcl-section-title">{html.escape(text["research_insights"])}</div>',
            unsafe_allow_html=True,
        )
        st.dataframe(
            _research_insight_display_rows(insight_rows, language),
            use_container_width=True,
        )
    map_html = research_evidence_map_html(evidence_map)
    if map_html:
        st.markdown(
            f'<div class="pcl-section-title">{html.escape(text["research_evidence_map"])}</div>'
            + map_html,
            unsafe_allow_html=True,
        )
    _render_research_pipeline(st, text)

    if scorecard_rows:
        st.markdown(
            f'<div class="pcl-section-title">{html.escape(text["ecosystem_scorecard"])}</div>',
            unsafe_allow_html=True,
        )
        scorecard = detail.get("ecosystem_scorecard")
        scorecard_dict = scorecard if isinstance(scorecard, dict) else {}
        st.caption(str(scorecard_dict.get("positioning", "")))
        if scorecard_matrix_rows:
            st.markdown(
                f'<div class="pcl-section-title">{html.escape(text["ecosystem_evidence_matrix"])}</div>',
                unsafe_allow_html=True,
            )
            st.dataframe(scorecard_matrix_rows, use_container_width=True)
        if scorecard_market_readiness:
            st.markdown(
                f'<div class="pcl-section-title">{html.escape(text["ecosystem_market_readiness"])}</div>',
                unsafe_allow_html=True,
            )
            st.caption(text["ecosystem_market_readiness_note"])
            _render_market_readiness_summary(st, scorecard_market_readiness, language)
        if scorecard_market_rows:
            st.markdown(
                f'<div class="pcl-section-title">{html.escape(text["ecosystem_market_map"])}</div>',
                unsafe_allow_html=True,
            )
            st.caption(text["ecosystem_market_map_note"])
            st.dataframe(
                _market_map_display_rows(scorecard_market_rows, language),
                use_container_width=True,
            )
        st.dataframe(scorecard_rows, use_container_width=True)

    if ecosystem_rows:
        st.markdown(
            f'<div class="pcl-section-title">{html.escape(text["ecosystem_demo"])}</div>',
            unsafe_allow_html=True,
        )
        st.dataframe(ecosystem_rows, use_container_width=True)

    if asset_rows:
        st.markdown(
            f'<div class="pcl-section-title">{html.escape(text["prompt_assets"])}</div>',
            unsafe_allow_html=True,
        )
        st.caption(str(asset_summary.get("boundary", "")))
        metric_cards(
            st,
            [
                (
                    text["prompt_assets_summary"],
                    str(asset_summary.get("asset_count", 0)),
                ),
                (
                    text["evidence_summary"],
                    str(asset_summary.get("evaluation_status", "")),
                ),
            ],
        )
        source_tool = str(asset_summary.get("source_tool", ""))
        source_sha = str(asset_summary.get("source_sha256", ""))
        if source_tool or source_sha:
            st.caption(f"{source_tool} {source_sha[:24]}".strip())
        st.dataframe(asset_rows, use_container_width=True)
        if asset_gap_rows:
            st.markdown(
                f'<div class="pcl-section-title">{html.escape(text["prompt_assets_gap_plan"])}</div>',
                unsafe_allow_html=True,
            )
            st.dataframe(asset_gap_rows, use_container_width=True)
        st.markdown(
            f'<div class="pcl-section-title">{html.escape(text["scaffold_check"])}</div>',
            unsafe_allow_html=True,
        )
        if scaffold_summary:
            st.caption(str(scaffold_summary.get("boundary", "")))
            metric_cards(
                st,
                [
                    (text["scaffold_status"], str(scaffold_summary.get("status", ""))),
                    (text["scaffold_issues"], str(scaffold_summary.get("issue_count", 0))),
                    ("tasks", str(scaffold_summary.get("task_count", 0))),
                    ("prompts", str(scaffold_summary.get("prompt_file_count", 0))),
                ],
            )
            if scaffold_issue_rows:
                st.dataframe(scaffold_issue_rows, use_container_width=True)
            if scaffold_action_rows:
                st.markdown(
                    f'<div class="pcl-section-title">{html.escape(text["scaffold_next_actions"])}</div>',
                    unsafe_allow_html=True,
                )
                st.dataframe(scaffold_action_rows, use_container_width=True)
        else:
            empty_state(st, text["scaffold_check_missing"], text["scaffold_check_command"])

    if gap_rows:
        st.markdown(
            f'<div class="pcl-section-title">{html.escape(text["evidence_gap_diagnosis"])}</div>',
            unsafe_allow_html=True,
        )
        st.dataframe(gap_rows, use_container_width=True)
    if gap_action_rows:
        st.markdown(
            f'<div class="pcl-section-title">{html.escape(text["evidence_gap_actions"])}</div>',
            unsafe_allow_html=True,
        )
        st.dataframe(gap_action_rows, use_container_width=True)
    if gap_plan_rows:
        st.markdown(
            f'<div class="pcl-section-title">{html.escape(text["research_gap_plan"])}</div>',
            unsafe_allow_html=True,
        )
        plan = detail.get("research_gap_plan")
        plan_dict = plan if isinstance(plan, dict) else {}
        st.caption(str(plan_dict.get("boundary", "")))
        st.dataframe(gap_plan_rows, use_container_width=True)
    if gap_script_rows:
        st.markdown(
            f'<div class="pcl-section-title">{html.escape(text["research_gap_scripts"])}</div>',
            unsafe_allow_html=True,
        )
        st.dataframe(gap_script_rows, use_container_width=True)
    if gap_status_rows:
        st.markdown(
            f'<div class="pcl-section-title">{html.escape(text["research_gap_status"])}</div>',
            unsafe_allow_html=True,
        )
        status = detail.get("research_gap_status")
        status_dict = status if isinstance(status, dict) else {}
        st.caption(
            f"{status_dict.get('status', '')}: "
            f"{status_dict.get('complete_count', 0)}/{status_dict.get('action_count', 0)}"
        )
        st.dataframe(gap_status_rows, use_container_width=True)

    _render_external_bridge_section(st, text, bridge)

    st.markdown(
        f'<div class="pcl-section-title">{html.escape(text["evidence_gate"])}</div>',
        unsafe_allow_html=True,
    )
    if evidence_gate:
        st.write(f"**{text['evidence_summary']}:** {evidence_gate.get('summary', '')}")
        gate_rows = evidence_gate_rows(detail)
        if gate_rows:
            st.dataframe(gate_rows, use_container_width=True)
    else:
        empty_state(st, text["evidence_gate_missing"], text["evidence_gate_command"])

    st.markdown(
        f'<div class="pcl-section-title">{html.escape(text["evidence_card"])}</div>',
        unsafe_allow_html=True,
    )
    if evidence_dict:
        st.write(f"**{text['evidence_summary']}:** {evidence_dict.get('summary', '')}")
        evidence_rows = evidence_card_rows(detail)
        if evidence_rows:
            st.dataframe(evidence_rows, use_container_width=True)
    else:
        empty_state(st, text["evidence_card_missing"], text["evidence_card_command"])

    st.markdown(
        f'<div class="pcl-section-title">{html.escape(text["claim_check"])}</div>',
        unsafe_allow_html=True,
    )
    if claim_check:
        ladder_html = evidence_ladder_html(claim_ladder)
        if ladder_html:
            st.markdown(
                f'<div class="pcl-section-title">{html.escape(text["claim_ladder"])}</div>'
                + ladder_html,
                unsafe_allow_html=True,
            )
        claim_rows = [
            {"field": text["claim_check_requested"], "value": claim_check.get("requested_claim", "")},
            {"field": text["claim_check_status"], "value": claim_check.get("status", "")},
            {"field": text["claim_check_tier"], "value": claim_check.get("evidence_tier", "")},
            {"field": text["claim_check_safe"], "value": claim_check.get("safe_claim", "")},
            {"field": text["claim_check_reason"], "value": claim_check.get("reason", "")},
            {
                "field": text["claim_check_next_missing"],
                "value": ", ".join(str(item) for item in claim_check.get("next_tier_missing", [])),
            },
        ]
        st.dataframe(claim_rows, use_container_width=True)
    else:
        empty_state(st, text["claim_check_missing"], text["claim_check_command"])

    st.markdown(f'<div class="pcl-section-title">{html.escape(text["research_diagnostics"])}</div>', unsafe_allow_html=True)
    st.plotly_chart(
        research_diagnostic_bar(rows, title=text["research_coverage"]),
        use_container_width=True,
    )
    st.dataframe(rows, use_container_width=True)

    st.markdown(
        '<div class="pcl-grid">'
        + paper_card_html(text["soft_hard"], "soft prompt -> hard token projection risk")
        + paper_card_html(text["hidden_state_input"], "HuggingFace/local hidden-state artifact source")
        + paper_card_html(text["trajectory_diag"], "hidden-state drift, decay, and turnpike-like signal")
        + paper_card_html(text["riccati_diag"], "finite-dimensional surrogate stability check")
        + paper_card_html(text["tv_soft_diag"], "static / time-varying / shuffled / random comparison")
        + "</div>",
        unsafe_allow_html=True,
    )
    st.info(text["research_boundary"])


def _render_research_pipeline(st: Any, text: dict[str, str]) -> None:
    """Render research pipeline content without changing dashboard state."""
    steps = [
        (text["tri_split"], "train / validation / withheld"),
        (text["paired_stats"], "paired CI + permutation test"),
        (text["soft_hard"], "projection gap"),
        (text["hidden_state_input"], "HF/local states"),
        (text["trajectory_diag"], "state trajectory"),
        (text["riccati_diag"], "surrogate stability"),
        (text["tv_soft_diag"], "control lane"),
    ]
    html_steps = "".join(
        (
            '<div class="pcl-pipeline-step">'
            f"<strong>{html.escape(title)}</strong>"
            f"<span>{html.escape(caption)}</span>"
            "</div>"
        )
        for title, caption in steps
    )
    st.markdown(
        f'<div class="pcl-section-title">{html.escape(text["research_pipeline"])}</div>'
        f'<div class="pcl-pipeline">{html_steps}</div>',
        unsafe_allow_html=True,
    )


def _research_insight_display_rows(rows: list[JsonDict], language: str) -> list[JsonDict]:
    """Normalize research insight display rows values for the dashboard."""
    labels = {
        "en": {
            "diagnostic": "Diagnostic",
            "checks": "Checks",
            "result": "Result",
            "interpretation": "Interpretation",
            "next_action": "Next action",
        },
        "zh": {
            "diagnostic": "诊断",
            "checks": "检查什么",
            "result": "当前结果",
            "interpretation": "说明什么",
            "next_action": "下一步",
        },
    }
    selected = labels["zh"] if language == "zh" else labels["en"]
    ordered_keys = ["diagnostic", "checks", "result", "interpretation", "next_action"]
    return [
        {selected[key]: str(row.get(key, "")) for key in ordered_keys}
        for row in rows
    ]


def _market_map_display_rows(rows: list[JsonDict], language: str) -> list[JsonDict]:
    """Normalize market map display rows values for the dashboard."""
    labels = {
        "en": {
            "tool": "Tool",
            "strong_lane": "Strong lane",
            "pcl_should_learn": "What PCL should learn",
            "pcl_still_owns": "What PCL still owns",
            "pcl_product_move": "PCL product move",
            "priority": "Priority",
            "status": "Status",
        },
        "zh": {
            "tool": "工具",
            "strong_lane": "强项",
            "pcl_should_learn": "PCL 应该学习什么",
            "pcl_still_owns": "PCL 仍然负责什么",
            "pcl_product_move": "PCL 下一步产品动作",
            "priority": "优先级",
            "status": "状态",
        },
    }
    selected = labels["zh"] if language == "zh" else labels["en"]
    ordered_keys = [
        "tool",
        "strong_lane",
        "pcl_should_learn",
        "pcl_still_owns",
        "pcl_product_move",
        "priority",
        "status",
    ]
    return [
        {
            selected[key]: _market_map_display_value(
                tool=str(row.get("tool", "")),
                key=key,
                value=row.get(key, ""),
                language=language,
            )
            for key in ordered_keys
        }
        for row in rows
    ]


def _render_market_readiness_summary(
    st: Any,
    readiness: JsonDict,
    language: str,
) -> None:
    """Render market readiness summary content without changing dashboard state."""
    status = str(readiness.get("status") or "")
    positioning = str(readiness.get("recommended_positioning") or "")
    st.markdown(
        '<div class="pcl-grid">'
        + stat_card_html(
            "Status" if language != "zh" else "状态",
            status,
            "early signal" if language != "zh" else "早期信号",
        )
        + stat_card_html(
            "Next moves" if language != "zh" else "下一步动作",
            str(len(_market_readiness_next_move_rows(readiness, language))),
            "P1 / P2",
        )
        + "</div>",
        unsafe_allow_html=True,
    )
    if positioning:
        st.caption(positioning)
    columns = st.columns(2)
    with columns[0]:
        st.markdown("**Best first users**" if language != "zh" else "**优先用户**")
        for item in _string_items(readiness.get("best_first_users")):
            st.markdown(f"- {item}")
    with columns[1]:
        st.markdown("**Do not build**" if language != "zh" else "**暂时不要做**")
        for item in _string_items(readiness.get("do_not_build")):
            st.markdown(f"- {item}")
    next_moves = _market_readiness_next_move_rows(readiness, language)
    if next_moves:
        st.dataframe(next_moves, use_container_width=True)


def _market_readiness_next_move_rows(
    readiness: JsonDict,
    language: str,
) -> list[JsonDict]:
    """Normalize market readiness next move rows values for the dashboard."""
    labels = {
        "en": {"priority": "Priority", "tool": "Tool", "move": "Next move"},
        "zh": {"priority": "优先级", "tool": "工具", "move": "下一步动作"},
    }
    selected = labels["zh"] if language == "zh" else labels["en"]
    raw_moves = readiness.get("next_moves")
    if not isinstance(raw_moves, list):
        return []
    rows: list[JsonDict] = []
    for item in raw_moves:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                selected["priority"]: _market_map_display_value(
                    tool=str(item.get("tool", "")),
                    key="priority",
                    value=item.get("priority", ""),
                    language=language,
                ),
                selected["tool"]: str(item.get("tool", "")),
                selected["move"]: str(item.get("move", "")),
            }
        )
    return rows


def _string_items(value: object) -> list[str]:
    """Normalize string items values for the dashboard."""
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _market_map_display_value(
    *,
    tool: str,
    key: str,
    value: object,
    language: str,
) -> str:
    """Normalize market map display value values for the dashboard."""
    raw = str(value or "")
    if key == "priority":
        priority_labels = {
            "P1": {"en": "P1 - near-term", "zh": "P1 - 近期优先"},
            "P2": {"en": "P2 - next", "zh": "P2 - 下一阶段"},
            "P3": {"en": "P3 - later", "zh": "P3 - 后续观察"},
        }
        mapped_priority = priority_labels.get(raw)
        if mapped_priority:
            return mapped_priority["zh" if language == "zh" else "en"]
        return raw
    if key == "status":
        labels = {
            "positioning_only_not_imported": {
                "en": "Positioning only (not imported)",
                "zh": "定位参考 - 未导入",
            },
            "historical_sunset_reference_not_imported": {
                "en": "Historical/sunset reference (not imported)",
                "zh": "历史/已停止服务参考 - 未导入",
            },
        }
        mapped = labels.get(raw)
        if mapped:
            return mapped["zh" if language == "zh" else "en"]
        return raw
    if language != "zh" or key == "tool":
        return raw
    zh_rows = {
        "Braintrust": {
            "strong_lane": "评测数据集、实验、trace 与人工 review 工作流。",
            "pcl_should_learn": "快速实验体验和适合 reviewer 的对比页面。",
            "pcl_still_owns": "prompt 优化主张的论文诊断证据。",
            "pcl_product_move": "优化 reviewer 工作流和实验对比体验。",
        },
        "Arize Phoenix": {
            "strong_lane": "开源 observability、trace、评测和检索分析。",
            "pcl_should_learn": "trace-first 调试和丰富的本地排查视图。",
            "pcl_still_owns": "prompt-only 有效性、控制论诊断和 soft-hard 风险报告。",
            "pcl_product_move": "深化 trace / audit UI，但不扩张成完整 tracing 平台。",
        },
        "OpenAI Evals": {
            "strong_lane": "标准化评测 harness 和可复用 benchmark 定义。",
            "pcl_should_learn": "可移植 eval schema，以及清楚的任务/结果分离。",
            "pcl_still_owns": "tri-split 协议、prompt 身份和围绕 eval 输出的证据卡。",
            "pcl_product_move": "保持 import 与 scaffold 契约对 eval harness 友好。",
        },
        "Humanloop": {
            "strong_lane": "历史 prompt 管理与评测工作流参考。",
            "pcl_should_learn": "prompt 生命周期、registry 语言和 review 工作流。",
            "pcl_still_owns": "本地研究诊断和 provenance-first 导出 artifact。",
            "pcl_product_move": "保持本地 registry 语言清楚，不做托管平台膨胀。",
        },
    }
    return zh_rows.get(tool, {}).get(key, raw)


def _render_external_bridge_section(
    st: Any,
    text: dict[str, str],
    bridge: JsonDict,
) -> None:
    """Render external bridge section content without changing dashboard state."""
    st.markdown(
        f'<div class="pcl-section-title">{html.escape(text["ecosystem_bridge"])}</div>',
        unsafe_allow_html=True,
    )
    if not bridge:
        empty_state(st, text["ecosystem_bridge_missing"], "pcl evidence-from --help")
        return
    rows = [
        {"field": text["external_tools"], "value": ", ".join(_strings(bridge.get("detected_tools")))},
        {"field": text["recommendation"], "value": bridge.get("recommendation", "")},
        {"field": text["comparison_validity"], "value": bridge.get("validity", "")},
        {"field": text["claim_check_status"], "value": bridge.get("claim_check_status", "")},
        {
            "field": text["claim_check_requested"],
            "value": bridge.get("claim_check_requested_claim", ""),
        },
        {
            "field": text["pcl_added_evidence"],
            "value": ", ".join(_strings(bridge.get("pcl_added_evidence"))),
        },
        {
            "field": text["missing_evidence"],
            "value": ", ".join(_strings(bridge.get("missing_evidence"))),
        },
        {
            "field": text["bridge_next_actions"],
            "value": " | ".join(_strings(bridge.get("next_actions"))),
        },
    ]
    st.dataframe(rows, use_container_width=True)


def _render_tool_choice_advisor(st: Any, text: dict[str, str], language: str) -> None:
    """Render a small adjacent-tool advisor in the research overview."""

    st.markdown(
        f'<div class="pcl-section-title">{html.escape(text["ecosystem_choice_title"])}</div>',
        unsafe_allow_html=True,
    )
    default_need = "prompt writing" if language == "en" else "prompt 写作"
    if hasattr(st, "text_input"):
        need = str(
            st.text_input(
                text["tool_choice_need"],
                default_need,
                placeholder=text["tool_choice_placeholder"],
                key="tool-choice-need",
            )
        ).strip()
    else:
        need = default_need
    if not need:
        return
    recommendation = choose_tool_for_need(need)
    pcl_adds = (
        recommendation.get("pcl_adds_zh")
        if language == "zh"
        else recommendation.get("pcl_adds")
    ) or recommendation.get("pcl_adds", "")
    why = (
        recommendation.get("why_zh") if language == "zh" else recommendation.get("why")
    ) or recommendation.get("why", "")
    avoid = (
        recommendation.get("avoid_zh") if language == "zh" else recommendation.get("avoid")
    ) or recommendation.get("avoid", "")
    action_key = "market_gap_action_zh" if language == "zh" else "market_gap_action"
    selected_action = recommendation.get(action_key)
    selected_action = selected_action if isinstance(selected_action, dict) else {}
    use_first = _tool_choice_use_first(recommendation, language)
    matched_lane = _tool_choice_matched_lane(recommendation, language)
    st.markdown(
        '<div class="pcl-grid">'
        + stat_card_html(
            text["tool_choice_recommendation"],
            use_first,
            matched_lane,
        )
        + stat_card_html(
            "PCL",
            str(pcl_adds),
            str(recommendation.get("confidence") or ""),
        )
        + "</div>",
        unsafe_allow_html=True,
    )
    rows = [
        {"field": text["tool_choice_why"], "value": why},
        {
            "field": text["tool_choice_gap_command"],
            "value": str(selected_action.get("command") or ""),
        },
        {
            "field": text["tool_choice_gap_open"],
            "value": str(selected_action.get("open") or ""),
        },
        {"field": text["tool_choice_avoid"], "value": avoid},
    ]
    st.dataframe(rows, use_container_width=True)
    commands = recommendation.get("commands")
    command_list = [str(command) for command in commands] if isinstance(commands, list) else []
    if command_list:
        st.caption(text["tool_choice_commands"])
        st.code("\n".join(command_list), language="bash")
    st.caption(text["adoption_path_title"])
    st.dataframe(
        [
            {
                text["adoption_path_minute"]: row.get("minute", ""),
                text["adoption_path_action"]: row.get("action", ""),
                text["adoption_path_result"]: row.get("result", ""),
            }
            for row in adoption_path_rows(language)
        ],
        use_container_width=True,
    )
    gap_rows = [
        {
            text["tool_choice_gap_input"]: row.get("input", ""),
            text["tool_choice_gap_gap"]: row.get("gap", ""),
            text["tool_choice_gap_command"]: row.get("command", ""),
            text["tool_choice_gap_open"]: row.get("open", ""),
        }
        for row in market_gap_action_rows(language=language)
    ]
    if gap_rows:
        st.caption(text["tool_choice_gap_actions"])
        st.dataframe(gap_rows, use_container_width=True)
    if hasattr(st, "download_button"):
        st.download_button(
            text["tool_choice_download_json"],
            data=json.dumps(recommendation, ensure_ascii=False, indent=2, sort_keys=True),
            file_name="tool_choice.json",
            mime="application/json",
        )
        st.download_button(
            text["tool_choice_download_md"],
            data=render_tool_choice_markdown(recommendation, language=language),
            file_name="tool_choice.md",
            mime="text/markdown",
        )


def _tool_choice_use_first(recommendation: JsonDict, language: str) -> str:
    """Normalize tool choice use first values for the dashboard."""
    if language == "zh":
        return str(recommendation.get("use_first_zh") or recommendation.get("use_first") or "")
    return str(recommendation.get("use_first") or "")


def _tool_choice_matched_lane(recommendation: JsonDict, language: str) -> str:
    """Normalize tool choice matched lane values for the dashboard."""
    lane_id = str(recommendation.get("matched", "") or "")
    label = (
        str(
            recommendation.get("matched_label_zh")
            or recommendation.get("matched_label")
            or lane_id
        )
        if language == "zh"
        else str(recommendation.get("matched_label") or lane_id)
    )
    return f"{label} ({lane_id})" if lane_id and label != lane_id else label
