"""Rendering helpers for external evidence bridge artifacts."""

from __future__ import annotations

import html

from promptcontrollab.core.files import JsonDict


def _render_bridge_summary(payload: JsonDict) -> str:
    """Render an external evidence bridge summary as Markdown."""

    lines = [
        "# External Evidence Bridge Summary",
        "",
        f"- Requested tool: `{payload.get('requested_tool')}`",
        f"- Detected tools: `{payload.get('detected_tools', [])}`",
        f"- Recommendation: `{payload.get('recommendation')}`",
        f"- Evidence tier: `{payload.get('evidence_tier')}`",
        f"- Claim scope: {payload.get('claim_scope')}",
        f"- Safe claim language: {payload.get('claim_language')}",
        f"- Validity: `{payload.get('validity')}`",
        f"- Paired n: `{payload.get('paired_n')}`",
        f"- Mean delta: `{payload.get('mean_delta')}`",
        f"- Bootstrap CI: `{payload.get('bootstrap_ci')}`",
        f"- Permutation p-value: `{payload.get('permutation_p_value')}`",
        f"- Holm-adjusted p-value: `{payload.get('holm_adjusted_p_value')}`",
        "",
        "## Source input provenance",
        "",
        "| Role | Tool | Path | Path kind | Resolved path | Bytes | SHA-256 | Imported rows |",
        "|---|---|---|---|---|---:|---|---:|",
        *_source_input_markdown_rows(payload.get("source_inputs")),
        "",
        "## Tool roles",
        "",
    ]
    roles = payload.get("source_tool_roles")
    if isinstance(roles, list):
        for role in roles:
            if not isinstance(role, dict):
                continue
            lines.extend(
                [
                    f"### {role.get('display_name') or role.get('tool')}",
                    "",
                    f"- External tool role: {role.get('role')}",
                    f"- What PCL adds: {role.get('pcl_adds')}",
                    "",
                ]
            )
    lines.extend(
        [
            "## PCL added evidence",
            "",
            *[f"- `{item}`" for item in _string_list(payload.get("pcl_added_evidence"))],
            "",
            "## Research diagnostics",
            "",
        ]
    )
    bundle_path = payload.get("research_bundle_html_path")
    research_path = payload.get("research_diagnostics_html_path") or payload.get(
        "research_diagnostics_md_path"
    )
    if research_path:
        gap_plan_path = payload.get("research_gap_plan_html_path") or payload.get(
            "research_gap_plan_md_path",
            "",
        )
        integrity = _bridge_bundle_integrity_lines(payload.get("research_bundle_integrity"))
        lines.extend(
            [
                f"- Bundle index: `{bundle_path or ''}`",
                *integrity,
                f"- Report: `{research_path}`",
                f"- Diagnostic type: `{payload.get('research_diagnostic_type')}`",
                f"- Missing paper diagnostics: `{payload.get('missing_paper_diagnostics', [])}`",
                f"- Gap plan: `{gap_plan_path}`",
                f"- Commands: `{payload.get('research_gap_commands_ps1_path', '')}`",
                "",
            ]
        )
        remediation_rows = _remediation_rows(payload.get("paper_gap_remediation"))
        if remediation_rows:
            lines.extend(
                [
                    "### How to close paper-evidence gaps",
                    "",
                    "| Missing diagnostic | Command | Artifact |",
                    "|---|---|---|",
                    *remediation_rows,
                    "",
                ]
            )
    else:
        lines.extend(
            [
                "- Research diagnostics have not been generated for this bridge yet.",
                "",
            ]
        )
    lines.extend(
        [
            "## Missing or review evidence",
            "",
            f"- Missing evidence: `{payload.get('missing_evidence', [])}`",
            f"- Missing for next tier: `{payload.get('next_tier_missing', [])}`",
            f"- Review items: `{payload.get('review_items', [])}`",
            f"- Blocking issues: `{payload.get('blocking_issues', [])}`",
            "",
            "## Next actions",
            "",
            *[f"- {item}" for item in _string_list(payload.get("next_actions"))],
            "",
            "## Boundary",
            "",
            str(payload.get("boundary", "")),
            "",
        ]
    )
    return "\n".join(lines)


