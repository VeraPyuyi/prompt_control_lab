"""Integrations command handlers and terminal formatters."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

from promptcontrollab.cli.common import _config_path, _print_command_payload
from promptcontrollab.core.config import (
    get_config_str,
    load_project_config,
)
from promptcontrollab.core.errors import PromptControlLabError
from promptcontrollab.core.files import JsonDict, read_json
from promptcontrollab.core.network import is_loopback_host
from promptcontrollab.integrations.doctor import format_doctor, run_doctor
from promptcontrollab.integrations.ecosystem_demo import (
    run_ecosystem_demo,
    write_ecosystem_scorecard,
)
from promptcontrollab.integrations.harness_integration import (
    doctor_harness,
    finalize_harness_run,
    initialize_harness_project,
    replay_harness_session,
    resolve_harness_report,
)
from promptcontrollab.integrations.plugin_installer import install_plugin
from promptcontrollab.integrations.providers import (
    doctor_provider,
    inspect_provider,
    list_providers,
)
from promptcontrollab.integrations.templates import write_external_examples


def _cmd_ecosystem_demo(args: argparse.Namespace) -> None:
    """Execute the ecosystem demo command handler."""
    payload = run_ecosystem_demo(
        examples_dir=args.examples,
        out_dir=args.out,
        split_hash=args.split_hash,
        provider=args.provider,
        model=args.model,
        bootstrap_samples=args.bootstrap_samples,
        permutation_samples=args.permutation_samples,
    )
    if args.summary:
        print(_format_ecosystem_demo_summary(payload))
        return
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_ecosystem_scorecard(args: argparse.Namespace) -> None:
    """Execute the ecosystem scorecard command handler."""
    payload = write_ecosystem_scorecard(run_dir=args.run, out_path=args.out)
    if args.summary:
        print(_format_ecosystem_scorecard_summary(payload))
        return
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _format_ecosystem_scorecard_summary(payload: JsonDict) -> str:
    lines = [
        "Ecosystem scorecard summary",
        f"HTML: {payload.get('html_path', '')}",
        f"Markdown: {payload.get('markdown_path', '')}",
        "",
    ]
    lines.extend(_market_readiness_summary_lines(payload))
    return "\n".join(lines)


def _format_ecosystem_demo_summary(payload: JsonDict) -> str:
    runs = payload.get("runs")
    run_count = len(runs) if isinstance(runs, list) else 0
    scorecard_path = Path(str(payload.get("ecosystem_scorecard_path") or ""))
    scorecard_payload = read_json(scorecard_path) if scorecard_path.exists() else {}
    lines = [
        "Ecosystem demo summary",
        f"Run: {payload.get('out_dir', '')}",
        f"Tool bundles: {run_count}",
        f"Scorecard: {payload.get('ecosystem_scorecard_html_path', '')}",
        f"Research bundle: {payload.get('research_bundle_html_path', '')}",
        "",
    ]
    if scorecard_payload:
        lines.extend(_market_readiness_summary_lines(scorecard_payload))
    else:
        lines.append("Market readiness: not available")
    lines.extend(
        [
            "",
            "Next: open ecosystem_scorecard.html first, or run the local UI Research Overview.",
        ]
    )
    return "\n".join(lines)


def _market_readiness_summary_lines(payload: JsonDict) -> list[str]:
    readiness = payload.get("market_readiness")
    readiness_dict = readiness if isinstance(readiness, dict) else {}
    next_moves = readiness_dict.get("next_moves")
    lines = [
        "Market readiness",
        f"Status: {readiness_dict.get('status', 'unknown')}",
    ]
    positioning = str(readiness_dict.get("recommended_positioning") or "")
    if positioning:
        lines.append(f"Positioning: {positioning}")
    first_users = _summary_string_items(readiness_dict.get("best_first_users"))
    if first_users:
        lines.extend(["", "Best first users:", *[f"- {item}" for item in first_users]])
    do_not_build = _summary_string_items(readiness_dict.get("do_not_build"))
    if do_not_build:
        lines.extend(["", "Do not build:", *[f"- {item}" for item in do_not_build]])
    lines.extend(["", "Next moves:"])
    if isinstance(next_moves, list) and next_moves:
        for item in next_moves:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- {item.get('priority', '')} {item.get('tool', '')}: {item.get('move', '')}"
            )
    else:
        lines.append("- No next moves recorded.")
    lines.extend(
        [
            "",
            "Boundary: positioning guidance only; imported rows remain the evidence.",
        ]
    )
    return lines


def _summary_string_items(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _run_start_ecosystem(args: argparse.Namespace, *, out_dir: Path) -> JsonDict:
    examples_dir = Path("examples") / "external"
    if examples_dir.exists():
        return _run_ecosystem_demo_with_examples(args, examples_dir=examples_dir, out_dir=out_dir)
    bundled_examples = out_dir.parent / f"{out_dir.name}_source_examples"
    write_external_examples(bundled_examples)
    return _run_ecosystem_demo_with_examples(
        args,
        examples_dir=bundled_examples,
        out_dir=out_dir,
    )


def _run_ecosystem_demo_with_examples(
    args: argparse.Namespace,
    *,
    examples_dir: Path,
    out_dir: Path,
) -> JsonDict:
    return run_ecosystem_demo(
        examples_dir=examples_dir,
        out_dir=out_dir,
        split_hash="external-demo-split",
        provider=args.provider or "openai",
        model=args.model or "gpt-4o-mini-20260601",
        bootstrap_samples=50,
        permutation_samples=50,
    )


def _format_start_ecosystem_result(
    *,
    out_dir: Path,
    payload: JsonDict,
    language: str = "en",
) -> str:
    runs = payload.get("runs")
    run_count = len(runs) if isinstance(runs, list) else 0
    scorecard = payload.get("ecosystem_scorecard_html_path") or str(
        out_dir / "ecosystem_scorecard.html"
    )
    bundle = out_dir / "research_bundle.html"
    if language == "zh":
        return "\n".join(
            [
                f"已生成生态对比 demo: {out_dir}",
                f"- 工具证据包数量: {run_count}",
                f"- 先打开: {scorecard}",
                (
                    "- 先看 Market readiness: 它会告诉你 PCL 应该优先切入哪里, "
                    "学习什么, 暂时不要做什么。"
                ),
                f"- 研究证据包: {bundle}",
                "- 下一步: 再看扩展市场地图和每个外部工具强项, 确认 PCL 补充的证据层。",
            ]
        )
    return "\n".join(
        [
            f"Generated ecosystem comparison demo: {out_dir}",
            f"- Tool bundles: {run_count}",
            f"- Open first: {scorecard}",
            (
                "- Start with Market readiness: it shows where PCL should lead, "
                "learn, and avoid overbuilding."
            ),
            f"- Research bundle: {bundle}",
            (
                "- Next: review the extended market map and each external tool's strength "
                "against PCL-added evidence."
            ),
        ]
    )


def _cmd_providers_list(args: argparse.Namespace) -> None:
    """Execute the providers list command handler."""
    _print_command_payload(list_providers(), compact=args.json)


def _cmd_providers_inspect(args: argparse.Namespace) -> None:
    """Execute the providers inspect command handler."""
    payload = inspect_provider(
        args.provider,
        base_url=args.base_url,
        api_key_env=args.api_key_env,
    )
    _print_command_payload(payload, compact=args.json)


def _cmd_providers_doctor(args: argparse.Namespace) -> None:
    """Execute the providers doctor command handler."""
    payload = doctor_provider(
        args.provider,
        live=args.live,
        model=args.model,
        base_url=args.base_url,
        api_key_env=args.api_key_env,
        timeout=args.timeout,
    )
    _print_command_payload(payload, compact=args.json)


def _cmd_harness_init(args: argparse.Namespace) -> None:
    """Execute the harness init command handler."""
    payload = initialize_harness_project(args.project, force=args.force)
    _print_command_payload(payload, compact=args.json)


def _cmd_harness_doctor(args: argparse.Namespace) -> None:
    """Execute the harness doctor command handler."""
    _print_command_payload(doctor_harness(args.project), compact=args.json)


def _cmd_harness_replay(args: argparse.Namespace) -> None:
    """Execute the harness replay command handler."""
    payload = replay_harness_session(
        args.session,
        run_dir=args.out,
        policy_path=args.policy,
        authorization=args.authorization,
    )
    _print_command_payload(payload, compact=args.json)


def _cmd_harness_finalize(args: argparse.Namespace) -> None:
    """Execute the harness finalize command handler."""
    payload = finalize_harness_run(
        args.runs,
        args.session,
        outcome=args.outcome,
        exit_code=args.exit_code,
    )
    _print_command_payload(payload, compact=args.json)


def _cmd_harness_report(args: argparse.Namespace) -> None:
    """Execute the harness report command handler."""
    payload = resolve_harness_report(args.runs, args.session)
    _print_command_payload(payload, compact=args.json)


def _cmd_install_plugin(args: argparse.Namespace) -> None:
    """Execute the install plugin command handler."""
    payload = install_plugin(
        args.plugin,
        target=args.target,
        force=args.force,
        dry_run=args.dry_run,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_doctor(args: argparse.Namespace) -> None:
    """Execute the doctor command handler."""
    payload = run_doctor()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(format_doctor(payload))


def _cmd_ui(args: argparse.Namespace) -> None:
    """Launch the React cockpit or the compatibility Streamlit dashboard."""
    if not is_loopback_host(args.host):
        raise PromptControlLabError(
            "The unauthenticated local UI can bind only to a loopback host."
        )
    project_config, project_config_path = load_project_config()
    runs_dir = (
        args.runs or _config_path(project_config, project_config_path, "runs_dir") or Path("runs")
    )
    policy_path = args.policy or _config_path(
        project_config,
        project_config_path,
        "guard_policy",
    )
    default_view = get_config_str(project_config, "ui.default_view", "workflows")
    required = ["streamlit", "plotly"] if args.legacy_streamlit else ["fastapi", "uvicorn"]
    missing = [module for module in required if importlib.util.find_spec(module) is None]
    if missing:
        msg = (
            f"pcl ui requires optional UI dependencies ({', '.join(missing)} missing). "
            "Install them with "
            '`pip install -e ".[ui]"` or `uv pip install -e ".[ui]"`.'
        )
        raise PromptControlLabError(msg)
    env = os.environ.copy()
    env["PCL_UI_RUNS"] = str(runs_dir)
    env["PCL_UI_POLICY"] = str(policy_path) if policy_path is not None else ""
    env["PCL_UI_LANGUAGE"] = args.language
    env["PCL_UI_DEFAULT_VIEW"] = default_view
    env["PCL_UI_CONFIG"] = str(project_config_path) if project_config_path is not None else ""
    if args.legacy_streamlit:
        app_path = Path(__file__).resolve().parents[2] / "integrations" / "ui" / "app.py"
        if not app_path.is_file():
            raise PromptControlLabError(f"Streamlit app entry point is missing: {app_path}")
        command = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app_path),
            f"--server.address={args.host}",
            f"--server.port={args.port}",
            f"--server.headless={str(args.no_browser).lower()}",
            "--browser.gatherUsageStats=false",
            "--client.toolbarMode=viewer",
        ]
        service = "Streamlit"
    else:
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "promptcontrollab.integrations.web_api:create_app",
            "--factory",
            "--host",
            str(args.host),
            "--port",
            str(args.port),
        ]
        service = "Workflow cockpit"
        if not args.no_browser:
            browser_host = "127.0.0.1" if args.host in {"0.0.0.0", "localhost"} else args.host
            timer = threading.Timer(
                1.0,
                webbrowser.open,
                args=(f"http://{browser_host}:{args.port}",),
            )
            timer.daemon = True
            timer.start()
    try:
        subprocess.run(command, env=env, check=True)
    except KeyboardInterrupt:
        return
    except subprocess.CalledProcessError as exc:
        msg = f"{service} exited with status {exc.returncode}"
        raise PromptControlLabError(msg) from exc
