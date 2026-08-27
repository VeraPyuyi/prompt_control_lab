"""Preflight command handlers and terminal formatters."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from promptcontrollab.cli.common import (
    _config_path,
    _first_stats_comparison,
    _format_optional_number,
    _open_html_report,
    _read_json_if_exists,
)
from promptcontrollab.cli.handlers.diagnostics import _format_research_demo_output
from promptcontrollab.cli.handlers.evaluation import _cmd_analyze
from promptcontrollab.cli.handlers.integrations import (
    _format_start_ecosystem_result,
    _run_start_ecosystem,
)
from promptcontrollab.core.config import (
    load_project_config,
)
from promptcontrollab.core.errors import PromptControlLabError
from promptcontrollab.core.files import JsonDict, ensure_dir, write_json
from promptcontrollab.diagnostics.research_workflow import (
    write_research_demo,
)
from promptcontrollab.evaluation.history import index_history
from promptcontrollab.evaluation.workflow import (
    run_quick_analysis,
)
from promptcontrollab.evidence.ingest import (
    ingest_auto_results,
    ingest_deepeval_results,
    ingest_langfuse_results,
    ingest_langsmith_results,
    ingest_prompt_optimizer_assets,
    ingest_promptfoo_results,
)
from promptcontrollab.integrations.templates import write_example_project
from promptcontrollab.preflight.prompt_context import load_prompt_context
from promptcontrollab.preflight.prompt_diff import render_prompt_diff
from promptcontrollab.preflight.prompt_guard import guard_prompt
from promptcontrollab.preflight.prompt_improver import improve_prompt
from promptcontrollab.preflight.scaffold_check import write_scaffold_check
from promptcontrollab.preflight.tool_choice import (
    adoption_path_rows,
    choose_tool_for_need,
    format_tool_choice,
    market_gap_action_rows,
    render_tool_choice_markdown,
    tool_choice_lanes,
)


def _cmd_init(args: argparse.Namespace) -> None:
    """Execute the init command handler."""
    write_example_project(args.path)
    print(_format_init_output(args.path))


def _format_init_output(
    path: Path,
    *,
    language: str = "en",
    quick_run: Path | None = None,
    history_index: Path | None = None,
) -> str:
    """Return concise next steps after creating an example project."""

    if language == "zh":
        lines = [
            f"已创建 PromptControlLab 示例项目: {path}",
        ]
        if quick_run is not None:
            lines.extend(
                [
                    f"已生成 quick report: {quick_run / 'report.html'}",
                    f"已生成 gate result: {quick_run / 'gate_result.json'}",
                    *_format_quick_run_summary(quick_run, language=language),
                ]
            )
        if history_index is not None:
            lines.append(f"已生成 history index: {history_index}")
        lines.extend(
            [
                "",
                "下一步:",
                f"  cd {path}",
                *(
                    [
                        "  打开 runs/quick/report.html 查看报告",
                        "  pcl ui --runs runs --policy examples/guard.policy.yaml",
                    ]
                    if quick_run is not None
                    else [
                        "  pcl start --guide --language zh",
                        "  pcl analyze --config promptcontrol.example.yaml --out runs/quick",
                        "  pcl ui --runs runs --policy examples/guard.policy.yaml",
                    ]
                ),
                "",
                "打开该目录里的 README.zh.md, 可以查看中文文件说明和可复制命令。",
            ]
        )
        return "\n".join(lines)

    lines = [
        f"Created PromptControlLab example at {path}",
    ]
    if quick_run is not None:
        lines.extend(
            [
                f"Generated quick report: {quick_run / 'report.html'}",
                f"Generated gate result: {quick_run / 'gate_result.json'}",
                *_format_quick_run_summary(quick_run, language=language),
            ]
        )
    if history_index is not None:
        lines.append(f"Generated history index: {history_index}")
    lines.extend(
        [
            "",
            "Next steps:",
            f"  cd {path}",
            *(
                [
                    "  Open runs/quick/report.html in your browser",
                    "  pcl ui --runs runs --policy examples/guard.policy.yaml",
                ]
                if quick_run is not None
                else [
                    "  pcl start --guide",
                    "  pcl analyze --config promptcontrol.example.yaml --out runs/quick",
                    "  pcl ui --runs runs --policy examples/guard.policy.yaml",
                ]
            ),
            "",
            "Open README.md in that folder for the file map and copy-paste paths. "
            "Chinese guide: README.zh.md.",
        ]
    )
    return "\n".join(lines)


def _format_quick_run_summary(quick_run: Path, *, language: str = "en") -> list[str]:
    """Return a compact terminal summary for a generated quick run."""

    gate = _read_json_if_exists(quick_run / "gate_result.json")
    metrics = _read_json_if_exists(quick_run / "candidate" / "metrics.json")
    stats = _read_json_if_exists(quick_run / "stats.json")
    comparison = _first_stats_comparison(stats)
    gate_status = str(gate.get("status") or "unknown")
    score = _format_optional_number(metrics.get("mean_score"))
    delta = _format_optional_number(comparison.get("mean_delta"), signed=True)
    if language == "zh":
        return [
            "Demo 结果摘要:",
            f"- Gate: {gate_status}",
            f"- Candidate score: {score}",
            f"- Mean delta: {delta}",
        ]
    return [
        "Demo result summary:",
        f"- Gate: {gate_status}",
        f"- Candidate score: {score}",
        f"- Mean delta: {delta}",
    ]


def _cmd_scaffold_check(args: argparse.Namespace) -> None:
    """Execute the scaffold check command handler."""
    scaffold_dir = args.scaffold if args.scaffold is not None else args.run / "eval_scaffold"
    payload = write_scaffold_check(scaffold_dir=scaffold_dir, out_path=args.out)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    if args.strict and payload.get("status") != "pass":
        msg = f"Scaffold check failed in strict mode: status={payload.get('status')}"
        raise PromptControlLabError(msg)


def _cmd_choose(args: argparse.Namespace) -> None:
    """Print adjacent-tool guidance for a user need."""

    language = _resolve_choose_language(args.need, args.language)
    if args.need is None:
        payload = {
            "choices": tool_choice_lanes(),
            "market_gap_actions": market_gap_action_rows(language=language),
            "adoption_path": adoption_path_rows(language=language),
            "next": "Run pcl choose --need <your-goal>.",
        }
    else:
        payload = choose_tool_for_need(args.need)
    written: tuple[Path, Path] | None = None
    if args.out is not None:
        json_path = _choice_output_path(args.out)
        md_path = json_path.with_suffix(".md")
        write_json(json_path, payload)
        md_path.write_text(
            render_tool_choice_markdown(payload, language=language),
            encoding="utf-8",
        )
        written = (json_path, md_path)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return
    print(format_tool_choice(payload, language=language))
    if written is not None:
        print(f"\nWrote tool-choice artifacts: {written[0]} and {written[1]}")


def _resolve_choose_language(need: str | None, language: str) -> str:
    """Resolve ``pcl choose --language auto`` from the user's need text."""

    if language != "auto":
        return language
    if need and any("\u4e00" <= character <= "\u9fff" for character in need):
        return "zh"
    return "en"


