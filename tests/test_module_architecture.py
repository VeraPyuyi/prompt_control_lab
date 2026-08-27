"""Architecture and compatibility contracts for the modular package layout."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).parents[1] / "src" / "promptcontrollab"

MODULES = (
    "core",
    "preflight",
    "evaluation",
    "control",
    "provenance",
    "audit",
    "evidence",
    "diagnostics",
    "integrations",
    "cli",
)

PUBLIC_COMPATIBILITY = (
    ("preflight", "prompt_guard", "guard_prompt"),
    ("evaluation", "workflow", "run_quick_analysis"),
    ("control", "control_protocol", "ControlRun"),
    ("provenance", "model_identity", "detect_model_identity"),
    ("audit", "audit_diff", "run_audit_diff"),
    ("evidence", "server_evidence", "scan_evidence_root"),
    ("diagnostics", "terminal_sensitivity", "analyze_terminal_sensitivity"),
    ("integrations", "providers", "call_provider"),
)

CANONICAL_IMPLEMENTATIONS = {
    "core": ("config", "doctor", "errors", "files", "optional", "schemas", "version"),
    "preflight": (
        "guard_policy",
        "prompt_context",
        "prompt_diff",
        "prompt_guard",
        "prompt_improver",
        "scaffold_check",
        "tool_choice",
    ),
    "provenance": ("model_drift", "model_identity", "prompt_identity"),
    "evaluation": (
        "artifact_export",
        "evaluation",
        "explain",
        "gate",
        "history",
        "metrics",
        "report_model",
        "reporting",
        "run_comparison",
        "splitting",
        "statistics",
        "validity",
        "workflow",
    ),
    "control": (
        "control_analysis",
        "control_benchmark",
        "control_bridge",
        "control_events",
        "control_index",
        "control_protocol",
        "control_workflow",
    ),
    "audit": ("agent_run", "audit_diff", "claim_check", "github_app", "pr_summary"),
    "integrations": (
        "ecosystem_demo",
        "harness_integration",
        "hf_demo",
        "hf_space",
        "plugin_installer",
        "providers",
        "templates",
    ),
}


@pytest.mark.parametrize("module_name", MODULES)
def test_canonical_module_has_bilingual_readmes(module_name: str) -> None:
    """Require every canonical package to carry English and Chinese module guides."""

    package_dir = PACKAGE_ROOT / module_name
    assert (package_dir / "__init__.py").is_file()
    assert (package_dir / "README.md").is_file()
    assert (package_dir / "README.zh.md").is_file()


@pytest.mark.parametrize(("canonical", "legacy", "symbol"), PUBLIC_COMPATIBILITY)
def test_legacy_public_api_reexports_canonical_symbol(
    canonical: str,
    legacy: str,
    symbol: str,
) -> None:
    """Keep established imports bound to the canonical implementation object."""

    canonical_module = importlib.import_module(f"promptcontrollab.{canonical}")
    legacy_module = importlib.import_module(f"promptcontrollab.{legacy}")
    assert getattr(legacy_module, symbol) is getattr(canonical_module, symbol)


def test_cli_entrypoint_remains_public() -> None:
    """Preserve the console entrypoint while converting the CLI into a package."""

    cli = importlib.import_module("promptcontrollab.cli")
    assert callable(cli.main)
    assert callable(cli.build_parser)
    assert callable(cli._reconfigure_windows_pipe)


def test_ui_implementation_lives_under_integrations() -> None:
    """Keep the old UI package as a compatibility-only import surface."""

    canonical = PACKAGE_ROOT / "integrations" / "ui"
    legacy = PACKAGE_ROOT / "ui"
    for module_name in ("app", "charts", "components", "data", "workflows"):
        assert (canonical / f"{module_name}.py").is_file()
        facade = legacy / f"{module_name}.py"
        assert facade.is_file()
        assert "Backward-compatible facade" in facade.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("domain", "module_name"),
    [
        (domain, module_name)
        for domain, module_names in CANONICAL_IMPLEMENTATIONS.items()
        for module_name in module_names
    ],
)
def test_implementation_is_canonical_and_legacy_file_is_only_a_facade(
    domain: str,
    module_name: str,
) -> None:
    """Prevent canonical packages from becoming documentation-only shells."""

    implementation = PACKAGE_ROOT / domain / f"{module_name}.py"
    facade = PACKAGE_ROOT / f"{module_name}.py"
    assert implementation.is_file()
    assert facade.is_file()
    assert "Backward-compatible facade" in facade.read_text(encoding="utf-8")
