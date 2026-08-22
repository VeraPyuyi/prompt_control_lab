from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
README_EN = ROOT / "README.md"
README_ZH = ROOT / "README.zh.md"

DOC_PAIRS = (
    ("control_loop.en.md", "control_loop.zh.md"),
    ("deepseek_harness.en.md", "deepseek_harness.zh.md"),
    ("providers.en.md", "providers.zh.md"),
    ("control_benchmark.en.md", "control_benchmark.zh.md"),
    ("control_ui.en.md", "control_ui.zh.md"),
)

CENTRAL_DOCS = (
    README_EN,
    README_ZH,
    *(ROOT / "docs" / name for pair in DOC_PAIRS for name in pair),
    ROOT / "docs" / "github_discussion_deepseek_harness.md",
    ROOT / "docs" / "artifacts.en.md",
    ROOT / "docs" / "artifacts.zh.md",
    ROOT / "docs" / "background.en.md",
    ROOT / "docs" / "background.zh.md",
    ROOT / "docs" / "users.en.md",
    ROOT / "docs" / "users.zh.md",
    ROOT / "docs" / "innovation.en.md",
    ROOT / "docs" / "innovation.zh.md",
    ROOT / "docs" / "tutorial.en.md",
    ROOT / "docs" / "tutorial.zh.md",
)

