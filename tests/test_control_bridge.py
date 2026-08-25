from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from promptcontrollab.files import JsonDict, read_json, read_jsonl, stable_digest


def _record_accepted_harness_events(
    bridge: Any,
    *,
    run_id: str,
    session_id: str,
    start_sequence: int = 10,
) -> None:
    records: list[tuple[str, JsonDict]] = [
        (
            "agent/request",
            {
                "turn": 1,
                "step": 1,
                "request_id": "pcl-request-1",
                "request_id_source": "prompt_control_lab",
                "provider": "deepseek",
                "model": "deepseek-test",
            },
        ),
        (
            "session/assistant/message",
            {
                "turn": 1,
                "step": 1,
                "response_id": "assistant-message-1",
                "provider": "deepseek",
                "model": "deepseek-test",
            },
        ),
        (
            "tools/result",
            {"tool": {"operation_category": "file_read"}, "result": {"is_error": False}},
        ),
        (
            "tools/result",
            {"tool": {"operation_category": "file_write"}, "result": {"is_error": False}},
        ),
        (
            "tools/result",
            {
                "tool": {"operation_category": "test_execution"},
                "result": {"is_error": False, "exit_code": 0},
            },
        ),
    ]
    for offset, (event_type, payload) in enumerate(records):
        bridge.dispatch(
            "harness_event",
            {
                "run_id": run_id,
                "session_id": session_id,
                "idempotency_key": f"acceptance-{start_sequence + offset}",
                "event_type": event_type,
                "sequence": start_sequence + offset,
                "timestamp": "2026-08-23T00:00:00Z",
                "payload": payload,
            },
        )


def test_stdio_bridge_handles_a_persistent_control_lifecycle(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    runs_root = tmp_path / "runs"
    run_dir = runs_root / "bridge-run"
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "health", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "session_start",
            "params": {
                "run_id": "bridge-run",
                "run_dir": str(run_dir),
                "prompt": "Inspect the current behavior.",
                "authorization": "inspect",
                "profile": "general",
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "preflight",
            "params": {"run_id": "bridge-run"},
        },
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "event_append",
            "params": {
                "run_id": "bridge-run",
                "idempotency_key": "harness-tool-result-1",
                "event_type": "tools/post-execute",
                "payload": {
                    "tool": "fixture",
                    "api_key": "must-not-leak",
                    "message": (
                        "Authorization: Bearer bearer-secret-1234567890; "
                        "client_secret=client-secret-1234567890"
                    ),
                    "prompt": "RAW-BRIDGE-PROMPT-MUST-NOT-PERSIST",
                },
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "event_append",
            "params": {
                "run_id": "bridge-run",
                "idempotency_key": "harness-tool-result-1",
                "event_type": "tools/post-execute",
                "payload": {
                    "tool": "fixture",
                    "api_key": "must-not-leak",
                    "message": (
                        "Authorization: Bearer bearer-secret-1234567890; "
                        "client_secret=client-secret-1234567890"
                    ),
                    "prompt": "RAW-BRIDGE-PROMPT-MUST-NOT-PERSIST",
                },
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "status",
            "params": {"run_id": "bridge-run"},
        },
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "finalize",
            "params": {"run_id": "bridge-run"},
        },
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "promptcontrollab",
            "bridge",
            "serve",
            "--transport",
            "stdio",
            "--runs-root",
            str(runs_root),
        ],
        cwd=root,
        env=env,
        input="".join(json.dumps(request) + "\n" for request in requests),
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
    responses = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    assert [response["id"] for response in responses] == list(range(1, 8))
    assert responses[0]["result"]["status"] == "ok"
    assert responses[0]["result"]["protocol"] == "prompt_control_lab.bridge.v1"
    assert responses[1]["result"]["run_id"] == "bridge-run"
    assert responses[2]["result"]["decision"] in {"allow", "suggest"}
    assert responses[2]["result"]["improved_prompt"] != "[REDACTED]"
    assert responses[3]["result"]["appended"] is True
    assert responses[4]["result"]["appended"] is False
    assert responses[5]["result"]["event_count"] == 3
    assert responses[6]["result"]["status"] == "finalized"

    events = read_jsonl(run_dir / "events.jsonl")
    assert [event["sequence"] for event in events] == [1, 2, 3, 4]
    assert events[0]["payload"]["authorization_scope"] == "inspect"
    assert "authorization" not in events[0]["payload"]
    assert events[2]["payload"]["api_key"] == "[REDACTED]"
    assert read_json(run_dir / "preflight.json")["details"]["authorization_scope"] == "inspect"
    persisted = (run_dir / "events.jsonl").read_text(encoding="utf-8")
    for secret in (
        "must-not-leak",
        "bearer-secret-1234567890",
        "client-secret-1234567890",
        "RAW-BRIDGE-PROMPT-MUST-NOT-PERSIST",
    ):
        assert secret not in persisted
    assert read_json(run_dir / "control_run.json")["status"] == "finalized"
    assert (runs_root / ".prompt_control_lab" / "runs.sqlite3").exists()


