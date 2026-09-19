"""Standard-library replay of externally fixed control-diagnostic forecasts."""

# Chinese report text deliberately uses full-width punctuation.
# ruff: noqa: RUF001

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from promptcontrollab.transfer_prediction import analyze_document


def report(result, *, chinese=False):
    lines = [
        "# 控制诊断的独立迁移预测"
        if chinese
        else "# Fixed control-diagnostic transfer predictions",
        "",
    ]
    if result["synthetic"]:
        lines += [
            "**合成测试数据，不是实验结果。**"
            if chinese
            else "**SYNTHETIC TEST DATA; not research results.**",
            "",
        ]
    lines += [
        f"Evidence status: `{result['evidence_status']}`.",
        f"Input SHA256: `{result['input_file_sha256']}`.",
        f"External prediction lock: `{result['prediction_lock_sha256']}`.",
        "",
        "G = AUC(state diagnostic) - AUC(reference loss).",
        "",
        "| Model | Score | Valid pairs | Full MAE | Cheap MAE | Mean MAE | Zero MAE |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]

    def cell(value):
        return "undefined" if value is None else format(value, ".6g")

    for row in result["summaries"]:
        model = row["model"].replace("|", "\\|").replace("\n", " ").replace("\r", " ")
        lines.append(
            f"| {model} | {row['score']} | {row['common_valid_pairs']}/{row['pair_count']} | "
            + " | ".join(
                cell(row["mae"][name]) for name in ("full", "cheap", "uniform_mean", "zero")
            )
            + " |"
        )
    if chinese:
        lines += [
            "",
            "输入声明历史观察、锁定预测或独立确认状态。"
            "本脚本只复算固定分数的 AUC 差和预测误差，不从行为标签拟合规则。",
            "无定义 AUC 保留为空；逐对结果见 pairs.csv。"
            "独立性、原始张量和 token 重放、同时区间应由研究复现包另外核验。",
            "优于统一均值与优于廉价预测分别回答逐对信息和控制测量的增量价值；单个点估计不能替代校正区间。",
            "预测误差改善也不等于评估效率改善；后者还需计入探针、评分和行为检查成本。",
        ]
    else:
        lines += [
            "",
            "The input declares historical observation, locked prediction, or independent "
            "confirmation. This script recomputes fixed-score AUC gaps and prediction errors; "
            "it never fits a rule on behavior labels.",
            "Undefined AUCs remain null; pairs.csv retains every pair. Prospective isolation, "
            "raw tensor/token replay, and simultaneous intervals require the separate "
            "research bundle.",
            "Improvement over a common mean tests pair-specific information; improvement "
            "over cheap forecasts tests added control-measurement information. Point estimates "
            "do not replace corrected intervals.",
            "Better predictions alone do not establish evaluation efficiency: probes, scoring, "
            "and completed behavioral checks must also be charged.",
        ]
    lines += [
        "",
        "Theory and practice: [control-response theory](https://arxiv.org/abs/2606.17762), "
        "[PromptControlLab](https://github.com/VeraPyuyi/prompt_control_lab).",
        "",
    ]
    return "\n".join(lines)


def run(input_path, output):
    input_path, output = Path(input_path), Path(output)
    raw = input_path.read_bytes()
    result = analyze_document(json.loads(raw))
    result["input_file_sha256"] = hashlib.sha256(raw).hexdigest()
    if output.exists():
        raise FileExistsError("Use a new output directory to preserve earlier reports")
    output.mkdir(parents=True)
    (output / "results.json").write_text(
        json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    fields = (
        "model",
        "pair_id",
        "pairing_type",
        "status",
        "score",
        "predictor",
        "prediction",
        "observed_gap",
        "absolute_error",
    )
    with (output / "pairs.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for pair in result["pairs"]:
            for score, predictors in pair["predictions"].items():
                for predictor, value in predictors.items():
                    writer.writerow(
                        {
                            **{name: pair[name] for name in fields[:4]},
                            "score": score,
                            "predictor": predictor,
                            "prediction": value,
                            "observed_gap": pair["gains"][score]
                            if pair["gains"] is not None
                            else None,
                            "absolute_error": pair["errors"][score][predictor]["absolute"]
                            if pair["errors"] is not None and pair["errors"][score] is not None
                            else None,
                        }
                    )
    for chinese, name in ((False, "report.md"), (True, "report.zh.md")):
        (output / name).write_text(report(result, chinese=chinese), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.input, args.out)
    print(
        json.dumps(
            {"status": "replayed", "synthetic": result["synthetic"], "pairs": len(result["pairs"])}
        )
    )
