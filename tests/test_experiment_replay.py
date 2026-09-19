"""Portable, offline replay recomputes raw evidence and rejects unsafe bundles."""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
import zipfile
from pathlib import Path
from typing import Any

import pytest

from promptcontrollab.evaluation.experiments import (
    create_experiment,
    export_experiment,
    run_experiment,
)
from promptcontrollab.evaluation.experiments import replay as replay_module
from promptcontrollab.evaluation.experiments.replay import replay_experiment
from promptcontrollab.evaluation.experiments.storage import job_directory


def _spec(count: int = 6) -> dict[str, Any]:
    return {
        "schema_version": "experiment/v1",
        "synthetic": True,
        "operation": "run",
        "data": [{"id": str(i), "input": f"task {i}", "expected": "yes"} for i in range(count)],
        "baseline": {
            "provider": "openai",
            "model": "offline",
            "prompt": "baseline",
            "max_output_tokens": 10,
        },
        "candidate": {
            "provider": "openai",
            "model": "offline",
            "prompt": "candidate",
            "max_output_tokens": 10,
        },
        "metric": "exact_match",
        "budget": {"max_calls": 100, "max_output_tokens": 1000, "max_seconds": 30},
    }


def _provider(**kwargs: Any) -> dict[str, Any]:
    return {
        "output_text": "yes" if kwargs["prompt"].startswith("candidate") else "no",
        "model_id": "offline",
        "usage": {"input_tokens": 2, "output_tokens": 1},
    }


def _job(tmp_path: Path, spec: dict[str, Any] | None = None) -> tuple[Path, dict[str, Any], Path]:
    root = tmp_path / "source-workspace"
    job = run_experiment(root, create_experiment(root, spec or _spec())["id"], _provider)
    archive = export_experiment(root, job["id"])
    return job_directory(root, job["id"]), job, archive


def _rewrite_zip(source: Path, target: Path, change: Any) -> None:
    with zipfile.ZipFile(source) as archive:
        files = {info.filename: archive.read(info) for info in archive.infolist()}
    change(files)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)


def test_export_receipts_cover_exact_package_bytes_and_exclude_self(tmp_path: Path) -> None:
    _, _, archive = _job(tmp_path)
    with zipfile.ZipFile(archive) as zipped:
        root = zipped.namelist()[0].split("/", 1)[0]
        receipt = json.loads(zipped.read(f"{root}/bundle_receipts.json"))
        assert "bundle_receipts.json" not in receipt["files"]
        assert len(receipt["files"]) == len(zipped.namelist()) - 1
        for name, expected in receipt["files"].items():
            assert hashlib.sha256(zipped.read(f"{root}/{name}")).hexdigest() == expected


def test_zip_replay_from_changed_working_directory_is_offline_and_exact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, job, archive = _job(tmp_path)
    relocated = tmp_path / "relocated" / "bundle.zip"
    relocated.parent.mkdir()
    shutil.copyfile(archive, relocated)
    monkeypatch.chdir(relocated.parent)
    monkeypatch.setattr(
        "socket.create_connection", lambda *a, **kw: pytest.fail("network forbidden")
    )
    monkeypatch.setattr(
        "promptcontrollab.evaluation.experiments.runtime.call_provider",
        lambda **kw: pytest.fail("provider forbidden"),
    )
    result = replay_experiment(Path("bundle.zip"), tmp_path / "out")
    assert result["integrity"]["status"] == "passed"
    assert result["numerical_replay"]["status"] == "passed"
    assert result["assessment_recomputed"] == job["assessment"]
    assert result["numerical_replay"]["assessment_differences"] == []
    assert not result["integrity"]["external_authenticity_verified"]
    assert not result["premise_checks"]["temporal_independence_verified"]
    serialized = json.dumps(result)
    assert str(tmp_path) not in serialized
    assert len(list((tmp_path / "out").iterdir())) == 8
    assert "<details>" in (tmp_path / "out/report.en.html").read_text(encoding="utf-8")
    assert "离线复算" in (tmp_path / "out/report.zh.html").read_text(encoding="utf-8")


