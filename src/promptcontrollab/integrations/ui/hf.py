"""Hugging Face demo session setup for the Streamlit entrypoint."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any, cast

from promptcontrollab.integrations.hf_demo import (
    DemoSession,
    cleanup_expired_sessions,
    prepare_demo_session,
    store_uploaded_artifact,
    validate_uploaded_artifact,
)
from promptcontrollab.integrations.ui.content import HF_DEMO_TEXT


def _streamlit() -> Any:
    """Normalize streamlit values for the dashboard."""
    return cast(Any, importlib.import_module("streamlit"))


def _prepare_hf_demo_session(st: Any) -> DemoSession:
    """Return the isolated artifact workspace owned by this Streamlit session."""

    base_dir = Path(os.environ.get("PCL_UI_RUNS", "/tmp/prompt_control_lab"))
    state = st.session_state
    session_id = state.get("pcl_hf_demo_session_id")
    if not isinstance(session_id, str):
        cleanup_expired_sessions(base_dir)
        session_id = None
    seed_raw = os.environ.get("PCL_HF_DEMO_SOURCE", "")
    seed = Path(seed_raw) if seed_raw and session_id is None else None
    session = prepare_demo_session(base_dir, seed_runs=seed, session_id=session_id)
    state["pcl_hf_demo_session_id"] = session.session_id
    return session


def _render_hf_demo_upload(st: Any, session: DemoSession, language: str) -> None:
    """Render the bounded JSON/JSONL importer for one public-demo session."""

    labels = HF_DEMO_TEXT[language]
    with st.sidebar.expander(labels["upload_title"], expanded=False):
        st.caption(labels["upload_help"])
        run_name = st.text_input(labels["upload_run"], "uploaded-run", key="hf_upload_run")
        uploaded = st.file_uploader(
            labels["upload_title"],
            type=["json", "jsonl"],
            accept_multiple_files=False,
            key="hf_artifact_upload",
            label_visibility="collapsed",
        )
        if st.button(labels["upload_button"], key="hf_upload_button"):
            if uploaded is None:
                st.warning(labels["upload_help"])
                return
            try:
                content = uploaded.getvalue()
                metadata = validate_uploaded_artifact(uploaded.name, content)
                output = store_uploaded_artifact(
                    session,
                    run_name=run_name,
                    filename=uploaded.name,
                    content=content,
                )
            except (OSError, UnicodeError, ValueError) as exc:
                st.error(str(exc))
                return
            st.success(f"{labels['upload_ok']}: {output.relative_to(session.root)}")
            st.json(
                {
                    "format": metadata["format"],
                    "record_count": metadata["record_count"],
                    "size_bytes": metadata["size_bytes"],
                }
            )
