"""Portable bilingual reports for committed analysis suites."""

from __future__ import annotations

import csv
import html
import io
import json
import os
import uuid
from pathlib import Path
from typing import Any

from promptcontrollab.diagnostics.research_tools.common import flatten
from promptcontrollab.evaluation.experiments.storage import read_json, write_json

from .bundles import data_path, get_bundle, sha256
from .models import ResearchJob

REPORT_FILES = (
    "report.json",
    "metrics.csv",
    "report.en.html",
    "report.zh.html",
    "report.en.md",
    "report.zh.md",
)


def _publish_text(path: Path, text: str) -> None:
    temporary = path.with_name(f".report-{uuid.uuid4().hex[:12]}")
    try:
        with temporary.open("x", encoding="utf-8", newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _cell(value: Any) -> str:
    if value is None:
        return "—"
    return html.escape(f"{value:.6g}" if isinstance(value, float) else str(value))


def _intervals(directory: Path, result: dict[str, Any], zh: bool) -> str:
    report = read_json(data_path(directory, result["files"]["report"]))
    rows = report["primary_intervals"]
    labels = (
        ["对照", "估计", "下限", "上限", "有效抽样", "证据"]
        if zh
        else ["Contrast", "Estimate", "Lower", "Upper", "Valid draws", "Support"]
    )
    cells = []
    for row in rows:
        lower, upper = row["lower"], row["upper"]
        support = (
            ("未定义" if zh else "Undefined")
            if lower is None
            else (
                ("区间包含零" if zh else "Interval includes zero")
                if lower <= 0 <= upper
                else ("区间不含零" if zh else "Interval excludes zero")
            )
        )
        values = [
            f"{row.get('model', '')} / {row.get('score', '')} / {row['estimand']}",
            row["estimate"],
            lower,
            upper,
            row["valid_draws"],
            support,
        ]
        cells.append("<tr>" + "".join(f"<td>{_cell(x)}</td>" for x in values) + "</tr>")
    boundary = (
        "区间包含零不代表等效。统计支持与实际收益需分别判断。"
        if zh
        else "An interval containing zero does not establish equivalence. "
        "Statistical support and practical value require separate judgments."
    )
    return (
        f"<p>{boundary}</p><div class='table-scroll'><table><tr>"
        + "".join(f"<th>{x}</th>" for x in labels)
        + "</tr>"
        + "".join(cells)
        + "</table></div>"
    )


def write_job_report(root: Path, job: ResearchJob) -> None:
    """Publish bilingual reports and a final manifest from verified committed suites."""
    from .engine import job_directory

    directory = job_directory(root, job["id"])
    output = data_path(directory, "report")
    output.mkdir(exist_ok=True)
    bundle = get_bundle(root, job["spec"]["bundle_id"])
    results = [
        {"analysis": row["analysis"], "result": row["result"]} for row in job["completed"].values()
    ]
    report = {
        "schema_version": "pcl.research-assessment/v1",
        "status": job["status"],
        "synthetic": bundle["synthetic"],
        "source_integrity": "verified_imported_files",
        "historical_chronology_verified": False,
        "scope": (
            "See each analysis for numerical support, protocol and practical value; "
            "integrity alone establishes none of these."
        ),
        "capabilities": bundle["capabilities"],
        "analyses": results,
    }
    payload = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    _publish_text(output / "report.json", payload + "\n")
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["metric", "value"])
    for key, value in flatten(report):
        text = "null" if value is None else str(value)
        if isinstance(value, str) and text[:1] in {"=", "+", "-", "@"}:
            text = "'" + text
        writer.writerow([key, text])
    _publish_text(output / "metrics.csv", stream.getvalue())
    for lang in ("en", "zh"):
        zh = lang == "zh"
        title = "研究证据报告" if zh else "Research evidence report"
        boundary = (
            "文件完整性、数值复算、协议符合性和实际收益分别判断。"
            "导出文件的哈希不认证原始预测的锁定时间。"
            if zh
            else "File integrity, numerical replay, protocol conformity and practical value "
            "are separate judgments. This export does not certify original prediction timing."
        )
        marker = (
            ("合成演示" if zh else "Synthetic demonstration")
            if bundle["synthetic"]
            else ("已提供的研究记录" if zh else "Supplied research records")
        )
        sections = []
        for unit, row in job["completed"].items():
            name = row["analysis"].get("suite", row["analysis"]["kind"])
            source = directory / "units" / unit / f"report.{lang}.html"
            heading = f"<h2>{html.escape(name)}</h2>"
            if row["analysis"]["kind"] == "bootstrap":
                status = row["result"]["status"]
                label = "数值重放比较" if zh else "Numerical replay comparison"
                sections.append(
                    heading
                    + f"<p>{label}: {_cell(status)}</p>"
                    + _intervals(directory / "units" / unit, row["result"], zh)
                )
            elif source.is_file():
                # Only embed our own renderer's output, never uploaded HTML.
                page = source.read_text(encoding="utf-8")
                style = page.split("<style>", 1)[1].split("</style>", 1)[0]
                body = page.split("</style>", 1)[1].rsplit("</html>", 1)[0]
                sections.append(f"<section>{heading}<style>{style}</style>{body}</section>")
            else:
                body = json.dumps(row["result"], ensure_ascii=False, indent=2)
                sections.append(heading + f"<pre>{html.escape(body)}</pre>")
        complete = "完整记录" if zh else "Complete record"
        page = (
            f'<!doctype html><html lang="{lang}"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width">'
            f"<title>{title}</title><style>"
            "body{font:16px/1.6 system-ui;margin:32px auto;max-width:1100px;"
            "padding:0 20px;color:#18283d;background:#f8fafc}"
            "pre{white-space:pre-wrap;overflow-wrap:anywhere}p{max-width:90ch}"
            ".table-scroll{overflow:auto}table{border-collapse:collapse;width:100%;"
            "background:white}td,th{padding:10px;text-align:left;border-bottom:1px solid #dae3ee}"
            "section{margin:32px 0}</style>"
            f"<h1>{title}</h1><p>{marker} · {html.escape(job['status'])}</p><p>{boundary}</p>"
            f"{''.join(sections)}<details><summary>{complete}</summary>"
            f"<pre>{html.escape(payload)}</pre></details></html>"
        )
        _publish_text(output / f"report.{lang}.html", page)
        _publish_text(
            output / f"report.{lang}.md",
            f"# {title}\n\n{marker}\n\n{boundary}\n\n```json\n{payload}\n```\n",
        )
    write_json(
        output / "report-manifest.json", {name: sha256(output / name) for name in REPORT_FILES}
    )
