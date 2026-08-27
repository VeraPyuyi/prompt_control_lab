"""Documentation contracts for every canonical PromptControlLab package."""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).parents[1] / "src" / "promptcontrollab"
CANONICAL_DOMAINS = (
    "core",
    "preflight",
    "provenance",
    "evaluation",
    "control",
    "audit",
    "evidence",
    "diagnostics",
    "integrations",
    "cli",
)
CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
SUMMARY_TERMINATORS = (".", "!", "?")


def _python_sources() -> list[Path]:
    """Return canonical Python sources covered by the documentation contract."""

    return [
        path
        for domain in CANONICAL_DOMAINS
        for path in sorted((PACKAGE_ROOT / domain).rglob("*.py"))
    ]


def _is_tiny_property(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return whether a method is a short property accessor exempt from the contract."""

    is_property = any(
        isinstance(decorator, ast.Name) and decorator.id == "property"
        for decorator in node.decorator_list
    )
    line_count = (node.end_lineno or node.lineno) - node.lineno + 1
    return is_property and line_count <= 10


def _requires_docstring(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    *,
    scope: str,
) -> bool:
    """Return whether an AST definition is part of the documented API contract."""

    if isinstance(node, ast.ClassDef):
        return scope == "module" and not node.name.startswith("_")
    if node.name.startswith("__") and node.name.endswith("__"):
        return False
    if scope == "public_class" and _is_tiny_property(node):
        return False
    if scope == "module" and (
        not node.name.startswith("_") or node.name.startswith("_cmd_")
    ):
        return True
    if scope == "public_class" and not node.name.startswith("_"):
        return True
    line_count = (node.end_lineno or node.lineno) - node.lineno + 1
    return line_count > 50


def _definition_label(path: Path, parents: list[str], name: str, line: int) -> str:
    """Build a compact location label for a documented definition."""

    relative = path.relative_to(PACKAGE_ROOT.parent)
    qualified_name = ".".join([*parents, name])
    return f"{relative}:{line} ({qualified_name})"


def _docstring_violations(path: Path) -> list[str]:
    """Collect missing, non-English, or malformed required docstrings in one source file."""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []

    def visit_body(nodes: list[ast.stmt], parents: list[str], scope: str) -> None:
        for node in nodes:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if _requires_docstring(node, scope=scope):
                label = _definition_label(path, parents, node.name, node.lineno)
                docstring = ast.get_docstring(node, clean=False)
                if not docstring or not docstring.strip():
                    violations.append(f"missing docstring: {label}")
                else:
                    lines = docstring.splitlines()
                    summary = lines[0].strip()
                    if CJK_PATTERN.search(docstring):
                        violations.append(f"CJK text in required docstring: {label}")
                    if not summary.endswith(SUMMARY_TERMINATORS):
                        violations.append(f"summary must end with punctuation: {label}")
                    if len(lines) > 1 and lines[1].strip():
                        violations.append(f"multiline summary needs a blank line: {label}")
            child_scope = "nested"
            if isinstance(node, ast.ClassDef):
                child_scope = "private_class" if node.name.startswith("_") else "public_class"
            visit_body(node.body, [*parents, node.name], scope=child_scope)

    visit_body(tree.body, [], scope="module")
    return violations


@pytest.mark.parametrize("source_path", _python_sources(), ids=lambda path: path.name)
def test_canonical_apis_have_english_pep257_docstrings(source_path: Path) -> None:
    """Require English PEP 257 docstrings on canonical API definitions."""

    violations = _docstring_violations(source_path)
    assert not violations, "\n".join(violations)


@pytest.mark.parametrize("source_path", _python_sources(), ids=lambda path: path.name)
def test_canonical_inline_comments_remain_english(source_path: Path) -> None:
    """Reject CJK text in Python comments within canonical packages."""

    source = source_path.read_text(encoding="utf-8")
    comments = [
        token.string
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type == tokenize.COMMENT
    ]
    assert not [comment for comment in comments if CJK_PATTERN.search(comment)]
