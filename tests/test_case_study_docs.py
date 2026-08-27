import csv
import json
import re
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
    public_chinese_docs = [Path("README.zh.md"), *sorted(Path("docs").rglob("*.zh.md"))]
    bad_markers = [
        "\ufffd",
        "???",
        "閵",
        "閻",
        "閿",
        "闂",
        "涔",
        "闈",
        "闁",
        "娑",
    ]
    assert public_chinese_docs
    for path in public_chinese_docs:
        text = path.read_text(encoding="utf-8")
        for marker in bad_markers:
            assert marker not in text, f"{path} contains mojibake marker {marker!r}"

    readme_zh = Path("README.zh.md").read_text(encoding="utf-8")
    assert "面向 Prompt、模型、Checkpoint 与 AI Agent 的本地 Change Review 决策层。" in readme_zh
    assert "旗舰集成" in readme_zh and "DeepSeek Harness" in readme_zh
    assert "核心诊断闭环" in readme_zh
    assert "边界" in readme_zh


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
    assert "raw-agent vs guarded-agent" in production_zh
    assert "python -m build" in release_en
    assert "pipx install dist/" in release_en
    assert "python -m build --wheel --no-isolation" in release_en
    assert "promptcontrollab" in release_zh
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
    assert "docs/case_studies/agent_guard_pilot.en.md" in readme
    assert "docs/case_studies/agent_guard_pilot.zh.md" in readme_zh
    assert "small pilots are not universal benchmarks" in readme
    assert "不是通用 benchmark" in readme_zh
    assert raw_avg_tokens > 0
    assert guarded_avg_tokens > raw_avg_tokens


def test_agent_guard_paired_pilot_schema_and_readme_links() -> None:
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

    raw_success = f"{summary['raw_success']}/{summary['sample_size']}"
    guarded_success = f"{summary['guarded_success']}/{summary['sample_size']}"
    raw_tests = f"{summary['raw_tests_passed']}/{summary['sample_size']}"
    guarded_tests = f"{summary['guarded_tests_passed']}/{summary['sample_size']}"
    assert raw_success == guarded_success
    assert raw_tests == guarded_tests

    readme = Path("README.md").read_text(encoding="utf-8")
    readme_zh = Path("README.zh.md").read_text(encoding="utf-8")
    assert "docs/case_studies/agent_guard_paired_pilot.en.md" in readme
    assert "docs/case_studies/agent_guard_paired_pilot.zh.md" in readme_zh
    assert "small pilots are not universal benchmarks" in readme
    assert "不是通用 benchmark" in readme_zh


def test_agent_guard_paired_pilot_visual_assets_exist() -> None:
    en_svg = Path("docs/assets/agent_guard_paired_pilot.svg")
    zh_svg = Path("docs/assets/agent_guard_paired_pilot.zh.svg")

    assert en_svg.exists()
    assert zh_svg.exists()
    assert "Real Paired Pilot" in en_svg.read_text(encoding="utf-8")
    assert "真实成对试点" in zh_svg.read_text(encoding="utf-8")
    assert "promptcontrollab" not in en_svg.read_text(encoding="utf-8")
    assert "promptcontrollab" not in zh_svg.read_text(encoding="utf-8")


def test_real_peoc_case_study_is_public_safe_and_numerically_consistent() -> None:
    case_dir = Path("docs/case_studies/peoc_real")
    payload = json.loads((case_dir / "research_case_study.json").read_text(encoding="utf-8"))
    readme = (case_dir / "README.md").read_text(encoding="utf-8")
    readme_zh = (case_dir / "README.zh.md").read_text(encoding="utf-8")

    assert payload["schema"] == "prompt_control_lab.peoc_case_study.v1"
    assert payload["evidence_origin"] == "real"
    assert payload["claim_boundary"]["full_research_support"] is False
    assert payload["claim_boundary"]["status"] == "not_supported"
    assert payload["status_counts"] == {
        "available": 2,
        "failed_validation": 1,
        "missing": 2,
        "partial": 0,
        "unusable": 1,
    }

    sources = payload["source_inventory"]
    assert len(sources) == 14
    assert all(item.get("relative_path") and item.get("sha256") for item in sources)
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "resolved_path" not in serialized
    assert "AppData" not in serialized
    assert "Vibe Research Projects" not in serialized
    assert re.search(r"[A-Za-z]:\\\\", serialized) is None
    assert not list(case_dir.rglob("*.npz"))

    hard = payload["hard_summary"]
    rows = payload["hard_method_rows"]
    assert hard["status"] == "available"
    assert hard["valid_row_count"] == len(rows) == 72
    assert len(hard["models"]) == 3
    assert len(hard["tasks"]) == 4
    assert len(hard["methods"]) == 6

    cells = sorted({(row["model"], row["task"]) for row in rows})
    deltas: list[float] = []
    tv_best = 0
    for model, task in cells:
        group = [row for row in rows if row["model"] == model and row["task"] == task]
        tv = next(row for row in group if row["method"] == "tv_pmp")["mean"]
        static = next(row for row in group if row["method"] == "static_autograd")["mean"]
        deltas.append(float(tv) - float(static))
        tv_best += int(float(tv) == max(float(row["mean"]) for row in group))
    assert len(cells) == 12
    assert sum(delta > 0 for delta in deltas) == 6
    assert sum(delta < 0 for delta in deltas) == 6
    assert round(sum(deltas) / len(deltas), 4) == 0.0063
    assert round(min(deltas), 4) == -0.0566
    assert round(max(deltas), 4) == 0.0449
    assert tv_best == 2

    pair = payload["selected_trajectory_pair"]
    assert round(pair["stationary"]["alpha_emp_mean"], 5) == 0.02471
    assert round(pair["stationary"]["R2_mean"], 4) == 0.6020
    assert round(pair["heterogeneous"]["alpha_emp_mean"], 6) == 0.001741
    assert round(pair["heterogeneous"]["R2_mean"], 4) == 0.0880
    assert payload["stage_validation"]["verdict"] == "FAIL"

    for text in [readme, readme_zh]:
        assert "72" in text
        assert "available=2" in text
        assert "failed_validation=1" in text
        assert "+0.0063" in text
        assert "-0.0566" in text
        assert "+0.0449" in text
        assert "0.02471" in text
        assert "0.001741" in text
        assert "not_supported" in text
