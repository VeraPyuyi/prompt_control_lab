"""Evidence-aware checkpoint comparison and post-training gate."""

from __future__ import annotations

import html
import math
from importlib import resources
from pathlib import Path
from typing import Any

from promptcontrollab.config import read_simple_yaml
from promptcontrollab.files import JsonDict, ensure_dir, read_json, write_json

_REQUIRED_ARTIFACTS = (
    "manifest.json",
    "metrics.json",
    "diagnostics/trajectory.json",
    "diagnostics/soft_hard.json",
    "diagnostics/generation_mismatch.json",
    "diagnostics/selective_risk.json",
)
_CANDIDATE_REQUIRED_ARTIFACTS = ("stats.json",)


def run_posttrain_gate(
    *,
    baseline_dir: Path,
    candidate_dir: Path,
    policy_path: Path | None,
    out_dir: Path,
) -> JsonDict:
    """Compare checkpoint evidence and write a bounded deployment decision."""

    baseline = baseline_dir.resolve()
    candidate = candidate_dir.resolve()
    policy, policy_label = _load_policy(policy_path)
    missing = _missing_artifacts(baseline, candidate)
    comparison = _build_comparison(baseline, candidate)
    invalid = _invalid_evidence(comparison)
    evidence_gaps = [*missing, *invalid]
    checks = _build_checks(comparison, policy, missing=evidence_gaps)
    decision = _decision(checks, missing=evidence_gaps)
    attribution = _build_attribution(comparison, checks)
    payload: JsonDict = {
        "schema": "prompt_control_lab.posttrain_gate.v1",
        "decision": decision,
        "baseline": str(baseline),
        "candidate": str(candidate),
        "policy_path": policy_label,
        "missing_artifacts": missing,
        "invalid_evidence": invalid,
        "checks": checks,
        "plain_summary": _plain_summary(decision, checks),
        "claim_boundary": (
            "This gate combines recorded checkpoint diagnostics. It supports selection and review, "
            "but does not prove that training caused a hidden-model mechanism."
        ),
    }
    ensure_dir(out_dir)
    write_json(out_dir / "posttrain_gate.json", payload)
    write_json(out_dir / "checkpoint_comparison.json", comparison)
    write_json(out_dir / "mechanism_attribution.json", attribution)
    markdown = render_posttrain_markdown(payload, comparison, attribution)
    (out_dir / "report.md").write_text(markdown, encoding="utf-8")
    (out_dir / "report.html").write_text(
        render_posttrain_html(payload, comparison, attribution), encoding="utf-8"
    )
    return payload


def render_posttrain_markdown(
    gate: JsonDict,
    comparison: JsonDict,
    attribution: JsonDict,
) -> str:
    """Render an auditable Markdown checkpoint report."""

    lines = [
        "# Post-training checkpoint gate",
        "",
        f"- Decision: `{gate['decision']}`",
        f"- Score delta: `{comparison.get('score_delta')}`",
        "- Paired bootstrap CI: "
        f"`{_dict(comparison.get('paired_statistics')).get('bootstrap_ci')}`",
        f"- Baseline: `{comparison.get('baseline_checkpoint')}`",
        f"- Candidate: `{comparison.get('candidate_checkpoint')}`",
        "",
        "## Checks",
        "",
        "| Check | Passed | Severity | Observation |",
        "|---|---:|---|---|",
    ]
    checks = gate.get("checks", {})
    if isinstance(checks, dict):
        for name, raw in checks.items():
            check = raw if isinstance(raw, dict) else {}
            lines.append(
                f"| {name} | {check.get('passed')} | {check.get('severity')} | "
                f"{check.get('message', '')} |"
            )
    lines.extend(["", "## Mechanism and boundary interpretation", ""])
    raw_findings = attribution.get("findings", [])
    if isinstance(raw_findings, list):
        for raw in raw_findings:
            if not isinstance(raw, dict):
                continue
            lines.extend(
                [
                    f"### {raw.get('dimension')}",
                    f"- Observed: {raw.get('observation')}",
                    f"- Explains: {raw.get('explanation')}",
                    f"- Boundary: {raw.get('claim_boundary')}",
                    f"- Next: {raw.get('next_action')}",
                    "",
                ]
            )
    lines.extend(["## Claim boundary", "", str(gate["claim_boundary"]), ""])
    return "\n".join(lines)


