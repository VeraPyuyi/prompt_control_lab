from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from promptcontrollab.integrations import harness_integration
from promptcontrollab.integrations.harness_integration import (
    HARNESS_COMMIT,
    HARNESS_VERSION,
    finalize_harness_run,
    initialize_harness_project,
    inspect_harness_session,
    replay_harness_session,
    resolve_harness_report,
    sanitize_harness_event,
)


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def _accepted_harness_events() -> list[tuple[str, dict[str, object]]]:
    return [
        (
            "agent/request",
            {
                "turn": 1,
                "step": 1,
                "request_id": "pcl-request-1",
                "request_id_source": "prompt_control_lab",
                "provider": "deepseek",
                "model": "deepseek-chat",
            },
        ),
        (
            "session/assistant/message",
            {
                "turn": 1,
                "step": 1,
                "response_id": "assistant-message-1",
                "provider": "deepseek",
                "model": "deepseek-chat",
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


def test_harness_init_writes_reviewable_project_files_without_overwrite(
    tmp_path: Path,
) -> None:
    result = initialize_harness_project(tmp_path)

    config = tmp_path / ".promptcontrol" / "deepseek-harness.json"
    snippet = tmp_path / ".promptcontrol" / "deepseek-harness.cordis.yml"
    compatibility = tmp_path / ".promptcontrol" / "deepseek-harness.compatibility.json"
    assert {str(config), str(snippet), str(compatibility)} == set(result["written"])
    payload = json.loads(config.read_text(encoding="utf-8"))
    assert payload["schema"] == "prompt_control_lab.deepseek_harness.config.v1"
    assert payload["mode"] == "suggest"
    assert payload["capture"] == "redacted"
    assert payload["autoRecover"] is False
    assert payload["bridgeFailure"] == "warn"
    snippet_text = snippet.read_text(encoding="utf-8")
    assert snippet_text.startswith("- insert:\n")
    assert "    - id: prompt-control-lab" in snippet_text
    assert "      name: '@prompt-control-lab/deepseek-harness'" in snippet_text
    assert "      runsRoot: .promptcontrol/runs" in snippet_text
    contract = json.loads(compatibility.read_text(encoding="utf-8"))
    assert contract["deepseek_harness"]["version"] == HARNESS_VERSION
    assert contract["deepseek_harness"]["commit"] == HARNESS_COMMIT

    config.write_text("user-owned\n", encoding="utf-8")
    with pytest.raises(ValueError, match="already exists"):
        initialize_harness_project(tmp_path)
    assert config.read_text(encoding="utf-8") == "user-owned\n"


def test_harness_doctor_is_offline_and_checks_local_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialize_harness_project(tmp_path)
    commands: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        assert kwargs["check"] is False
        assert kwargs["timeout"] == 5
        return subprocess.CompletedProcess(command, 0, stdout="v22.19.0\n", stderr="")

    monkeypatch.setattr(
        "promptcontrollab.integrations.harness_integration.shutil.which",
        lambda name: "node.exe",
    )
    monkeypatch.setattr(
        "promptcontrollab.integrations.harness_integration.subprocess.run",
        fake_run,
    )

    result = harness_integration.doctor_harness(tmp_path)

    assert result["status"] == "ok"
    assert result["offline"] is True
    assert set(result["checks"]) == {
        "config",
        "compatibility_lock",
        "python_bridge",
        "node",
        "packaged_plugin",
    }
    assert all(check["status"] == "ok" for check in result["checks"].values())
    assert commands == [["node.exe", "--version"]]


def test_sanitize_harness_event_hashes_content_and_removes_sensitive_reasoning() -> None:
    raw = {
        "seq": 7,
        "type": "assistant/chunk",
        "data": {
            "chunk": {
                "type": "text-delta",
                "text": "private model output",
                "reasoning": "hidden chain of thought",
            },
            "authorization": "Bearer secret-token-value",
            "apiKey": "sk-very-secret-value",
        },
    }

    safe = sanitize_harness_event(raw)
    encoded = json.dumps(safe, ensure_ascii=False)
    assert safe["event_type"] == "assistant/chunk"
    assert safe["sequence"] == 7
    assert safe["payload"]["content_chars"] == len("private model output")
    assert str(safe["payload"]["content_sha256"]).startswith("sha256:")
    assert "private model output" not in encoded
    assert "hidden chain of thought" not in encoded
    assert "secret-token-value" not in encoded
    assert "sk-very-secret-value" not in encoded


def test_sanitize_harness_event_normalizes_private_keys_and_bounds_strings() -> None:
    long_note = "private metadata " * 1_000
    raw = {
        "seq": 8,
        "type": "tool/result",
        "data": {
            "status": "ok",
            "usage": {"inputTokens": 11, "outputTokens": 4},
            "metadata": {
                "label": "safe-label",
                "note": long_note,
                "tags": ["safe-tag", long_note],
                "reasoningContent": "camel-case hidden reasoning",
                "assistantReasoningDelta": "nested assistant reasoning",
                "hiddenThoughts": "hidden thought trace",
                "output_text": "snake-case assistant text",
                "assistantDelta": "streamed assistant text",
                "responseBody": "assistant response body",
                "toolOutput": "camel-case raw tool output",
                "rawPrompt": "camel-case raw user prompt",
                "apiKey": "sk-private-harness-key-123456",
            },
        },
    }

    first = sanitize_harness_event(raw)
    second = sanitize_harness_event(raw)

    assert first == second
    payload = first["payload"]
    metadata = payload["metadata"]
    encoded = json.dumps(first, ensure_ascii=False)
    assert payload["status"] == "ok"
    assert payload["usage"] == {"inputTokens": 11, "outputTokens": 4}
    assert metadata["label"] == "safe-label"
    assert metadata["tags"][0] == "safe-tag"
    assert isinstance(metadata["note"], str)
    assert len(metadata["note"]) <= 256
    assert metadata["tags"][1] == metadata["note"]
    assert "sha256:" in metadata["note"]
    assert metadata["apiKey"] == "[REDACTED]"
    assert "reasoningContent" not in metadata
    assert "assistantReasoningDelta" not in metadata
    assert "hiddenThoughts" not in metadata
    assert "output_text" not in metadata
    assert "assistantDelta" not in metadata
    assert "responseBody" not in metadata
    assert "toolOutput" not in metadata
    assert "rawPrompt" not in metadata
    for private_value in (
        long_note,
        "camel-case hidden reasoning",
        "nested assistant reasoning",
        "hidden thought trace",
        "snake-case assistant text",
        "streamed assistant text",
        "assistant response body",
        "camel-case raw tool output",
        "camel-case raw user prompt",
        "sk-private-harness-key-123456",
    ):
        assert private_value not in encoded


def test_inspect_harness_session_summarizes_observable_signals(tmp_path: Path) -> None:
    session = tmp_path / "session.jsonl"
    _write_jsonl(
        session,
        [
            {"seq": 1, "type": "turn/start", "data": {"turn": 1}},
            {
                "seq": 2,
                "type": "user/message",
                "data": {"content": [{"type": "text", "text": "Fix auth.py"}]},
            },
            {
                "seq": 3,
                "type": "guard/signal",
                "data": {"guard": "repeat-tool-reminder"},
            },
            {"seq": 4, "type": "agent/request-error", "data": {"retry": True}},
            {"seq": 5, "type": "tool/call", "data": {"name": "read"}},
            {"seq": 6, "type": "turn/end", "data": {"turn": 1}},
        ],
    )

    summary = inspect_harness_session(session)

    assert summary["event_count"] == 6
    assert summary["turns"] == 1
    assert summary["tool_calls"] == 1
    assert summary["request_errors"] == 1
    assert summary["guard_signals"] == ["repeat-tool-reminder"]
    assert summary["prompt_hashes"][0].startswith("sha256:")
    assert "Fix auth.py" not in json.dumps(summary)


def test_replay_builds_redacted_control_run_and_report(tmp_path: Path) -> None:
    session = tmp_path / "harness-session.jsonl"
    secret_prompt = "Fix src/auth.py with token sk-sensitive-value and run pytest."
    assistant_text = "PRIVATE-ASSISTANT-TEXT-MUST-NOT-PERSIST"
    tool_output = "PRIVATE-TOOL-OUTPUT-MUST-NOT-PERSIST"
    camel_cot = "PRIVATE-CAMEL-COT-MUST-NOT-PERSIST"
    long_metadata = "PRIVATE-LONG-METADATA-MUST-NOT-PERSIST-" * 500
    _write_jsonl(
        session,
        [
            {
                "seq": 1,
                "type": "session/created",
                "data": {"sessionId": "dsh-session-1", "cwd": str(tmp_path)},
            },
            {
                "seq": 2,
                "type": "user/message",
                "data": {"content": [{"type": "text", "text": secret_prompt}]},
            },
            {
                "seq": 3,
                "type": "request/header",
                "data": {
                    "provider": "deepseek",
                    "model": "deepseek-test",
                    "usage": {"total_tokens": 17},
                },
            },
            {
                "seq": 4,
                "type": "assistant/chunk",
                "data": {
                    "chunk": {
                        "type": "reasoning-delta",
                        "text": "private chain of thought",
                        "reasoningContent": camel_cot,
                        "output_text": assistant_text,
                    }
                },
            },
            {
                "seq": 5,
                "type": "tool/result",
                "data": {
                    "name": "pytest",
                    "status": "ok",
                    "toolOutput": tool_output,
                    "metadata": {"note": long_metadata},
                    "apiKey": "sk-replay-private-key-123456",
                },
            },
            {"seq": 6, "type": "turn/end", "data": {"turn": 1, "reason": "complete"}},
        ],
    )
    run_dir = tmp_path / "runs" / "replayed"

    result = replay_harness_session(session, run_dir=run_dir)

    assert result["run_id"]
    assert (run_dir / "control_run.json").is_file()
    assert (run_dir / "events.jsonl").is_file()
    assert (run_dir / "preflight.json").is_file()
    assert (run_dir / "decision.json").is_file()
    assert (run_dir / "report.md").is_file()
    persisted = "\n".join(
        path.read_text(encoding="utf-8")
        for path in run_dir.rglob("*")
        if path.is_file() and path.suffix in {".json", ".jsonl", ".md", ".html"}
    )
    assert secret_prompt not in persisted
    assert "sk-sensitive-value" not in persisted
    assert "private chain of thought" not in persisted
    assert assistant_text not in persisted
    assert tool_output not in persisted
    assert camel_cot not in persisted
    assert long_metadata not in persisted
    assert "sk-replay-private-key-123456" not in persisted
    control_run = json.loads((run_dir / "control_run.json").read_text(encoding="utf-8"))
    assert control_run["agent"] == "deepseek-harness"
    assert control_run["provider"] == "deepseek"
    assert control_run["model"] == "deepseek-test"
    assert control_run["metadata"]["harness_session_id"] == "dsh-session-1"

    report = resolve_harness_report(tmp_path / "runs", "dsh-session-1")
    assert report["run_dir"] == str(run_dir.resolve())
    assert report["report_md"] == str((run_dir / "report.md").resolve())


def test_harness_finalize_closes_preflightless_external_failure_honestly(
    tmp_path: Path,
) -> None:
    from promptcontrollab.control_bridge import ControlBridge

    runs_root = tmp_path / "runs"
    bridge = ControlBridge(runs_root)
    started = bridge.dispatch(
        "harness_session_start",
        {
            "session_id": "credential-failure-session",
            "source": "startup",
            "mode": "gate",
            "authorization": "agent-scoped",
            "policy_path": None,
            "capture": "redacted",
            "provider": "deepseek-official",
            "model": "deepseek-v4-flash",
            "runs_root": str(runs_root),
            "harness_version": HARNESS_VERSION,
            "harness_commit": HARNESS_COMMIT,
            "session_origin": "live_cordis",
            "bridge_transport": "persistent_stdio",
        },
    )


    result = finalize_harness_run(
        runs_root,
        "credential-failure-session",
        outcome="failed",
        exit_code=1,
    )

    run_dir = runs_root / str(started["run_id"])
    assert result["status"] == "finalized"
    assert result["termination"]["outcome"] == "failed"
    assert result["termination"]["preflight_observed"] is False
    assert not (run_dir / "preflight.json").exists()
    decision = json.loads((run_dir / "decision.json").read_text(encoding="utf-8"))
    assert decision["decision"] == "insufficient_evidence"
    assert "preflight" in decision["reasons"][0].lower()
    report = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "not_observed" in report
    persisted = (run_dir / "harness_termination.json").read_text(encoding="utf-8")
    assert "credential" not in persisted.lower()

    repeated = finalize_harness_run(
        runs_root,
        str(started["run_id"]),
        outcome="failed",
        exit_code=1,
    )
    assert repeated["status"] == "finalized"
    assert repeated["event_count"] == result["event_count"]


def test_completed_harness_run_requires_a_real_model_tool_and_test_chain(
    tmp_path: Path,
) -> None:
    from promptcontrollab.control_bridge import ControlBridge
    from promptcontrollab.files import stable_digest

    runs_root = tmp_path / "runs"
    bridge = ControlBridge(runs_root)
    started = bridge.dispatch(
        "harness_session_start",
        {
            "session_id": "incomplete-live-session",
            "source": "runtime",
            "mode": "suggest",
            "authorization": "agent-scoped",
            "policy_path": None,
            "capture": "redacted",
            "provider": "deepseek",
            "model": "deepseek-chat",
            "runs_root": str(runs_root),
            "harness_version": HARNESS_VERSION,
            "harness_commit": HARNESS_COMMIT,
            "session_origin": "live_cordis",
            "bridge_transport": "persistent_stdio",
        },
    )
    prompt = "Update one fixture and run its test."
    bridge.dispatch(
        "harness_pre_step",
        {
            "run_id": started["run_id"],
            "session_id": "incomplete-live-session",
            "turn": 1,
            "step": 1,
            "prompt": prompt,
            "prompt_hash": "sha256:" + stable_digest(prompt),
            "policy_path": None,
            "feedback_max_chars": 600,
        },
    )

    with pytest.raises(
        ValueError,
        match="model response, file read, file modification, successful test execution",
    ):
        finalize_harness_run(
            runs_root,
            "incomplete-live-session",
            outcome="completed",
            exit_code=0,
        )

    run_dir = runs_root / str(started["run_id"])
    acceptance = json.loads((run_dir / "harness_acceptance.json").read_text(encoding="utf-8"))
    assert acceptance["accepted"] is False
    assert acceptance["checks"]["preflight"]["passed"] is True
    assert acceptance["checks"]["model_response"]["passed"] is False
    assert json.loads((run_dir / "control_run.json").read_text())["status"] != "finalized"


def test_completed_harness_run_writes_machine_verified_acceptance(tmp_path: Path) -> None:
    from promptcontrollab.control_bridge import ControlBridge
    from promptcontrollab.files import stable_digest

    runs_root = tmp_path / "runs"
    bridge = ControlBridge(runs_root)
    started = bridge.dispatch(
        "harness_session_start",
        {
            "session_id": "accepted-live-session",
            "source": "runtime",
            "mode": "suggest",
            "authorization": "agent-scoped",
            "policy_path": None,
            "capture": "redacted",
            "provider": "deepseek",
            "model": "deepseek-chat",
            "runs_root": str(runs_root),
            "harness_version": HARNESS_VERSION,
            "harness_commit": HARNESS_COMMIT,
            "session_origin": "live_cordis",
            "bridge_transport": "persistent_stdio",
        },
    )
    prompt = "Update one fixture and run its test."
    bridge.dispatch(
        "harness_pre_step",
        {
            "run_id": started["run_id"],
            "session_id": "accepted-live-session",
            "turn": 1,
            "step": 1,
            "prompt": prompt,
            "prompt_hash": "sha256:" + stable_digest(prompt),
            "policy_path": None,
            "feedback_max_chars": 600,
        },
    )
    run_dir = runs_root / str(started["run_id"])
    events = _accepted_harness_events()
    for index, (event_type, payload) in enumerate(events, 1):
        bridge.dispatch(
            "harness_event",
            {
                "run_id": started["run_id"],
                "session_id": "accepted-live-session",
                "idempotency_key": f"acceptance-{index}",
                "event_type": event_type,
                "sequence": index,
                "timestamp": "2026-08-24T00:00:00Z",
                "payload": payload,
            },
        )

    result = finalize_harness_run(
        runs_root,
        "accepted-live-session",
        outcome="completed",
        exit_code=0,
    )

    assert result["status"] == "finalized"
    assert result["acceptance"]["accepted"] is True
    acceptance = json.loads((run_dir / "harness_acceptance.json").read_text(encoding="utf-8"))
    assert all(check["passed"] for check in acceptance["checks"].values())


@pytest.mark.parametrize(
    "test_result",
    [
        {"is_error": False, "exit_code": 1},
        {"is_error": False},
    ],
    ids=["nonzero-exit", "missing-exit"],
)
def test_completed_harness_run_rejects_unverified_test_result(
    tmp_path: Path,
    test_result: dict[str, object],
) -> None:
    from promptcontrollab.control_bridge import ControlBridge
    from promptcontrollab.files import stable_digest

    runs_root = tmp_path / "runs"
    bridge = ControlBridge(runs_root)
    started = bridge.dispatch(
        "harness_session_start",
        {
            "session_id": "failed-test-live-session",
            "source": "runtime",
            "mode": "suggest",
            "authorization": "agent-scoped",
            "policy_path": None,
            "capture": "redacted",
            "provider": "deepseek",
            "model": "deepseek-chat",
            "runs_root": str(runs_root),
            "harness_version": HARNESS_VERSION,
            "harness_commit": HARNESS_COMMIT,
            "session_origin": "live_cordis",
            "bridge_transport": "persistent_stdio",
        },
    )
    prompt = "Update one fixture and run its test."
    bridge.dispatch(
        "harness_pre_step",
        {
            "run_id": started["run_id"],
            "session_id": "failed-test-live-session",
            "turn": 1,
            "step": 1,
            "prompt": prompt,
            "prompt_hash": "sha256:" + stable_digest(prompt),
            "policy_path": None,
            "feedback_max_chars": 600,
        },
    )
    events = _accepted_harness_events()
    events[-1] = (
        "tools/result",
        {
            "tool": {"operation_category": "test_execution"},
            "result": test_result,
        },
    )
    for index, (event_type, payload) in enumerate(events, 1):
        bridge.dispatch(
            "harness_event",
            {
                "run_id": started["run_id"],
                "session_id": "failed-test-live-session",
                "idempotency_key": f"failed-test-{index}",
                "event_type": event_type,
                "sequence": index,
                "timestamp": "2026-08-25T00:00:00Z",
                "payload": payload,
            },
        )

    with pytest.raises(ValueError, match="successful test execution"):
        finalize_harness_run(
            runs_root,
            "failed-test-live-session",
            outcome="completed",
            exit_code=0,
        )

    run_dir = runs_root / str(started["run_id"])
    acceptance = json.loads((run_dir / "harness_acceptance.json").read_text())
    assert acceptance["checks"]["test"]["passed"] is False


def test_direct_fixture_events_cannot_satisfy_live_harness_acceptance(
    tmp_path: Path,
) -> None:
    from promptcontrollab.control_bridge import ControlBridge
    from promptcontrollab.control_workflow import append_control_event, load_control_session
    from promptcontrollab.files import stable_digest

    runs_root = tmp_path / "runs"
    bridge = ControlBridge(runs_root)
    started = bridge.dispatch(
        "harness_session_start",
        {
            "session_id": "fixture-session",
            "source": "fixture",
            "mode": "suggest",
            "authorization": "agent-scoped",
            "policy_path": None,
            "capture": "redacted",
            "provider": "deepseek",
            "model": "deepseek-chat",
            "runs_root": str(runs_root),
            "harness_version": HARNESS_VERSION,
            "harness_commit": HARNESS_COMMIT,
        },
    )
    prompt = "Update one fixture and run its test."
    bridge.dispatch(
        "harness_pre_step",
        {
            "run_id": started["run_id"],
            "session_id": "fixture-session",
            "turn": 1,
            "step": 1,
            "prompt": prompt,
            "prompt_hash": "sha256:" + stable_digest(prompt),
            "policy_path": None,
            "feedback_max_chars": 600,
        },
    )
    run_dir = runs_root / str(started["run_id"])
    session = load_control_session(run_dir)
    for index, (event_type, payload) in enumerate(_accepted_harness_events(), 1):
        append_control_event(
            session,
            event_type=event_type,
            payload=payload,
            idempotency_key=f"fixture-{index}",
        )

    with pytest.raises(ValueError, match="matching preflight/request evidence"):
        finalize_harness_run(
            runs_root,
            "fixture-session",
            outcome="completed",
            exit_code=0,
        )
    acceptance = json.loads((run_dir / "harness_acceptance.json").read_text())
    assert acceptance["accepted"] is False
    assert acceptance["checks"]["native_bridge"]["passed"] is False


def test_bridge_capture_does_not_persist_private_event_content(tmp_path: Path) -> None:
    from promptcontrollab.control_bridge import ControlBridge

    runs_root = tmp_path / "runs"
    bridge = ControlBridge(runs_root)
    started = bridge.dispatch(
        "harness_session_start",
        {
            "session_id": "privacy-session",
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
        },
    )
    private_values = {
        "raw prompt": "BRIDGE-RAW-PROMPT-MUST-NOT-PERSIST",
        "assistant text": "BRIDGE-ASSISTANT-TEXT-MUST-NOT-PERSIST",
        "tool output": "BRIDGE-TOOL-OUTPUT-MUST-NOT-PERSIST",
        "chain of thought": "BRIDGE-COT-MUST-NOT-PERSIST",
        "api key": "sk-bridge-private-key-123456",
        "long metadata": "BRIDGE-LONG-METADATA-MUST-NOT-PERSIST-" * 500,
    }

    bridge.dispatch(
        "harness_event",
        {
            "run_id": started["run_id"],
            "session_id": "privacy-session",
            "idempotency_key": "privacy-event-1",
            "event_type": "tools/result",
            "sequence": 1,
            "timestamp": "2026-08-23T00:00:00Z",
            "payload": {
                "status": "ok",
                "rawPrompt": private_values["raw prompt"],
                "output_text": private_values["assistant text"],
                "toolOutput": private_values["tool output"],
                "reasoningContent": private_values["chain of thought"],
                "apiKey": private_values["api key"],
                "metadata": {"note": private_values["long metadata"]},
            },
        },
    )

    run_dir = runs_root / str(started["run_id"])
    persisted = "\n".join(
        path.read_text(encoding="utf-8")
        for path in run_dir.rglob("*")
        if path.is_file() and path.suffix in {".json", ".jsonl", ".md", ".html"}
    )
    for private_value in private_values.values():
        assert private_value not in persisted
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
    assert events[-1]["payload"]["status"] == "ok"


def test_replay_requires_a_user_prompt_for_honest_preflight(tmp_path: Path) -> None:
    session = tmp_path / "no-prompt.jsonl"
    _write_jsonl(session, [{"seq": 1, "type": "turn/start", "data": {"turn": 1}}])

    with pytest.raises(ValueError, match="user prompt"):
        replay_harness_session(session, run_dir=tmp_path / "runs" / "missing")