def _render_evidence_audit_markdown(payload: JsonDict) -> str:
    """Render source, bundle, and gate verification details as Markdown."""

    gap = payload.get("gap_status")
    verification = payload.get("bundle_verification")
    source_verification = payload.get("source_verification")
    evidence_gate = payload.get("evidence_gate")
    gap_summary = gap if isinstance(gap, dict) else {}
    verification_summary = verification if isinstance(verification, dict) else {}
    source_summary = source_verification if isinstance(source_verification, dict) else {}
    evidence_gate_summary = evidence_gate if isinstance(evidence_gate, dict) else {}
    lines = [
        "# External Evidence Audit Summary",
        "",
        f"- Tool: `{payload.get('tool')}`",
        f"- Claim scope: `{payload.get('claim_scope')}`",
        f"- Evidence tier: `{payload.get('evidence_tier')}`",
        f"- Prompt-only validity: `{payload.get('validity')}`",
        f"- Gap status: `{gap_summary.get('status')}`",
        f"- Missing paper diagnostics: `{payload.get('missing_paper_diagnostics', [])}`",
        f"- Source input verification: `{source_summary.get('status')}`",
        f"- Evidence gate: `{evidence_gate_summary.get('status', 'not_recorded')}`",
        (
            f"- Source verification counts: checked `{source_summary.get('checked_count')}`, "
            f"mismatch `{source_summary.get('mismatch_count')}`, "
            f"missing `{source_summary.get('missing_count')}`"
        ),
        f"- Bundle verification: `{verification_summary.get('status')}`",
        (
            f"- Verification counts: checked `{verification_summary.get('checked_count')}`, "
            f"mismatch `{verification_summary.get('mismatch_count')}`, "
            f"missing `{verification_summary.get('missing_count')}`"
        ),
        "",
        "## Source input provenance",
        "",
        "| Role | Tool | Path | Path kind | Resolved path | Bytes | SHA-256 | Imported rows |",
        "|---|---|---|---|---|---:|---|---:|",
        *_source_input_markdown_rows(payload.get("source_inputs")),
        "",
        "## Reviewer links",
        "",
        f"- Evidence audit HTML: `{payload.get('html_path')}`",
        f"- Bridge summary: `{payload.get('bridge_summary_html_path')}`",
        f"- Research bundle: `{payload.get('research_bundle_path')}`",
        f"- Research diagnostics: `{payload.get('research_diagnostics_path')}`",
        f"- Gap status: `{payload.get('research_gap_status_path')}`",
        f"- Source input verification: `{payload.get('source_input_verification_path')}`",
        f"- Bundle verification: `{payload.get('research_bundle_verification_path')}`",
        f"- Evidence gate: `{payload.get('evidence_gate_path')}`",
        "",
        "## What this audit did",
        "",
        "- Imported external baseline and candidate exports.",
        "- Built paired prompt-optimization comparison evidence.",
        "- Checked whether the comparison is valid as prompt-only evidence.",
        "- Checked paper-derived diagnostic gaps.",
        "- Verified original external export files against recorded source-input hashes.",
        "- Verified the research bundle against recorded artifact hashes.",
        "",
        "## Next actions",
        "",
        *[f"- {item}" for item in _string_list(payload.get("next_actions"))],
        "",
        "## Boundary",
        "",
        str(payload.get("boundary", "")),
        "",
    ]
    return "\n".join(lines)


