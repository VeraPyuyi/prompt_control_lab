"""Import external GenAI traces into the versioned local control protocol."""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from promptcontrollab.control.control_protocol import (
    ControlEvent,
    ControlRun,
    redact_sensitive,
)
from promptcontrollab.core.files import (
    JsonDict,
    read_json,
    read_jsonl,
    stable_digest,
    write_json,
    write_jsonl,
)

TRACE_FORMATS = ("auto", "otel", "openinference")
TRACE_IMPORT_SCHEMA = "prompt_control_lab.trace_import.v1"
_EPOCH = "1970-01-01T00:00:00Z"
_TRACE_ARTIFACTS = {"control_run.json", "events.jsonl", "trace_import.json"}

_PROMPT_KEYS = {
    "gen_ai.prompt",
    "gen_ai.input.messages",
    "llm.input_messages",
    "input.value",
    "input.messages",
    "prompt",
    "prompts",
}
_OUTPUT_KEYS = {
    "gen_ai.completion",
    "gen_ai.output.messages",
    "llm.output_messages",
    "output.value",
    "output.messages",
    "completion",
}
_REASONING_MARKERS = ("reasoning", "chain_of_thought", "chain-of-thought", "thinking")
_WRITE_ACTIONS = {"create", "delete", "modify", "move", "rename", "write"}


@dataclass(frozen=True)
class _Observation:
    source_key: str
    timestamp: str
    event_type: str
    payload: JsonDict

    @property
    def fingerprint(self) -> str:
        return stable_digest(
            {
                "source_key": self.source_key,
                "timestamp": self.timestamp,
                "event_type": self.event_type,
                "payload": self.payload,
            }
        )


@dataclass(frozen=True)
class _ExtractedTrace:
    observations: list[_Observation]
    formats: set[str]
    records_received: int
    out_of_order: bool
    warnings: list[str]


def import_trace_file(
    *,
    input_path: Path,
    format_name: str,
    out_dir: Path,
) -> JsonDict:
    """Import a JSON or JSONL trace file into a shadow-only control run.

    Args:
        input_path: OTLP/OpenTelemetry GenAI or OpenInference JSON/JSONL input.
        format_name: Explicit source format or ``auto`` detection.
        out_dir: Destination directory for the canonical artifacts.

    Returns:
        The persisted trace import summary.

    Raises:
        ValueError: If the input is empty, malformed, or uses an unsupported format.
    """

    payloads = _read_trace_payloads(input_path)
    return import_trace_payloads(
        payloads,
        format_name=format_name,
        out_dir=out_dir,
        merge_existing=False,
    )


def import_trace_payloads(
    payloads: object,
    *,
    format_name: str,
    out_dir: Path,
    merge_existing: bool = False,
) -> JsonDict:
    """Normalize in-memory trace payloads and persist a shadow observation run.

    This function never executes, blocks, retries, or modifies the observed downstream
    operation. It writes only the three trace artifacts inside ``out_dir``.
    """

    if format_name not in TRACE_FORMATS:
        raise ValueError(f"Trace format must be one of: {', '.join(TRACE_FORMATS)}")
    _validate_output_directory(out_dir, merge_existing=merge_existing)
    extracted = _extract_trace(payloads, format_name=format_name)
    if not extracted.observations:
        raise ValueError("Trace input did not contain any supported spans or events")

    existing_observations: list[_Observation] = []
    previous_summary: JsonDict = {}
    existing_run: ControlRun | None = None
    if merge_existing and (out_dir / "control_run.json").exists():
        existing_run = ControlRun.from_json(read_json(out_dir / "control_run.json"))
        existing_observations = [
            _observation_from_event(event)
            for event in (
                ControlEvent.from_json(value)
                for value in read_jsonl(out_dir / "events.jsonl")
            )
        ]
        if (out_dir / "trace_import.json").exists():
            previous_summary = read_json(out_dir / "trace_import.json")

    all_observations = existing_observations + extracted.observations
    unique_observations = _deduplicate_observations(all_observations)
    formats = set(extracted.formats)
    formats.update(_string_items(previous_summary.get("formats")))
    records_received = extracted.records_received + _nonnegative_int(
        previous_summary.get("records_received")
    )
    out_of_order = extracted.out_of_order or bool(previous_summary.get("out_of_order"))
    warnings = sorted(
        set(extracted.warnings + _string_items(previous_summary.get("warnings")))
    )
    run_id = existing_run.run_id if existing_run is not None else _run_id(unique_observations)
    run = _build_control_run(
        run_id=run_id,
        observations=unique_observations,
        formats=formats,
        records_received=records_received,
    )
    events = [
        ControlEvent.create(
            run_id=run.run_id,
            sequence=index,
            event_type=observation.event_type,
            timestamp=observation.timestamp,
            payload=observation.payload,
            idempotency_key=observation.source_key,
        )
        for index, observation in enumerate(unique_observations, start=1)
    ]
    detected_format = next(iter(formats)) if len(formats) == 1 else "mixed"
    summary: JsonDict = {
        "schema": TRACE_IMPORT_SCHEMA,
        "mode": "shadow",
        "capture_mode": "redacted",
        "requested_format": format_name,
        "detected_format": detected_format,
        "formats": sorted(formats),
        "records_received": records_received,
        "events_written": len(events),
        "duplicates_dropped": max(0, records_received - len(events)),
        "out_of_order": out_of_order,
        "warnings": warnings,
        "redaction": {
            "authorization_headers": True,
            "chain_of_thought": True,
            "credentials": True,
            "raw_prompt": True,
        },
    }

    _persist_trace_artifacts(
        out_dir,
        run=run.to_json(),
        events=[event.to_json() for event in events],
        summary=summary,
    )
    return summary


