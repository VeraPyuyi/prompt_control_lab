"""Streamlit composition entry for the local prompt_control_lab dashboard."""
# ruff: noqa: F401

from __future__ import annotations

import html
import os
from pathlib import Path
from typing import Any

from promptcontrollab.core.files import JsonDict
from promptcontrollab.integrations.hf_demo import is_hf_demo
from promptcontrollab.integrations.ui.charts import research_diagnostic_bar
from promptcontrollab.integrations.ui.components import dashboard_css, metric_cards
from promptcontrollab.integrations.ui.content import (
    CHOICE_OPTIONS,
    CONTROL_TEXT,
    DEFAULT_PRIMARY_VIEW,
    HF_DEMO_TEXT,
    INTERPRETATION_LABELS,
    LEGACY_VIEW_ALIASES,
    LEGACY_VIEW_GROUPS,
    PRIMARY_VIEW_LABELS,
    PRIMARY_VIEW_ORDER,
    TEXT,
)
from promptcontrollab.integrations.ui.content_tutorial import (
    ONBOARDING_PATHS,
    TUTORIAL_IMAGES,
    TUTORIAL_SCREENSHOTS,
    TUTORIAL_SECTION_SCREENSHOTS,
    TUTORIAL_SECTIONS,
    TUTORIAL_STEPS,
)
from promptcontrollab.integrations.ui.data import list_runs
from promptcontrollab.integrations.ui.hf import (
    _prepare_hf_demo_session,
    _render_hf_demo_upload,
    _streamlit,
)
from promptcontrollab.integrations.ui.navigation import (
    _choice_labels,
    _choice_value,
    _hide_streamlit_chrome,
    _ordered_views,
    _query_params,
    _resolve_primary_view,
    _select_run,
    _sidebar_language,
    adoption_path_rows,
    ecosystem_choice_rows,
    legacy_sections_for,
    onboarding_paths,
    primary_view_labels,
    tutorial_gallery_items,
    tutorial_sections,
)
from promptcontrollab.integrations.ui.pages.control import (
    _render_after_view,
    _render_before_view,
    _render_decision_view,
    _render_evidence_scope_view,
    _render_interpretation_records,
    _render_mechanism_view,
    _render_run_view,
    _render_stability_view,
    _render_training_gate_view,
    _render_why_view,
)
from promptcontrollab.integrations.ui.pages.reporting import (
    _render_audit_tab,
    _render_guard_tab,
    _render_history_tab,
    _render_model_drift_tab,
    _render_report_tab,
)
from promptcontrollab.integrations.ui.pages.research import (
    _market_map_display_rows,
    _market_readiness_next_move_rows,
    _render_peoc_evidence_section,
    _render_research_overview_tab,
    _render_tool_choice_advisor,
    _research_insight_display_rows,
)
from promptcontrollab.integrations.ui.pages.tutorial import (
    _render_image,
    _render_svg,
    _render_tutorial_tab,
)
from promptcontrollab.integrations.ui.pages.workflows import _render_workflows_tab

__all__ = [
    "CHOICE_OPTIONS",
    "CONTROL_TEXT",
    "DEFAULT_PRIMARY_VIEW",
    "HF_DEMO_TEXT",
    "INTERPRETATION_LABELS",
    "LEGACY_VIEW_ALIASES",
    "LEGACY_VIEW_GROUPS",
    "ONBOARDING_PATHS",
    "PRIMARY_VIEW_LABELS",
    "PRIMARY_VIEW_ORDER",
    "TEXT",
    "TUTORIAL_IMAGES",
    "TUTORIAL_SCREENSHOTS",
    "TUTORIAL_SECTION_SCREENSHOTS",
    "TUTORIAL_SECTIONS",
    "TUTORIAL_STEPS",
    "_choice_labels",
    "_choice_value",
    "_hide_streamlit_chrome",
    "_market_map_display_rows",
    "_market_readiness_next_move_rows",
    "_ordered_views",
    "_render_before_view",
    "_render_evidence_scope_view",
    "_render_image",
    "_render_interpretation_records",
    "_render_mechanism_view",
    "_render_peoc_evidence_section",
    "_render_research_overview_tab",
    "_render_run_view",
    "_render_stability_view",
    "_render_svg",
    "_render_tool_choice_advisor",
    "_render_training_gate_view",
    "_research_insight_display_rows",
    "_resolve_primary_view",
    "adoption_path_rows",
    "ecosystem_choice_rows",
    "legacy_sections_for",
    "main",
    "onboarding_paths",
    "primary_view_labels",
    "tutorial_gallery_items",
    "tutorial_sections",
]


