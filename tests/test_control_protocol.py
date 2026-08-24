from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path

import pytest


def test_control_schemas_round_trip_and_redact_sensitive_fields() -> None:
    from promptcontrollab.control_protocol import (
        AttributionReport,
        ControlDecision,
        ControlEvent,
        ControlRun,
        PreflightDecision,
        StabilityReport,
    )

    run = ControlRun.create(
        run_id="run-001",
        authorization="agent-scoped",
        prompt_hash="sha256:prompt",
        provider="deepseek",
        model="deepseek-test",
        agent="deepseek-harness",
        metadata={
            "api_key": "should-not-leak",
            "usage": {"input_tokens": 12},
            "headers": {"Authorization": "Bearer should-not-leak"},
        },
    )
    run_json = run.to_json()
    assert run_json["schema"] == "prompt_control_lab.control_run.v1"
    assert run_json["metadata"]["api_key"] == "[REDACTED]"
    assert run_json["metadata"]["headers"]["Authorization"] == "[REDACTED]"
    assert run_json["metadata"]["usage"]["input_tokens"] == 12
    assert ControlRun.from_json(run_json) == ControlRun.from_json(
        ControlRun.from_json(run_json).to_json()
    )

    event = ControlEvent.create(
        run_id=run.run_id,
        sequence=1,
        event_type="agent/request",
        timestamp="2026-08-23T00:00:01Z",
        payload={"access_token": "secret", "token_count": 8},
    )
    assert event.to_json()["payload"] == {
        "access_token": "[REDACTED]",
        "token_count": 8,
    }
    assert ControlEvent.from_json(event.to_json()) == event

    preflight = PreflightDecision(
        run_id=run.run_id,
        decision="suggest",
        risk_level="medium",
        required_review=True,
        summary="Add a test plan.",
        improved_prompt="Fix the bug and run tests.",
        details={"password": "secret"},
    )
    attribution = AttributionReport(
        run_id=run.run_id,
        status="insufficient_evidence",
        factors=[],
        summary="No completed execution is available.",
    )
    stability = StabilityReport(
        run_id=run.run_id,
        state="insufficient_evidence",
        signals={},
        summary="No trajectory is available.",
    )
    decision = ControlDecision(
        run_id=run.run_id,
        decision="review",
        next_action="Review the preflight result.",
        reasons=["The prompt needs review."],
    )
    persistence_json = preflight.to_persistence_json()
    transport_json = preflight.to_transport_json()
    persisted_preflight = PreflightDecision.from_persistence_json(persistence_json)
    assert preflight.improved_prompt == "Fix the bug and run tests."
    assert transport_json["improved_prompt"] == preflight.improved_prompt
    assert persistence_json["improved_prompt"] == "[REDACTED]"
    assert preflight.improved_prompt not in json.dumps(persistence_json, sort_keys=True)
    assert persisted_preflight.improved_prompt == "[REDACTED]"
    assert persisted_preflight.to_persistence_json() == persistence_json
    assert preflight.to_json() == persistence_json
    assert AttributionReport.from_json(attribution.to_json()) == attribution
    assert StabilityReport.from_json(stability.to_json()) == stability
    assert ControlDecision.from_json(decision.to_json()) == decision
    assert persistence_json["details"]["password"] == "[REDACTED]"
    assert transport_json["details"]["password"] == "[REDACTED]"


