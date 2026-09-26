"""Self-contained bilingual reports and credential-safe portable packages."""

from __future__ import annotations

import csv
import html
import json
import zipfile
from hashlib import sha256
from pathlib import Path
from typing import Any

from .storage import read_json, write_json


def _cell(value: object) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


def _html_value(value: object) -> str:
    return html.escape("" if value is None else str(value))


def _practical_html(assessment: dict[str, Any], language: str) -> str:
    """Render shared practical conclusions without interpreting unknown values as zero."""
    practical = assessment.get("practical")
    if not practical:
        return ""
    zh = language == "zh"
    fields = [
        ("score_mean", "Mean score", "平均分数"),
        ("mean_latency_ms", "Mean latency (ms)", "平均耗时 (毫秒)"),
        ("mean_input_tokens", "Input tokens / item", "每题输入 token"),
        ("mean_output_tokens", "Output tokens / item", "每题输出 token"),
    ]
    rows = []
    for field, en, cn in fields:
        cells = [cn if zh else en]
        for arm in ("baseline", "candidate", "delta"):
            value = practical.get(arm, {}).get(field)
            cells.append("—" if value is None else f"{value:.4g}")
        rows.append("<tr>" + "".join(f"<td>{_html_value(c)}</td>" for c in cells) + "</tr>")
    amount = ["金额" if zh else "Amount"]
    for arm in ("baseline", "candidate"):
        section = practical.get(arm, {})
        value = section.get("known_cost")
        amount.append(
            str(value)
            if section.get("cost_status") == "known" and value is not None
            else "未知或不完整"
            if zh
            else "Unknown or partial"
        )
    delta_cost = practical.get("delta", {}).get("cost")
    amount.append("—" if delta_cost is None else str(delta_cost))
    rows.append("<tr>" + "".join(f"<td>{_html_value(c)}</td>" for c in amount) + "</tr>")
    headings = (
        ("指标", "原版本", "候选版本", "变化")
        if zh
        else ("Measure", "Original", "Candidate", "Change")
    )
    header = "".join(f"<th>{heading}</th>" for heading in headings)
    evidence = _html_value(practical.get("evidence_range", {}).get(language))
    next_action = _html_value(assessment.get("next_action", {}).get(language))
    stats = assessment.get("effect", {}).get("statistics") or {}
    metric = _html_value(assessment.get("comparability", {}).get("metric"))
    lower = assessment.get("effect", {}).get("direction") == "lower_is_better"
    direction = (
        ("越低越好; 负向变化有利于候选。" if lower else "越高越好; 正向变化有利于候选。")
        if zh
        else (
            "Lower is better; negative change favors the candidate."
            if lower
            else "Higher is better; positive change favors the candidate."
        )
    )
    interval = _html_value(stats.get("bootstrap_ci"))
    p_value = _html_value(stats.get("holm_adjusted_p_value"))
    statistical = (
        f"95% 区间: {interval or '—'}; 校正后 p 值: {p_value or '—'}。"
        "效果判断同时要求区间方向支持改进且成对检验通过。"
        if zh
        else f"95% interval: {interval or '—'}; adjusted p-value: {p_value or '—'}. "
        "An improvement requires a favorable interval and a supported paired test."
    )
    return (
        f"<section><h2>{'质量、耗时与成本' if zh else 'Quality, time and cost'}</h2>"
        f"<p>{metric}: {direction}</p><p>{evidence}</p><table><thead><tr>{header}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table><p>{statistical}</p>"
        f"<p><b>{'下一步' if zh else 'Next step'}</b>: {next_action}</p></section>"
    )


