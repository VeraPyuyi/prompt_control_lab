"""Markdown and HTML renderers for ecosystem demo artifacts."""

from __future__ import annotations

import html

from promptcontrollab.core.files import JsonDict


def _render_scorecard(payload: JsonDict) -> str:
    """Render the reviewer-facing ecosystem scorecard as Markdown."""

    lines = [
        "# Ecosystem Scorecard",
        "",
        str(payload.get("positioning", "")),
        "",
        "## PCL-added evidence matrix",
        "",
        (
            "| Tool | Prompt-only validity | Paired stats | Evidence card | Claim check | "
            "Research bundle | Bundle verification | Gap status | Missing diagnostics | "
            "Next command |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    matrix_rows = payload.get("pcl_evidence_matrix")
    if isinstance(matrix_rows, list):
        for row in matrix_rows:
            if not isinstance(row, dict):
                continue
            missing = row.get("missing_paper_diagnostics")
            missing_text = (
                ", ".join(str(item) for item in missing)
                if isinstance(missing, list)
                else str(missing or "")
            )
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row.get("display_name", "")),
                        str(row.get("prompt_only_validity", "")),
                        str(row.get("paired_stats", "")),
                        _artifact_status_markdown(
                            row.get("evidence_card"),
                            row.get("evidence_card_path"),
                        ),
                        _artifact_status_markdown(
                            row.get("claim_check"),
                            row.get("claim_check_path"),
                        ),
                        _artifact_status_markdown(
                            row.get("research_bundle"),
                            row.get("research_bundle_path"),
                        ),
                        str(row.get("bundle_verification", "")),
                        str(row.get("gap_status", "")),
                        missing_text,
                        f"`{row.get('next_command', '')}`",
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Cross-tool summary",
            "",
            (
                "| Tool | External strength | What PCL adds | Validity | Evidence tier | "
                "Gap status | Bundle integrity | Reviewer artifacts | Missing paper diagnostics |"
            ),
            "|---|---|---|---|---|---|---|---|---|",
        ]
    )
    rows = payload.get("rows")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            missing = row.get("missing_paper_diagnostics")
            missing_text = (
                ", ".join(str(item) for item in missing)
                if isinstance(missing, list)
                else str(missing or "")
            )
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row.get("display_name", "")),
                        str(row.get("external_strength", "")),
                        str(row.get("pcl_adds", "")),
                        str(row.get("validity", "")),
                        str(row.get("evidence_tier", "")),
                        str(row.get("gap_status", "")),
                        _bundle_integrity_markdown(row.get("research_bundle_integrity")),
                        _artifact_links_markdown(row.get("artifact_links")),
                        missing_text,
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Gap closure commands",
            "",
            "| Tool | Open first | Gap status command |",
            "|---|---|---|",
        ]
    )
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            gap_status = str(row.get("gap_status", ""))
            if row.get("gap_missing_count") is not None:
                gap_status = f"{gap_status} ({row.get('gap_missing_count')} missing)"
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row.get("display_name", "")),
                        f"`{row.get('open_first', '')}`",
                        f"{gap_status}; `{row.get('gap_status_command', '')}`",
                    ]
                )
                + " |"
            )
    readiness = payload.get("market_readiness")
    if isinstance(readiness, dict):
        lines.extend(_market_readiness_markdown_lines(readiness))
    market_map = payload.get("market_map")
    lines.extend(
        [
            "",
            "## Extended market map (not imported in this demo)",
            "",
            (
                "These rows are positioning references only. They are not imported evidence "
                "bundles and should not be used as direct benchmark results."
            ),
            "",
            (
                "| Tool | Strong lane | What PCL should learn | What PCL still owns | "
                "PCL product move | Priority | Status |"
            ),
            "|---|---|---|---|---|---|---|",
        ]
    )
    if isinstance(market_map, list):
        for row in market_map:
            if not isinstance(row, dict):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row.get("tool", "")),
                        str(row.get("strong_lane", "")),
                        str(row.get("pcl_should_learn", "")),
                        str(row.get("pcl_owns", "")),
                        str(row.get("pcl_product_move", "")),
                        str(row.get("priority", "")),
                        str(row.get("status", "")),
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Recommended review order",
            "",
            *[f"- {item}" for item in _string_list(payload.get("recommended_review_order"))],
            "",
            "## Boundary",
            "",
            str(payload.get("boundary", "")),
            "",
        ]
    )
    return "\n".join(lines)


