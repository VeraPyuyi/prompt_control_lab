"""Readable bilingual reports and deterministic plots of supplied research quantities."""

# Report prose and SVG template literals preserve intentional multilingual punctuation.
# ruff: noqa: E501, RUF001

from __future__ import annotations

import html
import math
from bisect import bisect_right
from fractions import Fraction
from pathlib import Path
from typing import Any

from .common import JsonDict


def measurement_profiles(document: JsonDict, result: JsonDict) -> JsonDict:
    """Replay fixed queues efficiently at fractions of each case's own budget."""
    from .measurement_value import STRATEGIES, _number, _validated_case

    grid = [Fraction(index, 20) for index in range(21)]
    curves: dict[tuple[str, str], list[JsonDict]] = {}
    costs: dict[tuple[str, str], JsonDict] = {}
    for raw in document["cases"]:
        case = _validated_case(raw)
        prefixes: dict[str, list[tuple[int, int]]] = {}
        for paid in [False] if case["paid"] is None else [False, True]:
            for strategy in STRATEGIES:
                name = f"paid_{strategy}" if paid else strategy
                upfront = case["overhead"][strategy] + (case["paid"] if paid else 0)
                cumulative, discoveries, consumed, found = [], [0], Fraction(0), 0
                for item in case["orders"][strategy]:
                    consumed += case["generation"][item]
                    found += abs(
                        case["labels"]["risk_target"][item] - case["labels"]["risk_source"][item]
                    )
                    cumulative.append(consumed)
                    discoveries.append(found)
                prefixes[name] = []
                for fraction in grid:
                    available = case["budget"] * fraction - upfront
                    count = bisect_right(cumulative, available) if available >= 0 else 0
                    prefixes[name].append((count, discoveries[count]))
        for strategy, points in prefixes.items():
            key = (case["model"], strategy)
            if key not in curves:
                curves[key] = [
                    {"budget_fraction": float(fraction), "K": 0, "Y": 0, "delta_Y": 0}
                    for fraction in grid
                ]
            for index, (count, found_count) in enumerate(points):
                curves[key][index]["K"] += count
                curves[key][index]["Y"] += found_count
                curves[key][index]["delta_Y"] += found_count - prefixes["direct"][index][1]
        id_index = {item: index for index, item in enumerate(raw["item_ids"])}
        for row in result["rows"]:
            if (row["model"], row["pair"]) != (raw["model"], raw["pair"]):
                continue
            strategy = row["strategy"].removeprefix("paid_")
            paid = row["strategy"].startswith("paid_")
            ledger = raw["costs"]
            components = {
                "probe": ledger.get("probe_seconds", 0) if paid else 0,
                "selection": ledger.get("selection_seconds", 0) if paid else 0,
                "scan": 0 if strategy == "direct" else ledger["scan_seconds"][strategy],
                "sort": ledger["direct_sort_seconds"]
                if strategy == "direct"
                else ledger["sort_seconds"][strategy],
                "transmission": ledger.get("transmission_seconds", 0),
                "generation": 0,
            }
            exact = {name: _number(value, name) for name, value in components.items()}
            for item in row["completed_item_ids"]:
                index = id_index[item]
                exact["generation"] += _number(
                    ledger["generation_pair_seconds"][index], "generation"
                )
                exact["transmission"] += _number(
                    ledger.get("transmission_pair_seconds", [0] * len(id_index))[index],
                    "transmission",
                )
            key = (raw["model"], row["strategy"])
            target = costs.setdefault(key, {name: Fraction(0) for name in exact})
            for name, value in exact.items():
                target[name] += value
    return {
        "scope": "At each fraction, every case receives that fraction of its own budget; fixed queues and all declared costs are replayed without refitting.",
        "curves": [
            {"model": model, "strategy": strategy, "points": points}
            for (model, strategy), points in sorted(curves.items())
        ],
        "cost_breakdown": [
            {
                "model": model,
                "strategy": strategy,
                "seconds": {name: float(value) for name, value in values.items()},
            }
            for (model, strategy), values in sorted(costs.items())
        ],
    }


