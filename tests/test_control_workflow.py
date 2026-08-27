from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest

from promptcontrollab.control import control_workflow
from promptcontrollab.control_events import EventLog
from promptcontrollab.control_index import RunIndex
from promptcontrollab.control_protocol import ControlEvent
from promptcontrollab.control_workflow import (
    ControlSession,
    append_control_event,
    finalize_control_session,
    perform_preflight,
    run_control,
    start_control_session,
)
from promptcontrollab.files import JsonDict, read_json, read_jsonl, write_json, write_jsonl


def test_finalize_indexes_only_current_run_when_parent_has_foreign_artifact(
    tmp_path: Path,
) -> None:
    write_json(tmp_path / "foreign" / "control_run.json", {"tool": "not-pcl"})
    run_dir = tmp_path / "current"

    result = run_control(
        prompt="Inspect this request and propose a bounded plan.",
        authorization="inspect",
        run_dir=run_dir,
        run_id="current-run",
        provider=None,
        model=None,
        agent=None,
        profile="general",
        policy_path=None,
        token_mode="balanced",
        max_tokens=None,
        language="auto",
        model_executor=None,
    )

    assert result["decision"]["decision"] == "inspect_only"
    index = RunIndex(tmp_path / ".prompt_control_lab" / "runs.sqlite3")
    assert index.get("current-run") is not None


