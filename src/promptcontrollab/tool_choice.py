"""Adjacent-tool choice guidance for prompt_control_lab."""

from __future__ import annotations

from promptcontrollab.files import JsonDict


def tool_choice_lanes() -> list[JsonDict]:
    """Return PCL's recommended adjacent-tool lanes."""

    return [
        {
            "id": "security",
            "use_first": "Promptfoo",
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
            "pcl_adds": (
                "Use PCL after Promptfoo when you need paired uncertainty, prompt-only validity, "
                "claim boundaries, and paper-diagnostic evidence."
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
        },
        {
            "id": "unit-tests",
            "use_first": "DeepEval",
            "keywords": ["unit test", "pytest", "deepeval", "metric", "assert", "component test"],
            "why": "DeepEval is strongest for Pytest-style LLM tests and ready-made metrics.",
            "pcl_adds": (
                "Use PCL around DeepEval results when you need prompt/model/split provenance, "
                "paired uncertainty, and claim checks."
            ),
            "commands": [
                "pcl import deepeval --input deepeval-results.json --out runs/from-deepeval",
                "pcl evidence-card --run runs/from-deepeval",
            ],
            "avoid": "Do not ask PCL to become a broad LLM-as-judge metric catalog.",
        },
        {
            "id": "observability",
            "use_first": "LangSmith or Langfuse",
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
            ],
            "why": (
                "LangSmith and Langfuse are stronger for traces, monitoring, "
                "prompt registries, and production observability."
            ),
            "pcl_adds": (
                "Use PCL when those exports need to become reproducible prompt-optimization "
                "evidence with model provenance and research diagnostics."
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
        },
        {
            "id": "prompt-writing",
            "use_first": "linshenkx/prompt-optimizer",
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
            ],
            "why": (
                "prompt-optimizer is stronger as a polished prompt writing, "
                "prompt asset, and interactive testing product."
            ),
            "pcl_adds": (
                "Use PCL after prompt-optimizer when an optimized prompt needs clean evaluation "
                "evidence before deployment or publication."
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
        },
        {
            "id": "research-evidence",
            "use_first": "prompt_control_lab",
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
            ],
            "why": (
                "PCL is strongest when the question is what a prompt optimization "
                "result can safely claim."
            ),
            "pcl_adds": (
                "Start directly with PCL for tri-split evaluation, paired statistics, "
                "soft-hard gap, trajectory, Riccati, and time-varying soft-control diagnostics."
            ),
            "commands": [
                "pcl research-demo --out runs/research-demo",
                "pcl diagnose --run runs/research-demo",
            ],
            "avoid": (
                "Do not start with PCL if the only need is a nicer prompt editor "
                "or tracing dashboard."
            ),
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
        "pcl_adds": best_lane["pcl_adds"],
        "commands": best_lane["commands"],
        "avoid": best_lane["avoid"],
    }


def format_tool_choice(payload: JsonDict, *, language: str = "en") -> str:
    """Format a tool-choice payload for humans."""

    choices = payload.get("choices")
    if isinstance(choices, list):
        if language == "zh":
            lines = ["工具选择地图", "", "按你的目标选择第一步:"]
            for lane in choices:
                lines.append(f"- {lane.get('id')}: 先用 {lane.get('use_first')}")
            lines.extend(["", "下一步: pcl choose --need <你的目标>"])
            return "\n".join(lines)
        lines = ["Tool choice map", "", "Pick the first tool by your goal:"]
        for lane in choices:
            lines.append(f"- {lane.get('id')}: start with {lane.get('use_first')}")
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
            f"为什么: {payload.get('why', '')}",
            f"PCL 补什么: {payload.get('pcl_adds', '')}",
            "",
            "可复制命令:",
        ]
        lines.extend(f"- {command}" for command in command_list)
        lines.extend(["", f"不要做: {payload.get('avoid', '')}"])
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