def render_posttrain_html(
    gate: JsonDict,
    comparison: JsonDict,
    attribution: JsonDict,
) -> str:
    """Render a compact reviewer-facing HTML checkpoint report."""

    cards: list[str] = []
    findings = attribution.get("findings", [])
    if isinstance(findings, list):
        for raw in findings:
            if not isinstance(raw, dict):
                continue
            cards.append(
                "<section>"
                f"<h2>{_escape(raw.get('dimension'))}</h2>"
                f"<p><b>Observed:</b> {_escape(raw.get('observation'))}</p>"
                f"<p><b>Explains:</b> {_escape(raw.get('explanation'))}</p>"
                f"<p><b>Boundary:</b> {_escape(raw.get('claim_boundary'))}</p>"
                f"<p><b>Next:</b> {_escape(raw.get('next_action'))}</p>"
                "</section>"
            )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width"><title>Post-training gate</title><style>
body{{font-family:Arial,sans-serif;background:#f5f7fa;color:#172b4d;margin:0}}
main{{max-width:1100px;margin:auto;padding:32px}}
header{{background:#153e75;color:white;padding:24px}}
.metrics{{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0}} .metric,section{{background:white;
border:1px solid #d9e2ec;border-radius:8px;padding:16px}} .metric{{min-width:180px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}}
p{{line-height:1.5;overflow-wrap:anywhere}}</style></head><body><main>
<header><h1>Post-training checkpoint gate</h1><p>{_escape(gate.get('plain_summary'))}</p></header>
<div class="metrics"><div class="metric"><b>Decision</b><br>{_escape(gate.get('decision'))}</div>
<div class="metric"><b>Score delta</b><br>{_escape(comparison.get('score_delta'))}</div>
<div class="metric"><b>Missing artifacts</b><br>{len(gate.get('missing_artifacts', []))}</div></div>
<div class="grid">{''.join(cards)}</div><p>{_escape(gate.get('claim_boundary'))}</p>
</main></body></html>"""


def _missing_artifacts(baseline: Path, candidate: Path) -> list[str]:
    missing: list[str] = []
    for label, root in [("baseline", baseline), ("candidate", candidate)]:
        missing.extend(
            f"{label}:{relative}"
            for relative in _REQUIRED_ARTIFACTS
            if not (root / relative).is_file()
        )
    missing.extend(
        f"candidate:{relative}"
        for relative in _CANDIDATE_REQUIRED_ARTIFACTS
        if not (candidate / relative).is_file()
    )
    return missing


def _load_policy(path: Path | None) -> tuple[JsonDict, str]:
    if path is not None:
        return read_simple_yaml(path), str(path.resolve())
    resource = (
        resources.files("promptcontrollab.template_data")
        .joinpath("policies")
        .joinpath("posttrain.policy.yaml")
    )
    with resources.as_file(resource) as resource_path:
        return read_simple_yaml(resource_path), "packaged-default"


def _build_comparison(baseline: Path, candidate: Path) -> JsonDict:
    baseline_manifest = _optional_json(baseline / "manifest.json")
    candidate_manifest = _optional_json(candidate / "manifest.json")
    baseline_metrics = _optional_json(baseline / "metrics.json")
    candidate_metrics = _optional_json(candidate / "metrics.json")
    candidate_stats = _optional_json(candidate / "stats.json")
    baseline_diagnostics = _diagnostics(baseline)
    candidate_diagnostics = _diagnostics(candidate)
    baseline_score = _optional_float(baseline_metrics.get("mean_score"))
    candidate_score = _optional_float(candidate_metrics.get("mean_score"))
    score_delta = _delta(candidate_score, baseline_score)
    slice_deltas, slice_coverage = _slice_comparison(baseline_metrics, candidate_metrics)
    return {
        "schema": "prompt_control_lab.checkpoint_comparison.v1",
        "baseline_checkpoint": _checkpoint_identity(baseline_manifest),
        "candidate_checkpoint": _checkpoint_identity(candidate_manifest),
        "baseline_score": baseline_score,
        "candidate_score": candidate_score,
        "score_delta": score_delta,
        "paired_statistics": _paired_statistics(candidate_stats),
        "evaluation_binding": _evaluation_binding(baseline_metrics, candidate_metrics),
        "slice_deltas": slice_deltas,
        "slice_coverage": slice_coverage,
        "resources": _resource_comparison(baseline_metrics, candidate_metrics),
        "provenance": {
            "baseline": _checkpoint(baseline_manifest),
            "candidate": _checkpoint(candidate_manifest),
        },
        "diagnostics": {
            "baseline": baseline_diagnostics,
            "candidate": candidate_diagnostics,
        },
    }


def _invalid_evidence(comparison: JsonDict) -> list[str]:
    invalid: list[str] = []
    if not str(comparison.get("baseline_checkpoint") or "").strip():
        invalid.append("baseline:manifest.checkpoint.id")
    if not str(comparison.get("candidate_checkpoint") or "").strip():
        invalid.append("candidate:manifest.checkpoint.id")
    if _optional_float(comparison.get("baseline_score")) is None:
        invalid.append("baseline:metrics.mean_score")
    if _optional_float(comparison.get("candidate_score")) is None:
        invalid.append("candidate:metrics.mean_score")
    diagnostics = _dict(comparison.get("diagnostics"))
    baseline = _dict(diagnostics.get("baseline"))
    candidate = _dict(diagnostics.get("candidate"))
    if _diagnostic_number(baseline, "trajectory", "mean_step_drift") is None:
        invalid.append("baseline:diagnostics.trajectory.mean_step_drift")
    if _diagnostic_number(candidate, "trajectory", "mean_step_drift") is None:
        invalid.append("candidate:diagnostics.trajectory.mean_step_drift")
    if _diagnostic_number(candidate, "generation_mismatch", "gap") is None:
        invalid.append("candidate:diagnostics.generation_mismatch.gap")
    if _diagnostic_number(candidate, "selective_risk", "observed_aurc") is None:
        invalid.append("candidate:diagnostics.selective_risk.observed_aurc")
    paired = _dict(comparison.get("paired_statistics"))
    interval = paired.get("bootstrap_ci")
    if not _valid_interval(interval):
        invalid.append("candidate:stats.bootstrap_ci")
    if not _valid_probability(paired.get("permutation_p_value")):
        invalid.append("candidate:stats.permutation_p_value")
    if not _valid_probability(paired.get("holm_adjusted_p_value")):
        invalid.append("candidate:stats.holm_adjusted_p_value")
    score_delta = _optional_float(comparison.get("score_delta"))
    paired_delta = _optional_float(paired.get("mean_delta"))
    if (
        score_delta is None
        or paired_delta is None
        or not math.isclose(score_delta, paired_delta, rel_tol=1e-9, abs_tol=1e-9)
    ):
        invalid.append("candidate:stats.mean_delta")
    if paired.get("baseline_checkpoint") != comparison.get("baseline_checkpoint"):
        invalid.append("candidate:stats.baseline_checkpoint")
    if paired.get("candidate_checkpoint") != comparison.get("candidate_checkpoint"):
        invalid.append("candidate:stats.candidate_checkpoint")
    provenance = _dict(comparison.get("provenance"))
    baseline_provenance = _dict(provenance.get("baseline"))
    candidate_provenance = _dict(provenance.get("candidate"))
    if paired.get("baseline_split_hash") != baseline_provenance.get("split_hash"):
        invalid.append("candidate:stats.baseline_split_hash")
    if paired.get("candidate_split_hash") != candidate_provenance.get("split_hash"):
        invalid.append("candidate:stats.candidate_split_hash")
    binding = _dict(comparison.get("evaluation_binding"))
    baseline_n = _optional_positive_int(binding.get("baseline_n"))
    candidate_n = _optional_positive_int(binding.get("candidate_n"))
    n_pairs = _optional_positive_int(paired.get("n_pairs"))
    if baseline_n is None:
        invalid.append("baseline:metrics.n")
    if candidate_n is None:
        invalid.append("candidate:metrics.n")
    if n_pairs is None or n_pairs != baseline_n or n_pairs != candidate_n:
        invalid.append("candidate:stats.n_pairs")
    baseline_sample_hash = binding.get("baseline_sample_hash")
    candidate_sample_hash = binding.get("candidate_sample_hash")
    if not _valid_sha256(baseline_sample_hash):
        invalid.append("baseline:metrics.sample_hash")
    if not _valid_sha256(candidate_sample_hash):
        invalid.append("candidate:metrics.sample_hash")
    if baseline_sample_hash != candidate_sample_hash:
        invalid.append("candidate:metrics.sample_hash_mismatch")
    if paired.get("baseline_sample_hash") != baseline_sample_hash:
        invalid.append("candidate:stats.baseline_sample_hash")
    if paired.get("candidate_sample_hash") != candidate_sample_hash:
        invalid.append("candidate:stats.candidate_sample_hash")
    coverage = _dict(comparison.get("slice_coverage"))
    missing_candidate = coverage.get("missing_in_candidate")
    if isinstance(missing_candidate, list):
        invalid.extend(f"candidate:metrics.by_slice.{name}" for name in missing_candidate)
    invalid_baseline = coverage.get("invalid_in_baseline")
    if isinstance(invalid_baseline, list):
        invalid.extend(f"baseline:metrics.by_slice.{name}" for name in invalid_baseline)
    invalid_candidate = coverage.get("invalid_in_candidate")
    if isinstance(invalid_candidate, list):
        invalid.extend(f"candidate:metrics.by_slice.{name}" for name in invalid_candidate)
    resources = _dict(comparison.get("resources"))
    resource_fields = [
        "baseline_tokens",
        "candidate_tokens",
        "baseline_latency_ms",
        "candidate_latency_ms",
    ]
    for key in resource_fields:
        if _optional_float(resources.get(key)) is None:
            invalid.append(f"metrics:{key}")
    soft_hard = _dict(candidate.get("soft_hard"))
    not_applicable = str(soft_hard.get("applicability", "")).lower() == "not_applicable"
    if not not_applicable and str(soft_hard.get("risk", "")) not in {"low", "medium", "high"}:
        invalid.append("candidate:diagnostics.soft_hard.risk")
    return invalid


def _build_checks(comparison: JsonDict, policy: JsonDict, *, missing: list[str]) -> JsonDict:
    diagnostics = comparison.get("diagnostics", {})
    diagnostic_dict = diagnostics if isinstance(diagnostics, dict) else {}
    baseline = _dict(diagnostic_dict.get("baseline"))
    candidate = _dict(diagnostic_dict.get("candidate"))
    return {
        "artifact_completeness": {
            "passed": not missing,
            "severity": "insufficient",
            "missing": missing,
            "message": (
                "Required checkpoint evidence is complete."
                if not missing
                else "Evidence is missing."
            ),
        },
        "provenance": _provenance_check(comparison, policy),
        "task_score": _minimum_delta_check(comparison, policy),
        "paired_uncertainty": _paired_uncertainty_check(comparison, policy),
        "slice_regression": _slice_check(comparison, policy),
        "resource_cost": _resource_check(comparison, policy),
        "trajectory_stability": _trajectory_check(baseline, candidate, policy),
        "soft_hard_deployment": _soft_hard_check(candidate, policy),
        "generation_mismatch": _generation_check(candidate, policy),
        "selective_risk": _selective_check(candidate, policy),
    }


def _provenance_check(comparison: JsonDict, policy: JsonDict) -> JsonDict:
    provenance = _dict(comparison.get("provenance"))
    baseline = _dict(provenance.get("baseline"))
    candidate = _dict(provenance.get("candidate"))
    split_match = baseline.get("split_hash") == candidate.get("split_hash") and bool(
        baseline.get("split_hash")
    )
    model_match = _model_key(baseline) == _model_key(candidate) and _model_key(baseline) != (
        "",
        "",
    )
    violations: list[str] = []
    if _bool(
        policy.get("require_split_hash_match"),
        key="require_split_hash_match",
        default=True,
    ) and not split_match:
        violations.append("split_hash_mismatch")
    if _bool(
        policy.get("require_model_match"),
        key="require_model_match",
        default=True,
    ) and not model_match:
        violations.append("model_mismatch")
    return {
        "passed": not violations,
        "severity": "fail",
        "violations": violations,
        "split_match": split_match,
        "model_match": model_match,
        "message": (
            "Checkpoint provenance is comparable." if not violations else "Provenance differs."
        ),
    }


def _minimum_delta_check(comparison: JsonDict, policy: JsonDict) -> JsonDict:
    threshold = _number(policy, "min_score_delta", 0.0)
    observed = _optional_float(comparison.get("score_delta"))
    passed = observed is not None and observed >= threshold
    return {
        "passed": passed,
        "severity": "fail",
        "observed": observed,
        "threshold": threshold,
        "message": (
            "Task score meets the checkpoint policy."
            if passed
            else "Task score is insufficient."
        ),
    }


def _slice_check(comparison: JsonDict, policy: JsonDict) -> JsonDict:
    threshold = _number(policy, "max_slice_regression", 0.05)
    deltas = _dict(comparison.get("slice_deltas"))
    regressed = {
        name: value
        for name, value in deltas.items()
        if isinstance(value, int | float) and float(value) < -threshold
    }
    return {
        "passed": not regressed,
        "severity": "review",
        "regressed_slices": regressed,
        "threshold": threshold,
        "message": (
            "No slice exceeds the regression allowance."
            if not regressed
            else "Slices regressed."
        ),
    }


def _paired_uncertainty_check(comparison: JsonDict, policy: JsonDict) -> JsonDict:
    threshold = _number(policy, "min_paired_ci_lower", 0.0)
    paired = _dict(comparison.get("paired_statistics"))
    interval = paired.get("bootstrap_ci")
    lower = _optional_float(interval[0]) if isinstance(interval, list) and interval else None
    passed = lower is not None and lower >= threshold
    return {
        "passed": passed,
        "severity": "review",
        "bootstrap_ci": interval,
        "permutation_p_value": paired.get("permutation_p_value"),
        "threshold": threshold,
        "message": (
            "The paired confidence interval meets policy."
            if passed
            else "The paired confidence interval crosses the review boundary."
        ),
    }


def _resource_check(comparison: JsonDict, policy: JsonDict) -> JsonDict:
    max_token = _number(policy, "max_token_increase_ratio", 0.2)
    max_latency = _number(policy, "max_latency_increase_ratio", 0.2)
    resources = _dict(comparison.get("resources"))
    token_ratio = _optional_float(resources.get("token_increase_ratio"))
    latency_ratio = _optional_float(resources.get("latency_increase_ratio"))
    passed = (
        token_ratio is not None
        and latency_ratio is not None
        and token_ratio <= max_token
        and latency_ratio <= max_latency
    )
    return {
        "passed": passed,
        "severity": "review",
        **resources,
        "max_token_increase_ratio": max_token,
        "max_latency_increase_ratio": max_latency,
        "message": (
            "Token and latency changes meet policy."
            if passed
            else "Token or latency cost increased beyond policy."
        ),
    }
def _trajectory_check(baseline: JsonDict, candidate: JsonDict, policy: JsonDict) -> JsonDict:
    threshold = _number(policy, "max_trajectory_drift_increase", 0.05)
    baseline_value = _diagnostic_number(baseline, "trajectory", "mean_step_drift")
    candidate_value = _diagnostic_number(candidate, "trajectory", "mean_step_drift")
    increase = _delta(candidate_value, baseline_value)
    passed = increase is not None and increase <= threshold
    return {
        "passed": passed,
        "severity": "fail",
        "baseline": baseline_value,
        "candidate": candidate_value,
        "increase": increase,
        "threshold": threshold,
        "message": (
            "Trajectory drift remains within policy."
            if passed
            else "Trajectory drift increased."
        ),
    }


def _soft_hard_check(candidate: JsonDict, policy: JsonDict) -> JsonDict:
    threshold = str(policy.get("max_soft_hard_risk", "medium"))
    if threshold not in {"low", "medium", "high"}:
        msg = "Policy key `max_soft_hard_risk` must be one of low, medium, or high"
        raise ValueError(msg)
    diagnostic = _dict(candidate.get("soft_hard"))
    if str(diagnostic.get("applicability", "")).lower() == "not_applicable":
        return {
            "passed": True,
            "applicable": False,
            "severity": "info",
            "observed": "not_applicable",
            "threshold": threshold,
            "message": str(
                diagnostic.get(
                    "reason",
                    "Soft-to-hard deployment is not applicable to this checkpoint.",
                )
            ),
        }
    observed = str(diagnostic.get("risk", "unknown"))
    passed = _risk_rank(observed) <= _risk_rank(threshold)
    return {
        "passed": passed,
        "applicable": True,
        "severity": "fail",
        "observed": observed,
        "threshold": threshold,
        "message": (
            "Soft-to-hard risk meets policy." if passed else "Soft-to-hard risk is too high."
        ),
    }


def _generation_check(candidate: JsonDict, policy: JsonDict) -> JsonDict:
    threshold = _number(policy, "max_generation_mismatch", 0.1)
    observed = _diagnostic_number(candidate, "generation_mismatch", "gap")
    passed = observed is not None and observed <= threshold
    return {
        "passed": passed,
        "severity": "fail",
        "observed": observed,
        "threshold": threshold,
        "message": (
            "Generation mismatch meets policy."
            if passed
            else "Generation mismatch is too large."
        ),
    }


def _selective_check(candidate: JsonDict, policy: JsonDict) -> JsonDict:
    threshold = _number(policy, "max_selective_aurc", 0.4)
    observed = _diagnostic_number(candidate, "selective_risk", "observed_aurc")
    passed = observed is not None and observed <= threshold
    return {
        "passed": passed,
        "severity": "review",
        "observed": observed,
        "threshold": threshold,
        "message": "Selective risk meets policy." if passed else "Selective risk needs review.",
    }


def _decision(checks: JsonDict, *, missing: list[str]) -> str:
    if missing:
        return "insufficient_evidence"
    values = [value for value in checks.values() if isinstance(value, dict)]
    if any(value.get("severity") == "fail" and value.get("passed") is False for value in values):
        return "hold"
    if any(value.get("severity") == "review" and value.get("passed") is False for value in values):
        return "needs_review"
    return "pass"


def _build_attribution(comparison: JsonDict, checks: JsonDict) -> JsonDict:
    dimensions = [
        ("task_score", "mechanism", "Task performance changed across matched checkpoints."),
        ("paired_uncertainty", "uncertainty", "Paired uncertainty was measured."),
        ("resource_cost", "decision", "Token and latency changes were measured."),
        ("trajectory_stability", "stability", "Hidden-state drift changed after training."),
        ("soft_hard_deployment", "boundary", "Deployment projection risk was recorded."),
        ("generation_mismatch", "boundary", "Teacher-forced and free-generation behavior differ."),
        ("selective_risk", "uncertainty", "Risk-coverage behavior was measured."),
    ]
    findings: list[JsonDict] = []
    for name, role, explanation in dimensions:
        check = _dict(checks.get(name))
        findings.append(
            {
                "dimension": name,
                "interpretation_role": role,
                "observation": check.get("message", "No recorded observation."),
                "explanation": explanation,
                "confidence": "medium" if check.get("passed") is not None else "unknown",
                "scope": "The matched baseline/candidate checkpoint artifacts.",
                "claim_boundary": (
                    "This association does not isolate training as a causal mechanism without a "
                    "controlled intervention."
                ),
                "next_action": _next_action(name, bool(check.get("passed"))),
                "evidence": check,
            }
        )
    return {
        "schema": "prompt_control_lab.mechanism_attribution.v1",
        "score_delta": comparison.get("score_delta"),
        "findings": findings,
    }


def _plain_summary(decision: str, checks: JsonDict) -> str:
    task_passed = _dict(checks.get("task_score")).get("passed") is True
    if decision == "pass":
        return "The candidate checkpoint meets the recorded performance and diagnostic policy."
    if decision == "insufficient_evidence":
        return (
            "The checkpoint decision is incomplete because required diagnostic evidence is missing."
        )
    if decision == "needs_review":
        return "No hard hold was triggered, but slice or uncertainty evidence needs review."
    if task_passed:
        return (
            "The score improvement is recorded, but a stability or deployment check requires hold."
        )
    return "The candidate checkpoint does not meet the configured hold criteria."


def _next_action(dimension: str, passed: bool) -> str:
    if passed:
        return f"Retain the `{dimension}` evidence with the checkpoint decision."
    return f"Inspect and rerun the `{dimension}` diagnostic before promotion."


def _diagnostics(root: Path) -> JsonDict:
    path = root / "diagnostics"
    if not path.is_dir():
        return {}
    return {item.stem: read_json(item) for item in sorted(path.glob("*.json"))}


def _checkpoint(manifest: JsonDict) -> JsonDict:
    return _dict(manifest.get("checkpoint"))


def _checkpoint_identity(manifest: JsonDict) -> str:
    checkpoint = _checkpoint(manifest)
    return str(checkpoint.get("id") or "").strip()


def _model_key(checkpoint: JsonDict) -> tuple[str, str]:
    return (str(checkpoint.get("provider") or ""), str(checkpoint.get("model_id") or ""))


def _slice_comparison(baseline: JsonDict, candidate: JsonDict) -> tuple[JsonDict, JsonDict]:
    baseline_slices = _dict(baseline.get("by_slice"))
    candidate_slices = _dict(candidate.get("by_slice"))
    result: JsonDict = {}
    matched = sorted(set(baseline_slices) & set(candidate_slices))
    invalid_baseline: list[str] = []
    invalid_candidate: list[str] = []
    for name in matched:
        baseline_value = _optional_float(baseline_slices.get(name))
        candidate_value = _optional_float(candidate_slices.get(name))
        if baseline_value is None:
            invalid_baseline.append(name)
        if candidate_value is None:
            invalid_candidate.append(name)
        if baseline_value is not None and candidate_value is not None:
            result[name] = _delta(candidate_value, baseline_value)
    return result, {
        "matched": matched,
        "missing_in_candidate": sorted(set(baseline_slices) - set(candidate_slices)),
        "new_in_candidate": sorted(set(candidate_slices) - set(baseline_slices)),
        "invalid_in_baseline": invalid_baseline,
        "invalid_in_candidate": invalid_candidate,
    }


def _paired_statistics(stats: JsonDict) -> JsonDict:
    comparisons = stats.get("comparisons")
    if isinstance(comparisons, list) and comparisons and isinstance(comparisons[0], dict):
        comparison = _dict(comparisons[0])
    else:
        comparison = stats
    return {
        "baseline_checkpoint": comparison.get("baseline_checkpoint"),
        "candidate_checkpoint": comparison.get("candidate_checkpoint"),
        "baseline_split_hash": comparison.get("baseline_split_hash"),
        "candidate_split_hash": comparison.get("candidate_split_hash"),
        "baseline_sample_hash": comparison.get("baseline_sample_hash"),
        "candidate_sample_hash": comparison.get("candidate_sample_hash"),
        "mean_delta": _optional_float(comparison.get("mean_delta")),
        "bootstrap_ci": _normalized_interval(comparison.get("bootstrap_ci")),
        "permutation_p_value": _optional_float(comparison.get("permutation_p_value")),
        "holm_adjusted_p_value": _optional_float(comparison.get("holm_adjusted_p_value")),
        "n_pairs": _optional_positive_int(comparison.get("n_pairs")),
    }


def _evaluation_binding(baseline: JsonDict, candidate: JsonDict) -> JsonDict:
    return {
        "baseline_n": _optional_positive_int(baseline.get("n")),
        "candidate_n": _optional_positive_int(candidate.get("n")),
        "baseline_sample_hash": baseline.get("sample_hash"),
        "candidate_sample_hash": candidate.get("sample_hash"),
    }


def _resource_comparison(baseline: JsonDict, candidate: JsonDict) -> JsonDict:
    baseline_tokens = _optional_float(baseline.get("mean_tokens"))
    candidate_tokens = _optional_float(candidate.get("mean_tokens"))
    baseline_latency = _optional_float(baseline.get("mean_latency_ms"))
    candidate_latency = _optional_float(candidate.get("mean_latency_ms"))
    return {
        "baseline_tokens": baseline_tokens,
        "candidate_tokens": candidate_tokens,
        "token_increase_ratio": _increase_ratio(candidate_tokens, baseline_tokens),
        "baseline_latency_ms": baseline_latency,
        "candidate_latency_ms": candidate_latency,
        "latency_increase_ratio": _increase_ratio(candidate_latency, baseline_latency),
    }


def _increase_ratio(candidate: float | None, baseline: float | None) -> float | None:
    if candidate is None or baseline is None or baseline <= 0:
        return None
    return round((candidate - baseline) / baseline, 12)


def _normalized_interval(value: object) -> list[float] | None:
    if not _valid_interval(value):
        return None
    assert isinstance(value, list)
    lower = _optional_float(value[0])
    upper = _optional_float(value[1])
    if lower is None or upper is None:
        return None
    return [lower, upper]


def _valid_interval(value: object) -> bool:
    if not isinstance(value, list) or len(value) != 2:
        return False
    lower = _optional_float(value[0])
    upper = _optional_float(value[1])
    return lower is not None and upper is not None and lower <= upper


def _diagnostic_number(diagnostics: JsonDict, name: str, key: str) -> float | None:
    return _optional_float(_dict(diagnostics.get(name)).get(key))


def _delta(candidate: float | None, baseline: float | None) -> float | None:
    if candidate is None or baseline is None:
        return None
    return round(candidate - baseline, 12)


def _number(policy: JsonDict, key: str, default: float) -> float:
    value = policy.get(key, default)
    converted = _optional_float(value)
    if converted is None:
        msg = f"Policy key `{key}` must be numeric"
        raise ValueError(msg)
    return converted


def _optional_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        converted = float(value)
        return converted if math.isfinite(converted) else None
    if isinstance(value, str):
        try:
            converted = float(value)
            return converted if math.isfinite(converted) else None
        except ValueError:
            return None
    return None


def _optional_positive_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _valid_sha256(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        return False
    digest = value.removeprefix("sha256:")
    return len(digest) == 64 and all(character in "0123456789abcdef" for character in digest)


def _valid_probability(value: object) -> bool:
    converted = _optional_float(value)
    return converted is not None and 0.0 <= converted <= 1.0


def _bool(value: object, *, key: str, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    raise ValueError(f"Policy key `{key}` must be true or false")


def _risk_rank(value: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(value, 3)


def _optional_json(path: Path) -> JsonDict:
    return read_json(path) if path.is_file() else {}


def _dict(value: object) -> JsonDict:
    return value if isinstance(value, dict) else {}


def _escape(value: object) -> str:
    return html.escape(str(value if value is not None else ""))