def _validate_output_directory(out_dir: Path, *, merge_existing: bool) -> None:
    """Reject unrelated or partially initialized output directories before writing."""

    if out_dir.exists() and not out_dir.is_dir():
        raise ValueError(f"Trace output must be a directory: {out_dir}")
    if not out_dir.exists() or not any(out_dir.iterdir()):
        return
    if not merge_existing:
        raise ValueError(
            f"Trace import requires a dedicated empty output directory: {out_dir}"
        )
    names = {path.name for path in out_dir.iterdir()}
    if names != _TRACE_ARTIFACTS:
        raise ValueError(
            "Trace receiver can merge only a complete dedicated shadow trace run."
        )
    try:
        run = read_json(out_dir / "control_run.json")
        summary = read_json(out_dir / "trace_import.json")
    except (OSError, ValueError):
        raise ValueError(
            "Trace receiver can merge only a complete dedicated shadow trace run."
        ) from None
    metadata = run.get("metadata")
    valid = (
        run.get("schema") == "prompt_control_lab.control_run.v1"
        and run.get("authorization") == "inspect"
        and run.get("status") == "observed"
        and isinstance(metadata, dict)
        and metadata.get("mode") == "shadow"
        and summary.get("schema") == TRACE_IMPORT_SCHEMA
        and summary.get("mode") == "shadow"
    )
    if not valid:
        raise ValueError(
            "Trace receiver can merge only a complete dedicated shadow trace run."
        )


def _persist_trace_artifacts(
    out_dir: Path,
    *,
    run: JsonDict,
    events: list[JsonDict],
    summary: JsonDict,
) -> None:
    """Replace the dedicated artifact directory as one rollback-safe directory set."""

    out_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{out_dir.name}.trace-", dir=out_dir.parent)
    )
    backup: Path | None = None
    try:
        write_json(temporary / "control_run.json", run)
        write_jsonl(temporary / "events.jsonl", events)
        write_json(temporary / "trace_import.json", summary)
        if out_dir.exists():
            if not any(out_dir.iterdir()):
                out_dir.rmdir()
            else:
                backup = Path(
                    tempfile.mkdtemp(
                        prefix=f".{out_dir.name}.backup-",
                        dir=out_dir.parent,
                    )
                )
                backup.rmdir()
                out_dir.replace(backup)
        try:
            temporary.replace(out_dir)
        except OSError:
            if backup is not None and backup.exists() and not out_dir.exists():
                backup.replace(out_dir)
            raise
        if backup is not None:
            shutil.rmtree(backup)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def _read_trace_payloads(path: Path) -> object:
    if not path.exists() or not path.is_file():
        raise ValueError(f"Trace input does not exist or is not a file: {path}")
    text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        raise ValueError(f"Trace input is empty: {path}")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        payloads: list[object] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                payloads.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on {path}:{line_number}: {exc.msg}") from None
        if not payloads:
            raise ValueError(f"Trace input is empty: {path}") from None
        return payloads


