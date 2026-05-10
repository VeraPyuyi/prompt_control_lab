from __future__ import annotations

from pathlib import Path

from promptcontrollab.cli import main


def test_cli_example_flow(tmp_path: Path) -> None:
    demo = tmp_path / "demo"
    assert main(["init", "--path", str(demo)]) == 0
    assert (
        main(
            [
                "split",
                "--data",
                str(demo / "examples" / "tasks.jsonl"),
                "--out",
                str(demo / "runs" / "candidate"),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "eval",
                "--data",
                str(demo / "examples" / "tasks.jsonl"),
                "--predictions",
                str(demo / "examples" / "predictions_baseline.jsonl"),
                "--out",
                str(demo / "runs" / "baseline"),
                "--method",
                "baseline",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "eval",
                "--data",
                str(demo / "examples" / "tasks.jsonl"),
                "--predictions",
                str(demo / "examples" / "predictions_candidate.jsonl"),
                "--out",
                str(demo / "runs" / "candidate"),
                "--method",
                "candidate",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "stats",
                "--baseline",
                str(demo / "runs" / "baseline" / "predictions.jsonl"),
                "--candidate",
                str(demo / "runs" / "candidate" / "predictions.jsonl"),
                "--out",
                str(demo / "runs" / "candidate" / "stats.json"),
                "--bootstrap-samples",
                "10",
                "--permutation-samples",
                "10",
            ]
        )
        == 0
    )
    assert main(["report", "--run", str(demo / "runs" / "candidate")]) == 0
    assert (demo / "runs" / "candidate" / "report.md").exists()