def _choice_output_path(path: Path) -> Path:
    """Resolve ``pcl choose --out`` to a JSON artifact path."""

    if path.suffix.lower() == ".json":
        return path
    if path.suffix:
        return path.with_suffix(".json")
    return path / "tool_choice.json"


def _cmd_start(args: argparse.Namespace) -> None:
    """Execute the start command handler."""
    if args.guide:
        print(_format_start_guide(args.language))
        return

    choice = _start_choice(args.choice, language=args.language)
    if choice == "demo":
        out_dir = args.out or Path("demo")
        write_example_project(out_dir)
        quick_run = out_dir / "runs" / "quick"
        run_quick_analysis(
            data_path=out_dir / "examples" / "tasks.jsonl",
            baseline_predictions_path=out_dir / "examples" / "predictions_baseline.jsonl",
            candidate_predictions_path=out_dir / "examples" / "predictions_candidate.jsonl",
            out_dir=quick_run,
            metric="exact_match",
            train_ratio=0.5,
            val_ratio=0.25,
            seed=args.seed,
            bootstrap_samples=50,
            permutation_samples=50,
            explain_level="plain",
            title="PromptControlLab Demo Analysis",
            policy_path=out_dir / "examples" / "gate.policy.yaml",
            prompt_id="demo-prompt",
            prompt_file=out_dir / "prompts" / "current.txt",
            prompt_version="v1",
        )
        history_index = out_dir / "runs" / "history_index.json"
        index_history(runs_dir=out_dir / "runs", out_path=history_index)
        if args.language == "zh":
            print("新手模式: 创建可运行 demo 项目并生成 quick report")
        else:
            print("Beginner mode: create a runnable demo project and quick report")
        print(
            _format_init_output(
                out_dir,
                language=args.language,
                quick_run=quick_run,
                history_index=history_index,
            )
        )
        if args.open_report:
            _open_html_report(quick_run / "report.html", language=args.language)
        return

    if choice == "research":
        out_dir = args.out or Path("runs") / "research-demo"
        payload = write_research_demo(out_dir=out_dir, seed=args.seed)
        if args.language == "zh":
            print("新手模式: 运行论文风格的 prompt optimization 诊断 demo")
        else:
            print("Beginner mode: run the paper-style research diagnostics demo")
        print(
            _format_research_demo_output(
                out_dir=out_dir,
                payload=payload,
                language=args.language,
            )
        )
        return

    if choice == "choose":
        if args.language == "zh":
            print("新手模式: 选择先用哪个相邻工具")
        else:
            print("Beginner mode: choose the right adjacent tool")
        _cmd_choose(
            argparse.Namespace(
                need=args.need,
                language=args.language,
                json=False,
                out=args.out,
            )
        )
        return

    if choice == "ecosystem":
        out_dir = args.out or Path("runs") / "ecosystem-demo"
        payload = _run_start_ecosystem(args, out_dir=out_dir)
        if args.language == "zh":
            print("新手模式: 对比相邻生态工具")
        else:
            print("Beginner mode: compare adjacent ecosystem tools")
        print(
            _format_start_ecosystem_result(
                out_dir=out_dir,
                payload=payload,
                language=args.language,
            )
        )
        return

    if choice == "import":
        if args.input is None:
            print(_format_start_import_guide(args.language))
            return
        out_dir = args.out or _default_start_import_out_dir(args.tool)
        payload = _run_start_import(args, out_dir=out_dir)
        payload.setdefault("source_tool", args.tool)
        print(_format_start_import_result(out_dir=out_dir, payload=payload, language=args.language))
        return

    if choice == "plugins":
        print(_format_start_plugins_guide(args.language))
        return

    if choice == "improve":
        prompt = _read_start_prompt(args.prompt, args.prompt_file)
        print("Beginner mode: improve a prompt")
        context = load_prompt_context(args.run)
        improvement = improve_prompt(
            prompt,
            context=context,
            goal="stability",
            language="auto",
            style="stable",
            token_mode=args.token_mode,
            max_tokens=args.max_tokens,
        )
        print(
            _format_improvement_output(
                improvement.improved_prompt,
                improvement.changes,
                improvement.token_report.to_json(),
            )
        )
        if args.out is not None:
            ensure_dir(args.out)
            (args.out / "improved_prompt.txt").write_text(
                improvement.improved_prompt + "\n",
                encoding="utf-8",
            )
            write_json(args.out / "prompt_improvement.json", improvement.to_json())
            (args.out / "prompt_diff.md").write_text(
                render_prompt_diff(improvement),
                encoding="utf-8",
            )
        return

    if choice == "guard":
        prompt = _read_start_prompt(args.prompt, args.prompt_file)
        print("Beginner mode: guard a prompt")
        result = guard_prompt(
            prompt,
            context=load_prompt_context(args.run),
            mode="suggest",
            profile=args.profile,
            token_mode=args.token_mode,
            max_tokens=args.max_tokens,
            policy_path=args.policy,
        )
        print(_format_guard_output(result.to_json()))
        return

    print("Beginner mode: create a prompt evaluation report")
    if args.config is not None:
        analyze_args = argparse.Namespace(
            config=args.config,
            data=None,
            baseline_predictions=None,
            candidate_predictions=None,
            out=args.out,
            metric=None,
            train_ratio=None,
            val_ratio=None,
            seed=None,
            bootstrap_samples=None,
            permutation_samples=None,
            explain_level=None,
            policy=args.policy,
            title=None,
            baseline_model=None,
            candidate_model=None,
            baseline_provider=None,
            candidate_provider=None,
            api_version=None,
            verify_model=False,
            prompt_id=None,
            prompt_file=None,
            prompt_version=None,
            baseline_prompt_id=None,
            baseline_prompt_file=None,
            baseline_prompt_version=None,
            candidate_prompt_id=None,
            candidate_prompt_file=None,
            candidate_prompt_version=None,
        )
        _cmd_analyze(analyze_args)
        return
    print(
        "\n".join(
            [
                "To create your first report, run:",
                "",
                "  pcl init --path demo",
                "  cd demo",
                "  pcl analyze --config promptcontrol.example.yaml --out runs/quick",
                "",
                "Result: a report.md/report.html that says whether the prompt change "
                "is worth keeping.",
            ]
        )
    )