def _extract_trace(payloads: object, *, format_name: str) -> _ExtractedTrace:
    records = payloads if isinstance(payloads, list) else [payloads]
    observations: list[_Observation] = []
    formats: set[str] = set()
    records_received = 0
    warnings: list[str] = []
    original_order: list[tuple[str, str]] = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Each trace record must be a JSON object")
        source_format = _resolve_format(cast(JsonDict, record), format_name=format_name)
        formats.add(source_format)
        if source_format == "otel":
            extracted = _extract_otel(cast(JsonDict, record))
        else:
            extracted = _extract_openinference(cast(JsonDict, record))
        records_received += len(extracted)
        observations.extend(extracted)
        original_order.extend((item.timestamp, item.source_key) for item in extracted)
    if not observations:
        return _ExtractedTrace([], formats, records_received, False, warnings)
    ordered = sorted(original_order)
    out_of_order = original_order != ordered
    if out_of_order:
        warnings.append("Input records were out of order and were sorted deterministically.")
    return _ExtractedTrace(
        observations=observations,
        formats=formats,
        records_received=records_received,
        out_of_order=out_of_order,
        warnings=warnings,
    )


def _resolve_format(record: JsonDict, *, format_name: str) -> str:
    detected = _detect_format(record)
    if format_name == "auto":
        return detected
    if detected != format_name:
        raise ValueError(
            f"Trace record looks like `{detected}`, not requested format `{format_name}`"
        )
    return format_name


def _detect_format(record: JsonDict) -> str:
    if any(key in record for key in ("resourceSpans", "scopeSpans", "traceId", "spanId")):
        return "otel"
    spans = record.get("spans")
    if isinstance(spans, list) and spans and isinstance(spans[0], dict):
        return _detect_format(cast(JsonDict, spans[0]))
    attributes = _attribute_object(record.get("attributes", {}))
    context = record.get("context")
    if (
        isinstance(context, dict)
        or any(key.startswith(("openinference.", "llm.")) for key in attributes)
    ):
        return "openinference"
    raise ValueError("Could not detect trace format; use --format with supported input")


def _extract_otel(record: JsonDict) -> list[_Observation]:
    if "resourceSpans" in record:
        resource_spans = record.get("resourceSpans")
        if not isinstance(resource_spans, list):
            raise ValueError("OTLP resourceSpans must be a list")
        result: list[_Observation] = []
        for resource_span in resource_spans:
            if not isinstance(resource_span, dict):
                raise ValueError("OTLP resourceSpans entries must be objects")
            resource = resource_span.get("resource", {})
            resource_attributes = _attributes_from_container(resource)
            scope_spans = resource_span.get(
                "scopeSpans", resource_span.get("instrumentationLibrarySpans", [])
            )
            if not isinstance(scope_spans, list):
                raise ValueError("OTLP scopeSpans must be a list")
            for scope_span in scope_spans:
                if not isinstance(scope_span, dict):
                    raise ValueError("OTLP scopeSpans entries must be objects")
                spans = scope_span.get("spans", [])
                if not isinstance(spans, list):
                    raise ValueError("OTLP spans must be a list")
                for span in spans:
                    if not isinstance(span, dict):
                        raise ValueError("OTLP span entries must be objects")
                    result.append(
                        _normalize_span(
                            cast(JsonDict, span),
                            attributes=_attributes_from_container(span),
                            resource_attributes=resource_attributes,
                            source_format="otel",
                        )
                    )
        return result
    if "scopeSpans" in record:
        return _extract_otel({"resourceSpans": [{"scopeSpans": record["scopeSpans"]}]})
    return [
        _normalize_span(
            record,
            attributes=_attributes_from_container(record),
            resource_attributes={},
            source_format="otel",
        )
    ]


def _extract_openinference(record: JsonDict) -> list[_Observation]:
    spans = record.get("spans")
    if isinstance(spans, list):
        return [
            _normalize_span(
                cast(JsonDict, span),
                attributes=_attributes_from_container(span),
                resource_attributes={},
                source_format="openinference",
            )
            for span in spans
            if isinstance(span, dict)
        ]
    return [
        _normalize_span(
            record,
            attributes=_attributes_from_container(record),
            resource_attributes={},
            source_format="openinference",
        )
    ]


