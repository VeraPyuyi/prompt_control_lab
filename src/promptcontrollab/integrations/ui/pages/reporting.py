"""Guard, report, drift, audit, and history dashboard pages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from promptcontrollab.core.files import JsonDict
from promptcontrollab.integrations.ui.charts import (
    file_breakdown_bar,
    history_category_timeline,
    history_numeric_trend,
    risk_category_bar,
    score_delta_ci,
    slice_score_heatmap,
)
from promptcontrollab.integrations.ui.components import (
    badge,
    empty_state,
    metric_cards,
    prompt_diff,
)
from promptcontrollab.integrations.ui.content import HF_DEMO_TEXT
from promptcontrollab.integrations.ui.data import (
    audit_detail_sections,
    changed_line_rows,
    filter_history_rows,
    first_comparison,
    guard_download_payloads,
    history_rows,
    model_rows,
    slice_rows,
)
from promptcontrollab.integrations.ui.navigation import _choice_labels, _choice_value
from promptcontrollab.integrations.ui.shared import (
    _category_count,
    _dict,
    _list,
    _recommendation_label,
    _strings,
)
from promptcontrollab.integrations.ui.workflows import save_guard_outputs
from promptcontrollab.preflight.prompt_context import load_prompt_context
from promptcontrollab.preflight.prompt_guard import guard_prompt


def _render_guard_tab(
    st: Any,
    text: dict[str, str],
    language: str,
    policy_path: Path | None,
    runs_dir: Path,
    run_demo: bool = False,
    overwrite: bool = False,
    persistence_enabled: bool = True,
) -> None:
    """Render guard tab content without changing dashboard state."""
    prompt = st.text_area(
        text["prompt"],
        "Fix this bug in auth/session.py and run tests.",
        height=140,
    )
    columns = st.columns(4)
    profile_label = str(
        columns[0].selectbox(text["profile"], _choice_labels("profile", language))
    )
    mode_label = str(
        columns[1].selectbox(text["mode"], _choice_labels("guard_mode", language))
    )
    token_mode_label = str(
        columns[2].selectbox(text["token_mode"], _choice_labels("token_mode", language))
    )
    profile = _choice_value("profile", profile_label, language)
    mode = _choice_value("guard_mode", mode_label, language)
    token_mode = _choice_value("token_mode", token_mode_label, language)
    max_tokens_raw = columns[3].number_input(text["max_tokens"], min_value=0, value=0)
    max_tokens = int(max_tokens_raw) if max_tokens_raw else None
    if persistence_enabled:
        save_guard = bool(st.checkbox(text["save_guard"], value=False))
        save_dir = Path(
            st.text_input(
                text["save_guard_dir"],
                str(runs_dir / "guard-ui"),
                disabled=not save_guard,
            )
        )
    else:
        save_guard = False
        save_dir = runs_dir / "guard-ui"
        st.caption(HF_DEMO_TEXT[language]["guard_memory"])
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
        downloads = guard_download_payloads(result)
        download_cols = st.columns(2)
        download_cols[0].download_button(
            text["download_guard_json"],
            downloads["guard_result.json"],
            file_name="guard_result.json",
            mime="application/json",
        )
        download_cols[1].download_button(
            text["download_improved_prompt"],
            downloads["improved_prompt.txt"],
            file_name="improved_prompt.txt",
            mime="text/plain",
        )
        if save_guard:
            outputs = [
                save_dir / "guard_result.json",
                save_dir / "improved_prompt.txt",
                save_dir / "guarded_prompt.txt",
            ]
            existing = [path for path in outputs if path.exists()]
            if existing and not overwrite:
                st.warning("Output artifacts already exist; enable overwrite to replace them.")
            else:
                written = save_guard_outputs(result, out_dir=save_dir)
                st.success(f"{text['saved_guard']}: {', '.join(str(path) for path in written)}")


def _render_report_tab(st: Any, text: dict[str, str], detail: JsonDict) -> None:
    """Render report tab content without changing dashboard state."""
    if not detail.get("has_artifacts"):
        empty_state(st, text["empty_run"], str(detail.get("empty_state", "")))
        return
    explanation = _dict(detail.get("explanation"))
    gate = _dict(detail.get("gate"))
    validity = _dict(detail.get("comparison_validity"))
    comparison = _dict(detail.get("first_comparison")) or first_comparison(
        _dict(detail.get("stats"))
    )
    metric_cards(
        st,
        [
            (
                text["recommendation"],
                _recommendation_label(explanation.get("deployment_recommendation")),
            ),
            (text["gate"], gate.get("status", "-")),
            (text["candidate_score"], detail.get("candidate_score")),
            (text["comparison_validity"], validity.get("validity", "-")),
            (text["prompt_only"], validity.get("prompt_only_comparison", "-")),
        ],
    )
    metric_cards(
        st,
        [
            (text["mean_delta"], comparison.get("mean_delta")),
            (text["p_value"], comparison.get("permutation_p_value")),
        ],
    )
    if comparison:
        st.plotly_chart(
            score_delta_ci(comparison, title=text["score_ci"], mean_label=text["mean_delta"]),
            use_container_width=True,
        )
    if validity:
        issues = [
            *_list(validity.get("blocking_issues")),
            *_list(validity.get("review_items")),
        ]
        if issues:
            st.warning("\n".join(str(issue) for issue in issues))
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
    """Render model drift tab content without changing dashboard state."""
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
    """Render audit tab content without changing dashboard state."""
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
    changed_line_table = changed_line_rows(audit)
    if changed_line_table:
        st.subheader(text["changed_lines"])
        st.dataframe(changed_line_table, use_container_width=True)
    dangerous = _strings(audit.get("dangerous_paths"))
    if dangerous:
        st.error(text["dangerous_paths"])
        st.dataframe([{text["path"]: path} for path in dangerous], use_container_width=True)
    changed = _strings(audit.get("changed_files"))
    if changed:
        st.dataframe([{text["path"]: path} for path in changed], use_container_width=True)
    sections = audit_detail_sections(audit)
    detail_labels = {
        "secret_findings": text["secret_findings"],
        "dependency_files_changed": text["dependency_files"],
        "lockfiles_changed": text["lockfiles"],
        "workflow_files_changed": text["workflow_files"],
        "deleted_test_files": text["deleted_test_files"],
        "unexpected_files": text["unexpected_files"],
        "test_results": text["test_results"],
    }
    if any(sections.values()):
        st.subheader(text["audit_details"])
    for key, label in detail_labels.items():
        rows = sections.get(key, [])
        if rows:
            st.markdown(f"**{label}**")
            st.dataframe(rows, use_container_width=True)


def _render_history_tab(st: Any, text: dict[str, str], detail: JsonDict) -> None:
    """Render history tab content without changing dashboard state."""
    history = _dict(detail.get("history_index"))
    runs = history.get("runs")
    if not isinstance(runs, list) or not runs:
        empty_state(
            st,
            text["no_history"],
            "pcl history index --runs runs/ --out runs/history_index.json",
        )
        return
    rows = history_rows(detail)
    filters = st.columns(4)
    only_review_required = bool(filters[0].checkbox(text["only_review_required"], value=False))
    only_high_risk = bool(filters[1].checkbox(text["only_high_risk"], value=False))
    provider_filter = str(filters[2].text_input(text["provider_filter"], ""))
    model_filter = str(filters[3].text_input(text["model_filter"], ""))
    rows = filter_history_rows(
        rows,
        only_review_required=only_review_required,
        only_high_risk=only_high_risk,
        provider=provider_filter,
        model=model_filter,
    )
    st.subheader(text["run_timeline"])
    st.dataframe(rows, use_container_width=True)
    st.plotly_chart(
        history_numeric_trend(
            rows,
            y_key="mean_score",
            title=text["score_trend"],
            value_label=text["candidate_score"],
        ),
        use_container_width=True,
    )
    st.plotly_chart(
        history_category_timeline(
            rows,
            y_key="gate_status",
            title=text["gate_trend"],
            category_label=text["gate"],
        ),
        use_container_width=True,
    )
    st.plotly_chart(
        history_category_timeline(
            rows,
            y_key="risk_level",
            title=text["risk_trend"],
            category_label=text["risk"],
        ),
        use_container_width=True,
    )
    st.plotly_chart(
        history_category_timeline(
            rows,
            y_key="review_required",
            title=text["review_trend"],
            category_label=text["review"],
        ),
        use_container_width=True,
    )
    st.subheader(text["model_changes"])
    st.dataframe(
        [
            {
                "run": row.get("run"),
                "provider": row.get("provider"),
                "model": row.get("model"),
                "prompt_hash": row.get("prompt_hash"),
            }
            for row in rows
        ],
        use_container_width=True,
    )
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
    """Normalize history row values for the dashboard."""
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
    """Normalize history model rows values for the dashboard."""
    rows: list[JsonDict] = []
    for item in runs:
        if not isinstance(item, dict):
            continue
        rows.append(_history_row(item))
    return rows
