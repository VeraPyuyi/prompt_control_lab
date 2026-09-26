"""Serial, durable research jobs with owned child-process cancellation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any, cast

from promptcontrollab.core.files import absolute_path, stable_digest
from promptcontrollab.evaluation.experiments.storage import (
    JobLock,
    active_job,
    alive,
    event,
    read_json,
    write_json,
)

from .bundles import (
    bundle_directory,
    contained_directory,
    data_path,
    get_bundle,
    sha256,
    storage_directory,
    verify_bundle,
)
from .models import ResearchAnalysisSpec, ResearchJob
from .storage import state_lock

TERMINAL = {"completed", "cancelled", "interrupted", "failed"}


def job_directory(root: Path, identifier: str) -> Path:
    """Resolve the owned directory of a research job."""
    return contained_directory(root, "jobs", identifier)


def _save(directory: Path, job: ResearchJob) -> None:
    with state_lock(directory):
        _save_locked(directory, job)


def _save_locked(directory: Path, job: ResearchJob) -> None:
    job["updated_at"] = time.time()
    write_json(directory / "job.json", job)


def create_job(root: Path, document: dict[str, Any]) -> ResearchJob:
    """Freeze a supported analysis selection and persist its initial queue record."""
    if document.get("schema_version", "pcl.research-analysis/v1") != "pcl.research-analysis/v1":
        raise ValueError("Unsupported research analysis version")
    bundle = verify_bundle(root, document.get("bundle_id", ""))
    analyses = document.get("analyses", bundle["analyses"])
    if not isinstance(analyses, list) or not analyses or len(analyses) > 100:
        raise ValueError("Select between one and 100 analyses")
    if any(entry not in bundle["analyses"] for entry in analyses):
        raise ValueError("Choose an analysis supported by the imported data")
    if len({stable_digest(entry) for entry in analyses}) != len(analyses):
        raise ValueError("Duplicate analysis selection")
    spec: ResearchAnalysisSpec = {
        "schema_version": "pcl.research-analysis/v1",
        "bundle_id": bundle["id"],
        "analyses": analyses,
    }
    identifier = uuid.uuid4().hex[:24]
    directory = job_directory(root, identifier)
    directory.mkdir(parents=True)
    job = cast(
        ResearchJob,
        {
            "schema_version": "pcl.research-job/v1",
            "id": identifier,
            "status": "queued",
            "created_at": time.time(),
            "updated_at": time.time(),
            "spec": spec,
            "spec_sha256": stable_digest(spec),
            "bundle_sha256": stable_digest(bundle),
            "completed": {},
            "attempts": [],
            "error": None,
            "queue_owner_pid": os.getpid(),
            "progress": {"completed": 0, "total": len(analyses), "phase": "queued"},
        },
    )
    _save(directory, job)
    event(directory, "created", analyses=len(analyses))
    return job


def get_job(root: Path, identifier: str) -> ResearchJob:
    """Read a locked job snapshot and reconcile abandoned workers or queues."""
    with state_lock(job_directory(root, identifier)):
        return _get_job_locked(root, identifier)


def _get_job_locked(root: Path, identifier: str) -> ResearchJob:
    directory = job_directory(root, identifier)
    job = cast(ResearchJob, read_json(directory / "job.json"))
    if job["status"] == "queued" and not alive(job.get("queue_owner_pid")):
        job["status"] = "interrupted"
        job["progress"]["phase"] = "interrupted"
        job["error"] = "The previous queue owner exited; resume to schedule this analysis."
        _save_locked(directory, job)
    if job["status"] == "running":
        owner = active_job(absolute_path(root))
        if not owner or owner.get("id") != f"research-{identifier}":
            job["status"] = "interrupted"
            job["progress"]["phase"] = "interrupted"
            job["error"] = (
                "The previous worker exited; incomplete suites restart from their frozen inputs."
            )
            for attempt in job["attempts"]:
                if attempt["status"] == "running":
                    attempt.update(
                        status="interrupted",
                        interrupted_detected_at=time.time(),
                        elapsed_seconds=None,
                    )
            _save_locked(directory, job)
    if job["status"] == "queued" and (directory / "cancel.json").exists():
        job["status"] = "cancelled"
        job["progress"]["phase"] = "cancelled"
    return job


def list_jobs(root: Path) -> list[ResearchJob]:
    """Return research jobs in reverse creation order with reconciled states."""
    directory = storage_directory(root, "jobs")
    if not directory.exists():
        return []
    jobs = [
        get_job(root, path.name) for path in directory.iterdir() if (path / "job.json").is_file()
    ]
    return sorted(jobs, key=lambda item: item["created_at"], reverse=True)


def _verify_job(root: Path, job: ResearchJob) -> None:
    if stable_digest(job["spec"]) != job.get("spec_sha256"):
        raise ValueError("Research specification integrity check failed")
    bundle = verify_bundle(root, job["spec"]["bundle_id"])
    if stable_digest(bundle) != job.get("bundle_sha256"):
        raise ValueError("Research bundle inventory integrity check failed")
    directory = job_directory(root, job["id"])
    for unit, result in job["completed"].items():
        for name, digest in result["files"].items():
            path = data_path(directory / "units" / unit, name)
            if not path.is_file() or sha256(path) != digest:
                raise ValueError("Completed research output integrity check failed")


def cancel_job(root: Path, identifier: str) -> ResearchJob:
    """Persist a cancellation request without replacing a worker state snapshot."""
    directory = job_directory(root, identifier)
    with state_lock(directory):
        job = _get_job_locked(root, identifier)
        if job["status"] in TERMINAL:
            return job
        write_json(directory / "cancel.json", {"requested_at": time.time()})
        event(directory, "cancel_requested")
        return _get_job_locked(root, identifier)


def prepare_resume(root: Path, identifier: str) -> ResearchJob:
    """Verify frozen inputs and completed suites before requeuing stopped work."""
    with state_lock(job_directory(root, identifier)):
        return _prepare_resume_locked(root, identifier)


def _prepare_resume_locked(root: Path, identifier: str) -> ResearchJob:
    job = _get_job_locked(root, identifier)
    if job["status"] not in {"cancelled", "failed", "interrupted"}:
        raise ValueError("Only stopped research jobs can resume")
    _verify_job(root, job)
    directory = job_directory(root, identifier)
    (directory / "cancel.json").unlink(missing_ok=True)
    job["status"] = "queued"
    job["queue_owner_pid"] = os.getpid()
    job["error"] = None
    job["progress"]["phase"] = "queued"
    _save_locked(directory, job)
    event(directory, "resumed", completed=len(job["completed"]))
    return job


def _stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def record_admission_failure(root: Path, identifier: str, message: str) -> None:
    """Record a rejected queue attempt without replacing another worker's state."""
    directory = job_directory(root, identifier)
    with state_lock(directory):
        job = _get_job_locked(root, identifier)
        owner = active_job(absolute_path(root))
        if job["status"] != "queued" or (owner and owner.get("id") == f"research-{identifier}"):
            return
        job["status"] = "failed"
        job["progress"]["phase"] = "failed"
        job["error"] = message.replace(str(root), "[workspace]")[:1000]
        _save_locked(directory, job)
        event(directory, "admission_failed")