def _cmd_quickstart(args: argparse.Namespace) -> None:
    """Create the beginner demo through a shorter public command."""

    _cmd_start(
        argparse.Namespace(
            guide=False,
            choice="demo",
            language=args.language,
            out=args.out,
            seed=args.seed,
            open_report=args.open_report,
        )
    )


def _default_start_import_out_dir(tool: str) -> Path:
    name = "external" if tool == "auto" else tool
    return Path("runs") / f"from-{name}"


def _run_start_import(args: argparse.Namespace, *, out_dir: Path) -> JsonDict:
    """Implement the  run start import CLI workflow helper."""
    if args.input is None:
        raise ValueError("--input is required when start import executes an import.")
    source_path: Path = args.input
    if args.tool == "auto":
        return ingest_auto_results(
            source_path=source_path,
            out_dir=out_dir,
            prompt_id=args.prompt_id,
            name=args.name,
            experiment=args.experiment,
            score_name=args.score_name,
            model=args.model,
            provider=args.provider,
            method=args.method,
            asset_id=args.asset_id,
        )
    if args.tool == "promptfoo":
        return ingest_promptfoo_results(
            source_path=source_path,
            out_dir=out_dir,
            prompt_id=args.prompt_id,
            provider=args.provider,
            method=args.method,
        )
    if args.tool == "langfuse":
        return ingest_langfuse_results(
            source_path=source_path,
            out_dir=out_dir,
            name=args.name,
            score_name=args.score_name,
            model=args.model,
            provider=args.provider,
            method=args.method,
        )
    if args.tool == "langsmith":
        return ingest_langsmith_results(
            source_path=source_path,
            out_dir=out_dir,
            experiment=args.experiment,
            score_name=args.score_name,
            model=args.model,
            provider=args.provider,
            method=args.method,
        )
    if args.tool == "deepeval":
        return ingest_deepeval_results(
            source_path=source_path,
            out_dir=out_dir,
            score_name=args.score_name,
            model=args.model,
            provider=args.provider,
            method=args.method,
        )
    return ingest_prompt_optimizer_assets(
        source_path=source_path,
        out_dir=out_dir,
        asset_id=args.asset_id,
    )


