from __future__ import annotations

import json
import threading
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from promptcontrollab.cli import main
from promptcontrollab.control.trace_ingest import import_trace_payloads
from promptcontrollab.core.files import read_json, read_jsonl


def _otel_attribute(key: str, value: object) -> dict[str, object]:
    if isinstance(value, bool):
        encoded: dict[str, object] = {"boolValue": value}
    elif isinstance(value, int):
        encoded = {"intValue": str(value)}
    else:
        encoded = {"stringValue": str(value)}
    return {"key": key, "value": encoded}


def _otel_span(
    *,
    span_id: str,
    name: str,
    start_ns: int,
    attributes: dict[str, object],
    status: dict[str, object] | None = None,
) -> dict[str, object]:
    span: dict[str, object] = {
        "traceId": "trace-001",
        "spanId": span_id,
        "name": name,
        "startTimeUnixNano": str(start_ns),
        "endTimeUnixNano": str(start_ns + 100),
        "attributes": [
            _otel_attribute(key, value) for key, value in attributes.items()
        ],
    }
    if status is not None:
        span["status"] = status
    return span


def _otel_payload(spans: list[dict[str, object]]) -> dict[str, object]:
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        _otel_attribute("service.name", "trace-test-agent"),
                        _otel_attribute("service.version", "1.2.3"),
                    ]
                },
                "scopeSpans": [{"scope": {"name": "test"}, "spans": spans}],
            }
        ]
    }


def test_trace_import_otel_sorts_deduplicates_and_redacts(tmp_path: Path) -> None:
    raw_prompt = "RAW PROMPT MUST NOT PERSIST"
    hidden_reasoning = "PRIVATE CHAIN OF THOUGHT MUST NOT PERSIST"
    api_key = "sk-super-secret-provider-key-123456"
    model_span = _otel_span(
        span_id="span-model",
        name="chat deepseek",
        start_ns=3_000_000_000,
        attributes={
            "gen_ai.system": "deepseek",
            "gen_ai.request.model": "deepseek-chat",
            "gen_ai.prompt": raw_prompt,
            "gen_ai.response.reasoning": hidden_reasoning,
            "gen_ai.usage.input_tokens": 17,
            "gen_ai.usage.output_tokens": 5,
            "http.request.header.authorization": f"Bearer {api_key}",
        },
    )
    tool_span = _otel_span(
        span_id="span-tool",
        name="read_file",
        start_ns=2_000_000_000,
        attributes={
            "openinference.span.kind": "TOOL",
            "tool.name": "read_file",
            "tool.call.id": "call-1",
            "file.path": "src/app.py",
            "file.action": "read",
        },
    )
    input_path = tmp_path / "traces.json"
    input_path.write_text(
        json.dumps(_otel_payload([model_span, tool_span, model_span])),
        encoding="utf-8",
    )
    out_dir = tmp_path / "run"

    assert (
        main(
            [
                "trace",
                "import",
                "--input",
                str(input_path),
                "--format",
                "auto",
                "--out",
                str(out_dir),
            ]
        )
        == 0
    )

    run = read_json(out_dir / "control_run.json")
    events = read_jsonl(out_dir / "events.jsonl")
    imported = read_json(out_dir / "trace_import.json")
    assert run["schema"] == "prompt_control_lab.control_run.v1"
    assert run["authorization"] == "inspect"
    assert run["status"] == "observed"
    assert run["metadata"]["mode"] == "shadow"
    assert [event["sequence"] for event in events] == [1, 2]
    assert [event["event_type"] for event in events] == [
        "tools/result",
        "agent/request",
    ]
    assert imported["schema"] == "prompt_control_lab.trace_import.v1"
    assert imported["detected_format"] == "otel"
    assert imported["records_received"] == 3
    assert imported["events_written"] == 2
    assert imported["duplicates_dropped"] == 1
    assert imported["mode"] == "shadow"

    model_event = events[1]
    assert model_event["payload"]["model"] == "deepseek-chat"
    assert model_event["payload"]["provider"] == "deepseek"
    assert model_event["payload"]["usage"] == {
        "input_tokens": 17,
        "output_tokens": 5,
    }
    assert model_event["payload"]["prompt_hash"].startswith("sha256:")
    assert model_event["payload"]["prompt_length"] == len(raw_prompt)
    assert model_event["payload"]["reasoning_redacted"] is True

    persisted = "".join(
        path.read_text(encoding="utf-8")
        for path in (
            out_dir / "control_run.json",
            out_dir / "events.jsonl",
            out_dir / "trace_import.json",
        )
    )
    assert raw_prompt not in persisted
    assert hidden_reasoning not in persisted
    assert api_key not in persisted


