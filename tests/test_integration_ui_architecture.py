"""Architecture contracts for the integration dashboard split."""

from __future__ import annotations

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "src" / "promptcontrollab" / "integrations" / "ui"
INTEGRATIONS_ROOT = ROOT / "src" / "promptcontrollab" / "integrations"


def _line_count(path: Path) -> int:
    """Return the physical line count for one source file."""

    return len(path.read_text(encoding="utf-8").splitlines())


def test_dashboard_implementation_files_stay_within_split_limit() -> None:
    """Keep canonical dashboard modules below the agreed size ceiling."""

    implementation_files = [
        *UI_ROOT.rglob("*.py"),
        *INTEGRATIONS_ROOT.glob("ecosystem_*.py"),
    ]
    oversized = {
        str(path.relative_to(ROOT)): _line_count(path)
        for path in implementation_files
        if _line_count(path) > 1500
    }
    assert oversized == {}


def test_dashboard_app_is_a_small_composition_entry() -> None:
    """Keep the Streamlit entry focused on composition and dispatch."""

    assert _line_count(UI_ROOT / "app.py") <= 600


def test_old_ui_facades_export_the_canonical_public_symbols() -> None:
    """Preserve supported imports while implementation modules move."""

    canonical_app = importlib.import_module("promptcontrollab.integrations.ui.app")
    legacy_app = importlib.import_module("promptcontrollab.ui.app")
    canonical_data = importlib.import_module("promptcontrollab.integrations.ui.data")
    legacy_data = importlib.import_module("promptcontrollab.ui.data")

    assert legacy_app.main is canonical_app.main
    assert legacy_app.TEXT is canonical_app.TEXT
    assert legacy_app.primary_view_labels is canonical_app.primary_view_labels
    assert legacy_data.list_runs is canonical_data.list_runs
    assert legacy_data.load_run_detail is canonical_data.load_run_detail
    assert legacy_data.deepseek_harness_view is canonical_data.deepseek_harness_view