def _format_start_import_guide(language: str = "en") -> str:
    if language == "zh":
        return "\n".join(
            [
                "新手模式: 把外部评测结果导入成证据",
                "",
                "如果你已经有 Promptfoo / Langfuse / LangSmith / DeepEval 导出文件, 运行:",
                (
                    "  pcl start --choice import --tool auto --input results.json "
                    "--out runs/from-external"
                ),
                "",
                "如果是 prompt-optimizer 收藏或模板导出, 运行:",
                (
                    "  pcl start --choice import --tool prompt-optimizer "
                    "--input favorites.json --out runs/from-prompt-optimizer"
                ),
                "",
                "得到什么: PCL run artifact、manifest、metrics 或 prompt asset gap plan。",
                (
                    "下一步: 运行 `pcl scaffold-check --run <run>`、"
                    "`pcl evidence-card --run <run>` 或 `pcl evidence-audit`。"
                ),
            ]
        )
    return "\n".join(
        [
            "Beginner mode: import external eval results as evidence",
            "",
            "If you already have Promptfoo / Langfuse / LangSmith / DeepEval exports, run:",
            "  pcl start --choice import --tool auto --input results.json --out runs/from-external",
            "",
            "For prompt-optimizer favorites or template exports, run:",
            (
                "  pcl start --choice import --tool prompt-optimizer "
                "--input favorites.json --out runs/from-prompt-optimizer"
            ),
            "",
            "Result: PCL run artifacts, manifest, metrics, or a prompt asset gap plan.",
            (
                "Next: run `pcl scaffold-check --run <run>`, "
                "`pcl evidence-card --run <run>`, or `pcl evidence-audit`."
            ),
        ]
    )


