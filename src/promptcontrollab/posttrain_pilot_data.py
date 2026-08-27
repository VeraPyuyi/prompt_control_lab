"""Deterministic, provenance-bound inputs for the controlled SFT pilot."""

from __future__ import annotations

import hashlib
import importlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path

from promptcontrollab.core.files import JsonDict, ensure_dir, stable_digest, write_json

GSM8K_DATASET_ID = "openai/gsm8k"
GSM8K_DATASET_REVISION = "740312add88f781978c0658806c59bc2815b9866"
GSM8K_CONFIGURATION = "main"
PILOT_SELECTION_SEED = 20260824

_TRAIN_COUNT = 320
_VALIDATION_COUNT = 80
_WITHHELD_COUNT = 128
_FORMAT_COUNT = 64


def prepare_sft_pilot_data(
    *,
    train_rows: Iterable[Mapping[str, object]],
    test_rows: Iterable[Mapping[str, object]],
    out_dir: Path,
    dataset_id: str = GSM8K_DATASET_ID,
    dataset_revision: str = GSM8K_DATASET_REVISION,
    selection_seed: int = PILOT_SELECTION_SEED,
    source_mode: str = "provided_rows",
) -> JsonDict:
    """Write fixed, disjoint pilot splits from public GSM8K records."""

    train_pool = _ranked_rows(train_rows, seed=selection_seed, namespace="train")
    test_pool = _ranked_rows(test_rows, seed=selection_seed, namespace="test")
    required_train = _TRAIN_COUNT + _VALIDATION_COUNT
    if len(train_pool) < required_train:
        raise ValueError(
            f"GSM8K train source needs at least {required_train} valid rows; "
            f"found {len(train_pool)}"
        )
    if len(test_pool) < _WITHHELD_COUNT:
        raise ValueError(
            f"GSM8K test source needs at least {_WITHHELD_COUNT} valid rows; "
            f"found {len(test_pool)}"
        )

    selected_train = train_pool[:_TRAIN_COUNT]
    selected_validation = train_pool[_TRAIN_COUNT:required_train]
    selected_withheld = test_pool[:_WITHHELD_COUNT]
    splits = {
        "train": _pilot_rows(selected_train, split="train"),
        "validation": _pilot_rows(selected_validation, split="validation"),
        "withheld": _pilot_rows(selected_withheld, split="withheld"),
        "format_fixture": _format_fixture_rows(_FORMAT_COUNT),
    }
    ensure_dir(out_dir)
    file_records: JsonDict = {}
    split_sha256: JsonDict = {}
    for name, rows in splits.items():
        path = out_dir / f"{name}.jsonl"
        _write_jsonl(path, rows)
        digest = _sha256(path)
        split_sha256[name] = digest
        file_records[name] = {
            "path": path.name,
            "row_count": len(rows),
            "bytes": path.stat().st_size,
            "sha256": digest,
        }
    payload: JsonDict = {
        "schema": "prompt_control_lab.sft_pilot_dataset.v1",
        "source_mode": source_mode,
        "dataset": {
            "id": dataset_id,
            "revision": dataset_revision,
            "configuration": GSM8K_CONFIGURATION,
        },
        "selection_seed": selection_seed,
        "selection_method": "sha256_ranked_without_replacement",
        "counts": {
            "train": _TRAIN_COUNT,
            "validation": _VALIDATION_COUNT,
            "withheld": _WITHHELD_COUNT,
            "format_fixture": _FORMAT_COUNT,
        },
        "files": file_records,
        "split_sha256": split_sha256,
        "combined_sha256": f"sha256:{stable_digest(split_sha256)}",
        "claim_boundary": (
            "The fixed public subset supports matched checkpoint comparison. It is not a "
            "leaderboard estimate or a universal post-training benchmark."
        ),
    }
    write_json(out_dir / "dataset_provenance.json", payload)
    return payload


