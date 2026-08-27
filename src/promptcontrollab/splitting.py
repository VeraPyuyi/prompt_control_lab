"""Backward-compatible facade for :mod:`promptcontrollab.evaluation.splitting`."""

from promptcontrollab.evaluation.splitting import (
    SplitResult,
    leakage_report,
    load_tasks,
    make_split,
    write_split,
)

__all__ = [
    "SplitResult",
    "leakage_report",
    "load_tasks",
    "make_split",
    "write_split",
]