def run_job(root: Path, identifier: str) -> ResearchJob:
    """Execute allowlisted analyses, one owned child at a time, without model calls."""
    root = absolute_path(root)
    directory = job_directory(root, identifier)
    job = get_job(root, identifier)
    _verify_job(root, job)
    if job["status"] in {"completed", "cancelled"}:
        return job
    lease = JobLock(root, f"research-{identifier}")
    process: subprocess.Popen[bytes] | None = None
    try:
        job["status"] = "running"
        job["error"] = None
        _save(directory, job)
        for index, analysis in enumerate(job["spec"]["analyses"]):
            unit = f"unit-{index:03d}"
            if unit in job["completed"]:
                continue
            if (directory / "cancel.json").exists():
                job["status"] = "cancelled"
                break
            attempt: dict[str, Any] = {"unit": unit, "started_at": time.time(), "status": "running"}
            job["attempts"].append(attempt)
            temporary = directory / "attempts" / uuid.uuid4().hex
            temporary.mkdir(parents=True)
            write_json(
                temporary / "request.json",
                {
                    "analysis": analysis,
                    "bundle_id": job["spec"]["bundle_id"],
                    "parent_pid": os.getpid(),
                    "lease_token": lease.token,
                },
            )
            job["progress"] = {
                "completed": len(job["completed"]),
                "total": len(job["spec"]["analyses"]),
                "phase": analysis.get("suite", analysis["kind"]),
            }
            _save(directory, job)
            event(directory, "unit_started", unit=unit, analysis=analysis)
            env = {
                **os.environ,
                **dict.fromkeys(
                    (
                        "OMP_NUM_THREADS",
                        "OPENBLAS_NUM_THREADS",
                        "MKL_NUM_THREADS",
                        "NUMEXPR_NUM_THREADS",
                    ),
                    "1",
                ),
            }
            with (temporary / "worker.log").open("wb") as log:
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-B",
                        "-m",
                        "promptcontrollab.diagnostics.research_jobs.worker",
                        str(root),
                        identifier,
                        str(temporary),
                    ],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    env=env,
                    creationflags=0x08000000 if os.name == "nt" else 0,
                )
                while process.poll() is None:
                    if (directory / "cancel.json").exists():
                        _stop(process)
                        job["status"] = "cancelled"
                        break
                    time.sleep(0.1)
                code = process.wait()
            attempt.update(
                finished_at=time.time(), elapsed_seconds=time.time() - float(attempt["started_at"])
            )
            if job["status"] == "cancelled":
                attempt["status"] = "cancelled"
                break
            if code != 0:
                attempt["status"] = "failed"
                failure = (
                    read_json(temporary / "failure.json")
                    if (temporary / "failure.json").is_file()
                    else {}
                )
                raise ValueError(
                    str(failure.get("error", "Research worker exited before committing its result"))
                )
            result = read_json(temporary / "receipt.json")
            _verify_job(root, job)
            target = directory / "units" / unit
            target.parent.mkdir(exist_ok=True)
            # A previous crash may have left an uncommitted output directory.
            if target.exists():
                target.rename(directory / "attempts" / f"uncommitted-{uuid.uuid4().hex}")
            (temporary / "output").rename(target)
            files = {
                p.relative_to(target).as_posix(): sha256(p)
                for p in target.rglob("*")
                if p.is_file()
            }
            job["completed"][unit] = {"analysis": analysis, "result": result, "files": files}
            attempt["status"] = "completed"
            job["progress"]["completed"] = len(job["completed"])
            _save(directory, job)
            event(directory, "unit_completed", unit=unit)
        if job["status"] == "running":
            job["status"] = "completed"
        job["progress"]["phase"] = job["status"]
    except BaseException as error:
        if process is not None:
            _stop(process)
        job["status"] = (
            "interrupted" if isinstance(error, (KeyboardInterrupt, SystemExit)) else "failed"
        )
        job["error"] = str(error).replace(str(root), "[workspace]")[:1000]
        job["progress"]["phase"] = job["status"]
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
    finally:
        try:
            from .reporting import write_job_report

            with state_lock(directory):
                try:
                    _verify_job(root, job)
                    write_job_report(root, job)
                except (OSError, ValueError) as report_error:
                    job["error"] = (
                        job["error"] or str(report_error).replace(str(root), "[workspace]")[:1000]
                    )
                    if job["status"] == "completed":
                        job["status"] = "failed"
                        job["progress"]["phase"] = "failed"
                _save_locked(directory, job)
                event(directory, "stopped", status=job["status"])
        finally:
            lease.release()
    return job