def _normalize_span(
    span: JsonDict,
    *,
    attributes: JsonDict,
    resource_attributes: JsonDict,
    source_format: str,
) -> _Observation:
    context = span.get("context") if isinstance(span.get("context"), dict) else {}
    trace_id = _first_string(span, "traceId", "trace_id") or _first_string(
        cast(JsonDict, context), "trace_id", "traceId"
    )
    span_id = _first_string(span, "spanId", "span_id") or _first_string(
        cast(JsonDict, context), "span_id", "spanId"
    )
    timestamp = _span_timestamp(span)
    identity = {
        "trace_id": trace_id,
        "span_id": span_id,
        "timestamp": timestamp,
        "attributes": _safe_identity_attributes(attributes),
    }
    source_key = (
        f"{source_format}:{trace_id}:{span_id}"
        if trace_id and span_id
        else f"{source_format}:anonymous:{stable_digest(identity)[:24]}"
    )
    payload = _normalized_payload(
        span,
        attributes=attributes,
        resource_attributes=resource_attributes,
        trace_id=trace_id,
        span_id=span_id,
        source_format=source_format,
    )
    return _Observation(
        source_key=source_key,
        timestamp=timestamp,
        event_type=_event_type(span, attributes),
        payload=payload,
    )


def _normalized_payload(
    span: JsonDict,
    *,
    attributes: JsonDict,
    resource_attributes: JsonDict,
    trace_id: str | None,
    span_id: str | None,
    source_format: str,
) -> JsonDict:
    """Project one source span into a redacted, bounded ControlEvent payload."""

    event_type = _event_type(span, attributes)
    observation = event_type.split("/", maxsplit=1)[0]
    payload: JsonDict = {
        "observation": observation,
        "source_format": source_format,
    }
    if trace_id:
        payload["trace_id"] = trace_id
    if span_id:
        payload["span_id"] = span_id
    service = _string_value(resource_attributes.get("service.name"))
    if service:
        payload["service"] = service

    provider = _first_attribute(
        attributes,
        "gen_ai.system",
        "gen_ai.provider.name",
        "llm.provider",
        "provider",
    )
    model = _first_attribute(
        attributes,
        "gen_ai.response.model",
        "gen_ai.request.model",
        "llm.model_name",
        "model",
    )
    if model:
        payload["model"] = model
    inferred_provider = provider or _infer_provider(model)
    if inferred_provider:
        payload["provider"] = inferred_provider

    usage = _usage(attributes)
    if usage:
        payload["usage"] = usage
    prompt_value = _first_present(attributes, _PROMPT_KEYS)
    if prompt_value is not None:
        payload.update(_content_metadata("prompt", prompt_value))
    output_value = _first_present(attributes, _OUTPUT_KEYS)
    if output_value is not None:
        payload.update(_content_metadata("output", output_value))
    if any(
        any(marker in key.lower() for marker in _REASONING_MARKERS)
        and not key.lower().endswith("reasoning_tokens")
        for key in attributes
    ):
        payload["reasoning_redacted"] = True

    tool_name = _first_attribute(
        attributes,
        "tool.name",
        "gen_ai.tool.name",
        "tool.call.name",
    )
    tool_call_id = _first_attribute(
        attributes,
        "tool.call.id",
        "gen_ai.tool.call.id",
    )
    if tool_name or tool_call_id:
        payload["tool"] = {
            key: value
            for key, value in {"call_id": tool_call_id, "name": tool_name}.items()
            if value is not None
        }

    file_path = _first_attribute(attributes, "file.path", "code.filepath")
    file_action = _first_attribute(attributes, "file.action", "code.file.action")
    if file_path or file_action:
        payload["file"] = {
            key: value
            for key, value in {"action": file_action, "path": file_path}.items()
            if value is not None
        }

    test_command = _first_attribute(attributes, "test.command")
    test_passed = attributes.get("test.passed")
    test_status = _first_attribute(attributes, "test.status")
    if test_command or test_passed is not None or test_status:
        payload["test"] = {
            key: value
            for key, value in {
                "command": test_command,
                "passed": test_passed if isinstance(test_passed, bool) else None,
                "status": test_status,
            }.items()
            if value is not None
        }

    error = _error_metadata(span, attributes)
    if error:
        payload["error"] = error
    return cast(JsonDict, redact_sensitive(payload))