def main() -> None:
    """Run the Streamlit dashboard."""

    st = _streamlit()
    st.set_page_config(page_title="prompt_control_lab", layout="wide")
    _hide_streamlit_chrome(st)
    st.markdown(dashboard_css(), unsafe_allow_html=True)
    query = _query_params(st)
    language = _sidebar_language(st, query)
    text = TEXT[language]
    deployment_mode = os.environ.get("PCL_DEPLOYMENT_MODE", "local")
    if is_hf_demo(deployment_mode):
        session = _prepare_hf_demo_session(st)
        runs_dir = session.runs_dir
        default_policy = os.environ.get("PCL_UI_POLICY", "")
        policy_path = Path(default_policy) if default_policy else None
        execution_mode = "confirm"
        overwrite = False
        allow_external_outputs = False
        st.sidebar.info(HF_DEMO_TEXT[language]["mode"])
        _render_hf_demo_upload(st, session, language)
    else:
        runs_dir = Path(
            str(st.sidebar.text_input(text["runs"], os.environ.get("PCL_UI_RUNS", "runs")))
        )
        default_policy = os.environ.get("PCL_UI_POLICY", "")
        policy_raw = st.sidebar.text_input(text["policy"], default_policy)
        policy_path = Path(policy_raw) if policy_raw else None
        project_config = os.environ.get("PCL_UI_CONFIG", "")
        if project_config:
            st.sidebar.caption(f"Project config: {project_config}")
        execution_label = str(
            st.sidebar.selectbox(
                text["execution_mode"],
                _choice_labels("execution_mode", language),
                index=0,
            )
        )
        execution_mode = _choice_value("execution_mode", execution_label, language)
        overwrite = bool(st.sidebar.checkbox(text["overwrite"], value=False))
        allow_external_outputs = bool(
            st.sidebar.checkbox(text["allow_external_outputs"], value=False)
        )
    hero_subtitle = (
        HF_DEMO_TEXT[language]["subtitle"]
        if is_hf_demo(deployment_mode)
        else text["subtitle"]
    )
    st.markdown(
        (
            '<section class="pcl-hero">'
            f"<h1>{html.escape(text['title'])}</h1>"
            f"<p>{html.escape(hero_subtitle)}</p>"
            "</section>"
        ),
        unsafe_allow_html=True,
    )

    runs = list_runs(runs_dir)
    detail = _select_run(st, runs, text)
    requested_view = str(
        query.get("view") or os.environ.get("PCL_UI_DEFAULT_VIEW", DEFAULT_PRIMARY_VIEW)
    )
    default_view = _resolve_primary_view(requested_view)
    views = _ordered_views(default_view)
    labels = primary_view_labels(language)
    selected_label = str(
        st.radio(
            CONTROL_TEXT[language]["navigation"],
            labels,
            index=views.index(default_view),
            horizontal=True,
            label_visibility="collapsed",
        )
    )
    selected_view = views[labels.index(selected_label)]
    _render_view(
        st,
        selected_view,
        text,
        language,
        policy_path,
        detail,
        query,
        runs_dir,
        execution_mode,
        overwrite,
        allow_external_outputs,
        deployment_mode,
    )


def _render_view(
    st: Any,
    name: str,
    text: dict[str, str],
    language: str,
    policy_path: Path | None,
    detail: JsonDict,
    query: JsonDict,
    runs_dir: Path,
    execution_mode: str,
    overwrite: bool,
    allow_external_outputs: bool,
    deployment_mode: str = "local",
) -> None:
    """Render view content without changing dashboard state."""
    primary = _resolve_primary_view(name)
    if primary == "before":
        _render_before_view(
            st,
            text,
            language,
            policy_path,
            detail,
            query,
            runs_dir,
            overwrite,
            deployment_mode,
        )
    elif primary == "run":
        _render_run_view(
            st,
            text,
            language,
            policy_path,
            detail,
            runs_dir,
            execution_mode,
            overwrite,
            allow_external_outputs,
            deployment_mode=deployment_mode,
        )
    elif primary == "mechanism":
        _render_mechanism_view(st, language, detail)
    elif primary == "stability":
        _render_stability_view(st, text, language, detail)
    elif primary == "training":
        _render_training_gate_view(st, language, detail)
    elif primary == "evidence":
        _render_evidence_scope_view(st, text, language, detail)
    elif primary == "decision":
        _render_decision_view(st, text, language, detail)
    elif primary == "history":
        _render_history_tab(st, text, detail)


if __name__ == "__main__":
    main()