def test_redaction_normalizes_provider_credentials_but_keeps_usage_fields() -> None:
    from promptcontrollab.control_protocol import redact_sensitive

    payload = {
        "OPENAI_API_KEY": "openai-secret",
        "x-api-key": "provider-secret",
        "ToKeN": "bearer-secret",
        "credentials": {"client": "secret"},
        "nested": {"AWS_SECRET_ACCESS_KEY": "aws-secret"},
        "accessToken": "camel-access-secret",
        "refreshToken": "camel-refresh-secret",
        "clientSecret": "camel-client-secret",
        "apiKeys": ["plural-api-secret"],
        "clientSecrets": ["plural-client-secret"],
        "privateKeys": ["plural-private-secret"],
        "passwords": ["plural-password-secret"],
        "access_tokens": ["plural-access-secret"],
        "refresh_tokens": ["plural-refresh-secret"],
        "session_tokens": ["generic-token-secret"],
        "token_count": 23,
        "input_tokens": 11,
        "output_tokens": 12,
        "total_tokens": 23,
        "cached_tokens": 4,
        "reasoning_tokens": 2,
        "prompt_tokens": 11,
        "completion_tokens": 12,
        "max_tokens": 100,
        "token_usage": {"cached_tokens": 4},
        "usage": {"total_tokens": 23},
    }
    redacted = redact_sensitive(payload)
    assert redacted["OPENAI_API_KEY"] == "[REDACTED]"
    assert redacted["x-api-key"] == "[REDACTED]"
    assert redacted["ToKeN"] == "[REDACTED]"
    assert redacted["credentials"] == "[REDACTED]"
    assert redacted["nested"]["AWS_SECRET_ACCESS_KEY"] == "[REDACTED]"
    assert redacted["accessToken"] == "[REDACTED]"
    assert redacted["refreshToken"] == "[REDACTED]"
    assert redacted["clientSecret"] == "[REDACTED]"
    assert redacted["apiKeys"] == "[REDACTED]"
    assert redacted["clientSecrets"] == "[REDACTED]"
    assert redacted["privateKeys"] == "[REDACTED]"
    assert redacted["passwords"] == "[REDACTED]"
    assert redacted["access_tokens"] == "[REDACTED]"
    assert redacted["refresh_tokens"] == "[REDACTED]"
    assert redacted["session_tokens"] == "[REDACTED]"
    assert redacted["token_count"] == 23
    assert redacted["input_tokens"] == 11
    assert redacted["output_tokens"] == 12
    assert redacted["total_tokens"] == 23
    assert redacted["cached_tokens"] == 4
    assert redacted["reasoning_tokens"] == 2
    assert redacted["prompt_tokens"] == 11
    assert redacted["completion_tokens"] == 12
    assert redacted["max_tokens"] == 100
    assert redacted["token_usage"] == {"cached_tokens": 4}
    assert redacted["usage"] == {"total_tokens": 23}


def test_redaction_scrubs_secret_values_inside_external_strings() -> None:
    from promptcontrollab.control_protocol import redact_sensitive

    bearer = "bearer-secret-1234567890"
    api_key = "sk-project-super-secret-1234567890"
    password = "correct-horse-battery-staple"
    provider_key = "provider-secret-1234567890"
    access_token = "camel-access-secret-1234567890"
    client_secrets = "camel-client-secret-1234567890"
    generic_token = "generic-token-secret-1234567890"
    embedded_json_key = "json-provider-secret-1234567890"
    private_key = "-----BEGIN PRIVATE KEY-----\nvery-secret-bytes\n-----END PRIVATE KEY-----"
    ordinary = "Use token_count and token_usage to explain ordinary request usage."
    redacted = redact_sensitive(
        {
            "message": (
                f"Authorization: Bearer {bearer}; api_key={api_key}; password={password}"
            ),
            "certificate_note": private_key,
            "configuration": (
                f"OPENAI_API_KEY={provider_key}; accessToken={access_token}; "
                f"clientSecrets={client_secrets}; token={generic_token}; "
                f'\"api_key\": \"{embedded_json_key}\"'
            ),
            "ordinary": ordinary,
        }
    )

    persisted = json.dumps(redacted, sort_keys=True)
    for secret in (
        bearer,
        api_key,
        password,
        provider_key,
        access_token,
        client_secrets,
        generic_token,
        embedded_json_key,
        "very-secret-bytes",
    ):
        assert secret not in persisted
    assert "Bearer [REDACTED]" in redacted["message"]
    assert "api_key=[REDACTED]" in redacted["message"]
    assert "password=[REDACTED]" in redacted["message"]
    assert redacted["certificate_note"] == "[REDACTED PRIVATE KEY]"
    assert redacted["ordinary"] == ordinary


