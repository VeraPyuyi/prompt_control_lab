"""Local control-run lifecycle shared by the CLI and bridge."""

from __future__ import annotations

import html
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

from promptcontrollab.control_analysis import (
    analyze_attribution,
    analyze_stability,
    make_control_decision,
)
from promptcontrollab.control_events import EventLog, run_lifecycle_lock
from promptcontrollab.control_index import RunIndex
from promptcontrollab.control_protocol import (
    AttributionReport,
    ControlDecision,
    ControlEvent,
    ControlRun,
    PreflightDecision,
    StabilityReport,
    redact_sensitive,
    utc_now,
)
from promptcontrollab.files import JsonDict, ensure_dir, read_json, stable_digest, write_json
from promptcontrollab.prompt_context import empty_prompt_context
from promptcontrollab.prompt_guard import guard_prompt

AUTHORIZATIONS = ("inspect", "model", "agent-scoped", "agent-full")
PENDING_PROMPT_HASH = "pending:unbound"
_HIDDEN_REASONING_KEYS = {
    "chain_of_thought",
    "chainofthought",
    "cot",
    "hidden_reasoning",
    "reasoning",
    "reasoning_content",
    "thinking",
    "thought",
    "thoughts",
}


@dataclass(frozen=True)
class ControlSession:
    """Filesystem-backed state for one local control run."""

    run_dir: Path
    run: ControlRun

    @property
    def events(self) -> EventLog:
        return EventLog(self.run_dir / "events.jsonl", run_id=self.run.run_id)


def start_control_session(
    *,
    run_dir: Path,
    prompt: str | None,
    authorization: str,
    run_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    agent: str | None = None,
    profile: str = "general",
    policy_path: Path | None = None,
    capture_mode: str = "redacted",
    token_mode: str = "balanced",
    max_tokens: int | None = None,
    language: str = "auto",
    extra_metadata: JsonDict | None = None,
) -> ControlSession:
    """Create a new session without executing a provider or agent."""

    _validate_authorization(authorization)
    prompt_hash = PENDING_PROMPT_HASH if prompt is None else "sha256:" + stable_digest(prompt)
    metadata = _session_metadata(
        profile=profile,
        policy_path=policy_path,
        capture_mode=capture_mode,
        token_mode=token_mode,
        max_tokens=max_tokens,
        language=language,
    )
    if extra_metadata:
        safe_extra = redact_sensitive(extra_metadata)
        assert isinstance(safe_extra, dict)
        metadata.update(cast(JsonDict, safe_extra))
    run_path = run_dir / "control_run.json"
    if run_path.exists():
        existing = ControlRun.from_json(read_json(run_path))
        _validate_session_retry(
            existing,
            requested_run_id=run_id,
            authorization=authorization,
            prompt_hash=prompt_hash,
            provider=provider,
            model=model,
            agent=agent,
            metadata=metadata,
        )
        session = ControlSession(run_dir=run_dir, run=existing)
        _ensure_session_start_event(session)
        return session

    ensure_dir(run_dir)
    resolved_id = run_id or _new_run_id(prompt_hash)
    run = ControlRun.create(
        run_id=resolved_id,
        authorization=authorization,
        prompt_hash=prompt_hash,
        provider=provider,
        model=model,
        agent=agent,
        metadata=metadata,
    )
    write_json(run_path, run.to_json())
    session = ControlSession(run_dir=run_dir, run=run)
    _ensure_session_start_event(session)
    return session


def bind_control_prompt(
    session: ControlSession,
    *,
    prompt: str,
    prompt_hash: str | None = None,
) -> ControlSession:
    """Bind an unbound session to its first transport-only prompt exactly once."""

    calculated = "sha256:" + stable_digest(prompt)
    if prompt_hash is not None and prompt_hash != calculated:
        msg = "Supplied prompt_hash does not match the transport prompt"
        raise ValueError(msg)
    with run_lifecycle_lock(session.run_dir):
        current = ControlRun.from_json(read_json(session.run_dir / "control_run.json"))
        if current.status == "finalized":
            msg = f"Control run `{current.run_id}` is finalized; prompt cannot be bound"
            raise ValueError(msg)
        if current.prompt_hash == calculated:
            return ControlSession(session.run_dir, current)
        if current.prompt_hash != PENDING_PROMPT_HASH:
            msg = "Harness pre-step prompt does not match the already bound prompt"
            raise ValueError(msg)
        metadata = dict(current.metadata)
        if metadata.get("prompt_binding") == "pending":
            metadata["prompt_binding"] = "bound"
        bound = replace(current, prompt_hash=calculated, metadata=metadata)
        write_json(session.run_dir / "control_run.json", bound.to_json())
        bound_session = ControlSession(session.run_dir, bound)
        bound_session.events.append_new(
            event_type="session/prompt-bound",
            payload={"prompt_hash": calculated, "capture_mode": "redacted"},
            idempotency_key="session-prompt-bound",
        )
        return bound_session