def prepare_sft_pilot_data_from_huggingface(
    *,
    out_dir: Path,
    dataset_id: str = GSM8K_DATASET_ID,
    dataset_revision: str = GSM8K_DATASET_REVISION,
    selection_seed: int = PILOT_SELECTION_SEED,
) -> JsonDict:
    """Download the pinned public dataset through the optional datasets package."""

    try:
        datasets_module = importlib.import_module("datasets")
    except ImportError as exc:
        raise ValueError(
            "Preparing GSM8K from Hugging Face requires `datasets`; "
            "install the post-training environment first."
        ) from exc
    load_dataset = getattr(datasets_module, "load_dataset", None)
    if not callable(load_dataset):
        raise ValueError("The installed `datasets` package does not expose load_dataset().")
    dataset = load_dataset(
        dataset_id,
        GSM8K_CONFIGURATION,
        revision=dataset_revision,
        trust_remote_code=False,
    )
    return prepare_sft_pilot_data(
        train_rows=dataset["train"],
        test_rows=dataset["test"],
        out_dir=out_dir,
        dataset_id=dataset_id,
        dataset_revision=dataset_revision,
        selection_seed=selection_seed,
        source_mode="huggingface",
    )


def load_gsm8k_jsonl(path: Path) -> list[JsonDict]:
    """Read offline GSM8K question/answer rows without importing datasets."""

    if not path.is_file():
        raise ValueError(f"GSM8K JSONL source is missing: {path}")
    rows: list[JsonDict] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid GSM8K JSONL at {path}:{line_number}") from exc
        if not isinstance(raw, dict):
            raise ValueError(f"GSM8K row must be an object at {path}:{line_number}")
        rows.append(raw)
    return rows


def _ranked_rows(
    rows: Iterable[Mapping[str, object]],
    *,
    seed: int,
    namespace: str,
) -> list[JsonDict]:
    unique: dict[str, JsonDict] = {}
    for index, raw in enumerate(rows):
        question = str(raw.get("question", "")).strip()
        answer = str(raw.get("answer", "")).strip()
        if not question or not answer:
            raise ValueError(f"GSM8K {namespace} row {index} is missing question or answer")
        identity = stable_digest({"question": question, "answer": answer})
        if identity in unique:
            raise ValueError(f"Duplicate GSM8K {namespace} row content: sha256:{identity}")
        unique[identity] = {
            "source_sha256": f"sha256:{identity}",
            "question": question,
            "answer": answer,
        }
    return sorted(
        unique.values(),
        key=lambda row: stable_digest(
            {
                "seed": seed,
                "namespace": namespace,
                "source_sha256": row["source_sha256"],
            }
        ),
    )


def _pilot_rows(rows: list[JsonDict], *, split: str) -> list[JsonDict]:
    result: list[JsonDict] = []
    for row in rows:
        source_sha256 = str(row["source_sha256"])
        result.append(
            {
                "id": f"gsm8k-{split}-{source_sha256.removeprefix('sha256:')[:16]}",
                "prompt": (
                    "Solve the following math word problem. Show concise reasoning, then put "
                    "the final numeric answer after `####`.\n\n"
                    f"Problem: {row['question']}"
                ),
                "answer": row["answer"],
                "slice": "gsm8k",
                "source_sha256": source_sha256,
            }
        )
    return result


def _format_fixture_rows(count: int) -> list[JsonDict]:
    return [
        {
            "id": f"format-withheld-{index:03d}",
            "prompt": (
                "Return exactly the text between the brackets. Do not add an explanation.\n"
                f"[{_format_label(index)}]"
            ),
            "answer": _format_label(index),
            "slice": "format_following",
            "source": "prompt_control_lab_generated_fixture_v1",
        }
        for index in range(count)
    ]


def _format_label(index: int) -> str:
    groups = ("ALPHA", "BETA", "GAMMA", "DELTA")
    return f"LABEL: {groups[index % len(groups)]}-{index:03d}"


def _write_jsonl(path: Path, rows: list[JsonDict]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"