def test_relocated_directory_and_zip_recompute_same_assessment(tmp_path: Path) -> None:
    source, _, archive = _job(tmp_path)
    moved = tmp_path / "other-location" / "saved-job"
    shutil.copytree(source, moved)
    first = replay_experiment(moved, tmp_path / "directory-out")
    second = replay_experiment(archive, tmp_path / "zip-out")
    assert first["assessment_recomputed"] == second["assessment_recomputed"]
    assert first["numerical_replay"] == second["numerical_replay"]
    assert first["integrity"]["status"] == "passed"


def test_missing_full_receipts_stays_partial_without_blocking_numeric_replay(
    tmp_path: Path,
) -> None:
    _, _, archive = _job(tmp_path)
    older = tmp_path / "older.zip"

    def omit(files: dict[str, bytes]) -> None:
        for name in list(files):
            if name.endswith("/bundle_receipts.json"):
                del files[name]

    _rewrite_zip(archive, older, omit)
    result = replay_experiment(older, tmp_path / "out")
    assert result["integrity"]["status"] == "partial"
    assert "spec.json" in result["integrity"]["uncovered_files"]
    assert result["numerical_replay"]["status"] == "passed"


def test_byte_mismatch_is_separate_from_numerical_agreement(tmp_path: Path) -> None:
    _, _, archive = _job(tmp_path)
    changed = tmp_path / "different-whitespace.zip"

    def rewrite(files: dict[str, bytes]) -> None:
        name = next(name for name in files if name.endswith("/spec.json"))
        files[name] = json.dumps(json.loads(files[name]), separators=(",", ":")).encode()

    _rewrite_zip(archive, changed, rewrite)
    result = replay_experiment(changed, tmp_path / "out")
    assert result["integrity"]["status"] == "failed"
    assert result["numerical_replay"]["status"] == "passed"


def test_saved_scores_are_recomputed_from_raw_output(tmp_path: Path) -> None:
    _, _, archive = _job(tmp_path)
    changed = tmp_path / "wrong-score.zip"

    def rewrite(files: dict[str, bytes]) -> None:
        name = next(name for name in files if "/records/" in name)
        row = json.loads(files[name])
        row["score"] = 1 - row["score"]
        files[name] = json.dumps(row).encode()

    _rewrite_zip(archive, changed, rewrite)
    result = replay_experiment(changed, tmp_path / "out")
    assert result["integrity"]["status"] == "failed"
    assert result["numerical_replay"]["status"] == "failed"
    assert any(row["status"] == "failed" for row in result["numerical_replay"]["score_checks"])
    assert result["assessment_recomputed"]["effect"]["statistics"]["mean_delta"] == 1


def test_raw_output_change_changes_assessment_and_breaks_call_link(tmp_path: Path) -> None:
    _, _, archive = _job(tmp_path)
    changed = tmp_path / "wrong-output.zip"

    def rewrite(files: dict[str, bytes]) -> None:
        for name in files:
            if "/records/" not in name:
                continue
            row = json.loads(files[name])
            if row["name"] == "candidate":
                row["output"] = "no"
                files[name] = json.dumps(row).encode()
                return

    _rewrite_zip(archive, changed, rewrite)
    result = replay_experiment(changed, tmp_path / "out")
    assert result["numerical_replay"]["assessment_differences"]
    assert any(row["status"] == "failed" for row in result["numerical_replay"]["record_call_links"])