def load_control_session(run_dir: Path) -> ControlSession:
    """Load a session from its JSON source of truth."""

    path = run_dir / "control_run.json"
    if not path.exists():
        msg = f"Missing control run artifact: {path}"
        raise ValueError(msg)
    return ControlSession(run_dir=run_dir, run=ControlRun.from_json(read_json(path)))


def perform_preflight(
    session: ControlSession,
    *,
    prompt: str,
    profile: str,
    policy_path: Path | None = None,
    token_mode: str = "balanced",
    max_tokens: int | None = None,
    language: str = "auto",
) -> PreflightDecision:
    """Run the existing guard and persist a versioned preflight decision."""

    prompt_hash = "sha256:" + stable_digest(prompt)
    if prompt_hash != session.run.prompt_hash:
        msg = "Preflight prompt does not match the recorded prompt hash"
        raise ValueError(msg)
    path = session.run_dir / "preflight.json"
    existing: PreflightDecision | None = None
    if path.exists():
        existing = PreflightDecision.from_persistence_json(read_json(path))
        if existing.run_id != session.run.run_id:
            msg = "Persisted preflight run_id does not match the control run"
            raise ValueError(msg)
        if existing.prompt_hash and existing.prompt_hash != prompt_hash:
            msg = "Persisted preflight prompt hash does not match the control run"
            raise ValueError(msg)
    decision = _build_preflight_decision(
        session,
        prompt=prompt,
        profile=profile,
        policy_path=policy_path,
        token_mode=token_mode,
        max_tokens=max_tokens,
        language=language,
    )
    if existing is not None:
        if existing.to_persistence_json() != decision.to_persistence_json():
            msg = "Persisted preflight decision does not match the recomputed decision"
            raise ValueError(msg)
        _ensure_preflight_event(session, decision)
        return decision
    write_json(path, decision.to_persistence_json())
    _ensure_preflight_event(session, decision)
    return decision