def _format_start_import_result(
    *,
    out_dir: Path,
    payload: JsonDict,
    language: str = "en",
) -> str:
    source_tool = payload.get("source_tool") or payload.get("tool") or "external"
    status = payload.get("evaluation_status") or payload.get("status") or "imported"
    count = payload.get("count")
    count_text = "unknown" if count is None else str(count)
    if language == "zh":
        return "\n".join(
            [
                "新手模式: 把外部评测结果导入成证据",
                f"- 来源工具: {source_tool}",
                f"- 输出目录: {out_dir}",
                f"- 记录数量: {count_text}",
                f"- 状态: {status}",
                "",
                "下一步:",
                f"  pcl scaffold-check --run {out_dir}",
                f"  pcl evidence-card --run {out_dir} --out {out_dir / 'evidence_card.md'}",
            ]
        )
    return "\n".join(
        [
            "Beginner mode: import external eval results as evidence",
            f"- Source tool: {source_tool}",
            f"- Output directory: {out_dir}",
            f"- Records: {count_text}",
            f"- Status: {status}",
            "",
            "Next steps:",
            f"  pcl scaffold-check --run {out_dir}",
            f"  pcl evidence-card --run {out_dir} --out {out_dir / 'evidence_card.md'}",
        ]
    )


def _cmd_improve(args: argparse.Namespace) -> None:
    """Execute the improve command handler."""
    prompt = _read_improve_prompt(args.prompt, args.prompt_file)
    context = load_prompt_context(args.run)
    improvement = improve_prompt(
        prompt,
        context=context,
        goal=args.goal,
        language=args.language,
        style=args.style,
        token_mode=args.token_mode,
        max_tokens=args.max_tokens,
    )
    print(
        _format_improvement_output(
            improvement.improved_prompt,
            improvement.changes,
            improvement.token_report.to_json(),
        )
    )
    if args.out is not None:
        ensure_dir(args.out)
        (args.out / "improved_prompt.txt").write_text(
            improvement.improved_prompt + "\n",
            encoding="utf-8",
        )
        write_json(args.out / "prompt_improvement.json", improvement.to_json())
        (args.out / "prompt_diff.md").write_text(
            render_prompt_diff(improvement),
            encoding="utf-8",
        )


def _cmd_guard(args: argparse.Namespace) -> None:
    """Execute the guard command handler."""
    prompt = _read_guard_prompt(args.prompt, args.prompt_file, args.stdin)
    context = load_prompt_context(args.run)
    project_config, project_config_path = load_project_config()
    policy_path = args.policy or _config_path(
        project_config,
        project_config_path,
        "guard_policy",
    )
    result = guard_prompt(
        prompt,
        context=context,
        mode=args.mode,
        profile=args.profile,
        token_mode=args.token_mode,
        max_tokens=args.max_tokens,
        language=args.language,
        policy_path=policy_path,
    )
    payload = result.to_json()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return
    print(_format_guard_output(payload))


def _read_improve_prompt(prompt: str | None, prompt_file: Path | None) -> str:
    if prompt is not None and prompt_file is not None:
        msg = "Use either --prompt or --prompt-file, not both"
        raise ValueError(msg)
    if prompt is None and prompt_file is None:
        msg = "Provide --prompt or --prompt-file"
        raise ValueError(msg)
    if prompt_file is not None:
        return prompt_file.read_text(encoding="utf-8")
    if prompt is None:
        msg = "Provide --prompt or --prompt-file"
        raise ValueError(msg)
    return prompt


def _read_guard_prompt(prompt: str | None, prompt_file: Path | None, use_stdin: bool) -> str:
    sources = sum(source is not None for source in [prompt, prompt_file]) + int(use_stdin)
    if sources != 1:
        msg = "Provide exactly one of --prompt, --prompt-file, or --stdin"
        raise ValueError(msg)
    if use_stdin:
        return sys.stdin.read()
    if prompt_file is not None:
        return prompt_file.read_text(encoding="utf-8")
    if prompt is None:
        msg = "Provide exactly one of --prompt, --prompt-file, or --stdin"
        raise ValueError(msg)
    return prompt


