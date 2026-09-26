"""Local-session experiment API. Jobs execute typed operations, never shell commands."""

from __future__ import annotations

import asyncio
import hmac
import json
import os
import re
import secrets
import time
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from promptcontrollab.integrations.experiment_inputs import parse_dataset


def register_experiment_api(app: FastAPI, root: Path, deployment_mode: str) -> None:
    """Register guarded local experiment routes and their background worker."""
    token = secrets.token_urlsafe(32)
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pcl-experiment")
    app.state.experiment_pool = pool
    credential_values: dict[str, str] = {}

    def local(request: Request, *, write: bool = False) -> None:
        if deployment_mode == "hf_demo":
            raise HTTPException(403, "Experiments are disabled in the public demo")
        if request.url.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise HTTPException(403, "Use the local loopback address")
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
            raise HTTPException(403, "Cross-origin requests are not allowed")
        if write and not hmac.compare_digest(
            request.headers.get("x-pcl-session", "").encode(), token.encode()
        ):
            raise HTTPException(403, "Local session token required; reload this page")

    class LocalSessionGuard:
        """Guard legacy and new routes before body parsing or route dispatch."""

        def __init__(self, app: ASGIApp):
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return
            request = Request(scope)
            write = request.method not in {"GET", "HEAD", "OPTIONS"}
            try:
                if deployment_mode == "hf_demo":
                    if write:
                        raise HTTPException(403, "The public demo is read-only")
                else:
                    local(request, write=write)
            except HTTPException as exc:
                await JSONResponse({"detail": exc.detail}, status_code=exc.status_code)(
                    scope, receive, send
                )
                return
            if not write:
                await self.app(scope, receive, send)
                return
            if request.url.path == "/api/research-bundles" and request.method == "POST":
                # This route enforces a separate streaming limit after the same
                # host, origin and session checks. Never buffer a ZIP in memory.
                await self.app(scope, receive, send)
                return
            maximum = 6_000_000
            length = request.headers.get("content-length")
            if length:
                try:
                    declared = int(length)
                except ValueError:
                    declared = -1
                if declared < 0 or declared > maximum:
                    await JSONResponse(
                        {"detail": "Input exceeds 6 MB or has invalid length"}, status_code=413
                    )(scope, receive, send)
                    return
            chunks: list[bytes] = []
            size = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                size += len(chunk)
                if size > maximum:
                    await JSONResponse({"detail": "Input exceeds 6 MB"}, status_code=413)(
                        scope, receive, send
                    )
                    return
                chunks.append(chunk)
                if not message.get("more_body", False):
                    break
            body = b"".join(chunks)
            replayed = False

            async def replay() -> Message:
                nonlocal replayed
                if replayed:
                    return await receive()
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}

            await self.app(scope, replay, send)

    app.add_middleware(LocalSessionGuard)

    from promptcontrollab.integrations.research_api import register_research_api

    register_research_api(app, root, local, pool)

    def clean_error(exc: Exception) -> str:
        message = str(exc)
        for value in credential_values.values():
            if value:
                message = message.replace(value, "[redacted]")
        return message[:2000]

    async def document(request: Request) -> dict[str, Any]:
        local(request, write=True)
        body = await request.body()
        if len(body) > 6_000_000:
            raise HTTPException(413, "Input exceeds 6 MB")
        try:
            value = json.loads(body)
        except (ValueError, UnicodeError) as exc:
            raise HTTPException(422, "Expected UTF-8 JSON") from exc
        if not isinstance(value, dict):
            raise HTTPException(422, "Expected a JSON object")
        return value

    def job_path(job_id: str) -> Path:
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", job_id):
            raise HTTPException(404, "Unknown experiment")
        path = root / ".pcl" / "experiments" / job_id
        if not path.is_dir() or not path.resolve().is_relative_to(
            (root / ".pcl" / "experiments").resolve()
        ):
            raise HTTPException(404, "Unknown experiment")
        return path

    def submit(job_id: str) -> None:
        from promptcontrollab.evaluation.experiments import run_experiment

        def execute() -> None:
            try:
                run_experiment(root, job_id)
            except Exception as exc:
                # Admission can fail before the engine marks the job running,
                # e.g. a CLI process owns the shared lease. Persist that failure.
                from promptcontrollab.evaluation.experiments.storage import (
                    event,
                    job_directory,
                    read_json,
                    write_json,
                )

                directory = job_directory(root, job_id)
                job = read_json(directory / "job.json")
                if job["status"] in {"queued", "running", "cancelling"}:
                    job.update(
                        status="stopped",
                        stop_reason="worker_admission_failed",
                        error=clean_error(exc),
                        error_type=type(exc).__name__,
                        updated_at=time.time(),
                        finished_at=time.time(),
                    )
                    write_json(directory / "job.json", job)
                    event(
                        directory,
                        "worker_stopped",
                        reason="worker_admission_failed",
                        error_type=type(exc).__name__,
                    )

        pool.submit(execute)

    @app.get("/api/session")
    def session(request: Request) -> JSONResponse:
        if deployment_mode == "hf_demo":
            return JSONResponse(
                {"enabled": False, "token": None}, headers={"Cache-Control": "no-store"}
            )
        local(request)
        return JSONResponse(
            {"enabled": True, "token": token}, headers={"Cache-Control": "no-store"}
        )

    @app.post("/api/credentials")
    async def credentials(request: Request) -> dict[str, str]:
        payload = await document(request)
        value = payload.get("key")
        if not isinstance(value, str) or not value.strip() or len(value) > 8192:
            raise HTTPException(422, "Enter an API key")
        reference = payload.get("reference") or f"PCL_SESSION_{secrets.token_hex(16).upper()}"
        if not isinstance(reference, str) or not re.fullmatch(
            r"PCL_SESSION_[A-F0-9]{32}", reference
        ):
            raise HTTPException(422, "Invalid credential reference")
        os.environ[reference] = value.strip()
        credential_values[reference] = value.strip()
        return {"api_key_env": reference, "storage": "process_memory"}

    @app.post("/api/experiments/parse-data")
    async def parse_data(request: Request) -> dict[str, Any]:
        payload = await document(request)
        try:
            records = parse_dataset(
                payload.get("text", ""), payload.get("format", "jsonl"), payload.get("mapping")
            )
        except (ValueError, TypeError, AttributeError) as exc:
            raise HTTPException(422, clean_error(exc)) from exc
        return {"data": records, "count": len(records)}

    @app.post("/api/experiments/normalize-import")
    async def normalize_import(request: Request) -> dict[str, Any]:
        payload = await document(request)
        from promptcontrollab.integrations.experiment_imports import normalize_import_document

        try:
            return normalize_import_document(payload, root / ".pcl" / "imports")
        except (ValueError, TypeError, OSError) as exc:
            raise HTTPException(422, clean_error(exc)) from exc

    @app.get("/api/experiments")
    def experiments(request: Request) -> dict[str, Any]:
        local(request)
        from promptcontrollab.evaluation.experiments import list_experiments

        return {"experiments": list_experiments(root)}

    @app.get("/api/research-examples/{kind}")
    def example(kind: str, request: Request, version: int = 1) -> dict[str, Any]:
        if deployment_mode != "hf_demo":
            local(request)
        if version not in {1, 2}:
            raise HTTPException(422, "Choose research example version 1 or 2")
        if kind not in {"readout", "response", "measurement-value", "transfer", "replay"}:
            raise HTTPException(404, "Unknown research tool")
        packaged = files("promptcontrollab").joinpath("example_data").joinpath("research")
        if version == 2:
            packaged = packaged.joinpath("a2")
        packaged = packaged.joinpath(f"{kind}.json")
        if packaged.is_file():
            return cast(dict[str, Any], json.loads(packaged.read_text(encoding="utf-8")))
        example_directory = Path(__file__).resolve().parents[3] / "examples"
        source = (
            example_directory
            / ("research/a2" if version == 2 else "research-tools")
            / f"{kind}.json"
        )
        if source.is_file():
            return cast(dict[str, Any], json.loads(source.read_text(encoding="utf-8")))
        raise HTTPException(404, "Example unavailable; reinstall the complete package")

    @app.post("/api/experiments", status_code=201)
    async def create(request: Request) -> dict[str, Any]:
        payload = await document(request)
        from promptcontrollab.evaluation.experiments import create_experiment

        try:
            job = create_experiment(root, payload)
        except (ValueError, TypeError, OSError) as exc:
            raise HTTPException(422, clean_error(exc)) from exc
        submit(job["id"])
        return job

    @app.get("/api/experiments/{job_id}")
    def detail(job_id: str, request: Request) -> dict[str, Any]:
        local(request)
        job_path(job_id)
        from promptcontrollab.evaluation.experiments import get_experiment

        return get_experiment(root, job_id)

    @app.post("/api/experiments/{job_id}/{action}")
    async def manage(job_id: str, action: str, request: Request) -> dict[str, Any]:
        payload = await document(request)
        job_path(job_id)
        from promptcontrollab.evaluation.experiments import cancel_experiment, prepare_resume

        try:
            if action == "cancel":
                return cancel_experiment(root, job_id)
            if action == "resume":
                retry_failed = payload.get("retry_failed", False)
                if not isinstance(retry_failed, bool):
                    raise HTTPException(422, "retry_failed must be true or false")
                job = prepare_resume(root, job_id, retry_failed=retry_failed)
                submit(job_id)
                return job
        except (ValueError, OSError, RuntimeError) as exc:
            raise HTTPException(409, clean_error(exc)) from exc
        raise HTTPException(404, "Unknown operation")

    @app.get("/api/experiments/{job_id}/events")
    async def events(job_id: str, request: Request, after: int = 0) -> StreamingResponse:
        local(request)
        path = job_path(job_id) / "events.jsonl"

        async def stream() -> AsyncIterator[str]:
            cursor = max(0, after)
            while not await request.is_disconnected():
                lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
                for line in lines[cursor : cursor + 500]:
                    cursor += 1
                    yield f"id: {cursor}\ndata: {line}\n\n"
                yield ": heartbeat\n\n"
                await asyncio.sleep(1)

        return StreamingResponse(
            stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
        )

    @app.get("/api/experiments/{job_id}/artifacts/{filename}")
    def artifact(job_id: str, filename: str, request: Request) -> FileResponse:
        local(request)
        directory = job_path(job_id)
        allowed = {
            "report.en.html",
            "report.zh.html",
            "report.json",
            "summary.json",
            "records.json",
            "records.csv",
            "predictions.csv",
            "experiment.zip",
            "assessment.json",
            "comparison_assessment.json",
        }
        if filename not in allowed:
            raise HTTPException(404, "Unknown artifact")
        if filename == "experiment.zip":
            from promptcontrollab.evaluation.experiments import export_experiment

            try:
                export_experiment(root, job_id)
            except ValueError as exc:
                raise HTTPException(409, clean_error(exc)) from exc
        for base in (directory / "report", directory):
            path = base / filename
            if path.is_file() and path.resolve().is_relative_to(directory.resolve()):
                headers = {
                    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; "
                    "img-src data:; sandbox"
                }
                return FileResponse(path, filename=filename, headers=headers)
        raise HTTPException(404, "Artifact is not ready")

    @app.post("/api/research/{kind}")
    async def research(kind: str, request: Request) -> dict[str, Any]:
        payload = await document(request)
        from promptcontrollab.diagnostics.research_tools import analyze_research

        if kind not in {"readout", "response", "measurement-value", "transfer", "replay"}:
            raise HTTPException(404, "Unknown research tool")
        identifier = secrets.token_hex(12)
        try:
            result = await asyncio.to_thread(
                analyze_research, kind, payload, root / ".pcl" / "research" / identifier
            )
        except (ValueError, TypeError, OSError) as exc:
            raise HTTPException(422, clean_error(exc)) from exc
        return {"id": identifier, "result": result}

    @app.get("/api/research/{identifier}/artifacts/{filename}")
    def research_artifact(identifier: str, filename: str, request: Request) -> FileResponse:
        local(request)
        if not re.fullmatch(r"[a-f0-9]{24}", identifier) or filename not in {
            "report.json",
            "metrics.csv",
            "report.en.html",
            "report.zh.html",
            "report.en.md",
            "report.zh.md",
        }:
            raise HTTPException(404, "Unknown artifact")
        path = root / ".pcl" / "research" / identifier / filename
        if not path.is_file() or not path.resolve().is_relative_to(
            (root / ".pcl" / "research").resolve()
        ):
            raise HTTPException(404, "Artifact not ready")
        return FileResponse(
            path,
            filename=filename,
            headers={
                "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox"
            },
        )
