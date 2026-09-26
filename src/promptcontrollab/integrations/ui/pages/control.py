"""Control-loop, mechanism, stability, training, and decision pages."""
# ruff: noqa: E501

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, cast

from promptcontrollab.core.files import JsonDict
from promptcontrollab.diagnostics.presentation import (
    diagnostic_status_label,
    get_diagnostic_presentation,
)
from promptcontrollab.integrations.hf_demo import is_hf_demo
from promptcontrollab.integrations.ui.charts import (
    control_event_timeline,
    control_signal_bar,
    green_boundary_margin,
    terminal_sensitivity_decay,
)
from promptcontrollab.integrations.ui.components import (
    metric_cards,
    recommendation_card_html,
)
from promptcontrollab.integrations.ui.content import (
    CONTROL_TEXT,
    HF_DEMO_TEXT,
    INTERPRETATION_LABELS,
)
from promptcontrollab.integrations.ui.data import (
    control_certificate_interpretation_rows,
    decision_trace_interpretation_rows,
    deepseek_harness_view,
    evidence_matrix_rows,
    green_certificate_rows,
    interpretability_rows,
    posterior_certificate_metrics,
    prompt_reach_interpretation_rows,
    terminal_sensitivity_rows,
)
from promptcontrollab.integrations.ui.navigation import _truthy
from promptcontrollab.integrations.ui.pages.reporting import (
    _render_audit_tab,
    _render_guard_tab,
    _render_model_drift_tab,
    _render_report_tab,
)
from promptcontrollab.integrations.ui.pages.research import _render_research_overview_tab
from promptcontrollab.integrations.ui.pages.tutorial import _render_tutorial_tab
from promptcontrollab.integrations.ui.pages.workflows import _render_workflows_tab
from promptcontrollab.integrations.ui.shared import _dict, _list


def _render_before_view(
    st: Any,
    text: dict[str, str],
    language: str,
    policy_path: Path | None,
    detail: JsonDict,
    query: JsonDict,
    runs_dir: Path,
    overwrite: bool,
    deployment_mode: str = "local",
) -> None:
    """Render before view content without changing dashboard state."""
    control_text = CONTROL_TEXT[language]
    view = deepseek_harness_view(detail)
    identity = _dict(view.get("identity"))
    st.subheader(control_text["before_title"])
    st.caption(control_text["before_caption"])
    if not _dict(detail.get("control_run")):
        st.info(control_text["missing"])
    else:
        metric_cards(
            st,
            [
                (control_text["run_id"], identity.get("run_id")),
                (control_text["status"], identity.get("status")),
                (control_text["authorization"], identity.get("authorization")),
                (control_text["agent"], identity.get("agent")),
            ],
        )
        prompt_gates = [
            cast(JsonDict, row)
            for row in _list(view.get("gates"))
            if isinstance(row, dict) and row.get("scope") == "prompt"
        ]
        if prompt_gates:
            st.markdown(f"### {control_text['prompt_gate']}")
            st.dataframe(prompt_gates, use_container_width=True, hide_index=True)
    demo_mode = is_hf_demo(deployment_mode)
    guard_tab, tutorial_tab = st.tabs(
        [control_text["legacy_guard"], control_text["legacy_tutorial"]]
    )
    with guard_tab:
        _render_guard_tab(
            st,
            text,
            language,
            policy_path,
            runs_dir,
            _truthy(query.get("demo")),
            overwrite,
            persistence_enabled=not demo_mode,
        )
    with tutorial_tab:
        _render_tutorial_tab(st, text, language)


