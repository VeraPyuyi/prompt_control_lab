"""Shared structured data model for reports and the local UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from promptcontrollab.core.files import JsonDict, read_json

_CONTROL_CERTIFICATE_NAMES = (
    "terminal_sensitivity",
    "green_certificate",
    "posterior_certificate",
)


@dataclass(frozen=True)
class ReportModel:
    """Structured view over PromptControlLab run artifacts."""

    run_dir: Path
    manifest: JsonDict
    source_manifest: JsonDict
    evidence_matrix: JsonDict
    interpretability_report: JsonDict
    peoc_evidence: JsonDict
    peoc_case_study: JsonDict
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
    posttrain_gate: JsonDict
    checkpoint_comparison: JsonDict
    mechanism_attribution: JsonDict
    research_diagnostics: JsonDict
    research_gap_plan: JsonDict
    research_gap_status: JsonDict
    evidence_card: JsonDict
    evidence_gate: JsonDict
    claim_check: JsonDict
    external_evidence: JsonDict
    bridge_summary: JsonDict
    ecosystem_demo: JsonDict
    ecosystem_scorecard: JsonDict
    prompt_assets: JsonDict
    prompt_optimizer_gap_plan: JsonDict
    scaffold_check: JsonDict
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
        diagnostics = _collect_diagnostics(run_dir)
        artifacts = _existing_artifacts(run_dir, diagnostics)
        return cls(
            run_dir=run_dir,
            manifest=manifest,
            source_manifest=_read_optional(run_dir / "source_manifest.json"),
            evidence_matrix=_read_optional(run_dir / "evidence_matrix.json"),
            interpretability_report=_read_optional(run_dir / "interpretability_report.json"),
            peoc_evidence=_read_optional(run_dir / "peoc_evidence.json"),
            peoc_case_study=_read_optional(run_dir / "research_case_study.json"),
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
            posttrain_gate=_read_optional(run_dir / "posttrain_gate.json"),
            checkpoint_comparison=_read_optional(run_dir / "checkpoint_comparison.json"),
            mechanism_attribution=_read_optional(run_dir / "mechanism_attribution.json"),
            research_diagnostics=_read_optional(run_dir / "research_diagnostics.json"),
            research_gap_plan=_read_optional(run_dir / "research_gap_plan.json"),
            research_gap_status=_read_optional(run_dir / "research_gap_status.json"),
            evidence_card=_read_optional(run_dir / "evidence_card.json"),
            evidence_gate=_read_optional(run_dir / "evidence_gate_result.json"),
            claim_check=_read_optional(run_dir / "claim_check.json"),
            external_evidence=_read_optional(run_dir / "evidence_from_result.json"),
            bridge_summary=_read_optional(run_dir / "bridge_summary.json"),
            ecosystem_demo=_read_optional(run_dir / "ecosystem_demo.json"),
            ecosystem_scorecard=_read_optional(run_dir / "ecosystem_scorecard.json"),
            prompt_assets=_read_optional(run_dir / "prompt_assets.json"),
            prompt_optimizer_gap_plan=_read_optional(run_dir / "prompt_optimizer_gap_plan.json"),
            scaffold_check=_read_optional(run_dir / "eval_scaffold" / "scaffold_check.json"),
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
    """List known report artifacts that exist for a run.

    Args:
        run_dir: Run directory containing evaluation artifacts.
        diagnostics: Diagnostic artifacts already loaded from the run.

    Returns:
        Stable relative artifact names suitable for reports and user interfaces.
    """

    names = [
        "manifest.json",
        "source_manifest.json",
        "evidence_matrix.json",
        "interpretability_report.json",
        "interpretability_report.html",
        "peoc_evidence.json",
        "research_case_study.json",
        "research_case_study.md",
        "research_case_study.html",
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
        "posttrain_gate.json",
        "checkpoint_comparison.json",
        "mechanism_attribution.json",
        "research_bundle.json",
        "research_bundle.html",
        "research_overview.svg",
        "research_bundle_verification.json",
        "research_bundle_verification.md",
        "research_bundle_verification.html",
        "source_input_verification.json",
        "source_input_verification.md",
        "source_input_verification.html",
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
        "evidence_gate_result.json",
        "evidence_gate_result.md",
        "evidence_gate_result.html",
        "claim_check.json",
        "claim_check.md",
        "claim_check.html",
        "evidence_from_result.json",
        "evidence_audit_result.json",
        "evidence_audit_result.md",
        "evidence_audit_result.html",
        "bridge_summary.json",
        "bridge_summary.md",
        "bridge_summary.html",
        "ecosystem_demo.json",
        "ecosystem_scorecard.json",
        "ecosystem_scorecard.md",
        "ecosystem_scorecard.html",
        "prompt_assets.json",
        "prompt_assets.md",
        "prompt_assets.html",
        "prompt_optimizer_gap_plan.json",
        "prompt_optimizer_gap_plan.md",
        "prompt_optimizer_gap_plan.html",
        "eval_scaffold/scaffold_check.json",
        "eval_scaffold/scaffold_check.md",
        "eval_scaffold/scaffold_check.html",
        "eval_scaffold/prompt_optimizer_eval_scaffold.json",
        "eval_scaffold/promptcontrol.prompt_optimizer.example.yaml",
        "eval_scaffold/tasks.template.jsonl",
        "eval_scaffold/baseline_predictions.template.jsonl",
        "eval_scaffold/candidate_predictions.template.jsonl",
        "inputs/hidden_states.npz",
        "inputs/hidden_states.npz.metadata.json",
        "report.md",
        "report.html",
    ]
    artifacts = [name for name in names if (run_dir / name).exists()]
    for name in sorted(diagnostics):
        nested = run_dir / "diagnostics" / f"{name}.json"
        artifacts.append(
            f"diagnostics/{name}.json" if nested.is_file() else f"{name}.json"
        )
    return artifacts


def _collect_diagnostics(run_dir: Path) -> dict[str, JsonDict]:
    result: dict[str, JsonDict] = {}
    nested = run_dir / "diagnostics"
    if nested.is_dir():
        result.update({item.stem: read_json(item) for item in sorted(nested.glob("*.json"))})
    for name in _CONTROL_CERTIFICATE_NAMES:
        path = run_dir / f"{name}.json"
        if name not in result and path.is_file():
            result[name] = read_json(path)
    return result


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
