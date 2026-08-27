"""Architecture and compatibility contracts for the modular package layout."""

from __future__ import annotations

import ast
import importlib
import inspect
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

ENGLISH_GUIDE_SECTIONS = (
    "Purpose",
    "Use cases",
    "CLI commands",
    "Python API",
    "Inputs/Artifacts",
    "Dependencies",
    "Extension points",
    "Limitations",
    "Tests/Examples",
)

CHINESE_GUIDE_SECTIONS = (
    "目的",
    "使用场景",
    "CLI 命令",
    "Python API",
    "输入与产物",
    "依赖",
    "扩展点",
    "限制",
    "测试与示例",
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
    "core": ("config", "errors", "files", "optional", "schemas", "version"),
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
        "doctor",
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


def test_canonical_implementation_files_stay_below_the_hard_size_limit() -> None:
    """Prevent any canonical implementation from returning to a giant module."""

    oversized: dict[str, int] = {}
    for module_name in MODULES:
        for source in (PACKAGE_ROOT / module_name).rglob("*.py"):
            line_count = len(source.read_text(encoding="utf-8").splitlines())
            if line_count > 1500:
                oversized[source.relative_to(PACKAGE_ROOT).as_posix()] = line_count
    assert oversized == {}


def test_all_flat_facades_preserve_their_declared_public_symbols() -> None:
    """Bind every legacy flat export to the same canonical object and signature."""

    failures: list[str] = []
    for facade_path in sorted(PACKAGE_ROOT.glob("*.py")):
        source = facade_path.read_text(encoding="utf-8")
        if "Backward-compatible facade" not in source:
            continue
        tree = ast.parse(source, filename=str(facade_path))
        imported: dict[str, tuple[str, str]] = {}
        public: list[str] | None = None
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    imported[alias.asname or alias.name] = (node.module, alias.name)
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in node.targets
            ):
                value = ast.literal_eval(node.value)
                public = list(value)

        if public is None:
            failures.append(f"{facade_path.name}: missing explicit __all__")
            continue
        legacy = importlib.import_module(f"promptcontrollab.{facade_path.stem}")
        for symbol in public:
            target = imported.get(symbol)
            if target is None:
                failures.append(f"{facade_path.name}: {symbol} has no explicit canonical import")
                continue
            module_name, canonical_name = target
            canonical = getattr(importlib.import_module(module_name), canonical_name)
            legacy_value = getattr(legacy, symbol, None)
            if legacy_value is not canonical:
                failures.append(f"{facade_path.name}: {symbol} is not the canonical object")
                continue
            if callable(canonical):
                try:
                    legacy_signature = inspect.signature(legacy_value)
                    canonical_signature = inspect.signature(canonical)
                except (TypeError, ValueError):
                    continue
                assert legacy_signature == canonical_signature

    assert failures == []


@pytest.mark.parametrize("module_name", MODULES)
def test_bilingual_module_guides_share_the_required_structure(module_name: str) -> None:
    """Keep every module guide complete and structurally aligned across languages."""

    package_dir = PACKAGE_ROOT / module_name
    english = (package_dir / "README.md").read_text(encoding="utf-8")
    chinese = (package_dir / "README.zh.md").read_text(encoding="utf-8")
    assert [line[3:] for line in english.splitlines() if line.startswith("## ")] == list(
        ENGLISH_GUIDE_SECTIONS
    )
    assert [line[3:] for line in chinese.splitlines() if line.startswith("## ")] == list(
        CHINESE_GUIDE_SECTIONS
    )
    assert english.count("```") == chinese.count("```")


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
    for module_name in ("app", "charts", "components", "workflows"):
        assert (canonical / f"{module_name}.py").is_file()
        facade = legacy / f"{module_name}.py"
        assert facade.is_file()
        assert "Backward-compatible facade" in facade.read_text(encoding="utf-8")

    assert (canonical / "data" / "__init__.py").is_file()
    data_facade = legacy / "data.py"
    assert data_facade.is_file()
    assert "Backward-compatible facade" in data_facade.read_text(encoding="utf-8")


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