def perform_harness_preflight(
    session: ControlSession,
    *,
    prompt: str,
    turn: int,
    step: int,
    profile: str,
    policy_path: Path | None = None,
    token_mode: str = "balanced",
    max_tokens: int | None = None,
    language: str = "auto",
) -> PreflightDecision:
    """Persist one idempotent, redacted preflight per Harness turn and step."""

    if (
        not isinstance(turn, int)
        or isinstance(turn, bool)
        or turn < 0
        or not isinstance(step, int)
        or isinstance(step, bool)
        or step < 0
    ):
        raise ValueError("Harness preflight turn and step must be non-negative integers")
    prompt_hash = "sha256:" + stable_digest(prompt)
    artifact = session.run_dir / f"preflight.turn-{turn:06d}.step-{step:06d}.json"
    current = ControlRun.from_json(read_json(session.run_dir / "control_run.json"))
    if current.status == "finalized":
        msg = f"Control run `{current.run_id}` is finalized; preflight cannot run"
        raise ValueError(msg)
    decision = _build_preflight_decision(
        ControlSession(session.run_dir, current),
        prompt=prompt,
        profile=profile,
        policy_path=policy_path,
        token_mode=token_mode,
        max_tokens=max_tokens,
        language=language,
    )
    position = (turn, step)

    with run_lifecycle_lock(session.run_dir):
        current = ControlRun.from_json(read_json(session.run_dir / "control_run.json"))
        if current.status == "finalized":
            msg = f"Control run `{current.run_id}` is finalized; preflight cannot run"
            raise ValueError(msg)
        metadata = dict(current.metadata)
        last = _harness_preflight_state(metadata.get("harness_last_pre_step"))
        last_position = (last[0], last[1]) if last is not None else None
        if last is None and current.prompt_hash != prompt_hash:
            msg = "Harness pre-step does not match the initially bound prompt"
            raise ValueError(msg)
        if last is not None and last_position == position and last[2] != prompt_hash:
            msg = "Harness pre-step does not match the bound prompt for this turn and step"
            raise ValueError(msg)

        existing: PreflightDecision | None = None
        if artifact.exists():
            existing = PreflightDecision.from_persistence_json(read_json(artifact))
            if existing.run_id != current.run_id:
                msg = "Persisted Harness preflight run_id does not match the control run"
                raise ValueError(msg)
            if existing.prompt_hash != prompt_hash:
                msg = "Harness pre-step does not match the bound prompt for this turn and step"
                raise ValueError(msg)
            if existing.to_persistence_json() != decision.to_persistence_json():
                msg = "Persisted Harness preflight does not match the recomputed decision"
                raise ValueError(msg)
        else:
            write_json(artifact, decision.to_persistence_json())

        if last_position is None or position >= last_position:
            metadata["harness_last_pre_step"] = {
                "turn": turn,
                "step": step,
                "prompt_hash": prompt_hash,
            }
            current = replace(current, metadata=metadata)
            write_json(session.run_dir / "control_run.json", current.to_json())
            write_json(session.run_dir / "preflight.json", decision.to_persistence_json())

        ControlSession(session.run_dir, current).events.append_new(
            event_type="preflight/completed",
            payload={
                "decision": decision.decision,
                "risk_level": decision.risk_level,
                "required_review": decision.required_review,
                "prompt_hash": prompt_hash,
                "improved_prompt_hash": decision.improved_prompt_hash,
                "capture_mode": decision.capture_mode,
                "turn": turn,
                "step": step,
            },
            idempotency_key=f"preflight-completed:turn-{turn}:step-{step}",
        )
    return decision


def append_control_event(
    session: ControlSession,
    *,
    event_type: str,
    payload: JsonDict,
    sequence: int | None = None,
    timestamp: str | None = None,
    idempotency_key: str | None = None,
) -> tuple[ControlEvent, bool]:
    """Create and append one event, returning whether it was newly written."""

    with run_lifecycle_lock(session.run_dir):
        current = ControlRun.from_json(read_json(session.run_dir / "control_run.json"))
        if current.status == "finalized":
            msg = f"Control run `{current.run_id}` is finalized; events cannot be appended"
            raise ValueError(msg)
        return session.events.append_new(
            event_type=event_type,
            timestamp=timestamp,
            payload=payload,
            idempotency_key=idempotency_key,
            sequence=sequence,
        )


def control_status(session: ControlSession) -> JsonDict:
    """Return a compact status derived only from local artifacts."""

    run = ControlRun.from_json(read_json(session.run_dir / "control_run.json"))
    artifacts = sorted(path.name for path in session.run_dir.iterdir() if path.is_file())
    return {
        "run_id": run.run_id,
        "run_dir": str(session.run_dir.resolve()),
        "status": run.status,
        "authorization": run.authorization,
        "event_count": len(session.events.read()),
        "artifacts": artifacts,
    }


def finalize_control_session(session: ControlSession) -> JsonDict:
    """Write diagnostic skeletons and mark a local session finalized."""

    with run_lifecycle_lock(session.run_dir):
        return _finalize_control_session_locked(session)


def _finalize_control_session_locked(session: ControlSession) -> JsonDict:
    current = ControlRun.from_json(read_json(session.run_dir / "control_run.json"))
    if current.status == "finalized":
        return control_status(ControlSession(session.run_dir, current))
    preflight_path = session.run_dir / "preflight.json"
    if not preflight_path.exists():
        msg = "Run preflight before finalizing the control session"
        raise ValueError(msg)
    preflight = PreflightDecision.from_persistence_json(read_json(preflight_path))
    events = session.events.read()
    execution_evidence = _has_execution_evidence(events)
    if execution_evidence:
        event_payloads = [event.to_json() for event in events]
        attribution = analyze_attribution(current.to_json(), event_payloads)
        stability = analyze_stability(current.to_json(), event_payloads)
        decision = make_control_decision(
            current.to_json(),
            preflight=preflight,
            attribution=attribution,
            stability=stability,
            events=event_payloads,
        )
    else:
        attribution = AttributionReport(
            run_id=current.run_id,
            status="insufficient_evidence",
            factors=[],
            summary="No provider or agent execution evidence is available.",
        )
        stability = StabilityReport(
            run_id=current.run_id,
            state="insufficient_evidence",
            signals={"observed_events": len(events)},
            summary="A preflight-only run does not contain enough trajectory evidence.",
        )
        decision = _final_decision(current, preflight)
    write_json(session.run_dir / "attribution.json", attribution.to_json())
    write_json(session.run_dir / "stability.json", stability.to_json())
    write_json(session.run_dir / "decision.json", decision.to_json())
    _write_report(
        session.run_dir,
        current,
        preflight,
        attribution,
        stability,
        decision,
        execution_evidence=execution_evidence,
    )
    session.events.append_new(
        event_type="session/finalized",
        payload={"decision": decision.decision},
        idempotency_key="session-finalized",
    )
    finalized = replace(current, status="finalized")
    write_json(session.run_dir / "control_run.json", finalized.to_json())
    _index_control_run(session.run_dir)
    return control_status(ControlSession(session.run_dir, finalized))


