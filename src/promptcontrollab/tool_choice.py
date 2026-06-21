"""Adjacent-tool choice guidance for prompt_control_lab."""
# ruff: noqa: RUF001

from __future__ import annotations

from promptcontrollab.files import JsonDict


def tool_choice_lanes() -> list[JsonDict]:
    """Return PCL's recommended adjacent-tool lanes."""

    return [
        {
            "id": "security",
            "label": "Security and red-team evals",
            "label_zh": "安全评测和红队检查",
            "use_first": "Promptfoo",
            "when": "Security evals, red-team checks, CI eval matrices.",
            "when_zh": "安全评测, 红队检查, CI 评测矩阵.",
            "pcl_short": "Paired uncertainty, prompt-only validity, and claim boundaries.",
            "pcl_short_zh": "成对不确定性, prompt-only 有效性和 claim 边界.",
            "keywords": [
                "security",
                "red-team",
                "red team",
                "vulnerability",
                "jailbreak",
                "guardrail",
                "provider matrix",
                "ci",
                "安全",
                "红队",
                "越狱",
            ],
            "why": (
                "Promptfoo is strongest for LLM eval matrices, CI checks, "
                "and red-team/security testing."
            ),
            "why_zh": "Promptfoo 更适合做 LLM 评测矩阵、CI 检查和红队/安全测试。",
            "pcl_adds": (
                "Use PCL after Promptfoo when you need paired uncertainty, prompt-only validity, "
                "claim boundaries, and paper-diagnostic evidence."
            ),
            "pcl_adds_zh": (
                "当你需要成对不确定性、prompt-only 有效性、claim 边界和论文诊断证据时, "
                "再把 Promptfoo 结果导入 PCL."
            ),
            "commands": [
                (
                    "pcl import promptfoo --input results.json "
                    "--out runs/from-promptfoo --prompt-id candidate"
                ),
                (
                    "pcl evidence-audit --tool promptfoo --baseline-input baseline.json "
                    "--candidate-input candidate.json --out runs/from-promptfoo-audit"
                ),
            ],
            "avoid": "Do not ask PCL to replace Promptfoo's red-team plugin breadth.",
            "avoid_zh": "不要让 PCL 替代 Promptfoo 的红队插件广度; PCL 更适合做证据审计.",
        },
        {
            "id": "unit-tests",
            "label": "LLM unit tests and metrics",
            "label_zh": "LLM 单元测试和指标",
            "use_first": "DeepEval",
            "when": "Pytest-style LLM unit tests, assertions, and ready-made metrics.",
            "when_zh": "Pytest 风格 LLM 单元测试, 断言和现成指标.",
            "pcl_short": "Prompt/model/split provenance and claim checks around test results.",
            "pcl_short_zh": "围绕测试结果补 prompt/model/split 溯源和 claim 检查.",
            "keywords": [
                "unit test",
                "pytest",
                "deepeval",
                "metric",
                "assert",
                "component test",
                "单元测试",
                "测试",
                "指标",
                "断言",
                "组件测试",
            ],
            "why": "DeepEval is strongest for Pytest-style LLM tests and ready-made metrics.",
            "why_zh": "DeepEval 更适合写 Pytest 风格的 LLM 单元测试, 并直接使用现成指标.",
            "pcl_adds": (
                "Use PCL around DeepEval results when you need prompt/model/split provenance, "
                "paired uncertainty, and claim checks."
            ),
            "pcl_adds_zh": (
                "当 DeepEval 的测试结果需要 prompt、模型、切分溯源, 以及成对不确定性和 "
                "claim 检查时, 再用 PCL 包一层证据."
            ),
            "commands": [
                "pcl import deepeval --input deepeval-results.json --out runs/from-deepeval",
                "pcl evidence-card --run runs/from-deepeval",
            ],
            "avoid": "Do not ask PCL to become a broad LLM-as-judge metric catalog.",
            "avoid_zh": "不要让 PCL 变成大型 LLM-as-judge 指标库; 这不是它最强的方向.",
        },
        {
            "id": "observability",
            "label": "Observability and agent debugging",
            "label_zh": "观测和 agent 调试",
            "use_first": "LangSmith or Langfuse",
            "use_first_zh": "LangSmith 或 Langfuse",
            "when": "Traces, monitoring, cost, prompt registry, and agent debugging.",
            "when_zh": "trace, 监控, 成本, prompt registry 和 agent 调试.",
            "pcl_short": "Turn trace/eval exports into reproducible prompt-optimization evidence.",
            "pcl_short_zh": "把 trace/eval 导出变成可复现的 prompt 优化证据.",
            "keywords": [
                "trace",
                "tracing",
                "observability",
                "langsmith",
                "langfuse",
                "monitor",
                "cost",
                "prompt registry",
                "agent debug",
                "观测",
                "可观测",
                "监控",
                "成本",
                "追踪",
                "日志",
                "调试",
            ],
            "why": (
                "LangSmith and Langfuse are stronger for traces, monitoring, "
                "prompt registries, and production observability."
            ),
            "why_zh": "LangSmith 和 Langfuse 更适合 traces、监控、prompt registry 和生产可观测性。",
            "pcl_adds": (
                "Use PCL when those exports need to become reproducible prompt-optimization "
                "evidence with model provenance and research diagnostics."
            ),
            "pcl_adds_zh": (
                "当这些 trace / eval 导出需要变成带模型溯源和研究诊断的可复现 prompt "
                "优化证据时, 再用 PCL."
            ),
            "commands": [
                (
                    "pcl import langsmith --input langsmith-runs.csv "
                    "--out runs/from-langsmith --experiment candidate"
                ),
                (
                    "pcl import langfuse --input langfuse-export.json "
                    "--out runs/from-langfuse --name candidate"
                ),
            ],
            "avoid": "Do not ask PCL to replace hosted tracing dashboards or annotation queues.",
            "avoid_zh": "不要让 PCL 替代托管 trace dashboard 或标注队列; PCL 负责证据层.",
        },
        {
            "id": "prompt-writing",
            "label": "Prompt writing and rewriting",
            "label_zh": "Prompt 写作和改写",
            "use_first": "linshenkx/prompt-optimizer",
            "when": "Prompt rewriting, prompt assets, favorites, and interactive testing.",
            "when_zh": "prompt 改写, prompt 资产, 收藏和交互测试.",
            "pcl_short": "Prove whether optimized prompts improve under a clean protocol.",
            "pcl_short_zh": "证明优化后的 prompt 是否在干净协议下真的变好.",
            "keywords": [
                "rewrite prompt",
                "prompt writing",
                "prompt editor",
                "prompt optimizer",
                "prompt-optimizer",
                "better prompt",
                "favorite",
                "template",
                "chrome extension",
                "写作",
                "改写",
                "提示词",
                "提示词优化",
                "prompt 优化",
                "收藏",
                "模板",
                "浏览器插件",
            ],
            "why": (
                "prompt-optimizer is stronger as a polished prompt writing, "
                "prompt asset, and interactive testing product."
            ),
            "why_zh": "prompt-optimizer 更适合做成熟的 prompt 写作、prompt 资产管理和交互测试。",
            "pcl_adds": (
                "Use PCL after prompt-optimizer when an optimized prompt needs clean evaluation "
                "evidence before deployment or publication."
            ),
            "pcl_adds_zh": (
                "当优化后的 prompt 要上线、发表或给别人审查时, "
                "用 PCL 验证它是否真的在干净协议下变好."
            ),
            "commands": [
                (
                    "pcl import prompt-optimizer --input favorites.json "
                    "--out runs/from-prompt-optimizer"
                ),
                "pcl scaffold-check --run runs/from-prompt-optimizer",
            ],
            "avoid": (
                "Do not rebuild prompt-optimizer's prompt editor; "
                "prove whether its outputs improved."
            ),
            "avoid_zh": (
                "不要重做 prompt-optimizer 的编辑器; "
                "PCL 应该证明它产出的 prompt 是否可靠提升."
            ),
        },
        {
            "id": "research-evidence",
            "label": "Research evidence and diagnostics",
            "label_zh": "研究证据和论文诊断",
            "use_first": "prompt_control_lab",
            "when": "Paper-derived diagnostics, reproducibility, and safe claim boundaries.",
            "when_zh": "论文诊断, 可复现性和安全 claim 边界.",
            "pcl_short": "Research bundle, evidence card, soft-hard, trajectory, Riccati, tv-soft.",
            "pcl_short_zh": (
                "research bundle, evidence card, soft-hard, trajectory, Riccati, tv-soft."
            ),
            "keywords": [
                "paper",
                "research",
                "evidence",
                "claim",
                "reproducible",
                "tri-split",
                "soft-hard",
                "trajectory",
                "riccati",
                "tv-soft",
                "diagnose",
                "diagnostic",
                "diagnostics",
                "control-theoretic",
                "论文",
                "研究",
                "证据",
                "声明",
                "可复现",
                "诊断",
                "轨迹",
                "控制论",
            ],
            "why": (
                "PCL is strongest when the question is what a prompt optimization "
                "result can safely claim."
            ),
            "why_zh": "当问题是“这个 prompt 优化结果到底能安全说明什么”时, PCL 最合适.",
            "pcl_adds": (
                "Start directly with PCL for tri-split evaluation, paired statistics, "
                "soft-hard gap, trajectory, Riccati, and time-varying soft-control diagnostics."
            ),
            "pcl_adds_zh": (
                "直接用 PCL 跑 tri-split 评测、成对统计、soft-hard gap、trajectory、Riccati "
                "和 time-varying soft-control 诊断。"
            ),
            "commands": [
                "pcl research-demo --out runs/research-demo",
                "pcl diagnose --run runs/research-demo",
            ],
            "avoid": (
                "Do not start with PCL if the only need is a nicer prompt editor "
                "or tracing dashboard."
            ),
            "avoid_zh": "如果你只想要更好看的 prompt 编辑器或 trace dashboard, 不要先从 PCL 开始.",
        },
    ]