def render_evidence_audit_html(payload: JsonDict) -> str:
    """Render the top-level ``pcl evidence-audit`` summary as HTML."""

    gap = payload.get("gap_status")
    verification = payload.get("bundle_verification")
    source_verification = payload.get("source_verification")
    evidence_gate = payload.get("evidence_gate")
    gap_summary = gap if isinstance(gap, dict) else {}
    verification_summary = verification if isinstance(verification, dict) else {}
    source_summary = source_verification if isinstance(source_verification, dict) else {}
    evidence_gate_summary = evidence_gate if isinstance(evidence_gate, dict) else {}
    cards = "\n".join(
        [
            _html_card("Tool", payload.get("tool")),
            _html_card("Evidence tier", payload.get("evidence_tier")),
            _html_card("Validity", payload.get("validity")),
            _html_card("Gap status", gap_summary.get("status")),
            _html_card("Missing diagnostics", gap_summary.get("missing_count")),
            _html_card("Source verification", source_summary.get("status")),
            _html_card("Bundle verification", verification_summary.get("status")),
            _html_card("Evidence gate", evidence_gate_summary.get("status", "not_recorded")),
        ]
    )
    reviewer_links = " ".join(
        item
        for item in [
            _html_link(payload.get("bridge_summary_html_path"), "Bridge summary"),
            _html_link(payload.get("research_bundle_path"), "Research bundle"),
            _html_link(payload.get("research_diagnostics_path"), "Research diagnostics"),
            _html_link(payload.get("research_gap_status_path"), "Gap status"),
            _html_link(
                payload.get("source_input_verification_path"),
                "Source input verification",
            ),
            _html_link(
                payload.get("research_bundle_verification_path"),
                "Bundle verification",
            ),
            _html_link(payload.get("evidence_gate_path"), "Evidence gate"),
        ]
        if item
    )
    source_table = _html_table(
        ["Role", "Tool", "Path", "Path kind", "Resolved path", "Bytes", "SHA-256", "Imported rows"],
        _source_input_html_rows(payload.get("source_inputs")),
        empty="No source input provenance recorded.",
    )
    audit_steps = [
        "Imported external baseline and candidate exports.",
        "Built paired prompt-optimization comparison evidence.",
        "Checked whether the comparison is valid as prompt-only evidence.",
        "Checked paper-derived diagnostic gaps.",
        "Verified original external export files against recorded source-input hashes.",
        "Verified the research bundle against recorded artifact hashes.",
    ]
    steps_html = "".join(f"<li>{_html_text(item)}</li>" for item in audit_steps)
    next_actions = "".join(
        f"<li>{_html_text(item)}</li>" for item in _string_list(payload.get("next_actions"))
    )
    missing = _html_text(payload.get("missing_paper_diagnostics", []))
    verification_counts = (
        f"checked {verification_summary.get('checked_count')}, "
        f"mismatch {verification_summary.get('mismatch_count')}, "
        f"missing {verification_summary.get('missing_count')}"
    )
    source_counts = (
        f"checked {source_summary.get('checked_count')}, "
        f"mismatch {source_summary.get('mismatch_count')}, "
        f"missing {source_summary.get('missing_count')}"
    )
    body = f"""
    <section class="hero">
      <p class="eyebrow">prompt_control_lab evidence audit</p>
      <h1>External Evidence Audit Summary</h1>
      <p>{_html_text(payload.get("claim_scope"))}</p>
    </section>
    <section class="cards">{cards}</section>
    <section>
      <h2>Source Input Provenance</h2>
      {source_table}
    </section>
    <section>
      <h2>Reviewer Links</h2>
      <p>{reviewer_links}</p>
    </section>
    <section>
      <h2>What This Audit Did</h2>
      <ol>{steps_html}</ol>
    </section>
    <section>
      <h2>Paper Diagnostic Gaps</h2>
      <p><strong>Missing paper diagnostics:</strong> {missing}</p>
      <p><strong>Source verification counts:</strong> {_html_text(source_counts)}</p>
      <p><strong>Bundle verification counts:</strong> {_html_text(verification_counts)}</p>
    </section>
    <section>
      <h2>Next Actions</h2>
      <ol>{next_actions}</ol>
    </section>
    <section>
      <h2>Boundary</h2>
      <p>{_html_text(payload.get("boundary"))}</p>
    </section>
    """
    return _html_page(title="External Evidence Audit Summary", body=body)


def _render_source_input_verification_markdown(payload: JsonDict) -> str:
    lines = [
        "# Source Input Verification",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Source artifact: `{payload.get('source_artifact')}`",
        f"- Checked: `{payload.get('checked_count')}`",
        f"- OK: `{payload.get('ok_count')}`",
        f"- Mismatch: `{payload.get('mismatch_count')}`",
        f"- Missing: `{payload.get('missing_count')}`",
        f"- Unchecked: `{payload.get('unchecked_count')}`",
        "",
        "## Results",
        "",
        (
            "| Role | Tool | Status | Path | Resolved path | Expected SHA-256 | "
            "Actual SHA-256 | Bytes |"
        ),
        "|---|---|---|---|---|---|---|---:|",
        *_source_verification_markdown_rows(payload.get("results")),
        "",
        "## Boundary",
        "",
        str(payload.get("boundary", "")),
        "",
    ]
    return "\n".join(lines)