def write_reports(
    job_dir: Path,
    job: dict[str, Any],
    baseline: list[dict[str, Any]],
    candidate: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Write portable bilingual experiment reports and return exact artifact receipts."""
    report = job_dir / "report"
    report.mkdir(exist_ok=True)
    records = [
        {"arm": arm, **row}
        for arm, rows in (("baseline", baseline), ("candidate", candidate))
        for row in rows
    ]
    summary = {
        "schema_version": "experiment-report/v1",
        "id": job["id"],
        "name": job.get("name"),
        "operation": job["operation"],
        "status": job["status"],
        "stop_reason": job.get("stop_reason"),
        "snapshot_hash": job["snapshot_hash"],
        "assessment": job.get("assessment"),
        "optimization": job.get("optimization"),
        "budget": job.get("budget"),
        "synthetic": job.get("synthetic", False),
    }
    write_json(report / "summary.json", summary)
    write_json(report / "records.json", {"baseline": baseline, "candidate": candidate})
    with (report / "records.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        fields = [
            "arm",
            "id",
            "phase",
            "status",
            "output_status",
            "score",
            "expected",
            "output",
            "slice",
            "error_type",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({key: _cell(record.get(key)) for key in fields})
    assessment = job.get("assessment", {})
    for language in ("en", "zh"):
        chinese = language == "zh"
        title = "提示词实验报告" if chinese else "Prompt experiment report"
        labels = {
            "comparability": "可比性",
            "effect": "效果",
            "coverage": "覆盖情况",
            "cost": "成本",
        }
        statuses = {
            "comparable": "可比",
            "confounded": "设置有混杂",
            "declared_only": "仅用户声明",
            "improved": "观察到改善",
            "regressed": "观察到退步",
            "uncertain": "尚不确定",
            "no_observed_change": "未观察到变化",
            "insufficient_data": "数据不足",
            "complete": "完整",
            "partial": "部分覆盖",
            "none": "无配对数据",
            "unknown": "未知",
            "known": "已知",
        }
        coverage = assessment.get("coverage", {})
        effect = assessment.get("effect", {}).get("statistics") or {}
        cost = assessment.get("cost", {})
        messages = {
            "comparability": ("比较范围: " if chinese else "Comparison scope: ")
            + str(assessment.get("comparability", {}).get("scope", "unknown")),
            "effect": ("平均分数差: " if chinese else "Mean score difference: ")
            + str(effect.get("mean_delta", "—")),
            "coverage": ("成功配对: " if chinese else "Successfully paired: ")
            + f"{coverage.get('matched', 0)} / {coverage.get('total', 0)}",
            "cost": ("调用数: " if chinese else "Calls: ")
            + str(cost.get("calls", 0))
            + ("; 成本未知的调用数: " if chinese else "; calls with unknown cost: ")
            + str(cost.get("unknown_cost_calls", 0)),
        }
        cards = ""
        for key in labels:
            section = assessment.get(key, {})
            status = str(section.get("status", "unknown"))
            status_text = _html_value(statuses.get(status, status) if chinese else status)
            detail = html.escape(json.dumps(section, ensure_ascii=False, indent=2))
            cards += (
                f"<section><h2>{labels[key] if chinese else key.title()}</h2>"
                f"<strong>{status_text}</strong>"
                f"<p>{html.escape(messages[key])}</p><details><summary>"
                f"{'证据详情' if chinese else 'Evidence details'}</summary><pre>{detail}</pre>"
                "</details></section>"
            )
        rows = "".join(
            "<tr>"
            + "".join(
                f"<td>{_html_value(record.get(key))}</td>"
                for key in ("arm", "id", "status", "score", "output")
            )
            + "</tr>"
            for record in records
        )
        explanation = (
            "四项结论独立判断。缺失和服务错误不按质量零分处理。"
            if chinese
            else "The four conclusions are independent. Missing outputs and service errors "
            "are excluded from quality scores."
        )
        csv_note = (
            "CSV 文本已防护公式执行。原始文本见 records.json。"
            if chinese
            else "CSV text is protected against formula execution; exact text is in records.json."
        )
        demo_note = (
            (
                "<p><strong>合成演示数据: 不代表真实模型表现。</strong></p>"
                if chinese
                else "<p><strong>Synthetic demonstration: "
                "no claim about real model performance.</strong></p>"
            )
            if job.get("synthetic")
            else ""
        )
        headers = (
            ("组别", "ID", "状态", "分数", "输出")
            if chinese
            else ("Arm", "ID", "Status", "Score", "Output")
        )
        header_html = "".join(f"<th>{header}</th>" for header in headers)
        practical_html = _practical_html(assessment, language)
        source = f"""<!doctype html><html lang="{language}"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title>
<style>body{{font:16px system-ui,sans-serif;max-width:1100px;margin:40px auto;
padding:0 24px;color:#17252e;background:#f5f8fa}}
h1{{font-size:32px}}section{{background:white;border:1px solid #d4e0e6;
border-radius:12px;padding:20px;margin:16px 0}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}}
table{{width:100%;border-collapse:collapse;background:white}}
td,th{{padding:10px;border:1px solid #d4e0e6;text-align:left;vertical-align:top;
white-space:pre-wrap;overflow-wrap:anywhere}}strong{{font-size:20px}}</style>
<h1>{title}</h1><p>{html.escape(str(job.get("name") or job["id"]))}</p>
<p>{"状态" if chinese else "Status"}: {html.escape(job["status"])}</p>
{demo_note}<p>{explanation}</p>{cards}{practical_html}
<h2>{"逐项输出" if chinese else "Per-item outputs"}</h2>
<table><thead><tr>{header_html}</tr></thead><tbody>{rows}</tbody></table>
<p>{csv_note}</p></html>"""
        (report / f"report.{language}.html").write_text(source, encoding="utf-8")
    artifacts = []
    for path in sorted(report.iterdir()):
        if path.is_file():
            artifacts.append(
                {
                    "name": path.name,
                    "path": path.relative_to(job_dir).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path.read_bytes()).hexdigest(),
                }
            )
    return artifacts


def export_experiment(root: Path, job_id: str) -> Path:
    """Package only persisted job artifacts, using paths relative to the job."""
    from .storage import job_directory

    job_dir = job_directory(root, job_id)
    job = read_json(job_dir / "job.json")
    if job["status"] in {"queued", "running", "cancelling"}:
        raise ValueError("Export requires a stopped or completed experiment")
    target = job_dir / "experiment.zip"
    allowed_files = {
        "spec.json",
        "data.json",
        "split.json",
        "job.json",
        "events.jsonl",
        "manifest.json",
        "bundle_receipts.json",
    }
    allowed_dirs = {"calls", "records", "checkpoints", "report"}
    files = []
    for path in sorted(job_dir.rglob("*")):
        relative = path.relative_to(job_dir)
        if (
            path.is_symlink()
            or not path.is_file()
            or any(part.startswith(".") for part in relative.parts)
        ):
            continue
        if (
            path.resolve().is_relative_to(job_dir.resolve())
            and (relative.as_posix() in allowed_files or relative.parts[0] in allowed_dirs)
            and relative.as_posix() != "bundle_receipts.json"
        ):
            files.append((path.read_bytes(), relative.as_posix()))
    receipt_path = job_dir / "bundle_receipts.json"
    write_json(
        receipt_path,
        {
            "schema_version": "experiment-bundle-receipts/v1",
            "files": {name: sha256(data).hexdigest() for data, name in files},
            "scope": "Exact exported bytes only; no external authenticity or chronology claim",
        },
    )
    files.append((receipt_path.read_bytes(), "bundle_receipts.json"))
    temporary = target.with_suffix(".zip.tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for data, archive_name in files:
            archive.writestr(f"{job_id}/{archive_name}", data)
    temporary.replace(target)
    return target