def _render_run_view(
    st: Any,
    text: dict[str, str],
    language: str,
    policy_path: Path | None,
    detail: JsonDict,
    runs_dir: Path,
    execution_mode: str,
    overwrite: bool,
    allow_external_outputs: bool,
    *,
    deployment_mode: str = "local",
) -> None:
    """Render run view content without changing dashboard state."""
    control_text = CONTROL_TEXT[language]
    view = deepseek_harness_view(detail)
    timeline = [cast(JsonDict, row) for row in _list(view.get("timeline")) if isinstance(row, dict)]
    st.subheader(control_text["run_title"])
    st.caption(control_text["run_caption"])
    if not timeline and not _dict(detail.get("control_run")):
        st.info(control_text["missing"])
    else:
        identity = _dict(view.get("identity"))
        metric_cards(
            st,
            [
                (control_text["run_id"], identity.get("run_id")),
                (control_text["session_id"], identity.get("session_id")),
                (control_text["status"], identity.get("status")),
                (control_text["agent"], identity.get("agent")),
            ],
        )
        if timeline:
            st.markdown(f"### {control_text['timeline']}")
            st.plotly_chart(
                control_event_timeline(timeline, title=control_text["timeline"]),
                use_container_width=True,
                config={"displayModeBar": False},
            )
            st.dataframe(timeline, use_container_width=True, hide_index=True)
        tool_gates = [
            cast(JsonDict, row)
            for row in _list(view.get("gates"))
            if isinstance(row, dict) and row.get("scope") == "tool"
        ]
        if tool_gates:
            st.markdown(f"### {control_text['tool_gates']}")
            st.dataframe(tool_gates, use_container_width=True, hide_index=True)
        provider = _dict(view.get("provider"))
        st.markdown(f"### {control_text['provider_model']}")
        metric_cards(
            st,
            [
                (control_text["provider"], provider.get("provider")),
                (control_text["requested_model"], provider.get("requested_model")),
                (control_text["observed_model"], provider.get("observed_model")),
            ],
        )
        provenance = [
            cast(JsonDict, row)
            for row in _list(provider.get("provenance"))
            if isinstance(row, dict)
        ]
        if provenance:
            st.markdown(f"#### {control_text['provenance']}")
            st.dataframe(provenance, use_container_width=True, hide_index=True)
        usage = _dict(view.get("usage"))
        st.markdown(f"### {control_text['usage']}")
        metric_cards(
            st,
            [
                (control_text["input_tokens"], usage.get("input_tokens")),
                (control_text["output_tokens"], usage.get("output_tokens")),
                (control_text["total_tokens"], usage.get("total_tokens")),
                (control_text["cached_tokens"], usage.get("cached_tokens")),
                (control_text["cost"], usage.get("cost")),
                (control_text["latency"], usage.get("latency_ms")),
            ],
        )
        repeated = [
            cast(JsonDict, row)
            for row in _list(view.get("repeated_tool_calls"))
            if isinstance(row, dict)
        ]
        if repeated:
            st.markdown(f"### {control_text['repeated_tools']}")
            st.dataframe(repeated, use_container_width=True, hide_index=True)
    if is_hf_demo(deployment_mode):
        st.info(HF_DEMO_TEXT[language]["restricted"])
    else:
        with st.expander(control_text["legacy_workflows"], expanded=False):
            _render_workflows_tab(
                st,
                text,
                language,
                policy_path,
                detail,
                runs_dir,
                execution_mode,
                overwrite,
                allow_external_outputs,
            )


def _render_why_view(st: Any, language: str, detail: JsonDict) -> None:
    """Render why view content without changing dashboard state."""
    control_text = CONTROL_TEXT[language]
    view = deepseek_harness_view(detail)
    attribution = _dict(view.get("attribution"))
    st.subheader(control_text["why_title"])
    st.caption(control_text["why_caption"])
    if not _dict(detail.get("control_run")):
        st.info(control_text["missing"])
        return
    metric_cards(
        st,
        [(control_text["attribution"], attribution.get("status"))],
    )
    if attribution.get("summary"):
        st.info(str(attribution["summary"]))
    factors = [
        cast(JsonDict, row)
        for row in _list(attribution.get("factors"))
        if isinstance(row, dict)
    ]
    if factors:
        st.dataframe(factors, use_container_width=True, hide_index=True)
    guard_signals = [
        cast(JsonDict, row)
        for row in _list(view.get("guard_signals"))
        if isinstance(row, dict)
    ]
    st.markdown(f"### {control_text['guard_signals']}")
    if guard_signals:
        st.dataframe(guard_signals, use_container_width=True, hide_index=True)
    else:
        st.caption(control_text["no_guard_signals"])
    recommendation = _dict(view.get("recommendation"))
    st.caption(str(recommendation.get("boundary") or ""))


def _render_mechanism_view(st: Any, language: str, detail: JsonDict) -> None:
    """Render mechanism view content without changing dashboard state."""
    _render_why_view(st, language, detail)
    prompt_rows = [
        row
        for row in prompt_reach_interpretation_rows(detail, language)
        if row.get("role") in {"mechanism", "boundary"}
    ]
    report_rows = [
        row
        for row in interpretability_rows(detail)
        if row.get("role") in {"mechanism", "boundary"}
    ]
    rows = _merge_interpretation_records(
        control_certificate_interpretation_rows(detail, language),
        _merge_interpretation_records(prompt_rows, report_rows),
    )
    title = "Mechanism and boundary findings" if language == "en" else "机制与适用边界"
    if rows:
        _render_interpretation_records(st, rows, language, title=title)