def render_source_input_verification_html(payload: JsonDict) -> str:
    """Render source input hash verification as a reviewer-facing HTML page."""

    cards = "\n".join(
        [
            _html_card("Status", payload.get("status")),
            _html_card("Checked", payload.get("checked_count")),
            _html_card("OK", payload.get("ok_count")),
            _html_card("Mismatch", payload.get("mismatch_count")),
            _html_card("Missing", payload.get("missing_count")),
            _html_card("Unchecked", payload.get("unchecked_count")),
        ]
    )
    rows = _source_verification_html_rows(payload.get("results"))
    table = _html_table(
        [
            "Role",
            "Tool",
            "Status",
            "Path",
            "Resolved path",
            "Expected SHA-256",
            "Actual SHA-256",
            "Bytes",
        ],
        rows,
        empty="No source input verification rows recorded.",
    )
    body = f"""
    <section class="hero">
      <p class="eyebrow">prompt_control_lab source input verification</p>
      <h1>Source Input Verification</h1>
      <p>Verifies whether original external export files still match recorded SHA-256 values.</p>
    </section>
    <section class="cards">{cards}</section>
    <section>
      <h2>Results</h2>
      {table}
    </section>
    <section>
      <h2>Boundary</h2>
      <p>{_html_text(payload.get("boundary"))}</p>
    </section>
    """
    return _html_page(title="Source Input Verification", body=body)


def render_bridge_summary_html(payload: JsonDict) -> str:
    """Render a reviewer-facing HTML summary for an external evidence bridge."""

    roles = payload.get("source_tool_roles")
    role_rows = []
    if isinstance(roles, list):
        for role in roles:
            if not isinstance(role, dict):
                continue
            display = _html_text(role.get("display_name") or role.get("tool"))
            role_rows.append(
                "<tr>"
                f"<td><strong>{display}</strong></td>"
                f"<td>{_html_text(role.get('role'))}</td>"
                f"<td>{_html_text(role.get('pcl_adds'))}</td>"
                "</tr>"
            )
    role_table = _html_table(
        ["Tool", "External tool role", "What PCL adds"],
        role_rows,
        empty="No external tool roles recorded.",
    )
    source_table = _html_table(
        ["Role", "Tool", "Path", "Path kind", "Resolved path", "Bytes", "SHA-256", "Imported rows"],
        _source_input_html_rows(payload.get("source_inputs")),
        empty="No source input provenance recorded.",
    )
    evidence_items = "".join(
        f"<li><code>{_html_text(item)}</code></li>"
        for item in _string_list(payload.get("pcl_added_evidence"))
    )
    integrity = _bridge_bundle_integrity_lines(payload.get("research_bundle_integrity"))
    integrity_items = "".join(f"<li>{_markdownish_to_html(item)}</li>" for item in integrity)
    remediation_rows = _remediation_html_rows(payload.get("paper_gap_remediation"))
    remediation_table = _html_table(
        ["Missing diagnostic", "Command", "Artifact"],
        remediation_rows,
        empty="No paper-evidence gap remediation commands recorded.",
    )
    next_actions = "".join(
        f"<li>{_html_text(item)}</li>" for item in _string_list(payload.get("next_actions"))
    )
    cards = "\n".join(
        [
            _html_card("Recommendation", payload.get("recommendation")),
            _html_card("Evidence tier", payload.get("evidence_tier")),
            _html_card("Validity", payload.get("validity")),
            _html_card("Paired n", payload.get("paired_n")),
            _html_card("Mean delta", payload.get("mean_delta")),
            _html_card("Permutation p-value", payload.get("permutation_p_value")),
        ]
    )
    bundle_link = _html_link(payload.get("research_bundle_html_path"), "Research bundle")
    diagnostics_link = _html_link(
        payload.get("research_diagnostics_html_path")
        or payload.get("research_diagnostics_md_path"),
        "Research diagnostics",
    )
    gap_plan_link = _html_link(
        payload.get("research_gap_plan_html_path") or payload.get("research_gap_plan_md_path"),
        "Gap plan",
    )
    missing_paper = _html_text(payload.get("missing_paper_diagnostics", []))
    next_tier = _html_text(payload.get("next_tier_missing", []))
    body = f"""
    <section class="hero">
      <p class="eyebrow">prompt_control_lab external evidence bridge</p>
      <h1>External Evidence Bridge Summary</h1>
      <p>{_html_text(payload.get("claim_scope"))}</p>
    </section>
    <section class="cards">{cards}</section>
    <section>
      <h2>Source Input Provenance</h2>
      {source_table}
    </section>
    <section>
      <h2>Tool Roles</h2>
      {role_table}
    </section>
    <section>
      <h2>PCL Added Evidence</h2>
      <ul>{evidence_items}</ul>
    </section>
    <section>
      <h2>Research Diagnostics</h2>
      <p>{bundle_link} {diagnostics_link} {gap_plan_link}</p>
      <ul>{integrity_items}</ul>
      <p><strong>Diagnostic type:</strong> {_html_text(payload.get("research_diagnostic_type"))}</p>
      <p><strong>Missing paper diagnostics:</strong> {missing_paper}</p>
      {remediation_table}
    </section>
    <section>
      <h2>Missing Or Review Evidence</h2>
      <p><strong>Missing evidence:</strong> {_html_text(payload.get("missing_evidence", []))}</p>
      <p><strong>Missing for next tier:</strong> {next_tier}</p>
      <p><strong>Review items:</strong> {_html_text(payload.get("review_items", []))}</p>
      <p><strong>Blocking issues:</strong> {_html_text(payload.get("blocking_issues", []))}</p>
    </section>
    <section>
      <h2>Next Actions</h2>
      <ol>{next_actions}</ol>
    </section>
    <section>
      <h2>Boundary</h2>
      <p>{_html_text(payload.get("boundary"))}</p>
    </section>
    """
    return _html_page(title="External Evidence Bridge Summary", body=body)