def _event_type(span: JsonDict, attributes: JsonDict) -> str:
    if _is_error(span, attributes):
        return "agent/request-error"
    tool_name = (_first_attribute(attributes, "tool.name", "gen_ai.tool.name") or "").lower()
    if any(key.startswith("test.") for key in attributes) or tool_name in {
        "pytest",
        "unittest",
        "vitest",
        "jest",
    }:
        return "tests/result"
    file_action = (_first_attribute(attributes, "file.action", "code.file.action") or "").lower()
    if file_action in _WRITE_ACTIONS:
        return "files/changed"
    kind = (
        _first_attribute(attributes, "openinference.span.kind", "gen_ai.operation.name") or ""
    ).upper()
    if tool_name or kind == "TOOL":
        return "tools/result"
    if (
        kind in {"LLM", "CHAT"}
        or any(key.startswith(("gen_ai.", "llm.")) for key in attributes)
    ):
        return "agent/request"
    return "trace/span"


def _is_error(span: JsonDict, attributes: JsonDict) -> bool:
    if any(key.startswith(("error.", "exception.")) for key in attributes):
        return True
    status = span.get("status")
    if not isinstance(status, dict):
        return False
    code = status.get("code", status.get("status_code"))
    return code == 2 or str(code).upper() in {"ERROR", "STATUS_CODE_ERROR"}


def _error_metadata(span: JsonDict, attributes: JsonDict) -> JsonDict:
    error_type = _first_attribute(attributes, "error.type", "exception.type")
    message = _first_attribute(attributes, "error.message", "exception.message")
    status = span.get("status")
    if isinstance(status, dict):
        message = message or _string_value(status.get("message", status.get("description")))
    result: JsonDict = {}
    if error_type:
        result["type"] = error_type
    if message:
        result.update(_content_metadata("message", redact_sensitive(message)))
    return result


def _usage(attributes: JsonDict) -> JsonDict:
    mappings = {
        "input_tokens": (
            "gen_ai.usage.input_tokens",
            "llm.token_count.prompt",
            "prompt_tokens",
        ),
        "output_tokens": (
            "gen_ai.usage.output_tokens",
            "llm.token_count.completion",
            "completion_tokens",
        ),
        "total_tokens": ("gen_ai.usage.total_tokens", "llm.token_count.total"),
    }
    result: JsonDict = {}
    for target, source_keys in mappings.items():
        value = next((attributes[key] for key in source_keys if key in attributes), None)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            result[target] = value
    return result


def _content_metadata(prefix: str, value: object) -> JsonDict:
    serialized = value if isinstance(value, str) else json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return {
        f"{prefix}_hash": "sha256:" + stable_digest(value),
        f"{prefix}_length": len(serialized),
    }


def _attributes_from_container(container: object) -> JsonDict:
    if not isinstance(container, dict):
        return {}
    return _attribute_object(container.get("attributes", {}))


def _attribute_object(value: object) -> JsonDict:
    if isinstance(value, dict):
        return cast(JsonDict, value)
    if not isinstance(value, list):
        return {}
    result: JsonDict = {}
    for item in value:
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            continue
        result[str(item["key"])] = _decode_otel_value(item.get("value"))
    return result


def _decode_otel_value(value: object) -> object:
    if not isinstance(value, dict):
        return value
    typed_keys = (
        "stringValue",
        "boolValue",
        "doubleValue",
        "intValue",
        "bytesValue",
    )
    for key in typed_keys:
        if key not in value:
            continue
        item = value[key]
        if key == "intValue":
            try:
                return int(str(item))
            except ValueError:
                return str(item)
        if key == "bytesValue":
            return "[REDACTED BINARY]"
        return item
    array_value = value.get("arrayValue")
    if isinstance(array_value, dict) and isinstance(array_value.get("values"), list):
        return [_decode_otel_value(item) for item in array_value["values"]]
    kvlist_value = value.get("kvlistValue")
    if isinstance(kvlist_value, dict):
        return _attribute_object(kvlist_value.get("values", []))
    return None


def _span_timestamp(span: JsonDict) -> str:
    nanos = span.get("startTimeUnixNano", span.get("start_time_unix_nano"))
    if nanos is not None:
        try:
            value = int(str(nanos))
        except ValueError:
            return _EPOCH
        seconds, remainder = divmod(value, 1_000_000_000)
        timestamp = datetime.fromtimestamp(seconds, tz=timezone.utc).replace(
            microsecond=remainder // 1_000
        )
        return _format_timestamp(timestamp)
    text = _first_string(span, "start_time", "startTime", "timestamp", "time")
    if text:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return _format_timestamp(parsed.astimezone(timezone.utc))
        except ValueError:
            return _EPOCH
    return _EPOCH