def test_control_event_from_json_rejects_noncanonical_event_id() -> None:
    from promptcontrollab.control_protocol import ControlEvent

    event = ControlEvent.create(
        run_id="run-001",
        sequence=1,
        event_type="session/start",
        timestamp="2026-08-23T00:00:01Z",
        payload={"status": "ok"},
    )
    tampered = event.to_json()
    tampered["payload"] = {"status": "changed"}
    with pytest.raises(ValueError, match="event_id does not match canonical content"):
        ControlEvent.from_json(tampered)


def test_control_event_idempotency_key_excludes_server_sequence_and_timestamp() -> None:
    from promptcontrollab.control_protocol import ControlEvent

    first = ControlEvent.create(
        run_id="run-001",
        sequence=2,
        event_type="tools/post-execute",
        timestamp="2026-08-23T00:00:02Z",
        payload={"tool": "pytest"},
        idempotency_key="harness-tool-event-42",
    )
    retry = ControlEvent.create(
        run_id="run-001",
        sequence=9,
        event_type="tools/post-execute",
        timestamp="2026-08-23T00:01:00Z",
        payload={"tool": "pytest"},
        idempotency_key="harness-tool-event-42",
    )
    assert first.event_id == retry.event_id
    assert ControlEvent.from_json(first.to_json()) == first


def test_event_log_is_append_only_sequence_checked_and_idempotent(tmp_path: Path) -> None:
    from promptcontrollab.control_events import EventLog
    from promptcontrollab.control_protocol import ControlEvent

    log = EventLog(tmp_path / "events.jsonl", run_id="run-001")
    first = ControlEvent.create(
        run_id="run-001",
        sequence=1,
        event_type="session/start",
        timestamp="2026-08-23T00:00:01Z",
        payload={"agent": "fixture"},
    )
    second = ControlEvent.create(
        run_id="run-001",
        sequence=2,
        event_type="agent/pre-step",
        timestamp="2026-08-23T00:00:02Z",
        payload={"decision": "allow"},
    )

    assert log.append(first) is True
    assert log.append(first) is False
    assert log.replay([first, second]) == 1
    assert [item.sequence for item in log.read()] == [1, 2]

    gap = ControlEvent.create(
        run_id="run-001",
        sequence=4,
        event_type="turn/end",
        timestamp="2026-08-23T00:00:04Z",
        payload={},
    )
    with pytest.raises(ValueError, match="expected sequence 3"):
        log.append(gap)

    conflicting = ControlEvent(
        run_id=first.run_id,
        event_id=first.event_id,
        sequence=first.sequence,
        event_type=first.event_type,
        timestamp=first.timestamp,
        payload={"agent": "different"},
    )
    with pytest.raises(ValueError, match="conflicts with an existing event"):
        log.append(conflicting)

    lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert all(isinstance(json.loads(line), dict) for line in lines)


def test_event_log_rejects_reused_idempotency_key_with_changed_content(tmp_path: Path) -> None:
    from promptcontrollab.control_events import EventLog
    from promptcontrollab.control_protocol import ControlEvent

    log = EventLog(tmp_path / "events.jsonl", run_id="run-001")
    first = ControlEvent.create(
        run_id="run-001",
        sequence=1,
        event_type="tools/post-execute",
        payload={"result": "pass"},
        idempotency_key="tool-event-1",
    )
    changed = ControlEvent.create(
        run_id="run-001",
        sequence=2,
        event_type="tools/post-execute",
        payload={"result": "fail"},
        idempotency_key="tool-event-1",
    )
    assert log.append(first) is True
    with pytest.raises(ValueError, match="Idempotency key `tool-event-1` was reused"):
        log.append(changed)


def test_event_log_serializes_concurrent_cross_process_appends(tmp_path: Path) -> None:
    from promptcontrollab.control_events import EventLog

    root = Path(__file__).resolve().parents[1]
    event_path = tmp_path / "events.jsonl"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(root / "src")
    code = """
import sys
from pathlib import Path
from promptcontrollab.control_events import EventLog

path = Path(sys.argv[1])
key = sys.argv[2]
EventLog(path, run_id="concurrent-run").append_new(
    event_type="worker/event",
    payload={"worker": key},
    idempotency_key=key,
)
"""
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", code, str(event_path), f"worker-{number}"],
            cwd=root,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for number in range(8)
    ]
    failures: list[str] = []
    for process in processes:
        _, stderr = process.communicate(timeout=20)
        if process.returncode != 0:
            failures.append(stderr)
    assert failures == []

    events = EventLog(event_path, run_id="concurrent-run").read()
    assert [event.sequence for event in events] == list(range(1, 9))
    assert {event.idempotency_key for event in events} == {
        f"worker-{number}" for number in range(8)
    }


