"""Renderers for research bundle indexes and verification results."""

from __future__ import annotations

import html

from promptcontrollab.core.files import JsonDict
from promptcontrollab.diagnostics.renderers import (
    _badge,
    _bullet_list,
    _html_attr,
    _html_page,
    _html_text,
    _metric_grid,
    _paragraph,
    _section,
    _table,
)


def render_research_bundle_index_html(payload: JsonDict, *, language: str = "en") -> str:
    """Render the research bundle navigation page."""

    zh = language == "zh"
    review_order = payload.get("review_order")
    review_rows = []
    if isinstance(review_order, list):
        for item in review_order:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "")
            exists = bool(item.get("exists"))
            link = f'<a href="{_html_attr(path)}">{_html_text(path)}</a>' if exists else path
            review_rows.append(
                [
                    item.get("label", ""),
                    _badge("present" if exists else "missing"),
                    link,
                    item.get("explains", ""),
                ]
            )
    artifacts = payload.get("artifacts")
    artifact_rows = []
    if isinstance(artifacts, list):
        for item in artifacts:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "")
            exists = bool(item.get("exists"))
            link = f'<a href="{_html_attr(path)}">{_html_text(path)}</a>' if exists else path
            artifact_rows.append(
                [
                    item.get("role", ""),
                    _badge("present" if exists else "missing"),
                    link,
                    item.get("bytes", ""),
                    item.get("sha256") or item.get("hash_status", ""),
                ]
            )
    return _html_page(
        title="研究证据包" if zh else "Research Evidence Bundle",
        subtitle=(
            "论文 prompt optimization 证据的本地浏览入口。"
            if zh
            else "One browser entry point for paper-derived prompt optimization evidence."
        ),
        body=[
            _metric_grid(
                [
                    ("状态" if zh else "Status", _badge(str(payload.get("status", "")))),
                    (
                        "证据层级" if zh else "Evidence tier",
                        (
                            payload.get("evidence_tier_label_zh")
                            if zh
                            else payload.get("evidence_tier_label")
                        )
                        or payload.get("evidence_tier", ""),
                    ),
                    (
                        "主张检查" if zh else "Claim check",
                        _badge(str(payload.get("claim_check_status", ""))),
                    ),
                    (
                        "Gap 状态" if zh else "Gap status",
                        _badge(str(payload.get("gap_status", ""))),
                    ),
                    ("诊断类型" if zh else "Diagnostic type", payload.get("diagnostic_type", "")),
                ]
            ),
            _section(
                "这个证据包说明什么" if zh else "What this bundle tells you",
                _bullet_list(payload.get("plain_summary_zh" if zh else "plain_summary")),
            ),
            _section(
                "建议阅读顺序" if zh else "Review Order",
                _table(
                    (
                        ["步骤", "状态", "打开", "它说明什么"]
                        if zh
                        else ["Step", "Status", "Open", "What it explains"]
                    ),
                    review_rows,
                ),
            ),
            _section(
                "Artifact 清单" if zh else "Artifact Inventory",
                _table(
                    (
                        ["角色", "状态", "Artifact", "大小", "SHA-256 / hash 状态"]
                        if zh
                        else ["Role", "Status", "Artifact", "Bytes", "SHA-256 / hash status"]
                    ),
                    artifact_rows,
                ),
            ),
            _section(
                "安全主张表述" if zh else "Safe Claim Language",
                _paragraph(payload.get("claim_language")),
            ),
            _section(
                "边界" if zh else "Boundary",
                _paragraph(
                    (
                        "这个索引只是导航入口。它不会增加链接 artifact 之外的新证据, "
                        "也不证明科学充分性。"
                    )
                    if zh
                    else payload.get("boundary")
                ),
            ),
        ],
    )


def render_research_bundle_index_markdown(payload: JsonDict) -> str:
    """Render the research bundle navigation index as portable Markdown."""

    lines = [
        "# Research Evidence Bundle",
        "",
        f"- Status: `{_bundle_markdown_text(payload.get('status'))}`",
        f"- Evidence tier: `{_bundle_markdown_text(payload.get('evidence_tier'))}`",
        f"- Claim check: `{_bundle_markdown_text(payload.get('claim_check_status'))}`",
        f"- Gap status: `{_bundle_markdown_text(payload.get('gap_status'))}`",
        "",
        "## Review order",
        "",
        "| Step | Status | Artifact | What it explains |",
        "|---:|---|---|---|",
    ]
    review_order = payload.get("review_order")
    if isinstance(review_order, list):
        for step, item in enumerate(review_order, start=1):
            if not isinstance(item, dict):
                continue
            path = _bundle_markdown_text(item.get("path"))
            exists = bool(item.get("exists"))
            artifact = f"[{path}]({path})" if exists else path
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(step),
                        "present" if exists else "missing",
                        artifact,
                        _bundle_markdown_text(item.get("explains")),
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Safe claim language",
            "",
            _bundle_markdown_text(payload.get("claim_language")),
            "",
            "## Boundary",
            "",
            _bundle_markdown_text(payload.get("boundary")),
            "",
        ]
    )
    return "\n".join(lines)


def _bundle_markdown_text(value: object) -> str:
    return (
        html.escape(str(value or ""), quote=False)
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("|", r"\|")
        .replace("`", "&#96;")
    )


def _render_research_bundle_verification_markdown(payload: JsonDict) -> str:
    lines = [
        "# Research Bundle Verification",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Checked artifacts: `{payload.get('checked_count')}`",
        f"- OK: `{payload.get('ok_count')}`",
        f"- Mismatches: `{payload.get('mismatch_count')}`",
        f"- Missing: `{payload.get('missing_count')}`",
        f"- Unchecked: `{payload.get('unchecked_count')}`",
        "",
        "| Artifact | Status | Expected SHA-256 | Actual SHA-256 |",
        "|---|---|---|---|",
    ]
    for item in _verification_rows(payload.get("results")):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item.get("path", "")),
                    str(item.get("status", "")),
                    str(item.get("expected_sha256", "")),
                    str(item.get("actual_sha256", "")),
                ]
            )
            + " |"
        )
    lines.extend(["", str(payload.get("boundary", "")), ""])
    return "\n".join(lines)


def render_research_bundle_verification_html(payload: JsonDict) -> str:
    """Render research bundle hash verification as browser-friendly HTML."""

    rows = [
        [
            item.get("path", ""),
            _badge(str(item.get("status", ""))),
            item.get("expected_sha256", ""),
            item.get("actual_sha256", ""),
        ]
        for item in _verification_rows(payload.get("results"))
    ]
    return _html_page(
        title="Research Bundle Verification",
        subtitle="SHA-256 verification for linked paper-evidence artifacts.",
        body=[
            _metric_grid(
                [
                    ("Status", _badge(str(payload.get("status", "")))),
                    ("Checked", payload.get("checked_count", "")),
                    ("OK", payload.get("ok_count", "")),
                    ("Mismatches", payload.get("mismatch_count", "")),
                    ("Missing", payload.get("missing_count", "")),
                ]
            ),
            _section(
                "Artifact Hash Checks",
                _table(["Artifact", "Status", "Expected SHA-256", "Actual SHA-256"], rows),
            ),
            _section("Boundary", _paragraph(payload.get("boundary"))),
        ],
    )


def _verification_rows(value: object) -> list[JsonDict]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
