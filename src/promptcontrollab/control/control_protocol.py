"""Versioned records for the local prompt and agent control loop."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar, cast

from promptcontrollab.core.files import JsonDict, stable_digest

REDACTED = "[REDACTED]"
_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "authorization",
    "password",
    "passwd",
    "secret",
    "client_secret",
    "cookie",
    "set_cookie",
    "private_key",
    "credentials",
    "credential",
    "token",
    "tokens",
    "prompt",
    "prompts",
    "raw_prompt",
    "original_prompt",
    "improved_prompt",
    "input_prompt",
}
_SENSITIVE_SUFFIXES = (
    "_api_key",
    "_access_key",
    "_secret_access_key",
    "_access_token",
    "_refresh_token",
    "_auth_token",
    "_id_token",
    "_tokens",
    "_password",
    "_passwd",
    "_secret",
    "_credentials",
    "_credential",
    "_private_key",
    "_prompt",
)
_SAFE_USAGE_KEYS = {
    "token_count",
    "token_usage",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cached_tokens",
    "reasoning_tokens",
    "prompt_tokens",
    "completion_tokens",
    "audio_tokens",
    "accepted_prediction_tokens",
    "rejected_prediction_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
    "max_tokens",
    "max_output_tokens",
    "max_completion_tokens",
    "input_token_count",
    "output_token_count",
    "total_token_count",
    "usage",
}
_SAFE_USAGE_COMPACT = {key.replace("_", "") for key in _SAFE_USAGE_KEYS}
_SENSITIVE_COMPACT_ROOTS = (
    "apikey",
    "accesskey",
    "secretaccesskey",
    "accesstoken",
    "refreshtoken",
    "authtoken",
    "idtoken",
    "password",
    "passwd",
    "secret",
    "credential",
    "privatekey",
    "token",
    "cookie",
    "prompt",
)

_PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN(?: [A-Z0-9]+)* PRIVATE KEY-----.*?"
    r"-----END(?: [A-Z0-9]+)* PRIVATE KEY-----",
    flags=re.IGNORECASE | re.DOTALL,
)
_BEARER_PATTERN = re.compile(
    r"\b(Bearer)\s+[A-Za-z0-9._~+/=-]{8,}",
    flags=re.IGNORECASE,
)
_CREDENTIAL_ASSIGNMENT_PATTERN = re.compile(
    r"(?P<name_quote>[\"']?)\b(?P<name>"
    r"x-api-key|(?:[A-Za-z0-9]+[_-])*api[_-]?keys?|"
    r"(?:[A-Za-z0-9]+[_-])*secret[_-]?access[_-]?keys?|"
    r"access[_-]?tokens?|refresh[_-]?tokens?|"
    r"client[_-]?secrets?|private[_-]?keys?|passwords?|passwd|credentials?|tokens?"
    r")\b(?P=name_quote)(?P<separator>\s*[:=]\s*)"
    r"(?P<quote>[\"']?)(?P<value>[^\s,;\"']{4,})(?P=quote)",
    flags=re.IGNORECASE,
)
_SECRET_VALUE_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{12,}\b", flags=re.IGNORECASE),
    re.compile(r"\bAIza[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
)


def utc_now() -> str:
    """Return a stable UTC timestamp representation."""

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def redact_sensitive(value: Any) -> Any:
    """Recursively redact credential-shaped fields while retaining usage metrics."""

    if isinstance(value, dict):
        result: JsonDict = {}
        for key, item in value.items():
            separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(key))
            normalized = re.sub(r"[^a-z0-9]+", "_", separated.lower()).strip("_")
            compact = re.sub(r"[^a-z0-9]+", "", str(key).lower())
            result[str(key)] = (
                REDACTED
                if _is_sensitive_name(normalized, compact)
                else redact_sensitive(item)
            )
        return result
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, str):
        return _redact_sensitive_string(value)
    return value


def _is_sensitive_name(normalized: str, compact: str) -> bool:
    if normalized in _SAFE_USAGE_KEYS or compact in _SAFE_USAGE_COMPACT:
        return False
    return (
        normalized in _SENSITIVE_KEYS
        or normalized.endswith(_SENSITIVE_SUFFIXES)
        or compact in {"token", "tokens", "credential", "credentials"}
        or any(
            compact.endswith(root) or compact.endswith(f"{root}s")
            for root in _SENSITIVE_COMPACT_ROOTS
        )
    )


def _redact_sensitive_string(value: str) -> str:
    redacted = _PRIVATE_KEY_PATTERN.sub("[REDACTED PRIVATE KEY]", value)
    redacted = _BEARER_PATTERN.sub(lambda match: f"{match.group(1)} {REDACTED}", redacted)

    def redact_assignment(match: re.Match[str]) -> str:
        name_quote = match.group("name_quote")
        quote = match.group("quote")
        return (
            f"{name_quote}{match.group('name')}{name_quote}{match.group('separator')}"
            f"{quote}{REDACTED}{quote}"
        )

    redacted = _CREDENTIAL_ASSIGNMENT_PATTERN.sub(redact_assignment, redacted)
    for pattern in _SECRET_VALUE_PATTERNS:
        redacted = pattern.sub(REDACTED, redacted)
    return redacted


def _object(value: object, name: str) -> JsonDict:
    if not isinstance(value, dict):
        msg = f"Expected object field `{name}`"
        raise ValueError(msg)
    return cast(JsonDict, redact_sensitive(value))


def _string(value: object, name: str) -> str:
    if not isinstance(value, str):
        msg = f"Expected string field `{name}`"
        raise ValueError(msg)
    return value


def _boolean(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        msg = f"Expected boolean field `{name}`"
        raise ValueError(msg)
    return value


def _string_list(value: object, name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        msg = f"Expected string list field `{name}`"
        raise ValueError(msg)
    return cast(list[str], value)


def _schema(value: JsonDict, expected: str) -> None:
    actual = value.get("schema")
    if actual != expected:
        msg = f"Expected schema `{expected}`, got `{actual}`"
        raise ValueError(msg)


@dataclass(frozen=True)
class ControlRun:
    """Identity and immutable context for one control-loop run."""

    SCHEMA: ClassVar[str] = "prompt_control_lab.control_run.v1"

    run_id: str
    created_at: str
    authorization: str
    status: str
    prompt_hash: str
    provider: str | None = None
    model: str | None = None
    agent: str | None = None
    metadata: JsonDict = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", redact_sensitive(self.metadata))

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        authorization: str,
        prompt_hash: str,
        provider: str | None = None,
        model: str | None = None,
        agent: str | None = None,
        metadata: JsonDict | None = None,
        created_at: str | None = None,
        status: str = "initialized",
    ) -> ControlRun:
        """Create a validated control-run record with redacted metadata."""

        return cls(
            run_id=run_id,
            created_at=created_at or utc_now(),
            authorization=authorization,
            status=status,
            prompt_hash=prompt_hash,
            provider=provider,
            model=model,
            agent=agent,
            metadata=cast(JsonDict, redact_sensitive(metadata or {})),
        )

    def to_json(self) -> JsonDict:
        """Serialize the control run to its versioned persistence schema."""

        return {
            "schema": self.SCHEMA,
            "run_id": self.run_id,
            "created_at": self.created_at,
            "authorization": self.authorization,
            "status": self.status,
            "prompt_hash": self.prompt_hash,
            "provider": self.provider,
            "model": self.model,
            "agent": self.agent,
            "metadata": redact_sensitive(self.metadata),
        }

    @classmethod
    def from_json(cls, value: JsonDict) -> ControlRun:
        """Create a control run from its validated persistence schema."""

        _schema(value, cls.SCHEMA)
        return cls.create(
            run_id=_string(value.get("run_id"), "run_id"),
            created_at=_string(value.get("created_at"), "created_at"),
            authorization=_string(value.get("authorization"), "authorization"),
            status=_string(value.get("status"), "status"),
            prompt_hash=_string(value.get("prompt_hash"), "prompt_hash"),
            provider=_optional_string(value.get("provider"), "provider"),
            model=_optional_string(value.get("model"), "model"),
            agent=_optional_string(value.get("agent"), "agent"),
            metadata=_object(value.get("metadata", {}), "metadata"),
        )


@dataclass(frozen=True)
class ControlEvent:
    """One ordered event in a control run."""

    SCHEMA: ClassVar[str] = "prompt_control_lab.control_event.v1"

    run_id: str
    event_id: str
    sequence: int
    event_type: str
    timestamp: str
    payload: JsonDict = field(default_factory=dict)
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", redact_sensitive(self.payload))
        if self.idempotency_key == "":
            msg = "Control event idempotency_key cannot be empty"
            raise ValueError(msg)

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        sequence: int,
        event_type: str,
        payload: JsonDict,
        timestamp: str | None = None,
        idempotency_key: str | None = None,
    ) -> ControlEvent:
        """Create a deterministic, redacted control event."""

        safe_payload = cast(JsonDict, redact_sensitive(payload))
        resolved_timestamp = timestamp or utc_now()
        event_id = _canonical_event_id(
            run_id=run_id,
            sequence=sequence,
            event_type=event_type,
            timestamp=resolved_timestamp,
            payload=safe_payload,
            idempotency_key=idempotency_key,
        )
        return cls(
            run_id=run_id,
            event_id=event_id,
            sequence=sequence,
            event_type=event_type,
            timestamp=resolved_timestamp,
            payload=safe_payload,
            idempotency_key=idempotency_key,
        )

    def to_json(self) -> JsonDict:
        """Serialize the control event to its versioned persistence schema."""

        return {
            "schema": self.SCHEMA,
            "run_id": self.run_id,
            "event_id": self.event_id,
            "sequence": self.sequence,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "payload": redact_sensitive(self.payload),
            "idempotency_key": self.idempotency_key,
        }

    @classmethod
    def from_json(cls, value: JsonDict) -> ControlEvent:
        """Create a control event from its validated persistence schema."""

        _schema(value, cls.SCHEMA)
        sequence = value.get("sequence")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            msg = "Control event sequence must be a positive integer"
            raise ValueError(msg)
        run_id = _string(value.get("run_id"), "run_id")
        event_id = _string(value.get("event_id"), "event_id")
        event_type = _string(value.get("event_type"), "event_type")
        timestamp = _string(value.get("timestamp"), "timestamp")
        payload = _object(value.get("payload", {}), "payload")
        idempotency_key = _optional_string(value.get("idempotency_key"), "idempotency_key")
        expected_event_id = _canonical_event_id(
            run_id=run_id,
            sequence=sequence,
            event_type=event_type,
            timestamp=timestamp,
            payload=payload,
            idempotency_key=idempotency_key,
        )
        if event_id != expected_event_id:
            msg = "Control event event_id does not match canonical content"
            raise ValueError(msg)
        return cls(
            run_id=run_id,
            event_id=event_id,
            sequence=sequence,
            event_type=event_type,
            timestamp=timestamp,
            payload=payload,
            idempotency_key=idempotency_key,
        )


@dataclass(frozen=True)
class PreflightDecision:
    """Decision made before a model or agent is allowed to execute."""

    SCHEMA: ClassVar[str] = "prompt_control_lab.preflight_decision.v1"

    run_id: str
    decision: str
    risk_level: str
    required_review: bool
    summary: str
    improved_prompt: str
    prompt_hash: str = ""
    improved_prompt_hash: str = ""
    capture_mode: str = "redacted"
    details: JsonDict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.capture_mode not in {"redacted", "full"}:
            msg = "Preflight capture_mode must be `redacted` or `full`"
            raise ValueError(msg)
        safe_summary = cast(str, redact_sensitive(self.summary))
        improved_hash = self.improved_prompt_hash
        if not improved_hash and self.improved_prompt != REDACTED:
            improved_hash = "sha256:" + stable_digest(self.improved_prompt)
        object.__setattr__(self, "summary", safe_summary)
        object.__setattr__(self, "improved_prompt_hash", improved_hash)
        object.__setattr__(self, "details", redact_sensitive(self.details))

    def to_transport_json(self) -> JsonDict:
        """Serialize the live decision for its immediate trusted caller."""

        return {
            "schema": self.SCHEMA,
            "run_id": self.run_id,
            "decision": self.decision,
            "risk_level": self.risk_level,
            "required_review": self.required_review,
            "summary": self.summary,
            "improved_prompt": self.improved_prompt,
            "prompt_hash": self.prompt_hash,
            "improved_prompt_hash": self.improved_prompt_hash,
            "capture_mode": self.capture_mode,
            "details": redact_sensitive(self.details),
        }

    def to_persistence_json(self) -> JsonDict:
        """Serialize a decision without retaining either prompt body."""

        value = self.to_transport_json()
        value["improved_prompt"] = REDACTED
        return value

    def to_json(self) -> JsonDict:
        """Return the persistence-safe representation for compatibility."""

        return self.to_persistence_json()

    @classmethod
    def from_persistence_json(cls, value: JsonDict) -> PreflightDecision:
        """Load a persistence-safe decision and reject prompt-bearing artifacts."""

        _schema(value, cls.SCHEMA)
        improved_prompt = _string(value.get("improved_prompt"), "improved_prompt")
        if improved_prompt != REDACTED:
            msg = "Persisted preflight decision must not contain an improved prompt"
            raise ValueError(msg)
        return cls(
            run_id=_string(value.get("run_id"), "run_id"),
            decision=_string(value.get("decision"), "decision"),
            risk_level=_string(value.get("risk_level"), "risk_level"),
            required_review=_boolean(value.get("required_review"), "required_review"),
            summary=_string(value.get("summary"), "summary"),
            improved_prompt=improved_prompt,
            prompt_hash=_string(value.get("prompt_hash", ""), "prompt_hash"),
            improved_prompt_hash=_string(
                value.get("improved_prompt_hash", ""), "improved_prompt_hash"
            ),
            capture_mode=_string(value.get("capture_mode", "redacted"), "capture_mode"),
            details=_object(value.get("details", {}), "details"),
        )

    @classmethod
    def from_json(cls, value: JsonDict) -> PreflightDecision:
        """Load the persistence-safe representation for compatibility."""

        return cls.from_persistence_json(value)


@dataclass(frozen=True)
class AttributionReport:
    """Evidence-backed attribution summary for a run."""

    SCHEMA: ClassVar[str] = "prompt_control_lab.attribution_report.v1"

    run_id: str
    status: str
    factors: list[JsonDict]
    summary: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "factors", redact_sensitive(self.factors))

    def to_json(self) -> JsonDict:
        """Serialize the attribution report with sensitive fields redacted."""

        return {
            "schema": self.SCHEMA,
            "run_id": self.run_id,
            "status": self.status,
            "factors": redact_sensitive(self.factors),
            "summary": self.summary,
        }

    @classmethod
    def from_json(cls, value: JsonDict) -> AttributionReport:
        """Create an attribution report from its validated persistence schema."""

        _schema(value, cls.SCHEMA)
        factors = value.get("factors")
        if not isinstance(factors, list) or not all(isinstance(item, dict) for item in factors):
            msg = "Expected object list field `factors`"
            raise ValueError(msg)
        return cls(
            run_id=_string(value.get("run_id"), "run_id"),
            status=_string(value.get("status"), "status"),
            factors=cast(list[JsonDict], redact_sensitive(factors)),
            summary=_string(value.get("summary"), "summary"),
        )


@dataclass(frozen=True)
class StabilityReport:
    """Observable stability state for a control run."""

    SCHEMA: ClassVar[str] = "prompt_control_lab.stability_report.v1"

    run_id: str
    state: str
    signals: JsonDict
    summary: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "signals", redact_sensitive(self.signals))

    def to_json(self) -> JsonDict:
        """Serialize the stability report with sensitive fields redacted."""

        return {
            "schema": self.SCHEMA,
            "run_id": self.run_id,
            "state": self.state,
            "signals": redact_sensitive(self.signals),
            "summary": self.summary,
        }

    @classmethod
    def from_json(cls, value: JsonDict) -> StabilityReport:
        """Create a stability report from its validated persistence schema."""

        _schema(value, cls.SCHEMA)
        return cls(
            run_id=_string(value.get("run_id"), "run_id"),
            state=_string(value.get("state"), "state"),
            signals=_object(value.get("signals", {}), "signals"),
            summary=_string(value.get("summary"), "summary"),
        )


@dataclass(frozen=True)
class ControlDecision:
    """Final recommendation produced by the control loop."""

    SCHEMA: ClassVar[str] = "prompt_control_lab.control_decision.v1"

    run_id: str
    decision: str
    next_action: str
    reasons: list[str]

    def to_json(self) -> JsonDict:
        """Serialize the control decision to its versioned persistence schema."""

        return {
            "schema": self.SCHEMA,
            "run_id": self.run_id,
            "decision": self.decision,
            "next_action": self.next_action,
            "reasons": self.reasons,
        }

    @classmethod
    def from_json(cls, value: JsonDict) -> ControlDecision:
        """Create a control decision from its validated persistence schema."""

        _schema(value, cls.SCHEMA)
        return cls(
            run_id=_string(value.get("run_id"), "run_id"),
            decision=_string(value.get("decision"), "decision"),
            next_action=_string(value.get("next_action"), "next_action"),
            reasons=_string_list(value.get("reasons"), "reasons"),
        )


def _optional_string(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _string(value, name)


def _canonical_event_id(
    *,
    run_id: str,
    sequence: int,
    event_type: str,
    timestamp: str,
    payload: JsonDict,
    idempotency_key: str | None,
) -> str:
    identity: JsonDict = {
        "run_id": run_id,
        "event_type": event_type,
        "payload": redact_sensitive(payload),
    }
    if idempotency_key is None:
        identity["sequence"] = sequence
        identity["timestamp"] = timestamp
    else:
        identity["idempotency_key"] = idempotency_key
    return "evt_" + stable_digest(identity)[:24]
