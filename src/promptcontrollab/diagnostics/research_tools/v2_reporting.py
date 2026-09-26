"""Bilingual v2 reports that preserve missing data and distinct evidential targets."""

# Multilingual report prose preserves intentional punctuation and readable sentences.
# ruff: noqa: E501, RUF001

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from .common import JsonDict
from .reporting import _plot, _table


def render_sections(result: JsonDict, language: str, out_dir: Path) -> tuple[str, str]:
    """Render bilingual version-two diagnostic explanations and portable figures."""
    zh = language == "zh"
    sections: list[str] = []
    markdown: list[str] = []

    def t(en: str, cn: str) -> str:
        return cn if zh else en

    def paragraph(en: str, cn: str) -> None:
        value = t(en, cn)
        sections.append(f"<p>{html.escape(value)}</p>")
        markdown.append(value + "\n")

    def table(headers: list[str], rows: list[list[Any]]) -> None:
        h, m = _table(headers, rows)
        sections.append(h)
        markdown.append(m)

    def plot(
        name: str,
        title: str,
        series: list[tuple[str, list[tuple[float, float | None]]]],
        x: str,
        y: str,
    ) -> None:
        svg = _plot(title, series, x, y)
        if svg:
            filename = f"{name}.{language}.svg"
            (out_dir / filename).write_text(svg, encoding="utf-8")
            sections.append(f"<figure>{svg}</figure>")
            markdown.append(f"![{title}]({filename})\n")

    paragraph(
        "Version 2 keeps measured records, saved summaries, and independent evidence claims separate. Missing values remain unknown.",
        "第二版分别呈现实测记录、保存的汇总表和独立证据声明。缺失值保留为未知。",
    )
    table(
        [t("Evidence channel", "证据通道"), t("Result", "结果")],
        [
            [
                t("Computation", "计算类型"),
                t(
                    "Saved summaries only; raw records not recomputed",
                    "仅保存的汇总；未复算原始记录",
                )
                if not result["raw_recomputation"]
                else t("Recomputed from supplied records", "根据输入记录复算"),
            ],
            [t("Source claim", "来源声明"), result["evidence"]["declared"]],
            [t("Chronological independence", "时间独立性"), t("Not verified", "未核验")],
            [t("Theory scope", "理论范围"), t("Supplied local records only", "仅所提供的局部记录")],
        ],
    )
    if not result["raw_recomputation"]:
        paragraph(
            "These tables are imported evidence, not reconstruction of missing raw activations, labels or timing traces.",
            "这些表格是导入的证据，不代表重建了缺失的原始激活、标签或计时轨迹。",
        )
        table(
            [t("Saved summaries", "保存的汇总")],
            [[json.dumps(result["summaries"], ensure_ascii=False)]],
        )
        return "".join(sections), "\n".join(markdown)
    kind = result["kind"]
    if kind == "readout":
        paragraph(
            "The fixed-score and initial-answer premise is checked separately from observed changes. A failed premise retains the inference perturbation results but cannot support a readout-only claim. Parse status, answer changes, correctness and ranking remain separate. Stored prefixes are not real short-generation runs.",
            "固定分数与初始答案前提与观察变化分别核验。前提不满足时仍保留推理条件扰动结果，但不能支持仅改变读出的结论。解析状态、答案变化、正确性和排序分别计算。保存前缀不等同于真实短生成。",
        )
        table(
            [t("Claim premise", "结论前提"), t("Status", "状态")],
            [
                [
                    t("Fixed scores and preserved initial answers", "固定分数与初始答案保留"),
                    result["fixed_score_initial_answer_preserving_claim"],
                ]
            ],
        )
        table(
            [
                t("Condition", "条件"),
                t("Comparison scope", "比较范围"),
                t("Same execution", "执行条件相同"),
                t("Same source records", "原始输出相同"),
            ],
            [
                [
                    row["condition_id"],
                    t("Readout only", "仅改变读出")
                    if row["comparison_class"] == "readout_only"
                    else t("Inference or output perturbation", "执行或输出发生扰动"),
                    row["execution_conditions_preserved"],
                    row["source_records_preserved"],
                ]
                for row in result["conditions"]
            ],
        )
        table(
            [
                t("Condition", "条件"),
                t("Parser", "解析器"),
                t("Generation", "生成方式"),
                t("Batch", "批量"),
                t("Stopping", "停止条件"),
                t("Precision", "精度"),
                t("Template", "模板"),
                t("Parse changes", "解析变化"),
                t("Answer changes", "答案变化"),
                t("Correctness changes", "正确性变化"),
            ],
            [
                [
                    row["condition_id"],
                    row["parser"]["rule"],
                    row["generation_mode"],
                    row["comparison_axes"]["batch_size"],
                    row["comparison_axes"]["stopping"],
                    row["comparison_axes"]["precision"],
                    row["comparison_axes"]["template_id"],
                    row["changes_from_reference"]["parse_status_changes"],
                    row["changes_from_reference"]["parsed_answer_changes"],
                    row["changes_from_reference"]["correctness_changes"],
                ]
                for row in result["conditions"]
            ],
        )
        table(
            [
                t("Condition", "条件"),
                t("Outcome", "目标"),
                t("Score", "分数"),
                "AUC",
                t("Gap vs loss", "相对损失差值"),
            ],
            [
                [row["condition_id"], target, name, value, row["auc_gaps"][target].get(name)]
                for row in result["conditions"]
                for target, scores in row["auc"].items()
                for name, value in scores.items()
            ],
        )
    elif kind == "response":
        paragraph(
            "Calibration, measurement and evaluation label uses are declared separately. Fixed-coefficient replacement and refitting have different evidence requirements. Local response properties do not establish whole-model properties.",
            "校准、测量和评估阶段的标签用途分别声明。固定系数读出替换与重新拟合采用不同的证据要求。局部响应性质不证明整个模型的性质。",
        )
        table(
            [t("Stage", "阶段"), t("Label use", "标签用途")],
            [list(row) for row in result["label_usage"].items()],
        )
        table(
            [
                t("Record", "记录"),
                t("Response gain", "响应增益"),
                t("Alignment", "对齐"),
                t("Residual", "残差"),
            ],
            [
                [
                    row["record_id"],
                    row["response_gain"],
                    row["readout_alignment"],
                    row["approximation_residual"],
                ]
                for row in result["rows"]
            ],
        )
        selection = result["selection_statistics"]
        if selection["status"] == "computed":
            paragraph(
                "Five question-group folds use within-pair AUC, equal pair weights and equal fold weights. Scores from different folds are never pooled to compute selection AUC.",
                "五个按题目分组的折内分别计算配对 AUC，再对配对及折等权平均。选择 AUC 从不混合不同折的分数。",
            )
            table(
                [
                    t("Score", "分数"),
                    t("Five-fold AUC", "五折 AUC"),
                    t("Gap vs loss", "相对损失差值"),
                ],
                [
                    [key, value, selection["auc_gaps"].get(key)]
                    for key, value in selection["mean_auc"].items()
                ],
            )
        for index, curve in enumerate(result["calibration_curves"]):
            paragraph(
                "Calibration curve: saved-bin summary only; raw calibration is not recomputed.",
                "校准曲线：仅使用保存的分箱汇总，未重新计算原始校准数据。",
            )
            plot(
                f"calibration-{index}",
                str(curve["readout_id"]),
                [
                    (
                        t("Saved curve", "保存的曲线"),
                        [(row["mean_prediction"], row["observed_rate"]) for row in curve["bins"]],
                    )
                ],
                t("Mean prediction", "平均预测"),
                t("Observed rate", "观察比例"),
            )
    elif kind == "measurement-value":
        paragraph(
            "Only complete measured batches finishing within budget count. Unknown components keep net value unknown. Primitive timings do not establish full-policy value or gains on larger models.",
            "仅统计预算内完成的实测批次。未知成本使净价值保留为未知。原语计时不证明完整策略价值，也不推断更大模型的收益。",
        )
        table(
            [
                t("Case", "案例"),
                t("Policy", "策略"),
                t("Batch", "批量"),
                t("Budget", "预算"),
                t("Consumed within budget", "预算内消耗"),
                t("Measured overrun", "实测超时"),
                "K",
                "Y",
                "ΔY",
                t("Gain evidence", "增益证据"),
                t("Unknown costs", "未知成本"),
            ],
            [
                [
                    case["case_id"],
                    row["strategy"],
                    row["actual_batch_size"],
                    row["budget_seconds"],
                    row["observed_spend_within_cutoff_seconds"],
                    row["measured_overrun_seconds"],
                    row["K"],
                    row["Y"],
                    row["delta_Y"],
                    row["gain_status"],
                    ", ".join(row["unknown_cost_components"]),
                ]
                for case in result["cases"]
                for row in case["policies"]
            ],
        )
        table(
            [t("Policy", "策略"), t("Cost component", "成本分项"), t("Seconds", "秒")],
            [
                [f"{case['case_id']}/{row['strategy']}", component, seconds]
                for case in result["cases"]
                for row in case["policies"]
                for component, seconds in row["cost_components_seconds"].items()
            ],
        )
        for index, case in enumerate(result["cases"]):
            plot(
                f"budget-{index}",
                case["case_id"],
                [
                    (
                        row["strategy"],
                        [
                            (
                                point["budget_seconds"],
                                next(
                                    policy["Y"]
                                    for policy in point["policies"]
                                    if policy["strategy"] == row["strategy"]
                                ),
                            )
                            for point in case["budget_curves"]
                        ],
                    )
                    for row in case["policies"]
                ],
                t("Budget seconds", "预算秒数"),
                t("Discovered changes", "发现的变化数"),
            )
    elif kind == "transfer":
        paragraph(
            "New questions and unseen prompts are distinct crossed axes. Group-average gain, pair-level prediction error and measured additional control value answer different questions. Provenance labels do not authorize independent confirmation.",
            "新题目与未见提示是不同的交叉轴。组平均增益、配对预测误差和实测额外控制价值回答不同的问题。来源标签不能授权独立确认。",
        )
        table(
            [
                t("Panel", "面板"),
                t("Questions", "题目轴"),
                t("Prompts", "提示轴"),
                t("Score", "分数"),
                t("Group gain", "组平均增益"),
                t("Pair MAE", "配对 MAE"),
                t("MAE improvement", "MAE 改善"),
                t("Control evidence", "控制证据"),
            ],
            [
                [
                    panel["panel_id"],
                    panel["axes"]["questions"],
                    panel["axes"]["prompts"],
                    row["score"],
                    row["group_mean_gain"],
                    row["pair_prediction_mae"]["full"],
                    row["mae_improvement_vs_group_mean"],
                    panel["additional_control_value"]["status"],
                ]
                for panel in result["panels"]
                for row in panel["summaries"]
            ],
        )
    elif kind == "replay":
        paragraph(
            "Integrity, numerical agreement, protocol premises and local theoretical checks are independent. Hashes cannot prove chronological prediction lock. Local properties cannot establish model-global claims.",
            "完整性、数值一致性、协议前提和局部理论检查彼此独立。哈希不能证明预测按时间顺序锁定。局部性质不能证明整个模型的性质。",
        )
        table(
            [t("Channel", "通道"), t("Status", "状态")],
            [list(row) for row in result["statuses"].items()],
        )
        table(
            [t("Kind", "类型"), t("Input", "输入"), t("Numerical status", "数值状态")],
            [
                [row["kind"], row["input_file"], row["status"]]
                for row in result["numerical_replay"]["checks"]
            ],
        )
    return "".join(sections), "\n".join(markdown)
