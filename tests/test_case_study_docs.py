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


def test_agent_guard_pilot_schema_and_readme_status() -> None:
    csv_path = Path("docs/case_studies/agent_guard_pilot.csv")
    rows = list(csv.DictReader(csv_path.read_text(encoding="utf-8").splitlines()))

    assert csv.DictReader(csv_path.read_text(encoding="utf-8").splitlines()).fieldnames == (
        EXPECTED_AGENT_GUARD_FIELDS
    )

    readme = Path("README.md").read_text(encoding="utf-8")
    readme_zh = Path("README.zh.md").read_text(encoding="utf-8")
    if len(rows) < 20:
        assert "Status: **in progress**" in readme
        assert "Paired local Codex tasks collected | 0/20" in readme
        assert "Status: **in progress**" not in readme_zh
        assert "**正在收集**" in readme_zh
        assert "已收集 Codex 本地成对任务 | 0/20" in readme_zh
        assert "task success rate | TBD" not in readme
        assert "任务成功率 | TBD" not in readme_zh
