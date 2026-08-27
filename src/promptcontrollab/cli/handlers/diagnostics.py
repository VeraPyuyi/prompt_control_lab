"""Diagnostics command handlers and terminal formatters."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from promptcontrollab.cli.common import _maybe_refresh_explanation, _open_html_report
from promptcontrollab.core.errors import PromptControlLabError
from promptcontrollab.core.files import JsonDict
from promptcontrollab.diagnostics.green_certificate import analyze_green_certificate
from promptcontrollab.diagnostics.hf_hidden import extract_hidden_states
from promptcontrollab.diagnostics.posterior_certificate import analyze_posterior_certificate
from promptcontrollab.diagnostics.research_workflow import (
    run_research_diagnostics,
    verify_research_bundle_index,
    write_research_bundle_index,
    write_research_demo,
    write_research_gap_status,
)
from promptcontrollab.diagnostics.riccati import analyze_riccati
from promptcontrollab.diagnostics.soft_hard import analyze_soft_hard
from promptcontrollab.diagnostics.terminal_sensitivity import analyze_terminal_sensitivity
from promptcontrollab.diagnostics.trajectory import analyze_trajectory
from promptcontrollab.diagnostics.tv_soft import summarize_tv_soft


def _cmd_research_demo(args: argparse.Namespace) -> None:
    """Execute the research demo command handler."""
    payload = write_research_demo(out_dir=args.out, seed=args.seed)
    print(_format_research_demo_output(out_dir=args.out, payload=payload, language=args.language))


def _cmd_research_quickstart(args: argparse.Namespace) -> None:
    """Execute the research quickstart command handler."""
    write_research_demo(out_dir=args.out, seed=args.seed)
    payload = run_research_diagnostics(
        run_dir=args.out,
        mode="diagnose",
        summary_dir=args.out,
    )
    if args.language == "zh":
        print("研究 quickstart: 已生成论文诊断 demo 并刷新 diagnose 证据包")
    else:
        print("Research quickstart: generated the paper demo and refreshed diagnose evidence")
    print(_format_research_demo_output(out_dir=args.out, payload=payload, language=args.language))
    if args.open_report:
        report_name = "research_bundle.zh.html" if args.language == "zh" else "research_bundle.html"
        _open_html_report(args.out / report_name, language=args.language)


def _format_research_demo_output(
    *,
    out_dir: Path,
    payload: JsonDict,
    language: str = "en",
) -> str:
    diagnostics = payload.get("diagnostics", {})
    diagnostic_names = sorted(diagnostics) if isinstance(diagnostics, dict) else []
    readable_diagnostics = _readable_research_diagnostic_names(
        diagnostic_names,
        language=language,
    )
    if language == "zh":
        lines = [
            f"已写出研究 demo: {out_dir}",
            f"做了什么: 生成一个用于论文诊断的小型 synthetic 证据包({readable_diagnostics})。",
            f"诊断项: {', '.join(diagnostic_names)}",
            *_research_cli_summary_lines(
                summary_dir=out_dir,
                payload=payload,
                language=language,
            ),
            *_research_output_guide_lines(out_dir, language=language),
            f"UI: pcl ui --runs {out_dir} --language zh",
        ]
        return "\n".join(lines)
    lines = [
        f"Wrote research demo to {out_dir}",
        "What it did: generated a small synthetic evidence bundle for the paper "
        f"diagnostics ({readable_diagnostics}).",
        f"Diagnostics: {', '.join(diagnostic_names)}",
        *_research_cli_summary_lines(summary_dir=out_dir, payload=payload, language=language),
        *_research_output_guide_lines(out_dir, language=language),
        f"UI: pcl ui --runs {out_dir}",
    ]
    return "\n".join(lines)


def _readable_research_diagnostic_names(names: list[str], *, language: str = "en") -> str:
    labels = _research_diagnostic_labels(language=language)
    readable = [labels.get(name, name.replace("_", "-")) for name in names]
    return ", ".join(readable) if readable else "none"


def _research_diagnostic_labels(*, language: str = "en") -> dict[str, str]:
    if language == "zh":
        return {
            "soft_hard": "soft-hard gap (soft prompt 转 hard prompt 的差距)",
            "trajectory": "hidden-state trajectory (隐藏状态轨迹)",
            "riccati": "Riccati surrogate (降维控制论替代模型)",
            "tv_soft": "time-varying soft-control (时变 soft prompt 控制)",
            "terminal_sensitivity": "终端敏感度衰减",
            "green_certificate": "Green 边界证书",
            "posterior_certificate": "局部后验证书",
        }
    return {
        "soft_hard": "soft-hard gap",
        "trajectory": "hidden-state trajectory",
        "riccati": "Riccati surrogate",
        "tv_soft": "time-varying soft-control",
        "terminal_sensitivity": "terminal sensitivity decay",
        "green_certificate": "Green boundary certificate",
        "posterior_certificate": "local posterior certificate",
    }


def _research_output_guide_lines(out_dir: Path, *, language: str = "en") -> list[str]:
    if language == "zh":
        return [
            "",
            "如何阅读输出:",
            f"研究诊断报告: {out_dir / 'research_diagnostics.html'}",
            "  用直白语言解释每个论文诊断。",
            f"证据卡片: {out_dir / 'evidence_card.html'}",
            "  总结当前 prompt optimization 主张有哪些证据支持。",
            f"主张检查: {out_dir / 'claim_check.html'}",
            "  说明当前证据最多能安全支持什么主张。",
            f"证据门禁: {out_dir / 'evidence_gate_result.html'}",
            "  检查论文证据 artifact 是否齐全、是否链接完整。",
        ]
    return [
        "",
        "How to read the outputs:",
        f"Research diagnostics: {out_dir / 'research_diagnostics.html'}",
        "  Explains each paper-derived diagnostic in plain language.",
        f"Evidence card: {out_dir / 'evidence_card.html'}",
        "  Summarizes what evidence exists for a prompt-optimization claim.",
        f"Claim check: {out_dir / 'claim_check.html'}",
        "  Shows the strongest claim this run can safely support.",
        f"Evidence gate: {out_dir / 'evidence_gate_result.html'}",
        "  Checks whether required research artifacts are present and linked.",
    ]


def _research_cli_summary_lines(
    *,
    summary_dir: Path,
    payload: JsonDict,
    language: str = "en",
) -> list[str]:
    at_a_glance = payload.get("at_a_glance")
    summary = at_a_glance if isinstance(at_a_glance, dict) else {}
    diagnostics_ready = summary.get("diagnostics_ready", "unknown")
    control_certificates_ready = summary.get("control_certificates_ready", "unknown")
    claim_status = summary.get("claim_status", "unknown")
    evidence_tier = summary.get("evidence_tier", "unknown")
    readable_tier = _readable_evidence_tier(str(evidence_tier), language=language)
    next_action = summary.get("next_action")
    open_first = summary.get("open_first")
    if language == "zh":
        lines = [
            (
                f"概览: 诊断={diagnostics_ready}; 控制证书={control_certificates_ready}; "
                f"主张检查={claim_status}; 证据层级={readable_tier}"
            ),
        ]
        if isinstance(open_first, str) and open_first:
            open_path = (
                "research_bundle.zh.html" if open_first == "research_bundle.html" else open_first
            )
            lines.append(f"先打开: {summary_dir / open_path}")
        if isinstance(next_action, str) and next_action:
            lines.append(f"下一步: {_translate_research_next_action(next_action)}")
        return lines
    lines = [
        (
            "At a glance: "
            f"diagnostics={diagnostics_ready}; claim={claim_status}; "
            f"evidence tier={readable_tier}; "
            f"control certificates={control_certificates_ready}"
        ),
    ]
    if isinstance(open_first, str) and open_first:
        lines.append(f"Open first: {summary_dir / open_first}")
    if isinstance(next_action, str) and next_action:
        lines.append(f"Next action: {next_action}")
    return lines


def _readable_evidence_tier(value: str, *, language: str = "en") -> str:
    if language == "zh":
        labels = {
            "tier_1_paired": "仅成对比较",
            "tier_2_partial_research": "部分研究诊断",
            "tier_3_research_ready": "研究证据基本齐备",
            "tier_4_full_research_diagnostics": "完整研究诊断",
        }
        return labels.get(value, value.replace("_", " "))
    labels = {
        "tier_1_paired": "paired comparison only",
        "tier_2_partial_research": "partial research diagnostics",
        "tier_3_research_ready": "research-ready evidence",
        "tier_4_full_research_diagnostics": "full research diagnostics",
    }
    return labels.get(value, value.replace("_", " "))


def _translate_research_next_action(value: str) -> str:
    if value == "Share the research bundle, evidence card, and claim check together.":
        return "把 research_bundle、evidence_card 和 claim_check 一起分享给审阅者。"
    return value


def _cmd_research_bundle(args: argparse.Namespace) -> None:
    """Execute the research bundle command handler."""
    if args.strict and not args.verify:
        msg = "research-bundle --strict must be used together with --verify"
        raise PromptControlLabError(msg)
    if args.verify:
        payload = verify_research_bundle_index(args.run)
    else:
        payload = write_research_bundle_index(args.run)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    if args.strict and payload.get("status") != "pass":
        msg = (
            "Research bundle verification failed in strict mode: "
            f"status={payload.get('status')}, "
            f"mismatches={payload.get('mismatch_count')}, "
            f"missing={payload.get('missing_count')}, "
            f"unchecked={payload.get('unchecked_count')}"
        )
        raise PromptControlLabError(msg)


def _cmd_diagnose(args: argparse.Namespace) -> None:
    """Execute the diagnose command handler."""
    summary_dir = args.run if args.run is not None else args.out
    payload = run_research_diagnostics(
        run_dir=args.run,
        mode="diagnose",
        soft_path=args.soft,
        vocab_path=args.vocab,
        states_path=args.states,
        matrices_path=args.matrices,
        tv_predictions_path=args.tv_predictions,
        diagnostics_dir=args.out,
        summary_dir=summary_dir,
        baseline_method=args.baseline_method,
        tail=args.tail,
        iterations=args.iterations,
    )
    summary_dir_path = Path(str(payload["summary_dir"]))
    if args.language == "zh":
        print(f"已写出研究诊断: {payload['diagnostics_dir']}")
        print(f"报告: {summary_dir_path / 'research_diagnostics.html'}")
    else:
        print(f"Wrote research diagnostics to {payload['diagnostics_dir']}")
        print(f"Report: {summary_dir_path / 'research_diagnostics.html'}")
    print(
        "\n".join(
            _research_cli_summary_lines(
                summary_dir=summary_dir_path,
                payload=payload,
                language=args.language,
            )
        )
    )
    print("\n".join(_research_output_guide_lines(summary_dir_path, language=args.language)))


def _cmd_terminal_sensitivity(args: argparse.Namespace) -> None:
    """Execute the terminal sensitivity command handler."""
    payload = analyze_terminal_sensitivity(
        records_path=args.records,
        surrogate_path=args.surrogate,
        horizons=args.horizons,
        early_steps=args.early_steps,
        bootstrap_samples=args.bootstrap_samples,
        out_dir=args.out,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_green_certificate(args: argparse.Namespace) -> None:
    """Execute the green certificate command handler."""
    payload = analyze_green_certificate(
        surrogate_path=args.surrogate,
        horizons=args.horizons,
        premises_path=args.premises,
        out_dir=args.out,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_posterior_certificate(args: argparse.Namespace) -> None:
    """Execute the posterior certificate command handler."""
    payload = analyze_posterior_certificate(input_path=args.input, out_dir=args.out)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_gap_status(args: argparse.Namespace) -> None:
    """Execute the gap status command handler."""
    payload = write_research_gap_status(run_dir=args.run, out_path=args.out)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_extract_hidden(args: argparse.Namespace) -> None:
    """Execute the extract hidden command handler."""
    payload = extract_hidden_states(
        model_id=args.model,
        prompts_path=args.prompts,
        out_path=args.out,
        layer=args.layer,
        pool=args.pool,
        max_items=args.max_items,
        max_length=args.max_length,
        device=args.device,
        trust_remote_code=args.trust_remote_code,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_soft_hard(args: argparse.Namespace) -> None:
    """Execute the soft hard command handler."""
    analyze_soft_hard(soft_path=args.soft, vocab_path=args.vocab, out_dir=args.out)
    _maybe_refresh_explanation(args.out, args.explain_level)
    print(f"Wrote soft-hard diagnostics to {args.out}")


def _cmd_trajectory(args: argparse.Namespace) -> None:
    """Execute the trajectory command handler."""
    analyze_trajectory(states_path=args.states, out_dir=args.out, tail=args.tail)
    _maybe_refresh_explanation(args.out, args.explain_level)
    print(f"Wrote trajectory diagnostics to {args.out}")


def _cmd_riccati(args: argparse.Namespace) -> None:
    """Execute the riccati command handler."""
    analyze_riccati(
        matrices_path=args.matrices,
        trajectory_path=args.trajectory,
        out_dir=args.out,
        iterations=args.iterations,
    )
    _maybe_refresh_explanation(args.out, args.explain_level)
    print(f"Wrote Riccati diagnostics to {args.out}")


def _cmd_tv_soft(args: argparse.Namespace) -> None:
    """Execute the tv soft command handler."""
    summarize_tv_soft(
        predictions_path=args.predictions,
        out_dir=args.out,
        baseline_method=args.baseline_method,
    )
    _maybe_refresh_explanation(args.out, args.explain_level)
    print(f"Wrote time-varying soft-control summary to {args.out}")
