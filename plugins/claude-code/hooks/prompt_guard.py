"""Claude Code UserPromptSubmit hook for prompt_control_lab."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


sys.path.insert(0, str(_repo_root() / "src"))

from promptcontrollab.prompt_context import load_prompt_context  # noqa: E402
from promptcontrollab.prompt_guard import guard_prompt  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="prompt_control_lab Claude Code hook.")
    parser.add_argument("--mode", choices=["suggest", "auto", "gate"], default="suggest")
    parser.add_argument("--profile", choices=["general", "coding", "research"], default="coding")
    parser.add_argument("--token-mode", choices=["balanced", "aggressive"], default="balanced")
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--run", type=Path, default=None)
    args = parser.parse_args(argv)

    event = _read_event()
    prompt = _extract_prompt(event)
    result = guard_prompt(
        prompt,
        context=load_prompt_context(args.run),
        mode=args.mode,
        profile=args.profile,
        token_mode=args.token_mode,
        max_tokens=args.max_tokens,
    )
    print(json.dumps(_claude_response(result.to_json()), ensure_ascii=False, sort_keys=True))
    return 0


def _read_event() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict):
        msg = "Claude Code hook input must be a JSON object"
        raise ValueError(msg)
    return value


def _extract_prompt(event: dict[str, Any]) -> str:
    prompt = event.get("prompt")
    if isinstance(prompt, str):
        return prompt
    message = event.get("message")
    if isinstance(message, str):
        return message
    return ""


def _claude_response(result: dict[str, Any]) -> dict[str, Any]:
    if result["action"] == "block":
        return {
            "decision": "block",
            "reason": "prompt_control_lab blocked this prompt: " + "; ".join(result["reasons"]),
        }
    context = "\n".join(
        [
            "prompt_control_lab guard suggestion:",
            "",
            str(result["improved_prompt"]),
            "",
            "Reasons:",
            *[f"- {reason}" for reason in result["reasons"]],
        ]
    )
    return {"additionalContext": context}


if __name__ == "__main__":
    raise SystemExit(main())
