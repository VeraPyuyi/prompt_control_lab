"""Backward-compatible facade for :mod:`promptcontrollab.control.control_benchmark`."""

from promptcontrollab.control.control_benchmark import (
    ControlBenchmarkError,
    main,
    run_benchmark,
)

__all__ = [
    "ControlBenchmarkError",
    "main",
    "run_benchmark",
]
