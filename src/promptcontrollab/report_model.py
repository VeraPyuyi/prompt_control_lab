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
    comparison_validity: JsonDict
    model_drift: JsonDict
    audit: JsonDict
    history_index: JsonDict
    history_compare: JsonDict
    agent_run: JsonDict
    research_diagnostics: JsonDict
    research_gap_plan: JsonDict
    research_gap_status: JsonDict
    evidence_card: JsonDict
    claim_check: JsonDict
    external_evidence: JsonDict
    bridge_summary: JsonDict
    ecosystem_demo: JsonDict
    ecosystem_scorecard: JsonDict
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
        diagnostics = _collect_diagnostics(run_dir / "diagnostics")
        artifacts = _existing_artifacts(run_dir, diagnostics)
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
            comparison_validity=_read_optional(run_dir / "comparison_validity.json"),
            model_drift=_read_optional(run_dir / "model_drift.json"),
            audit=_read_optional(run_dir / "audit_result.json"),
            history_index=_read_optional(run_dir / "history_index.json"),
            history_compare=_read_optional(run_dir / "history_compare.json"),
            agent_run=_read_optional(run_dir / "agent_run.json"),
            research_diagnostics=_read_optional(run_dir / "research_diagnostics.json"),
            research_gap_plan=_read_optional(run_dir / "research_gap_plan.json"),
            research_gap_status=_read_optional(run_dir / "research_gap_status.json"),
            evidence_card=_read_optional(run_dir / "evidence_card.json"),
            claim_check=_read_optional(run_dir / "claim_check.json"),
            external_evidence=_read_optional(run_dir / "evidence_from_result.json"),
            bridge_summary=_read_optional(run_dir / "bridge_summary.json"),
            ecosystem_demo=_read_optional(run_dir / "ecosystem_demo.json"),
            ecosystem_scorecard=_read_optional(run_dir / "ecosystem_scorecard.json"),
            diagnostics=diagnostics,
            artifacts=artifacts,
            candidate_score=_first_score(candidate_metrics, root_metrics),
            baseline_score=_score(baseline_metrics),
        )

    @property
    def has_artifacts(self) -> bool:
        """Whether this run has any recognized artifact."""

        return bool(self.artifacts)

    @property
    def first_comparison(self) -> JsonDict:
        """Primary statistical comparison, normalized across old and new stats shapes."""

        return _first_comparison(self.stats)

    @property
    def mean_delta(self) -> float | None:
        """Mean candidate-baseline score delta for the primary comparison."""

        return _optional_number(self.first_comparison.get("mean_delta"))

    @property
    def bootstrap_ci(self) -> list[object] | None:
        """Bootstrap confidence interval for the primary comparison."""

        value = self.first_comparison.get("bootstrap_ci")
        return value if isinstance(value, list) else None

    @property
    def permutation_p_value(self) -> float | None:
        """Permutation-test p-value for the primary comparison."""

        return _optional_number(self.first_comparison.get("permutation_p_value"))

    @property
    def holm_adjusted_p_value(self) -> float | None:
        """Holm-adjusted p-value for the primary comparison."""

        return _optional_number(self.first_comparison.get("holm_adjusted_p_value"))


def _read_optional(path: Path) -> JsonDict:
    if not path.exists():
        return {}
    return read_json(path)


def _existing_artifacts(run_dir: Path, diagnostics: dict[str, JsonDict]) -> list[str]:
    names = [
        "manifest.json",
        "metrics.json",
        "baseline/metrics.json",
        "candidate/metrics.json",
        "stats.json",
        "splits.json",
        "gate_result.json",
        "comparison_validity.json",
        "explanation.json",
        "model_drift.json",
        "audit_result.json",
        "history_index.json",
        "history_compare.json",
        "agent_run.json",
        "research_bundle.json",
        "research_bundle.html",
        "research_diagnostics.json",
        "research_diagnostics.md",
        "research_diagnostics.html",
        "research_gap_plan.json",
        "research_gap_plan.md",
        "research_gap_plan.html",
        "research_gap_commands.ps1",
        "research_gap_commands.sh",
        "research_gap_status.json",
        "research_gap_status.md",
        "research_gap_status.html",
        "evidence_card.json",
        "evidence_card.md",
        "evidence_card.html",
        "claim_check.json",
        "claim_check.md",
        "claim_check.html",
        "evidence_from_result.json",
        "bridge_summary.json",
        "bridge_summary.md",
        "ecosystem_demo.json",
        "ecosystem_scorecard.json",
        "ecosystem_scorecard.md",
        "ecosystem_scorecard.html",
        "inputs/hidden_states.npz",
        "inputs/hidden_states.npz.metadata.json",
        "report.md",
        "report.html",
    ]
    artifacts = [name for name in names if (run_dir / name).exists()]
    artifacts.extend(f"diagnostics/{name}.json" for name in sorted(diagnostics))
    return artifacts


def _collect_diagnostics(path: Path) -> dict[str, JsonDict]:
    if not path.exists():
        return {}
    return {item.stem: read_json(item) for item in sorted(path.glob("*.json"))}


def _score(value: JsonDict) -> float | None:
    raw = value.get("mean_score")
    if isinstance(raw, int | float):
        return float(raw)
    return None


def _first_score(*values: JsonDict) -> float | None:
    for value in values:
        score = _score(value)
        if score is not None:
            return score
    return None


def _first_comparison(stats: JsonDict) -> JsonDict:
    comparisons = stats.get("comparisons")
    if isinstance(comparisons, list) and comparisons and isinstance(comparisons[0], dict):
        return comparisons[0]
    if any(
        key in stats
        for key in [
            "mean_delta",
            "bootstrap_ci",
            "permutation_p_value",
            "holm_adjusted_p_value",
        ]
    ):
        return stats
    return {}


def _optional_number(value: object) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    return None
