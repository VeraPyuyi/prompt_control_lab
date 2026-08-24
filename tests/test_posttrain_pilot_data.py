from __future__ import annotations

import json
from pathlib import Path

from promptcontrollab.cli import main
from promptcontrollab.files import read_json
from promptcontrollab.posttrain_pilot import PilotInputs, build_sft_pilot_plan
from promptcontrollab.posttrain_pilot_data import (
    GSM8K_DATASET_ID,
    GSM8K_DATASET_REVISION,
    prepare_sft_pilot_data,
)


def _gsm8k_rows(count: int, *, offset: int = 0) -> list[dict[str, str]]:
    return [
        {
            "question": f"If item {index + offset} costs 2 dollars, what is twice its cost?",
            "answer": f"Twice 2 is 4. #### {index + offset + 4}",
        }
        for index in range(count)
    ]


def _write_jsonl(path: Path, rows: list[dict[str, str]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_prepare_sft_pilot_data_writes_fixed_disjoint_splits_and_provenance(
    tmp_path: Path,
) -> None:
    out = tmp_path / "pilot-data"
    first = prepare_sft_pilot_data(
        train_rows=_gsm8k_rows(500),
        test_rows=_gsm8k_rows(200, offset=10_000),
        out_dir=out,
        dataset_id=GSM8K_DATASET_ID,
        dataset_revision=GSM8K_DATASET_REVISION,
        selection_seed=20260824,
    )
    second = prepare_sft_pilot_data(
        train_rows=list(reversed(_gsm8k_rows(500))),
        test_rows=list(reversed(_gsm8k_rows(200, offset=10_000))),
        out_dir=tmp_path / "pilot-data-repeat",
        dataset_id=GSM8K_DATASET_ID,
        dataset_revision=GSM8K_DATASET_REVISION,
        selection_seed=20260824,
    )

    assert first["counts"] == {
        "train": 320,
        "validation": 80,
        "withheld": 128,
        "format_fixture": 64,
    }
    assert first["dataset"] == {
        "id": GSM8K_DATASET_ID,
        "revision": GSM8K_DATASET_REVISION,
        "configuration": "main",
    }
    assert first["split_sha256"] == second["split_sha256"]
    for name in ("train", "validation", "withheld", "format_fixture"):
        assert (out / f"{name}.jsonl").is_file()

    plan = build_sft_pilot_plan(
        PilotInputs(
            model_path=tmp_path / "model",
            train_path=out / "train.jsonl",
            validation_path=out / "validation.jsonl",
            withheld_path=out / "withheld.jsonl",
            format_fixture_path=out / "format_fixture.jsonl",
            out_dir=tmp_path / "pilot",
        )
    )
    assert plan["split_provenance"]["files"]["train"]["row_count"] == 320
    assert plan["split_provenance"]["files"]["format_fixture"]["row_count"] == 64


def test_posttrain_pilot_prepare_cli_supports_offline_jsonl_sources(tmp_path: Path) -> None:
    train_source = tmp_path / "gsm8k-train.jsonl"
    test_source = tmp_path / "gsm8k-test.jsonl"
    _write_jsonl(train_source, _gsm8k_rows(500))
    _write_jsonl(test_source, _gsm8k_rows(200, offset=10_000))
    out = tmp_path / "prepared"

    assert (
        main(
            [
                "posttrain-pilot-prepare",
                "--gsm8k-train-jsonl",
                str(train_source),
                "--gsm8k-test-jsonl",
                str(test_source),
                "--dataset-revision",
                GSM8K_DATASET_REVISION,
                "--out",
                str(out),
            ]
        )
        == 0
    )
    manifest = read_json(out / "dataset_provenance.json")
    assert manifest["counts"]["withheld"] == 128
    assert manifest["source_mode"] == "offline_jsonl"


def test_posttrain_pilot_prepare_cli_requires_both_offline_sources(tmp_path: Path) -> None:
    train_source = tmp_path / "gsm8k-train.jsonl"
    _write_jsonl(train_source, _gsm8k_rows(500))

    assert (
        main(
            [
                "posttrain-pilot-prepare",
                "--gsm8k-train-jsonl",
                str(train_source),
                "--out",
                str(tmp_path / "prepared"),
            ]
        )
        == 2
    )