def choose_tool_for_need(need: str) -> JsonDict:
    """Return the best adjacent-tool lane for a free-text need."""

    text = need.lower().strip()
    lanes = tool_choice_lanes()
    best_lane: JsonDict | None = None
    best_score = 0
    for lane in lanes:
        keywords = lane.get("keywords")
        keyword_list = (
            [str(item).lower() for item in keywords] if isinstance(keywords, list) else []
        )
        score = 0
        if text == str(lane.get("id", "")).lower():
            score += 5
        score += sum(1 for keyword in keyword_list if keyword in text)
        if score > best_score:
            best_lane = lane
            best_score = score
    if best_lane is None:
        best_lane = next(lane for lane in lanes if lane["id"] == "research-evidence")
        best_score = 0
    matched = str(best_lane["id"])
    gap_action = market_gap_action_for_lane(matched, language="en")
    gap_action_zh = market_gap_action_for_lane(matched, language="zh")
    return {
        "need": need,
        "matched": matched,
        "matched_label": best_lane.get("label", matched),
        "matched_label_zh": best_lane.get("label_zh", best_lane.get("label", matched)),
        "confidence": "high" if best_score >= 2 else "medium" if best_score == 1 else "low",
        "use_first": best_lane["use_first"],
        "use_first_zh": best_lane.get("use_first_zh", best_lane["use_first"]),
        "why": best_lane["why"],
        "why_zh": best_lane.get("why_zh", best_lane["why"]),
        "pcl_adds": best_lane["pcl_adds"],
        "pcl_adds_zh": best_lane.get("pcl_adds_zh", best_lane["pcl_adds"]),
        "commands": best_lane["commands"],
        "avoid": best_lane["avoid"],
        "avoid_zh": best_lane.get("avoid_zh", best_lane["avoid"]),
        "market_gap_action": gap_action,
        "market_gap_action_zh": gap_action_zh,
        "adoption_path": adoption_path_rows(language="en"),
        "adoption_path_zh": adoption_path_rows(language="zh"),
    }


