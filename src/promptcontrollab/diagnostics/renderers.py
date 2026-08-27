"""Markdown, HTML, and SVG renderers for research diagnostic summaries."""

from __future__ import annotations

import html
from pathlib import Path

from promptcontrollab.core.files import JsonDict
from promptcontrollab.diagnostics.common import _remediation_list
from promptcontrollab.diagnostics.constants import PAPER_MAPPING
from promptcontrollab.diagnostics.interpretation import (
    _plain_language_research_insights,
    _research_at_a_glance,
)


def render_research_diagnostics_markdown(payload: JsonDict) -> str:
    """Render a readable research diagnostics report."""

    diagnostics = payload.get("diagnostics", {})
    if not isinstance(diagnostics, dict):
        diagnostics = {}
    lines = [
        "# Research Diagnostics Report",
        "",
        "This report summarizes paper-derived PromptControlLab diagnostics.",
        "",
        "## At a glance",
        "",
        "| Field | Value |",
        "|---|---|",
    ]
    for key, value in _research_at_a_glance(payload).items():
        lines.append(f"| {key.replace('_', ' ')} | {value} |")
    lines.extend(
        [
            "",
            "## Visual Overview",
            "",
            "![Research overview](research_overview.svg)",
            "",
        ]
    )
    lines.extend(
        [
            "## Plain-language interpretation",
            "",
            "| Diagnostic | Checks | Result | Interpretation | Next action |",
            "|---|---|---|---|---|",
        ]
    )
    for row in _plain_language_research_insights(payload):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("diagnostic", "")),
                    str(row.get("checks", "")),
                    str(row.get("result", "")),
                    str(row.get("interpretation", "")),
                    str(row.get("next_action", "")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Paper Concept Map",
            "",
            "| Concept | Commands | Artifact | Meaning |",
            "|---|---|---|---|",
        ]
    )
    for item in PAPER_MAPPING:
        lines.append(
            "| {concept} | `{commands}` | `{artifact}` | {meaning} |".format(
                concept=item["concept"],
                commands="`, `".join(item["commands"]),
                artifact=item["artifact"],
                meaning=item["meaning"],
            )
        )
    lines.extend(["", "## Diagnostic Results", ""])
    ecosystem = diagnostics.get("ecosystem_bridge", {})
    if isinstance(ecosystem, dict) and ecosystem:
        lines.extend(
            [
                "### Ecosystem evidence gap diagnosis",
                "",
                (
                    "| Tool | Validity | Evidence tier | Claim check | "
                    "Missing paper diagnostics | Open first |"
                ),
                "|---|---|---|---|---|---|",
            ]
        )
        rows = ecosystem.get("runs")
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                missing = row.get("missing_paper_diagnostics", [])
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            str(row.get("display_name") or row.get("tool")),
                            str(row.get("validity")),
                            str(row.get("evidence_tier")),
                            str(row.get("claim_check_status")),
                            ", ".join(str(item) for item in missing)
                            if isinstance(missing, list)
                            else str(missing),
                            str(row.get("bridge_summary_path") or ""),
                        ]
                    )
                    + " |"
                )
        remediation = ecosystem.get("paper_gap_remediation")
        lines.extend(_render_remediation_table(remediation))
        lines.extend([""])
    external = diagnostics.get("external_bridge", {})
    if isinstance(external, dict) and external:
        lines.extend(
            [
                "### External evidence gap diagnosis",
                "",
                f"- Tool: `{external.get('display_name') or external.get('tool')}`",
                f"- Validity: `{external.get('validity')}`",
                f"- Evidence tier: `{external.get('evidence_tier')}`",
                f"- Claim check: `{external.get('claim_check_status')}`",
                f"- Missing paper diagnostics: `{external.get('missing_paper_diagnostics', [])}`",
                "",
            ]
        )
        lines.extend(_render_remediation_table(external.get("paper_gap_remediation")))
    inputs = payload.get("inputs", {})
    inputs_dict = inputs if isinstance(inputs, dict) else {}
    hidden_input = inputs_dict.get("hidden_states")
    if isinstance(hidden_input, dict):
        lines.extend(
            [
                "### Hidden-state input",
                "",
                f"- Source: `{hidden_input.get('source')}`",
                f"- Path: `{hidden_input.get('path')}`",
                f"- Model id: `{hidden_input.get('model_id')}`",
                f"- States shape: `{hidden_input.get('states_shape')}`",
                f"- Pool: `{hidden_input.get('pool')}`",
                "",
            ]
        )
    soft = diagnostics.get("soft_hard", {})
    if isinstance(soft, dict) and soft:
        lines.extend(
            [
                "### Soft-to-hard projection gap",
                "",
                f"- Risk: `{soft.get('risk')}`",
                f"- Mean projection distance: `{soft.get('mean_projection_distance')}`",
                f"- Max projection distance: `{soft.get('max_projection_distance')}`",
                "",
            ]
        )
    trajectory = diagnostics.get("trajectory", {})
    if isinstance(trajectory, dict) and trajectory:
        lines.extend(
            [
                "### Hidden-state trajectory",
                "",
                f"- Turnpike-like signal: `{trajectory.get('turnpike_like_signal')}`",
                f"- Log-decay slope: `{trajectory.get('log_decay_slope')}`",
                f"- Decay fit R2: `{trajectory.get('decay_r2')}`",
                "",
            ]
        )
    riccati = diagnostics.get("riccati", {})
    if isinstance(riccati, dict) and riccati:
        lines.extend(
            [
                "### Riccati surrogate",
                "",
                f"- Stable surrogate: `{riccati.get('stable_surrogate')}`",
                f"- Closed-loop spectral radius: `{riccati.get('closed_loop_spectral_radius')}`",
                "",
            ]
        )
    tv_soft = diagnostics.get("tv_soft", {})
    if isinstance(tv_soft, dict) and tv_soft:
        lines.extend(
            [
                "### Time-varying soft-control lane",
                "",
                f"- Method means: `{tv_soft.get('method_means')}`",
                f"- Delta vs baseline: `{tv_soft.get('delta_vs_baseline')}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Boundary",
            "",
            str(payload.get("boundary", "")),
            "",
        ]
    )
    return "\n".join(lines)