def _format_timestamp(value: datetime) -> str:
    if value.microsecond:
        return value.isoformat(timespec="microseconds").replace("+00:00", "Z")
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _safe_identity_attributes(attributes: JsonDict) -> JsonDict:
    identity: JsonDict = {}
    for key in (
        "file.action",
        "file.path",
        "gen_ai.operation.name",
        "gen_ai.request.model",
        "llm.model_name",
        "openinference.span.kind",
        "test.command",
        "tool.call.id",
        "tool.name",
    ):
        if key in attributes:
            identity[key] = redact_sensitive(attributes[key])
    prompt_value = _first_present(attributes, _PROMPT_KEYS)
    if prompt_value is not None:
        identity["prompt_hash"] = "sha256:" + stable_digest(prompt_value)
    return identity


def _deduplicate_observations(observations: list[_Observation]) -> list[_Observation]:
    by_source: dict[str, list[_Observation]] = {}
    for observation in observations:
        by_source.setdefault(observation.source_key, []).append(observation)
    selected = [
        max(
            candidates,
            key=lambda item: (_payload_size(item.payload), item.fingerprint),
        )
        for candidates in by_source.values()
    ]
    return sorted(selected, key=lambda item: (item.timestamp, item.source_key, item.fingerprint))


def _payload_size(value: object) -> int:
    if isinstance(value, dict):
        return len(value) + sum(_payload_size(item) for item in value.values())
    if isinstance(value, list):
        return len(value) + sum(_payload_size(item) for item in value)
    return int(value is not None)


def _observation_from_event(event: ControlEvent) -> _Observation:
    return _Observation(
        source_key=event.idempotency_key or event.event_id,
        timestamp=event.timestamp,
        event_type=event.event_type,
        payload=event.payload,
    )


def _build_control_run(
    *,
    run_id: str,
    observations: list[_Observation],
    formats: set[str],
    records_received: int,
) -> ControlRun:
    """Create a deterministic inspect-only run identity for imported observations."""

    providers = sorted(
        {
            value
            for item in observations
            if (value := _string_value(item.payload.get("provider")))
        }
    )
    models = sorted(
        {
            value
            for item in observations
            if (value := _string_value(item.payload.get("model")))
        }
    )
    agents = sorted(
        {
            value
            for item in observations
            if (value := _string_value(item.payload.get("service")))
        }
    )
    prompt_hashes = sorted(
        {
            value
            for item in observations
            if (value := _string_value(item.payload.get("prompt_hash")))
        }
    )
    prompt_hash = ""
    if len(prompt_hashes) == 1:
        prompt_hash = prompt_hashes[0]
    elif prompt_hashes:
        prompt_hash = "sha256:" + stable_digest(prompt_hashes)
    return ControlRun.create(
        run_id=run_id,
        authorization="inspect",
        status="observed",
        created_at=min(item.timestamp for item in observations),
        prompt_hash=prompt_hash,
        provider=providers[0] if len(providers) == 1 else None,
        model=models[0] if len(models) == 1 else None,
        agent=agents[0] if len(agents) == 1 else None,
        metadata={
            "capture_mode": "redacted",
            "event_count": len(observations),
            "formats": sorted(formats),
            "mode": "shadow",
            "models": models,
            "providers": providers,
            "records_received": records_received,
        },
    )


def _run_id(observations: list[_Observation]) -> str:
    identity = [
        {
            "event_type": item.event_type,
            "payload": item.payload,
            "source_key": item.source_key,
            "timestamp": item.timestamp,
        }
        for item in observations
    ]
    return "trace_" + stable_digest(identity)[:20]


def _first_attribute(attributes: JsonDict, *keys: str) -> str | None:
    for key in keys:
        value = _string_value(attributes.get(key))
        if value:
            return value
    return None


def _first_present(attributes: JsonDict, keys: set[str]) -> object | None:
    for key in sorted(keys):
        if key in attributes and attributes[key] is not None:
            return cast(object, attributes[key])
    return None


def _first_string(value: JsonDict, *keys: str) -> str | None:
    for key in keys:
        item = _string_value(value.get(key))
        if item:
            return item
    return None


def _string_value(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _infer_provider(model: str | None) -> str | None:
    if model is None:
        return None
    lowered = model.lower()
    prefixes = {
        "claude": "anthropic",
        "deepseek": "deepseek",
        "gemini": "google",
        "gpt": "openai",
        "kimi": "moonshot",
        "qwen": "alibaba",
    }
    return next((provider for prefix, provider in prefixes.items() if prefix in lowered), None)


def _string_items(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _nonnegative_int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0