def market_gap_action_for_lane(lane_id: str, *, language: str = "en") -> JsonDict:
    """Return the closest market-gap action row for a chosen lane."""

    for row in market_gap_action_rows(language=language):
        if row.get("lane") == lane_id:
            return dict(row)
    fallback = "research-evidence" if lane_id == "research-evidence" else "security"
    return next(
        (
            dict(row)
            for row in market_gap_action_rows(language=language)
            if row.get("lane") == fallback
        ),
        {},
    )


def market_gap_action_rows(*, language: str = "en") -> list[JsonDict]:
    """Return action rows that turn adjacent-tool outputs into PCL next steps."""

    if language == "zh":
        return [
            {
                "lane": "security",
                "input": "Promptfoo eval 或红队导出",
                "gap": "有分数，但成对不确定性和 prompt-only 有效性还不清楚。",
                "command": (
                    "pcl evidence-audit --tool promptfoo ... "
                    "--out runs/from-promptfoo-audit"
                ),
                "open": "evidence_audit_result.html",
            },
            {
                "lane": "unit-tests",
                "input": "DeepEval TestRun 输出",
                "gap": "有指标，但 prompt/model/split provenance 和 claim 边界还需要审查。",
                "command": "pcl import deepeval --input test-run.json --out runs/from-deepeval",
                "open": "manifest.json, 然后运行 pcl evidence-card",
            },
            {
                "lane": "observability",
                "input": "LangSmith / Langfuse trace 或 eval 导出",
                "gap": "有 trace，但 prompt 效果可能和模型、指标、切分变化混在一起。",
                "command": (
                    "pcl start --choice import --tool auto --input results.json "
                    "--out runs/from-external"
                ),
                "open": "bridge_summary.html",
            },
            {
                "lane": "prompt-writing",
                "input": "prompt-optimizer 收藏或模板",
                "gap": "有更好的 prompt 候选，但还不是成对打分证据。",
                "command": (
                    "pcl import prompt-optimizer --input favorites.json "
                    "--out runs/from-prompt-optimizer"
                ),
                "open": "prompt_optimizer_gap_plan.html",
            },
            {
                "lane": "research-evidence",
                "input": "任意 baseline / candidate run",
                "gap": "还没有先打开论文诊断证据包，用户不容易理解各项诊断之间的关系。",
                "command": (
                    "pcl research-demo --out runs/research-demo && "
                    "pcl diagnose --run runs/research-demo"
                ),
                "open": "research_bundle.html",
            },
        ]
    return [
        {
            "lane": "security",
            "input": "Promptfoo eval or red-team export",
            "gap": (
                "Scores exist, but paired uncertainty and prompt-only validity may still be "
                "unclear."
            ),
            "command": (
                "pcl evidence-audit --tool promptfoo ... --out runs/from-promptfoo-audit"
            ),
            "open": "evidence_audit_result.html",
        },
        {
            "lane": "unit-tests",
            "input": "DeepEval TestRun output",
            "gap": (
                "Metrics exist, but prompt/model/split provenance and claim boundary need "
                "review."
            ),
            "command": "pcl import deepeval --input test-run.json --out runs/from-deepeval",
            "open": "manifest.json, then pcl evidence-card",
        },
        {
            "lane": "observability",
            "input": "LangSmith/Langfuse trace or eval export",
            "gap": (
                "Traces exist, but prompt effects may be confounded with model, metric, "
                "or split changes."
            ),
            "command": (
                "pcl start --choice import --tool auto --input results.json "
                "--out runs/from-external"
            ),
            "open": "bridge_summary.html",
        },
        {
            "lane": "prompt-writing",
            "input": "prompt-optimizer favorites/templates",
            "gap": "Better prompt candidates exist, but they are not yet paired scored evidence.",
            "command": (
                "pcl import prompt-optimizer --input favorites.json "
                "--out runs/from-prompt-optimizer"
            ),
            "open": "prompt_optimizer_gap_plan.html",
        },
        {
            "lane": "research-evidence",
            "input": "Any baseline/candidate run",
            "gap": "The paper-diagnostic evidence bundle has not been opened first.",
            "command": (
                "pcl research-demo --out runs/research-demo && "
                "pcl diagnose --run runs/research-demo"
            ),
            "open": "research_bundle.html",
        },
    ]


