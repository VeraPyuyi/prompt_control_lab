"""Minimal stdio MCP-style server for Cursor prompt guarding.

This adapter intentionally stays dependency-free. It implements the small JSON-RPC surface
needed for Cursor or another MCP client to discover and call a `guard_prompt` tool.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from promptcontrollab.prompt_context import load_prompt_context  # noqa: E402
from promptcontrollab.prompt_guard import guard_prompt  # noqa: E402

Json = dict[str, Any]


def main() -> int:
    """Serve newline-delimited JSON-RPC requests until stdin closes."""

    for line in sys.stdin:
        if not line.strip():
            continue
        request = json.loads(line)
        response = handle_request(request)
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)
    return 0


def handle_request(request: Json) -> Json | None:
    """Handle one JSON-RPC request."""

    method = str(request.get("method", ""))
    request_id = request.get("id")
    if request_id is None:
        return None
    try:
        if method == "initialize":
            return _result(
                request_id,
                {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "prompt_control_lab", "version": "0.1.0"},
                    "capabilities": {"tools": {}},
                },
            )
        if method == "tools/list":
            return _result(request_id, {"tools": [_guard_tool_schema()]})
        if method == "tools/call":
            return _result(request_id, _call_tool(request.get("params", {})))
        return _error(request_id, -32601, f"Unknown method: {method}")
    except Exception as exc:  # pragma: no cover - defensive adapter boundary
        return _error(request_id, -32000, str(exc))


def _call_tool(params: object) -> Json:
    if not isinstance(params, dict):
        raise ValueError("Tool call params must be an object.")
    name = params.get("name")
    if name != "guard_prompt":
        raise ValueError("Only the `guard_prompt` tool is available.")
    arguments = params.get("arguments", {})
    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be an object.")
    prompt = str(arguments.get("prompt", "")).strip()
    if not prompt:
        raise ValueError("`prompt` is required.")
    run_value = arguments.get("run")
    context = load_prompt_context(Path(str(run_value))) if run_value else load_prompt_context(None)
    result = guard_prompt(
        prompt,
        context=context,
        mode=str(arguments.get("mode", "suggest")),
        profile=str(arguments.get("profile", "coding")),
        token_mode=str(arguments.get("token_mode", "balanced")),
        max_tokens=_optional_int(arguments.get("max_tokens")),
        language=str(arguments.get("language", "auto")),
    ).to_json()
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
            }
        ]
    }


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _guard_tool_schema() -> Json:
    return {
        "name": "guard_prompt",
        "description": "Check and rewrite a prompt before Cursor or another agent spends tokens.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "profile": {"type": "string", "enum": ["general", "coding", "research"]},
                "mode": {"type": "string", "enum": ["suggest", "auto", "gate"]},
                "token_mode": {"type": "string", "enum": ["balanced", "aggressive"]},
                "max_tokens": {"type": "integer"},
                "language": {"type": "string", "enum": ["auto", "zh", "en"]},
                "run": {"type": "string"},
            },
            "required": ["prompt"],
        },
    }


def _result(request_id: object, result: Json) -> Json:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: object, code: int, message: str) -> Json:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


if __name__ == "__main__":
    raise SystemExit(main())