def test_errors_empty_output_and_numeric_parse_failure_remain_distinct(tmp_path: Path) -> None:
    spec = _spec(3)
    spec.update(
        operation="import",
        metric="numeric_tolerance:0",
        predictions={
            "baseline": [{"id": "0", "output": "oops"}, {"id": "1", "error": "offline"}],
            "candidate": [
                {"id": "0", "output": "1"},
                {"id": "1", "output": ""},
                {"id": "2", "status": "timeout"},
            ],
        },
    )
    for task in spec["data"]:
        task["expected"] = "1"
    _, _, archive = _job(tmp_path, spec)
    result = replay_experiment(archive, tmp_path / "out")
    rows = {row["id"]: row for row in result["records_recomputed"]["baseline"]}
    assert rows["0"]["score"] == 0 and rows["0"]["output_status"] == "parse_error"
    assert rows["1"]["score"] is None and rows["1"]["status"] == "service_error"
    assert rows["2"]["score"] is None and rows["2"]["status"] == "missing"
    assert result["assessment_recomputed"]["coverage"]["matched"] == 1
    assert result["numerical_replay"]["status"] == "passed"


def test_format_error_replay_keeps_lower_is_better_and_grouped_inference(tmp_path: Path) -> None:
    spec = _spec()
    spec.update(
        operation="import",
        metric="format_error",
        predictions={
            "baseline": [{"id": str(i), "output": ""} for i in range(6)],
            "candidate": [{"id": str(i), "output": "yes"} for i in range(6)],
        },
    )
    for task in spec["data"]:
        task["meta"] = {"group": "shared"}
    _, _, archive = _job(tmp_path, spec)
    result = replay_experiment(archive, tmp_path / "out")
    effect = result["assessment_recomputed"]["effect"]
    assert effect["direction"] == "lower_is_better"
    assert effect["statistics"]["mean_delta"] == -1
    assert effect["statistics"]["bootstrap_ci"] is None
    assert effect["statistics"]["inference_status"] == "descriptive_only_nonindependent_rows"
    assert result["numerical_replay"]["status"] == "passed"