def test_trace_import_openinference_jsonl_normalizes_observations(
    tmp_path: Path,
) -> None:
    records = [
        {
            "name": "unit tests",
            "context": {"trace_id": "trace-2", "span_id": "test-1"},
            "start_time": "2026-08-28T00:00:03Z",
            "attributes": {
                "openinference.span.kind": "TOOL",
                "tool.name": "pytest",
                "test.command": "pytest -q",
                "test.passed": True,
            },
        },
        {
            "name": "write source",
            "context": {"trace_id": "trace-2", "span_id": "file-1"},
            "start_time": "2026-08-28T00:00:02Z",
            "attributes": {
                "openinference.span.kind": "TOOL",
                "file.path": "src/service.py",
                "file.action": "write",
                "tool.name": "write_file",
            },
        },
        {
            "name": "failed model request",
            "context": {"trace_id": "trace-2", "span_id": "error-1"},
            "start_time": "2026-08-28T00:00:04Z",
            "status": {"status_code": "ERROR", "description": "token=hidden-value"},
            "attributes": {
                "openinference.span.kind": "LLM",
                "llm.model_name": "gpt-4o-mini",
                "llm.token_count.prompt": 9,
                "llm.token_count.completion": 2,
                "input.value": "secret user input",
                "error.type": "provider_error",
            },
        },
    ]
    input_path = tmp_path / "traces.jsonl"
    input_path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    out_dir = tmp_path / "run"

    assert (
        main(
            [
                "trace",
                "import",
                "--input",
                str(input_path),
                "--format",
                "openinference",
                "--out",
                str(out_dir),
            ]
        )
        == 0
    )

    events = read_jsonl(out_dir / "events.jsonl")
    assert [event["event_type"] for event in events] == [
        "files/changed",
        "tests/result",
        "agent/request-error",
    ]
    assert events[0]["payload"]["file"] == {
        "action": "write",
        "path": "src/service.py",
    }
    assert events[1]["payload"]["test"] == {
        "command": "pytest -q",
        "passed": True,
    }
    assert events[2]["payload"]["usage"] == {
        "input_tokens": 9,
        "output_tokens": 2,
    }
    assert events[2]["payload"]["error"]["type"] == "provider_error"
    persisted = (out_dir / "events.jsonl").read_text(encoding="utf-8")
    assert "secret user input" not in persisted
    assert "hidden-value" not in persisted


def test_trace_import_is_deterministic_for_out_of_order_input(tmp_path: Path) -> None:
    first = _otel_span(
        span_id="span-a",
        name="first",
        start_ns=1_000_000_000,
        attributes={"gen_ai.request.model": "model-a"},
    )
    second = _otel_span(
        span_id="span-b",
        name="second",
        start_ns=2_000_000_000,
        attributes={"tool.name": "search"},
    )
    paths = [tmp_path / "forward.json", tmp_path / "reverse.json"]
    paths[0].write_text(json.dumps(_otel_payload([first, second])), encoding="utf-8")
    paths[1].write_text(json.dumps(_otel_payload([second, first])), encoding="utf-8")
    outputs = [tmp_path / "run-forward", tmp_path / "run-reverse"]

    for input_path, out_dir in zip(paths, outputs, strict=True):
        assert (
            main(
                [
                    "trace",
                    "import",
                    "--input",
                    str(input_path),
                    "--out",
                    str(out_dir),
                ]
            )
            == 0
        )

    assert read_json(outputs[0] / "control_run.json") == read_json(
        outputs[1] / "control_run.json"
    )
    assert read_jsonl(outputs[0] / "events.jsonl") == read_jsonl(
        outputs[1] / "events.jsonl"
    )


