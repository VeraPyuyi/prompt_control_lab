"""Reviewer-facing reports for imported PEOC evidence."""

from __future__ import annotations

import html
import re

from promptcontrollab.core.files import JsonDict

_LANGUAGES = {"en", "zh"}


def render_peoc_case_study_markdown(payload: JsonDict, *, language: str) -> str:
    """Render a bounded PEOC evidence case study as Markdown."""

    labels = _labels(language)
    status_counts = _mapping(payload.get("status_counts"))
    hard_summary = _mapping(payload.get("hard_summary"))
    hard_rows = _rows(payload.get("hard_method_rows"))
    trajectory = _mapping(payload.get("selected_trajectory_pair"))
    stage = _mapping(payload.get("stage_validation"))
    limited_sections = _rows(payload.get("limited_sections"))
    inventory = _rows(payload.get("source_inventory"))
    limitations = _localized_values(payload, "limitations", language)
    safe_claim = _localized_value(payload, "safe_claim", language)
    boundary = _mapping(payload.get("claim_boundary"))

    lines = [
        f"# {labels['title']}",
        "",
        f"> **{_md(payload.get('evidence_source', 'REAL PEOC BUNDLE'))}**  ",
        f"> {labels['manifest_hash']}: `{_md(payload.get('manifest_hash', 'unknown'))}`",
        "",
        f"## {labels['status_summary']}",
        "",
        f"| {labels['status']} | {labels['count']} |",
        "|---|---:|",
    ]
    for status in _status_order(status_counts):
        lines.append(f"| `{_md(status.upper())}` | {_md(status_counts.get(status, 0))} |")

    lines.extend(
        [
            "",
            f"## {labels['hard_evaluation']}",
            "",
            (
                f"- {labels['metric']}: `{_md(hard_summary.get('metric', 'unknown'))}`  \n"
                f"- {labels['valid_rows']}: {_md(hard_summary.get('valid_row_count', 0))}  \n"
                f"- {labels['excluded_rows']}: "
                f"{_md(hard_summary.get('excluded_row_count', 0))}"
            ),
            "",
            (
                f"| {labels['model']} | {labels['task']} | {labels['method']} | "
                f"{labels['mean']} | {labels['sd']} | n |"
            ),
            "|---|---|---|---:|---:|---:|",
        ]
    )
    if hard_rows:
        for row in hard_rows:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md(row.get("model", "")),
                        _md(row.get("task", "")),
                        _md(row.get("method", "")),
                        _md(row.get("mean", "")),
                        _md(row.get("sd", "")),
                        _md(row.get("n", "")),
                    ]
                )
                + " |"
            )
    else:
        lines.append(f"| {labels['not_available']} |  |  |  |  |  |")

    lines.extend(["", f"## {labels['trajectory']}", ""])
    if trajectory:
        stationary = _mapping(trajectory.get("stationary"))
        heterogeneous = _mapping(trajectory.get("heterogeneous"))
        lines.extend(
            [
                f"- {labels['model']}: `{_md(trajectory.get('model', 'unknown'))}`",
                f"- {labels['seed']}: {_md(trajectory.get('seed', 'unknown'))}",
                "",
                (f"| {labels['trace']} | alpha | R2 | {labels['source']} |"),
                "|---|---:|---:|---|",
                (
                    f"| {labels['stationary']} | "
                    f"{_md(stationary.get('alpha_emp_mean', ''))} | "
                    f"{_md(stationary.get('R2_mean', ''))} | "
                    f"`{_md(stationary.get('relative_path', ''))}` |"
                ),
                (
                    f"| {labels['heterogeneous']} | "
                    f"{_md(heterogeneous.get('alpha_emp_mean', ''))} | "
                    f"{_md(heterogeneous.get('R2_mean', ''))} | "
                    f"`{_md(heterogeneous.get('relative_path', ''))}` |"
                ),
            ]
        )
    else:
        lines.append(labels["not_available"])

    lines.extend(
        [
            "",
            f"## {labels['stage_validation']}",
            "",
            f"- {labels['status']}: `{_md(stage.get('status', 'missing')).upper()}`",
            f"- {labels['verdict']}: `{_md(stage.get('verdict', 'unknown'))}`",
            (f"- {labels['held_rho']}: {_md(stage.get('held_spearman_rho', 'unknown'))}"),
            (f"- {labels['held_ci']}: {_md(_format_value(stage.get('held_bootstrap_ci')))}"),
            "",
            f"## {labels['evidence_limits']}",
            "",
            (
                f"| {labels['section']} | {labels['origin']} | "
                f"{labels['status']} | {labels['limitation']} |"
            ),
            "|---|---|---|---|",
        ]
    )
    if limited_sections:
        for row in limited_sections:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md(row.get("section", "")),
                        _md(row.get("origin", "")),
                        f"`{_md(row.get('status', '')).upper()}`",
                        _md(
                            row.get("limitation_zh", row.get("limitation", ""))
                            if language == "zh"
                            else row.get("limitation", "")
                        ),
                    ]
                )
                + " |"
            )
    else:
        lines.append(f"| {labels['none']} |  |  |  |")

    lines.extend(
        [
            "",
            f"## {labels['source_inventory']}",
            "",
            (f"| {labels['role']} | {labels['relative_path']} | SHA-256 | {labels['bytes']} |"),
            "|---|---|---|---:|",
        ]
    )
    for row in inventory:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md(row.get("role", "")),
                    f"`{_md(row.get('relative_path', ''))}`",
                    f"`{_md(row.get('sha256', ''))}`",
                    _md(row.get("bytes", "")),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            f"## {labels['safe_claim']}",
            "",
            _md(safe_claim),
            "",
            f"## {labels['limitations']}",
            "",
        ]
    )
    lines.extend(f"- {_md(value)}" for value in limitations)
    lines.extend(
        [
            "",
            f"## {labels['claim_boundary']}",
            "",
            (f"- {labels['full_support']}: `{_md(boundary.get('full_research_support', False))}`"),
            f"- {labels['boundary_status']}: `{_md(boundary.get('status', 'unknown'))}`",
            f"- {labels['statement']}: {_md(boundary.get('statement', ''))}",
            "",
        ]
    )
    return "\n".join(lines)


