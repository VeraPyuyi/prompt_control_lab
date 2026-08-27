from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _runner() -> ModuleType:
    path = Path("scripts/run_agent_guard_paired_pilot.py")
    spec = importlib.util.spec_from_file_location("pcl_paired_pilot_runner", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_codex_jsonl_usage_uses_last_complete_turn() -> None:
    runner = _runner()
    stdout = "\n".join(
        [
            json.dumps({"type": "turn.started"}),
            json.dumps(
                {
                    "type": "turn.completed",
                    "usage": {
                        "input_tokens": 120,
                        "cached_input_tokens": 40,
                        "output_tokens": 30,
                    },
                }
            ),
        ]
    )

    assert runner._codex_usage(stdout) == {
        "input_tokens": 120,
        "cached_input_tokens": 40,
        "output_tokens": 30,
        "total_tokens": 150,
    }


def test_codex_jsonl_tool_count_ignores_started_items() -> None:
    runner = _runner()
    item = {"type": "command_execution", "command": "pytest -q"}
    stdout = "\n".join(
        [
            json.dumps({"type": "item.started", "item": item}),
            json.dumps({"type": "item.completed", "item": item}),
            json.dumps({"type": "item.completed", "item": {"type": "agent_message"}}),
        ]
    )

    assert runner._codex_tool_call_count(stdout) == 1
