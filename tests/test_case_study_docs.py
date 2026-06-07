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

def test_core_chinese_docs_do_not_contain_mojibake() -> None:
    for path in [
        Path("README.zh.md"),
        Path("docs/case_studies/agent_guard_pilot.zh.md"),
        Path("docs/case_studies/agent_guard_paired_pilot.zh.md"),
    ]:
        text = path.read_text(encoding="utf-8")
        assert "\ufffd" not in text
    readme_zh = Path("README.zh.md").read_text(encoding="utf-8")
    assert "AI 编程 Agent 的执行前检查" in readme_zh
    assert "本地 Case Study" in readme_zh
    assert "模型追溯边界" in readme_zh


def test_readmes_link_production_and_release_readiness_docs() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    readme_zh = Path("README.zh.md").read_text(encoding="utf-8")

    assert "docs/production_pilot.en.md" in readme
    assert "docs/release_install.en.md" in readme
    assert "docs/production_pilot.zh.md" in readme_zh
    assert "docs/release_install.zh.md" in readme_zh


def test_production_and_release_docs_state_boundaries() -> None:
    production_en = Path("docs/production_pilot.en.md").read_text(encoding="utf-8")
    production_zh = Path("docs/production_pilot.zh.md").read_text(encoding="utf-8")
    release_en = Path("docs/release_install.en.md").read_text(encoding="utf-8")
    release_zh = Path("docs/release_install.zh.md").read_text(encoding="utf-8")

    assert "Do not publish private prompts or source code" in production_en
    assert "raw-agent vs guarded-agent" in production_en
    assert "不要公开私有 prompt 或源码" in production_zh
    assert "raw-agent vs guarded-agent" in production_zh
    assert "python -m build" in release_en
    assert "pipx install dist/" in release_en
    assert "python -m build --wheel --no-isolation" in release_en
    assert "Python 包名是 `promptcontrollab`" in release_zh
    assert "pcl install-plugin all" in release_zh
    assert "python -m build --wheel --no-isolation" in release_zh


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
    raw_avg_tokens = round(
        sum(int(row["raw_prompt_tokens"]) for row in rows) / len(rows),
        2,
    )
    guarded_avg_tokens = round(
        sum(int(row["guarded_prompt_tokens"]) for row in rows) / len(rows),
        2,
    )

    readme = Path("README.md").read_text(encoding="utf-8")
    readme_zh = Path("README.zh.md").read_text(encoding="utf-8")
    assert "small local preflight pilot" in readme
    assert "小样本本地 preflight 试点" in readme_zh
    assert "does **not** claim task-success improvement" in readme
    assert "不声称任务成功率提升" in readme_zh
    assert f"Avg raw estimated prompt tokens | {raw_avg_tokens}" in readme
    assert f"Avg guarded estimated prompt tokens | {guarded_avg_tokens}" in readme


def test_agent_guard_paired_pilot_schema_and_readme_numbers() -> None:
    csv_path = Path("docs/case_studies/agent_guard_paired_pilot.csv")
    summary_path = Path("docs/case_studies/agent_guard_paired_pilot.summary.json")
    reader = csv.DictReader(csv_path.read_text(encoding="utf-8").splitlines())
    rows = list(reader)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert reader.fieldnames == PAIRED_FIELDS
    assert len(rows) >= 12
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
    raw_success = f"{summary['raw_success']}/{summary['sample_size']}"
    guarded_success = f"{summary['guarded_success']}/{summary['sample_size']}"
    raw_tests = f"{summary['raw_tests_passed']}/{summary['sample_size']}"
    guarded_tests = f"{summary['guarded_tests_passed']}/{summary['sample_size']}"
    assert f"Completed tasks | {raw_success} | {guarded_success}" in readme
    assert f"Tests passed | {raw_tests} | {guarded_tests}" in readme
    assert "guarded prompts still did **not** improve success rate" in readme
    assert "docs/assets/agent_guard_paired_pilot.svg" in readme
    assert f"完成任务 | {raw_success} | {guarded_success}" in readme_zh
    assert f"测试通过 | {raw_tests} | {guarded_tests}" in readme_zh
    assert "没有提升成功率" in readme_zh
    assert "docs/assets/agent_guard_paired_pilot.zh.svg" in readme_zh


def test_agent_guard_paired_pilot_visual_assets_exist() -> None:
    en_svg = Path("docs/assets/agent_guard_paired_pilot.svg")
    zh_svg = Path("docs/assets/agent_guard_paired_pilot.zh.svg")

    assert en_svg.exists()
    assert zh_svg.exists()
    assert "Real Paired Pilot" in en_svg.read_text(encoding="utf-8")
    assert "真实成对试点" in zh_svg.read_text(encoding="utf-8")
    assert "promptcontrollab" not in en_svg.read_text(encoding="utf-8")
    assert "promptcontrollab" not in zh_svg.read_text(encoding="utf-8")