def render_peoc_case_study_html(payload: JsonDict, *, language: str) -> str:
    """Render a bounded PEOC evidence case study as self-contained HTML."""

    labels = _labels(language)
    status_counts = _mapping(payload.get("status_counts"))
    hard_summary = _mapping(payload.get("hard_summary"))
    hard_rows = _rows(payload.get("hard_method_rows"))
    trajectory = _mapping(payload.get("selected_trajectory_pair"))
    stage = _mapping(payload.get("stage_validation"))
    limited_sections = _rows(payload.get("limited_sections"))
    inventory = _rows(payload.get("source_inventory"))
    limitations = _localized_values(payload, "limitations", language)
    safe_claim = _localized_value(payload, "safe_claim", language)
    boundary = _mapping(payload.get("claim_boundary"))

    status_cards = "".join(
        (
            '<div class="metric">'
            f'<div class="metric-label">{_h(status.upper())}</div>'
            f'<div class="metric-value">{_h(status_counts.get(status, 0))}</div>'
            "</div>"
        )
        for status in _status_order(status_counts)
    )
    hard_table = _html_table(
        [
            labels["model"],
            labels["task"],
            labels["method"],
            labels["mean"],
            labels["sd"],
            "n",
        ],
        [
            [
                row.get("model", ""),
                row.get("task", ""),
                row.get("method", ""),
                row.get("mean", ""),
                row.get("sd", ""),
                row.get("n", ""),
            ]
            for row in hard_rows
        ],
        empty=labels["not_available"],
    )
    trajectory_html = _trajectory_html(trajectory, labels)
    limited_table = _html_table(
        [
            labels["section"],
            labels["origin"],
            labels["status"],
            labels["limitation"],
        ],
        [
            [
                row.get("section", ""),
                row.get("origin", ""),
                _status_html(row.get("status")),
                (
                    row.get("limitation_zh", row.get("limitation", ""))
                    if language == "zh"
                    else row.get("limitation", "")
                ),
            ]
            for row in limited_sections
        ],
        empty=labels["none"],
        safe_columns={2},
    )
    inventory_table = _html_table(
        [
            labels["role"],
            labels["relative_path"],
            "SHA-256",
            labels["bytes"],
        ],
        [
            [
                row.get("role", ""),
                row.get("relative_path", ""),
                row.get("sha256", ""),
                row.get("bytes", ""),
            ]
            for row in inventory
        ],
        empty=labels["not_available"],
    )
    limitation_items = "".join(f"<li>{_h(value)}</li>" for value in limitations)

    return f"""<!doctype html>
<html lang="{_h(language)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_h(labels["title"])}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #f4f7f9; color: #17202f;
      font: 15px/1.55 Inter, ui-sans-serif, system-ui, sans-serif; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 56px; }}
    h1, h2 {{ letter-spacing: 0; }}
    h1 {{ margin: 10px 0 6px; font-size: 32px; }}
    h2 {{ margin: 0 0 14px; font-size: 20px; }}
    .hero, .panel {{ background: #fff; border: 1px solid #dbe2e8;
      border-radius: 8px; padding: 22px; overflow-wrap: anywhere; }}
    .panel {{ margin-top: 16px; }}
    .badge {{ display: inline-block; padding: 4px 8px; border-radius: 6px;
      background: #e8f4ed; color: #17603a; font-weight: 750; }}
    .hash {{ margin-top: 10px; color: #536170; overflow-wrap: anywhere; }}
    .grid {{ display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 12px; margin-top: 16px; }}
    .metric {{ min-width: 0; border: 1px solid #e0e6eb; border-radius: 8px;
      padding: 14px; background: #fbfcfd; overflow-wrap: anywhere; }}
    .metric-label {{ color: #5c6875; font-size: 12px; font-weight: 700; }}
    .metric-value {{ margin-top: 5px; font-size: 24px; font-weight: 750; }}
    .status {{ font-weight: 750; overflow-wrap: anywhere; }}
    .failed_validation {{ color: #a32020; }}
    .unusable, .missing, .partial {{ color: #8a4b08; }}
    .available {{ color: #17603a; }}
    .table-wrap {{ max-width: 100%; overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 620px; }}
    th, td {{ border-bottom: 1px solid #e4e8ef; padding: 9px;
      text-align: left; vertical-align: top; overflow-wrap: anywhere;
      word-break: break-word; }}
    th {{ background: #f7f9fb; color: #485664; }}
    code {{ white-space: normal; overflow-wrap: anywhere; }}
    .claim {{ border-left: 4px solid #26734d; padding-left: 14px; }}
    @media (max-width: 640px) {{
      main {{ padding: 18px 12px 40px; }}
      h1 {{ font-size: 26px; }}
      .hero, .panel {{ padding: 16px; }}
    }}
  </style>
</head>
<body>
<main>
  <section class="hero">
    <span class="badge">{_h(payload.get("evidence_source", "REAL PEOC BUNDLE"))}</span>
    <h1>{_h(labels["title"])}</h1>
    <div class="hash"><strong>{_h(labels["manifest_hash"])}:</strong>
      <code>{_h(payload.get("manifest_hash", "unknown"))}</code></div>
    <div class="grid">{status_cards}</div>
  </section>
  <section class="panel">
    <h2>{_h(labels["hard_evaluation"])}</h2>
    <div class="grid">
      {_metric(labels["metric"], hard_summary.get("metric", "unknown"))}
      {_metric(labels["valid_rows"], hard_summary.get("valid_row_count", 0))}
      {_metric(labels["excluded_rows"], hard_summary.get("excluded_row_count", 0))}
    </div>
    {hard_table}
  </section>
  <section class="panel">
    <h2>{_h(labels["trajectory"])}</h2>
    {trajectory_html}
  </section>
  <section class="panel">
    <h2>{_h(labels["stage_validation"])}</h2>
    <div class="grid">
      {_metric(labels["status"], _status_html(stage.get("status")), safe=True)}
      {_metric(labels["verdict"], stage.get("verdict", "unknown"))}
      {_metric(labels["held_rho"], stage.get("held_spearman_rho", "unknown"))}
      {_metric(labels["held_ci"], _format_value(stage.get("held_bootstrap_ci")))}
    </div>
  </section>
  <section class="panel">
    <h2>{_h(labels["evidence_limits"])}</h2>
    {limited_table}
  </section>
  <section class="panel">
    <h2>{_h(labels["source_inventory"])}</h2>
    {inventory_table}
  </section>
  <section class="panel">
    <h2>{_h(labels["safe_claim"])}</h2>
    <p class="claim">{_h(safe_claim)}</p>
  </section>
  <section class="panel">
    <h2>{_h(labels["limitations"])}</h2>
    <ul>{limitation_items}</ul>
  </section>
  <section class="panel">
    <h2>{_h(labels["claim_boundary"])}</h2>
    <div class="grid">
      {_metric(labels["full_support"], boundary.get("full_research_support", False))}
      {_metric(labels["boundary_status"], boundary.get("status", "unknown"))}
    </div>
    <p>{_h(boundary.get("statement", ""))}</p>
  </section>
</main>
</body>
</html>
"""


