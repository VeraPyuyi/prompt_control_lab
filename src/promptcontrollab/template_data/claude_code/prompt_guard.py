"""Claude Code hook wrapper for prompt_control_lab."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from promptcontrollab.prompt_context import load_prompt_context
from promptcontrollab.prompt_guard import guard_prompt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="coding")
    parser.add_argument("--mode", choices=["suggest", "auto", "gate"], default="suggest")
    parser.add_argument("--policy", type=Path, default=None)
    args = parser.parse_args()
    prompt = sys.stdin.read()
    result = guard_prompt(
        prompt,
        context=load_prompt_context(None),
        profile=args.profile,
        mode=args.mode,
        token_mode="balanced",
        max_tokens=None,
        policy_path=args.policy,
    )
    print(json.dumps(result.to_json(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