HARNESS_COMMIT = "b150a551b8d465e31e418e1b2eaf5e79bbb7d28e"
HARNESS_METHODS = (
    "harness_session_start",
    "harness_pre_step",
    "harness_tool_pre_execute",
    "harness_event",
    "harness_turn_end",
    "harness_status",
    "harness_finalize",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _first_screen(text: str) -> str:
    marker = "\n## Documentation"
    assert marker in text
    return text.split(marker, 1)[0]


def test_readme_first_screens_lead_with_the_local_control_loop() -> None:
    english = _read(README_EN)
    chinese = _read(README_ZH)
    first_en = _first_screen(english)
    first_zh = _first_screen(chinese)

    assert english.startswith(
        "# PromptControlLab 2.0\n\n**The local control loop for prompts and AI agents.**"
    )
    assert chinese.startswith(
        "# PromptControlLab 2.0\n\n**Prompt 与 AI Agent 的本地控制闭环。**"
    )
    for first in (first_en, first_zh):
        assert "2-Minute" in first or "2 分钟" in first
        assert "pcl control" in first
        assert "--authorization inspect" in first
        assert "DeepSeek Harness" in first
        assert "OpenAI" in first
        assert "Anthropic" in first
        assert "Gemini" in first
        assert "DeepSeek" in first
        assert "Qwen" in first
        assert "Kimi" in first
        assert "Codex" in first
        assert "Cursor" in first
        assert "Claude Code" in first
        assert "GitHub Action" in first
        assert "prompt_control_lab.control_event.v1" in first
        assert "Before / Run / Why / After / Decision / History / Advanced" in first
        assert "PEOC" not in first

    assert "Control-theoretic diagnostics and reproducible evidence" not in english
    assert "面向 prompt 优化的控制论诊断与可复现证据工具" not in chinese
    assert "Real evidence first" not in english
    assert len(english.splitlines()) <= 70
    assert len(chinese.splitlines()) <= 70


def test_readmes_link_every_bilingual_control_guide() -> None:
    english = _read(README_EN)
    chinese = _read(README_ZH)

    for en_name, zh_name in DOC_PAIRS:
        assert f"docs/{en_name}" in english
        assert f"docs/{zh_name}" in chinese
        assert f"]({zh_name})" in _read(ROOT / "docs" / en_name)
        assert f"]({en_name})" in _read(ROOT / "docs" / zh_name)

    for text in (english, chinese):
        advanced = text.find("Advanced Diagnostics")
        if advanced < 0:
            advanced = text.find("高级诊断")
        assert advanced >= 0
        assert text.find("PEOC") > advanced


def test_control_loop_docs_define_authorization_and_artifact_authority() -> None:
    for path in (
        ROOT / "docs" / "control_loop.en.md",
        ROOT / "docs" / "control_loop.zh.md",
    ):
        text = _read(path)
        for level in ("inspect", "model", "agent-scoped", "agent-full"):
            assert f"`{level}`" in text
        for artifact in (
            "control_run.json",
            "events.jsonl",
            "preflight.json",
            "provider_result.json",
            "attribution.json",
            "stability.json",
            "decision.json",
            "report.md",
            "report.html",
            ".prompt_control_lab/runs.sqlite3",
        ):
            assert f"`{artifact}`" in text
        for schema in (
            "prompt_control_lab.control_run.v1",
            "prompt_control_lab.control_event.v1",
            "prompt_control_lab.preflight_decision.v1",
            "prompt_control_lab.attribution_report.v1",
            "prompt_control_lab.stability_report.v1",
            "prompt_control_lab.control_decision.v1",
        ):
            assert f"`{schema}`" in text
        assert "pcl control" in text
        assert "JSON" in text and "SQLite" in text
        assert "source of truth" in text or "事实源" in text
        assert "rebuild" in text.lower() or "重建" in text
        assert "does not launch an agent" in text or "不会启动 Agent" in text


def test_deepseek_harness_docs_match_the_pinned_native_contract() -> None:
    commands = (
        "pcl install-plugin deepseek-harness --target ./plugins/prompt-control-lab",
        "pcl harness init --project .",
        "pcl harness doctor --project . --json",
        "pcl harness replay --session <session.jsonl> --out runs/harness-replay --json",
        "pcl harness report --runs .promptcontrol/runs --session <session-or-run-id> --json",
    )
    official_links = (
        f"https://github.com/deepseek-ai/deepseek-harness/tree/{HARNESS_COMMIT}",
        "https://github.com/deepseek-ai/deepseek-harness/blob/"
        f"{HARNESS_COMMIT}/docs/user/develop/framework/events.md",
        "https://github.com/deepseek-ai/deepseek-harness/blob/"
        f"{HARNESS_COMMIT}/docs/architecture.md",
    )

    for path in (
        ROOT / "docs" / "deepseek_harness.en.md",
        ROOT / "docs" / "deepseek_harness.zh.md",
    ):
        text = _read(path)
        assert "native Cordis" in text or "原生 Cordis" in text
        assert "0.1.1-rc.2" in text
        assert HARNESS_COMMIT in text
        for command in commands:
            assert command in text
        for method in HARNESS_METHODS:
            assert f"`{method}`" in text
        for event in (
            "agent/session-start",
            "agent/pre-step",
            "agent/request",
            "agent/request-error",
            "tools/pre-execute",
            "tools/post-execute",
            "tools/result",
            "session/event",
            "turn/end",
            "agent/turn-stopping",
            "agent/disposed",
        ):
            assert f"`{event}`" in text
        for link in official_links:
            assert link in text
        assert "suggest" in text and "gate" in text
        assert "fail open" in text.lower() or "失败时继续" in text
        assert "fail closed" in text.lower() or "失败时关闭" in text
        assert "600" in text and "256" in text
        assert "repeat-tool-reminder" in text
        assert "timeout" in text.lower()
        assert "raw prompt" in text.lower() or "原始 prompt" in text
        assert "hidden reasoning" in text.lower() or "隐藏推理" in text
        assert "API keys" in text or "API key" in text


def test_provider_docs_list_adapters_commands_and_honest_provenance() -> None:
    providers = (
        "openai",
        "anthropic",
        "gemini",
        "deepseek",
        "qwen",
        "kimi",
        "openai-compatible",
    )
    environment_variables = (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "DEEPSEEK_API_KEY",
        "DASHSCOPE_API_KEY",
        "MOONSHOT_API_KEY",
        "OPENAI_COMPATIBLE_API_KEY",
    )
    for path in (
        ROOT / "docs" / "providers.en.md",
        ROOT / "docs" / "providers.zh.md",
    ):
        text = _read(path)
        assert "pcl providers list --json" in text
        assert "pcl providers inspect" in text
        assert "pcl providers doctor" in text
        assert "--live" in text
        for provider in providers:
            assert f"`{provider}`" in text
        for variable in environment_variables:
            assert f"`{variable}`" in text
        assert "public model" in text.lower() or "公开模型" in text
        assert "hidden weights" in text.lower() or "隐藏权重" in text
        assert "does not prove" in text.lower() or "不能证明" in text
        assert "no default model" in text.lower() or "不选择默认模型" in text


def test_benchmark_docs_explain_exactly_what_accuracy_means() -> None:
    for path in (
        ROOT / "docs" / "control_benchmark.en.md",
        ROOT / "docs" / "control_benchmark.zh.md",
    ):
        text = _read(path)
        assert (
            "python -m promptcontrollab.control_benchmark "
            "examples/control-benchmark/manifest.json"
        ) in text
        assert "prompt_control_lab.control_benchmark_manifest.v1" in text
        assert "prompt_control_lab.control_benchmark_result.v1" in text
        assert "does not write" in text or "不会写出" in text
        for label in (
            "converging",
            "stalled",
            "oscillating",
            "diverging",
            "insufficient_evidence",
        ):
            assert f"`{label}`" in text
        assert "accuracy" in text
        assert "synthetic" in text.lower() or "合成" in text
        assert "causal" in text.lower() or "因果" in text
        assert "safety" in text.lower() or "安全" in text
        assert "performance" in text.lower() or "性能" in text


def test_ui_docs_keep_the_control_story_and_advanced_boundary() -> None:
    expected = "Before -> Run -> Why -> After -> Decision -> History -> Advanced"
    expected_zh = "执行前 -> 运行中 -> 原因 -> 执行后 -> 决策 -> 历史 -> 高级"
    english = _read(ROOT / "docs" / "control_ui.en.md")
    chinese = _read(ROOT / "docs" / "control_ui.zh.md")

    assert expected in english
    assert expected_zh in chinese
    for text in (english, chinese):
        assert "pcl ui --runs runs" in text
        assert "PEOC" in text
        assert text.find("PEOC") > text.find("Advanced")
        assert "causal" in text.lower() or "因果" in text
        assert "safety proof" in text.lower() or "安全证明" in text


def test_legacy_entry_docs_no_longer_lead_with_peoc_research() -> None:
    expected_openings = {
        "background.en.md": "local control loop",
        "background.zh.md": "本地控制闭环",
        "users.en.md": "Prompt and Agent Operators",
        "users.zh.md": "Prompt 与 Agent 操作者",
        "innovation.en.md": "authorization",
        "innovation.zh.md": "授权",
        "tutorial.en.md": "## 2-Minute Control Loop",
        "tutorial.zh.md": "## 2 分钟控制闭环",
        "artifacts.en.md": "control_run.json",
        "artifacts.zh.md": "control_run.json",
    }
    for name, phrase in expected_openings.items():
        opening = "\n".join(_read(ROOT / "docs" / name).splitlines()[:20])
        assert phrase in opening
        assert "PEOC" not in opening


def test_discussion_draft_requests_feedback_without_promising_inclusion() -> None:
    text = _read(ROOT / "docs" / "github_discussion_deepseek_harness.md")

    assert text.startswith("# GitHub Discussion Draft")
    assert "Title:" in text
    assert "maintainer feedback" in text.lower()
    assert "0.1.1-rc.2" in text
    assert HARNESS_COMMIT in text
    assert "native Cordis plugin" in text
    assert "does not imply official inclusion" in text.lower()
    assert "no promise" in text.lower()
    assert "official integration" not in text.lower()


@pytest.mark.parametrize("path", CENTRAL_DOCS, ids=lambda path: path.name)
def test_control_positioning_has_no_commercial_plan_or_performance_claims(path: Path) -> None:
    text = _read(path)
    forbidden = (
        r"\bpricing\b",
        r"\bsales\b",
        r"\bSaaS\b",
        r"\benterprise roadmap\b",
        r"\bcommercial roadmap\b",
        r"\bstate[- ]of[- ]the[- ]art\b",
        r"\bbest[- ]in[- ]class\b",
        r"\boutperforms?\b",
    )
    for pattern in forbidden:
        assert re.search(pattern, text, flags=re.IGNORECASE) is None, pattern


@pytest.mark.parametrize("path", CENTRAL_DOCS, ids=lambda path: path.name)
def test_control_docs_have_balanced_code_fences(path: Path) -> None:
    fences = [line for line in _read(path).splitlines() if line.strip().startswith("```")]
    assert len(fences) % 2 == 0