def _trajectory_html(trajectory: JsonDict, labels: dict[str, str]) -> str:
    if not trajectory:
        return f"<p>{_h(labels['not_available'])}</p>"
    stationary = _mapping(trajectory.get("stationary"))
    heterogeneous = _mapping(trajectory.get("heterogeneous"))
    rows = [
        [
            labels["stationary"],
            stationary.get("alpha_emp_mean", ""),
            stationary.get("R2_mean", ""),
            stationary.get("relative_path", ""),
        ],
        [
            labels["heterogeneous"],
            heterogeneous.get("alpha_emp_mean", ""),
            heterogeneous.get("R2_mean", ""),
            heterogeneous.get("relative_path", ""),
        ],
    ]
    return (
        '<div class="grid">'
        + _metric(labels["model"], trajectory.get("model", "unknown"))
        + _metric(labels["seed"], trajectory.get("seed", "unknown"))
        + "</div>"
        + _html_table(
            [labels["trace"], "alpha", "R2", labels["source"]],
            rows,
            empty=labels["not_available"],
        )
    )


def _html_table(
    headers: list[str],
    rows: list[list[object]],
    *,
    empty: str,
    safe_columns: set[int] | None = None,
) -> str:
    safe = safe_columns or set()
    head = "".join(f"<th>{_h(header)}</th>" for header in headers)
    if rows:
        body = "".join(
            "<tr>"
            + "".join(
                f"<td>{value if index in safe else _h(value)}</td>"
                for index, value in enumerate(row)
            )
            + "</tr>"
            for row in rows
        )
    else:
        body = f'<tr><td colspan="{len(headers)}">{_h(empty)}</td></tr>'
    return (
        '<div class="table-wrap"><table><thead><tr>'
        + head
        + "</tr></thead><tbody>"
        + body
        + "</tbody></table></div>"
    )