def run_control(
    *,
    prompt: str,
    authorization: str,
    run_dir: Path,
    run_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    agent: str | None = None,
    profile: str = "general",
    policy_path: Path | None = None,
    token_mode: str = "balanced",
    max_tokens: int | None = None,
    language: str = "auto",
    model_executor: Callable[..., object] | None = None,
) -> JsonDict:
    """Run preflight and an explicitly authorized model call when configured."""

    if authorization == "model" and (
        provider is None
        or not provider.strip()
        or model is None
        or not model.strip()
    ):
        msg = "Model authorization requires both --provider and --model."
        raise ValueError(msg)

    session = start_control_session(
        run_dir=run_dir,
        prompt=prompt,
        authorization=authorization,
        run_id=run_id,
        provider=provider,
        model=model,
        agent=agent,
        profile=profile,
        policy_path=policy_path,
        token_mode=token_mode,
        max_tokens=max_tokens,
        language=language,
    )
    preflight = perform_preflight(
        session,
        prompt=prompt,
        profile=profile,
        policy_path=policy_path,
        token_mode=token_mode,
        max_tokens=max_tokens,
        language=language,
    )
    if (
        authorization == "model"
        and not _preflight_blocks_execution(preflight)
        and model_executor is not None
        and not (run_dir / "provider_result.json").exists()
    ):
        assert provider is not None
        assert model is not None
        response = model_executor(provider=provider, model=model, prompt=prompt)
        record_provider_execution(
            session,
            response=response,
            requested_model=model,
        )
    status = finalize_control_session(session)
    return {
        **status,
        "preflight": preflight.to_transport_json(),
        "decision": read_json(run_dir / "decision.json"),
    }


def record_provider_execution(
    session: ControlSession,
    *,
    response: object,
    requested_model: str,
) -> JsonDict:
    """Persist one normalized provider result and its redacted execution events."""

    payload = _normalized_provider_result(response, requested_model=requested_model)
    with run_lifecycle_lock(session.run_dir):
        current = ControlRun.from_json(read_json(session.run_dir / "control_run.json"))
        if current.status == "finalized":
            msg = f"Control run `{current.run_id}` is finalized; provider result cannot be recorded"
            raise ValueError(msg)
        write_json(session.run_dir / "provider_result.json", payload)
        session.events.append_new(
            event_type="agent/request",
            payload={
                "provider": payload["provider"],
                "model": requested_model,
                "prompt_hash": current.prompt_hash,
                "request_sha256": payload["request_sha256"],
            },
            idempotency_key="provider-request",
        )
        session.events.append_new(
            event_type="agent/response",
            payload={
                "provider": payload["provider"],
                "model": payload["model_id"],
                "request_id": payload["request_id"],
                "usage": payload["usage"],
                "latency_ms": payload["latency_ms"],
                "request_sha256": payload["request_sha256"],
                "response_sha256": payload["response_sha256"],
                "output_sha256": payload["response_sha256"],
                "output_chars": len(str(payload["output_text"])),
                "provenance_evidence": payload["provenance_evidence"],
                "warnings": payload["warnings"],
            },
            idempotency_key="provider-response",
        )
    return payload


