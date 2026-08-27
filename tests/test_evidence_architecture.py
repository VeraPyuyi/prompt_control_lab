"""Architecture contracts for the canonical evidence domain."""

from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).parents[1] / "src" / "promptcontrollab"
EVIDENCE_ROOT = PACKAGE_ROOT / "evidence"

CANONICAL_MODULES = (
    "evidence_card",
    "evidence_gate",
    "evidence_profiles",
    "external_evidence",
    "ingest",
    "peoc_import",
    "peoc_reporting",
    "server_evidence",
    "posttrain_gate",
    "posttrain_pilot",
    "posttrain_pilot_data",
    "posttrain_pilot_runner",
    "posttrain_pilot_summary",
    "posttrain_export",
)

PUBLIC_COMPATIBILITY = (
    ("evidence_card", "build_evidence_card"),
    ("evidence_gate", "run_evidence_gate"),
    ("evidence_profiles", "get_evidence_profile"),
    ("external_evidence", "build_external_evidence"),
    ("ingest", "ingest_auto_results"),
    ("peoc_import", "import_peoc_bundle"),
    ("peoc_reporting", "render_peoc_case_study_markdown"),
    ("server_evidence", "scan_evidence_root"),
    ("posttrain_gate", "run_posttrain_gate"),
    ("posttrain_pilot", "build_sft_pilot_plan"),
    ("posttrain_pilot_data", "prepare_sft_pilot_data"),
    ("posttrain_pilot_runner", "execute_sft_pilot"),
    ("posttrain_pilot_summary", "write_pilot_summary"),
    ("posttrain_export", "export_posttrain_pilot"),
)

ADAPTER_MODULES = (
    "base",
    "prompt_projection",
    "prompt_reachability",
    "prompt_routing",
    "prompt_stability",
    "readout_alignment",
)

_CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


@pytest.mark.parametrize("module_name", CANONICAL_MODULES)
def test_evidence_implementation_is_canonical(module_name: str) -> None:
    """Keep real implementations in the evidence package and legacy files as facades."""

    implementation = EVIDENCE_ROOT / f"{module_name}.py"
    facade = PACKAGE_ROOT / f"{module_name}.py"
    assert implementation.is_file()
    assert facade.is_file()
    assert "Backward-compatible facade" in facade.read_text(encoding="utf-8")


@pytest.mark.parametrize(("module_name", "symbol"), PUBLIC_COMPATIBILITY)
def test_legacy_evidence_api_reexports_canonical_symbol(
    module_name: str,
    symbol: str,
) -> None:
    """Bind established evidence imports to the canonical implementation object."""

    canonical = importlib.import_module(f"promptcontrollab.evidence.{module_name}")
    legacy = importlib.import_module(f"promptcontrollab.{module_name}")
    assert getattr(legacy, symbol) is getattr(canonical, symbol)


@pytest.mark.parametrize("module_name", ADAPTER_MODULES)
def test_evidence_adapter_legacy_module_reexports_canonical_symbols(
    module_name: str,
) -> None:
    """Preserve every established evidence adapter module path."""

    canonical = importlib.import_module(f"promptcontrollab.evidence.adapters.{module_name}")
    legacy = importlib.import_module(f"promptcontrollab.evidence_adapters.{module_name}")
    public = getattr(canonical, "__all__", ())
    assert public
    for symbol in public:
        assert getattr(legacy, symbol) is getattr(canonical, symbol)


def test_canonical_evidence_implementation_files_stay_bounded() -> None:
    """Require focused evidence implementation files rather than new monoliths."""

    oversized = {
        path.relative_to(EVIDENCE_ROOT).as_posix(): len(
            path.read_text(encoding="utf-8").splitlines()
        )
        for path in EVIDENCE_ROOT.rglob("*.py")
        if len(path.read_text(encoding="utf-8").splitlines()) > 1500
    }
    assert oversized == {}


def test_canonical_evidence_code_never_imports_legacy_facades() -> None:
    """Prevent canonical evidence modules from depending on compatibility facades."""

    legacy_names = set(CANONICAL_MODULES) | {"evidence_adapters"}
    violations: list[str] = []
    for path in EVIDENCE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            imported: list[str] = []
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = [node.module]
            for module_name in imported:
                parts = module_name.split(".")
                if len(parts) >= 2 and parts[0] == "promptcontrollab" and parts[1] in legacy_names:
                    violations.append(
                        f"{path.relative_to(PACKAGE_ROOT)}:"
                        f"{getattr(node, 'lineno', 0)}:{module_name}"
                    )
    assert violations == []


def test_canonical_evidence_entrypoints_have_concise_english_docstrings() -> None:
    """Require PEP 257 summaries on evidence APIs and substantial private helpers."""

    violations: list[str] = []
    for path in EVIDENCE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            node_parent = parents.get(node)
            public_top_level = isinstance(node_parent, ast.Module) and not node.name.startswith("_")
            public_method = isinstance(node_parent, ast.ClassDef) and not node.name.startswith("_")
            line_count = (node.end_lineno or node.lineno) - node.lineno + 1
            substantial_private_helper = (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.startswith("_")
                and line_count > 50
            )
            if not (public_top_level or public_method or substantial_private_helper):
                continue

            location = f"{path.relative_to(EVIDENCE_ROOT)}:{node.lineno}:{node.name}"
            docstring = ast.get_docstring(node, clean=False)
            if not docstring:
                violations.append(f"{location}: missing docstring")
                continue
            summary = docstring.strip().splitlines()[0].strip()
            if _CJK_PATTERN.search(docstring):
                violations.append(f"{location}: docstring must be English")
            if len(summary) > 120:
                violations.append(f"{location}: summary exceeds 120 characters")
            if summary and summary[-1] not in ".!?":
                violations.append(f"{location}: summary must end with punctuation")

    assert violations == []