def _stdin_is_tty() -> bool:
    isatty = getattr(sys.stdin, "isatty", None)
    if not callable(isatty):
        return False
    try:
        return bool(isatty())
    except OSError:
        return False


def _format_guard_output(payload: JsonDict) -> str:
    lines = [
        "PromptControlLab Guard",
        "",
        f"Decision: {payload['action']}",
        f"Risk: {payload['risk_level']}",
        f"Profile: {payload['profile']}",
        f"Required review: {payload.get('required_review', False)}",
        f"Risk categories: {payload.get('risk_categories', [])}",
        "",
        "Plain summary:",
        str(payload.get("plain_summary", "Review the guarded prompt before sending.")),
        "",
        "Why:",
    ]
    lines.extend(f"- {reason}" for reason in payload["reasons"])
    lines += [
        "",
        "Suggested prompt:",
        "",
        str(payload["improved_prompt"]),
        "",
        "Next steps:",
    ]
    lines.extend(_guard_next_steps(payload))
    violations = payload.get("policy_violations", [])
    if violations:
        lines += ["", "Policy violations:"]
        lines.extend(
            f"- {item.get('id')}: {item.get('message')} ({item.get('severity')})"
            for item in violations
            if isinstance(item, dict)
        )
    token_report = payload["token_report"]
    lines += [
        "",
        "Estimated token cost:",
        f"- Original prompt: {token_report['original_estimated_tokens']}",
        f"- Guarded prompt: {token_report['improved_estimated_tokens']}",
        f"- Token mode: {token_report['token_mode']}",
    ]
    if token_report["max_tokens"] is not None:
        lines.append(f"- Max tokens: {token_report['max_tokens']}")
        lines.append(f"- Within budget: {payload['within_budget']}")
    return "\n".join(lines)


def _guard_next_steps(payload: JsonDict) -> list[str]:
    if payload["action"] == "block":
        return [
            "Revise the prompt before sending it to the agent.",
            "Add scope, target files, failing behavior, and verification steps.",
        ]
    if payload.get("required_review", False):
        return [
            "Have a human review the risky parts before agent execution.",
            "Tighten scope and add a concrete test or verification command.",
        ]
    return [
        "Use the suggested prompt directly, or copy the missing context into your original prompt.",
        "Keep the JSON output for wrappers or IDE integrations when automation is needed.",
    ]


def _format_improvement_output(
    improved_prompt: str,
    changes: list[str],
    token_report: JsonDict,
) -> str:
    lines = ["Optimized prompt:", "", improved_prompt, "", "Why it changed:"]
    lines.extend(f"- {change}" for change in changes)
    lines += [
        "",
        "Estimated token cost:",
        f"- Original prompt: {token_report['original_estimated_tokens']}",
        f"- Optimized prompt: {token_report['improved_estimated_tokens']}",
        f"- Token mode: {token_report['token_mode']}",
    ]
    if token_report["max_tokens"] is not None:
        lines.append(f"- Max tokens: {token_report['max_tokens']}")
        lines.append(f"- Within budget: {token_report['within_budget']}")
    return "\n".join(lines)


def _start_choice(value: str | None, *, language: str = "en") -> str:
    """Implement the  start choice CLI workflow helper."""
    if value is not None:
        return value
    if language == "zh":
        print(
            "\n".join(
                [
                    "你想先做什么?",
                    "1) 创建一个可直接运行的 demo 项目",
                    "2) 运行论文风格的 prompt optimization 研究 demo",
                    "3) 把外部评测结果导入成证据",
                    "4) 让我的 prompt 更清楚",
                    "5) 在发送给 AI 工具前检查 prompt",
                    "6) 比较 prompts 并生成报告",
                    "7) 生成生态对比 demo",
                    "8) 选择应该先用哪个相邻工具",
                    "9) \u5b89\u88c5 Claude Code / Cursor / Codex prompt guard adapter",
                    "",
                    "提示: 如果不确定路径, 运行 `pcl start --guide --language zh`。",
                ]
            )
        )
        raw = input("\u8bf7\u9009\u62e9 1-9: ").strip().lower()
    else:
        print(
            "\n".join(
                [
                    "What do you want to do?",
                    "1) Create a runnable demo project",
                    "2) Run a paper-style prompt optimization research demo",
                    "3) Import external eval results as evidence",
                    "4) Make my prompt clearer",
                    "5) Check a prompt before sending it to an AI tool",
                    "6) Compare prompts and create a report",
                    "7) Generate an ecosystem comparison demo",
                    "8) Choose which adjacent tool to use first",
                    "9) Install Claude Code / Cursor / Codex prompt guard adapters",
                    "",
                    "Tip: run `pcl start --guide` if you are unsure which path fits your goal.",
                ]
            )
        )
        raw = input("Choose 1-9: ").strip().lower()
    choices = {
        "1": "demo",
        "demo": "demo",
        "2": "research",
        "research": "research",
        "3": "import",
        "import": "import",
        "evidence": "import",
        "4": "improve",
        "improve": "improve",
        "5": "guard",
        "guard": "guard",
        "6": "analyze",
        "analyze": "analyze",
        "7": "ecosystem",
        "ecosystem": "ecosystem",
        "ecosystem-demo": "ecosystem",
        "8": "choose",
        "choose": "choose",
        "tool-choice": "choose",
        "9": "plugins",
        "plugins": "plugins",
        "plugin": "plugins",
        "install-plugin": "plugins",
        "adapters": "plugins",
    }
    if raw not in choices:
        msg = "\u8bf7\u9009\u62e9 1-9" if language == "zh" else "Choose 1-9"
        raise ValueError(msg)
    return choices[raw]