def test_event_log_retries_transient_windows_lock_permission_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import promptcontrollab.control_events as control_events

    real_open = os.open
    calls = 0

    def transient_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
    ) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise PermissionError(13, "simulated Windows lock contention", str(path))
        return int(real_open(path, flags))

    monkeypatch.setattr(os, "open", transient_open)
    log = control_events.EventLog(tmp_path / "events.jsonl", run_id="run")

    _, appended = log.append_new(event_type="test/event", payload={"ok": True})

    assert appended is True
    assert calls >= 2


def test_event_log_bounds_persistent_windows_lock_permission_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import promptcontrollab.control_events as control_events

    def denied_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
    ) -> int:
        raise PermissionError(13, "simulated permanent permission denial", str(path))

    monkeypatch.setattr(os, "open", denied_open)
    log = control_events.EventLog(
        tmp_path / "events.jsonl",
        run_id="run",
        lock_timeout=0.02,
    )

    with pytest.raises(TimeoutError, match="Timed out acquiring event log lock"):
        log.append_new(event_type="test/event", payload={"ok": True})


def test_event_log_recovers_a_stale_sibling_lock(tmp_path: Path) -> None:
    from promptcontrollab.control_events import EventLog

    event_path = tmp_path / "events.jsonl"
    lock_path = tmp_path / "events.jsonl.lock"
    lock_path.write_text("abandoned", encoding="utf-8")
    stale_time = time.time() - 60
    os.utime(lock_path, (stale_time, stale_time))

    log = EventLog(
        event_path,
        run_id="run-001",
        lock_timeout=1.0,
        stale_after=0.1,
    )
    event, appended = log.append_new(
        event_type="session/event",
        payload={"status": "ok"},
        idempotency_key="stale-lock-event",
    )
    assert appended is True
    assert event.sequence == 1
    assert not lock_path.exists()


def test_sqlite_index_rebuilds_from_json_artifacts(tmp_path: Path) -> None:
    from promptcontrollab.control_index import RunIndex
    from promptcontrollab.control_protocol import ControlDecision, ControlRun, StabilityReport
    from promptcontrollab.files import write_json

    runs_dir = tmp_path / "runs"
    run_dir = runs_dir / "run-001"
    write_json(
        run_dir / "control_run.json",
        ControlRun.create(
            run_id="run-001",
            authorization="inspect",
            prompt_hash="sha256:prompt",
            provider="deepseek",
            model="fixture-model",
            agent="deepseek-harness",
        ).to_json(),
    )
    write_json(
        run_dir / "stability.json",
        StabilityReport(
            run_id="run-001",
            state="stalled",
            signals={"repeated_tool_calls": 3},
            summary="The run stalled.",
        ).to_json(),
    )
    write_json(
        run_dir / "decision.json",
        ControlDecision(
            run_id="run-001",
            decision="review",
            next_action="Inspect repeated tool calls.",
            reasons=["The run stalled."],
        ).to_json(),
    )
    (run_dir / "events.jsonl").write_text(
        '{"event_id":"event-1"}\n{"event_id":"event-2"}\n',
        encoding="utf-8",
    )

    database = tmp_path / "control-index.sqlite3"
    index = RunIndex(database)
    assert index.rebuild(runs_dir) == 1
    record = index.get("run-001")
    assert record is not None
    assert record["run_dir"] == str(run_dir.resolve())
    assert record["authorization"] == "inspect"
    assert record["provider"] == "deepseek"
    assert record["stability_state"] == "stalled"
    assert record["decision"] == "review"
    assert record["event_count"] == 2

    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("UPDATE runs SET decision = 'tampered' WHERE run_id = 'run-001'")
        connection.commit()
    assert index.rebuild(runs_dir) == 1
    assert index.get("run-001")["decision"] == "review"  # type: ignore[index]
    database.unlink()
    assert not database.exists()
