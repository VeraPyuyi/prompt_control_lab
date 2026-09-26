"""Replay a versioned measurement-value fixture using only the Python standard library."""

# Chinese report text deliberately uses full-width punctuation.
# ruff: noqa: RUF001

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from promptcontrollab.measurement_value import analyze_document  # noqa: E402

CSV_FIELDS = (
    "evidence_status",
    "synthetic",
    "model",
    "pair",
    "strategy",
    "budget_seconds",
    "K",
    "p",
    "Y",
    "risk_increases",
    "risk_decreases",
    "K_0",
    "p_0",
    "Y_0",
    "delta_Y",
    "precision_threshold",
    "precision_threshold_gt_one",
    "upfront_seconds",
    "audit_seconds",
    "required_seconds",
    "unspent_seconds",
    "overhead_exceeds_budget",
    "decomposition_status",
    "precision_gain",
    "capacity_loss",
)


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _report(result: dict[str, Any], *, chinese: bool) -> str:
    if chinese:
        lines = [
            "# 测量价值：固定预算案例",
            "",
            "**合成测试数据；不构成实证结果。**"
            if result["synthetic"]
            else "基于所提供记录的成本重放。",
            "",
            f"声明的证据状态：`{result['evidence_status']}`。",
            f"输入文件 SHA256：`{result['input_sha256']}`。",
            "",
            "该状态由输入显式声明；文件完整性与标签存在不会把历史观察升级为独立确认。",
            "发现事件为 `abs(risk_target-risk_source)`；风险增加和减少都计数。",
            "K 是预算内完整配对审计量，p 是其中发现比例，Y 是发现数。",
            "所有 delta_Y 都相对于同一案例的未付费 direct。",
            "",
            "下表在每个模型内按策略汇总。逐案例结果见 strategies.csv；"
            "完整队列及精确分解见 results.json。",
            "未提供 probe_seconds 与 selection_seconds 的案例不会生成付费策略行。",
            "",
            "| 模型 | 策略 | 配对数 | 总 K | 总 Y | 平均 Y | 总 delta_Y |",
        ]
    else:
        lines = [
            "# Measurement value under a fixed budget",
            "",
            "**SYNTHETIC TEST DATA; not empirical results.**"
            if result["synthetic"]
            else "Cost replay of the supplied records.",
            "",
            f"Declared evidence status: `{result['evidence_status']}`.",
            f"Input file SHA256: `{result['input_sha256']}`.",
            "",
            "The input declares this status; integrity and label availability "
            "do not upgrade evidence.",
            "A discovery is abs(risk_target-risk_source); both risk increases and decreases count.",
            "K counts completed paired audits, p their discovery fraction, and Y discoveries.",
            "Every delta_Y compares with the unpaid direct strategy in the same case.",
            "",
            "The table aggregates by model and strategy. strategies.csv retains each case;",
            "results.json retains the full queues and exact decomposition.",
            "Cases without both probe_seconds and selection_seconds have no paid-strategy rows.",
            "",
            "| Model | Strategy | Pairs | Total K | Total Y | Mean Y | Total delta_Y |",
        ]
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in result["rows"]:
        groups[(row["model"], row["strategy"])].append(row)
    for (model, strategy), rows in sorted(groups.items()):
        total_y = sum(row["Y"] for row in rows)
        lines.append(
            f"| {_cell(model)} | {_cell(strategy)} | {len(rows)} | "
            f"{sum(row['K'] for row in rows)} | {total_y} | {total_y / len(rows):.6f} | "
            f"{sum(row['delta_Y'] for row in rows)} |"
        )
    lines.extend(
        [
            "",
            "`delta_Y = K_s*(p_s-p_0) - (K_0-K_s)*p_0`.",
            "",
            (
                "这是标准计数恒等式，不是论文的新定理。精确有理数项在 JSON 中保留。"
                "K=0 时 p 为 null；K_0=0 时精度分解未定义，但 Y 与 delta_Y 仍保留。"
                if chinese
                else "This is a standard accounting identity, not a new theorem from the paper. "
                "Exact rational terms are retained in JSON. p is null at K=0; "
                "the precision decomposition is undefined "
                "at K_0=0, while Y and delta_Y remain defined."
            ),
            "",
            (
                "精度盈亏阈值是 Y_0/K_s；大于 1 表示该完成量下即使全部命中也无法追平 direct。"
                "只有观察到的计数参与这项描述，不据此保证下一案例的表现。"
                if chinese
                else "The break-even precision is Y_0/K_s. A value above one means even "
                "perfect precision cannot match direct at that audit count. "
                "This describes observed counts and gives no "
                "guarantee for a future case."
            ),
            "",
            (
                "T 是论文控制时域，L 是生成长度上限，B 是墙钟时间预算，三者不可互换。"
                if chinese
                else "T is the paper's control horizon, L the decode cap, "
                "and B the wall-clock budget; "
                "they are distinct quantities."
            ),
            "",
            (
                "理论边界和独立的锁定决策接口见 "
                if chinese
                else "Theory boundaries and the separate locked-decision interface: "
            )
            + "[measurement-value case documentation]"
            + "(https://github.com/VeraPyuyi/prompt_control_lab/tree/main/docs/case_studies/measurement_value).",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Versioned JSON fixture")
    parser.add_argument("--out", required=True, type=Path, help="Output directory")
    args = parser.parse_args()
    try:
        for name in ("results.json", "strategies.csv", "report.md", "report.zh.md"):
            output = args.out / name
            if output.resolve() == args.input.resolve() or (
                output.exists() and args.input.exists() and output.samefile(args.input)
            ):
                raise ValueError("output would overwrite the input fixture")
        source_bytes = args.input.read_bytes()
        document = json.loads(source_bytes.decode("utf-8-sig"))
        if not isinstance(document, dict):
            raise ValueError("input must be a JSON object")
        result = analyze_document(document)
        result["input_sha256"] = hashlib.sha256(source_bytes).hexdigest()
        serialized = json.dumps(
            result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
        )
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(2, f"Invalid input: {error}\n")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(serialized + "\n", encoding="utf-8", newline="\n")
    with (args.out / "strategies.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in result["rows"]:
            flat = {key: row.get(key) for key in CSV_FIELDS}
            flat.update(
                {
                    "evidence_status": result["evidence_status"],
                    "synthetic": result["synthetic"],
                    "decomposition_status": row["decomposition"]["status"],
                    "precision_gain": row["decomposition"]["precision_gain"],
                    "capacity_loss": row["decomposition"]["capacity_loss"],
                }
            )
            writer.writerow(flat)
    for chinese, name in ((False, "report.md"), (True, "report.zh.md")):
        (args.out / name).write_text(
            _report(result, chinese=chinese), encoding="utf-8", newline="\n"
        )
    print(f"Wrote {len(result['rows'])} strategy rows and four artifacts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