def _format_start_plugins_guide(language: str = "en") -> str:
    """Return copy-paste steps for local IDE and coding-agent adapters."""

    if language == "zh":
        return "\n".join(
            [
                "PromptControlLab adapter 接入路径",
                "",
                "1. 先预览将写入哪些 adapter 文件:",
                "   pcl install-plugin all --dry-run",
                "2. 确认后安装本地 adapter 模板:",
                "   pcl install-plugin all",
                "3. 检查本地安装和 hook 是否可运行:",
                "   pcl doctor --json",
                "4. 在 IDE / CI adapter 中调用稳定 JSON 输出:",
                (
                    '   pcl guard --prompt "修复这个 bug" --profile coding '
                    "--policy examples/guard.policy.yaml --json"
                ),
                "",
                (
                    "说明: 这不是沙箱。它是在 Claude Code、Cursor、Codex 或 CI "
                    "把 prompt 交给 agent 前做本地 policy preflight。"
                ),
                "更多路径: docs/choice_guide.zh.md",
            ]
        )
    return "\n".join(
        [
            "PromptControlLab adapter setup",
            "",
            "1. Preview which adapter files would be written:",
            "   pcl install-plugin all --dry-run",
            "2. Install the local adapter templates after review:",
            "   pcl install-plugin all",
            "3. Check that local hooks and adapters can run:",
            "   pcl doctor --json",
            "4. Call the stable guard JSON from your IDE or CI adapter:",
            (
                '   pcl guard --prompt "Fix this bug" --profile coding '
                "--policy examples/guard.policy.yaml --json"
            ),
            "",
            (
                "Note: this is not a sandbox. It is local policy preflight before "
                "Claude Code, Cursor, Codex, or CI forwards a prompt to an agent."
            ),
            "More paths: docs/choice_guide.en.md",
        ]
    )