def _normalized_provider_result(response: object, *, requested_model: str) -> JsonDict:
    to_json = getattr(response, "to_json", None)
    raw = to_json() if callable(to_json) else response
    if not isinstance(raw, Mapping):
        msg = "Provider execution did not return a normalized object"
        raise ValueError(msg)
    provider = _result_string(raw, "provider")
    model_id = _result_string(raw, "model_id")
    output_text = _result_string(raw, "output_text")
    request_id_value = raw.get("request_id")
    if request_id_value is not None and not isinstance(request_id_value, str):
        msg = "Normalized provider field `request_id` must be a string or null"
        raise ValueError(msg)
    latency = raw.get("latency_ms")
    if not isinstance(latency, int | float) or isinstance(latency, bool):
        msg = "Normalized provider field `latency_ms` must be numeric"
        raise ValueError(msg)
    usage = _safe_mapping(raw.get("usage", {}), "usage")
    provenance = _safe_mapping_list(raw.get("provenance_evidence", []), "provenance_evidence")
    metadata = _safe_mapping(raw.get("raw_metadata", {}), "raw_metadata")
    warnings_value = raw.get("warnings", [])
    if not isinstance(warnings_value, list) or not all(
        isinstance(item, str) for item in warnings_value
    ):
        msg = "Normalized provider field `warnings` must be a string list"
        raise ValueError(msg)
    safe_output = redact_sensitive(output_text)
    assert isinstance(safe_output, str)
    return {
        "schema": "prompt_control_lab.provider_result.v1",
        "provider": provider,
        "requested_model": requested_model,
        "model_id": model_id,
        "output_text": safe_output,
        "request_id": request_id_value,
        "usage": usage,
        "latency_ms": float(latency),
        "request_sha256": _result_string(raw, "request_sha256"),
        "response_sha256": _result_string(raw, "response_sha256"),
        "provenance_evidence": provenance,
        "raw_metadata": metadata,
        "warnings": [cast(str, redact_sensitive(item)) for item in warnings_value],
    }


def _build_preflight_decision(
    session: ControlSession,
    *,
    prompt: str,
    profile: str,
    policy_path: Path | None,
    token_mode: str,
    max_tokens: int | None,
    language: str,
) -> PreflightDecision:
    prompt_hash = "sha256:" + stable_digest(prompt)
    guard_mode = "suggest" if session.run.authorization == "inspect" else "gate"
    guard = guard_prompt(
        prompt,
        context=empty_prompt_context(),
        mode=guard_mode,
        profile=profile,
        token_mode=token_mode,
        max_tokens=max_tokens,
        language=language,
        policy_path=policy_path,
    )
    guard_payload = guard.to_json()
    guard_payload.pop("original_prompt", None)
    guard_payload.pop("improved_prompt", None)
    return PreflightDecision(
        run_id=session.run.run_id,
        decision=guard.action,
        risk_level=guard.risk_level,
        required_review=guard.required_review,
        summary=guard.plain_summary,
        improved_prompt=guard.improved_prompt,
        prompt_hash=prompt_hash,
        improved_prompt_hash="sha256:" + stable_digest(guard.improved_prompt),
        capture_mode=str(session.run.metadata.get("capture_mode", "redacted")),
        details={
            "authorization_scope": session.run.authorization,
            "guard": guard_payload,
        },
    )


def _harness_preflight_state(value: object) -> tuple[int, int, str] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("Persisted harness_last_pre_step must be an object")
    turn = value.get("turn")
    step = value.get("step")
    prompt_hash = value.get("prompt_hash")
    if (
        not isinstance(turn, int)
        or isinstance(turn, bool)
        or turn < 0
        or not isinstance(step, int)
        or isinstance(step, bool)
        or step < 0
        or not isinstance(prompt_hash, str)
        or not prompt_hash
    ):
        raise ValueError("Persisted harness_last_pre_step is invalid")
    return turn, step, prompt_hash


def _result_string(value: Mapping[object, object], name: str) -> str:
    item = value.get(name)
    if not isinstance(item, str) or not item:
        msg = f"Normalized provider field `{name}` must be a non-empty string"
        raise ValueError(msg)
    safe = redact_sensitive(item)
    assert isinstance(safe, str)
    return safe


def _safe_mapping(value: object, name: str) -> JsonDict:
    if not isinstance(value, Mapping):
        msg = f"Normalized provider field `{name}` must be an object"
        raise ValueError(msg)
    safe: JsonDict = {}
    for raw_key, item in value.items():
        key = str(raw_key)
        normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
        if normalized in _HIDDEN_REASONING_KEYS:
            continue
        safe[key] = _safe_public_value(item)
    return cast(JsonDict, redact_sensitive(safe))


