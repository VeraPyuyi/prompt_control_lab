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


def _imported_module(node: ast.AST) -> str | None:
    """Return the absolute module named by one import node."""

    if isinstance(node, ast.ImportFrom):
        return node.module
    if isinstance(node, ast.Import) and node.names:
        return node.names[0].name
    return None