def _render_after_view(
    st: Any,
    text: dict[str, str],
    language: str,
    detail: JsonDict,
) -> None:
    """Render after view content without changing dashboard state."""
    control_text = CONTROL_TEXT[language]
    view = deepseek_harness_view(detail)
    stability = _dict(view.get("stability"))
    st.subheader(control_text["after_title"])
    st.caption(control_text["after_caption"])
    if not _dict(detail.get("control_run")):
        st.info(control_text["missing"])
    else:
        metric_cards(
            st,
            [
                (control_text["stability"], stability.get("state")),
                (control_text["confidence"], stability.get("confidence")),
                (control_text["observed_events"], stability.get("observed_events")),
            ],
        )
        if stability.get("summary"):
            st.info(str(stability["summary"]))
        signal_rows = [
            cast(JsonDict, row)
            for row in _list(stability.get("signal_counts"))
            if isinstance(row, dict)
        ]
        if signal_rows:
            st.plotly_chart(
                control_signal_bar(signal_rows, title=control_text["signals"]),
                use_container_width=True,
                config={"displayModeBar": False},
            )
        changes = [
            cast(JsonDict, row)
            for row in _list(view.get("changes"))
            if isinstance(row, dict)
        ]
        if changes:
            st.markdown(f"### {control_text['changes']}")
            st.dataframe(changes, use_container_width=True, hide_index=True)
    with st.expander(control_text["legacy_drift"], expanded=False):
        _render_model_drift_tab(st, text, detail)
    with st.expander(control_text["legacy_audit"], expanded=False):
        _render_audit_tab(st, text, detail)


def _render_stability_view(
    st: Any,
    text: dict[str, str],
    language: str,
    detail: JsonDict,
) -> None:
    """Render stability view content without changing dashboard state."""
    _render_after_view(st, text, language, detail)
    prompt_rows = [
        row
        for row in prompt_reach_interpretation_rows(detail, language)
        if row.get("role") in {"stability", "uncertainty"}
    ]
    report_rows = [
        row
        for row in interpretability_rows(detail)
        if row.get("role") in {"stability", "uncertainty"}
    ]
    certificate_rows = control_certificate_interpretation_rows(detail, language)
    rows = _merge_interpretation_records(
        certificate_rows,
        _merge_interpretation_records(prompt_rows, report_rows),
    )
    title = "Stability and confidence findings" if language == "en" else "稳定性与可信度"
    if rows:
        _render_interpretation_records(st, rows, language, title=title)
    terminal_rows = terminal_sensitivity_rows(detail)
    if terminal_rows:
        st.plotly_chart(
            terminal_sensitivity_decay(
                terminal_rows,
                title=(
                    "Long-horizon goal influence by boundary distance"
                    if language == "en"
                    else "最终目标影响随任务距离变化"
                ),
            ),
            use_container_width=True,
            config={"displayModeBar": False},
        )
    green_rows = green_certificate_rows(detail)
    if green_rows:
        st.plotly_chart(
            green_boundary_margin(
                green_rows,
                title=(
                    "Local stability boundary margin"
                    if language == "en"
                    else "局部稳定边界余量"
                ),
            ),
            use_container_width=True,
            config={"displayModeBar": False},
        )
    posterior = posterior_certificate_metrics(detail)
    if any(value is not None for value in posterior.values()):
        metric_cards(
            st,
            [
                (
                    "Local condition indicator" if language == "en" else "局部条件指标",
                    posterior.get("h"),
                ),
                (
                    "Confidence neighborhood radius" if language == "en" else "可信邻域半径",
                    posterior.get("existence_radius"),
                ),
                (
                    "Remaining neighborhood margin" if language == "en" else "剩余邻域余量",
                    posterior.get("neighborhood_margin"),
                ),
                (
                    "Evidence level" if language == "en" else "证据等级",
                    diagnostic_status_label(posterior.get("certificate_level"), language),
                ),
            ],
        )