def _market_readiness_markdown_lines(readiness: JsonDict) -> list[str]:
    lines = [
        "",
        "## Market readiness",
        "",
        f"- Status: `{readiness.get('status', '')}`",
        f"- Recommended positioning: {readiness.get('recommended_positioning', '')}",
        "- Best first users:",
        *[f"  - {item}" for item in _string_list(readiness.get("best_first_users"))],
        "- Do not build:",
        *[f"  - {item}" for item in _string_list(readiness.get("do_not_build"))],
        "- Next moves:",
    ]
    next_moves = readiness.get("next_moves")
    if isinstance(next_moves, list):
        for item in next_moves:
            if not isinstance(item, dict):
                continue
            lines.append(
                "  - "
                f"{item.get('priority', '')} {item.get('tool', '')}: "
                f"{item.get('move', '')}"
            )
    return lines


def _artifact_status_markdown(status: object, path: object) -> str:
    status_text = str(status or "")
    path_text = str(path or "")
    if path_text:
        return f"{status_text}: [{path_text}]({path_text})"
    return status_text


def _artifact_links_markdown(value: object) -> str:
    if not isinstance(value, list):
        return ""
    links: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "")
        path = str(item.get("path") or "")
        if label and path:
            links.append(f"[{label}]({path})")
    return "<br>".join(links)


