import csv
from pathlib import Path

EXPECTED_AGENT_GUARD_FIELDS = [
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
    "notes",
]


def test_agent_guard_pilot_schema_and_no_unsupported_readme_claims() -> None:
    csv_path = Path("docs/case_studies/agent_guard_pilot.csv")
    reader = csv.DictReader(csv_path.read_text(encoding="utf-8").splitlines())
    rows = list(reader)

    assert reader.fieldnames == EXPECTED_AGENT_GUARD_FIELDS
    assert len(rows) >= 20
    assert all(row["raw_success"] == "not_run" for row in rows)
    assert all(row["guarded_success"] == "not_run" for row in rows)
    assert all(row["raw_prompt_tokens"] for row in rows)
    assert all(row["guarded_prompt_tokens"] for row in rows)
    assert all("preflight-only" in row["notes"] for row in rows)

    readme = Path("README.md").read_text(encoding="utf-8")
    readme_zh = Path("README.zh.md").read_text(encoding="utf-8")
    assert "task success rate | TBD" not in readme
    assert "任务成功率 | TBD" not in readme_zh
    assert "Completed tasks |" not in readme
    assert "完成任务数 |" not in readme_zh
    assert "small local preflight pilot" in readme
    assert "小样本本地 preflight 试点" in readme_zh
