import csv
import json
from pathlib import Path

BASE_AGENT_GUARD_FIELDS = [
    "task_id",
    "agent",
    "task_type",
    "raw_prompt_summary",
    "guarded_prompt_summary",
    "raw_success",
    "guarded_success",
    "raw_touched_files",
    "guarded_touched_files",
    "raw_unnecessary_file_edits",
    "guarded_unnecessary_file_edits",
    "raw_tests_passed",
    "guarded_tests_passed",
    "raw_human_corrections",
    "guarded_human_corrections",
    "raw_prompt_tokens",
    "guarded_prompt_tokens",
]

PREFLIGHT_FIELDS = [*BASE_AGENT_GUARD_FIELDS, "notes"]
PAIRED_FIELDS = [
    *BASE_AGENT_GUARD_FIELDS,
    "raw_duration_seconds",
    "guarded_duration_seconds",
    "notes",
]


def test_agent_guard_preflight_pilot_schema_and_claims() -> None:
    csv_path = Path("docs/case_studies/agent_guard_pilot.csv")
    reader = csv.DictReader(csv_path.read_text(encoding="utf-8").splitlines())
    rows = list(reader)

    assert reader.fieldnames == PREFLIGHT_FIELDS
    assert len(rows) >= 20
    assert all(row["raw_success"] == "not_run" for row in rows)
    assert all(row["guarded_success"] == "not_run" for row in rows)
    assert all(row["raw_prompt_tokens"] for row in rows)
    assert all(row["guarded_prompt_tokens"] for row in rows)
    assert all("preflight-only" in row["notes"] for row in rows)

    readme = Path("README.md").read_text(encoding="utf-8")
    readme_zh = Path("README.zh.md").read_text(encoding="utf-8")
    assert "small local preflight pilot" in readme
    assert "小样本本地 preflight 试点" in readme_zh
    assert "does **not** claim task-success improvement" in readme
    assert "不声称任务成功率提升" in readme_zh


def test_agent_guard_paired_pilot_schema_and_readme_numbers() -> None:
    csv_path = Path("docs/case_studies/agent_guard_paired_pilot.csv")
    summary_path = Path("docs/case_studies/agent_guard_paired_pilot.summary.json")
    reader = csv.DictReader(csv_path.read_text(encoding="utf-8").splitlines())
    rows = list(reader)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert reader.fieldnames == PAIRED_FIELDS
    assert len(rows) == 6
    assert summary["sample_size"] == len(rows)
    assert summary["raw_success"] == sum(row["raw_success"] == "true" for row in rows)
    assert summary["guarded_success"] == sum(row["guarded_success"] == "true" for row in rows)
    assert summary["raw_tests_passed"] == sum(row["raw_tests_passed"] == "true" for row in rows)
    assert summary["guarded_tests_passed"] == sum(
        row["guarded_tests_passed"] == "true" for row in rows
    )
    assert all("real Codex paired pilot" in row["notes"] for row in rows)

    readme = Path("README.md").read_text(encoding="utf-8")
    readme_zh = Path("README.zh.md").read_text(encoding="utf-8")
    assert "Completed tasks | 6/6 | 6/6" in readme
    assert "Tests passed | 6/6 | 6/6" in readme
    assert "guarded prompts did **not** improve success rate" in readme
    assert "完成任务 | 6/6 | 6/6" in readme_zh
    assert "测试通过 | 6/6 | 6/6" in readme_zh
    assert "没有提升成功率" in readme_zh
