"""Persistent research execution, recovery and portable replay."""

from __future__ import annotations

import json
import threading
import time
import zipfile
from pathlib import Path
from typing import Any

import pytest

from promptcontrollab.diagnostics.research_jobs.bundles import import_bundle
from promptcontrollab.diagnostics.research_jobs.engine import (
    cancel_job,
    create_job,
    export_job,
    get_job,
    job_directory,
    prepare_resume,
    run_job,
)


def _job(root: Path, kind: str = "readout") -> dict[str, Any]:
    source = Path(__file__).parents[1] / f"examples/research-tools/{kind}.json"
    bundle = import_bundle(root, source)
    return dict(create_job(root, {"bundle_id": bundle["id"]}))


def test_real_subprocess_job_reports_and_portable_inputs(tmp_path: Path) -> None:
    job = _job(tmp_path)
    result = run_job(tmp_path, job["id"])
    assert result["status"] == "completed", result
    assert result["progress"]["completed"] == 1
    directory = job_directory(tmp_path, job["id"])
    assert (directory / "report/report.zh.html").is_file()
    portable = export_job(tmp_path, job["id"])
    bundle = import_bundle(tmp_path / "relocated", portable)
    moved = create_job(tmp_path / "relocated", {"bundle_id": bundle["id"]})
    replayed = run_job(tmp_path / "relocated", moved["id"])
    assert replayed["status"] == "completed"
    first = json.loads((directory / "units/unit-000/report.json").read_text(encoding="utf-8"))
    second = json.loads(
        (
            job_directory(tmp_path / "relocated", moved["id"]) / "units/unit-000/report.json"
        ).read_text(encoding="utf-8")
    )
    assert first == second


def test_deep_archive_members_replay_after_relocation(tmp_path: Path) -> None:
    source = Path(__file__).parents[1] / "examples/research-tools/readout.json"
    member = "/".join(["nested-evidence-directory"] * 9 + ["readout.json"])
    archive_path = tmp_path / "deep-input.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(member, source.read_bytes())
    bundle = import_bundle(tmp_path, archive_path)
    job = create_job(tmp_path, {"bundle_id": bundle["id"]})
    first = run_job(tmp_path, job["id"])
    assert first["status"] == "completed", first
    exported = export_job(tmp_path, job["id"])
    moved_root = tmp_path / "another-directory"
    moved = import_bundle(moved_root, exported)
    assert moved["files"][0]["path"] == member
    second = run_job(moved_root, create_job(moved_root, {"bundle_id": moved["id"]})["id"])
    assert second["status"] == "completed", second
    assert first["completed"]["unit-000"]["result"] == second["completed"]["unit-000"]["result"]


def test_deep_workspace_shares_lease_with_legacy_experiments(tmp_path: Path) -> None:
    from promptcontrollab.core.files import absolute_path
    from promptcontrollab.evaluation.experiments.storage import JobLock, active_job

    workspace = tmp_path.joinpath(*(["deep-workspace-segment"] * 12))
    lease = JobLock(absolute_path(workspace), "research-owner")
    try:
        assert active_job(workspace)["id"] == "research-owner"  # type: ignore[index]
        with pytest.raises(RuntimeError, match="active"):
            JobLock(workspace, "second-owner")
    finally:
        lease.release()
    assert active_job(workspace) is None


def test_queued_cancel_and_resume_does_not_repeat_completed_units(tmp_path: Path) -> None:
    job = _job(tmp_path)
    cancel_job(tmp_path, job["id"])
    assert run_job(tmp_path, job["id"])["status"] == "cancelled"
    prepare_resume(tmp_path, job["id"])
    result = run_job(tmp_path, job["id"])
    assert result["status"] == "completed"
    count = len(result["attempts"])
    assert run_job(tmp_path, job["id"])["status"] == "completed"
    assert len(get_job(tmp_path, job["id"])["attempts"]) == count


