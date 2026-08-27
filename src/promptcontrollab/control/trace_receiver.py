"""Dependency-free local HTTP receiver for OTLP JSON traces."""

from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from promptcontrollab.control.trace_ingest import import_trace_payloads
from promptcontrollab.core.files import JsonDict
from promptcontrollab.core.network import is_loopback_host

_MAX_REQUEST_BYTES = 10 * 1024 * 1024


class TraceHTTPServer(ThreadingHTTPServer):
    """Threaded local server that persists observations without taking action."""

    daemon_threads = True

    def __init__(self, address: tuple[str, int], out_dir: Path) -> None:
        self.out_dir = out_dir
        self.ingest_lock = threading.Lock()
        super().__init__(address, _TraceRequestHandler)


class _TraceRequestHandler(BaseHTTPRequestHandler):
    server: TraceHTTPServer

    def do_GET(self) -> None:
        """Return a minimal health response without exposing run data."""

        if self.path != "/healthz":
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        self._write_json(HTTPStatus.OK, {"status": "ok", "mode": "shadow"})

    def do_POST(self) -> None:
        """Accept one OTLP JSON trace batch and acknowledge observation only."""

        if self.path != "/v1/traces":
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        content_type = self.headers.get("Content-Type", "").split(";", maxsplit=1)[0]
        if content_type.lower() != "application/json":
            self._write_json(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                {"error": "Only OTLP JSON with application/json is supported."},
            )
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid Content-Length."})
            return
        if content_length <= 0 or content_length > _MAX_REQUEST_BYTES:
            self._write_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"error": "Trace request body must be between 1 byte and 10 MiB."},
            )
            return
        try:
            payload = json.loads(self.rfile.read(content_length))
            with self.server.ingest_lock:
                import_trace_payloads(
                    payload,
                    format_name="otel",
                    out_dir=self.server.out_dir,
                    merge_existing=True,
                )
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid OTLP JSON payload."})
            return
        self._write_json(HTTPStatus.OK, {"partialSuccess": {}})

    def log_message(self, format: str, *args: object) -> None:
        """Suppress request logging so trace content cannot reach console logs."""

    def _write_json(self, status: HTTPStatus, payload: JsonDict) -> None:
        data = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def create_trace_server(*, host: str, port: int, out_dir: Path) -> TraceHTTPServer:
    """Create an in-process OTLP JSON receiver for tests or local embedding."""

    if not host.strip():
        raise ValueError("Trace receiver host cannot be empty")
    if not is_loopback_host(host):
        raise ValueError(
            "The unauthenticated trace receiver is local-only; use a loopback host."
        )
    if port < 0 or port > 65535:
        raise ValueError("Trace receiver port must be between 0 and 65535")
    return TraceHTTPServer((host, port), out_dir)


def serve_trace_http(*, host: str, port: int, out_dir: Path) -> None:
    """Serve the local shadow receiver until interrupted by the operator."""

    server = create_trace_server(host=host, port=port, out_dir=out_dir)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