def _cell(value: Any) -> str:
    if value is None:
        return "—"
    if type(value) is float:
        return format(value, ".5g")
    return str(value)


def _table(headers: list[str], rows: list[list[Any]]) -> tuple[str, str]:
    h = (
        "<div class='table-scroll'><table><thead><tr>"
        + "".join(f"<th>{html.escape(value)}</th>" for value in headers)
        + "</tr></thead><tbody>"
    )
    h += (
        "".join(
            "<tr>" + "".join(f"<td>{html.escape(_cell(value))}</td>" for value in row) + "</tr>"
            for row in rows
        )
        + "</tbody></table></div>"
    )

    def md(value: Any) -> str:
        return _cell(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")

    m = "| " + " | ".join(headers) + " |\n| " + " | ".join("---" for _ in headers) + " |\n"
    m += "".join("| " + " | ".join(md(value) for value in row) + " |\n" for row in rows)
    return h, m


def _plot(
    title: str, series: list[tuple[str, list[tuple[float, float | None]]]], xlabel: str, ylabel: str
) -> str:
    """Render deterministic SVG and tabular evidence from supplied numeric series."""
    width, height, left, top, right, bottom = 840, 370, 76, 44, 30, 90
    values = [
        (x, y) for _, points in series for x, y in points if y is not None and math.isfinite(y)
    ]
    if not values:
        return ""
    xmin, xmax = min(x for x, _ in values), max(x for x, _ in values)
    ymin, ymax = min(0.0, min(y for _, y in values)), max(0.0, max(y for _, y in values))
    if xmax == xmin:
        xmax = xmin + 1
    if ymax == ymin:
        ymax = ymin + 1
    gap = (ymax - ymin) * 0.08
    ymin, ymax = ymin - gap, ymax + gap

    def position(x: float, y: float) -> tuple[float, float]:
        return (
            left + (x - xmin) / (xmax - xmin) * (width - left - right),
            top + (ymax - y) / (ymax - ymin) * (height - top - bottom),
        )

    palette = [
        "#1d4ed8",
        "#ea580c",
        "#059669",
        "#7c3aed",
        "#be123c",
        "#0891b2",
        "#4f46e5",
        "#52525b",
    ]
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title, quote=True)}"><rect width="100%" height="100%" rx="12" fill="#fff"/><g font-family="system-ui,sans-serif" font-size="12" fill="#475569">',
        f'<text x="{left}" y="23" font-size="16" fill="#0f172a">{html.escape(title)}</text>',
    ]
    for index in range(5):
        value = ymin + (ymax - ymin) * index / 4
        _, y = position(xmin, value)
        svg += [
            f'<line x1="{left}" y1="{y:.2f}" x2="{width - right}" y2="{y:.2f}" stroke="#e2e8f0"/>',
            f'<text x="{left - 8}" y="{y + 4:.2f}" text-anchor="end">{_cell(value)}</text>',
        ]
        xvalue = xmin + (xmax - xmin) * index / 4
        x, _ = position(xvalue, ymin)
        svg.append(
            f'<text x="{x:.2f}" y="{height - bottom + 20}" text-anchor="middle">{_cell(xvalue)}</text>'
        )
    for index, (name, points) in enumerate(series):
        color = palette[index % len(palette)]
        segments: list[list[tuple[float, float]]] = [[]]
        for point_x, point_y in points:
            if point_y is None:
                segments.append([])
            else:
                segments[-1].append(position(point_x, point_y))
        for segment in segments:
            if not segment:
                continue
            coords = " ".join(f"{x:.2f},{y:.2f}" for x, y in segment)
            dash = ' stroke-dasharray="5 4"' if name.startswith("paid_") else ""
            svg.append(
                f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2"{dash}/>'
            )
            for x, y in segment:
                svg.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.5" fill="{color}"/>')
        lx, ly = left + (index % 4) * 178, height - 33 + (index // 4) * 18
        svg += [
            f'<line x1="{lx}" y1="{ly}" x2="{lx + 17}" y2="{ly}" stroke="{color}" stroke-width="3"/>',
            f'<text x="{lx + 22}" y="{ly + 4}">{html.escape(name)}</text>',
        ]
    svg += [
        f'<text x="{(left + width - right) / 2}" y="{height - bottom + 39}" text-anchor="middle">{html.escape(xlabel)}</text>',
        f'<text transform="translate(18 {(top + height - bottom) / 2}) rotate(-90)" text-anchor="middle">{html.escape(ylabel)}</text>',
        "</g></svg>",
    ]
    return "".join(svg)


def render_sections(result: JsonDict, language: str, out_dir: Path) -> tuple[str, str]:
    """Build bilingual explanations, metric tables, and plots from research results."""
    zh = language == "zh"

    def t(en: str, cn: str) -> str:
        return cn if zh else en

    sections, markdown = [], []

    def paragraph(en: str, cn: str) -> None:
        content = t(en, cn)
        sections.append(f"<p>{html.escape(content)}</p>")
        markdown.append(content + "\n")

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

    kind = result.get("kind")
    evidence = result.get("evidence", {})
    source = (
        t(
            "Linked receipt contents checked; dates remain unauthenticated",
            "已核对记录内容链接；日期仍未经外部认证",
        )
        if evidence.get("linked_receipts_verified")
        else t(
            "Supplied records; independent provenance not verified", "输入记录；独立来源未经核验"
        )
    )
    numeric = t("Recomputed from supplied inputs", "已从输入重新计算")
    premise = t("Local diagnostic only; no model-wide proof", "仅局部诊断，不构成整个模型的证明")
    if kind == "replay":
        source = str(result["integrity"]["status"])
        checks = result["numerical_replay"]["checks"]
        statuses = [row["status"] for row in checks]
        numeric = (
            "failed"
            if "failed" in statuses
            else "passed"
            if statuses and all(x == "passed" for x in statuses)
            else "not_supplied / partial"
        )
        premise = str(result["theoretical_checks"]["status"])
    cards = [
        (t("Source integrity", "来源与完整性"), source),
        (t("Numerical replay", "数值复算"), numeric),
        (t("Theoretical premises", "理论前提"), premise),
    ]
    sections.append(
        "<div class='cards'>"
        + "".join(
            f"<article><small>{html.escape(label)}</small><p>{html.escape(value)}</p></article>"
            for label, value in cards
        )
        + "</div>"
    )
    markdown.append("\n".join(f"- **{label}:** {value}" for label, value in cards) + "\n")
    if kind == "measurement-value":
        aggregated: dict[tuple[str, str], JsonDict] = {}
        for row in result["rows"]:
            item = aggregated.setdefault(
                (row["model"], row["strategy"]),
                {"K": 0, "Y": 0, "delta_Y": 0, "upfront": 0.0, "audit": 0.0},
            )
            for key in ("K", "Y", "delta_Y"):
                item[key] += row[key]
            item["upfront"] += row["upfront_seconds"]
            item["audit"] += row["audit_seconds"]
        better = sum(
            item["delta_Y"] > 0
            for (_, strategy), item in aggregated.items()
            if strategy != "direct"
        )
        exhausted = sum(row["K"] == 0 for row in result["rows"])
        paragraph(
            f"{len(result['cases'])} fixed model/pair cases were replayed. {better} model/strategy aggregates found more changes than direct evaluation at the declared budgets; {exhausted} case/strategy records completed no paired audit. These are observed net gains after declared costs, not a future-case guarantee.",
            f"已复算 {len(result['cases'])} 个固定模型/配对案例。在声明预算下，{better} 个模型/策略汇总的发现量超过直接评估；{exhausted} 条案例/策略记录未完成任何配对检查。这些是在声明成本下的观察净收益，不保证未来案例表现。",
        )
        table(
            [
                t("Model", "模型"),
                t("Strategy", "策略"),
                "K",
                "Y",
                "ΔY",
                t("Upfront s", "前置秒"),
                t("Audit s", "检查秒"),
            ],
            [
                [
                    model,
                    strategy,
                    item["K"],
                    item["Y"],
                    item["delta_Y"],
                    item["upfront"],
                    item["audit"],
                ]
                for (model, strategy), item in sorted(aggregated.items())
            ],
        )
        profiles = result.get("budget_profiles", {})
        paragraph(
            "Budget curves replay the same fixed queues at fractions of each case's own budget. The zero line is direct evaluation; negative values mean fewer discovered changes. No selection is refitted at any budget.",
            "预算曲线将每个案例自己的预算按同比例缩放，并重新执行相同固定队列。零线对应直接评估，负值表示发现的变化更少。任何预算点都不重新拟合选择规则。",
        )
        for index, model in enumerate(sorted({row["model"] for row in profiles.get("curves", [])})):
            series = [
                (
                    row["strategy"],
                    [(point["budget_fraction"], point["delta_Y"]) for point in row["points"]],
                )
                for row in profiles["curves"]
                if row["model"] == model
            ]
            plot(
                f"budget-gain-{index}",
                str(model),
                series,
                t("Fraction of each case budget", "各案例预算比例"),
                t("Net discoveries ΔY", "净发现量 ΔY"),
            )
        breakdown = profiles.get("cost_breakdown", [])
        table(
            [
                t("Model / strategy", "模型 / 策略"),
                t("Probe s", "探针秒"),
                t("Select s", "选择秒"),
                t("Scan s", "扫描秒"),
                t("Sort s", "排序秒"),
                t("Transmit s", "传输秒"),
                t("Generate s", "生成秒"),
            ],
            [
                [
                    f"{row['model']} / {row['strategy']}",
                    *[
                        row["seconds"][key]
                        for key in (
                            "probe",
                            "selection",
                            "scan",
                            "sort",
                            "transmission",
                            "generation",
                        )
                    ],
                ]
                for row in breakdown
            ],
        )
    elif kind == "readout":
        rows = result["conditions"]
        paragraph(
            f"{len(rows)} saved-output conditions share the same {rows[0]['item_count']}-item ordered panel and gold answers. Parse-success switching and correctness change are separate targets. AUC gaps are diagnostic-minus-loss; missing values mean the target had no class contrast.",
            f"{len(rows)} 个保存输出条件使用相同的 {rows[0]['item_count']} 样本有序面板和金标。解析成功切换与正确性变化分别统计。AUC 差为诊断减损失分数；空值表示目标没有正负类别对照。",
        )
        table(
            [
                t("Condition", "条件"),
                t("Parser / version", "解析器 / 版本"),
                t("Posthoc", "事后"),
                t("Token budget", "token 预算"),
                t("Parse switches", "解析切换"),
                t("Correctness changes", "正确性变化"),
                t("Primary AUC gap", "主诊断 AUC 差"),
            ],
            [
                [
                    row["condition_id"],
                    f"{row['parser']['rule']} / {row['parser']['version']}",
                    row["parser"]["posthoc"],
                    row["budget_tokens"],
                    sum(sample["parse_switch"] for sample in row["samples"]),
                    sum(sample["correctness_change"] for sample in row["samples"]),
                    row["auc_gaps"]["correctness_change"].get("primary"),
                ]
                for row in rows
            ],
        )
        names = sorted({name for row in rows for name in row["auc_gaps"]["correctness_change"]})
        plot(
            "readout-gaps",
            t("Readout-dependent diagnostic gaps", "读出条件下的诊断差异"),
            [
                (
                    name,
                    [
                        (float(i + 1), row["auc_gaps"]["correctness_change"].get(name))
                        for i, row in enumerate(rows)
                    ],
                )
                for name in names
            ],
            t("Condition number (table order)", "条件序号（表中顺序）"),
            "AUC gap",
        )
        paragraph(
            "A parser marked posthoc stays posthoc. A saved token prefix is not a fresh shorter-budget generation. This comparison does not establish which parser or decoding policy generalizes best.",
            "标记为事后分析的解析器仍属于事后分析。保存 token 的前缀不是真实重新运行的短预算生成。本比较不能确定哪种解析或解码策略具有最佳泛化表现。",
        )
    elif kind == "response":
        rows = result["rows"]
        undefined = sum(row["response_gain"] is None for row in rows)
        paragraph(
            f"{len(rows)} local response records were recomputed; {undefined} have zero control displacement and therefore undefined response gain. Alignment is a signed cosine, subspace fraction uses the supplied orthonormal basis, and residual measures the supplied local linear approximation.",
            f"已复算 {len(rows)} 条局部响应记录；其中 {undefined} 条控制位移为零，响应增益无定义。对齐量是带符号余弦，子空间比例使用提供的正交基，残差衡量提供的局部线性近似。",
        )
        table(
            [
                t("Record", "记录"),
                "Δloss",
                "‖Δu‖",
                "‖Δy‖/‖Δu‖",
                t("Alignment", "读出对齐"),
                t("Subspace", "子空间比例"),
                t("Residual", "近似残差"),
            ],
            [
                [
                    row["record_id"],
                    row["loss_delta"],
                    row["control_displacement"],
                    row["response_gain"],
                    row["readout_alignment"],
                    row["subspace_fraction"],
                    row["approximation_residual"],
                ]
                for row in rows
            ],
        )
        plot(
            "response-gain",
            t("Local response gain", "局部响应增益"),
            [
                (
                    "response_gain",
                    [(float(i + 1), row["response_gain"]) for i, row in enumerate(rows)],
                )
            ],
            t("Record number", "记录序号"),
            "‖Δy‖ / ‖Δu‖",
        )
        table(
            [t("Metadata", "元数据"), t("Declaration", "声明")],
            [[key, value] for key, value in result["metadata"].items()],
        )
        paragraph(
            "Lower loss, large response, and readout alignment answer different questions. These finite-dimensional quantities do not demonstrate a Transformer-wide mechanism or independently verify calibration separation.",
            "损失降低、响应幅度和读出对齐分别回答不同问题。这些有限维量不证明整个 Transformer 的机制，也不独立验证校准集分离。",
        )
    elif kind == "transfer":
        rows = result["summaries"]
        defined = sum(pair["status"] == "defined" for pair in result["pairs"])
        paragraph(
            f"Frozen predictions were compared on {defined}/{len(result['pairs'])} pairs with defined AUC. MAE compares full control, cheap features, common mean and zero forecasts. Smaller MAE indicates better prediction of this supplied AUC gap, not greater evaluation efficiency.",
            f"已在 {defined}/{len(result['pairs'])} 个 AUC 有定义的配对上比较冻结预测。MAE 对比完整控制、廉价特征、统一均值和零预测。较小 MAE 表示对这些输入 AUC 差的预测更准确，不等于评估效率更高。",
        )
        table(
            [
                t("Model / score", "模型 / 分数"),
                t("Valid pairs", "有效配对"),
                "Full MAE",
                "Cheap MAE",
                "Mean MAE",
                "Zero MAE",
            ],
            [
                [
                    f"{row['model']} / {row['score']}",
                    f"{row['common_valid_pairs']}/{row['pair_count']}",
                    *[row["mae"][name] for name in ("full", "cheap", "uniform_mean", "zero")],
                ]
                for row in rows
            ],
        )
        plot(
            "transfer-mae",
            t("Frozen forecast errors", "冻结预测误差"),
            [
                (name, [(float(i + 1), row["mae"][name]) for i, row in enumerate(rows)])
                for name in ("full", "cheap", "uniform_mean", "zero")
            ],
            t("Model / score row", "模型 / 分数行序号"),
            "MAE",
        )
        for model in result.get("bootstrap", {}).get("models", []):
            paragraph(
                f"{model['model']}: {model.get('endpoint_component_count', 0)} endpoint components; {model['valid_repetitions']} valid resamples; status {model['status']}. {model.get('endpoint_uncertainty', '')}. All comparisons share the same resampled item indices and endpoint components.",
                f"{model['model']}：{model.get('endpoint_component_count', 0)} 个端点连通组，{model['valid_repetitions']} 次有效重采样，状态 {model['status']}。{model.get('endpoint_uncertainty', '')}。所有比较共享相同的样本索引与端点组重采样。",
            )
            if model.get("intervals"):
                table(
                    [
                        t("Score / baseline", "分数 / 基线"),
                        t("MAE gain", "MAE 改善"),
                        t("Lower", "下限"),
                        t("Upper", "上限"),
                    ],
                    [
                        [
                            f"{row['score']} / {row['baseline']}",
                            row["mae_improvement"],
                            row["lower"],
                            row["upper"],
                        ]
                        for row in model["intervals"]
                    ],
                )
        paragraph(
            "One connected endpoint component supports only conditional item uncertainty. Bands are simultaneous within each model and conditional on the supplied dependency graph; undefined AUCs are never replaced by zero or 0.5. No forecast is refitted from these labels.",
            "只有一个端点连通组时，仅能表达给定端点组下的样本不确定性。区间在每个模型内部同时计算，并以提供的依赖关系为条件；无定义 AUC 不替换为零或 0.5。预测不会使用这些标签重新拟合。",
        )
    elif kind == "replay":
        checks = result["numerical_replay"]["checks"]
        paragraph(
            "File integrity, numerical agreement and theoretical premises are independent outcomes. An exact byte mismatch can coexist with a numerical pass within tolerance. Missing expected outputs remain unverified.",
            "文件完整性、数值一致性和理论前提分别给出结论。字节不一致与容差范围内的数值通过可以同时成立。未提供预期输出的项目仍未核验。",
        )
        table(
            [
                t("Input", "输入"),
                t("Tool", "工具"),
                t("Numerical status", "数值状态"),
                t("Differences", "差异数"),
            ],
            [
                [
                    row["input_file"],
                    row["kind"],
                    row["status"],
                    None if row["differences"] is None else len(row["differences"]),
                ]
                for row in checks
            ],
        )
        table(
            [t("File", "文件"), t("Hash status", "哈希状态"), t("Encoding", "编码")],
            [[row["file"], row["status"], row["encoding"]] for row in result["integrity"]["files"]],
        )
        theories = result["theoretical_checks"]["checks"]
        table(
            [
                t("Local check", "局部检查"),
                t("Conditions", "条件"),
                t("Certificate scope", "证书范围"),
            ],
            [[row["kind"], row["status"], row["certificate_level"]] for row in theories],
        )
        plot(
            "replay-status",
            t("Checks by outcome", "各类检查数量"),
            [
                (
                    status,
                    [
                        (float(i + 1), float(sum(row["status"] == status for row in group)))
                        for i, group in enumerate([result["integrity"]["files"], checks])
                    ],
                )
                for status in ("passed", "failed", "not_supplied")
            ],
            t("1 = file integrity, 2 = numerical replay", "1 = 文件完整性，2 = 数值复算"),
            t("Check count", "检查数量"),
        )
        paragraph(
            "Only allowlisted computations run. The bundle cannot execute commands, read arbitrary external paths or load pickle. Local certificate success applies only to its supplied surrogate and premises.",
            "仅执行白名单中的计算。清单不能运行任意命令、读取任意外部路径或加载 pickle。局部证书通过仅适用于提供的代理系统及其前提。",
        )
    return "\n".join(sections), "\n\n".join(markdown)
