"""Dashboard navigation, choices, and tutorial asset lookup."""
# ruff: noqa: RUF001

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from promptcontrollab.core.files import JsonDict
from promptcontrollab.integrations.ui.components import empty_state
from promptcontrollab.integrations.ui.content import (
    CHOICE_OPTIONS,
    DEFAULT_PRIMARY_VIEW,
    LEGACY_VIEW_ALIASES,
    LEGACY_VIEW_GROUPS,
    PRIMARY_VIEW_LABELS,
    PRIMARY_VIEW_ORDER,
)
from promptcontrollab.integrations.ui.content_tutorial import (
    ONBOARDING_PATHS,
    TUTORIAL_IMAGES,
    TUTORIAL_SCREENSHOTS,
    TUTORIAL_SECTION_SCREENSHOTS,
    TUTORIAL_SECTIONS,
    TUTORIAL_STEPS,
)
from promptcontrollab.integrations.ui.data import load_run_detail
from promptcontrollab.preflight.tool_choice import (
    adoption_path_rows as _tool_choice_adoption_path_rows,
)
from promptcontrollab.preflight.tool_choice import tool_choice_lanes


def _hide_streamlit_chrome(st: Any) -> None:
    """Normalize hide streamlit chrome values for the dashboard."""
    st.markdown(
        """
<style>
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}
[data-testid="stToolbar"] {display: none !important;}
[data-testid="stDecoration"] {display: none !important;}
</style>
""",
        unsafe_allow_html=True,
    )


def _sidebar_language(st: Any, query: JsonDict) -> str:
    """Normalize sidebar language values for the dashboard."""
    default = str(query.get("lang") or os.environ.get("PCL_UI_LANGUAGE", "en"))
    selected = st.sidebar.selectbox(
        "Language / 语言",
        ["English", "中文"],
        index=0 if default == "en" else 1,
    )
    return "zh" if selected == "中文" else "en"


def _query_params(st: Any) -> JsonDict:
    """Normalize query params values for the dashboard."""
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
    """Normalize first query value values for the dashboard."""
    if isinstance(value, list) and value:
        return str(value[0])
    return str(value)


def _truthy(value: object) -> bool:
    """Normalize truthy values for the dashboard."""
    return str(value).lower() in {"1", "true", "yes", "on"}


def _choice_labels(group: str, language: str) -> list[str]:
    """Return localized labels while keeping workflow values stable."""

    index = 2 if language == "zh" else 1
    return [str(item[index]) for item in CHOICE_OPTIONS[group]]


def _choice_value(group: str, label: str, language: str) -> str:
    """Map a localized UI label back to the stable internal enum value."""

    label_index = 2 if language == "zh" else 1
    for item in CHOICE_OPTIONS[group]:
        if label == item[label_index]:
            return str(item[0])
    return label


def tutorial_sections(language: str) -> list[JsonDict]:
    """Return tutorial cards for the selected language."""

    sections = TUTORIAL_SECTIONS.get(language) or TUTORIAL_SECTIONS["en"]
    steps = TUTORIAL_STEPS.get(language) or TUTORIAL_STEPS["en"]
    enriched: list[JsonDict] = []
    for section in sections:
        item: JsonDict = dict(section)
        section_id = str(item.get("id") or "")
        item["screenshot"] = TUTORIAL_SECTION_SCREENSHOTS.get(section_id, "workflows")
        item["steps"] = list(steps.get(section_id, []))
        enriched.append(item)
    return enriched


def onboarding_paths(language: str) -> list[JsonDict]:
    """Return role/goal-based starting paths for first-time UI users."""

    rows = ONBOARDING_PATHS.get(language) or ONBOARDING_PATHS["en"]
    return [dict(row) for row in rows]