def export_job(root: Path, identifier: str) -> Path:
    """Export verified data, specification and committed results using relative paths."""
    with state_lock(job_directory(root, identifier)):
        return _export_locked(root, _get_job_locked(root, identifier))


def _export_locked(root: Path, job: ResearchJob) -> Path:
    identifier = job["id"]
    _verify_job(root, job)
    _ensure_report_locked(root, job)
    directory = job_directory(root, identifier)
    bundle = get_bundle(root, job["spec"]["bundle_id"])
    data = bundle_directory(root, bundle["id"]) / "data"
    output = directory / "research.zip"
    temporary = directory / f".export-{uuid.uuid4().hex}.zip"
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            occupied = {row["path"].split("/", 1)[0].casefold() for row in bundle["files"]}
            metadata = "pcl-results"
            while metadata.casefold() in occupied:
                metadata = f"pcl-results-{uuid.uuid4().hex[:8]}"
            manifest = {
                key: bundle[key] for key in ("schema_version", "title", "synthetic", "files")
            }
            manifest["analyses"] = job["spec"]["analyses"]
            manifest["results_directory"] = metadata
            archive.writestr("research-bundle.json", json.dumps(manifest, ensure_ascii=False))
            archive.writestr(
                f"{metadata}/analysis-spec.json", json.dumps(job["spec"], ensure_ascii=False)
            )
            for row in bundle["files"]:
                archive.write(data_path(data, row["path"]), row["path"])
            for unit, result in job["completed"].items():
                for name in result["files"]:
                    archive.write(
                        data_path(directory / "units" / unit, name),
                        f"{metadata}/results/{unit}/{name}",
                    )
            for path in (directory / "report").glob("*"):
                if path.is_file():
                    archive.write(path, f"{metadata}/report/{path.name}")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return output


def ensure_report(root: Path, job: ResearchJob) -> None:
    """Rebuild a verified partial report after an abrupt parent exit."""
    with state_lock(job_directory(root, job["id"])):
        _ensure_report_locked(root, _get_job_locked(root, job["id"]))


def _ensure_report_locked(root: Path, job: ResearchJob) -> None:
    from .reporting import REPORT_FILES, write_job_report

    _verify_job(root, job)
    if job["status"] not in TERMINAL:
        raise ValueError("Research results are still being written")
    path = data_path(job_directory(root, job["id"]), "report/report.json")
    try:
        report = read_json(path) if path.is_file() else {}
        manifest = read_json(data_path(path.parent, "report-manifest.json"))
    except (ValueError, UnicodeError, FileNotFoundError):
        report = {}
        manifest = {}
    complete = set(manifest) == set(REPORT_FILES) and all(
        data_path(path.parent, name).is_file()
        and sha256(data_path(path.parent, name)) == manifest[name]
        for name in REPORT_FILES
    )
    if (
        not complete
        or report.get("status") != job["status"]
        or len(report.get("analyses", [])) != len(job["completed"])
    ):
        write_job_report(root, job)
