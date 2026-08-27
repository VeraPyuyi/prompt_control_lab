"""Tri-split benchmark utilities."""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from promptcontrollab.core.files import JsonDict, read_jsonl, stable_digest, write_json
from promptcontrollab.core.schemas import TaskRecord


@dataclass(frozen=True)
class SplitResult:
    """Train/validation/withheld split identifiers."""

    train: list[str]
    val: list[str]
    withheld: list[str]
    split_hash: str
    seed: int

    def to_json(self) -> JsonDict:
        return {
            "train": self.train,
            "val": self.val,
            "withheld": self.withheld,
            "split_hash": self.split_hash,
            "seed": self.seed,
            "counts": {
                "train": len(self.train),
                "val": len(self.val),
                "withheld": len(self.withheld),
            },
            "leakage": leakage_report(self.train, self.val, self.withheld),
        }


def load_tasks(path: Path) -> list[TaskRecord]:
    """Load task records from JSONL."""

    return [TaskRecord.from_json(record) for record in read_jsonl(path)]


def make_split(
    tasks: list[TaskRecord],
    *,
    train_ratio: float,
    val_ratio: float,
    seed: int,
) -> SplitResult:
    """Create a deterministic train/val/withheld split."""

    if not tasks:
        msg = "Cannot split an empty dataset"
        raise ValueError(msg)
    if train_ratio <= 0 or val_ratio < 0 or train_ratio + val_ratio >= 1:
        msg = "Expected train_ratio > 0, val_ratio >= 0, and train_ratio + val_ratio < 1"
        raise ValueError(msg)
    ids = [task.id for task in tasks]
    if len(set(ids)) != len(ids):
        msg = "Task ids must be unique"
        raise ValueError(msg)
    shuffled = ids[:]
    random.Random(seed).shuffle(shuffled)
    train_end = max(1, round(len(shuffled) * train_ratio))
    val_end = train_end + round(len(shuffled) * val_ratio)
    if val_end >= len(shuffled):
        val_end = len(shuffled) - 1
    train = sorted(shuffled[:train_end])
    val = sorted(shuffled[train_end:val_end])
    withheld = sorted(shuffled[val_end:])
    payload = {"ids": sorted(ids), "train": train, "val": val, "withheld": withheld, "seed": seed}
    return SplitResult(
        train=train,
        val=val,
        withheld=withheld,
        split_hash=stable_digest(payload),
        seed=seed,
    )


def leakage_report(train: list[str], val: list[str], withheld: list[str]) -> JsonDict:
    """Report overlap across split ids."""

    train_set = set(train)
    val_set = set(val)
    withheld_set = set(withheld)
    overlaps = {
        "train_val": sorted(train_set & val_set),
        "train_withheld": sorted(train_set & withheld_set),
        "val_withheld": sorted(val_set & withheld_set),
    }
    return {
        "has_leakage": any(overlaps.values()),
        "overlaps": overlaps,
    }


def write_split(path: Path, split: SplitResult) -> None:
    """Write split manifest."""

    write_json(path, split.to_json())