def adoption_path_rows(language: str = "en") -> list[JsonDict]:
    """Return the short path from adjacent-tool output to reviewer evidence."""

    if language == "zh":
        return [
            {
                "minute": "1",
                "action": '运行 `pcl choose --need "<你的目标>" --language zh`。',
                "result": "得到直白建议和下一条 PCL 命令。",
            },
            {
                "minute": "2",
                "action": "导入 Promptfoo / Langfuse / LangSmith / DeepEval 输出。",
                "result": "`manifest.json` 和 `bridge_summary.html`。",
            },
            {
                "minute": "3",
                "action": "运行 `pcl evidence-audit ...` 或中文 research-demo / diagnose。",
                "result": "`evidence_card.html`、`claim_check.html`、`research_bundle.zh.html`。",
            },
            {
                "minute": "4",
                "action": "打开命令输出里提示的第一个 HTML artifact。",
                "result": "看到发生了什么、还缺什么。",
            },
            {
                "minute": "5",
                "action": "如果 claim_check 或 gap_status 要求复查, 暂停强主张。",
                "result": "得到有边界的下一步。",
            },
        ]
    return [
        {
            "minute": "1",
            "action": 'Run `pcl choose --need "<your goal>"`.',
            "result": "A plain recommendation and the next PCL command.",
        },
        {
            "minute": "2",
            "action": "Import Promptfoo/Langfuse/LangSmith/DeepEval output.",
            "result": "`manifest.json` and `bridge_summary.html`.",
        },
        {
            "minute": "3",
            "action": "Run `pcl evidence-audit ...` or research-demo / diagnose.",
            "result": "`evidence_card.html`, `claim_check.html`, and `research_bundle.html`.",
        },
        {
            "minute": "4",
            "action": "Open the first HTML artifact named by the command output.",
            "result": "A reviewer-readable view of what changed and what is missing.",
        },
        {
            "minute": "5",
            "action": "If claim_check or gap_status says review, pause stronger claims.",
            "result": "A bounded next action instead of an overclaim.",
        },
    ]