@pytest.mark.parametrize(
    "name", ["../escape.json", "/absolute.json", "C:/escape.json", "a\\b.json"]
)
def test_zip_rejects_traversal_and_absolute_paths(tmp_path: Path, name: str) -> None:
    source = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr(name, "{}")
    if "\\" in name:
        source.write_bytes(
            source.read_bytes().replace(name.replace("\\", "/").encode(), name.encode())
        )
    with pytest.raises(ValueError, match="unsafe path"):
        replay_experiment(source, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_zip_rejects_symlink_entries(tmp_path: Path) -> None:
    source = tmp_path / "symlink.zip"
    info = zipfile.ZipInfo("job/link.json")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr(info, "../../escape")
    with pytest.raises(ValueError, match="symlinks"):
        replay_experiment(source, tmp_path / "out")


def test_zip_enforces_uncompressed_size_and_entry_count_limits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "compressed.zip"
    with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("job/padding.json", "x" * 4096)
    monkeypatch.setattr(replay_module, "MAX_BUNDLE_BYTES", 1024)
    with pytest.raises(ValueError, match="byte limit"):
        replay_experiment(source, tmp_path / "out")
    monkeypatch.setattr(replay_module, "MAX_BUNDLE_FILES", 0)
    with pytest.raises(ValueError, match="file-count"):
        replay_experiment(source, tmp_path / "out")


def test_replay_never_writes_inside_original_directory(tmp_path: Path) -> None:
    directory, _, _ = _job(tmp_path)
    with pytest.raises(ValueError, match="outside"):
        replay_experiment(directory, directory / "recomputed")


def test_report_escapes_html_and_redacts_configured_secrets_and_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PCL_REPLAY_SECRET", "private-replay-value")
    spec = _spec(1)
    spec["baseline"]["api_key_env"] = "PCL_REPLAY_SECRET"
    spec["candidate"]["api_key_env"] = "PCL_REPLAY_SECRET"
    spec.update(
        operation="import",
        predictions={
            "baseline": [
                {
                    "id": "0",
                    "output": "<script>alert(1)</script> C:\\private\\file private-replay-value",
                }
            ],
            "candidate": [{"id": "0", "output": "yes"}],
        },
    )
    _, _, archive = _job(tmp_path, spec)
    result = replay_experiment(archive, tmp_path / "out")
    text = json.dumps(result)
    assert "private-replay-value" not in text and "C:\\\\private" not in text
    assert "<script>" not in (tmp_path / "out/report.en.html").read_text(encoding="utf-8")


def test_added_assessment_fields_and_changed_wording_do_not_fail_numerical_replay(
    tmp_path: Path,
) -> None:
    _, _, archive = _job(tmp_path)
    older = tmp_path / "older-report.zip"

    def rewrite(files: dict[str, bytes]) -> None:
        name = next(name for name in files if name.endswith("/job.json"))
        job = json.loads(files[name])
        job["assessment"] = {
            "effect": {"statistics": job["assessment"]["effect"]["statistics"]},
            "legacy_explanation": "Earlier wording.",
        }
        files[name] = json.dumps(job).encode()

    _rewrite_zip(archive, older, rewrite)
    result = replay_experiment(older, tmp_path / "out")
    assert result["numerical_replay"]["status"] == "passed"
    assert result["numerical_replay"]["assessment_differences"] == []
    assert result["numerical_replay"]["metadata_differences"]


def test_assessment_comparison_preserves_tolerance_null_and_missing_numeric_fields() -> None:
    numerical, metadata = replay_module._assessment_differences(
        {"mean": 0.0, "unavailable": None, "count": 2, "status": "old"},
        {"mean": 1e-12, "unavailable": 0.0, "status": "new", "added": 10},
    )
    assert {row["path"] for row in numerical} == {"$.unavailable", "$.count"}
    assert [row["path"] for row in metadata] == ["$.status"]


def test_imported_record_linkage_detects_changed_raw_text_even_with_equal_scores(
    tmp_path: Path,
) -> None:
    spec = _spec(1)
    spec.update(
        operation="import",
        predictions={
            "baseline": [{"id": "0", "output": "no"}],
            "candidate": [{"id": "0", "output": "yes"}],
        },
    )
    _, _, archive = _job(tmp_path, spec)
    changed = tmp_path / "changed-import.zip"

    def rewrite(files: dict[str, bytes]) -> None:
        for name in files:
            if "/records/" in name:
                row = json.loads(files[name])
                if row["name"] == "baseline":
                    row["output"] = "another wrong answer"
                    files[name] = json.dumps(row).encode()

    _rewrite_zip(archive, changed, rewrite)
    result = replay_experiment(changed, tmp_path / "out")
    assert result["numerical_replay"]["status"] == "passed"
    assert result["integrity"]["record_linkage"]["status"] == "failed"


def test_optimizer_replay_uses_frozen_candidate_and_whole_search_call_ledger(
    tmp_path: Path,
) -> None:
    pytest.importorskip("gepa")
    spec = _spec(10)
    spec.update(
        operation="optimize", max_concurrency=1, optimization={"max_rounds": 1, "patience": 1}
    )
    spec["budget"].update(
        max_output_tokens=100000,
        max_seconds=60,
        input_cost_per_million=1.0,
        output_cost_per_million=2.0,
    )
    root = tmp_path / "source"

    def provider(**kwargs: Any) -> dict[str, Any]:
        if "Training examples and feedback:" in kwargs["prompt"]:
            return {
                "output_text": "```\ncandidate\n```",
                "usage": {"input_tokens": 3, "output_tokens": 2},
            }
        return _provider(**kwargs)

    job = run_experiment(root, create_experiment(root, spec)["id"], provider)
    assert job["status"] == "completed", job.get("error")
    result = replay_experiment(export_experiment(root, job["id"]), tmp_path / "out")
    assert result["numerical_replay"]["status"] == "passed", result["numerical_replay"][
        "assessment_differences"
    ]
    assert result["assessment_recomputed"]["effect"] == job["assessment"]["effect"]
    assert result["assessment_recomputed"]["cost"]["calls"] == job["budget"]["calls"]
    assert result["assessment_recomputed"]["cost"]["known_cost"] == pytest.approx(
        job["budget"]["known_cost"]
    )
    assert result["premise_checks"]["status"] == "passed"
    assert not result["premise_checks"]["temporal_independence_verified"]
