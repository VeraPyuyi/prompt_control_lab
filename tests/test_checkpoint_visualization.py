from __future__ import annotations

import json
from pathlib import Path

import pytest

from promptcontrollab.evidence.posttraining.visualization import (
    build_checkpoint_visualization,
    normalized_checkpoint_csv,
    parse_checkpoint_csv,
    render_checkpoint_svg,
    save_checkpoint_run,
)

VALID_CSV = (
    "seed,stage,checkpoint_id,mean_score,generation_mismatch,selective_aurc,"
    "trajectory_drift\n"
    "0,initial,seed-0-initial,0.10,0.60,0.90,8.0\n"
    "0,mid,seed-0-mid,0.20,0.50,0.75,8.3\n"
    "0,final,seed-0-final,0.25,0.40,0.65,8.5\n"
    "1,initial,seed-1-initial,0.12,0.62,0.91,8.1\n"
    "1,mid,seed-1-mid,0.19,0.52,0.77,8.4\n"
    "1,final,seed-1-final,0.23,0.42,0.67,8.6\n"
)


def test_checkpoint_visualization_preserves_seed_points_and_stage_aggregates() -> None:
    rows = parse_checkpoint_csv(VALID_CSV)

    payload = build_checkpoint_visualization(rows, decision="hold")

    assert payload["schema"] == "prompt_control_lab.checkpoint_visualization.v1"
    assert payload["decision"] == "hold"
    assert payload["stage_order"] == ["initial", "mid", "final"]
    assert payload["seeds"] == ["0", "1"]
    assert len(payload["points"]) == 6
    assert payload["aggregates"][0]["mean_score"] == pytest.approx(0.11)
    assert payload["aggregates"][-1]["mean_score"] == pytest.approx(0.24)
    assert payload["diagnostics"]["generation_mismatch"]["direction"] == "lower_is_better"
    assert payload["diagnostics"]["trajectory_drift"]["available"] is True
    assert normalized_checkpoint_csv(rows).startswith(
        "seed,stage,step,checkpoint_id,mean_score"
    )
    english_svg = render_checkpoint_svg(payload, language="en")
    chinese_svg = render_checkpoint_svg(payload, language="zh")
    assert "Checkpoint score by seed" in english_svg
    assert "Stage mean" in english_svg
    assert "各 Seed 的 Checkpoint 分数" in chinese_svg
    assert "阶段均值" in chinese_svg
    assert "初始" in chinese_svg
    assert "中间" in chinese_svg
    assert "最终" in chinese_svg
    assert chinese_svg.count(">初始</text>") == 4
    assert ">Initial</text>" not in chinese_svg


@pytest.mark.parametrize(
    ("csv_text", "message"),
    [
        ("seed,stage,checkpoint_id\n0,initial,a\n", "mean_score"),
        (
            "seed,stage,checkpoint_id,mean_score\n0,unknown,a,0.1\n",
            "stage",
        ),
        (
            "seed,stage,checkpoint_id,mean_score\n0,initial,a,nan\n",
            "finite",
        ),
        (
            "seed,stage,checkpoint_id,mean_score\n0,initial,a,0.1\n0,final,a,0.2\n",
            "duplicate",
        ),
    ],
)
def test_checkpoint_csv_rejects_invalid_or_ambiguous_rows(
    csv_text: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        parse_checkpoint_csv(csv_text)


def test_checkpoint_csv_accepts_numeric_steps_without_named_stages() -> None:
    rows = parse_checkpoint_csv(
        "seed,step,checkpoint_id,mean_score\n0,0,a,0.1\n0,30,b,0.2\n"
    )

    payload = build_checkpoint_visualization(rows)

    assert payload["stage_order"] == ["0", "30"]
    assert payload["decision"] == "insufficient_evidence"


def test_checkpoint_csv_enforces_size_and_row_limits() -> None:
    with pytest.raises(ValueError, match="1 MB"):
        parse_checkpoint_csv("x" * (1024 * 1024 + 1))

    rows = ["seed,stage,checkpoint_id,mean_score"]
    rows.extend(f"0,initial,checkpoint-{index},{index / 1000}" for index in range(1001))
    with pytest.raises(ValueError, match="1000"):
        parse_checkpoint_csv("\n".join(rows))


def test_save_checkpoint_run_writes_only_normalized_public_artifacts(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"

    output = save_checkpoint_run(runs_dir, "My Checkpoint Review", VALID_CSV)

    assert output == runs_dir / "my-checkpoint-review"
    assert sorted(path.name for path in output.iterdir()) == [
        "case_manifest.json",
        "checkpoint_metrics.csv",
        "checkpoint_visualization.json",
        "manifest.json",
    ]
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    case = json.loads((output / "case_manifest.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == "checkpoint_import"
    assert manifest["prompt"] == {"status": "not_recorded"}
    assert case["decision"] == "insufficient_evidence"
    assert case["display"]["featured"] is False
    assert "D:\\" not in json.dumps(case)

    with pytest.raises(FileExistsError, match="already exists"):
        save_checkpoint_run(runs_dir, "My Checkpoint Review", VALID_CSV)


@pytest.mark.parametrize("name", ["../outside", "..\\outside", "", "..."])
def test_save_checkpoint_run_rejects_unsafe_names(tmp_path: Path, name: str) -> None:
    with pytest.raises(ValueError, match="Run name"):
        save_checkpoint_run(tmp_path / "runs", name, VALID_CSV)