def format_tool_choice(payload: JsonDict, *, language: str = "en") -> str:
    """Format a tool-choice payload for humans."""

    choices = payload.get("choices")
    if isinstance(choices, list):
        if language == "zh":
            lines = ["工具选择地图", "", "按你的目标选择第一步:"]
            for lane in choices:
                lines.append(
                    f"- {_lane_display(lane, language='zh')}: "
                    f"先用 {_use_first_display(lane, language='zh')}"
                )
                lines.append(f"  适合: {lane.get('when_zh') or lane.get('when', '')}")
                lines.append(f"  PCL 补: {lane.get('pcl_short_zh') or lane.get('pcl_short', '')}")
            lines.extend(["", "5 分钟采用路径:"])
            lines.extend(_adoption_path_text_lines(language="zh"))
            lines.extend(["", "下一步: pcl choose --need <你的目标>"])
            return "\n".join(lines)
        lines = ["Tool choice map", "", "Pick the first tool by your goal:"]
        for lane in choices:
            lines.append(f"- {lane.get('id')}: start with {lane.get('use_first')}")
            lines.append(f"  When: {lane.get('when', '')}")
            lines.append(f"  PCL adds: {lane.get('pcl_short', '')}")
        lines.extend(["", "Five-minute adoption path:"])
        lines.extend(_adoption_path_text_lines(language="en"))
        lines.extend(["", "Next: pcl choose --need <your-goal>"])
        return "\n".join(lines)

    commands = payload.get("commands")
    command_list = [str(command) for command in commands] if isinstance(commands, list) else []
    if language == "zh":
        lines = [
            "工具选择建议",
            f"需求: {payload.get('need', '')}",
            f"匹配路线: {_payload_lane_display(payload, language='zh')}",
            f"置信度: {payload.get('confidence', 'unknown')}",
            f"先用: {payload.get('use_first_zh') or payload.get('use_first', '')}",
            "",
            f"为什么: {payload.get('why_zh') or payload.get('why', '')}",
            f"PCL 补什么: {payload.get('pcl_adds_zh') or payload.get('pcl_adds', '')}",
            "",
            "可复制命令:",
        ]
        lines.extend(f"- {command}" for command in command_list)
        action = _selected_market_gap_action(payload, language="zh")
        if action:
            lines.extend(
                [
                    "",
                    f"证据缺口: {action.get('gap', '')}",
                    f"下一步运行: {action.get('command', '')}",
                    f"先打开: {action.get('open', '')}",
                ]
            )
        lines.extend(["", "5 分钟采用路径:"])
        lines.extend(_adoption_path_text_lines(language="zh"))
        lines.extend(["", f"不要做: {payload.get('avoid_zh') or payload.get('avoid', '')}"])
        return "\n".join(lines)
    lines = [
        "Tool choice recommendation",
        f"Need: {payload.get('need', '')}",
        f"Matched lane: {payload.get('matched', '')} ({payload.get('confidence', 'unknown')})",
        f"Use first: {payload.get('use_first', '')}",
        "",
        f"Why: {payload.get('why', '')}",
        f"What PCL adds: {payload.get('pcl_adds', '')}",
        "",
        "Copy-paste commands:",
    ]
    lines.extend(f"- {command}" for command in command_list)
    action = _selected_market_gap_action(payload, language="en")
    if action:
        lines.extend(
            [
                "",
                f"Evidence gap: {action.get('gap', '')}",
                f"Run next: {action.get('command', '')}",
                f"Open first: {action.get('open', '')}",
            ]
        )
    lines.extend(["", "Five-minute adoption path:"])
    lines.extend(_adoption_path_text_lines(language="en"))
    lines.extend(["", f"Avoid: {payload.get('avoid', '')}"])
    return "\n".join(lines)