def test_required_review_never_becomes_ready_for_agent(tmp_path: Path) -> None:
    policy = tmp_path / "guard.policy.yaml"
    policy.write_text(
        "\n".join(
            [
                "profile: coding",
                "block_at: high",
                "review_at: medium",
                "rule.review_zone.severity: medium",
                "rule.review_zone.category: manual_review",
                "rule.review_zone.patterns: review-zone",
                "rule.review_zone.message: A reviewer must approve this target.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    run_dir = tmp_path / "runs" / "review"
    prompt = "Modify review-zone and run the focused tests."
    session = start_control_session(
        run_dir=run_dir,
        prompt=prompt,
        authorization="agent-scoped",
        profile="coding",
        policy_path=policy,
    )
    preflight = perform_preflight(
        session,
        prompt=prompt,
        profile="coding",
        policy_path=policy,
    )
    assert preflight.required_review is True

    finalize_control_session(session)
    decision = read_json(run_dir / "decision.json")
    assert decision["decision"] == "review_required"
    assert "review" in decision["next_action"].lower()


def test_preflight_reconciles_missing_completed_event_after_interruption(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "runs" / "recover"
    prompt = "Inspect this prompt."
    session = start_control_session(
        run_dir=run_dir,
        prompt=prompt,
        authorization="inspect",
    )
    interrupted = perform_preflight(session, prompt=prompt, profile="general")
    events = read_jsonl(run_dir / "events.jsonl")
    write_jsonl(run_dir / "events.jsonl", [events[0]])

    recovered = perform_preflight(session, prompt=prompt, profile="general")
    assert recovered == interrupted
    events = read_jsonl(run_dir / "events.jsonl")
    assert [event["event_type"] for event in events] == [
        "session/start",
        "preflight/completed",
    ]

    perform_preflight(session, prompt=prompt, profile="general")
    assert len(read_jsonl(run_dir / "events.jsonl")) == 2


def test_preflight_returns_improved_prompt_but_persists_only_safe_form(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "runs" / "transport-safe"
    prompt = "ORIGINAL-PROMPT-MUST-NOT-PERSIST: inspect the current behavior."
    session = start_control_session(
        run_dir=run_dir,
        prompt=prompt,
        authorization="agent-scoped",
        profile="coding",
    )

    first = perform_preflight(session, prompt=prompt, profile="coding")
    retry = perform_preflight(session, prompt=prompt, profile="coding")
    assert first.improved_prompt != "[REDACTED]"
    assert retry.improved_prompt == first.improved_prompt
    assert first.to_transport_json()["improved_prompt"] == first.improved_prompt

    persisted_preflight = read_json(run_dir / "preflight.json")
    assert persisted_preflight == first.to_persistence_json()
    assert persisted_preflight["improved_prompt"] == "[REDACTED]"
    assert persisted_preflight["details"]["authorization_scope"] == "agent-scoped"
    events = read_jsonl(run_dir / "events.jsonl")
    assert events[0]["payload"]["authorization_scope"] == "agent-scoped"
    assert "authorization" not in events[0]["payload"]

    finalize_control_session(session)
    original_bytes = prompt.encode()
    improved_bytes = first.improved_prompt.encode()
    for artifact in run_dir.iterdir():
        if artifact.is_file():
            persisted = artifact.read_bytes()
            assert original_bytes not in persisted, artifact.name
            assert improved_bytes not in persisted, artifact.name


def test_harness_preflight_scopes_prompt_identity_to_turn_and_step(
    tmp_path: Path,
) -> None:
    assert hasattr(control_workflow, "perform_harness_preflight")
    run_dir = tmp_path / "runs" / "multi-turn"
    first_prompt = "FIRST-TURN-RAW: inspect the initial request."
    second_prompt = "SECOND-TURN-RAW: inspect the follow-up request."
    session = start_control_session(
        run_dir=run_dir,
        prompt=first_prompt,
        authorization="agent-scoped",
        profile="coding",
    )

    first = control_workflow.perform_harness_preflight(
        session,
        prompt=first_prompt,
        turn=1,
        step=1,
        profile="coding",
    )
    second = control_workflow.perform_harness_preflight(
        session,
        prompt=second_prompt,
        turn=2,
        step=1,
        profile="coding",
    )
    retry = control_workflow.perform_harness_preflight(
        session,
        prompt=second_prompt,
        turn=2,
        step=1,
        profile="coding",
    )

    assert retry == second
    assert first.prompt_hash != second.prompt_hash
    assert read_json(run_dir / "preflight.json")["prompt_hash"] == second.prompt_hash
    assert read_json(run_dir / "preflight.turn-000001.step-000001.json")[
        "prompt_hash"
    ] == first.prompt_hash
    assert read_json(run_dir / "preflight.turn-000002.step-000001.json")[
        "prompt_hash"
    ] == second.prompt_hash
    completed = [
        event
        for event in read_jsonl(run_dir / "events.jsonl")
        if event["event_type"] == "preflight/completed"
    ]
    assert [event["payload"]["turn"] for event in completed] == [1, 2]
    assert len(completed) == 2

    persisted = b"\n".join(
        artifact.read_bytes() for artifact in run_dir.iterdir() if artifact.is_file()
    )
    assert first_prompt.encode() not in persisted
    assert second_prompt.encode() not in persisted


def test_harness_preflight_rejects_changed_interrupted_retry_before_writing(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "runs" / "interrupted-turn"
    prompt = "Inspect the original Harness coordinate."
    session = start_control_session(
        run_dir=run_dir,
        prompt=prompt,
        authorization="agent-scoped",
        profile="coding",
    )
    control_workflow.perform_harness_preflight(
        session,
        prompt=prompt,
        turn=3,
        step=2,
        profile="coding",
    )
    scoped = run_dir / "preflight.turn-000003.step-000002.json"
    scoped.unlink()
    changed = "CHANGED-RAW-PROMPT-MUST-NOT-PERSIST"

    with pytest.raises(ValueError, match="bound prompt"):
        control_workflow.perform_harness_preflight(
            session,
            prompt=changed,
            turn=3,
            step=2,
            profile="coding",
        )

    assert not scoped.exists()
    assert changed.encode() not in (run_dir / "control_run.json").read_bytes()
    assert changed.encode() not in (run_dir / "preflight.json").read_bytes()


def test_harness_preflight_requires_first_coordinate_to_match_initial_binding(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "runs" / "bound-before-preflight"
    bound_prompt = "The prompt was bound before the bridge was interrupted."
    session = start_control_session(
        run_dir=run_dir,
        prompt=bound_prompt,
        authorization="agent-scoped",
        profile="coding",
    )

    with pytest.raises(ValueError, match="bound prompt"):
        control_workflow.perform_harness_preflight(
            session,
            prompt="A changed prompt must not replace the interrupted first coordinate.",
            turn=1,
            step=1,
            profile="coding",
        )

    assert not (run_dir / "preflight.json").exists()
    assert not (run_dir / "preflight.turn-000001.step-000001.json").exists()


def test_session_retry_reuses_auto_generated_run_id(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "auto-id"
    prompt = "Inspect an idempotent generated run id."
    first = start_control_session(
        run_dir=run_dir,
        prompt=prompt,
        authorization="inspect",
        profile="research",
        token_mode="aggressive",
        max_tokens=120,
        language="en",
    )
    retry = start_control_session(
        run_dir=run_dir,
        prompt=prompt,
        authorization="inspect",
        profile="research",
        token_mode="aggressive",
        max_tokens=120,
        language="en",
    )

    assert retry.run.run_id == first.run.run_id
    assert len(read_jsonl(run_dir / "events.jsonl")) == 1


def test_event_append_holds_lifecycle_lock_until_append_completes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _ready_session(tmp_path, "append-first")
    original_append_new = EventLog.append_new
    append_reached = threading.Event()
    release_append = threading.Event()

    def controlled_append_new(
        self: EventLog,
        *,
        event_type: str,
        payload: JsonDict,
        idempotency_key: str | None = None,
        sequence: int | None = None,
        timestamp: str | None = None,
    ) -> tuple[ControlEvent, bool]:
        if event_type == "worker/event":
            append_reached.set()
            if not release_append.wait(timeout=5):
                raise TimeoutError("Test did not release controlled event append")
        return original_append_new(
            self,
            event_type=event_type,
            payload=payload,
            idempotency_key=idempotency_key,
            sequence=sequence,
            timestamp=timestamp,
        )

    monkeypatch.setattr(EventLog, "append_new", controlled_append_new)
    append_errors: list[Exception] = []
    finalize_errors: list[Exception] = []
    finalize_done = threading.Event()

    def append_worker() -> None:
        try:
            append_control_event(
                session,
                event_type="worker/event",
                payload={"status": "before-finalize"},
                idempotency_key="worker-before-finalize",
            )
        except Exception as exc:
            append_errors.append(exc)

    def finalize_worker() -> None:
        try:
            finalize_control_session(session)
        except Exception as exc:
            finalize_errors.append(exc)
        finally:
            finalize_done.set()

    append_thread = threading.Thread(target=append_worker)
    finalize_thread = threading.Thread(target=finalize_worker)
    append_thread.start()
    assert append_reached.wait(timeout=2)
    finalize_thread.start()
    finalized_before_release = finalize_done.wait(timeout=0.25)
    release_append.set()
    append_thread.join(timeout=5)
    finalize_thread.join(timeout=5)

    assert not append_thread.is_alive()
    assert not finalize_thread.is_alive()
    assert finalized_before_release is False
    assert append_errors == []
    assert finalize_errors == []
    event_types = [event["event_type"] for event in read_jsonl(session.run_dir / "events.jsonl")]
    assert event_types[-2:] == ["worker/event", "session/finalized"]


def test_finalize_holds_lifecycle_lock_through_transition_and_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _ready_session(tmp_path, "finalize-first")
    original_write_report = control_workflow._write_report
    finalize_reached = threading.Event()
    release_finalize = threading.Event()

    def controlled_write_report(*args: Any, **kwargs: Any) -> None:
        finalize_reached.set()
        if not release_finalize.wait(timeout=5):
            raise TimeoutError("Test did not release controlled finalization")
        original_write_report(*args, **kwargs)

    monkeypatch.setattr(control_workflow, "_write_report", controlled_write_report)
    append_errors: list[Exception] = []
    finalize_errors: list[Exception] = []
    append_done = threading.Event()

    def finalize_worker() -> None:
        try:
            finalize_control_session(session)
        except Exception as exc:
            finalize_errors.append(exc)

    def append_worker() -> None:
        try:
            append_control_event(
                session,
                event_type="worker/event",
                payload={"status": "too-late"},
                idempotency_key="worker-during-finalize",
            )
        except Exception as exc:
            append_errors.append(exc)
        finally:
            append_done.set()

    finalize_thread = threading.Thread(target=finalize_worker)
    append_thread = threading.Thread(target=append_worker)
    finalize_thread.start()
    assert finalize_reached.wait(timeout=2)
    append_thread.start()
    appended_before_release = append_done.wait(timeout=0.25)
    release_finalize.set()
    finalize_thread.join(timeout=5)
    append_thread.join(timeout=5)

    assert not finalize_thread.is_alive()
    assert not append_thread.is_alive()
    assert appended_before_release is False
    assert finalize_errors == []
    assert len(append_errors) == 1
    assert isinstance(append_errors[0], ValueError)
    assert "finalized" in str(append_errors[0])
    event_types = [event["event_type"] for event in read_jsonl(session.run_dir / "events.jsonl")]
    assert event_types[-1] == "session/finalized"
    assert "worker/event" not in event_types


def _ready_session(tmp_path: Path, name: str) -> ControlSession:
    run_dir = tmp_path / "runs" / name
    prompt = f"Inspect the controlled lifecycle for {name}."
    session = start_control_session(
        run_dir=run_dir,
        prompt=prompt,
        authorization="inspect",
    )
    perform_preflight(session, prompt=prompt, profile="general")
    return session
