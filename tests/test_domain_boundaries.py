"""Dependency-direction contracts for canonical PromptControlLab domains."""

from __future__ import annotations

import ast
from pathlib import Path

PACKAGE_ROOT = Path(__file__).parents[1] / "src" / "promptcontrollab"
PRODUCT_DOMAINS = {
    "audit",
    "cli",
    "control",
    "diagnostics",
    "evaluation",
    "evidence",
    "integrations",
    "preflight",
    "provenance",
}
CANONICAL_PACKAGES = PRODUCT_DOMAINS | {"core"}


def test_core_does_not_import_product_domains() -> None:
    """Keep shared infrastructure independent from every product domain."""

    violations: list[str] = []
    for source in sorted((PACKAGE_ROOT / "core").glob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            module = _imported_module(node)
            if module is None:
                continue
            parts = module.split(".")
            if len(parts) >= 2 and parts[0] == "promptcontrollab" and parts[1] in PRODUCT_DOMAINS:
                violations.append(f"{source.name}:{node.lineno} imports {module}")

    assert violations == []


def test_canonical_packages_do_not_import_legacy_facades() -> None:
    """Keep compatibility facades outside the canonical dependency graph."""

    flat_modules = {
        path.stem
        for path in PACKAGE_ROOT.glob("*.py")
        if path.stem not in {"__init__", "__main__"}
    }
    legacy_packages = {"evidence_adapters", "ui"}
    facade_names = (flat_modules | legacy_packages) - CANONICAL_PACKAGES
    violations: list[str] = []

    for domain in sorted(CANONICAL_PACKAGES):
        for source in sorted((PACKAGE_ROOT / domain).rglob("*.py")):
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
            for node in ast.walk(tree):
                module = _imported_module(node)
                if module is None:
                    continue
                parts = module.split(".")
                if (
                    len(parts) >= 2
                    and parts[0] == "promptcontrollab"
                    and parts[1] in facade_names
                ):
                    relative = source.relative_to(PACKAGE_ROOT)
                    violations.append(f"{relative}:{node.lineno} imports {module}")

    assert violations == []


def _imported_module(node: ast.AST) -> str | None:
    """Return the absolute module named by one import node."""

    if isinstance(node, ast.ImportFrom):
        return node.module
    if isinstance(node, ast.Import) and node.names:
        return node.names[0].name
    return None