def render_tool_choice_markdown(payload: JsonDict, *, language: str = "en") -> str:
    """Render a tool-choice payload as reviewer-friendly Markdown."""

    choices = payload.get("choices")
    if isinstance(choices, list):
        if language == "zh":
            lines = [
                "# 工具选择地图",
                "",
                "| 场景 | 先用 | PCL 补什么 |",
                "|---|---|---|",
            ]
            for lane in choices:
                lines.append(
                    "| "
                    f"{_md_cell(lane.get('when_zh') or lane.get('when'))} | "
                    f"{_md_cell(_use_first_display(lane, language='zh'))} | "
                    f"{_md_cell(lane.get('pcl_short_zh') or lane.get('pcl_short'))} |"
                )
            lines.extend(["", "## 5 分钟采用路径", ""])
            lines.extend(_adoption_path_markdown_table(language="zh"))
            lines.extend(["", "## 从市场缺口到 PCL 命令", ""])
            lines.extend(_market_gap_markdown_table(language="zh"))
            lines.extend(["", "下一步: `pcl choose --need <你的目标>`"])
            return "\n".join(lines) + "\n"
        lines = [
            "# Tool Choice Map",
            "",
            "| Scenario | Use first | What PCL adds |",
            "|---|---|---|",
        ]
        for lane in choices:
            lines.append(
                "| "
                f"{_md_cell(lane.get('when'))} | "
                f"{_md_cell(lane.get('use_first'))} | "
                f"{_md_cell(lane.get('pcl_short'))} |"
            )
        lines.extend(["", "## Five-Minute Adoption Path", ""])
        lines.extend(_adoption_path_markdown_table(language="en"))
        lines.extend(["", "## From Market Gap to PCL Command", ""])
        lines.extend(_market_gap_markdown_table(language="en"))
        lines.extend(["", "Next: `pcl choose --need <your-goal>`"])
        return "\n".join(lines) + "\n"

    command_list = _command_list(payload.get("commands"))
    if language == "zh":
        lines = [
            "# 工具选择建议",
            "",
            f"- 需求: `{payload.get('need', '')}`",
            f"- 匹配路线: `{_payload_lane_display(payload, language='zh')}`",
            f"- 置信度: `{payload.get('confidence', 'unknown')}`",
            f"- 先用: **{payload.get('use_first_zh') or payload.get('use_first', '')}**",
            "",
            "## 为什么",
            "",
            str(payload.get("why_zh") or payload.get("why", "")),
            "",
            "## PCL 补什么",
            "",
            str(payload.get("pcl_adds_zh") or payload.get("pcl_adds", "")),
            "",
            "## 可复制命令",
            "",
        ]
        lines.extend(f"```bash\n{command}\n```" for command in command_list)
        action = _selected_market_gap_action(payload, language="zh")
        if action:
            lines.extend(
                [
                    "",
                    "## 下一步证据缺口",
                    "",
                    f"- 缺口: {action.get('gap', '')}",
                    f"- 运行: `{action.get('command', '')}`",
                    f"- 先打开: `{action.get('open', '')}`",
                ]
            )
        lines.extend(["", "## 5 分钟采用路径", ""])
        lines.extend(_adoption_path_markdown_table(language="zh"))
        lines.extend(
            ["", "## 不要做", "", str(payload.get("avoid_zh") or payload.get("avoid", ""))]
        )
        return "\n".join(lines) + "\n"

    lines = [
        "# Tool Choice Recommendation",
        "",
        f"- Need: `{payload.get('need', '')}`",
        f"- Matched lane: `{payload.get('matched', '')}`",
        f"- Confidence: `{payload.get('confidence', 'unknown')}`",
        f"- Use first: **{payload.get('use_first', '')}**",
        "",
        "## Why",
        "",
        str(payload.get("why", "")),
        "",
        "## What PCL Adds",
        "",
        str(payload.get("pcl_adds", "")),
        "",
        "## Copy-Paste Commands",
        "",
    ]
    lines.extend(f"```bash\n{command}\n```" for command in command_list)
    action = _selected_market_gap_action(payload, language="en")
    if action:
        lines.extend(
            [
                "",
                "## Next Evidence Gap",
                "",
                f"- Gap: {action.get('gap', '')}",
                f"- Run: `{action.get('command', '')}`",
                f"- Open first: `{action.get('open', '')}`",
            ]
        )
    lines.extend(["", "## Five-Minute Adoption Path", ""])
    lines.extend(_adoption_path_markdown_table(language="en"))
    lines.extend(["", "## Avoid", "", str(payload.get("avoid", ""))])
    return "\n".join(lines) + "\n"


