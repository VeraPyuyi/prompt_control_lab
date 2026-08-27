"""Tutorial and local visual-asset rendering pages."""

from __future__ import annotations

import base64
import html
from pathlib import Path
from typing import Any

from promptcontrollab.integrations.ui.navigation import (
    _tutorial_asset_path,
    _tutorial_screenshot_path,
    adoption_path_rows,
    ecosystem_choice_rows,
    onboarding_paths,
    tutorial_gallery_items,
    tutorial_sections,
)


def _render_tutorial_tab(st: Any, text: dict[str, str], language: str) -> None:
    """Render tutorial tab content without changing dashboard state."""
    st.markdown(text["tutorial_intro"])
    st.markdown(
        f'<div class="pcl-section-title">{html.escape(text["onboarding_title"])}</div>',
        unsafe_allow_html=True,
    )
    st.dataframe(
        [
            {
                text["onboarding_goal"]: row.get("goal", ""),
                text["onboarding_start"]: row.get("start", ""),
                text["onboarding_next"]: row.get("next", ""),
            }
            for row in onboarding_paths(language)
        ],
        use_container_width=True,
    )
    st.markdown(
        f'<div class="pcl-section-title">{html.escape(text["ecosystem_choice_title"])}</div>',
        unsafe_allow_html=True,
    )
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
    st.dataframe(
        [
            {
                text["ecosystem_choice_start"]: row.get("start", ""),
                text["ecosystem_choice_use"]: row.get("tool", ""),
                text["ecosystem_choice_add"]: row.get("pcl", ""),
            }
            for row in ecosystem_choice_rows(language)
        ],
        use_container_width=True,
    )
    overview = _tutorial_asset_path("overview", language)
    if overview.exists():
        _render_image(st, overview)
    _render_tutorial_gallery(st, language)

    for section in tutorial_sections(language):
        title = str(section.get("title", ""))
        expanded = section.get("id") in {"guard", "workflows"}
        with st.expander(title, expanded=expanded):
            screenshot_key = str(section.get("screenshot") or "workflows")
            image_path = _tutorial_screenshot_path(screenshot_key, language)
            if image_path.exists():
                _render_image(st, image_path)
            steps = section.get("steps") or []
            if isinstance(steps, list) and steps:
                st.markdown(f"**{text['tutorial_steps']}**")
                for index, step in enumerate(steps, start=1):
                    st.markdown(f"{index}. {step}")
            st.markdown(f"**{text['tutorial_operation']}**: {section.get('operation', '')}")
            st.markdown(f"**{text['tutorial_result']}**: {section.get('result', '')}")
            st.markdown(f"**{text['tutorial_meaning']}**: {section.get('meaning', '')}")
            st.markdown(f"**{text['tutorial_next_step']}**: {section.get('next_step', '')}")
            st.caption(text["tutorial_command"])
            st.code(str(section.get("command", "")), language="bash")


def _render_tutorial_gallery(st: Any, language: str) -> None:
    """Render tutorial gallery content without changing dashboard state."""
    columns = st.columns(2)
    for index, item in enumerate(tutorial_gallery_items(language)):
        with columns[index % 2]:
            st.markdown(f"**{item['title']}**")
            path = _tutorial_screenshot_path(str(item["image"]), language)
            if path.exists():
                _render_image(st, path)


def _render_svg(st: Any, path: Path) -> None:
    """Render svg content without changing dashboard state."""
    _render_image(st, path)


def _render_image(st: Any, path: Path) -> None:
    """Render image content without changing dashboard state."""
    mime_type = "image/png" if path.suffix.lower() == ".png" else "image/svg+xml"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    st.markdown(
        (
            f'<img src="data:{mime_type};base64,{encoded}" '
            'style="width: 100%; max-width: 1100px; border-radius: 8px;" '
            f'alt="{path.stem}">'
        ),
        unsafe_allow_html=True,
    )
