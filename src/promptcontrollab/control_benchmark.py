"""Backward-compatible facade for :mod:`promptcontrollab.control.control_benchmark`."""

from promptcontrollab.control.control_benchmark import (
    MANIFEST_SCHEMA,
    RESULT_SCHEMA,
    STABILITY_LABELS,
    ControlBenchmarkError,
    main,
    run_benchmark,
)

__all__ = [
    "MANIFEST_SCHEMA",
    "RESULT_SCHEMA",
    "STABILITY_LABELS",
    "ControlBenchmarkError",
    "main",
    "run_benchmark",
]
