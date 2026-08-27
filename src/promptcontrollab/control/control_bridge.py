"""Dependency-free persistent JSON-RPC bridge over line-delimited stdio."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO, cast

from promptcontrollab.control.control_analysis import analyze_stability, make_control_decision
from promptcontrollab.control.control_index import RunIndex
from promptcontrollab.control.control_workflow import (
    ControlSession,
    append_control_event,
    bind_control_prompt,
    control_status,
    finalize_control_session,
    load_control_session,
    perform_harness_preflight,
    perform_preflight,
    start_control_session,
)
from promptcontrollab.core.config import read_simple_yaml
from promptcontrollab.core.files import JsonDict, read_json, stable_digest
from promptcontrollab.preflight.prompt_context import empty_prompt_context
from promptcontrollab.preflight.prompt_guard import guard_prompt

BRIDGE_PROTOCOL = "prompt_control_lab.bridge.v1"


class MethodNotFoundError(ValueError):
    """Raised when a JSON-RPC method is unknown."""


class InvalidRequestError(ValueError):
    """Raised when a JSON-RPC envelope is structurally invalid."""


class InvalidParamsError(ValueError):
    """Raised when method parameters do not satisfy the bridge contract."""


@dataclass
class _BridgeSession:
    session: ControlSession
    prompt: str | None
    profile: str
    policy_path: Path | None
    token_mode: str
    max_tokens: int | None
    language: str
    harness_session_id: str | None = None
    harness_mode: str | None = None


class ControlBridge:
    """Dispatch persistent bridge calls into the local control workflow."""

    def __init__(self, runs_root: Path) -> None:
        self.runs_root = runs_root.resolve()
        self._sessions: dict[str, _BridgeSession] = {}
        self._index = RunIndex(
            self.runs_root / ".prompt_control_lab" / "runs.sqlite3"
        )

    def dispatch(self, method: str, params: JsonDict) -> JsonDict:
        """Dispatch one versioned bridge request to its local handler.

        Args:
            method: JSON-RPC method name exposed by the bridge.
            params: Redacted method parameters.

        Returns:
            A JSON-compatible bridge response.

        Raises:
            ValueError: If the method or its parameters are unsupported.
        """

        if method == "health":
            return {"status": "ok", "protocol": BRIDGE_PROTOCOL}
        if method == "harness_session_start":
            return self._harness_session_start(params)
        if method == "harness_pre_step":
            return self._harness_pre_step(params)
        if method == "harness_tool_pre_execute":
            return self._harness_tool_pre_execute(params)
        if method == "harness_event":
            return self._harness_event(params)
        if method == "harness_turn_end":
            return self._harness_turn_end(params)
        if method == "harness_status":
            return self._harness_status(params)
        if method == "harness_finalize":
            return self._harness_finalize(params)
        if method == "session_start":
            return self._session_start(params)
        if method == "preflight":
            context = self._context(_required_string(params, "run_id"), params)
            if context.prompt is None:
                raise ValueError("Bridge preflight requires a bound prompt")
            decision = perform_preflight(
                context.session,
                prompt=context.prompt,
                profile=context.profile,
                policy_path=context.policy_path,
                token_mode=context.token_mode,
                max_tokens=context.max_tokens,
                language=context.language,
            )
            self._index.index_run(context.session.run_dir)
            return decision.to_transport_json()
        if method == "event_append":
            session = self._session(_required_string(params, "run_id"))
            payload = params.get("payload", {})
            if not isinstance(payload, dict):
                msg = "Bridge event payload must be an object"
                raise ValueError(msg)
            event, appended = append_control_event(
                session,
                event_type=_required_string(params, "event_type"),
                payload=cast(JsonDict, payload),
                sequence=_optional_int(params.get("sequence"), "sequence"),
                timestamp=_optional_string(params.get("timestamp"), "timestamp"),
                idempotency_key=_required_string(params, "idempotency_key"),
            )
            self._index.index_run(session.run_dir)
            return {"appended": appended, "event": event.to_json()}
        if method == "status":
            return control_status(self._session(_required_string(params, "run_id")))
        if method == "finalize":
            session = self._session(_required_string(params, "run_id"))
            result = finalize_control_session(session)
            self._index.index_run(session.run_dir)
            return result
        raise MethodNotFoundError(f"Unknown bridge method: {method}")

    def _harness_session_start(self, params: JsonDict) -> JsonDict:
        """Create a controlled Harness session after validating its safety contract."""

        from promptcontrollab.harness_integration import HARNESS_COMMIT, HARNESS_VERSION

        session_id = _required_string(params, "session_id")
        source = _required_string(params, "source")
        mode = _required_choice(params, "mode", {"suggest", "gate"})
        authorization = _required_string(params, "authorization")
        if authorization != "agent-scoped":
            raise ValueError("Harness authorization must be `agent-scoped`")
        capture = _required_string(params, "capture")
        if capture != "redacted":
            raise ValueError("Harness capture must be `redacted`")
        supplied_root = Path(_required_string(params, "runs_root")).resolve()
        if supplied_root != self.runs_root:
            msg = f"Harness runs_root must match bridge runs root `{self.runs_root}`"
            raise ValueError(msg)
        if _required_string(params, "harness_version") != HARNESS_VERSION:
            raise ValueError("Harness version does not match the packaged compatibility lock")
        if _required_string(params, "harness_commit") != HARNESS_COMMIT:
            raise ValueError("Harness commit does not match the packaged compatibility lock")
        policy_path = self._resolve_harness_policy_path(params.get("policy_path"))
        auto_recover_requested = _optional_bool(
            params.get("auto_recover"),
            "auto_recover",
            default=False,
        )
        max_auto_recoveries = _nonnegative_int(
            params.get("max_auto_recoveries"),
            "max_auto_recoveries",
            default=1,
        )
        auto_recover_policy = _policy_allows_recovery(policy_path)
        auto_recover = (
            auto_recover_requested and auto_recover_policy and max_auto_recoveries > 0
        )
        base_run_id = f"harness-{stable_digest(session_id)[:20]}"
        run_id, run_ordinal, previous_run_id = self._harness_start_run(base_run_id, session_id)
        run_dir = self._resolve_run_dir(None, run_id=run_id)
        self._validate_run_binding(run_id, run_dir)
        provider = _optional_string(params.get("provider"), "provider")
        model = _optional_string(params.get("model"), "model")
        session_origin = _optional_string(params.get("session_origin"), "session_origin")
        bridge_transport = _optional_string(
            params.get("bridge_transport"), "bridge_transport"
        )
        extra_metadata: JsonDict = {
            "harness_session_id": session_id,
            "harness_source": source,
            "harness_mode": mode,
            "harness_version": HARNESS_VERSION,
            "harness_commit": HARNESS_COMMIT,
            "harness_run_ordinal": run_ordinal,
            "harness_previous_run_id": previous_run_id,
            "prompt_binding": "pending",
            "harness_auto_recover_requested": auto_recover_requested,
            "harness_auto_recover_policy": auto_recover_policy,
            "harness_auto_recover": auto_recover,
            "harness_max_auto_recoveries": max_auto_recoveries,
            "harness_session_origin": session_origin or "unverified",
            "harness_bridge_transport": bridge_transport or "unverified",
        }
        if (run_dir / "control_run.json").exists():
            session = load_control_session(run_dir)
            _validate_harness_start_retry(
                session,
                provider=provider,
                model=model,
                policy_path=policy_path,
                extra_metadata=extra_metadata,
            )
        else:
            session = start_control_session(
                run_dir=run_dir,
                prompt=None,
                authorization=authorization,
                run_id=run_id,
                provider=provider,
                model=model,
                agent="deepseek-harness",
                profile="coding",
                policy_path=policy_path,
                capture_mode="redacted",
                extra_metadata=extra_metadata,
            )
        self._sessions[run_id] = _BridgeSession(
            session=session,
            prompt=None,
            profile="coding",
            policy_path=policy_path,
            token_mode="balanced",
            max_tokens=None,
            language="auto",
            harness_session_id=session_id,
            harness_mode=mode,
        )
        _validate_policy_hash(self._sessions[run_id])
        self._index.index_run(run_dir)
        return {"run_id": run_id, "status": session.run.status}

    def _harness_pre_step(self, params: JsonDict) -> JsonDict:
        """Apply prompt preflight before a Harness model step is allowed to run."""

        run_id = _required_string(params, "run_id")
        session_id = _required_string(params, "session_id")
        context = self._harness_context(run_id, session_id)
        turn = _required_int(params, "turn")
        step = _required_int(params, "step")
        feedback_limit = _bounded_limit(params.get("feedback_max_chars"))
        prompt = _required_string(params, "prompt")
        prompt_hash = _required_string(params, "prompt_hash")
        if prompt_hash != "sha256:" + stable_digest(prompt):
            raise ValueError("Supplied prompt_hash does not match the transport prompt")
        self._validate_harness_policy(context, params)
        current = load_control_session(context.session.run_dir)
        if current.run.prompt_hash in {"pending:unbound", prompt_hash}:
            current = bind_control_prompt(
                current,
                prompt=prompt,
                prompt_hash=prompt_hash,
            )
        context.session = current
        context.prompt = prompt
        self._sessions[run_id] = context
        _validate_policy_hash(context)
        preflight = perform_harness_preflight(
            current,
            prompt=prompt,
            turn=turn,
            step=step,
            profile=context.profile,
            policy_path=context.policy_path,
            token_mode=context.token_mode,
            max_tokens=context.max_tokens,
            language=context.language,
        )
        context.session = load_control_session(current.run_dir)
        self._sessions[run_id] = context
        self._index.index_run(current.run_dir)
        if preflight.decision == "block":
            decision = "deny"
        elif preflight.required_review or preflight.decision == "suggest":
            decision = "suggest"
        else:
            decision = "allow"
        feedback = (
            _bounded_text(preflight.improved_prompt, feedback_limit)
            if decision == "suggest"
            else None
        )
        return {
            "decision": decision,
            "risk_level": preflight.risk_level,
            "summary": _bounded_text(preflight.summary, feedback_limit),
            "feedback": feedback,
        }

    def _harness_tool_pre_execute(self, params: JsonDict) -> JsonDict:
        run_id = _required_string(params, "run_id")
        session_id = _required_string(params, "session_id")
        context = self._harness_context(run_id, session_id)
        event_id = _required_string(params, "event_id")
        self._validate_harness_policy(context, params)
        _validate_policy_hash(context)
        raw_tool = params.get("tool")
        if not isinstance(raw_tool, dict):
            raise ValueError("Harness tool metadata must be an object")
        tool = _safe_tool_metadata(cast(JsonDict, raw_tool))
        tool_name = str(tool.get("name", "unknown"))
        argument_keys = tool.get("argument_keys", [])
        synthetic_prompt = (
            f"Tool request: {tool_name}. Safe argument keys: "
            + ", ".join(str(item) for item in argument_keys)
        )
        guard = guard_prompt(
            synthetic_prompt,
            context=empty_prompt_context(),
            mode="gate",
            profile="coding",
            token_mode=context.token_mode,
            max_tokens=context.max_tokens,
            language=context.language,
            policy_path=context.policy_path,
        )
        if guard.action == "block":
            decision = "deny"
        elif guard.required_review:
            decision = "ask"
        else:
            decision = "allow"
        reason = _bounded_text(guard.plain_summary, 600)
        append_control_event(
            context.session,
            event_type="tools/pre-execute",
            payload={"tool": tool, "decision": decision, "reason": reason},
            idempotency_key=f"harness-tool:{event_id}",
        )
        self._index.index_run(context.session.run_dir)
        return {"decision": decision, "reason": reason}

    def _harness_event(self, params: JsonDict) -> JsonDict:
        from promptcontrollab.harness_integration import sanitize_harness_event

        run_id = _required_string(params, "run_id")
        session_id = _required_string(params, "session_id")
        context = self._harness_context(run_id, session_id)
        event_type = _required_string(params, "event_type")
        source_sequence = _optional_int(params.get("sequence"), "sequence")
        source_timestamp = _required_string(params, "timestamp")
        raw_payload = params.get("payload")
        if not isinstance(raw_payload, dict):
            raise ValueError("Harness event payload must be an object")
        safe = sanitize_harness_event(
            {
                "type": event_type,
                "sequence": source_sequence,
                "payload": cast(JsonDict, raw_payload),
            }
        )
        safe_payload = safe.get("payload")
        if not isinstance(safe_payload, dict):
            raise ValueError("Harness event sanitizer returned an invalid payload")
        _, appended = append_control_event(
            context.session,
            event_type=event_type,
            payload={
                "source_sequence": source_sequence,
                "source_timestamp": source_timestamp,
                **cast(JsonDict, safe_payload),
            },
            idempotency_key=_required_string(params, "idempotency_key"),
        )
        self._index.index_run(context.session.run_dir)
        return {"accepted": appended, "duplicate": not appended}

    def _harness_turn_end(self, params: JsonDict) -> JsonDict:
        run_id = _required_string(params, "run_id")
        session_id = _required_string(params, "session_id")
        context = self._harness_context(run_id, session_id)
        _required_int(params, "turn")
        feedback_limit = _bounded_limit(params.get("feedback_max_chars"))
        if not isinstance(params.get("reason"), dict):
            raise ValueError("Harness turn-end reason must be an object")
        events = [event.to_json() for event in context.session.events.read()]
        stability = analyze_stability(context.session.run.to_json(), events)
        preflight_path = context.session.run_dir / "preflight.json"
        preflight = read_json(preflight_path) if preflight_path.exists() else {}
        decision = make_control_decision(
            context.session.run.to_json(),
            preflight=preflight,
            stability=stability,
            events=events,
        )
        recover_allowed = context.session.run.metadata.get("harness_auto_recover") is True
        recover = recover_allowed and stability.state in {"stalled", "oscillating"}
        return {
            "stability": stability.state,
            "recommendation": _bounded_text(decision.next_action, feedback_limit),
            "recover": recover,
        }

    def _harness_status(self, params: JsonDict) -> JsonDict:
        run_id = _required_string(params, "run_id")
        session_id = _required_string(params, "session_id")
        context = self._harness_context(run_id, session_id)
        status = control_status(context.session)
        preflight_path = context.session.run_dir / "preflight.json"
        preflight = read_json(preflight_path) if preflight_path.exists() else {}
        stability_path = context.session.run_dir / "stability.json"
        if stability_path.exists():
            stability_state = str(read_json(stability_path).get("state", "insufficient_evidence"))
        else:
            events = [event.to_json() for event in context.session.events.read()]
            stability_state = analyze_stability(
                context.session.run.to_json(), events
            ).state
        report_path = context.session.run_dir / "report.md"
        return {
            "run_id": run_id,
            "status": status["status"],
            "risk_level": str(preflight.get("risk_level", "unknown")),
            "stability": stability_state,
            "report_path": str(report_path.resolve()) if report_path.exists() else None,
        }

    def _harness_finalize(self, params: JsonDict) -> JsonDict:
        from promptcontrollab.harness_integration import finalize_harness_run

        run_id = _required_string(params, "run_id")
        session_id = _required_string(params, "session_id")
        context = self._harness_context(run_id, session_id)
        status = finalize_harness_run(
            self.runs_root,
            run_id,
            outcome="completed",
            exit_code=0,
        )
        self._index.index_run(context.session.run_dir)
        report_path = context.session.run_dir / "report.md"
        return {
            "run_id": run_id,
            "status": status["status"],
            "report_path": str(report_path.resolve()) if report_path.exists() else None,
        }

    def _harness_context(self, run_id: str, session_id: str) -> _BridgeSession:
        context = self._sessions.get(run_id)
        if context is None:
            session = self._session(run_id)
            metadata = session.run.metadata
            context = _BridgeSession(
                session=session,
                prompt=None,
                profile=_metadata_string(metadata, "profile", "coding"),
                policy_path=_metadata_policy_path(metadata),
                token_mode=_metadata_string(metadata, "token_mode", "balanced"),
                max_tokens=_metadata_optional_int(metadata, "max_tokens"),
                language=_metadata_string(metadata, "language", "auto"),
                harness_session_id=_metadata_string(metadata, "harness_session_id", ""),
                harness_mode=_metadata_string(metadata, "harness_mode", "suggest"),
            )
            self._sessions[run_id] = context
        if context.harness_session_id != session_id:
            msg = f"Harness session_id does not match control run `{run_id}`"
            raise ValueError(msg)
        return context

    def _resolve_harness_policy_path(self, value: object) -> Path | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value:
            raise ValueError("Harness policy_path must be a string or null")
        candidate = Path(value)
        resolved = (candidate if candidate.is_absolute() else Path.cwd() / candidate).resolve()
        integration_root = self.runs_root.parent
        if not resolved.is_relative_to(integration_root):
            msg = f"Harness policy_path must remain under `{integration_root}`"
            raise ValueError(msg)
        return resolved

    def _harness_start_run(
        self,
        base_run_id: str,
        session_id: str,
    ) -> tuple[str, int, str | None]:
        ordinal = 1
        latest: ControlSession | None = None
        while True:
            run_id = base_run_id if ordinal == 1 else f"{base_run_id}-resume-{ordinal}"
            run_dir = self._resolve_run_dir(None, run_id=run_id)
            run_path = run_dir / "control_run.json"
            if not run_path.exists():
                break
            candidate = load_control_session(run_dir)
            if candidate.run.run_id != run_id:
                raise ValueError(f"Harness run directory does not match `{run_id}`")
            recorded_session = candidate.run.metadata.get("harness_session_id")
            if recorded_session != session_id:
                raise ValueError(f"Harness run id `{run_id}` belongs to another session")
            latest = candidate
            ordinal += 1

        if latest is not None and latest.run.status != "finalized":
            active_ordinal = ordinal - 1
            previous = (
                None
                if active_ordinal == 1
                else base_run_id
                if active_ordinal == 2
                else f"{base_run_id}-resume-{active_ordinal - 1}"
            )
            return latest.run.run_id, active_ordinal, previous
        previous = latest.run.run_id if latest is not None else None
        next_run_id = base_run_id if ordinal == 1 else f"{base_run_id}-resume-{ordinal}"
        return next_run_id, ordinal, previous

    def _validate_harness_policy(
        self,
        context: _BridgeSession,
        params: JsonDict,
    ) -> None:
        if "policy_path" not in params:
            return
        supplied = self._resolve_harness_policy_path(params.get("policy_path"))
        if supplied != context.policy_path:
            raise ValueError("Harness policy_path does not match the persisted policy_path")

    def _session_start(self, params: JsonDict) -> JsonDict:
        run_id = _required_string(params, "run_id")
        prompt = _required_string(params, "prompt")
        run_dir = self._resolve_run_dir(params.get("run_dir"), run_id=run_id)
        self._validate_run_binding(run_id, run_dir)
        policy_value = params.get("policy_path")
        policy_path = Path(policy_value) if isinstance(policy_value, str) else None
        token_mode = str(params.get("token_mode", "balanced"))
        max_tokens = _optional_int(params.get("max_tokens"), "max_tokens")
        language = str(params.get("language", "auto"))
        session = start_control_session(
            run_dir=run_dir,
            prompt=prompt,
            authorization=_required_string(params, "authorization"),
            run_id=run_id,
            provider=_optional_string(params.get("provider"), "provider"),
            model=_optional_string(params.get("model"), "model"),
            agent=_optional_string(params.get("agent"), "agent"),
            profile=str(params.get("profile", "general")),
            policy_path=policy_path,
            capture_mode="redacted",
            token_mode=token_mode,
            max_tokens=max_tokens,
            language=language,
        )
        self._sessions[run_id] = _BridgeSession(
            session=session,
            prompt=prompt,
            profile=str(params.get("profile", "general")),
            policy_path=policy_path,
            token_mode=token_mode,
            max_tokens=max_tokens,
            language=language,
        )
        self._index.index_run(run_dir)
        return control_status(session)

    def _session(self, run_id: str) -> ControlSession:
        context = self._sessions.get(run_id)
        if context is not None:
            return context.session
        indexed = self._index.get(run_id)
        if indexed is not None:
            run_dir = indexed.get("run_dir")
            if not isinstance(run_dir, str):
                msg = f"Indexed run `{run_id}` has no valid run directory"
                raise ValueError(msg)
            resolved_run_dir = self._resolve_run_dir(run_dir, run_id=run_id)
            session = load_control_session(resolved_run_dir)
            if session.run.run_id != run_id:
                msg = f"Indexed run id mismatch for `{run_id}`"
                raise ValueError(msg)
            return session
        return load_control_session(self._resolve_run_dir(None, run_id=run_id))

    def _context(self, run_id: str, params: JsonDict) -> _BridgeSession:
        context = self._sessions.get(run_id)
        if context is not None:
            _validate_context_request(context, params)
            _validate_policy_hash(context)
            return context
        session = self._session(run_id)
        prompt = _required_string(params, "prompt")
        prompt_hash = "sha256:" + stable_digest(prompt)
        if prompt_hash != session.run.prompt_hash:
            msg = "Restarted preflight prompt does not match the recorded prompt hash"
            raise ValueError(msg)
        metadata = session.run.metadata
        profile = _metadata_string(metadata, "profile", "general")
        policy_path = _metadata_policy_path(metadata)
        context = _BridgeSession(
            session=session,
            prompt=prompt,
            profile=profile,
            policy_path=policy_path,
            token_mode=_metadata_string(metadata, "token_mode", "balanced"),
            max_tokens=_metadata_optional_int(metadata, "max_tokens"),
            language=_metadata_string(metadata, "language", "auto"),
        )
        _validate_context_request(context, params)
        _validate_policy_hash(context)
        self._sessions[run_id] = context
        return context

    def _resolve_run_dir(self, value: object, *, run_id: str) -> Path:
        if value is None:
            candidate = self.runs_root / run_id
        else:
            if not isinstance(value, str) or not value:
                msg = "Bridge parameter `run_dir` must be a non-empty string"
                raise ValueError(msg)
            provided = Path(value)
            candidate = provided if provided.is_absolute() else self.runs_root / provided
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self.runs_root):
            msg = (
                f"Bridge run directory must remain under runs root "
                f"`{self.runs_root}`: {resolved}"
            )
            raise ValueError(msg)
        return resolved

    def _validate_run_binding(self, run_id: str, run_dir: Path) -> None:
        context = self._sessions.get(run_id)
        if context is not None and context.session.run_dir.resolve() != run_dir:
            msg = (
                f"Run id `{run_id}` is already registered at "
                f"{context.session.run_dir.resolve()}"
            )
            raise ValueError(msg)
        indexed = self._index.get(run_id)
        if indexed is None:
            return
        indexed_dir = indexed.get("run_dir")
        if not isinstance(indexed_dir, str):
            msg = f"Indexed run `{run_id}` has no valid run directory"
            raise ValueError(msg)
        resolved_indexed_dir = self._resolve_run_dir(indexed_dir, run_id=run_id)
        if resolved_indexed_dir != run_dir:
            msg = f"Run id `{run_id}` is already registered at {resolved_indexed_dir}"
            raise ValueError(msg)


def serve_stdio(
    *,
    runs_root: Path,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> None:
    """Serve line-delimited JSON-RPC requests until stdin reaches EOF."""

    source = input_stream or sys.stdin
    sink = output_stream or sys.stdout
    bridge = ControlBridge(runs_root)
    for line in source:
        if not line.strip():
            continue
        response = _handle_line(bridge, line)
        if response is not None:
            sink.write(json.dumps(response, ensure_ascii=False, sort_keys=True) + "\n")
            sink.flush()


def _handle_line(bridge: ControlBridge, line: str) -> JsonDict | None:
    request_id: object = None
    notification = False
    try:
        raw = json.loads(line)
        if not isinstance(raw, dict):
            raise InvalidRequestError("JSON-RPC request must be an object")
        request = cast(JsonDict, raw)
        request_id = request.get("id")
        if request.get("jsonrpc") != "2.0":
            raise InvalidRequestError("JSON-RPC version must be `2.0`")
        _validate_request_id(request)
        method_value = request.get("method")
        if not isinstance(method_value, str) or not method_value:
            raise InvalidRequestError("JSON-RPC method must be a non-empty string")
        method = method_value
        notification = "id" not in request
        params = request.get("params", {})
        if not isinstance(params, dict):
            raise InvalidParamsError("JSON-RPC params must be an object")
        result = bridge.dispatch(method, cast(JsonDict, params))
        if notification:
            return None
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }
    except MethodNotFoundError as exc:
        return None if notification else _error_response(request_id, -32601, str(exc))
    except json.JSONDecodeError as exc:
        return _error_response(None, -32700, f"Invalid JSON: {exc.msg}")
    except InvalidRequestError as exc:
        return _error_response(request_id, -32600, str(exc))
    except (InvalidParamsError, TypeError, ValueError) as exc:
        return None if notification else _error_response(request_id, -32602, str(exc))
    except OSError as exc:
        return None if notification else _error_response(request_id, -32603, str(exc))


def _error_response(request_id: object, code: int, message: str) -> JsonDict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _required_string(value: JsonDict, name: str) -> str:
    item = value.get(name)
    if not isinstance(item, str) or not item:
        msg = f"Bridge parameter `{name}` must be a non-empty string"
        raise ValueError(msg)
    return item


def _required_choice(value: JsonDict, name: str, choices: set[str]) -> str:
    item = _required_string(value, name)
    if item not in choices:
        allowed = ", ".join(sorted(choices))
        raise ValueError(f"Bridge parameter `{name}` must be one of: {allowed}")
    return item


def _required_int(value: JsonDict, name: str) -> int:
    item = _optional_int(value.get(name), name)
    if item is None or item < 0:
        raise ValueError(f"Bridge parameter `{name}` must be a non-negative integer")
    return item


def _bounded_limit(value: object) -> int:
    limit = _optional_int(value, "feedback_max_chars")
    if limit is None or not 1 <= limit <= 4000:
        raise ValueError("Bridge parameter `feedback_max_chars` must be between 1 and 4000")
    return limit


def _bounded_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= 3:
        return value[:limit]
    return value[: limit - 3] + "..."


def _safe_tool_metadata(value: JsonDict) -> JsonDict:
    name = value.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("Harness tool metadata requires a non-empty name")
    safe: JsonDict = {"name": name}
    for field in ("call_id", "root_call_id", "argument_hash"):
        item = value.get(field)
        if item is None:
            continue
        if not isinstance(item, str):
            raise ValueError(f"Harness tool metadata `{field}` must be a string")
        safe[field] = item
    keys = value.get("argument_keys", [])
    if not isinstance(keys, list) or not all(isinstance(item, str) for item in keys):
        raise ValueError("Harness tool metadata `argument_keys` must be a string list")
    safe["argument_keys"] = sorted(set(cast(list[str], keys)))[:64]
    return safe


def _validate_harness_start_retry(
    session: ControlSession,
    *,
    provider: str | None,
    model: str | None,
    policy_path: Path | None,
    extra_metadata: JsonDict,
) -> None:
    run = session.run
    metadata = run.metadata
    expected_policy = str(policy_path.resolve()) if policy_path is not None else None
    recorded_policy = metadata.get("policy_path")
    mismatched = (
        run.authorization != "agent-scoped"
        or run.provider != provider
        or run.model != model
        or run.agent != "deepseek-harness"
        or metadata.get("profile") != "coding"
        or metadata.get("capture_mode") != "redacted"
        or metadata.get("token_mode") != "balanced"
        or metadata.get("language") != "auto"
        or metadata.get("max_tokens") is not None
        or recorded_policy != expected_policy
        or metadata.get("prompt_binding") not in {"pending", "bound"}
        or any(
            metadata.get(key) != value
            for key, value in extra_metadata.items()
            if key != "prompt_binding"
        )
    )
    if mismatched:
        msg = f"Harness session start conflicts with existing control run `{run.run_id}`"
        raise ValueError(msg)


def _policy_allows_recovery(policy_path: Path | None) -> bool:
    if policy_path is None or not policy_path.exists():
        return False
    payload = read_simple_yaml(policy_path)
    return any(
        payload.get(name) is True
        for name in ("harness_auto_recover", "harness.auto_recover")
    )


def _optional_string(value: object, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        msg = f"Bridge parameter `{name}` must be a string"
        raise ValueError(msg)
    return value


def _optional_int(value: object, name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        msg = f"Bridge parameter `{name}` must be an integer"
        raise ValueError(msg)
    return value


def _optional_bool(value: object, name: str, *, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError(f"Bridge parameter `{name}` must be true or false")
    return value


def _nonnegative_int(value: object, name: str, *, default: int) -> int:
    parsed = _optional_int(value, name)
    if parsed is None:
        return default
    if parsed < 0:
        raise ValueError(f"Bridge parameter `{name}` must be a non-negative integer")
    return parsed


def _validate_context_request(context: _BridgeSession, params: JsonDict) -> None:
    if "prompt" in params:
        prompt = _required_string(params, "prompt")
        if "sha256:" + stable_digest(prompt) != context.session.run.prompt_hash:
            msg = "Restarted preflight prompt does not match the recorded prompt hash"
            raise ValueError(msg)
    recorded: JsonDict = {
        "profile": context.profile,
        "policy_path": (
            str(context.policy_path.resolve()) if context.policy_path is not None else None
        ),
        "token_mode": context.token_mode,
        "max_tokens": context.max_tokens,
        "language": context.language,
    }
    for name in ("profile", "policy_path", "token_mode", "max_tokens", "language"):
        if name not in params:
            continue
        if name == "max_tokens":
            supplied: object = _optional_int(params[name], name)
        elif name == "policy_path":
            policy_value = _optional_string(params[name], name)
            supplied = str(Path(policy_value).resolve()) if policy_value is not None else None
        else:
            supplied = _optional_string(params[name], name)
        if supplied != recorded[name]:
            msg = f"Bridge parameter `{name}` does not match persisted `{name}`"
            raise ValueError(msg)


def _validate_policy_hash(context: _BridgeSession) -> None:
    expected = context.session.run.metadata.get("policy_hash")
    if context.policy_path is None:
        if expected is not None:
            raise ValueError("Persisted policy_hash has no policy_path")
        return
    if not isinstance(expected, str) or not expected:
        raise ValueError("Persisted policy_path is missing policy_hash")
    try:
        content = context.policy_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ValueError("Persisted policy_hash cannot be validated") from exc
    actual = "sha256:" + stable_digest(content)
    if actual != expected:
        raise ValueError("Persisted policy_hash does not match current policy content")


def _metadata_string(metadata: JsonDict, name: str, default: str) -> str:
    value = metadata.get(name, default)
    if not isinstance(value, str):
        raise ValueError(f"Persisted control configuration `{name}` must be a string")
    return value


def _metadata_optional_int(metadata: JsonDict, name: str) -> int | None:
    value = metadata.get(name)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Persisted control configuration `{name}` must be an integer")
    return value


def _metadata_policy_path(metadata: JsonDict) -> Path | None:
    value = metadata.get("policy_path")
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError("Persisted control configuration `policy_path` must be a string")
    return Path(value).resolve()


def _validate_request_id(request: JsonDict) -> None:
    if "id" not in request:
        return
    request_id = request["id"]
    if request_id is None or isinstance(request_id, str):
        return
    if isinstance(request_id, int | float) and not isinstance(request_id, bool):
        return
    raise InvalidRequestError("JSON-RPC id must be a string, number, or null")
