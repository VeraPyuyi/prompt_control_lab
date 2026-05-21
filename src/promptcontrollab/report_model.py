"""Shared structured data model for reports and the local UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from promptcontrollab.files import JsonDict, read_json


@dataclass(frozen=True)
class ReportModel:
    """Structured view over PromptControlLab run artifacts."""

    run_dir: Path
    manifest: JsonDict
    metrics: JsonDict
    baseline_metrics: JsonDict
    candidate_metrics: JsonDict
    stats: JsonDict
    splits: JsonDict
    explanation: JsonDict
    gate: JsonDict
    model_drift: JsonDict
    audit: JsonDict
    history_index: JsonDict
    history_compare: JsonDict
    agent_run: JsonDict
    diagnostics: dict[str, JsonDict]
    artifacts: list[str]
    candidate_score: float | None
    baseline_score: float | None

    @classmethod
    def from_run(cls, run_dir: Path) -> ReportModel:
        """Load all known artifacts from a run directory."""

        manifest = _read_optional(run_dir / "manifest.json")
        root_metrics = _read_optional(run_dir / "metrics.json")
        baseline_metrics = _read_optional(run_dir / "baseline" / "metrics.json")
        candidate_metrics = _read_optional(run_dir / "candidate" / "metrics.json")
        metrics = root_metrics or candidate_metrics
        artifacts = _existing_artifacts(run_dir)
        diagnostics = _collect_diagnostics(run_dir / "diagnostics")
        return cls(
            run_dir=run_dir,
            manifest=manifest,
            metrics=metrics,
            baseline_metrics=baseline_metrics,
            candidate_metrics=candidate_metrics,
            stats=_read_optional(run_dir / "stats.json"),
            splits=_read_optional(run_dir / "splits.json"),
            explanation=_read_optional(run_dir / "explanation.json"),
            gate=_read_optional(run_dir / "gate_result.json"),
            model_drift=_read_optional(run_dir / "model_drift.json"),
            audit=_read_optional(run_dir / "audit_result.json"),
            history_index=_read_optional(run_dir / "history_index.json"),
            history_compare=_read_optional(run_dir / "history_compare.json"),
            agent_run=_read_optional(run_dir / "agent_run.json"),
            diagnostics=diagnostics,
            artifacts=artifacts,
            candidate_score=_score(candidate_metrics) or _score(root_metrics),
            baseline_score=_score(baseline_metrics),
        )

    @property
    def has_artifacts(self) -> bool:
        """Whether this run has any recognized artifact."""

        return bool(self.artifacts)


def _read_optional(path: Path) -> JsonDict:
    if not path.exists():
        return {}
    return read_json(path)


def _existing_artifacts(run_dir: Path) -> list[str]:
    names = [
        "manifest.json",
        "metrics.json",
        "baseline/metrics.json",
        "candidate/metrics.json",
        "stats.json",
        "splits.json",
        "gate_result.json",
        "explanation.json",
        "model_drift.json",
        "audit_result.json",
        "history_index.json",
        "history_compare.json",
        "agent_run.json",
        "report.md",
        "report.html",
    ]
    return [name for name in names if (run_dir / name).exists()]


def _collect_diagnostics(path: Path) -> dict[str, JsonDict]:
    if not path.exists():
        return {}
    return {item.stem: read_json(item) for item in sorted(path.glob("*.json"))}


def _score(value: JsonDict) -> float | None:
    raw = value.get("mean_score")
    if isinstance(raw, int | float):
        return float(raw)
    return None
