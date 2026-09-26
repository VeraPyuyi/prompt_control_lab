"""Control command handlers and terminal formatters."""

from __future__ import annotations

import argparse
import json

from promptcontrollab.cli.common import _config_path
from promptcontrollab.cli.handlers.preflight import (
    _read_guard_prompt,
    _stdin_is_tty,
)
from promptcontrollab.control.control_bridge import serve_stdio
from promptcontrollab.control.control_workflow import AUTHORIZATIONS, preview_guard, run_control
from promptcontrollab.control.trace_ingest import import_trace_file
from promptcontrollab.control.trace_receiver import serve_trace_http
from promptcontrollab.core.config import (
    load_project_config,
)
from promptcontrollab.integrations.providers import (
    call_provider,
)


def _cmd_control(args: argparse.Namespace) -> None:
    """Execute the control command handler."""
    authorization = args.authorization
    if authorization is None and not _stdin_is_tty():
        msg = "--authorization is required in non-interactive mode"
        raise ValueError(msg)
    prompt = _read_guard_prompt(args.prompt, args.prompt_file, args.stdin)
    project_config, project_config_path = load_project_config()
    policy_path = args.policy or _config_path(
        project_config,
        project_config_path,
        "guard_policy",
    )
    if authorization is None:
        preview = preview_guard(
            prompt,
            profile=args.profile,
            policy_path=policy_path,
            token_mode=args.token_mode,
            max_tokens=args.max_tokens,
            language=args.language,
        )
        print("Preflight preview")
        print(f"Risk: {preview['risk_level']}")
        token_report = preview["token_report"]
        print(
            "Estimated prompt tokens: "
            f"{token_report['original_estimated_tokens']} original -> "
            f"{token_report['improved_estimated_tokens']} guarded"
        )
        if args.provider and args.model:
            print(f"Provider/model: {args.provider}/{args.model}")
        else:
            print("Provider/model: not selected")
        print(f"Agent adapter: {args.agent or 'not selected'}")
        print("Authorization scopes:")
        print("- inspect: diagnostics only; no model, tool, or file execution")
        print("- model: one model request; no agent tools or file execution")
        print("- agent-scoped: adapter actions constrained by project policy")
        print("- agent-full: full scope declared by the selected adapter")
        print(
            "Boundary: PromptControlLab does not sandbox agent file access; "
            "the adapter and runtime must enforce it."
        )
        print(f"Suggested prompt:\n{preview['improved_prompt']}\n")
        authorization = input("Authorization [inspect/model/agent-scoped/agent-full]: ").strip()
        if authorization not in AUTHORIZATIONS:
            msg = f"Authorization must be one of: {', '.join(AUTHORIZATIONS)}"
            raise ValueError(msg)
    if authorization == "model" and (
        args.provider is None
        or not args.provider.strip()
        or args.model is None
        or not args.model.strip()
    ):
        msg = "Model authorization requires both --provider and --model."
        raise ValueError(msg)
    result = run_control(
        prompt=prompt,
        authorization=authorization,
        run_dir=args.out,
        run_id=args.run_id,
        provider=args.provider,
        model=args.model,
        agent=args.agent,
        profile=args.profile,
        policy_path=policy_path,
        token_mode=args.token_mode,
        max_tokens=args.max_tokens,
        language=args.language,
        model_executor=call_provider if authorization == "model" else None,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        decision = result["decision"]
        print("PromptControlLab Control")
        print(f"Run: {result['run_dir']}")
        print(f"Decision: {decision['decision']}")
        print(f"Next action: {decision['next_action']}")


def _cmd_bridge_serve(args: argparse.Namespace) -> None:
    """Execute the bridge serve command handler."""
    if args.transport != "stdio":
        msg = f"Unsupported bridge transport: {args.transport}"
        raise ValueError(msg)
    serve_stdio(runs_root=args.runs_root)


def _cmd_trace_import(args: argparse.Namespace) -> None:
    """Import external trace records into a redacted shadow control run."""

    result = import_trace_file(
        input_path=args.input,
        format_name=args.format,
        out_dir=args.out,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


def _cmd_trace_serve(args: argparse.Namespace) -> None:
    """Serve the dependency-free local OTLP JSON shadow receiver."""

    print(
        f"PromptControlLab trace receiver listening on http://{args.host}:{args.port}/v1/traces"
    )
    print(f"Shadow artifacts: {args.out}")
    serve_trace_http(host=args.host, port=args.port, out_dir=args.out)
