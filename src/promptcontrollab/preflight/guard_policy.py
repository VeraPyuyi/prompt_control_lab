"""Configurable prompt guard policies."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from promptcontrollab.core.config import read_simple_yaml
from promptcontrollab.core.files import JsonDict

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
        """Serialize the policy violation to a JSON-compatible object."""

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
    if _uses_nested_policy(path):
        return _load_nested_policy(path)
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


def _uses_nested_policy(path: Path) -> bool:
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        stripped = line.strip()
        if stripped in {"rules:", "required_fields:"}:
            return True
    return False


def _load_nested_policy(path: Path) -> GuardPolicy:
    """Parse the supported dependency-free nested policy syntax.

    Args:
        path: Policy file to parse.

    Returns:
        A validated guard policy assembled from the nested YAML subset.

    Raises:
        ValueError: If the file contains unsupported or malformed policy syntax.
    """

    profile: str | None = None
    block_at = "high"
    review_at = "medium"
    required_fields: list[str] = []
    rule_payloads: list[dict[str, object]] = []
    current_rule: dict[str, object] | None = None
    current_list: str | None = None

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if stripped.startswith("- "):
            item = stripped[2:].strip()
            if current_list == "patterns" and indent <= 2 and item.startswith("id:"):
                current_rule = {"id": _unquote(item.split(":", maxsplit=1)[1].strip())}
                rule_payloads.append(current_rule)
                current_list = "rules"
                continue
            if current_list == "required_fields":
                required_fields.append(item)
                continue
            if current_list == "patterns":
                if current_rule is None:
                    _raise_policy_format_error(path, line_number)
                assert current_rule is not None
                current_rule.setdefault("patterns", [])
                patterns = current_rule.get("patterns")
                if not isinstance(patterns, list):
                    _raise_policy_format_error(path, line_number)
                assert isinstance(patterns, list)
                patterns.append(item)
                continue
            if current_list == "rules":
                if not item.startswith("id:"):
                    _raise_policy_format_error(path, line_number)
                current_rule = {"id": _unquote(item.split(":", maxsplit=1)[1].strip())}
                rule_payloads.append(current_rule)
                continue
            _raise_policy_format_error(path, line_number)
        if ":" not in stripped:
            _raise_policy_format_error(path, line_number)
        key, raw_value = stripped.split(":", maxsplit=1)
        key = key.strip()
        value = _unquote(raw_value.strip())
        if key == "profile":
            profile = value or None
            current_list = None
            continue
        if key == "block_at":
            block_at = value or "high"
            current_list = None
            continue
        if key == "review_at":
            review_at = value or "medium"
            current_list = None
            continue
        if key == "required_fields":
            if value:
                required_fields = _split_list(value)
                current_list = None
            else:
                current_list = "required_fields"
            continue
        if key == "rules":
            if value:
                _raise_policy_format_error(path, line_number)
            current_list = "rules"
            continue
        if current_rule is None:
            _raise_policy_format_error(path, line_number)
        if key == "patterns":
            assert current_rule is not None
            if value:
                current_rule["patterns"] = _split_list(value)
                current_list = "rules"
            else:
                current_rule["patterns"] = []
                current_list = "patterns"
            continue
        if key in {"id", "severity", "message", "category"}:
            assert current_rule is not None
            current_rule[key] = value
            current_list = "rules"
            continue
        _raise_policy_format_error(path, line_number)

    rules: list[GuardPolicyRule] = []
    for rule_payload in rule_payloads:
        rule_id = _optional_str(rule_payload.get("id"))
        if rule_id is None:
            _raise_policy_format_error(path, 0)
        assert rule_id is not None
        rules.append(
            GuardPolicyRule(
                id=rule_id,
                severity=_severity(str(rule_payload.get("severity", "medium"))),
                message=str(rule_payload.get("message", f"Policy rule `{rule_id}` matched.")),
                category=str(rule_payload.get("category", "policy")),
                patterns=_split_list(rule_payload.get("patterns")),
            )
        )

    return GuardPolicy(
        profile=profile,
        block_at=_severity(block_at),
        review_at=_severity(review_at),
        required_fields=required_fields,
        rules=rules,
    )


def _raise_policy_format_error(path: Path, line_number: int) -> None:
    location = f"{path}:{line_number}" if line_number else str(path)
    msg = (
        f"Invalid guard policy format near {location}. "
        "Supported guard policy formats are flat keys such as "
        "`rule.destructive_action.patterns: delete database|drop table` "
        "or the minimal nested form `rules:` with `- id: ...` entries."
    )
    raise ValueError(msg)


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
    """Detect built-in prompt risks using bounded heuristic rules.

    The findings are preflight governance signals, not proof that an agent
    action is safe or unsafe.
    """

    lowered = prompt.lower()
    read_only_docs = _looks_like_read_only_docs(prompt, lowered)
    violations: list[GuardViolation] = []
    if _destructive_change(prompt, lowered, read_only_docs):
        violations.append(
            GuardViolation(
                id="destructive_operation",
                severity="high",
                category="destructive_change",
                message="Prompt asks for a destructive change.",
                source="builtin",
            )
        )
    if _security_sensitive_change(prompt, lowered, read_only_docs):
        violations.append(
            GuardViolation(
                id="security_sensitive",
                severity="high",
                category="security",
                message="Prompt changes authentication, permissions, credentials, or secrets.",
                source="builtin",
            )
        )
    if _data_exposure(prompt, lowered):
        violations.append(
            GuardViolation(
                id="data_exposure",
                severity="high",
                category="data_exposure",
                message="Prompt may expose private data or environment values.",
                source="builtin",
            )
        )
    if _broad_refactor(prompt, lowered):
        violations.append(
            GuardViolation(
                id="broad_refactor",
                severity="medium",
                category="broad_refactor",
                message="Prompt requests a broad refactor without tight scope.",
                source="builtin",
            )
        )
    if _production_change(prompt, lowered, read_only_docs):
        violations.append(
            GuardViolation(
                id="production_path",
                severity="high",
                category="production_path",
                message="Prompt changes production, billing, payment, or deployment paths.",
                source="builtin",
            )
        )
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


def _destructive_change(prompt: str, lowered: str, read_only_docs: bool) -> bool:
    if read_only_docs:
        return False
    direct = [
        "delete database",
        "drop table",
        "remove migration",
        "delete all",
        "remove auth",
        "delete auth",
        "删除数据库",
        "删库",
        "删除所有",
        "移除认证",
        "删除认证",
        "关闭权限",
        "删除迁移",
    ]
    if _has_non_negated_phrase(prompt, direct):
        return True
    return _has_non_negated_action_object_pair(
        prompt,
        _risk_actions(),
        ["database", "table", "migration", "数据库", "数据表", "迁移"],
    )


def _security_sensitive_change(prompt: str, lowered: str, read_only_docs: bool) -> bool:
    if read_only_docs:
        return False
    direct = [
        "remove auth",
        "delete auth",
        "disable auth",
        "disable permission",
        "移除认证",
        "删除认证",
        "移除登录验证",
        "关闭登录验证",
        "关闭认证",
        "关闭权限",
        "移除权限",
    ]
    if _has_non_negated_phrase(prompt, direct):
        return True
    return _has_non_negated_action_object_pair(
        prompt,
        _risk_actions(),
        [
            "auth",
            "authentication",
            "authorization",
            "permission",
            "permissions",
            "token",
            "tokens",
            "secret",
            "secrets",
            "credential",
            "credentials",
            "api key",
            "api keys",
            "认证",
            "权限",
            "令牌",
            "密钥",
            "凭证",
            "登录验证",
        ],
    )


def _data_exposure(prompt: str, lowered: str) -> bool:
    return _has_non_negated_phrase(
        prompt,
        [
            "dump database",
            "export user data",
            "print env",
            "print environment",
            "show env",
            "泄露密钥",
            "打印环境变量",
            "导出用户数据",
            "导出数据库",
        ],
    )


def _broad_refactor(prompt: str, lowered: str) -> bool:
    return _has_non_negated_phrase(
        prompt,
        [
            "refactor whole repo",
            "rewrite all",
            "rewrite entire",
            "重构整个仓库",
            "重写全部",
            "重写整个",
        ],
    )


def _production_change(prompt: str, lowered: str, read_only_docs: bool) -> bool:
    if read_only_docs:
        return False
    return _has_non_negated_action_object_pair(
        prompt,
        _risk_actions(),
        [
            "prod",
            "production",
            "billing",
            "payment",
            "deploy",
            "deployment",
            "生产环境",
            "生产",
            "账单",
            "支付",
            "部署",
        ],
    )


def _risk_actions() -> list[str]:
    return [
        "delete",
        "drop",
        "remove",
        "disable",
        "change",
        "modify",
        "migrate",
        "deploy",
        "rewrite",
        "删除",
        "删",
        "移除",
        "关闭",
        "修改",
        "变更",
        "迁移",
        "部署",
        "重写",
    ]


def _looks_like_read_only_docs(prompt: str, lowered: str) -> bool:
    return _has_any(prompt, lowered, ["docs/", ".md", "documentation", "文档"]) and _has_any(
        prompt,
        lowered,
        ["clarify", "explain", "document", "comment", "note", "说明", "解释", "注释"],
    )


def _has_any(prompt: str, lowered: str, tokens: list[str]) -> bool:
    return any(token in (lowered if token.isascii() else prompt) for token in tokens)


def _has_non_negated_phrase(prompt: str, phrases: list[str]) -> bool:
    normalized = prompt.lower()
    for phrase in phrases:
        for match in _phrase_matches(normalized, phrase):
            if not _is_negated(normalized, match.start()):
                return True
    return False


def _has_non_negated_action_object_pair(
    prompt: str,
    actions: list[str],
    objects: list[str],
) -> bool:
    clauses = re.split(r"[,\r\n.!?;:\uff0c\u3002\uff01\uff1f\uff1b\uff1a]+", prompt.lower())
    for clause in clauses:
        object_matches = [
            match
            for object_name in objects
            for match in _phrase_matches(clause, object_name)
        ]
        if not object_matches:
            continue
        for action in actions:
            for match in _phrase_matches(clause, action):
                if _is_negated(clause, match.start()):
                    continue
                if any(_match_gap(match, object_match) <= 48 for object_match in object_matches):
                    return True
    return False


def _phrase_matches(text: str, phrase: str) -> list[re.Match[str]]:
    escaped = re.escape(phrase.lower())
    pattern = rf"(?<!\w){escaped}(?!\w)" if phrase.isascii() else escaped
    return list(re.finditer(pattern, text))


def _match_gap(left: re.Match[str], right: re.Match[str]) -> int:
    if left.end() < right.start():
        return right.start() - left.end()
    if right.end() < left.start():
        return left.start() - right.end()
    return 0


def _is_negated(text: str, start: int) -> bool:
    prefix = text[max(0, start - 160) : start]
    scope = re.split(
        r"(?:[\r\n.!?;:\u3002\uff01\uff1f\uff1b\uff1a]|\bbut\b|\bhowever\b|\bthen\b|\u4f46\u662f|\u4f46|\u7136\u540e)",
        prefix,
    )[-1]
    if re.search(
        r"(?:\b(?:do\s+not|don't|never)\s+(?:forget|fail|hesitate)\s+to\b|"
        r"\b(?:avoid|without)\s+(?:forgetting|failing|hesitating)\s+to\b|"
        r"(?:\u4e0d\u8981|\u522b|\u4e0d\u5f97|\u5207\u52ff)(?:\u5fd8\u8bb0|\u5fd8\u4e86|\u72b9\u8c6b)(?:\u53bb|\u8981)?)"
        r".{0,120}$",
        scope,
    ):
        return False
    return bool(
        re.search(
            r"(?:\bdo\s+not\b|\bdon't\b|\bmust\s+not\b|\bnever\b|\bavoid\b|"
            r"\bwithout\b|\u4e0d\u8981|\u4e0d\u5f97|\u7981\u6b62|\u907f\u514d|\u65e0\u9700|\u4e0d\u80fd|\u4e0d\u5e94)"
            r".{0,120}$",
            scope,
        )
    )


def _looks_like_coding_prompt(lowered: str) -> bool:
    return any(
        token in lowered
        for token in ["bug", "fix", "code", "refactor", ".py", ".js", ".ts", ".md", "module"]
    ) or any(token in lowered for token in ["修复", "代码", "重构", "模块"])


def _has_required_field(prompt: str, field_name: str) -> bool:
    lowered = prompt.lower()
    if field_name == "target_files":
        return bool(re.search(r"[\w./\\-]+\.(py|js|ts|tsx|md|json|ya?ml|toml|sql)", lowered))
    if field_name == "failing_behavior":
        return any(
            token in lowered
            for token in [
                "fail",
                "error",
                "bug",
                "traceback",
                "exception",
                "expected",
                "actual",
                "失败",
                "错误",
                "异常",
                "预期",
                "实际",
            ]
        )
    if field_name == "test_plan":
        return any(
            token in lowered
            for token in ["test", "pytest", "verify", "check", "validate", "测试", "验证", "检查"]
        )
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


def _unquote(value: str) -> str:
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def _severity(value: str) -> str:
    if value not in SEVERITY_RANK:
        msg = f"Expected severity low, medium, or high, got {value!r}"
        raise ValueError(msg)
    return value
