import json
from pathlib import Path

from promptcontrollab.core.files import write_jsonl
from promptcontrollab.core.schemas import TaskRecord
from promptcontrollab.evaluation.splitting import make_split
from promptcontrollab.evaluation.workflow import run_quick_analysis


def test_quick_analysis_scores_the_partition_it_declares(tmp_path: Path) -> None:
    data = [{"id": str(i), "input": f"Unique input {i}", "expected": "yes"} for i in range(10)]
    write_jsonl(tmp_path / "data.jsonl", data)
    write_jsonl(tmp_path / "left.jsonl", [{"id": row["id"], "output": "no"} for row in data])
    write_jsonl(tmp_path / "right.jsonl", [{"id": row["id"], "output": "yes"} for row in data])
    for scope in ("withheld", "all"):
        output = tmp_path / scope
        run_quick_analysis(
            data_path=tmp_path / "data.jsonl",
            baseline_predictions_path=tmp_path / "left.jsonl",
            candidate_predictions_path=tmp_path / "right.jsonl",
            out_dir=output,
            metric="exact_match",
            train_ratio=0.6,
            val_ratio=0.2,
            seed=7,
            bootstrap_samples=50,
            permutation_samples=50,
            explain_level="plain",
            title="Isolation",
            evaluation_scope=scope,
        )
        split = json.loads((output / "splits.json").read_text())
        expected = set(split["withheld"]) if scope == "withheld" else {row["id"] for row in data}
        for arm in ("baseline", "candidate"):
            records = [
                json.loads(line)
                for line in (output / arm / "predictions.jsonl").read_text().splitlines()
            ]
            assert {row["id"] for row in records} == expected
            manifest = json.loads((output / arm / "manifest.json").read_text())
            assert manifest["evaluation_scope"]["partition"] == scope
            assert (
                manifest["evaluation_scope"]["independence"]
                == "not_verified_for_imported_predictions"
            )


def test_single_item_split_never_duplicates_across_partitions() -> None:
    result = make_split([TaskRecord("one", "one", "1")], train_ratio=0.6, val_ratio=0.2, seed=0)
    assert result.train == []
    assert result.val == []
    assert result.withheld == ["one"]
    assert not result.to_json()["leakage"]["has_leakage"]
