from __future__ import annotations

import csv
import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

from promptcontrollab.core.files import read_json
from promptcontrollab.integrations.ui.data import list_runs


def _builder() -> ModuleType:
    path = Path("scripts/build_change_review_cases.py")
    spec = importlib.util.spec_from_file_location("pcl_change_review_case_builder", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_checkpoint_case_preserves_docs_and_reproduces_real_aggregate(tmp_path: Path) -> None:
    builder = _builder()
    out_dir = tmp_path / "case"
    out_dir.mkdir()
    authored = out_dir / "README.md"
    authored.write_text("authored case guide", encoding="utf-8")

    case = builder.build_checkpoint_case(
        source_dir=Path("docs/case_studies/sft_checkpoint_pilot"),
        out_dir=out_dir,
    )

    assert authored.read_text(encoding="utf-8") == "authored case guide"
    assert case["seed_count"] == 3
    assert case["checkpoint_count"] == 9
    assert case["decision"] == "hold"
    assert case["observed"]["baseline_mean_score"] == 0.088541666667
    assert case["observed"]["candidate_mean_score"] == 0.194444444444
    review = read_json(out_dir / "review" / "change_review.json")
    assert review["change_kind"] == "checkpoint_change"
    assert review["baseline_run"] == "../baseline"
    assert review["candidate_run"] == "../candidate"


def test_committed_checkpoint_case_contains_no_private_absolute_paths() -> None:
    case_dir = Path("docs/case_studies/checkpoint_change_review")
    payload = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(case_dir.rglob("*"))
        if path.is_file() and path.suffix in {".json", ".md", ".html"}
    )

    assert "D:\\" not in payload
    assert "/root/" not in payload
    assert "\\.worktrees\\" not in payload


def test_model_case_reproduces_real_cross_model_aggregate(tmp_path: Path) -> None:
    builder = _builder()

    case = builder.build_model_case(
        source_case=Path("docs/case_studies/peoc_real/research_case_study.json"),
        out_dir=tmp_path / "model-case",
    )

    assert case["source_model_count"] == 3
    assert case["task_count"] == 4
    assert case["method_count"] == 6
    assert case["aggregation_units_per_model"] == 24
    assert case["source_replicates_per_model"] == 240
    assert case["observed"]["baseline_mean_score"] == 0.441780598958
    assert case["observed"]["candidate_mean_score"] == 0.445068359375
    assert case["decision"] == "needs_review"
    review = read_json(tmp_path / "model-case" / "review" / "change_review.json")
    assert review["change_kind"] == "model_change"
    assert review["decision"] == "needs_review"
    report = (tmp_path / "model-case" / "review" / "report.md").read_text(
        encoding="utf-8"
    )
    assert str(review["next_action"]) in report
    assert str(review["claim_boundary"]) in report
    assert (tmp_path / "model-case" / "comparison.en.svg").is_file()
    assert (tmp_path / "model-case" / "comparison.zh.svg").is_file()
    assert not (tmp_path / "model-case" / "review" / "stats.json").exists()


def test_agent_case_builds_prompt_change_review_from_real_execution_rows(
    tmp_path: Path,
) -> None:
    builder = _builder()
    pilot_csv = tmp_path / "pilot.csv"
    rows = [
        {
            "task_id": "task-1-trial-01",
            "base_task_id": "task-1",
            "trial": "1",
            "agent": "codex-local-exec",
            "raw_success": "true",
            "guarded_success": "true",
            "raw_tests_passed": "true",
            "guarded_tests_passed": "true",
            "raw_touched_files": "2",
            "guarded_touched_files": "1",
            "raw_unnecessary_file_edits": "1",
            "guarded_unnecessary_file_edits": "0",
            "raw_total_tokens": "1200",
            "guarded_total_tokens": "900",
            "raw_tool_calls": "4",
            "guarded_tool_calls": "3",
            "raw_duration_seconds": "10.5",
            "guarded_duration_seconds": "9.0",
        },
        {
            "task_id": "task-2-trial-01",
            "base_task_id": "task-2",
            "trial": "1",
            "agent": "codex-local-exec",
            "raw_success": "false",
            "guarded_success": "true",
            "raw_tests_passed": "false",
            "guarded_tests_passed": "true",
            "raw_touched_files": "1",
            "guarded_touched_files": "1",
            "raw_unnecessary_file_edits": "0",
            "guarded_unnecessary_file_edits": "0",
            "raw_total_tokens": "1000",
            "guarded_total_tokens": "1100",
            "raw_tool_calls": "3",
            "guarded_tool_calls": "4",
            "raw_duration_seconds": "8.0",
            "guarded_duration_seconds": "11.0",
        },
    ]
    with pilot_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    case = builder.build_agent_case(pilot_csv=pilot_csv, out_dir=tmp_path / "case")

    assert case["execution_count"] == 4
    assert case["task_count"] == 2
    assert case["observed"]["raw_success_rate"] == 0.5
    assert case["observed"]["guarded_success_rate"] == 1.0
    assert case["observed"]["raw_mean_total_tokens"] == 1100.0
    assert case["observed"]["guarded_mean_total_tokens"] == 1000.0
    review = read_json(tmp_path / "case" / "review" / "change_review.json")
    assert review["change_kind"] == "prompt_change"
    assert review["mode"] == "shadow"
    stability = read_json(tmp_path / "case" / "review" / "stability.json")
    assert stability["state"] == "insufficient_evidence"
    assert stability["signals"]["evidence_scope"] == "aggregate_independent_runs"
    assert (tmp_path / "case" / "baseline" / "events.jsonl").is_file()
    assert (tmp_path / "case" / "candidate" / "events.jsonl").is_file()
    assert (tmp_path / "case" / "comparison.en.svg").is_file()
    assert (tmp_path / "case" / "comparison.zh.svg").is_file()


