"""Architecture contracts for the canonical diagnostics domain."""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).parents[1] / "src" / "promptcontrollab"
DIAGNOSTICS_ROOT = PACKAGE_ROOT / "diagnostics"

PUBLIC_APIS = (
    ("green_certificate", "analyze_green_certificate"),
    ("hf_hidden", "load_prompt_texts"),
    ("hf_hidden", "extract_hidden_states"),
    ("posterior_certificate", "analyze_posterior_certificate"),
    ("riccati", "analyze_riccati"),
    ("soft_hard", "analyze_soft_hard"),
    ("terminal_sensitivity", "analyze_terminal_sensitivity"),
    ("trajectory", "analyze_trajectory"),
    ("tv_soft", "summarize_tv_soft"),
)

RESEARCH_APIS = (
    "PAPER_MAPPING",
    "PAPER_REMEDIATION",
    "ResearchPaths",
    "write_research_demo",
    "run_research_diagnostics",
    "write_peoc_research_gap_plan",
    "write_research_gap_status",
    "write_research_bundle_index",
    "verify_research_bundle_index",
    "build_research_bundle_index",
    "render_research_bundle_index_html",
    "render_research_bundle_index_markdown",
    "render_research_bundle_verification_html",
    "render_research_gap_status_html",
    "render_research_gap_plan_html",
    "render_research_diagnostics_markdown",
    "render_research_diagnostics_html",
    "render_research_overview_svg",
)

SPLIT_MODULES = (
    "bundle.py",
    "bundle_renderers.py",
    "gap.py",
    "gap_renderers.py",
    "interpretation.py",
    "renderers.py",
    "runner.py",
)

DIAGNOSTIC_MODULES = (
    "green_certificate",
    "hf_hidden",
    "posterior_certificate",
    "research_workflow",
    "riccati",
    "soft_hard",
    "terminal_sensitivity",
    "trajectory",
    "tv_soft",
)


@pytest.mark.parametrize(("module_name", "symbol"), PUBLIC_APIS)
def test_legacy_diagnostic_api_is_canonical(module_name: str, symbol: str) -> None:
    """Keep legacy diagnostic imports bound to canonical implementations."""

    canonical = importlib.import_module(f"promptcontrollab.diagnostics.{module_name}")
    legacy = importlib.import_module(f"promptcontrollab.{module_name}")
    assert getattr(legacy, symbol) is getattr(canonical, symbol)


@pytest.mark.parametrize("symbol", RESEARCH_APIS)
def test_legacy_research_workflow_api_is_canonical(symbol: str) -> None:
    """Keep the established research workflow surface silently compatible."""

    canonical = importlib.import_module("promptcontrollab.diagnostics.research_workflow")
    legacy = importlib.import_module("promptcontrollab.research_workflow")
    assert getattr(legacy, symbol) is getattr(canonical, symbol)
    if callable(getattr(legacy, symbol)):
        assert inspect.signature(getattr(legacy, symbol)) == inspect.signature(
            getattr(canonical, symbol)
        )


def test_research_workflow_is_split_into_bounded_modules() -> None:
    """Prevent the canonical research workflow from returning to a monolith."""

    for filename in SPLIT_MODULES:
        path = DIAGNOSTICS_ROOT / filename
        assert path.is_file(), filename

    for path in DIAGNOSTICS_ROOT.glob("*.py"):
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        assert line_count <= 1500, f"{path.name}: {line_count} lines"

    coordinator = DIAGNOSTICS_ROOT / "research_workflow.py"
    assert len(coordinator.read_text(encoding="utf-8").splitlines()) <= 250


@pytest.mark.parametrize("module_name", DIAGNOSTIC_MODULES)
def test_diagnostic_implementation_is_canonical_and_legacy_file_is_facade(
    module_name: str,
) -> None:
    """Keep real diagnostic code canonical and legacy modules intentionally small."""

    implementation = DIAGNOSTICS_ROOT / f"{module_name}.py"
    facade = PACKAGE_ROOT / f"{module_name}.py"
    assert implementation.is_file()
    assert facade.is_file()
    assert "Backward-compatible facade" in facade.read_text(encoding="utf-8")


def test_canonical_diagnostics_do_not_import_legacy_facades() -> None:
    """Require all diagnostics-internal imports to use canonical package paths."""

    legacy_modules = {
        "green_certificate",
        "hf_hidden",
        "posterior_certificate",
        "research_workflow",
        "riccati",
        "soft_hard",
        "terminal_sensitivity",
        "trajectory",
        "tv_soft",
    }
    violations: list[str] = []
    for path in DIAGNOSTICS_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                prefix, _, suffix = node.module.partition(".")
                if prefix == "promptcontrollab" and suffix in legacy_modules:
                    violations.append(f"{path.name}:{node.lineno}:{node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    prefix = "promptcontrollab."
                    is_legacy = (
                        alias.name.startswith(prefix)
                        and alias.name[len(prefix) :] in legacy_modules
                    )
                    if is_legacy:
                        violations.append(f"{path.name}:{node.lineno}:{alias.name}")
    assert violations == []


def test_diagnostics_package_exposes_explicit_public_surface() -> None:
    """Keep package-level imports lazy, explicit, and bound to canonical objects."""

    package = importlib.import_module("promptcontrollab.diagnostics")
    workflow = importlib.import_module("promptcontrollab.diagnostics.research_workflow")
    expected = {symbol for _, symbol in PUBLIC_APIS} | set(RESEARCH_APIS)
    assert expected <= set(package.__all__)
    for symbol in RESEARCH_APIS:
        assert getattr(package, symbol) is getattr(workflow, symbol)
