"""Shared data structures for research diagnostic workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResearchPaths:
    """Resolve the inputs and output locations used by a research diagnostic run."""

    soft_path: Path | None
    vocab_path: Path | None
    states_path: Path | None
    matrices_path: Path | None
    tv_predictions_path: Path | None
    terminal_records_path: Path | None
    terminal_surrogate_path: Path | None
    green_surrogate_path: Path | None
    green_premises_path: Path | None
    posterior_bounds_path: Path | None
    diagnostics_dir: Path
    summary_dir: Path