def test_agent_case_rejects_nonfinite_public_metrics(tmp_path: Path) -> None:
    builder = _builder()
    pilot_csv = tmp_path / "pilot.csv"
    row = {
        "task_id": "task-1-trial-01",
        "base_task_id": "task-1",
        "trial": "1",
        "agent": "codex-local-exec",
        "raw_success": "true",
        "guarded_success": "true",
        "raw_tests_passed": "true",
        "guarded_tests_passed": "true",
        "raw_touched_files": "1",
        "guarded_touched_files": "1",
        "raw_unnecessary_file_edits": "0",
        "guarded_unnecessary_file_edits": "0",
        "raw_total_tokens": "nan",
        "guarded_total_tokens": "100",
        "raw_tool_calls": "1",
        "guarded_tool_calls": "1",
        "raw_duration_seconds": "1",
        "guarded_duration_seconds": "1",
    }
    with pilot_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)

    with pytest.raises(ValueError, match="finite"):
        builder.build_agent_case(pilot_csv=pilot_csv, out_dir=tmp_path / "case")


def test_committed_agent_case_matches_the_real_public_source_table() -> None:
    case_dir = Path("docs/case_studies/agent_change_review")
    rows = list(csv.DictReader((case_dir / "pilot.csv").read_text(encoding="utf-8").splitlines()))
    case = read_json(case_dir / "case_manifest.json")

    assert len(rows) == 30
    assert len({row["base_task_id"] for row in rows}) == 10
    assert "raw_prompt_summary" not in rows[0]
    assert "guarded_prompt_summary" not in rows[0]
    assert case["paired_rows"] == 30
    assert case["execution_count"] == 60
    assert case["observed"]["raw_success_rate"] == 1.0
    assert case["observed"]["guarded_success_rate"] == 1.0
    assert case["observed"]["guarded_mean_total_tokens"] < case["observed"][
        "raw_mean_total_tokens"
    ]
    public_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in case_dir.rglob("*")
        if path.is_file() and path.suffix in {".csv", ".json", ".md", ".html", ".svg"}
    )
    assert "D:\\" not in public_text
    assert "/root/" not in public_text
    assert "Fix the failing test." not in public_text
    assert re.search(r"\bsk-[A-Za-z0-9_-]{12,}\b", public_text) is None


def test_committed_flagship_cases_are_discovered_in_product_order() -> None:
    rows = list_runs(Path("docs/case_studies"))
    featured = [row for row in rows if row.get("featured") is True]

    assert [row["name"] for row in featured] == [
        "agent_change_review",
        "model_change_review",
        "checkpoint_change_review",
    ]
    assert [row["decision"] for row in featured] == [
        "needs_review",
        "needs_review",
        "hold",
    ]
    assert featured[0]["technical_change_kind"] == "prompt_change"
    assert featured[1]["evidence_level"] == "historical_aggregate"


def test_paired_model_protocol_is_explicitly_unexecuted_and_bounded() -> None:
    protocol = read_json(
        Path("docs/case_studies/model_change_review/paired_model_pilot.protocol.json")
    )

    assert protocol["status"] == "not_executed"
    assert protocol["execution_authorized"] is False
    assert protocol["planned_run_count"] == 60
    assert len(protocol["task_ids"]) == 10
    assert protocol["repetitions_per_task_per_model"] == 3
    assert "api_keys" in protocol["redaction"]["exclude"]