def test_cancel_running_unit_and_restart_frozen_unit(tmp_path: Path) -> None:
    job = _job(tmp_path)
    errors = []

    def run() -> None:
        try:
            run_job(tmp_path, job["id"])
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=run)
    worker.start()
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        state = get_job(tmp_path, job["id"])
        if state["status"] in {"running", "completed"}:
            break
        time.sleep(0.02)
    cancel_job(tmp_path, job["id"])
    worker.join(20)
    assert not worker.is_alive() and not errors
    state = get_job(tmp_path, job["id"])
    assert state["status"] in {"cancelled", "completed"}
    if state["status"] == "cancelled":
        prepare_resume(tmp_path, job["id"])
        assert run_job(tmp_path, job["id"])["status"] == "completed"


def test_spec_and_completed_output_tampering_rejected(tmp_path: Path) -> None:
    job = _job(tmp_path)
    assert run_job(tmp_path, job["id"])["status"] == "completed"
    directory = job_directory(tmp_path, job["id"])
    (directory / "units/unit-000/report.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        export_job(tmp_path, job["id"])


def test_arbitrary_operation_or_input_is_rejected(tmp_path: Path) -> None:
    job = _job(tmp_path)
    for analysis in (
        {"kind": "shell", "command": "anything"},
        {"kind": "readout", "input": "../outside.json"},
    ):
        with pytest.raises(ValueError):
            create_job(tmp_path, {"bundle_id": job["spec"]["bundle_id"], "analyses": [analysis]})


def test_export_metadata_never_collides_with_input_names(tmp_path: Path) -> None:
    source = tmp_path / "analysis-spec.json"
    example = Path(__file__).parents[1] / "examples/research-tools/readout.json"
    source.write_bytes(example.read_bytes())
    bundle = import_bundle(tmp_path, source)
    job = create_job(tmp_path, {"bundle_id": bundle["id"]})
    assert run_job(tmp_path, job["id"])["status"] == "completed"
    archive_path = export_job(tmp_path, job["id"])
    with zipfile.ZipFile(archive_path) as archive:
        assert len(archive.namelist()) == len(set(archive.namelist()))
    moved = import_bundle(tmp_path / "moved", archive_path)
    assert moved["analyses"] == bundle["analyses"]


def test_orphaned_queue_is_resumable_even_with_an_unrelated_active_job(tmp_path: Path) -> None:
    from promptcontrollab.evaluation.experiments.storage import JobLock, write_json

    job = _job(tmp_path)
    job["queue_owner_pid"] = -1
    write_json(job_directory(tmp_path, job["id"]) / "job.json", job)
    lease = JobLock(tmp_path, "unrelated")
    try:
        assert get_job(tmp_path, job["id"])["status"] == "interrupted"
        assert prepare_resume(tmp_path, job["id"])["status"] == "queued"
    finally:
        lease.release()


def test_partial_failure_keeps_completed_reports_and_summary_values(tmp_path: Path) -> None:
    source = tmp_path / "partial.zip"
    example = Path(__file__).parents[1] / "examples/research-tools/readout.json"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("a-good.json", example.read_bytes())
        archive.writestr(
            "b-invalid.json",
            json.dumps(
                {"schema_version": "readout-sensitivity/v1", "synthetic": True, "records": []}
            ),
        )
    bundle = import_bundle(tmp_path, source)
    job = create_job(tmp_path, {"bundle_id": bundle["id"]})
    result = run_job(tmp_path, job["id"])
    assert result["status"] == "failed" and len(result["completed"]) == 1
    report = job_directory(tmp_path, job["id"]) / "report/report.json"
    assert json.loads(report.read_text(encoding="utf-8"))["status"] == "failed"
    csv_path = tmp_path / "summary.csv"
    csv_path.write_text("model,accuracy\na,0.5\nb,0.8\n", encoding="utf-8")
    bundle = import_bundle(tmp_path, csv_path)
    job = create_job(tmp_path, {"bundle_id": bundle["id"]})
    assert run_job(tmp_path, job["id"])["status"] == "completed"
    page = (job_directory(tmp_path, job["id"]) / "report/report.en.html").read_text(
        encoding="utf-8"
    )
    assert "0.5" in page and "0.8" in page


def test_cancel_does_not_overwrite_a_completed_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from promptcontrollab.diagnostics.research_jobs import engine
    from promptcontrollab.evaluation.experiments.storage import read_json, write_json

    job = _job(tmp_path)
    path = job_directory(tmp_path, job["id"]) / "job.json"
    original = engine._get_job_locked
    first = True

    def stale_once(root: Path, identifier: str) -> Any:
        nonlocal first
        value = original(root, identifier)
        if first:
            first = False
            # Inject a completed write at the former lost-update boundary.
            latest = dict(value, status="completed", completed={"unit-000": {"sentinel": True}})
            write_json(path, latest)
        return value

    monkeypatch.setattr(engine, "_get_job_locked", stale_once)
    assert cancel_job(tmp_path, job["id"])["status"] == "completed"
    assert read_json(path)["completed"] == {"unit-000": {"sentinel": True}}


def test_missing_truncated_or_corrupt_reports_are_rebuilt(tmp_path: Path) -> None:
    from promptcontrollab.diagnostics.research_jobs.engine import ensure_report

    job = _job(tmp_path)
    done = run_job(tmp_path, job["id"])
    report = job_directory(tmp_path, job["id"]) / "report"
    (report / "report.en.html").unlink()
    ensure_report(tmp_path, done)
    assert "Research evidence report" in (report / "report.en.html").read_text(encoding="utf-8")
    (report / "report.json").write_text("{", encoding="utf-8")
    (report / "report.zh.html").write_text("partial", encoding="utf-8")
    ensure_report(tmp_path, done)
    assert json.loads((report / "report.json").read_text(encoding="utf-8"))["status"] == "completed"
    assert "研究证据报告" in (report / "report.zh.html").read_text(encoding="utf-8")


def test_rejected_duplicate_dispatch_cannot_overwrite_active_or_completed_job(
    tmp_path: Path,
) -> None:
    from promptcontrollab.diagnostics.research_jobs.engine import record_admission_failure
    from promptcontrollab.evaluation.experiments.storage import JobLock

    job = _job(tmp_path)
    lease = JobLock(tmp_path, f"research-{job['id']}")
    try:
        record_admission_failure(tmp_path, job["id"], "duplicate dispatch")
        assert get_job(tmp_path, job["id"])["status"] == "queued"
    finally:
        lease.release()
    done = run_job(tmp_path, job["id"])
    record_admission_failure(tmp_path, job["id"], "late dispatch error")
    assert get_job(tmp_path, job["id"]) == done
    second = _job(tmp_path)
    record_admission_failure(tmp_path, second["id"], "cannot acquire execution slot")
    assert get_job(tmp_path, second["id"])["status"] == "failed"


def test_saved_research_tables_remain_display_only_and_never_execute_scripts(
    tmp_path: Path,
) -> None:
    source = tmp_path / "tables.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("supporting_analysis/data/probe_control.csv", "rank,auc\n4,0.55\n")
        archive.writestr("supporting_analysis/data/batch_cost.csv", "batch,seconds\n8,0.12\n")
        archive.writestr("supporting_analysis/run.py", "raise RuntimeError('never execute')")
    before = source.read_bytes()
    bundle = import_bundle(tmp_path, source)
    analyses = [entry for entry in bundle["analyses"] if entry["kind"] == "saved-summary"]
    assert {entry["tool"] for entry in analyses} == {"response", "measurement-value"}
    job = create_job(tmp_path, {"bundle_id": bundle["id"], "analyses": analyses})
    result = run_job(tmp_path, job["id"])
    assert result["status"] == "completed", result
    for value in result["completed"].values():
        assert value["result"]["raw_recomputation"] is False
        assert value["result"]["numerical_agreement"] == "not_tested"
    report = job_directory(tmp_path, job["id"]) / "report"
    assert "0.55" in (report / "report.en.html").read_text(encoding="utf-8")
    assert "0.12" in (report / "report.zh.html").read_text(encoding="utf-8")
    assert source.read_bytes() == before


@pytest.mark.parametrize(
    "name",
    [path.name for path in (Path(__file__).parents[1] / "examples/research/a2").glob("*.json")],
)
def test_v2_examples_run_through_bundle_worker(tmp_path: Path, name: str) -> None:
    bundle = import_bundle(tmp_path, Path(__file__).parents[1] / "examples/research/a2" / name)
    assert bundle["synthetic"] is True
    job = create_job(tmp_path, {"bundle_id": bundle["id"]})
    result = run_job(tmp_path, job["id"])
    assert result["status"] == "completed", result