def _safe_mapping_list(value: object, name: str) -> list[JsonDict]:
    if not isinstance(value, list):
        msg = f"Normalized provider field `{name}` must be a list"
        raise ValueError(msg)
    return [_safe_mapping(item, name) for item in value]


def _safe_public_value(value: object) -> object:
    if isinstance(value, Mapping):
        return _safe_mapping(value, "metadata")
    if isinstance(value, list):
        return [_safe_public_value(item) for item in value]
    return redact_sensitive(value)


def _preflight_blocks_execution(preflight: PreflightDecision) -> bool:
    return preflight.decision == "block" or preflight.required_review


def preview_guard(
    prompt: str,
    *,
    profile: str,
    policy_path: Path | None,
    token_mode: str,
    max_tokens: int | None,
    language: str,
) -> JsonDict:
    """Return a non-persisting guard preview used before interactive authorization."""

    return guard_prompt(
        prompt,
        context=empty_prompt_context(),
        mode="suggest",
        profile=profile,
        token_mode=token_mode,
        max_tokens=max_tokens,
        language=language,
        policy_path=policy_path,
    ).to_json()


def _final_decision(run: ControlRun, preflight: PreflightDecision) -> ControlDecision:
    if preflight.decision == "block":
        return ControlDecision(
            run_id=run.run_id,
            decision="blocked",
            next_action="Revise the prompt or obtain the required review before execution.",
            reasons=[preflight.summary],
        )
    if preflight.required_review:
        return ControlDecision(
            run_id=run.run_id,
            decision="review_required",
            next_action="Record explicit reviewer approval before any model or agent execution.",
            reasons=[preflight.summary],
        )
    if run.authorization == "model":
        return ControlDecision(
            run_id=run.run_id,
            decision="not_implemented",
            next_action="Use inspect mode until a provider adapter is available.",
            reasons=["Provider execution is not implemented in Task 1."],
        )
    if run.authorization == "inspect":
        return ControlDecision(
            run_id=run.run_id,
            decision="inspect_only",
            next_action="Review or copy the improved prompt; no execution was attempted.",
            reasons=[preflight.summary],
        )
    return ControlDecision(
        run_id=run.run_id,
        decision="ready_for_agent",
        next_action="Pass the preflight decision to an explicit agent adapter.",
        reasons=["Task 1 performs preflight only and does not launch an agent."],
    )


def _has_execution_evidence(events: list[ControlEvent]) -> bool:
    prefixes = ("agent/", "tools/", "tool/", "test/", "step/", "task/", "harness/")
    return any(event.event_type.startswith(prefixes) for event in events)


def _write_report(
    run_dir: Path,
    run: ControlRun,
    preflight: PreflightDecision,
    attribution: AttributionReport,
    stability: StabilityReport,
    decision: ControlDecision,
    *,
    execution_evidence: bool,
) -> None:
    evidence_note = (
        "Attribution and stability use recorded public execution metadata only."
        if execution_evidence
        else "No provider or agent execution was attempted by this preflight-only run."
    )
    markdown = "\n".join(
        [
            "# PromptControlLab Control Run",
            "",
            f"- Run: `{run.run_id}`",
            f"- Authorization: `{run.authorization}`",
            f"- Preflight: `{preflight.decision}` ({preflight.risk_level})",
            f"- Attribution: `{attribution.status}`",
            f"- Stability: `{stability.state}`",
            f"- Decision: `{decision.decision}`",
            "",
            "## Next Action",
            "",
            decision.next_action,
            "",
            evidence_note,
            "",
        ]
    )
    (run_dir / "report.md").write_text(markdown, encoding="utf-8")
    report_html = "\n".join(
        [
            "<!doctype html>",
            '<html lang="en"><head><meta charset="utf-8">',
            "<title>PromptControlLab Control Run</title></head><body>",
            "<main><h1>PromptControlLab Control Run</h1>",
            f"<p><strong>Run:</strong> <code>{html.escape(run.run_id)}</code></p>",
            f"<p><strong>Decision:</strong> {html.escape(decision.decision)}</p>",
            f"<p><strong>Next action:</strong> {html.escape(decision.next_action)}</p>",
            f"<p>{html.escape(evidence_note)}</p>",
            "</main></body></html>\n",
        ]
    )
    (run_dir / "report.html").write_text(report_html, encoding="utf-8")


