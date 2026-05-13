"""Configurable prompt guard policies."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from promptcontrollab.config import read_simple_yaml
from promptcontrollab.files import JsonDict

SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2}


@dataclass(frozen=True)
class GuardPolicyRule:
    """One configurable prompt guard rule."""

    id: str
    severity: str = "medium"
    message: str = ""
    category: str = "policy"
    patterns: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GuardPolicy:
    """Flat dependency-free guard policy."""

    profile: str | None = None
    block_at: str = "high"
    review_at: str = "medium"
    required_fields: list[str] = field(default_factory=list)
    rules: list[GuardPolicyRule] = field(default_factory=list)


@dataclass(frozen=True)
class GuardViolation:
    """One guard violation emitted by built-in or policy checks."""

    id: str
    severity: str
    message: str
    category: str
    source: str

    def to_json(self) -> JsonDict:
        return {
            "id": self.id,
            "severity": self.severity,
            "message": self.message,
            "category": self.category,
            "source": self.source,
        }


def load_guard_policy(path: Path | None) -> GuardPolicy | None:
    """Load a flat guard policy file."""

    if path is None:
        return None
    payload = read_simple_yaml(path)
    rules: dict[str, dict[str, object]] = {}
    for key, value in payload.items():
        if not key.startswith("rule."):
            continue
        parts = key.split(".", maxsplit=2)
        if len(parts) != 3:
            msg = f"Invalid guard policy key `{key}`"
            raise ValueError(msg)
        _, rule_id, field_name = parts
        rules.setdefault(rule_id, {})[field_name] = value

    return GuardPolicy(
        profile=_optional_str(payload.get("profile")),
        block_at=_severity(str(payload.get("block_at", "high"))),
        review_at=_severity(str(payload.get("review_at", "medium"))),
        required_fields=_split_list(payload.get("required_fields")),
        rules=[
            GuardPolicyRule(
                id=rule_id,
                severity=_severity(str(rule_payload.get("severity", "medium"))),
                message=str(rule_payload.get("message", f"Policy rule `{rule_id}` matched.")),
                category=str(rule_payload.get("category", "policy")),
                patterns=_split_list(rule_payload.get("patterns")),
            )
            for rule_id, rule_payload in sorted(rules.items())
        ],
    )


def evaluate_guard_policy(prompt: str, policy: GuardPolicy | None) -> list[GuardViolation]:
    """Evaluate built-in dangerous prompt checks plus optional configured policy."""

    violations = _builtin_violations(prompt)
    if policy is None:
        return violations
    for field_name in policy.required_fields:
        if not _has_required_field(prompt, field_name):
            violations.append(
                GuardViolation(
                    id=f"missing_{field_name}",
                    severity="medium",
                    message=f"Prompt should include `{field_name}`.",
                    category="missing_context",
                    source="policy",
                )
            )
    lowered = prompt.lower()
    for rule in policy.rules:
        if rule.patterns and any(pattern.lower() in lowered for pattern in rule.patterns):
            violations.append(
                GuardViolation(
                    id=rule.id,
                    severity=rule.severity,
                    message=rule.message,
                    category=rule.category,
                    source="policy",
                )
            )
    return violations


def highest_severity(values: list[str]) -> str:
    """Return highest severity from a list."""

    if not values:
        return "low"
    return max(values, key=lambda value: SEVERITY_RANK.get(value, -1))


def severity_at_least(value: str, threshold: str) -> bool:
    """Return whether severity value is at least threshold."""

    return SEVERITY_RANK.get(value, 0) >= SEVERITY_RANK.get(threshold, 0)


def unique_categories(violations: list[GuardViolation]) -> list[str]:
    """Return categories in first-seen order."""

    categories: list[str] = []
    for violation in violations:
        if violation.category not in categories:
            categories.append(violation.category)
    return categories


def _builtin_violations(prompt: str) -> list[GuardViolation]:
    lowered = prompt.lower()
    checks = [
        (
            "destructive_operation",
            "high",
            "destructive_change",
            [
                "delete ",
                "delete database",
                "drop table",
                "remove migration",
                "delete all",
                "remove auth",
            ],
            "Prompt asks for a destructive change.",
        ),
        (
            "security_sensitive",
            "high",
            "security",
            ["auth", "permission", "token", "secret", "credential", "api key", "env secrets"],
            "Prompt touches authentication, permissions, credentials, or secrets.",
        ),
        (
            "data_exposure",
            "high",
            "data_exposure",
            ["dump database", "export user data", "print env"],
            "Prompt may expose private data or environment values.",
        ),
        (
            "broad_refactor",
            "medium",
            "broad_refactor",
            ["refactor whole repo", "rewrite all", "rewrite entire"],
            "Prompt requests a broad refactor without tight scope.",
        ),
        (
            "production_path",
            "high",
            "production_path",
            ["prod", "production", "billing", "payment", "deploy"],
            "Prompt touches production, billing, payment, or deployment paths.",
        ),
    ]
    violations = [
        GuardViolation(
            id=rule_id,
            severity=severity,
            category=category,
            message=message,
            source="builtin",
        )
        for rule_id, severity, category, patterns, message in checks
        if any(pattern in lowered for pattern in patterns)
    ]
    if _looks_like_coding_prompt(lowered) and not _has_required_field(prompt, "test_plan"):
        violations.append(
            GuardViolation(
                id="no_tests",
                severity="medium",
                category="no_tests",
                message="Coding prompt should include verification or tests.",
                source="builtin",
            )
        )
    return violations


def _looks_like_coding_prompt(lowered: str) -> bool:
    return any(
        token in lowered
        for token in ["bug", "fix", "code", "refactor", ".py", ".js", ".ts", ".md", "module"]
    )


def _has_required_field(prompt: str, field_name: str) -> bool:
    lowered = prompt.lower()
    if field_name == "target_files":
        return bool(re.search(r"[\w./\\-]+\.(py|js|ts|tsx|md|json|ya?ml|toml|sql)", lowered))
    if field_name == "failing_behavior":
        return any(
            token in lowered
            for token in ["fail", "error", "bug", "traceback", "exception", "expected", "actual"]
        )
    if field_name == "test_plan":
        return any(token in lowered for token in ["test", "pytest", "verify", "check", "validate"])
    if field_name == "acceptance_criteria":
        return any(
            token in lowered
            for token in ["acceptance", "criteria", "done when", "should", "success", "passes"]
        )
    return field_name.replace("_", " ") in lowered


def _split_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in re.split(r"[,|]", str(value)) if item.strip()]


def _optional_str(value: object) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _severity(value: str) -> str:
    if value not in SEVERITY_RANK:
        msg = f"Expected severity low, medium, or high, got {value!r}"
        raise ValueError(msg)
    return value