def _render_training_gate_view(st: Any, language: str, detail: JsonDict) -> None:
    """Render training gate view content without changing dashboard state."""
    control_text = CONTROL_TEXT[language]
    gate = _dict(detail.get("posttrain_gate"))
    comparison = _dict(detail.get("checkpoint_comparison"))
    attribution = _dict(detail.get("mechanism_attribution"))
    trace_rows = decision_trace_interpretation_rows(detail, language)
    st.subheader(control_text["training_title"])
    st.caption(control_text["training_caption"])
    if not gate and not trace_rows:
        command = (
            "pcl posttrain-gate --baseline runs/checkpoint-000 "
            "--candidate runs/checkpoint-500 --policy examples/posttrain.policy.yaml "
            "--out runs/posttrain-gate"
        )
        st.info("No post-training gate artifact is available." if language == "en" else "当前没有后训练门禁结果。")
        st.code(command, language="bash")
        return
    paired = _dict(comparison.get("paired_statistics"))
    resources = _dict(comparison.get("resources"))
    metric_cards(
        st,
        [
            ("Decision" if language == "en" else "决策", gate.get("decision")),
            ("Score delta" if language == "en" else "分数变化", comparison.get("score_delta")),
            (
                "Paired CI" if language == "en" else "配对置信区间",
                paired.get("bootstrap_ci"),
            ),
            (
                "Token change" if language == "en" else "Token 变化",
                resources.get("token_increase_ratio"),
            ),
            (
                "Latency change" if language == "en" else "延迟变化",
                resources.get("latency_increase_ratio"),
            ),
            (
                "Missing evidence" if language == "en" else "缺失证据",
                len(_list(gate.get("missing_artifacts")))
                + len(_list(gate.get("invalid_evidence"))),
            ),
        ],
    )
    st.info(str(gate.get("plain_summary") or ""))
    certificate_summary = _dict(gate.get("certificate_summary"))
    certificate_checks = _dict(certificate_summary.get("checks"))
    if certificate_summary:
        st.markdown(
            "### Stability and confidence checks"
            if language == "en"
            else "### 稳定性与可信度检查"
        )
        metric_cards(
            st,
            [
                (
                    "Overall state" if language == "en" else "总体状态",
                    diagnostic_status_label(certificate_summary.get("overall_state"), language),
                ),
                (
                    "Highest level" if language == "en" else "最高等级",
                    diagnostic_status_label(
                        certificate_summary.get("highest_recorded_level"), language
                    ),
                ),
                (
                    "Minimum required" if language == "en" else "策略最低要求",
                    certificate_summary.get("minimum_required_level") or "not configured",
                ),
            ],
        )
        if certificate_checks:
            st.dataframe(
                [
                    {
                        "diagnostic": get_diagnostic_presentation(name, language)["label"],
                        "state": diagnostic_status_label(
                            _dict(raw).get("check_state") or _dict(raw).get("observed"),
                            language,
                        ),
                        "level": diagnostic_status_label(
                            _dict(raw).get("certificate_level"), language
                        ),
                        "passed": _dict(raw).get("passed"),
                        "message": _dict(raw).get("message"),
                    }
                    for name, raw in certificate_checks.items()
                ],
                use_container_width=True,
                hide_index=True,
            )
    checks = _dict(gate.get("checks"))
    if checks:
        st.dataframe(
            [
                {
                    "check": name,
                    "passed": _dict(raw).get("passed"),
                    "severity": _dict(raw).get("severity"),
                    "message": _dict(raw).get("message"),
                }
                for name, raw in checks.items()
            ],
            use_container_width=True,
            hide_index=True,
        )
    findings = _list(attribution.get("findings"))
    if findings:
        st.markdown("### Mechanism attribution" if language == "en" else "### 机制归因")
        st.dataframe(findings, use_container_width=True, hide_index=True)
    if trace_rows:
        _render_interpretation_records(
            st,
            trace_rows,
            language,
            title="Decision trace" if language == "en" else "决策轨迹",
        )
    st.caption(str(gate.get("claim_boundary") or ""))


