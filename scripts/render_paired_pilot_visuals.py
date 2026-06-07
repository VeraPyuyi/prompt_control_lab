"""Render SVG visual summaries for the real paired Codex guard pilot."""

# ruff: noqa: E501,RUF001

from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "docs" / "case_studies" / "agent_guard_paired_pilot.csv"
SUMMARY_PATH = ROOT / "docs" / "case_studies" / "agent_guard_paired_pilot.summary.json"
OUT_EN = ROOT / "docs" / "assets" / "agent_guard_paired_pilot.svg"
OUT_ZH = ROOT / "docs" / "assets" / "agent_guard_paired_pilot.zh.svg"

JsonDict = dict[str, Any]

WIDTH = 1280
HEIGHT = 820
RAW = "#2563eb"
GUARDED = "#16a34a"
INK = "#0f172a"
MUTED = "#64748b"
BORDER = "#dbe3ef"
SOFT = "#f8fafc"
WARN = "#f59e0b"


def main() -> int:
    rows = list(csv.DictReader(CSV_PATH.read_text(encoding="utf-8").splitlines()))
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    OUT_EN.write_text(_render(rows, summary, language="en"), encoding="utf-8")
    OUT_ZH.write_text(_render(rows, summary, language="zh"), encoding="utf-8")
    print(f"wrote {OUT_EN}")
    print(f"wrote {OUT_ZH}")
    return 0


def _render(rows: list[JsonDict], summary: JsonDict, *, language: str) -> str:
    text = _labels(language)
    parts = [
        _svg_header(text["title"], text["subtitle"]),
        _cards(summary, text),
        _bars(summary, text),
        _duration_chart(rows, text),
        _callout(text),
        _legend(text),
        "</svg>",
    ]
    return "\n".join(parts)


