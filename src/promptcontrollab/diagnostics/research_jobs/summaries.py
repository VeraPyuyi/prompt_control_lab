"""Display retained tables without pretending to reconstruct their source data."""
# Chinese report prose uses fullwidth punctuation intentionally.
# ruff: noqa: RUF001

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from promptcontrollab.diagnostics.research_tools.common import write_reports


def write_saved_tables(tool: str, tables: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    """Render retained tables with explicit descriptive-only evidence boundaries."""
    result = write_reports(
        {
            "kind": "saved-summary",
            "tool": tool,
            "schema_version": "pcl.saved-research-tables/v1",
            "synthetic": False,
            "computation": "saved_summary_only",
            "raw_recomputation": False,
            "numerical_agreement": "not_tested",
            "chronology_verified": False,
            "saved_tables": tables,
        },
        output,
    )
    for language in ("en", "zh"):
        zh = language == "zh"
        title = "已有研究表格" if zh else "Saved research tables"
        boundary = (
            "以下内容来自导入材料，仅展示保存的表格。未重建激活、重新校准或核验原始计时；"
            "数值重放与来源凭证需单独查看。预览有行列与文本长度限制，完整数据保留在导出包中。"
            if zh
            else "These are saved tables from the supplied material. Activations, calibration and "
            "original timings have not been reconstructed. Numerical replay and provenance "
            "are checked separately. Previews are bounded; the export retains the full input data."
        )
        sections = []
        for table in tables:
            heading = f"<h2>{html.escape(table['input'])}</h2>"
            values = table["saved_values"]
            if table["input"].lower().endswith(".csv") and isinstance(values, list):
                rows = []
                for index, row in enumerate(values):
                    tag = "th" if index == 0 else "td"
                    rows.append(
                        "<tr>"
                        + "".join(f"<{tag}>{html.escape(str(value))}</{tag}>" for value in row)
                        + "</tr>"
                    )
                body = "<div class='scroll'><table>" + "".join(rows) + "</table></div>"
            else:
                text = values if isinstance(values, str) else json.dumps(values, ensure_ascii=False)
                label = "查看保存内容" if zh else "View saved values"
                body = (
                    f"<details><summary>{label}</summary><pre>{html.escape(text)}</pre></details>"
                )
            sections.append(heading + body)
        page = (
            f'<!doctype html><html lang="{language}"><meta charset="utf-8">'
            f"<title>{title}</title><style>body{{font:16px/1.6 system-ui;margin:24px;"
            "color:#18283d}table{border-collapse:collapse}td,th{padding:8px;border-bottom:1px "
            "solid #ddd;text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere}"
            ".scroll{overflow:auto}h2{font-size:18px;overflow-wrap:anywhere}</style>"
            f"<h1>{title}</h1><p>{boundary}</p>{''.join(sections)}</html>"
        )
        (output / f"report.{language}.html").write_text(page, encoding="utf-8")
    return result