def _adoption_path_text_lines(*, language: str) -> list[str]:
    if language == "zh":
        return [
            f"- {row.get('minute')}. {row.get('action')} -> {row.get('result')}"
            for row in adoption_path_rows(language="zh")
        ]
    return [
        f"- {row.get('minute')}. {row.get('action')} -> {row.get('result')}"
        for row in adoption_path_rows(language="en")
    ]


def _adoption_path_markdown_table(*, language: str) -> list[str]:
    if language == "zh":
        lines = [
            "| 分钟 | 操作 | 应该得到什么 |",
            "|---:|---|---|",
        ]
    else:
        lines = [
            "| Minute | Do this | You should get |",
            "|---:|---|---|",
        ]
    for row in adoption_path_rows(language=language):
        lines.append(
            "| "
            f"{_md_cell(row.get('minute'))} | "
            f"{_md_cell(row.get('action'))} | "
            f"{_md_cell(row.get('result'))} |"
        )
    return lines


def _command_list(value: object) -> list[str]:
    return [str(command) for command in value] if isinstance(value, list) else []


def _selected_market_gap_action(payload: JsonDict, *, language: str) -> JsonDict:
    key = "market_gap_action_zh" if language == "zh" else "market_gap_action"
    value = payload.get(key)
    return dict(value) if isinstance(value, dict) else {}


def _lane_display(lane: JsonDict, *, language: str) -> str:
    lane_id = str(lane.get("id", "") or "")
    label = (
        str(lane.get("label_zh") or lane.get("label") or lane_id)
        if language == "zh"
        else str(lane.get("label") or lane_id)
    )
    return f"{label} ({lane_id})" if lane_id and label != lane_id else label


def _payload_lane_display(payload: JsonDict, *, language: str) -> str:
    lane_id = str(payload.get("matched", "") or "")
    label = (
        str(payload.get("matched_label_zh") or payload.get("matched_label") or lane_id)
        if language == "zh"
        else str(payload.get("matched_label") or lane_id)
    )
    return f"{label} ({lane_id})" if lane_id and label != lane_id else label


def _use_first_display(lane: JsonDict, *, language: str) -> str:
    if language == "zh":
        return str(lane.get("use_first_zh") or lane.get("use_first") or "")
    return str(lane.get("use_first") or "")


def _md_cell(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def _market_gap_markdown_table(*, language: str) -> list[str]:
    if language == "zh":
        lines = [
            "| 你已经从其他工具得到什么 | 还缺什么证据 | 下一步运行 | 先打开 |",
            "|---|---|---|---|",
        ]
    else:
        lines = [
            (
                "| What another tool leaves you with | Gap before a strong claim | "
                "Run next | Open first |"
            ),
            "|---|---|---|---|",
        ]
    for row in market_gap_action_rows(language=language):
        lines.append(
            "| "
            f"{_md_cell(row.get('input'))} | "
            f"{_md_cell(row.get('gap'))} | "
            f"`{_md_cell(row.get('command'))}` | "
            f"`{_md_cell(row.get('open'))}` |"
        )
    return lines