def _svg_header(title: str, subtitle: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="{_e(title)}">
  <rect width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/>
  <rect x="32" y="28" width="{WIDTH - 64}" height="{HEIGHT - 56}" rx="26" fill="{SOFT}" stroke="{BORDER}"/>
  <text x="64" y="78" font-family="{_font()}" font-size="32" font-weight="800" fill="{INK}">{_e(title)}</text>
  <text x="64" y="112" font-family="{_font()}" font-size="16" fill="{MUTED}">{_e(subtitle)}</text>"""


def _cards(summary: JsonDict, text: dict[str, str]) -> str:
    cards = [
        (
            text["success"],
            f"{summary['raw_success']}/{summary['sample_size']} = {summary['guarded_success']}/{summary['sample_size']}",
            text["same"],
            text["success_note"],
            GUARDED,
        ),
        (
            text["tests"],
            f"{summary['raw_tests_passed']}/{summary['sample_size']} = {summary['guarded_tests_passed']}/{summary['sample_size']}",
            text["same"],
            text["tests_note"],
            GUARDED,
        ),
        (
            text["runtime"],
            f"{_fmt(summary['raw_avg_duration_seconds'])} -> {_fmt(summary['guarded_avg_duration_seconds'])}",
            _delta_note(summary["raw_avg_duration_seconds"], summary["guarded_avg_duration_seconds"], "s", text),
            text["runtime_note"],
            RAW,
        ),
        (
            text["tokens"],
            f"{_fmt(summary['raw_avg_prompt_tokens'])} -> {_fmt(summary['guarded_avg_prompt_tokens'])}",
            _delta_note(summary["raw_avg_prompt_tokens"], summary["guarded_avg_prompt_tokens"], "", text),
            text["tokens_note"],
            WARN,
        ),
    ]
    out: list[str] = []
    x = 64
    y = 142
    card_w = 276
    card_h = 132
    for index, (title, value, detail, note, color) in enumerate(cards):
        cx = x + index * (card_w + 18)
        out.append(
            f'  <rect x="{cx}" y="{y}" width="{card_w}" height="{card_h}" rx="16" fill="#ffffff" stroke="{BORDER}"/>'
        )
        out.append(
            f'  <rect x="{cx}" y="{y}" width="6" height="{card_h}" rx="3" fill="{color}"/>'
        )
        out.append(
            f'  <text x="{cx + 22}" y="{y + 34}" font-family="{_font()}" font-size="15" font-weight="700" fill="{MUTED}">{_e(title)}</text>'
        )
        out.append(
            f'  <text x="{cx + 22}" y="{y + 70}" font-family="{_font()}" font-size="24" font-weight="800" fill="{INK}">{_e(value)}</text>'
        )
        out.append(
            f'  <text x="{cx + 22}" y="{y + 94}" font-family="{_font()}" font-size="13" font-weight="700" fill="{color}">{_e(detail)}</text>'
        )
        out.append(
            f'  <text x="{cx + 22}" y="{y + 116}" font-family="{_font()}" font-size="12" fill="{MUTED}">{_e(note)}</text>'
        )
    return "\n".join(out)


def _bars(summary: JsonDict, text: dict[str, str]) -> str:
    x = 64
    y = 302
    w = 520
    h = 244
    metrics = [
        (text["avg_duration"], float(summary["raw_avg_duration_seconds"]), float(summary["guarded_avg_duration_seconds"]), "s"),
        (text["avg_tokens"], float(summary["raw_avg_prompt_tokens"]), float(summary["guarded_avg_prompt_tokens"]), ""),
        (text["avg_touched"], float(summary["raw_avg_touched_files"]), float(summary["guarded_avg_touched_files"]), ""),
        (text["unexpected"], float(summary["raw_total_unnecessary_file_edits"]), float(summary["guarded_total_unnecessary_file_edits"]), ""),
    ]
    max_value = max(max(raw, guarded) for _, raw, guarded, _ in metrics)
    out = [
        f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="#ffffff" stroke="{BORDER}"/>',
        f'  <text x="{x + 22}" y="{y + 34}" font-family="{_font()}" font-size="20" font-weight="800" fill="{INK}">{_e(text["summary_bars"])}</text>',
    ]
    row_y = y + 68
    for label, raw, guarded, unit in metrics:
        out.append(
            f'  <text x="{x + 22}" y="{row_y + 13}" font-family="{_font()}" font-size="13" font-weight="700" fill="{MUTED}">{_e(label)}</text>'
        )
        out.extend(_bar_pair(x + 168, row_y, 258, raw, guarded, max_value, unit))
        row_y += 42
    return "\n".join(out)


def _bar_pair(x: int, y: int, width: int, raw: float, guarded: float, max_value: float, unit: str) -> list[str]:
    raw_w = max(2, round(width * raw / max_value))
    guarded_w = max(2, round(width * guarded / max_value))
    return [
        f'  <rect x="{x}" y="{y}" width="{raw_w}" height="12" rx="6" fill="{RAW}"/>',
        f'  <rect x="{x}" y="{y + 18}" width="{guarded_w}" height="12" rx="6" fill="{GUARDED}"/>',
        f'  <text x="{x + width + 14}" y="{y + 11}" font-family="{_font()}" font-size="12" fill="{INK}">{_fmt(raw)}{unit}</text>',
        f'  <text x="{x + width + 14}" y="{y + 29}" font-family="{_font()}" font-size="12" fill="{INK}">{_fmt(guarded)}{unit}</text>',
    ]


def _duration_chart(rows: list[JsonDict], text: dict[str, str]) -> str:
    x = 624
    y = 302
    w = 592
    h = 244
    chart_x = x + 100
    chart_y = y + 58
    chart_w = 402
    row_gap = 27
    max_duration = max(
        max(float(row["raw_duration_seconds"]), float(row["guarded_duration_seconds"]))
        for row in rows
    )
    out = [
        f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="#ffffff" stroke="{BORDER}"/>',
        f'  <text x="{x + 22}" y="{y + 34}" font-family="{_font()}" font-size="20" font-weight="800" fill="{INK}">{_e(text["task_runtime"])}</text>',
        f'  <line x1="{chart_x}" y1="{chart_y - 18}" x2="{chart_x + chart_w}" y2="{chart_y - 18}" stroke="{BORDER}"/>',
        f'  <text x="{chart_x}" y="{chart_y - 26}" font-family="{_font()}" font-size="11" fill="{MUTED}">0s</text>',
        f'  <text x="{chart_x + chart_w - 44}" y="{chart_y - 26}" font-family="{_font()}" font-size="11" fill="{MUTED}">{round(max_duration)}s</text>',
    ]
    for index, row in enumerate(rows):
        yy = chart_y + index * row_gap
        raw = float(row["raw_duration_seconds"])
        guarded = float(row["guarded_duration_seconds"])
        raw_x = chart_x + round(chart_w * raw / max_duration)
        guarded_x = chart_x + round(chart_w * guarded / max_duration)
        out.append(
            f'  <text x="{x + 22}" y="{yy + 4}" font-family="{_font()}" font-size="12" font-weight="700" fill="{MUTED}">{_e(row["task_id"])}</text>'
        )
        out.append(
            f'  <line x1="{min(raw_x, guarded_x)}" y1="{yy}" x2="{max(raw_x, guarded_x)}" y2="{yy}" stroke="#cbd5e1" stroke-width="4" stroke-linecap="round"/>'
        )
        out.append(f'  <circle cx="{raw_x}" cy="{yy}" r="6" fill="{RAW}"/>')
        out.append(f'  <circle cx="{guarded_x}" cy="{yy}" r="6" fill="{GUARDED}"/>')
        out.append(
            f'  <text x="{chart_x + chart_w + 16}" y="{yy + 4}" font-family="{_font()}" font-size="11" fill="{MUTED}">{_fmt(raw)} / {_fmt(guarded)}s</text>'
        )
    return "\n".join(out)


def _callout(text: dict[str, str]) -> str:
    x = 64
    y = 584
    w = 1152
    h = 124
    return f"""  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="#fff7ed" stroke="#fed7aa"/>
  <text x="{x + 24}" y="{y + 36}" font-family="{_font()}" font-size="19" font-weight="800" fill="#9a3412">{_e(text["interpret_title"])}</text>
  <text x="{x + 24}" y="{y + 68}" font-family="{_font()}" font-size="15" fill="#7c2d12">{_e(text["interpret_1"])}</text>
  <text x="{x + 24}" y="{y + 94}" font-family="{_font()}" font-size="15" fill="#7c2d12">{_e(text["interpret_2"])}</text>"""


def _legend(text: dict[str, str]) -> str:
    y = 746
    return f"""  <circle cx="66" cy="{y}" r="7" fill="{RAW}"/>
  <text x="80" y="{y + 5}" font-family="{_font()}" font-size="14" fill="{MUTED}">{_e(text["raw"])}</text>
  <circle cx="170" cy="{y}" r="7" fill="{GUARDED}"/>
  <text x="184" y="{y + 5}" font-family="{_font()}" font-size="14" fill="{MUTED}">{_e(text["guarded"])}</text>
  <text x="940" y="{y + 5}" font-family="{_font()}" font-size="13" fill="{MUTED}">{_e(text["footnote"])}</text>"""


def _labels(language: str) -> dict[str, str]:
    if language == "zh":
        return {
            "title": "真实成对试点：Raw Agent vs Guarded Agent",
            "subtitle": "6 个隔离 Python pytest bugfix；每个任务从相同初始仓库分别运行 raw 和 guarded prompt。",
            "success": "完成任务",
            "success_note": "两侧成功率相同",
            "tests": "测试通过",
            "tests_note": "pytest 验收结果",
            "runtime": "平均耗时",
            "runtime_note": "guarded 本次更快",
            "tokens": "Prompt Token",
            "tokens_note": "guarded 更长",
            "same": "相同",
            "delta": "变化",
            "avg_duration": "平均耗时",
            "avg_tokens": "平均 token",
            "avg_touched": "平均触碰文件",
            "unexpected": "非预期改动总数",
            "summary_bars": "汇总指标对比",
            "task_runtime": "逐任务耗时对比",
            "interpret_title": "如何解读",
            "interpret_1": "这组小样本里 guarded prompt 没有提升成功率，因为 raw Codex 已经 6/6 完成。",
            "interpret_2": "guarded 平均耗时更短，但 prompt token 更多；这说明需要更大、更真实的任务集继续验证。",
            "raw": "Raw agent",
            "guarded": "Guarded agent",
            "footnote": "小样本 fixture pilot，不是通用 benchmark。",
        }
    return {
        "title": "Real Paired Pilot: Raw Agent vs Guarded Agent",
        "subtitle": "6 isolated Python pytest bugfixes; each task ran from the same fresh repo with raw and guarded prompts.",
        "success": "Completed tasks",
        "success_note": "same success rate",
        "tests": "Tests passed",
        "tests_note": "pytest acceptance",
        "runtime": "Mean duration",
        "runtime_note": "guarded was faster here",
        "tokens": "Prompt tokens",
        "tokens_note": "guarded was longer",
        "same": "same",
        "delta": "delta",
        "avg_duration": "Mean duration",
        "avg_tokens": "Mean tokens",
        "avg_touched": "Mean touched files",
        "unexpected": "Unexpected edits",
        "summary_bars": "Summary Metrics",
        "task_runtime": "Per-Task Runtime",
        "interpret_title": "How to read this",
        "interpret_1": "Guarded prompts did not improve success rate in this small sample because raw Codex already solved 6/6 tasks.",
        "interpret_2": "Guarded prompts were faster on average but used more prompt tokens; larger real PR tasks are needed next.",
        "raw": "Raw agent",
        "guarded": "Guarded agent",
        "footnote": "Small fixture pilot, not a universal benchmark.",
    }


def _delta_note(raw: float, guarded: float, unit: str, text: dict[str, str]) -> str:
    delta = guarded - raw
    sign = "+" if delta >= 0 else ""
    return f"{text['delta']} {sign}{_fmt(delta)}{unit}"


def _fmt(value: float) -> str:
    if abs(value - round(value)) < 0.005:
        return str(round(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _font() -> str:
    return "Inter, Segoe UI, Arial, Microsoft YaHei, sans-serif"


def _e(text: object) -> str:
    return html.escape(str(text), quote=False)


if __name__ == "__main__":
    raise SystemExit(main())