def _metric(label: object, value: object, *, safe: bool = False) -> str:
    rendered = str(value) if safe else _h(value)
    return (
        '<div class="metric">'
        f'<div class="metric-label">{_h(label)}</div>'
        f'<div class="metric-value">{rendered}</div>'
        "</div>"
    )


def _status_html(value: object) -> str:
    status = str(value or "unknown")
    css = (
        status.lower()
        if status.lower()
        in {
            "available",
            "failed_validation",
            "missing",
            "partial",
            "unusable",
        }
        else ""
    )
    return f'<span class="status {css}">{_h(status.upper())}</span>'


def _status_order(status_counts: JsonDict) -> list[str]:
    preferred = [
        "available",
        "partial",
        "failed_validation",
        "unusable",
        "missing",
    ]
    extras = sorted(str(key) for key in status_counts if str(key) not in preferred)
    return [status for status in preferred if status in status_counts] + extras


def _labels(language: str) -> dict[str, str]:
    """Return localized labels for a PEOC evidence report."""

    if language not in _LANGUAGES:
        raise ValueError("PEOC report language must be 'en' or 'zh'")
    if language == "zh":
        return {
            "title": "真实 PEOC 证据案例",
            "manifest_hash": "清单哈希",
            "status_summary": "证据状态汇总",
            "status": "状态",
            "count": "数量",
            "hard_evaluation": "Hard prompt 方法结果",
            "metric": "指标",
            "valid_rows": "有效结果行",
            "excluded_rows": "排除结果行",
            "model": "模型",
            "task": "任务",
            "method": "方法",
            "mean": "均值",
            "sd": "标准差",
            "trajectory": "Hidden-state trajectory 对比",
            "seed": "随机种子",
            "trace": "轨迹",
            "stationary": "平稳算术",
            "heterogeneous": "异质 GSM8K",
            "source": "来源",
            "stage_validation": "阶段异质性验证",
            "verdict": "判定",
            "held_rho": "留出集 Spearman rho",
            "held_ci": "留出集 bootstrap 区间",
            "evidence_limits": "缺失、不可用与未通过证据",
            "section": "证据部分",
            "origin": "来源类型",
            "limitation": "限制",
            "source_inventory": "来源清单",
            "role": "角色",
            "relative_path": "相对路径",
            "bytes": "字节数",
            "safe_claim": "当前证据允许的结论",
            "limitations": "限制说明",
            "claim_boundary": "结论边界",
            "full_support": "完整研究支持",
            "boundary_status": "边界状态",
            "statement": "说明",
            "not_available": "当前没有可展示的数据",
            "none": "无",
        }
    return {
        "title": "Real PEOC Evidence Case Study",
        "manifest_hash": "Manifest hash",
        "status_summary": "Evidence status summary",
        "status": "Status",
        "count": "Count",
        "hard_evaluation": "Hard-prompt method results",
        "metric": "Metric",
        "valid_rows": "Valid rows",
        "excluded_rows": "Excluded rows",
        "model": "Model",
        "task": "Task",
        "method": "Method",
        "mean": "Mean",
        "sd": "SD",
        "trajectory": "Hidden-state trajectory comparison",
        "seed": "Seed",
        "trace": "Trace",
        "stationary": "Stationary arithmetic",
        "heterogeneous": "Heterogeneous GSM8K",
        "source": "Source",
        "stage_validation": "Stage-heterogeneity validation",
        "verdict": "Verdict",
        "held_rho": "Held-out Spearman rho",
        "held_ci": "Held-out bootstrap interval",
        "evidence_limits": "Missing, unusable, and failed evidence",
        "section": "Section",
        "origin": "Origin",
        "limitation": "Limitation",
        "source_inventory": "Source inventory",
        "role": "Role",
        "relative_path": "Relative path",
        "bytes": "Bytes",
        "safe_claim": "Evidence-bounded claim",
        "limitations": "Limitations",
        "claim_boundary": "Claim boundary",
        "full_support": "Full research support",
        "boundary_status": "Boundary status",
        "statement": "Statement",
        "not_available": "No data is available for this section.",
        "none": "None",
    }


def _mapping(value: object) -> JsonDict:
    return value if isinstance(value, dict) else {}


def _rows(value: object) -> list[JsonDict]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _values(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _localized_value(payload: JsonDict, key: str, language: str) -> object:
    if language == "zh":
        return payload.get(f"{key}_zh", payload.get(key, ""))
    return payload.get(key, "")


def _localized_values(payload: JsonDict, key: str, language: str) -> list[object]:
    return _values(_localized_value(payload, key, language))


def _format_value(value: object) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(str(item) for item in value) + "]"
    return str(value if value is not None else "unknown")


def _md(value: object) -> str:
    escaped = html.escape(str(value if value is not None else ""), quote=True)
    escaped = escaped.replace("`", "&#96;").replace("\r", " ").replace("\n", " ")
    return re.sub(r"([\\*_\[\]{}()#!|>])", r"\\\1", escaped)


def _h(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)