def test_stdio_bridge_recovers_custom_run_directory_after_restart(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    runs_root = tmp_path / "registry-root"
    custom_run = runs_root / "nested" / "custom-run"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")
    command = [
        sys.executable,
        "-m",
        "promptcontrollab",
        "bridge",
        "serve",
        "--transport",
        "stdio",
        "--runs-root",
        str(runs_root),
    ]
    first_requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "session_start",
            "params": {
                "run_id": "custom-run",
                "run_dir": str(custom_run),
                "prompt": "Inspect this run.",
                "authorization": "inspect",
            },
        }
    ]
    first = subprocess.run(
        command,
        cwd=root,
        env=env,
        input="".join(json.dumps(request) + "\n" for request in first_requests),
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert first.returncode == 0, first.stderr
    assert len(first.stdout.splitlines()) == 1

    second_requests = [
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "preflight",
            "params": {"run_id": "custom-run", "prompt": "Inspect this run."},
        },
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "status",
            "params": {"run_id": "custom-run"},
        },
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "event_append",
            "params": {
                "run_id": "custom-run",
                "idempotency_key": "after-restart-1",
                "event_type": "session/event",
                "payload": {"kind": "fixture"},
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "finalize",
            "params": {"run_id": "custom-run"},
        },
    ]
    second = subprocess.run(
        command,
        cwd=root,
        env=env,
        input="".join(json.dumps(request) + "\n" for request in second_requests),
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert second.returncode == 0, second.stderr
    responses = [json.loads(line) for line in second.stdout.splitlines() if line.strip()]
    assert responses[0]["result"]["decision"] in {"allow", "suggest"}
    assert responses[1]["result"]["run_dir"] == str(custom_run.resolve())
    assert responses[2]["result"]["appended"] is True
    assert responses[3]["result"]["status"] == "finalized"
    assert read_json(custom_run / "control_run.json")["status"] == "finalized"


def test_stdio_bridge_returns_json_rpc_error_and_continues(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")
    requests = [
        {"jsonrpc": "2.0", "id": "bad", "method": "unknown", "params": {}},
        {"jsonrpc": "2.0", "id": "good", "method": "health", "params": {}},
    ]
    completed = subprocess.run(
        [sys.executable, "-m", "promptcontrollab", "bridge", "serve", "--transport", "stdio"],
        cwd=root,
        env=env,
        input="".join(json.dumps(request) + "\n" for request in requests),
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
    responses = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    assert responses[0]["error"]["code"] == -32601
    assert responses[1]["result"]["status"] == "ok"


def test_stdio_bridge_obeys_notification_and_error_code_contract(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")
    lines = [
        json.dumps({"jsonrpc": "2.0", "method": "health", "params": {}}),
        json.dumps({"jsonrpc": "2.0", "method": "health", "params": []}),
        json.dumps({"jsonrpc": "1.0", "id": "version", "method": "health", "params": {}}),
        json.dumps({"jsonrpc": "2.0", "id": "params", "method": "health", "params": []}),
        json.dumps({"jsonrpc": "2.0", "id": "missing", "params": {}}),
        json.dumps({"jsonrpc": "2.0", "id": "good", "method": "health", "params": {}}),
    ]
    completed = subprocess.run(
        [sys.executable, "-m", "promptcontrollab", "bridge", "serve", "--transport", "stdio"],
        cwd=root,
        env=env,
        input="\n".join(lines) + "\n",
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
    responses = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    assert [response["id"] for response in responses] == ["version", "params", "missing", "good"]
    assert responses[0]["error"]["code"] == -32600
    assert responses[1]["error"]["code"] == -32602
    assert responses[2]["error"]["code"] == -32600
    assert responses[3]["result"]["status"] == "ok"


def test_stdio_bridge_requires_event_idempotency_key(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")
    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "session_start",
            "params": {
                "run_id": "key-run",
                "prompt": "Inspect this prompt.",
                "authorization": "inspect",
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "event_append",
            "params": {
                "run_id": "key-run",
                "event_type": "session/event",
                "payload": {},
            },
        },
    ]
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "promptcontrollab",
            "bridge",
            "serve",
            "--transport",
            "stdio",
            "--runs-root",
            str(tmp_path / "runs"),
        ],
        cwd=root,
        env=env,
        input="".join(json.dumps(request) + "\n" for request in requests),
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
    responses = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    assert responses[1]["error"]["code"] == -32602
    assert "idempotency_key" in responses[1]["error"]["message"]


def test_bridge_rejects_run_directories_outside_resolved_runs_root(tmp_path: Path) -> None:
    from promptcontrollab.control_bridge import ControlBridge

    runs_root = tmp_path / "runs"
    bridge = ControlBridge(runs_root)
    base = {
        "run_id": "escaped-run",
        "prompt": "Inspect this prompt.",
        "authorization": "inspect",
    }
    outside = tmp_path / "outside" / "run"
    with pytest.raises(ValueError, match="runs root"):
        bridge.dispatch("session_start", {**base, "run_dir": str(outside)})
    with pytest.raises(ValueError, match="runs root"):
        bridge.dispatch("session_start", {**base, "run_dir": "../escaped/run"})
    assert not outside.exists()
    assert not (tmp_path / "escaped").exists()


def test_bridge_session_start_retry_is_idempotent_and_rejects_conflicts(
    tmp_path: Path,
) -> None:
    from promptcontrollab.control_bridge import ControlBridge
    from promptcontrollab.control_index import RunIndex

    runs_root = tmp_path / "runs"
    first_dir = runs_root / "primary"
    bridge = ControlBridge(runs_root)
    request = {
        "run_id": "stable-run",
        "run_dir": str(first_dir),
        "prompt": "Inspect the current behavior.",
        "authorization": "inspect",
        "provider": "deepseek",
        "model": "fixture-model",
        "profile": "general",
    }

    first = bridge.dispatch("session_start", request)
    retry = bridge.dispatch("session_start", request)
    assert first["run_dir"] == retry["run_dir"] == str(first_dir.resolve())
    assert first["event_count"] == retry["event_count"] == 1

    with pytest.raises(ValueError, match="conflicts with existing control run"):
        bridge.dispatch(
            "session_start",
            {**request, "prompt": "A changed prompt must not reuse this run."},
        )
    with pytest.raises(ValueError, match="already registered"):
        bridge.dispatch(
            "session_start",
            {**request, "run_dir": str(runs_root / "other")},
        )

    index = RunIndex(runs_root / ".prompt_control_lab" / "runs.sqlite3")
    record = index.get("stable-run")
    assert record is not None
    assert record["run_dir"] == str(first_dir.resolve())
    assert len(read_jsonl(first_dir / "events.jsonl")) == 1


def test_bridge_rejects_event_append_after_finalize(tmp_path: Path) -> None:
    from promptcontrollab.control_bridge import ControlBridge

    runs_root = tmp_path / "runs"
    run_dir = runs_root / "finalized-run"
    bridge = ControlBridge(runs_root)
    bridge.dispatch(
        "session_start",
        {
            "run_id": "finalized-run",
            "run_dir": str(run_dir),
            "prompt": "Inspect this prompt.",
            "authorization": "inspect",
        },
    )
    bridge.dispatch("preflight", {"run_id": "finalized-run"})
    bridge.dispatch("finalize", {"run_id": "finalized-run"})

    with pytest.raises(ValueError, match="finalized"):
        bridge.dispatch(
            "event_append",
            {
                "run_id": "finalized-run",
                "event_type": "session/event",
                "idempotency_key": "too-late",
                "payload": {"status": "late"},
            },
        )
    assert len(read_jsonl(run_dir / "events.jsonl")) == 3


@pytest.mark.parametrize(
    "override_name",
    ["profile", "policy_path", "token_mode", "max_tokens", "language"],
)
def test_bridge_restart_rejects_configuration_overrides(
    tmp_path: Path,
    override_name: str,
) -> None:
    from promptcontrollab.control_bridge import ControlBridge

    runs_root = tmp_path / "runs"
    run_id = f"restart-{override_name.replace('_', '-')}"
    prompt = "Inspect the persisted bridge configuration."
    recorded_policy = tmp_path / "recorded.policy.yaml"
    other_policy = tmp_path / "other.policy.yaml"
    _write_guard_policy(recorded_policy, message="Use the recorded policy.")
    _write_guard_policy(other_policy, message="This is a different policy.")
    ControlBridge(runs_root).dispatch(
        "session_start",
        {
            "run_id": run_id,
            "prompt": prompt,
            "authorization": "inspect",
            "profile": "coding",
            "policy_path": str(recorded_policy),
            "token_mode": "aggressive",
            "max_tokens": 120,
            "language": "en",
        },
    )
    overrides: JsonDict = {
        "profile": "research",
        "policy_path": str(other_policy),
        "token_mode": "balanced",
        "max_tokens": 121,
        "language": "zh",
    }

    with pytest.raises(ValueError, match=override_name):
        ControlBridge(runs_root).dispatch(
            "preflight",
            {
                "run_id": run_id,
                "prompt": prompt,
                override_name: overrides[override_name],
            },
        )


def test_bridge_restart_uses_matching_persisted_configuration_and_policy_hash(
    tmp_path: Path,
) -> None:
    from promptcontrollab.control_bridge import ControlBridge

    runs_root = tmp_path / "runs"
    run_id = "restart-matching"
    prompt = "Inspect the matching persisted bridge configuration."
    policy = tmp_path / "recorded.policy.yaml"
    _write_guard_policy(policy, message="Use the original policy content.")
    settings: JsonDict = {
        "profile": "coding",
        "policy_path": str(policy),
        "token_mode": "aggressive",
        "max_tokens": 120,
        "language": "en",
    }
    ControlBridge(runs_root).dispatch(
        "session_start",
        {
            "run_id": run_id,
            "prompt": prompt,
            "authorization": "inspect",
            **settings,
        },
    )

    result = ControlBridge(runs_root).dispatch(
        "preflight",
        {"run_id": run_id, "prompt": prompt, **settings},
    )
    assert result["improved_prompt"] != "[REDACTED]"

    _write_guard_policy(policy, message="Changed policy content must be rejected.")
    with pytest.raises(ValueError, match="policy_hash"):
        ControlBridge(runs_root).dispatch(
            "preflight",
            {"run_id": run_id, "prompt": prompt},
        )


def test_harness_bridge_supports_pending_prompt_gate_events_status_and_finalize(
    tmp_path: Path,
) -> None:
    from promptcontrollab.control_bridge import ControlBridge
    from promptcontrollab.harness_integration import HARNESS_COMMIT, HARNESS_VERSION

    project = tmp_path / "project"
    runs_root = project / ".promptcontrol" / "runs"
    policy = project / ".promptcontrol" / "guard.policy.yaml"
    policy.parent.mkdir(parents=True)
    policy.write_text(
        "\n".join(
            [
                "profile: coding",
                "block_at: high",
                "review_at: high",
                "rule.deny_shell.severity: high",
                "rule.deny_shell.category: tool_policy",
                "rule.deny_shell.patterns: dangerous-shell",
                "rule.deny_shell.message: This tool requires explicit approval.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    bridge = ControlBridge(runs_root)
    session_id = "harness-session-1"
    start_params: JsonDict = {
        "session_id": session_id,
        "source": "runtime",
        "mode": "gate",
        "authorization": "agent-scoped",
        "policy_path": str(policy),
        "capture": "redacted",
        "provider": "deepseek",
        "model": "deepseek-test",
        "runs_root": str(runs_root),
        "harness_version": HARNESS_VERSION,
        "harness_commit": HARNESS_COMMIT,
        "session_origin": "live_cordis",
        "bridge_transport": "persistent_stdio",
    }
    started = bridge.dispatch("harness_session_start", start_params)
    run_id = str(started["run_id"])
    run_dir = runs_root / run_id
    assert started["status"] == "initialized"
    assert read_json(run_dir / "control_run.json")["prompt_hash"] == "pending:unbound"
    assert not (run_dir / "preflight.json").exists()

    prompt = "Fix failing src/app.py behavior, run pytest, and finish when tests pass."
    pre_step_params: JsonDict = {
        "run_id": run_id,
        "session_id": session_id,
        "turn": 1,
        "step": 1,
        "prompt": prompt,
        "prompt_hash": "sha256:" + stable_digest(prompt),
        "policy_path": str(policy),
        "feedback_max_chars": 80,
    }
    pre_step = bridge.dispatch("harness_pre_step", pre_step_params)
    assert pre_step["decision"] in {"allow", "suggest"}
    assert pre_step["risk_level"] in {"low", "medium", "high", "unknown"}
    assert len(str(pre_step["summary"])) <= 80
    assert pre_step["feedback"] is None or len(str(pre_step["feedback"])) <= 80
    bound_run = read_json(run_dir / "control_run.json")
    assert bound_run["prompt_hash"] == pre_step_params["prompt_hash"]
    assert bound_run["metadata"]["prompt_binding"] == "bound"
    restarted = ControlBridge(runs_root).dispatch("harness_session_start", start_params)
    assert restarted["run_id"] == run_id
    assert read_json(run_dir / "control_run.json")["prompt_hash"] == pre_step_params["prompt_hash"]
    bridge.dispatch("harness_pre_step", pre_step_params)

    changed = "A different prompt must not reuse the bound run."
    with pytest.raises(ValueError, match="bound prompt"):
        bridge.dispatch(
            "harness_pre_step",
            {
                **pre_step_params,
                "prompt": changed,
                "prompt_hash": "sha256:" + stable_digest(changed),
            },
        )

    follow_up = "Inspect this new non-empty Harness turn without reusing turn one."
    follow_up_params: JsonDict = {
        **pre_step_params,
        "turn": 2,
        "prompt": follow_up,
        "prompt_hash": "sha256:" + stable_digest(follow_up),
    }
    second_turn = bridge.dispatch("harness_pre_step", follow_up_params)
    second_turn_retry = bridge.dispatch("harness_pre_step", follow_up_params)
    assert second_turn_retry == second_turn
    assert second_turn["decision"] in {"allow", "suggest"}
    assert read_json(run_dir / "preflight.json")["prompt_hash"] == follow_up_params[
        "prompt_hash"
    ]

    tool_result = bridge.dispatch(
        "harness_tool_pre_execute",
        {
            "run_id": run_id,
            "session_id": session_id,
            "event_id": "tool-event-1",
            "tool": {
                "name": "dangerous-shell",
                "call_id": "call-1",
                "argument_hash": "sha256:arguments",
                "argument_keys": ["command"],
                "arguments": {"command": "RAW-TOOL-ARGUMENT-MUST-NOT-PERSIST"},
            },
            "policy_path": str(policy),
        },
    )
    assert tool_result["decision"] == "deny"
    assert len(str(tool_result["reason"])) <= 600

    event_params: JsonDict = {
        "run_id": run_id,
        "session_id": session_id,
        "idempotency_key": "harness-event-1",
        "event_type": "tools/result",
        "sequence": 1,
        "timestamp": "2026-08-23T00:00:00Z",
        "payload": {
            "tool": {"name": "read", "argument_hash": "sha256:safe"},
            "content": "RAW-EVENT-CONTENT-MUST-NOT-PERSIST",
            "reasoning": "RAW-CHAIN-OF-THOUGHT-MUST-NOT-PERSIST",
            "apiKey": "sk-private-bridge-key-123456",
        },
    }
    first_event = bridge.dispatch("harness_event", event_params)
    duplicate_event = bridge.dispatch("harness_event", event_params)
    assert first_event == {"accepted": True, "duplicate": False}
    assert duplicate_event == {"accepted": False, "duplicate": True}

    turn_end = bridge.dispatch(
        "harness_turn_end",
        {
            "run_id": run_id,
            "session_id": session_id,
            "turn": 1,
            "reason": {"kind": "complete", "content": "RAW-TURN-END"},
            "feedback_max_chars": 80,
        },
    )
    assert turn_end["stability"] in {
        "converging",
        "stalled",
        "oscillating",
        "diverging",
        "insufficient_evidence",
    }
    assert len(str(turn_end["recommendation"])) <= 80
    assert turn_end["recover"] is False

    status = bridge.dispatch(
        "harness_status",
        {"run_id": run_id, "session_id": session_id},
    )
    assert status["run_id"] == run_id
    assert status["risk_level"] in {"low", "medium", "high", "unknown"}
    assert status["report_path"] is None
    with pytest.raises(ValueError, match="session_id"):
        bridge.dispatch(
            "harness_status",
            {"run_id": run_id, "session_id": "different-session"},
        )

    _record_accepted_harness_events(
        bridge,
        run_id=run_id,
        session_id=session_id,
    )
    finalized = bridge.dispatch(
        "harness_finalize",
        {"run_id": run_id, "session_id": session_id},
    )
    assert finalized["status"] == "finalized"
    assert finalized["report_path"] == str((run_dir / "report.md").resolve())
    with pytest.raises(ValueError, match="finalized"):
        bridge.dispatch("harness_pre_step", pre_step_params)
    persisted = "\n".join(
        path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.is_file()
    )
    for secret in (
        prompt,
        follow_up,
        "RAW-TOOL-ARGUMENT-MUST-NOT-PERSIST",
        "RAW-EVENT-CONTENT-MUST-NOT-PERSIST",
        "RAW-CHAIN-OF-THOUGHT-MUST-NOT-PERSIST",
        "RAW-TURN-END",
        "sk-private-bridge-key-123456",
    ):
        assert secret not in persisted


def test_harness_finalized_resume_allocates_one_fresh_idempotent_run(
    tmp_path: Path,
) -> None:
    from promptcontrollab.control_bridge import ControlBridge
    from promptcontrollab.harness_integration import HARNESS_COMMIT, HARNESS_VERSION

    runs_root = tmp_path / "project" / ".promptcontrol" / "runs"
    bridge = ControlBridge(runs_root)
    session_id = "resumed-harness-session"
    start_params: JsonDict = {
        "session_id": session_id,
        "source": "runtime",
        "mode": "suggest",
        "authorization": "agent-scoped",
        "policy_path": None,
        "capture": "redacted",
        "provider": "deepseek",
        "model": "deepseek-test",
        "runs_root": str(runs_root),
        "harness_version": HARNESS_VERSION,
        "harness_commit": HARNESS_COMMIT,
        "session_origin": "live_cordis",
        "bridge_transport": "persistent_stdio",
    }
    first = bridge.dispatch("harness_session_start", start_params)
    first_run_id = str(first["run_id"])
    prompt = "Inspect the first Harness lifecycle before finalization."
    bridge.dispatch(
        "harness_pre_step",
        {
            "run_id": first_run_id,
            "session_id": session_id,
            "turn": 1,
            "step": 1,
            "prompt": prompt,
            "prompt_hash": "sha256:" + stable_digest(prompt),
            "policy_path": None,
            "feedback_max_chars": 100,
        },
    )
    _record_accepted_harness_events(
        bridge,
        run_id=first_run_id,
        session_id=session_id,
    )
    bridge.dispatch(
        "harness_finalize",
        {"run_id": first_run_id, "session_id": session_id},
    )

    resumed = bridge.dispatch("harness_session_start", start_params)
    retry = bridge.dispatch("harness_session_start", start_params)
    restarted_retry = ControlBridge(runs_root).dispatch(
        "harness_session_start",
        start_params,
    )

    resumed_run_id = str(resumed["run_id"])
    assert resumed_run_id == f"{first_run_id}-resume-2"
    assert retry["run_id"] == restarted_retry["run_id"] == resumed_run_id
    assert resumed["status"] == retry["status"] == "initialized"
    resumed_run = read_json(runs_root / resumed_run_id / "control_run.json")
    assert resumed_run["metadata"]["harness_run_ordinal"] == 2
    assert resumed_run["metadata"]["harness_previous_run_id"] == first_run_id
    assert len(read_jsonl(runs_root / resumed_run_id / "events.jsonl")) == 1


def test_harness_auto_recover_requires_config_policy_and_positive_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from promptcontrollab import control_bridge
    from promptcontrollab.control_bridge import ControlBridge
    from promptcontrollab.control_protocol import StabilityReport
    from promptcontrollab.harness_integration import HARNESS_COMMIT, HARNESS_VERSION

    project = tmp_path / "project"
    runs_root = project / ".promptcontrol" / "runs"
    policy = project / ".promptcontrol" / "guard.policy.yaml"
    policy.parent.mkdir(parents=True)
    policy.write_text("harness_auto_recover: true\n", encoding="utf-8")
    bridge = ControlBridge(runs_root)

    def stalled(run: object, _events: object) -> StabilityReport:
        assert isinstance(run, dict)
        return StabilityReport(
            run_id=str(run["run_id"]),
            state="stalled",
            signals={},
            summary="A bounded test stall.",
        )

    monkeypatch.setattr(control_bridge, "analyze_stability", stalled)

    def start_and_assess(
        session_id: str,
        *,
        requested: bool,
        maximum: int,
        policy_path: Path | None = policy,
    ) -> tuple[JsonDict, JsonDict]:
        started = bridge.dispatch(
            "harness_session_start",
            {
                "session_id": session_id,
                "source": "runtime",
                "mode": "suggest",
                "authorization": "agent-scoped",
                "policy_path": str(policy_path) if policy_path is not None else None,
                "capture": "redacted",
                "provider": None,
                "model": None,
                "runs_root": str(runs_root),
                "harness_version": HARNESS_VERSION,
                "harness_commit": HARNESS_COMMIT,
                "auto_recover": requested,
                "max_auto_recoveries": maximum,
            },
        )
        run_id = str(started["run_id"])
        prompt = f"RAW-{session_id}: inspect this recovery policy."
        bridge.dispatch(
            "harness_pre_step",
            {
                "run_id": run_id,
                "session_id": session_id,
                "turn": 1,
                "step": 1,
                "prompt": prompt,
                "prompt_hash": "sha256:" + stable_digest(prompt),
                "policy_path": str(policy_path) if policy_path is not None else None,
                "feedback_max_chars": 100,
            },
        )
        turn_end = bridge.dispatch(
            "harness_turn_end",
            {
                "run_id": run_id,
                "session_id": session_id,
                "turn": 1,
                "reason": {"kind": "turn-stopping"},
                "feedback_max_chars": 100,
            },
        )
        return read_json(runs_root / run_id / "control_run.json"), turn_end

    enabled_run, enabled = start_and_assess(
        "recover-enabled",
        requested=True,
        maximum=2,
    )
    config_off_run, config_off = start_and_assess(
        "recover-config-off",
        requested=False,
        maximum=2,
    )
    policy_off_run, policy_off = start_and_assess(
        "recover-policy-off",
        requested=True,
        maximum=2,
        policy_path=None,
    )
    zero_bound_run, zero_bound = start_and_assess(
        "recover-zero-bound",
        requested=True,
        maximum=0,
    )

    assert enabled_run["metadata"]["harness_auto_recover_requested"] is True
    assert enabled_run["metadata"]["harness_auto_recover_policy"] is True
    assert enabled_run["metadata"]["harness_auto_recover"] is True
    assert enabled_run["metadata"]["harness_max_auto_recoveries"] == 2
    assert enabled["recover"] is True
    assert config_off_run["metadata"]["harness_auto_recover"] is False
    assert config_off["recover"] is False
    assert policy_off_run["metadata"]["harness_auto_recover_policy"] is False
    assert policy_off_run["metadata"]["harness_auto_recover"] is False
    assert policy_off["recover"] is False
    assert zero_bound_run["metadata"]["harness_auto_recover"] is False
    assert zero_bound["recover"] is False


def test_harness_session_start_rejects_mismatched_path_root(tmp_path: Path) -> None:
    from promptcontrollab.control_bridge import ControlBridge
    from promptcontrollab.harness_integration import HARNESS_COMMIT, HARNESS_VERSION

    runs_root = tmp_path / "project" / ".promptcontrol" / "runs"
    bridge = ControlBridge(runs_root)

    with pytest.raises(ValueError, match="runs_root"):
        bridge.dispatch(
            "harness_session_start",
            {
                "session_id": "outside-root",
                "source": "runtime",
                "mode": "suggest",
                "authorization": "agent-scoped",
                "policy_path": None,
                "capture": "redacted",
                "provider": None,
                "model": None,
                "runs_root": str(tmp_path / "outside"),
                "harness_version": HARNESS_VERSION,
                "harness_commit": HARNESS_COMMIT,
            },
        )
    assert not runs_root.exists()


def _write_guard_policy(path: Path, *, message: str) -> None:
    path.write_text(
        "\n".join(
            [
                "profile: coding",
                "block_at: high",
                "review_at: high",
                "rule.recorded.severity: low",
                "rule.recorded.category: audit",
                "rule.recorded.patterns: persisted-configuration",
                f"rule.recorded.message: {message}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