def ecosystem_choice_rows(language: str) -> list[JsonDict]:
    """Return a compact map from adjacent tools to PCL's evidence layer."""

    rows: list[JsonDict] = []
    for lane in tool_choice_lanes():
        use_first = str(lane.get("use_first") or "")
        tools = ["LangSmith", "Langfuse"] if use_first == "LangSmith or Langfuse" else [use_first]
        for tool in tools:
            rows.append(
                {
                    "start": str(
                        (lane.get("when_zh") if language == "zh" else lane.get("when"))
                        or lane.get("when", "")
                    ),
                    "tool": "PCL" if tool == "prompt_control_lab" else tool,
                    "pcl": str(
                        (
                            lane.get("pcl_short_zh")
                            if language == "zh"
                            else lane.get("pcl_short")
                        )
                        or lane.get("pcl_short", "")
                    ),
                }
            )
    return rows


def adoption_path_rows(language: str) -> list[JsonDict]:
    """Return the shared five-minute adoption path for UI rendering."""

    return _tool_choice_adoption_path_rows(language)


def tutorial_gallery_items(language: str) -> list[JsonDict]:
    """Return always-visible tutorial image cards for the selected language."""

    if language == "zh":
        return [
            {"title": "工作流：一键生成和导出", "image": "workflows"},
            {"title": "守护：执行前检查风险", "image": "guard"},
            {"title": "报告：用证据做决策", "image": "report"},
            {"title": "模型漂移：确认比较是否干净", "image": "model_drift"},
            {"title": "审计：看清 Agent 改动", "image": "audit"},
            {"title": "历史：追踪 run 趋势", "image": "history"},
        ]
    return [
        {"title": "Workflows: run and export locally", "image": "workflows"},
        {"title": "Guard: check risk first", "image": "guard"},
        {"title": "Report: decide with evidence", "image": "report"},
        {"title": "Model drift: validate comparisons", "image": "model_drift"},
        {"title": "Audit: inspect agent changes", "image": "audit"},
        {"title": "History: track run trends", "image": "history"},
    ]


def _tutorial_asset_path(image_key: str, language: str) -> Path:
    """Normalize tutorial asset path values for the dashboard."""
    filenames = TUTORIAL_IMAGES.get(image_key) or TUTORIAL_IMAGES["overview"]
    filename = filenames[1] if language == "zh" else filenames[0]
    return _tutorial_assets_dir() / filename


def _tutorial_screenshot_path(image_key: str, language: str) -> Path:
    """Normalize tutorial screenshot path values for the dashboard."""
    filenames = TUTORIAL_SCREENSHOTS.get(image_key) or TUTORIAL_SCREENSHOTS["workflows"]
    filename = filenames[1] if language == "zh" else filenames[0]
    return _tutorial_assets_dir() / filename


def _tutorial_assets_dir() -> Path:
    """Locate packaged tutorial assets with a source-checkout fallback."""

    packaged = Path(__file__).resolve().parent / "assets"
    if packaged.is_dir():
        return packaged
    return Path(__file__).resolve().parents[4] / "docs" / "assets"


def _ordered_views(first: str) -> list[str]:
    """Normalize ordered views values for the dashboard."""
    del first
    return list(PRIMARY_VIEW_ORDER)


def primary_view_labels(language: str) -> list[str]:
    """Return primary control-run navigation labels in fixed lifecycle order."""

    labels = PRIMARY_VIEW_LABELS.get(language, PRIMARY_VIEW_LABELS["en"])
    return [labels[view] for view in PRIMARY_VIEW_ORDER]


def legacy_sections_for(view: str) -> tuple[str, ...]:
    """Return preserved legacy renderers nested under one primary view."""

    return LEGACY_VIEW_GROUPS.get(view, ())


def _resolve_primary_view(value: str) -> str:
    """Normalize resolve primary view values for the dashboard."""
    if value in PRIMARY_VIEW_ORDER:
        return value
    return LEGACY_VIEW_ALIASES.get(value, DEFAULT_PRIMARY_VIEW)


def _select_run(st: Any, runs: list[JsonDict], text: dict[str, str]) -> JsonDict:
    """Normalize select run values for the dashboard."""
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