def _render_decision_view(
    st: Any,
    text: dict[str, str],
    language: str,
    detail: JsonDict,
) -> None:
    """Render decision view content without changing dashboard state."""
    control_text = CONTROL_TEXT[language]
    view = deepseek_harness_view(detail)
    recommendation = _dict(view.get("recommendation"))
    reasons = [str(item) for item in _list(recommendation.get("reasons"))]
    st.subheader(control_text["decision_title"])
    st.caption(control_text["decision_caption"])
    st.markdown(
        recommendation_card_html(
            decision=str(recommendation.get("decision") or "insufficient_evidence"),
            next_action=str(recommendation.get("next_action") or ""),
            reasons=reasons,
            boundary=str(recommendation.get("boundary") or ""),
            label=control_text["recommendation"],
        ),
        unsafe_allow_html=True,
    )
    links = [
        cast(JsonDict, row)
        for row in _list(view.get("report_links"))
        if isinstance(row, dict)
    ]
    st.markdown(f"### {control_text['reports']}")
    if links:
        rendered_links = " · ".join(
            f"[{html.escape(str(row.get('name') or 'report'))}]({row.get('href')})"
            for row in links
        )
        st.markdown(rendered_links)
        st.dataframe(
            [{"report": row.get("name"), "path": row.get("path")} for row in links],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption(control_text["no_reports"])
    with st.expander(control_text["legacy_report"], expanded=False):
        _render_report_tab(st, text, detail)


def _render_advanced_view(
    st: Any,
    text: dict[str, str],
    language: str,
    detail: JsonDict,
) -> None:
    """Render advanced view content without changing dashboard state."""
    control_text = CONTROL_TEXT[language]
    st.subheader(control_text["advanced_title"])
    st.caption(control_text["advanced_caption"])
    matrix = evidence_matrix_rows(detail)
    if matrix:
        st.dataframe(matrix, use_container_width=True, hide_index=True)
    findings = _merge_interpretation_records(
        control_certificate_interpretation_rows(detail, language),
        _merge_interpretation_records(
            prompt_reach_interpretation_rows(detail, language),
            interpretability_rows(detail),
        ),
    )
    if findings:
        _render_interpretation_records(
            st,
            findings,
            language,
            title="Explanation records" if language == "en" else "可解释性记录",
        )
    with st.expander(control_text["legacy_research"], expanded=True):
        _render_research_overview_tab(st, text, detail, language)


def _render_evidence_scope_view(
    st: Any,
    text: dict[str, str],
    language: str,
    detail: JsonDict,
) -> None:
    """Render evidence scope view content without changing dashboard state."""
    _render_advanced_view(st, text, language, detail)


def _render_interpretation_records(
    st: Any,
    rows: list[JsonDict],
    language: str,
    *,
    title: str | None = None,
) -> None:
    """Render bounded diagnostic findings with one shared bilingual structure."""

    labels = INTERPRETATION_LABELS[language]
    if title:
        st.markdown(f"### {title}")
    for row in rows:
        name = str(row.get("diagnostic") or row.get("adapter") or "diagnostic")
        status = str(row.get("status_label") or row.get("status") or "unknown")
        confidence = str(row.get("confidence") or "unknown")
        st.markdown(f"#### {html.escape(name)}")
        st.markdown(
            f"**{labels['status']}:** {html.escape(status)} · "
            f"**{labels['confidence']}:** {html.escape(confidence)}"
        )
        purpose = row.get("function")
        if purpose:
            st.markdown(f"**{labels['purpose']}:** {html.escape(str(purpose))}")
        for key in ("observed", "explains", "does_not_prove", "next_action"):
            value = row.get(key)
            rendered = _interpretation_value(value)
            st.markdown(f"**{labels[key]}:** {html.escape(rendered)}")
        expander = getattr(st, "expander", None)
        if callable(expander) and row.get("technical_name"):
            with expander(labels["technical_details"], expanded=False):
                st.markdown(f"**Technical name:** {html.escape(str(row['technical_name']))}")
                st.markdown(
                    f"**Stable ID:** `{html.escape(str(row.get('adapter') or 'unknown'))}`"
                )
                st.markdown(
                    "**Certificate level:** "
                    f"{html.escape(str(row.get('certificate_level_label') or 'unknown'))}"
                )


def _merge_interpretation_records(
    primary: list[JsonDict],
    secondary: list[JsonDict],
) -> list[JsonDict]:
    """Prefer direct diagnostic artifacts and append non-duplicate report findings."""

    rows: list[JsonDict] = []
    seen: set[str] = set()
    for row in [*primary, *secondary]:
        identity = str(row.get("adapter") or row.get("dimension") or "")
        if identity and identity in seen:
            continue
        if identity:
            seen.add(identity)
        rows.append(row)
    return rows


def _interpretation_value(value: object) -> str:
    """Normalize interpretation value values for the dashboard."""
    if value is None or value == "":
        return "unknown"
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return str(value)