def test_trace_import_auto_detects_openinference_span_envelope(tmp_path: Path) -> None:
    input_path = tmp_path / "openinference.json"
    input_path.write_text(
        json.dumps(
            {
                "spans": [
                    {
                        "name": "chat",
                        "context": {"trace_id": "trace-3", "span_id": "span-3"},
                        "start_time": "2026-08-28T00:00:01Z",
                        "attributes": {
                            "openinference.span.kind": "LLM",
                            "llm.model_name": "model-3",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "run-envelope"

    assert main(["trace", "import", "--input", str(input_path), "--out", str(out_dir)]) == 0
    assert read_json(out_dir / "trace_import.json")["detected_format"] == "openinference"
    assert read_jsonl(out_dir / "events.jsonl")[0]["payload"]["model"] == "model-3"


def test_trace_http_receiver_accepts_otlp_json_in_process(tmp_path: Path) -> None:
    from promptcontrollab.control import create_trace_server

    out_dir = tmp_path / "receiver-run"
    server = create_trace_server(host="127.0.0.1", port=0, out_dir=out_dir)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        payload = _otel_payload(
            [
                _otel_span(
                    span_id="span-server",
                    name="server request",
                    start_ns=5_000_000_000,
                    attributes={"gen_ai.request.model": "server-model"},
                )
            ]
        )
        for _ in range(2):
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_address[1]}/v1/traces",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                response_body: Any = json.loads(response.read().decode("utf-8"))
                assert response.status == 200
                assert response_body == {"partialSuccess": {}}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert read_json(out_dir / "control_run.json")["authorization"] == "inspect"
    imported = read_json(out_dir / "trace_import.json")
    assert imported["mode"] == "shadow"
    assert imported["records_received"] == 2
    assert imported["duplicates_dropped"] == 1
    assert len(read_jsonl(out_dir / "events.jsonl")) == 1
    assert not (out_dir / "decision.json").exists()


def test_trace_import_refuses_to_overwrite_unrelated_output(tmp_path: Path) -> None:
    output = tmp_path / "existing-run"
    output.mkdir()
    marker = output / "manifest.json"
    marker.write_text(
        json.dumps({"schema": "unrelated.run.v1", "status": "keep"}),
        encoding="utf-8",
    )
    payload = _otel_payload(
        [
            _otel_span(
                span_id="span-safe",
                name="safe",
                start_ns=1_000_000_000,
                attributes={"gen_ai.request.model": "model-a"},
            )
        ]
    )

    with pytest.raises(ValueError, match="dedicated empty output"):
        import_trace_payloads(
            payload,
            format_name="otel",
            out_dir=output,
            merge_existing=False,
        )

    assert json.loads(marker.read_text(encoding="utf-8"))["status"] == "keep"
    assert not (output / "events.jsonl").exists()


def test_trace_receiver_merge_refuses_non_trace_control_run(tmp_path: Path) -> None:
    output = tmp_path / "existing-control-run"
    output.mkdir()
    (output / "control_run.json").write_text(
        json.dumps(
            {
                "schema": "prompt_control_lab.control_run.v1",
                "run_id": "real-agent-run",
                "authorization": "agent-full",
                "status": "running",
                "metadata": {"mode": "control"},
            }
        ),
        encoding="utf-8",
    )
    payload = _otel_payload(
        [
            _otel_span(
                span_id="span-safe",
                name="safe",
                start_ns=1_000_000_000,
                attributes={"gen_ai.request.model": "model-a"},
            )
        ]
    )

    with pytest.raises(ValueError, match="shadow trace run"):
        import_trace_payloads(
            payload,
            format_name="otel",
            out_dir=output,
            merge_existing=True,
        )

    persisted = read_json(output / "control_run.json")
    assert persisted["authorization"] == "agent-full"
    assert persisted["status"] == "running"


def test_trace_receiver_rejects_unauthenticated_non_loopback_binding(tmp_path: Path) -> None:
    from promptcontrollab.control import create_trace_server

    with pytest.raises(ValueError, match="loopback"):
        create_trace_server(host="0.0.0.0", port=0, out_dir=tmp_path / "receiver")