def render_research_diagnostics_html(payload: JsonDict) -> str:
    """Render the paper-derived diagnostics summary as browser-friendly HTML."""

    diagnostics = payload.get("diagnostics", {})
    if not isinstance(diagnostics, dict):
        diagnostics = {}
    body: list[str] = [
        _paragraph("This report summarizes paper-derived PromptControlLab diagnostics."),
        _section(
            "At a Glance",
            _metric_grid(
                [
                    (key.replace("_", " "), value)
                    for key, value in _research_at_a_glance(payload).items()
                ]
            ),
        ),
        _section(
            "Visual Overview",
            '<img class="overview" src="research_overview.svg" alt="Research diagnostic overview">',
        ),
        _section(
            "Plain-language Interpretation",
            _table(
                ["Diagnostic", "Checks", "Result", "Interpretation", "Next action"],
                [
                    [
                        row.get("diagnostic", ""),
                        row.get("checks", ""),
                        row.get("result", ""),
                        row.get("interpretation", ""),
                        row.get("next_action", ""),
                    ]
                    for row in _plain_language_research_insights(payload)
                ],
            ),
        ),
        _section(
            "Paper Concept Map",
            _table(
                ["Concept", "Commands", "Artifact", "Meaning"],
                [
                    [
                        item["concept"],
                        ", ".join(str(command) for command in item["commands"]),
                        item["artifact"],
                        item["meaning"],
                    ]
                    for item in PAPER_MAPPING
                ],
            ),
        ),
    ]
    ecosystem = diagnostics.get("ecosystem_bridge", {})
    if isinstance(ecosystem, dict) and ecosystem:
        rows = []
        raw_rows = ecosystem.get("runs")
        if isinstance(raw_rows, list):
            for row in raw_rows:
                if not isinstance(row, dict):
                    continue
                missing = row.get("missing_paper_diagnostics", [])
                rows.append(
                    [
                        row.get("display_name") or row.get("tool", ""),
                        row.get("validity", ""),
                        row.get("evidence_tier", ""),
                        row.get("claim_check_status", ""),
                        ", ".join(str(item) for item in missing)
                        if isinstance(missing, list)
                        else str(missing),
                        row.get("bridge_summary_path", ""),
                    ]
                )
        body.append(
            _section(
                "Ecosystem Evidence Gap Diagnosis",
                _table(
                    [
                        "Tool",
                        "Validity",
                        "Evidence tier",
                        "Claim check",
                        "Missing paper diagnostics",
                        "Open first",
                    ],
                    rows,
                )
                + _render_remediation_html(ecosystem.get("paper_gap_remediation")),
            )
        )
    external = diagnostics.get("external_bridge", {})
    if isinstance(external, dict) and external:
        body.append(
            _section(
                "External Evidence Gap Diagnosis",
                _metric_grid(
                    [
                        ("Tool", external.get("display_name") or external.get("tool", "")),
                        ("Validity", external.get("validity", "")),
                        ("Evidence tier", external.get("evidence_tier", "")),
                        ("Claim check", external.get("claim_check_status", "")),
                        (
                            "Missing diagnostics",
                            ", ".join(
                                str(item) for item in external.get("missing_paper_diagnostics", [])
                            ),
                        ),
                    ]
                )
                + _render_remediation_html(external.get("paper_gap_remediation")),
            )
        )
    inputs = payload.get("inputs", {})
    inputs_dict = inputs if isinstance(inputs, dict) else {}
    hidden_input = inputs_dict.get("hidden_states")
    if isinstance(hidden_input, dict):
        body.append(
            _section(
                "Hidden-state Input",
                _metric_grid(
                    [
                        ("Source", hidden_input.get("source", "")),
                        ("Path", hidden_input.get("path", "")),
                        ("Model id", hidden_input.get("model_id", "")),
                        ("States shape", hidden_input.get("states_shape", "")),
                        ("Pool", hidden_input.get("pool", "")),
                    ]
                ),
            )
        )
    soft = diagnostics.get("soft_hard", {})
    if isinstance(soft, dict) and soft:
        body.append(
            _section(
                "Soft-to-hard Projection Gap",
                _metric_grid(
                    [
                        ("Risk", _badge(str(soft.get("risk", "")))),
                        ("Mean projection distance", soft.get("mean_projection_distance", "")),
                        ("Max projection distance", soft.get("max_projection_distance", "")),
                    ]
                ),
            )
        )
    trajectory = diagnostics.get("trajectory", {})
    if isinstance(trajectory, dict) and trajectory:
        body.append(
            _section(
                "Hidden-state Trajectory",
                _metric_grid(
                    [
                        ("Turnpike-like signal", trajectory.get("turnpike_like_signal", "")),
                        ("Log-decay slope", trajectory.get("log_decay_slope", "")),
                        ("Decay fit R2", trajectory.get("decay_r2", "")),
                    ]
                ),
            )
        )
    riccati = diagnostics.get("riccati", {})
    if isinstance(riccati, dict) and riccati:
        body.append(
            _section(
                "Riccati Surrogate",
                _metric_grid(
                    [
                        ("Stable surrogate", riccati.get("stable_surrogate", "")),
                        (
                            "Closed-loop spectral radius",
                            riccati.get("closed_loop_spectral_radius", ""),
                        ),
                    ]
                ),
            )
        )
    tv_soft = diagnostics.get("tv_soft", {})
    if isinstance(tv_soft, dict) and tv_soft:
        body.append(
            _section(
                "Time-varying Soft-control Lane",
                _metric_grid(
                    [
                        ("Method means", tv_soft.get("method_means", "")),
                        ("Delta vs baseline", tv_soft.get("delta_vs_baseline", "")),
                    ]
                ),
            )
        )
    body.append(_section("Boundary", _paragraph(payload.get("boundary"))))
    return _html_page(
        title="Research Diagnostics Report",
        subtitle="Paper-derived prompt optimization diagnostics.",
        body=body,
    )