def _index_control_run(run_dir: Path) -> None:
    index_path = run_dir.parent / ".prompt_control_lab" / "runs.sqlite3"
    RunIndex(index_path).index_run(run_dir)


def _session_metadata(
    *,
    profile: str,
    policy_path: Path | None,
    capture_mode: str,
    token_mode: str,
    max_tokens: int | None,
    language: str,
) -> JsonDict:
    if capture_mode != "redacted":
        msg = "Task 1 persists only redacted prompt capture"
        raise ValueError(msg)
    metadata: JsonDict = {
        "profile": profile,
        "capture_mode": capture_mode,
        "token_mode": token_mode,
        "max_tokens": max_tokens,
        "language": language,
    }
    if policy_path is not None:
        resolved_policy = policy_path.resolve()
        metadata["policy_path"] = str(resolved_policy)
        if resolved_policy.exists():
            metadata["policy_hash"] = "sha256:" + stable_digest(
                resolved_policy.read_text(encoding="utf-8-sig")
            )
    return metadata


def _validate_session_retry(
    existing: ControlRun,
    *,
    requested_run_id: str | None,
    authorization: str,
    prompt_hash: str,
    provider: str | None,
    model: str | None,
    agent: str | None,
    metadata: JsonDict,
) -> None:
    existing_metadata = dict(existing.metadata)
    existing_metadata.setdefault("capture_mode", "redacted")
    requested = (
        requested_run_id or existing.run_id,
        authorization,
        prompt_hash,
        provider,
        model,
        agent,
        metadata,
    )
    recorded = (
        existing.run_id,
        existing.authorization,
        existing.prompt_hash,
        existing.provider,
        existing.model,
        existing.agent,
        existing_metadata,
    )
    if requested != recorded:
        msg = f"Session start conflicts with existing control run `{existing.run_id}`"
        raise ValueError(msg)


def _ensure_session_start_event(session: ControlSession) -> None:
    _ensure_lifecycle_event(
        session,
        event_type="session/start",
        payload={
            "authorization_scope": session.run.authorization,
            "prompt_hash": session.run.prompt_hash,
            "provider": session.run.provider,
            "model": session.run.model,
            "agent": session.run.agent,
            "capture_mode": session.run.metadata.get("capture_mode", "redacted"),
        },
        idempotency_key="session-start",
    )


def _ensure_preflight_event(
    session: ControlSession,
    decision: PreflightDecision,
) -> None:
    _ensure_lifecycle_event(
        session,
        event_type="preflight/completed",
        payload={
            "decision": decision.decision,
            "risk_level": decision.risk_level,
            "required_review": decision.required_review,
            "prompt_hash": decision.prompt_hash or session.run.prompt_hash,
            "improved_prompt_hash": decision.improved_prompt_hash,
            "capture_mode": decision.capture_mode,
        },
        idempotency_key="preflight-completed",
    )


def _ensure_lifecycle_event(
    session: ControlSession,
    *,
    event_type: str,
    payload: JsonDict,
    idempotency_key: str,
) -> None:
    with run_lifecycle_lock(session.run_dir):
        existing = session.events.read()
        if any(event.idempotency_key == idempotency_key for event in existing):
            session.events.append_new(
                event_type=event_type,
                payload=payload,
                idempotency_key=idempotency_key,
            )
            return
        current = ControlRun.from_json(read_json(session.run_dir / "control_run.json"))
        if current.status == "finalized":
            msg = f"Control run `{current.run_id}` is finalized; events cannot be appended"
            raise ValueError(msg)
        session.events.append_new(
            event_type=event_type,
            payload=payload,
            idempotency_key=idempotency_key,
        )


def _validate_authorization(authorization: str) -> None:
    if authorization not in AUTHORIZATIONS:
        msg = f"Authorization must be one of: {', '.join(AUTHORIZATIONS)}"
        raise ValueError(msg)


def _new_run_id(prompt_hash: str) -> str:
    stamp = utc_now().replace("-", "").replace(":", "").replace(".", "")
    return f"control-{stamp}-{stable_digest(prompt_hash)[:8]}"
