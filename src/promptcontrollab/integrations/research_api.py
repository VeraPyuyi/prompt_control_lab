"""Guarded streaming research imports and persistent analysis jobs."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from promptcontrollab.diagnostics.research_jobs import bundles, engine


def register_research_api(
    app: FastAPI, root: Path, local: Callable[..., None], pool: ThreadPoolExecutor
) -> None:
    """Register guarded streaming imports and persistent research job endpoints."""
    def error(exc: Exception) -> HTTPException:
        message = str(exc).replace(str(root), "[workspace]")[:1000]
        return HTTPException(404 if isinstance(exc, FileNotFoundError) else 422, message)

    def submit(identifier: str) -> None:
        def execute() -> None:
            try:
                engine.run_job(root, identifier)
            except Exception as exc:
                engine.record_admission_failure(root, identifier, str(error(exc).detail))

        pool.submit(execute)

    @app.get("/api/research-bundles")
    def list_bundles(request: Request) -> dict[str, Any]:
        local(request)
        return {"bundles": bundles.list_bundles(root)}

    @app.post("/api/research-bundles", status_code=201)
    async def import_bundle(request: Request, filename: str = "evidence.zip") -> Any:
        local(request, write=True)
        try:
            safe = bundles.safe_relative(filename)
            if "/" in safe:
                raise ValueError("Upload a file name, not a path")
        except ValueError as exc:
            raise error(exc) from exc
        uploads = bundles.storage_directory(root, "uploads")
        temporary = uploads / uuid.uuid4().hex
        temporary.mkdir(parents=True)
        source = temporary / safe
        try:
            size = 0
            with source.open("xb") as stream:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > bundles.MAX_UPLOAD:
                        raise HTTPException(413, "Research upload exceeds 64 MiB")
                    stream.write(chunk)
            return await asyncio.to_thread(bundles.import_bundle, root, source)
        except (ValueError, TypeError, OSError) as exc:
            raise error(exc) from exc
        finally:
            source.unlink(missing_ok=True)
            temporary.rmdir()

    @app.get("/api/research-bundles/{identifier}")
    def get_bundle(identifier: str, request: Request) -> Any:
        local(request)
        try:
            return bundles.get_bundle(root, identifier)
        except (ValueError, OSError) as exc:
            raise error(exc) from exc

    @app.get("/api/research-jobs")
    def list_jobs(request: Request) -> dict[str, Any]:
        local(request)
        return {"jobs": engine.list_jobs(root)}

    @app.post("/api/research-jobs", status_code=201)
    async def create_job(request: Request) -> Any:
        local(request, write=True)
        try:
            document = await request.json()
            if not isinstance(document, dict):
                raise ValueError("Research specification must be an object")
            job = engine.create_job(root, document)
            submit(job["id"])
            return job
        except (ValueError, TypeError, OSError) as exc:
            raise error(exc) from exc

    @app.get("/api/research-jobs/{identifier}")
    def status(identifier: str, request: Request) -> Any:
        local(request)
        try:
            return engine.get_job(root, identifier)
        except (ValueError, OSError) as exc:
            raise error(exc) from exc

    @app.post("/api/research-jobs/{identifier}/cancel")
    def cancel(identifier: str, request: Request) -> Any:
        local(request, write=True)
        try:
            return engine.cancel_job(root, identifier)
        except (ValueError, OSError) as exc:
            raise error(exc) from exc

    @app.post("/api/research-jobs/{identifier}/resume")
    def resume(identifier: str, request: Request) -> Any:
        local(request, write=True)
        try:
            job = engine.prepare_resume(root, identifier)
            submit(identifier)
            return job
        except (ValueError, OSError) as exc:
            raise error(exc) from exc

    @app.get("/api/research-jobs/{identifier}/events")
    async def events(identifier: str, request: Request, after: int = 0) -> StreamingResponse:
        local(request)
        if after < 0:
            raise HTTPException(422, "Event cursor must be nonnegative")
        try:
            engine.get_job(root, identifier)
            path = engine.job_directory(root, identifier) / "events.jsonl"
        except (ValueError, OSError) as exc:
            raise error(exc) from exc

        async def stream() -> AsyncIterator[str]:
            cursor = after
            while not await request.is_disconnected():
                lines = path.read_text(encoding="utf-8").splitlines()
                for index in range(cursor, len(lines)):
                    try:
                        json.loads(lines[index])
                    except json.JSONDecodeError:
                        break  # A concurrent append is not yet complete.
                    yield f"id: {index + 1}\ndata: {lines[index]}\n\n"
                    cursor = index + 1
                if engine.get_job(root, identifier)["status"] in engine.TERMINAL:
                    break
                yield ": heartbeat\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(
            stream(), media_type="text/event-stream", headers={"Cache-Control": "no-store"}
        )

    @app.get("/api/research-jobs/{identifier}/artifacts/{filename}")
    def artifact(identifier: str, filename: str, request: Request) -> FileResponse:
        local(request)
        if filename not in {
            "report.json",
            "metrics.csv",
            "report.en.html",
            "report.zh.html",
            "report.en.md",
            "report.zh.md",
            "research.zip",
        }:
            raise HTTPException(404, "Unknown research artifact")
        try:
            job = engine.get_job(root, identifier)
            if job["status"] not in engine.TERMINAL:
                raise HTTPException(409, "Research results are still being written")
            engine.ensure_report(root, job)
            path = (
                engine.export_job(root, identifier)
                if filename == "research.zip"
                else engine.job_directory(root, identifier) / "report" / filename
            )
            if not path.is_file():
                raise FileNotFoundError("Research artifact is not available")
            if path.is_symlink() or not path.resolve().is_relative_to(
                engine.job_directory(root, identifier).resolve()
            ):
                raise ValueError("Artifact path escapes research job")
            return FileResponse(
                path,
                filename=filename,
                headers={
                    "Content-Security-Policy": (
                        "default-src 'none'; style-src 'unsafe-inline'; img-src data:; sandbox"
                    )
                },
            )
        except (ValueError, OSError) as exc:
            raise error(exc) from exc
