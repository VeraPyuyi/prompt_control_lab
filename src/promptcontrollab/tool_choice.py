"""Adjacent-tool choice guidance for prompt_control_lab."""

from __future__ import annotations

from promptcontrollab.files import JsonDict


def tool_choice_lanes() -> list[JsonDict]:
    """Return PCL's recommended adjacent-tool lanes."""

    return [
        {
            "id": "security",
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
            "use_first": "LangSmith or Langfuse",
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
    return {
        "need": need,
        "matched": best_lane["id"],
        "confidence": "high" if best_score >= 2 else "medium" if best_score == 1 else "low",
        "use_first": best_lane["use_first"],
        "why": best_lane["why"],
        "why_zh": best_lane.get("why_zh", best_lane["why"]),
        "pcl_adds": best_lane["pcl_adds"],
        "pcl_adds_zh": best_lane.get("pcl_adds_zh", best_lane["pcl_adds"]),
        "commands": best_lane["commands"],
        "avoid": best_lane["avoid"],
        "avoid_zh": best_lane.get("avoid_zh", best_lane["avoid"]),
    }


def format_tool_choice(payload: JsonDict, *, language: str = "en") -> str:
    """Format a tool-choice payload for humans."""

    choices = payload.get("choices")
    if isinstance(choices, list):
        if language == "zh":
            lines = ["工具选择地图", "", "按你的目标选择第一步:"]
            for lane in choices:
                lines.append(f"- {lane.get('id')}: 先用 {lane.get('use_first')}")
                lines.append(f"  适合: {lane.get('when_zh') or lane.get('when', '')}")
                lines.append(f"  PCL 补: {lane.get('pcl_short_zh') or lane.get('pcl_short', '')}")
            lines.extend(["", "下一步: pcl choose --need <你的目标>"])
            return "\n".join(lines)
        lines = ["Tool choice map", "", "Pick the first tool by your goal:"]
        for lane in choices:
            lines.append(f"- {lane.get('id')}: start with {lane.get('use_first')}")
            lines.append(f"  When: {lane.get('when', '')}")
            lines.append(f"  PCL adds: {lane.get('pcl_short', '')}")
        lines.extend(["", "Next: pcl choose --need <your-goal>"])
        return "\n".join(lines)

    commands = payload.get("commands")
    command_list = [str(command) for command in commands] if isinstance(commands, list) else []
    if language == "zh":
        lines = [
            "工具选择建议",
            f"需求: {payload.get('need', '')}",
            f"匹配路线: {payload.get('matched', '')} ({payload.get('confidence', 'unknown')})",
            f"先用: {payload.get('use_first', '')}",
            "",
            f"为什么: {payload.get('why_zh') or payload.get('why', '')}",
            f"PCL 补什么: {payload.get('pcl_adds_zh') or payload.get('pcl_adds', '')}",
            "",
            "可复制命令:",
        ]
        lines.extend(f"- {command}" for command in command_list)
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
    lines.extend(["", f"Avoid: {payload.get('avoid', '')}"])
    return "\n".join(lines)