def _render_scorecard_html(payload: JsonDict) -> str:
    """Render the reviewer-facing ecosystem scorecard as standalone HTML."""

    rows = _scorecard_html_rows(payload.get("rows"))
    matrix_rows = _scorecard_html_rows(payload.get("pcl_evidence_matrix"))
    market_rows = _scorecard_html_rows(payload.get("market_map"))
    readiness = payload.get("market_readiness")
    readiness_html = (
        _render_market_readiness_html(readiness) if isinstance(readiness, dict) else ""
    )
    summary = _scorecard_summary(rows)
    matrix_table_rows = "\n".join(_render_matrix_html_row(row) for row in matrix_rows)
    table_rows = "\n".join(_render_scorecard_html_row(row) for row in rows)
    market_table_rows = "\n".join(_render_market_map_html_row(row) for row in market_rows)
    review_items = "\n".join(
        f"<li>{_html_text(item)}</li>"
        for item in _string_list(payload.get("recommended_review_order"))
    )
    boundary = _html_text(payload.get("boundary", ""))
    positioning = _html_text(payload.get("positioning", ""))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>prompt_control_lab Ecosystem Scorecard</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f8fb;
      --panel: #ffffff;
      --ink: #18212f;
      --muted: #667085;
      --line: #d9e1ec;
      --blue: #2563eb;
      --green-bg: #eaf8ef;
      --green: #166534;
      --amber-bg: #fff7df;
      --amber: #92400e;
      --red-bg: #feecec;
      --red: #991b1b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 15px/1.55 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
    }}
    main {{
      max-width: 1220px;
      margin: 0 auto;
      padding: 40px 24px 56px;
    }}
    .hero {{
      background: linear-gradient(135deg, #ffffff 0%, #eef5ff 100%);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 28px;
      box-shadow: 0 14px 38px rgba(24, 33, 47, 0.08);
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: clamp(28px, 4vw, 46px);
      line-height: 1.05;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 34px 0 14px;
      font-size: 22px;
      letter-spacing: 0;
    }}
    p {{ margin: 0; color: var(--muted); }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 14px;
      margin-top: 22px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 16px;
    }}
    .card strong {{
      display: block;
      font-size: 28px;
      line-height: 1;
      margin-bottom: 8px;
    }}
    .card span {{ color: var(--muted); }}
    .table-wrap {{
      overflow-x: auto;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 12px;
    }}
    table {{
      width: 100%;
      min-width: 1280px;
      border-collapse: collapse;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 12px 14px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #f0f4fa;
      color: #344054;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    code {{
      display: inline-block;
      max-width: 280px;
      overflow-wrap: anywhere;
      padding: 2px 6px;
      border-radius: 6px;
      background: #eef2f7;
      color: #26364d;
      font-size: 12px;
    }}
    a {{ color: var(--blue); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .badge {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 3px 9px;
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }}
    .good {{ background: var(--green-bg); color: var(--green); }}
    .warn {{ background: var(--amber-bg); color: var(--amber); }}
    .bad {{ background: var(--red-bg); color: var(--red); }}
    .neutral {{ background: #edf2f7; color: #475467; }}
    .muted {{ color: var(--muted); }}
    .two-col {{
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(260px, 0.8fr);
      gap: 18px;
    }}
    @media (max-width: 900px) {{
      .two-col {{ grid-template-columns: 1fr; }}
      main {{ padding: 22px 14px 40px; }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>Ecosystem Scorecard</h1>
      <p>{positioning}</p>
      <div class="summary">
        <div class="card">
          <strong>{summary["tool_count"]}</strong><span>tools imported</span>
        </div>
        <div class="card">
          <strong>{summary["valid_count"]}</strong><span>valid evidence rows</span>
        </div>
        <div class="card">
          <strong>{summary["needs_work_count"]}</strong><span>gap rows needing work</span>
        </div>
        <div class="card">
          <strong>{summary["missing_diagnostic_count"]}</strong><span>missing diagnostics</span>
        </div>
      </div>
    </section>

    <h2>PCL-added evidence matrix</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Tool</th>
            <th>Prompt-only validity</th>
            <th>Paired stats</th>
            <th>Evidence card</th>
            <th>Claim check</th>
            <th>Research bundle</th>
            <th>Bundle verification</th>
            <th>Gap status</th>
            <th>Missing diagnostics</th>
            <th>Next command</th>
          </tr>
        </thead>
        <tbody>
          {matrix_table_rows}
        </tbody>
      </table>
    </div>

    <h2>Cross-tool positioning</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Tool</th>
            <th>External strength</th>
            <th>What PCL adds</th>
            <th>Validity</th>
            <th>Evidence</th>
            <th>Gap</th>
            <th>Bundle integrity</th>
            <th>Reviewer artifacts</th>
            <th>Missing diagnostics</th>
            <th>Open first</th>
            <th>Next command</th>
          </tr>
        </thead>
        <tbody>
          {table_rows}
        </tbody>
      </table>
    </div>

    <section class="two-col">
      <div>
        <h2>Recommended review order</h2>
        <div class="card"><ol>{review_items}</ol></div>
      </div>
      <div>
        <h2>Boundary</h2>
        <div class="card"><p>{boundary}</p></div>
      </div>
    </section>

    {readiness_html}

    <h2>Extended market map (not imported in this demo)</h2>
    <p>
      These rows are positioning references only. They are not imported evidence bundles
      and should not be used as direct benchmark results.
    </p>
    <div class="table-wrap" style="margin-top: 14px;">
      <table>
        <thead>
          <tr>
            <th>Tool</th>
            <th>Strong lane</th>
            <th>What PCL should learn</th>
            <th>What PCL still owns</th>
            <th>PCL product move</th>
            <th>Priority</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {market_table_rows}
        </tbody>
      </table>
    </div>
  </main>
</body>
</html>
"""


def _render_market_readiness_html(readiness: JsonDict) -> str:
    """Render market-readiness evidence and next actions as HTML."""

    next_moves = readiness.get("next_moves")
    move_rows = ""
    if isinstance(next_moves, list):
        move_rows = "\n".join(
            _render_market_readiness_move_html(item)
            for item in next_moves
            if isinstance(item, dict)
        )
    return f"""
    <h2>Market readiness</h2>
    <section class="two-col">
      <div class="card">
        <p><strong>Status:</strong> <code>{_html_text(readiness.get("status", ""))}</code></p>
        <p style="margin-top: 12px;">{_html_text(readiness.get("recommended_positioning", ""))}</p>
      </div>
      <div class="card">
        <p><strong>Best first users</strong></p>
        {_html_unordered_list(readiness.get("best_first_users"))}
        <p style="margin-top: 12px;"><strong>Do not build</strong></p>
        {_html_unordered_list(readiness.get("do_not_build"))}
      </div>
    </section>
    <div class="table-wrap" style="margin-top: 14px;">
      <table>
        <thead>
          <tr><th>Priority</th><th>Tool</th><th>Next move</th></tr>
        </thead>
        <tbody>{move_rows}</tbody>
      </table>
    </div>
"""


def _render_market_readiness_move_html(row: JsonDict) -> str:
    return (
        "<tr>"
        f"<td>{_html_text(row.get('priority', ''))}</td>"
        f"<td><strong>{_html_text(row.get('tool', ''))}</strong></td>"
        f"<td>{_html_text(row.get('move', ''))}</td>"
        "</tr>"
    )


def _html_unordered_list(value: object) -> str:
    items = _string_list(value)
    if not items:
        return "<p class=\"muted\">None recorded.</p>"
    return "<ul>" + "".join(f"<li>{_html_text(item)}</li>" for item in items) + "</ul>"


def _scorecard_html_rows(value: object) -> list[JsonDict]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _scorecard_summary(rows: list[JsonDict]) -> JsonDict:
    return {
        "tool_count": len(rows),
        "valid_count": sum(1 for row in rows if str(row.get("validity")) == "valid"),
        "needs_work_count": sum(
            1 for row in rows if str(row.get("gap_status")) == "needs_work"
        ),
        "missing_diagnostic_count": sum(
            len(row.get("missing_paper_diagnostics", []))
            for row in rows
            if isinstance(row.get("missing_paper_diagnostics"), list)
        ),
    }


def _render_matrix_html_row(row: JsonDict) -> str:
    missing = row.get("missing_paper_diagnostics")
    missing_text = (
        ", ".join(str(item) for item in missing)
        if isinstance(missing, list)
        else str(missing or "")
    )
    return (
        "<tr>"
        f"<td><strong>{_html_text(row.get('display_name', ''))}</strong></td>"
        f"<td>{_html_badge(row.get('prompt_only_validity'))}</td>"
        f"<td>{_html_badge(row.get('paired_stats'))}</td>"
        f"<td>{_html_artifact_status(row.get('evidence_card'), row.get('evidence_card_path'))}</td>"
        f"<td>{_html_artifact_status(row.get('claim_check'), row.get('claim_check_path'))}</td>"
        "<td>"
        f"{_html_artifact_status(row.get('research_bundle'), row.get('research_bundle_path'))}"
        "</td>"
        f"<td>{_html_badge(row.get('bundle_verification'))}</td>"
        f"<td>{_html_badge(row.get('gap_status'))}</td>"
        f"<td class=\"muted\">{_html_text(missing_text)}</td>"
        f"<td><code>{_html_text(row.get('next_command', ''))}</code></td>"
        "</tr>"
    )


def _render_scorecard_html_row(row: JsonDict) -> str:
    missing = row.get("missing_paper_diagnostics")
    missing_text = (
        ", ".join(str(item) for item in missing)
        if isinstance(missing, list)
        else str(missing or "")
    )
    gap_status = str(row.get("gap_status") or "")
    if row.get("gap_missing_count") is not None:
        gap_status = f"{gap_status} ({row.get('gap_missing_count')} missing)"
    return (
        "<tr>"
        f"<td><strong>{_html_text(row.get('display_name', ''))}</strong></td>"
        f"<td>{_html_text(row.get('external_strength', ''))}</td>"
        f"<td>{_html_text(row.get('pcl_adds', ''))}</td>"
        f"<td>{_html_badge(row.get('validity'))}</td>"
        f"<td>{_html_badge(row.get('evidence_tier'))}</td>"
        f"<td>{_html_badge(gap_status)}</td>"
        f"<td>{_html_text(_bundle_integrity_markdown(row.get('research_bundle_integrity')))}</td>"
        f"<td>{_html_artifact_links(row.get('artifact_links'))}</td>"
        f"<td class=\"muted\">{_html_text(missing_text)}</td>"
        f"<td>{_html_link(row.get('open_first'))}</td>"
        f"<td><code>{_html_text(row.get('gap_status_command', ''))}</code></td>"
        "</tr>"
    )


def _render_market_map_html_row(row: JsonDict) -> str:
    return (
        "<tr>"
        f"<td><strong>{_html_text(row.get('tool', ''))}</strong></td>"
        f"<td>{_html_text(row.get('strong_lane', ''))}</td>"
        f"<td>{_html_text(row.get('pcl_should_learn', ''))}</td>"
        f"<td>{_html_text(row.get('pcl_owns', ''))}</td>"
        f"<td>{_html_text(row.get('pcl_product_move', ''))}</td>"
        f"<td>{_html_badge(row.get('priority'))}</td>"
        f"<td>{_html_badge(row.get('status'))}</td>"
        "</tr>"
    )


def _html_artifact_links(value: object) -> str:
    if not isinstance(value, list):
        return ""
    links: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "")
        path = str(item.get("path") or "")
        if label and path:
            links.append(_html_link_with_label(path=path, label=label))
    return "<br>".join(links)


def _html_artifact_status(status: object, path: object) -> str:
    status_html = _html_badge(status)
    path_text = str(path or "")
    if not path_text:
        return status_html
    return f"{status_html}<br>{_html_link(path_text)}"


def _bundle_integrity_markdown(value: object) -> str:
    if not isinstance(value, dict) or not value:
        return ""
    status = str(value.get("status") or "")
    present = value.get("present_artifact_count")
    total = value.get("artifact_count")
    hashed = value.get("hashed_artifact_count")
    missing = value.get("missing_html_count")
    verification = value.get("verification_status") or "not_checked"
    mismatches = value.get("verification_mismatch_count", 0)
    missing_verified = value.get("verification_missing_count", 0)
    return (
        f"{status}; present {present}/{total}; hashed {hashed}; "
        f"verify {verification}; mismatches {mismatches}; missing {missing_verified}; "
        f"missing html {missing}"
    )


def _html_badge(value: object) -> str:
    text = str(value or "")
    return f'<span class="badge {_html_status_class(text)}">{_html_text(text)}</span>'


def _html_status_class(value: str) -> str:
    normalized = value.lower()
    if any(item in normalized for item in ["valid", "complete", "pass", "clean"]):
        return "good"
    if any(item in normalized for item in ["fail", "invalid", "blocked"]):
        return "bad"
    if any(
        item in normalized
        for item in ["needs", "missing", "unknown", "not_checked", "review"]
    ):
        return "warn"
    return "neutral"


def _html_link(value: object) -> str:
    text = str(value or "")
    if not text:
        return ""
    escaped = html.escape(text, quote=True)
    return f'<a href="{escaped}">{html.escape(text)}</a>'


def _html_link_with_label(*, path: str, label: str) -> str:
    escaped = html.escape(path, quote=True)
    return f'<a href="{escaped}">{_html_text(label)}</a>'


def _html_text(value: object) -> str:
    return html.escape(str(value or ""))


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _render_readme(payload: JsonDict) -> str:
    """Render the compact README bundled with one ecosystem demo run."""

    lines = [
        "# prompt_control_lab Ecosystem Demo",
        "",
        (
            "This directory shows how `prompt_control_lab` works as a prompt optimization "
            "evidence auditor for exports from Promptfoo, DeepEval, Langfuse, LangSmith, "
            "and prompt-optimizer."
        ),
        "",
        "It does not replace those tools. It adds paired statistics, prompt-only validity, "
        "evidence cards, claim checks, and research-diagnostic hooks on top of their exports.",
        "",
        (
            "Start with `ecosystem_scorecard.html` for the cross-tool positioning and "
            "gap-closure view. Use `ecosystem_scorecard.md` for plain-text review."
        ),
        "",
        "## Generated bundles",
        "",
        "| Tool | Validity | Evidence tier | Claim check | Open first |",
        "|---|---|---|---|---|",
    ]
    runs = payload.get("runs")
    if isinstance(runs, list):
        for run in runs:
            if not isinstance(run, dict):
                continue
            tool = run.get("tool", "")
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(tool),
                        str(run.get("validity", "")),
                        str(run.get("evidence_tier", "")),
                        str(run.get("claim_check_status", "")),
                        f"[bridge_summary.html]({tool}/bridge_summary.html)",
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Suggested review order",
            "",
            "1. Open `bridge_summary.html` for each tool.",
            "2. Open `research_bundle.html` for reviewer navigation.",
            "3. Check `evidence_card.html` for protocol and statistical evidence.",
            "4. Check `claim_check.html` before making any prompt optimization claim.",
            "5. Read `research_diagnostics.html` for paper-evidence gap coverage.",
            "6. Run `pcl gap-status --run <tool-dir>` after closing diagnostic gaps.",
            "7. Open `report.html` or `pcl ui --runs <this-dir>` for a visual review.",
            "",
        ]
    )
    return "\n".join(lines)