def render_research_overview_svg(payload: JsonDict) -> str:
    """Render a dependency-free SVG overview of paper-derived evidence coverage."""

    rows = _research_overview_rows(payload)
    height = 180 + ((len(rows) + 2) // 3) * 116
    cards = []
    for index, row in enumerate(rows):
        col = index % 3
        card_row = index // 3
        x = 44 + col * 372
        y = 132 + card_row * 116
        status = str(row["status"])
        color = _overview_status_color(status)
        cards.append(
            f"""
  <g>
    <rect x="{x}" y="{y}" width="328" height="88" rx="14" fill="#ffffff" stroke="#d8e0ec"/>
    <circle cx="{x + 30}" cy="{y + 30}" r="13" fill="{color["fill"]}" stroke="{color["stroke"]}"/>
    <text x="{x + 52}" y="{y + 34}" class="h">{_svg_text(row["label"])}</text>
    <text x="{x + 20}" y="{y + 64}" class="t">{_svg_text(row["meaning"])}</text>
    <text x="{x + 272}" y="{y + 34}" class="badge" fill="{color["text"]}">{_svg_text(status)}</text>
  </g>""".rstrip()
        )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}"
  viewBox="0 0 1200 {height}" role="img" aria-labelledby="title desc">
  <title id="title">prompt_control_lab research overview</title>
  <desc id="desc">Paper-derived prompt optimization evidence coverage: protocol,
  statistics, deployment, hidden-state trajectory, Riccati, and time-varying
  diagnostics.</desc>
  <style>
    .title {{ font: 700 30px Segoe UI, Arial, sans-serif; fill: #172033; }}
    .sub {{ font: 16px Segoe UI, Arial, sans-serif; fill: #61708a; }}
    .h {{ font: 700 17px Segoe UI, Arial, sans-serif; fill: #172033; }}
    .t {{ font: 14px Segoe UI, Arial, sans-serif; fill: #53657d; }}
    .badge {{ font: 700 12px Segoe UI, Arial, sans-serif; text-anchor: middle; }}
  </style>
  <rect width="1200" height="{height}" rx="24" fill="#f6f8fb"/>
  <rect x="26" y="26" width="1148" height="{height - 52}" rx="22" fill="#ffffff" stroke="#d8e0ec"/>
  <text x="54" y="74" class="title">Paper-derived prompt-control evidence</text>
  <text x="54" y="103" class="sub">From clean protocol to deployability,
  hidden-state dynamics, surrogate stability, and reviewer artifacts.</text>
{"".join(cards)}
</svg>
"""


def _research_overview_rows(payload: JsonDict) -> list[JsonDict]:
    """Build stable overview rows from the available diagnostic artifacts."""

    run_dir_value = payload.get("run_dir")
    run_dir = Path(str(run_dir_value)) if run_dir_value else None
    diagnostics = payload.get("diagnostics")
    diagnostics_dict = diagnostics if isinstance(diagnostics, dict) else {}
    return [
        {
            "label": "Tri-split protocol",
            "meaning": "train / val / withheld separation",
            "status": _overview_artifact_status(payload, run_dir, "splits.json"),
        },
        {
            "label": "Paired statistics",
            "meaning": "mean delta, CI, p-value",
            "status": _overview_artifact_status(payload, run_dir, "stats.json"),
        },
        {
            "label": "Soft-to-hard gap",
            "meaning": "deployment projection risk",
            "status": _overview_diagnostic_status(diagnostics_dict, "soft_hard"),
        },
        {
            "label": "Hidden-state input",
            "meaning": "trajectory-ready state source",
            "status": _overview_artifact_status(payload, run_dir, "inputs/hidden_states.npz"),
        },
        {
            "label": "Trajectory signal",
            "meaning": "drift and turnpike-like decay",
            "status": _overview_diagnostic_status(diagnostics_dict, "trajectory"),
        },
        {
            "label": "Riccati surrogate",
            "meaning": "finite-dimensional stability probe",
            "status": _overview_diagnostic_status(diagnostics_dict, "riccati"),
        },
        {
            "label": "TV soft-control",
            "meaning": "static / tv / shuffled / random",
            "status": _overview_diagnostic_status(diagnostics_dict, "tv_soft"),
        },
        {
            "label": "Terminal sensitivity",
            "meaning": "early response vs terminal distance",
            "status": _overview_diagnostic_status(diagnostics_dict, "terminal_sensitivity"),
        },
        {
            "label": "Green certificate",
            "meaning": "hyperbolicity and boundary margin",
            "status": _overview_diagnostic_status(diagnostics_dict, "green_certificate"),
        },
        {
            "label": "Posterior certificate",
            "meaning": "local residual and derivative bounds",
            "status": _overview_diagnostic_status(diagnostics_dict, "posterior_certificate"),
        },
        {
            "label": "Evidence card",
            "meaning": "reviewer-facing claim summary",
            "status": _overview_artifact_status(payload, run_dir, "evidence_card.json"),
        },
        {
            "label": "Claim check",
            "meaning": "bounded full-research claim gate",
            "status": _overview_artifact_status(payload, run_dir, "claim_check.json"),
        },
    ]


def _overview_diagnostic_status(diagnostics: JsonDict, key: str) -> str:
    value = diagnostics.get(key)
    if isinstance(value, dict) and value:
        return "ready"
    return "missing"


def _overview_artifact_status(payload: JsonDict, run_dir: Path | None, artifact: str) -> str:
    if run_dir is not None and (run_dir / artifact).exists():
        return "ready"
    artifacts = payload.get("artifacts")
    if isinstance(artifacts, dict):
        normalized = artifact.replace("\\", "/")
        for value in artifacts.values():
            value_text = str(value).replace("\\", "/")
            if value_text.endswith(normalized):
                return "ready"
    return "missing"


def _overview_status_color(status: str) -> dict[str, str]:
    if status == "ready":
        return {"fill": "#dcfce7", "stroke": "#86efac", "text": "#166534"}
    if status == "review":
        return {"fill": "#fef3c7", "stroke": "#fcd34d", "text": "#92400e"}
    return {"fill": "#fee2e2", "stroke": "#fca5a5", "text": "#991b1b"}


def _svg_text(value: object) -> str:
    return html.escape(str(value or ""))


def _render_remediation_table(value: object) -> list[str]:
    rows = _remediation_list(value)
    if not rows:
        return []
    lines = [
        "",
        "#### How to close these gaps",
        "",
        "| Missing diagnostic | Required inputs | Command | Artifact | What it explains |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        required = row.get("required_inputs")
        required_inputs = (
            ", ".join(str(item) for item in required) if isinstance(required, list) else ""
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("concept", "")),
                    required_inputs,
                    f"`{row.get('command', '')}`",
                    f"`{row.get('artifact', '')}`",
                    str(row.get("explains", "")),
                ]
            )
            + " |"
        )
    return lines


def _render_remediation_html(value: object) -> str:
    rows = _remediation_list(value)
    if not rows:
        return ""
    table_rows = []
    for row in rows:
        required = row.get("required_inputs")
        required_inputs = (
            ", ".join(str(item) for item in required) if isinstance(required, list) else ""
        )
        table_rows.append(
            [
                row.get("concept", ""),
                required_inputs,
                row.get("command", ""),
                row.get("artifact", ""),
                row.get("explains", ""),
            ]
        )
    return '<h3 class="subhead">How to close these gaps</h3>' + _table(
        ["Missing diagnostic", "Required inputs", "Command", "Artifact", "What it explains"],
        table_rows,
    )


def _html_page(*, title: str, subtitle: str, body: list[str]) -> str:
    """Render a self-contained research dashboard page from trusted fragments."""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_html_text(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #172033;
      --muted: #61708a;
      --line: #d8e0ec;
      --panel: #ffffff;
      --bg: #f6f8fb;
      --accent: #2463eb;
      --good-bg: #dcfce7;
      --good: #166534;
      --warn-bg: #fef3c7;
      --warn: #92400e;
      --bad-bg: #fee2e2;
      --bad: #991b1b;
    }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system,
        BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.55;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 40px 24px 56px; }}
    .hero {{
      background: linear-gradient(135deg, #ffffff, #edf4ff);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 28px 30px;
      box-shadow: 0 14px 40px rgba(25, 42, 70, 0.08);
    }}
    h1 {{ margin: 0 0 8px; font-size: 34px; letter-spacing: 0; }}
    h2 {{ margin: 0 0 16px; font-size: 22px; }}
    .subtitle {{ color: var(--muted); font-size: 16px; }}
    section {{
      margin-top: 22px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 22px;
      overflow: hidden;
    }}
    .subhead {{ margin: 18px 0 10px; font-size: 17px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 12px;
    }}
    .metric {{
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 14px;
      background: #fbfdff;
    }}
    .metric .label {{ color: var(--muted); font-size: 13px; margin-bottom: 6px; }}
    .metric .value {{ font-weight: 700; overflow-wrap: anywhere; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{
      padding: 11px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #f1f5fb;
      font-size: 12px;
      text-transform: uppercase;
      color: #44536a;
      letter-spacing: .04em;
    }}
    code {{ background: #eef2f7; border-radius: 6px; padding: 2px 5px; overflow-wrap: anywhere; }}
    .badge {{
      display: inline-block;
      border-radius: 999px;
      padding: 3px 9px;
      font-weight: 700;
      font-size: 12px;
    }}
    .good {{ background: var(--good-bg); color: var(--good); }}
    .warn {{ background: var(--warn-bg); color: var(--warn); }}
    .bad {{ background: var(--bad-bg); color: var(--bad); }}
    .neutral {{ background: #e2e8f0; color: #334155; }}
    .empty {{
      color: var(--muted);
      border: 1px dashed var(--line);
      border-radius: 12px;
      padding: 16px;
    }}
    .overview {{ width: 100%; height: auto; display: block; }}
    p {{ margin: 0 0 10px; }}
  </style>
</head>
<body>
<main>
  <div class="hero">
    <h1>{_html_text(title)}</h1>
    <div class="subtitle">{_html_text(subtitle)}</div>
  </div>
  {"".join(body)}
</main>
</body>
</html>
"""


def _section(title: str, body: str) -> str:
    return f"<section><h2>{_html_text(title)}</h2>{body}</section>"


def _metric_grid(items: list[tuple[str, object]]) -> str:
    cells = []
    for label, value in items:
        rendered = str(value) if _is_safe_html(value) else _html_text(_format_value(value))
        cells.append(
            '<div class="metric">'
            f'<div class="label">{_html_text(label)}</div>'
            f'<div class="value">{rendered}</div>'
            "</div>"
        )
    return '<div class="grid">' + "".join(cells) + "</div>"


def _table(headers: list[str], rows: list[list[object]]) -> str:
    if not rows:
        return '<div class="empty">No rows recorded.</div>'
    header_html = "".join(f"<th>{_html_text(header)}</th>" for header in headers)
    row_html = []
    for row in rows:
        cells = []
        for value in row:
            rendered = str(value) if _is_safe_html(value) else _html_text(_format_value(value))
            cells.append(f"<td>{rendered}</td>")
        row_html.append("<tr>" + "".join(cells) + "</tr>")
    return (
        '<div style="overflow-x:auto"><table><thead><tr>'
        + header_html
        + "</tr></thead><tbody>"
        + "".join(row_html)
        + "</tbody></table></div>"
    )


def _paragraph(value: object) -> str:
    text = _format_value(value)
    return f"<p>{_html_text(text)}</p>" if text else ""


def _bullet_list(value: object) -> str:
    if not isinstance(value, list) or not value:
        return '<div class="empty">No summary recorded.</div>'
    items = "".join(f"<li>{_html_text(_format_value(item))}</li>" for item in value)
    return f"<ul>{items}</ul>"


def _badge(value: str) -> str:
    lower = value.lower()
    if lower in {"pass", "passed", "present", "complete", "clean", "low", "supported", "true"}:
        css = "good"
    elif lower in {"fail", "failed", "missing", "high", "needs_work", "blocked", "false"}:
        css = "bad"
    elif lower in {"needs_review", "medium", "warning", "not_checked", "unknown"}:
        css = "warn"
    else:
        css = "neutral"
    return f'<span class="badge {css}">{_html_text(value)}</span>'


def _is_safe_html(value: object) -> bool:
    return isinstance(value, str) and (
        value.startswith('<span class="badge ') or value.startswith('<a href="')
    )


def _format_value(value: object) -> str:
    if isinstance(value, dict):
        return ", ".join(f"{key}: {item}" for key, item in value.items())
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value or "")


def _html_text(value: object) -> str:
    return html.escape(str(value or ""))


def _html_attr(value: object) -> str:
    return html.escape(str(value or ""), quote=True)
