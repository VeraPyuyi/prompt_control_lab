"""Backward-compatible facade for :mod:`promptcontrollab.integrations.ui.app`."""
# ruff: noqa: F401

from promptcontrollab.integrations.ui.app import (
    CHOICE_OPTIONS,
    CONTROL_TEXT,
    DEFAULT_PRIMARY_VIEW,
    HF_DEMO_TEXT,
    INTERPRETATION_LABELS,
    LEGACY_VIEW_ALIASES,
    LEGACY_VIEW_GROUPS,
    ONBOARDING_PATHS,
    PRIMARY_VIEW_LABELS,
    PRIMARY_VIEW_ORDER,
    TEXT,
    TUTORIAL_IMAGES,
    TUTORIAL_SCREENSHOTS,
    TUTORIAL_SECTION_SCREENSHOTS,
    TUTORIAL_SECTIONS,
    TUTORIAL_STEPS,
    adoption_path_rows,
    ecosystem_choice_rows,
    legacy_sections_for,
    main,
    onboarding_paths,
    primary_view_labels,
    tutorial_gallery_items,
    tutorial_sections,
)

__all__ = [name for name in globals() if not name.startswith("_")]