def _format_start_guide(language: str = "en") -> str:
    """Return a compact beginner guide for choosing the right first command."""

    if language == "zh":
        rows = [
            (
                "先看产品长什么样",
                "pcl quickstart --language zh --out demo --open-report "
                "(同: pcl start --choice demo --language zh --out demo)",
                "生成 demo 并打开 `demo/runs/quick/report.html`。",
            ),
            (
                "打开本地 UI 工作台",
                "pcl ui --runs demo/runs --policy demo/examples/guard.policy.yaml --language zh",
                "查看 Workflows、Report、Model Drift、Audit 和 History。",
            ),
            (
                "运行论文里的 prompt optimization 诊断",
                "pcl research-quickstart --out runs/research-demo --language zh --open-report",
                "打开 research_bundle.zh.html 查看论文证据包。",
            ),
            (
                "不知道应该先用哪个工具",
                'pcl choose --need "安全评测和红队检查" --language zh',
                "Promptfoo / DeepEval / LangSmith / Langfuse / prompt-optimizer / PCL 的选择建议。",
            ),
            (
                "对比相邻工具和 PCL 补充证据",
                "pcl start --choice ecosystem --out runs/ecosystem-demo",
                "打开 `ecosystem_scorecard.html`, 先看 Market readiness。",
            ),
            (
                "把外部评测结果导入成证据",
                "pcl start --choice import --tool auto --input results.json "
                "--out runs/from-external",
                "`manifest.json` 和 `bridge_summary.html`。",
            ),
            (
                "在 coding agent 执行前守护 prompt",
                'pcl guard --prompt "修复这个 bug" '
                "--profile coding --policy examples/guard.policy.yaml",
                "复制改写后的 prompt。",
            ),
            (
                "审计 agent 到底改了什么",
                "pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit",
                "生成审计 artifact, 之后可做 PR summary。",
            ),
            (
                "\u5b89\u88c5 IDE / Agent prompt guard adapter",
                "pcl start --choice plugins --language zh",
                "Claude Code\u3001Cursor\u3001Codex \u548c CI \u63a5\u5165\u6b65\u9aa4\u3002",
            ),
        ]
        lines = ["PromptControlLab 新手路径指南", "", "复制最符合你目标的一条命令:", ""]
        start_label = "起点"
        result_label = "得到"
        final_lines = [
            "更多选择逻辑: docs/choice_guide.zh.md",
            (
                "相邻工具地图: Promptfoo -> eval / CI / red-team; "
                "DeepEval -> Pytest-style LLM tests; prompt-optimizer -> prompt 写作。"
            ),
            "如果想用交互菜单: pcl start --language zh",
        ]
    else:
        rows = [
            (
                "See the product first",
                "pcl quickstart --out demo --open-report "
                "(same as: pcl start --choice demo --out demo)",
                "A demo run and `demo/runs/quick/report.html`.",
            ),
            (
                "Open the local UI reviewer cockpit",
                "pcl ui --runs demo/runs --policy demo/examples/guard.policy.yaml",
                "Workflows, Report, Model Drift, Audit, and History in one browser view.",
            ),
            (
                "Run the paper-derived prompt optimization diagnostics",
                "pcl research-quickstart --out runs/research-demo --open-report",
                "research_bundle.html as the paper evidence bundle.",
            ),
            (
                "Choose the right adjacent tool",
                'pcl choose --need "security evals and red-team checks"',
                (
                    "A direct recommendation for Promptfoo, DeepEval, "
                    "LangSmith/Langfuse, prompt-optimizer, or PCL."
                ),
            ),
            (
                "Compare adjacent tools and PCL-added evidence",
                "pcl start --choice ecosystem --out runs/ecosystem-demo",
                "ecosystem_scorecard.html with Market readiness.",
            ),
            (
                "Import external eval results as evidence",
                "pcl start --choice import --tool auto --input results.json "
                "--out runs/from-external",
                "`manifest.json` and `bridge_summary.html`.",
            ),
            (
                "Guard a coding-agent prompt before it runs",
                'pcl guard --prompt "Fix this bug" '
                "--profile coding --policy examples/guard.policy.yaml",
                "An improved prompt and guard result.",
            ),
            (
                "Audit what an agent changed",
                "pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit",
                "Diff audit artifacts; optionally build a PR summary.",
            ),
            (
                "Install IDE / agent prompt guard adapters",
                "pcl start --choice plugins",
                "Claude Code, Cursor, Codex, and CI adapter setup steps.",
            ),
        ]
        lines = [
            "PromptControlLab beginner guide",
            "",
            "Copy the one command that matches your goal:",
            "",
        ]
        start_label = "Start"
        result_label = "You get"
        final_lines = [
            "More choice logic: docs/choice_guide.en.md",
            (
                "Adjacent-tool map: Promptfoo -> eval / CI / red-team; "
                "DeepEval -> Pytest-style LLM tests; prompt-optimizer -> prompt writing."
            ),
            "Interactive menu: pcl start",
        ]
    for index, (goal, command, next_step) in enumerate(rows, start=1):
        lines.extend(
            [
                f"{index}. {goal}",
                f"   {start_label}: {command}",
                f"   {result_label}: {next_step}",
                "",
            ]
        )
    lines.extend(final_lines)
    return "\n".join(lines)


def _read_start_prompt(prompt: str | None, prompt_file: Path | None) -> str:
    if prompt is not None or prompt_file is not None:
        return _read_improve_prompt(prompt, prompt_file)
    return input("Paste your prompt: ")