def _html_page(*, title: str, body: str) -> str:
    """Wrap rendered external evidence content in a standalone HTML page."""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_html_text(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f8fafc;
      --panel: #ffffff;
      --ink: #0f172a;
      --muted: #64748b;
      --line: #dbe4ef;
      --accent: #2563eb;
    }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system,
        BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--ink);
      line-height: 1.55;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 40px 24px 64px;
    }}
    section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 24px;
      margin: 18px 0;
      box-shadow: 0 12px 32px rgba(15, 23, 42, 0.06);
    }}
    .hero {{
      background: linear-gradient(135deg, #ffffff 0%, #eef6ff 100%);
    }}
    .eyebrow {{
      text-transform: uppercase;
      letter-spacing: .08em;
      color: var(--accent);
      font-size: 13px;
      font-weight: 700;
    }}
    h1 {{ font-size: 34px; margin: 8px 0 12px; }}
    h2 {{ font-size: 20px; margin-top: 0; }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
      background: transparent;
      border: 0;
      box-shadow: none;
      padding: 0;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 18px;
    }}
    .label {{ color: var(--muted); font-size: 12px; font-weight: 700; text-transform: uppercase; }}
    .value {{ margin-top: 8px; font-size: 18px; font-weight: 700; overflow-wrap: anywhere; }}
    table {{
      border-collapse: collapse;
      width: 100%;
      margin-top: 12px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 10px 8px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ color: var(--muted); font-size: 13px; }}
    code {{
      background: #eef2f7;
      border-radius: 6px;
      padding: 2px 6px;
      overflow-wrap: anywhere;
    }}
    a {{ color: var(--accent); font-weight: 700; text-decoration: none; margin-right: 14px; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <main>{body}</main>
</body>
</html>
"""


def _html_card(label: str, value: object) -> str:
    return (
        '<div class="card">'
        f'<div class="label">{_html_text(label)}</div>'
        f'<div class="value">{_html_text(value)}</div>'
        "</div>"
    )


def _html_table(headers: list[str], rows: list[str], *, empty: str) -> str:
    if not rows:
        return f"<p>{_html_text(empty)}</p>"
    header_html = "".join(f"<th>{_html_text(header)}</th>" for header in headers)
    return (
        "<table><thead><tr>"
        + header_html
        + "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _html_link(path: object, label: str) -> str:
    text = str(path or "")
    if not text:
        return ""
    return f'<a href="{html.escape(text, quote=True)}">{_html_text(label)}</a>'


def _html_text(value: object) -> str:
    return html.escape(str(value or ""))


def _markdownish_to_html(text: str) -> str:
    return _html_text(text).replace("`", "")


def _remediation_html_rows(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    rows: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        rows.append(
            "<tr>"
            f"<td>{_html_text(item.get('missing_diagnostic'))}</td>"
            f"<td><code>{_html_text(item.get('command'))}</code></td>"
            f"<td>{_html_text(item.get('expected_artifact'))}</td>"
            "</tr>"
        )
    return rows


def _source_input_markdown_rows(value: object) -> list[str]:
    if not isinstance(value, list):
        return ["| _missing_ |  |  |  |  |  |  |  |"]
    rows: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        rows.append(
            "| "
            f"{_markdown_cell(item.get('role'))} | "
            f"{_markdown_cell(item.get('source_tool'))} | "
            f"`{_markdown_cell(item.get('path'))}` | "
            f"{_markdown_cell(item.get('path_kind'))} | "
            f"`{_markdown_cell(item.get('resolved_path'))}` | "
            f"{_markdown_cell(item.get('bytes'))} | "
            f"`{_markdown_cell(item.get('sha256'))}` | "
            f"{_markdown_cell(item.get('import_count'))} |"
        )
    return rows or ["| _missing_ |  |  |  |  |  |  |  |"]


def _source_input_html_rows(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    rows: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        rows.append(
            "<tr>"
            f"<td>{_html_text(item.get('role'))}</td>"
            f"<td>{_html_text(item.get('source_tool'))}</td>"
            f"<td><code>{_html_text(item.get('path'))}</code></td>"
            f"<td>{_html_text(item.get('path_kind'))}</td>"
            f"<td><code>{_html_text(item.get('resolved_path'))}</code></td>"
            f"<td>{_html_text(item.get('bytes'))}</td>"
            f"<td><code>{_html_text(item.get('sha256'))}</code></td>"
            f"<td>{_html_text(item.get('import_count'))}</td>"
            "</tr>"
        )
    return rows


def _source_verification_markdown_rows(value: object) -> list[str]:
    if not isinstance(value, list):
        return ["| _missing_ |  |  |  |  |  |  |  |"]
    rows: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        rows.append(
            "| "
            f"{_markdown_cell(item.get('role'))} | "
            f"{_markdown_cell(item.get('source_tool'))} | "
            f"{_markdown_cell(item.get('status'))} | "
            f"`{_markdown_cell(item.get('path'))}` | "
            f"`{_markdown_cell(item.get('resolved_path'))}` | "
            f"`{_markdown_cell(item.get('expected_sha256'))}` | "
            f"`{_markdown_cell(item.get('actual_sha256'))}` | "
            f"{_markdown_cell(item.get('bytes'))} |"
        )
    return rows or ["| _missing_ |  |  |  |  |  |  |  |"]


def _source_verification_html_rows(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    rows: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        rows.append(
            "<tr>"
            f"<td>{_html_text(item.get('role'))}</td>"
            f"<td>{_html_text(item.get('source_tool'))}</td>"
            f"<td><strong>{_html_text(item.get('status'))}</strong></td>"
            f"<td><code>{_html_text(item.get('path'))}</code></td>"
            f"<td><code>{_html_text(item.get('resolved_path'))}</code></td>"
            f"<td><code>{_html_text(item.get('expected_sha256'))}</code></td>"
            f"<td><code>{_html_text(item.get('actual_sha256'))}</code></td>"
            f"<td>{_html_text(item.get('bytes'))}</td>"
            "</tr>"
        )
    return rows


def _markdown_cell(value: object) -> str:
    text = str(value or "")
    return text.replace("|", "\\|").replace("\n", " ")


def _bridge_bundle_integrity_lines(value: object) -> list[str]:
    if not isinstance(value, dict) or not value:
        return []
    return [
        f"- Bundle integrity: `{value.get('status')}`",
        (
            f"- Bundle artifacts: `{value.get('present_artifact_count')}/"
            f"{value.get('artifact_count')}` present, "
            f"`{value.get('hashed_artifact_count')}` hashed"
        ),
        (
            f"- Bundle verification: `{value.get('verification_status', 'not_checked')}` "
            f"({value.get('verification_mismatch_count', 0)} mismatches, "
            f"{value.get('verification_missing_count', 0)} missing)"
        ),
        f"- Missing HTML artifacts: `{value.get('missing_html_artifacts', [])}`",
    ]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _remediation_rows(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    rows: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        rows.append(
            "| "
            + " | ".join(
                [
                    str(item.get("concept", "")),
                    f"`{item.get('command', '')}`",
                    f"`{item.get('artifact', '')}`",
                ]
            )
            + " |"
        )
    return rows
