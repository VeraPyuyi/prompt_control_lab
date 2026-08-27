"""Evidence-aware checkpoint comparison and post-training gate."""

from __future__ import annotations

import html
import math
from importlib import resources
from pathlib import Path
from typing import Any, cast

from promptcontrollab.core.config import read_simple_yaml
from promptcontrollab.core.files import JsonDict, ensure_dir, read_json, write_json

_REQUIRED_ARTIFACTS = (
    "manifest.json",
    "metrics.json",
    "diagnostics/trajectory.json",
    "diagnostics/soft_hard.json",
    "diagnostics/generation_mismatch.json",
    "diagnostics/selective_risk.json",
    "diagnostics/prompt_reachability.json",
    "diagnostics/readout_alignment.json",
    "diagnostics/prompt_routing.json",
    "diagnostics/prompt_projection.json",
    "diagnostics/prompt_stability.json",
)
_CANDIDATE_REQUIRED_ARTIFACTS = ("stats.json",)
_BLACK_BOX_REQUIRED_ARTIFACTS = ("manifest.json", "metrics.json")
_BLACK_BOX_CANDIDATE_ARTIFACTS = (
    "stats.json",
    "diagnostics/selective_risk.json",
)
_CAPABILITY_PROFILES = {"auto", "full-open-model", "black-box"}
_CONTROL_CERTIFICATES = {
    "terminal_sensitivity": "require_terminal_sensitivity",
    "green_certificate": "require_green_certificate",
    "posterior_certificate": "require_posterior_certificate",
}
_CONTROL_CERTIFICATE_LEVELS = {
    "insufficient_evidence": 0,
    "not_applicable": 0,
    "empirical_only": 1,
    "surrogate_consistent": 2,
    "certificate_verified": 3,
}
_MINIMUM_CONTROL_CERTIFICATE_LEVELS = {
    "empirical_only",
    "surrogate_consistent",
    "certificate_verified",
}
_CONTROL_CERTIFICATE_SCHEMAS = {
    "terminal_sensitivity": "prompt_control_lab.terminal_sensitivity.v1",
    "green_certificate": "prompt_control_lab.green_certificate.v1",
    "posterior_certificate": "prompt_control_lab.posterior_certificate.v1",
}
_CONTROL_CERTIFICATE_NATURAL_MAXIMUM = {
    "terminal_sensitivity": "empirical_only",
    "green_certificate": "certificate_verified",
    "posterior_certificate": "certificate_verified",
}
_CONTROL_CERTIFICATE_STATES = {"passed", "conditions_not_met", "missing", "invalid"}


def run_posttrain_gate(
    *,
    baseline_dir: Path,
    candidate_dir: Path,
    policy_path: Path | None,
    out_dir: Path,
    capability: str = "auto",
) -> JsonDict:
    """Compare checkpoint evidence and write a bounded deployment decision."""

    baseline = baseline_dir.resolve()
    candidate = candidate_dir.resolve()
    capability_profile = _resolve_capability_profile(baseline, candidate, capability)
    policy, policy_label = _load_policy(policy_path)
    missing = _missing_artifacts(baseline, candidate, capability_profile, policy)
    comparison = _build_comparison(baseline, candidate)
    invalid = _invalid_evidence(comparison, capability_profile, policy)
    evidence_gaps = [*missing, *invalid]
    checks = _build_checks(
        comparison,
        policy,
        missing=missing,
        invalid=invalid,
        capability_profile=capability_profile,
    )
    decision = _decision(checks, missing=evidence_gaps)
    certificate_summary = _certificate_summary(checks, policy)
    attribution = _build_attribution(comparison, checks)
    decision_trace = _build_decision_trace(
        checks,
        decision=decision,
        capability_profile=capability_profile,
    )
    payload: JsonDict = {
        "schema": "prompt_control_lab.posttrain_gate.v1",
        "decision": decision,
        "capability_profile": capability_profile,
        "baseline": str(baseline),
        "candidate": str(candidate),
        "policy_path": policy_label,
        "missing_artifacts": missing,
        "invalid_evidence": invalid,
        "checks": checks,
        "certificate_summary": certificate_summary,
        "plain_summary": _plain_summary(
            decision,
            checks,
            missing=missing,
            invalid=invalid,
        ),
        "claim_boundary": (
            "This gate combines recorded checkpoint diagnostics. It supports selection and review, "
            "but does not prove that training caused a hidden-model mechanism."
        ),
    }
    ensure_dir(out_dir)
    write_json(out_dir / "posttrain_gate.json", payload)
    write_json(out_dir / "checkpoint_comparison.json", comparison)
    write_json(out_dir / "mechanism_attribution.json", attribution)
    write_json(out_dir / "decision_trace.json", decision_trace)
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


def _missing_artifacts(
    baseline: Path,
    candidate: Path,
    capability_profile: str,
    policy: JsonDict,
) -> list[str]:
    missing: list[str] = []
    if capability_profile == "black-box":
        for label, root in (("baseline", baseline), ("candidate", candidate)):
            missing.extend(
                f"{label}:{relative}"
                for relative in _BLACK_BOX_REQUIRED_ARTIFACTS
                if not (root / relative).is_file()
            )
        missing.extend(
            f"candidate:{relative}"
            for relative in _BLACK_BOX_CANDIDATE_ARTIFACTS
            if not (candidate / relative).is_file()
        )
        return [*missing, *_missing_required_control_certificates(candidate, policy)]
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
    return [*missing, *_missing_required_control_certificates(candidate, policy)]


def _missing_required_control_certificates(candidate: Path, policy: JsonDict) -> list[str]:
    minimum = _minimum_control_certificate_level(policy)
    missing: list[str] = []
    for name, required_key in _CONTROL_CERTIFICATES.items():
        required = _bool(policy.get(required_key), key=required_key, default=False)
        if (required or minimum is not None) and not (
            candidate / "diagnostics" / f"{name}.json"
        ).is_file():
            missing.append(f"candidate:diagnostics/{name}.json")
    return missing


def _resolve_capability_profile(
    baseline: Path,
    candidate: Path,
    requested: str,
) -> str:
    if requested not in _CAPABILITY_PROFILES:
        supported = ", ".join(sorted(_CAPABILITY_PROFILES))
        raise ValueError(f"Unsupported post-training capability `{requested}`; use {supported}")
    if requested != "auto":
        return requested
    manifests = [
        _optional_json(baseline / "manifest.json"),
        _optional_json(candidate / "manifest.json"),
    ]
    hidden_state_flags: list[bool] = []
    for manifest in manifests:
        capabilities = _dict(_checkpoint(manifest).get("capabilities"))
        hidden_state = capabilities.get("hidden_states")
        if isinstance(hidden_state, bool):
            hidden_state_flags.append(hidden_state)
    if hidden_state_flags and not all(hidden_state_flags):
        return "black-box"
    trajectory_available = all(
        (root / "diagnostics/trajectory.json").is_file() for root in (baseline, candidate)
    )
    return "full-open-model" if trajectory_available else "black-box"


def _not_applicable_check(message: str) -> JsonDict:
    return {
        "passed": None,
        "applicable": False,
        "severity": "info",
        "observed": "not_applicable",
        "evidence_status": "not_applicable",
        "message": message,
    }


def _build_decision_trace(
    checks: JsonDict,
    *,
    decision: str,
    capability_profile: str,
) -> JsonDict:
    evidence_map = {
        "artifact_completeness": ["manifest.json", "metrics.json", "stats.json"],
        "evidence_validity": ["checkpoint_comparison.json"],
        "provenance": ["checkpoint_comparison.json"],
        "task_score": ["checkpoint_comparison.json"],
        "paired_uncertainty": ["checkpoint_comparison.json"],
        "slice_regression": ["checkpoint_comparison.json"],
        "resource_cost": ["checkpoint_comparison.json"],
        "trajectory_stability": ["diagnostics/trajectory.json"],
        "soft_hard_deployment": ["diagnostics/soft_hard.json"],
        "generation_mismatch": ["diagnostics/generation_mismatch.json"],
        "selective_risk": ["diagnostics/selective_risk.json"],
        "prompt_reachability": ["diagnostics/prompt_reachability.json"],
        "readout_alignment": ["diagnostics/readout_alignment.json"],
        "prompt_routing": ["diagnostics/prompt_routing.json"],
        "prompt_projection": ["diagnostics/prompt_projection.json"],
        "prompt_stability": ["diagnostics/prompt_stability.json"],
        "terminal_sensitivity": ["diagnostics/terminal_sensitivity.json"],
        "green_certificate": ["diagnostics/green_certificate.json"],
        "posterior_certificate": ["diagnostics/posterior_certificate.json"],
    }
    rows: list[JsonDict] = []
    for name, raw in checks.items():
        if not isinstance(raw, dict):
            continue
        check = _dict(raw)
        applicable = check.get("applicable") is not False
        passed = check.get("passed") is True
        severity = str(check.get("severity", "info"))
        if not applicable:
            status = "not_applicable"
            impact = "none"
        elif passed:
            status = "passed"
            impact = "none"
        else:
            status = "triggered"
            impact = {
                "fail": "hold",
                "review": "needs_review",
                "insufficient": "insufficient_evidence",
            }.get(severity, "needs_review")
        observed = next(
            (
                check[key]
                for key in (
                    "observed",
                    "increase",
                    "bootstrap_ci",
                    "regressed_slices",
                    "violations",
                    "missing",
                    "invalid",
                )
                if key in check
            ),
            check.get("message"),
        )
        threshold = check.get("threshold")
        if threshold is None and name == "resource_cost":
            threshold = {
                "max_token_increase_ratio": check.get("max_token_increase_ratio"),
                "max_latency_increase_ratio": check.get("max_latency_increase_ratio"),
            }
        rows.append(
            {
                "check": name,
                "observed": observed,
                "threshold": threshold,
                "status": status,
                "impact": impact,
                "evidence": evidence_map.get(name, ["posttrain_gate.json"]),
                "next_action": _next_action(name, passed or not applicable),
            }
        )
    return {
        "schema": "prompt_control_lab.posttrain_decision_trace.v1",
        "decision": decision,
        "capability_profile": capability_profile,
        "checks": rows,
        "claim_boundary": (
            "The trace records how configured evidence checks produced the gate decision; it is "
            "not a causal proof of model behavior."
        ),
    }


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


def _invalid_evidence(
    comparison: JsonDict,
    capability_profile: str,
    policy: JsonDict,
) -> list[str]:
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
    if capability_profile == "full-open-model":
        if _diagnostic_number(baseline, "trajectory", "mean_step_drift") is None:
            invalid.append("baseline:diagnostics.trajectory.mean_step_drift")
        if _diagnostic_number(candidate, "trajectory", "mean_step_drift") is None:
            invalid.append("candidate:diagnostics.trajectory.mean_step_drift")
        if _diagnostic_number(candidate, "generation_mismatch", "gap") is None:
            invalid.append("candidate:diagnostics.generation_mismatch.gap")
        saturation = _diagnostic_number(
            candidate,
            "generation_mismatch",
            "generation_saturation_rate",
        )
        if saturation is not None and saturation > _number(
            policy,
            "max_generation_saturation_rate",
            0.0,
        ):
            invalid.append(
                "candidate:diagnostics.generation_mismatch.generation_saturation_rate"
            )
    if _diagnostic_number(candidate, "selective_risk", "observed_aurc") is None:
        invalid.append("candidate:diagnostics.selective_risk.observed_aurc")
    for name in _CONTROL_CERTIFICATES:
        diagnostic = _dict(candidate.get(name))
        if diagnostic:
            invalid.extend(
                f"candidate:diagnostics.{name}.{field}"
                for field in _control_certificate_validation_errors(name, diagnostic)
            )
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
    if capability_profile == "full-open-model":
        for label, checkpoint in (
            ("baseline", baseline_provenance),
            ("candidate", candidate_provenance),
        ):
            for field in (
                "provider",
                "model_id",
                "model_revision",
                "model_snapshot_sha256",
                "training_method",
            ):
                if not str(checkpoint.get(field) or "").strip():
                    invalid.append(f"{label}:manifest.checkpoint.{field}")
            seed = checkpoint.get("seed")
            if not isinstance(seed, int) or isinstance(seed, bool):
                invalid.append(f"{label}:manifest.checkpoint.seed")
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
    if capability_profile == "full-open-model":
        soft_hard = _dict(candidate.get("soft_hard"))
        not_applicable = str(soft_hard.get("applicability", "")).lower() == "not_applicable"
        if not not_applicable and str(soft_hard.get("risk", "")) not in {
            "low",
            "medium",
            "high",
        }:
            invalid.append("candidate:diagnostics.soft_hard.risk")
        reachability = _dict(candidate.get("prompt_reachability"))
        if _optional_float(
            reachability.get("representation_shift_l2_normalized")
        ) is None:
            invalid.append(
                "candidate:diagnostics.prompt_reachability."
                "representation_shift_l2_normalized"
            )
        readout = _dict(candidate.get("readout_alignment"))
        if _optional_float(readout.get("alignment_gap")) is None:
            invalid.append("candidate:diagnostics.readout_alignment.alignment_gap")
        routing = _dict(candidate.get("prompt_routing"))
        if not str(routing.get("evidence_status") or "").strip():
            invalid.append("candidate:diagnostics.prompt_routing.evidence_status")
        projection = _dict(candidate.get("prompt_projection"))
        projection_not_applicable = (
            str(projection.get("applicability", "")).lower() == "not_applicable"
        )
        if not projection_not_applicable and _optional_float(
            projection.get("projection_gap", projection.get("mean_projection_distance"))
        ) is None:
            invalid.append("candidate:diagnostics.prompt_projection.projection_gap")
        baseline_stability = _dict(baseline.get("prompt_stability"))
        candidate_stability = _dict(candidate.get("prompt_stability"))
        if _optional_float(baseline_stability.get("mean_step_drift")) is None:
            invalid.append("baseline:diagnostics.prompt_stability.mean_step_drift")
        if _optional_float(candidate_stability.get("mean_step_drift")) is None:
            invalid.append("candidate:diagnostics.prompt_stability.mean_step_drift")
    return invalid


def _build_checks(
    comparison: JsonDict,
    policy: JsonDict,
    *,
    missing: list[str],
    invalid: list[str],
    capability_profile: str,
) -> JsonDict:
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
        "evidence_validity": {
            "passed": not invalid,
            "severity": "insufficient",
            "invalid": invalid,
            "message": (
                "Recorded checkpoint evidence passes validity checks."
                if not invalid
                else "Recorded evidence is invalid or outside configured validity bounds."
            ),
        },
        "provenance": _provenance_check(comparison, policy),
        "task_score": _minimum_delta_check(comparison, policy),
        "paired_uncertainty": _paired_uncertainty_check(comparison, policy),
        "slice_regression": _slice_check(comparison, policy),
        "resource_cost": _resource_check(comparison, policy),
        "trajectory_stability": (
            _trajectory_check(baseline, candidate, policy)
            if capability_profile == "full-open-model"
            else _not_applicable_check("Hidden-state trajectory access was not recorded.")
        ),
        "soft_hard_deployment": (
            _soft_hard_check(candidate, policy)
            if capability_profile == "full-open-model"
            else _not_applicable_check("Soft-prompt projection evidence was not requested.")
        ),
        "generation_mismatch": (
            _generation_check(candidate, policy)
            if capability_profile == "full-open-model"
            else _not_applicable_check("Teacher-forced logits were not available.")
        ),
        "selective_risk": _selective_check(candidate, policy),
        "prompt_reachability": (
            _prompt_reachability_check(candidate, policy)
            if capability_profile == "full-open-model"
            else _not_applicable_check("Checkpoint representation access was not recorded.")
        ),
        "readout_alignment": (
            _readout_alignment_check(candidate, policy)
            if capability_profile == "full-open-model"
            else _not_applicable_check("Output-head alignment evidence was not available.")
        ),
        "prompt_routing": (
            _prompt_routing_check(candidate, policy)
            if capability_profile == "full-open-model"
            else _not_applicable_check("Prompt-routing interventions were not available.")
        ),
        "prompt_projection": (
            _prompt_projection_check(candidate, policy)
            if capability_profile == "full-open-model"
            else _not_applicable_check("Prompt projection was not used by this checkpoint.")
        ),
        "prompt_stability": (
            _prompt_stability_check(baseline, candidate, policy)
            if capability_profile == "full-open-model"
            else _not_applicable_check("Checkpoint representation access was not recorded.")
        ),
        "terminal_sensitivity": _control_certificate_check(
            "terminal_sensitivity",
            candidate,
            policy,
            capability_profile=capability_profile,
        ),
        "green_certificate": _control_certificate_check(
            "green_certificate",
            candidate,
            policy,
            capability_profile=capability_profile,
        ),
        "posterior_certificate": _control_certificate_check(
            "posterior_certificate",
            candidate,
            policy,
            capability_profile=capability_profile,
        ),
    }


def _provenance_check(comparison: JsonDict, policy: JsonDict) -> JsonDict:
    provenance = _dict(comparison.get("provenance"))
    baseline = _dict(provenance.get("baseline"))
    candidate = _dict(provenance.get("candidate"))
    split_match = baseline.get("split_hash") == candidate.get("split_hash") and bool(
        baseline.get("split_hash")
    )
    baseline_model = _model_key(baseline)
    candidate_model = _model_key(candidate)
    model_complete = all(baseline_model) and all(candidate_model)
    model_match = model_complete and baseline_model == candidate_model
    training_method_match = bool(baseline.get("training_method")) and (
        baseline.get("training_method") == candidate.get("training_method")
    )
    baseline_seed = baseline.get("seed")
    candidate_seed = candidate.get("seed")
    seed_complete = all(
        isinstance(value, int) and not isinstance(value, bool)
        for value in (baseline_seed, candidate_seed)
    )
    seed_match = seed_complete and baseline_seed == candidate_seed
    violations: list[str] = []
    missing_identity: list[str] = []
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
    ):
        if not model_complete:
            missing_identity.append("model_snapshot_identity")
        elif not model_match:
            violations.append("model_mismatch")
    if _bool(
        policy.get("require_training_method_match"),
        key="require_training_method_match",
        default=True,
    ):
        if not baseline.get("training_method") or not candidate.get("training_method"):
            missing_identity.append("training_method")
        elif not training_method_match:
            violations.append("training_method_mismatch")
    if _bool(
        policy.get("require_seed_match"),
        key="require_seed_match",
        default=True,
    ):
        if not seed_complete:
            missing_identity.append("seed")
        elif not seed_match:
            violations.append("seed_mismatch")
    return {
        "passed": not violations and not missing_identity,
        "severity": "fail" if violations else "insufficient" if missing_identity else "info",
        "violations": violations,
        "missing_identity": missing_identity,
        "split_match": split_match,
        "model_match": model_match,
        "training_method_match": training_method_match,
        "seed_match": seed_match,
        "model_identity": {
            "baseline": baseline_model,
            "candidate": candidate_model,
        },
        "message": (
            "Checkpoint provenance is comparable."
            if not violations and not missing_identity
            else "Checkpoint provenance differs or is incomplete."
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
        result = _not_applicable_check(
            str(
                diagnostic.get(
                    "reason",
                    "Soft-to-hard deployment is not applicable to this checkpoint.",
                )
            )
        )
        result["threshold"] = threshold
        return result
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


def _prompt_reachability_check(candidate: JsonDict, policy: JsonDict) -> JsonDict:
    diagnostic = _dict(candidate.get("prompt_reachability"))
    if not diagnostic:
        return _not_applicable_check("Prompt reachability evidence was not recorded.")
    threshold = _number(policy, "max_prompt_reachability_shift", 0.5)
    observed = _optional_float(diagnostic.get("representation_shift_l2_normalized"))
    passed = observed is not None and observed <= threshold
    return {
        "passed": passed,
        "applicable": True,
        "severity": "review" if observed is not None else "insufficient",
        "observed": observed,
        "threshold": threshold,
        "message": (
            "Checkpoint representation shift remains within the review boundary."
            if passed
            else "Checkpoint representation shift needs inspection."
        ),
    }


def _readout_alignment_check(candidate: JsonDict, policy: JsonDict) -> JsonDict:
    diagnostic = _dict(candidate.get("readout_alignment"))
    if not diagnostic:
        return _not_applicable_check("Readout alignment evidence was not recorded.")
    threshold = _number(policy, "max_readout_alignment_gap", 0.1)
    observed = _optional_float(diagnostic.get("alignment_gap"))
    passed = observed is not None and observed <= threshold
    return {
        "passed": passed,
        "applicable": True,
        "severity": "fail" if observed is not None else "insufficient",
        "observed": observed,
        "threshold": threshold,
        "message": (
            "Readout alignment meets policy."
            if passed
            else "Teacher-forced and generated answers are not sufficiently aligned."
        ),
    }


def _prompt_routing_check(candidate: JsonDict, policy: JsonDict) -> JsonDict:
    diagnostic = _dict(candidate.get("prompt_routing"))
    if not diagnostic:
        return _not_applicable_check("Prompt-routing evidence was not recorded.")
    status = str(diagnostic.get("evidence_status", "unknown")).strip().lower()
    observed = status in {"observed", "supported", "intervention_observed"}
    require_evidence = _bool(
        policy.get("require_prompt_routing_evidence"),
        key="require_prompt_routing_evidence",
        default=False,
    )
    if not observed and not require_evidence:
        return {
            "passed": False,
            "applicable": True,
            "severity": "insufficient",
            "observed": status,
            "evidence_status": "insufficient_evidence",
            "threshold": "observed intervention evidence",
            "message": (
                "Prompt routing remains insufficient because no routing intervention was "
                "available."
            ),
        }
    return {
        "passed": observed,
        "applicable": True,
        "severity": "insufficient",
        "observed": status,
        "evidence_status": "observed" if observed else "insufficient_evidence",
        "threshold": "observed intervention evidence",
        "message": (
            "Prompt-routing intervention evidence was recorded."
            if observed
            else "Required prompt-routing intervention evidence is missing."
        ),
    }


def _prompt_projection_check(candidate: JsonDict, policy: JsonDict) -> JsonDict:
    diagnostic = _dict(candidate.get("prompt_projection"))
    if not diagnostic:
        return _not_applicable_check("Prompt projection evidence was not recorded.")
    if str(diagnostic.get("applicability", "")).lower() == "not_applicable":
        return _not_applicable_check(
            str(
                diagnostic.get(
                    "reason",
                    "This checkpoint does not deploy a learned prompt projection.",
                )
            )
        )
    threshold = _number(policy, "max_prompt_projection_gap", 0.5)
    observed = _optional_float(
        diagnostic.get("projection_gap", diagnostic.get("mean_projection_distance"))
    )
    passed = observed is not None and observed <= threshold
    return {
        "passed": passed,
        "applicable": True,
        "severity": "fail" if observed is not None else "insufficient",
        "observed": observed,
        "threshold": threshold,
        "message": (
            "Prompt projection gap meets policy."
            if passed
            else "Prompt projection evidence is missing or exceeds policy."
        ),
    }


def _prompt_stability_check(
    baseline: JsonDict,
    candidate: JsonDict,
    policy: JsonDict,
) -> JsonDict:
    baseline_diagnostic = _dict(baseline.get("prompt_stability"))
    candidate_diagnostic = _dict(candidate.get("prompt_stability"))
    if not baseline_diagnostic and not candidate_diagnostic:
        return _not_applicable_check("Prompt stability evidence was not recorded.")
    threshold = _number(policy, "max_prompt_stability_drift_increase", 0.05)
    baseline_value = _optional_float(baseline_diagnostic.get("mean_step_drift"))
    candidate_value = _optional_float(candidate_diagnostic.get("mean_step_drift"))
    increase = _delta(candidate_value, baseline_value)
    passed = increase is not None and increase <= threshold
    return {
        "passed": passed,
        "applicable": True,
        "severity": "fail" if increase is not None else "insufficient",
        "baseline": baseline_value,
        "candidate": candidate_value,
        "increase": increase,
        "threshold": threshold,
        "message": (
            "Prompt stability drift remains within policy."
            if passed
            else "Prompt stability drift increased or could not be compared."
        ),
    }


def _control_certificate_check(
    name: str,
    candidate: JsonDict,
    policy: JsonDict,
    *,
    capability_profile: str,
) -> JsonDict:
    required_key = _CONTROL_CERTIFICATES[name]
    required = _bool(policy.get(required_key), key=required_key, default=False)
    configured_minimum = _minimum_control_certificate_level(policy)
    minimum = _effective_control_certificate_minimum(name, configured_minimum)
    forced = required or configured_minimum is not None
    if capability_profile == "black-box" and not forced:
        return _not_applicable_check(
            f"{name.replace('_', ' ').title()} requires an open or recorded surrogate."
        )
    diagnostic = _dict(candidate.get(name))
    if not diagnostic:
        if not forced:
            return _not_applicable_check(f"{name.replace('_', ' ').title()} was not recorded.")
        return {
            "passed": False,
            "applicable": True,
            "severity": "insufficient",
            "observed": "missing",
            "evidence_status": "missing",
            "certificate_level": "insufficient_evidence",
            "minimum_certificate_level": minimum,
            "message": f"Required {name.replace('_', ' ')} evidence is missing.",
        }
    check_state = str(diagnostic.get("check_state") or "invalid")
    certificate_level = str(diagnostic.get("certificate_level") or "insufficient_evidence")
    common: JsonDict = {
        "applicable": True,
        "observed": check_state,
        "check_state": check_state,
        "certificate_level": certificate_level,
        "minimum_certificate_level": minimum,
    }
    validation_errors = _control_certificate_validation_errors(name, diagnostic)
    if validation_errors:
        return {
            **common,
            "passed": False,
            "severity": "insufficient",
            "evidence_status": "invalid_certificate_schema",
            "validation_errors": validation_errors,
            "message": (
                f"{name.replace('_', ' ').title()} failed artifact schema and consistency "
                "validation."
            ),
        }
    if check_state == "conditions_not_met":
        return {
            **common,
            "passed": False,
            "severity": "fail",
            "evidence_status": "conditions_not_met",
            "message": (
                f"Recorded {name.replace('_', ' ')} conditions were not met; this triggers hold "
                "but does not prove nonexistence."
            ),
        }
    if check_state in {"missing", "invalid"}:
        return {
            **common,
            "passed": False,
            "severity": "insufficient",
            "evidence_status": check_state,
            "message": f"{name.replace('_', ' ').title()} evidence is {check_state}.",
        }
    if check_state != "passed" or certificate_level not in _CONTROL_CERTIFICATE_LEVELS:
        return {
            **common,
            "passed": False,
            "severity": "insufficient",
            "evidence_status": "invalid_certificate_schema",
            "message": f"{name.replace('_', ' ').title()} has an unsupported result state.",
        }
    if certificate_level == "insufficient_evidence":
        return {
            **common,
            "passed": False,
            "severity": "insufficient",
            "evidence_status": certificate_level,
            "message": f"{name.replace('_', ' ').title()} has insufficient evidence.",
        }
    if certificate_level == "not_applicable":
        if forced:
            return {
                **common,
                "passed": False,
                "severity": "insufficient",
                "evidence_status": certificate_level,
                "message": f"{name.replace('_', ' ').title()} does not satisfy required evidence.",
            }
        return _not_applicable_check(
            f"{name.replace('_', ' ').title()} is not applicable to this checkpoint."
        )
    if minimum is not None and (
        _CONTROL_CERTIFICATE_LEVELS[certificate_level]
        < _CONTROL_CERTIFICATE_LEVELS[minimum]
    ):
        return {
            **common,
            "passed": False,
            "severity": "insufficient",
            "evidence_status": "below_minimum_certificate_level",
            "message": (
                f"{name.replace('_', ' ').title()} is below the required certificate level."
            ),
        }
    return {
        **common,
        "passed": True,
        "severity": "info",
        "evidence_status": "recorded",
        "message": f"{name.replace('_', ' ').title()} meets the configured evidence policy.",
    }


def _minimum_control_certificate_level(policy: JsonDict) -> str | None:
    value = policy.get("minimum_control_certificate_level")
    if value is None or str(value).strip() == "":
        return None
    normalized = str(value).strip()
    if normalized not in _MINIMUM_CONTROL_CERTIFICATE_LEVELS:
        supported = ", ".join(sorted(_MINIMUM_CONTROL_CERTIFICATE_LEVELS))
        raise ValueError(
            "Policy key `minimum_control_certificate_level` must be one of " + supported
        )
    return normalized


def _effective_control_certificate_minimum(name: str, configured: str | None) -> str | None:
    if configured is None:
        return None
    natural_maximum = _CONTROL_CERTIFICATE_NATURAL_MAXIMUM[name]
    if _CONTROL_CERTIFICATE_LEVELS[configured] <= _CONTROL_CERTIFICATE_LEVELS[natural_maximum]:
        return configured
    return natural_maximum


def _control_certificate_validation_errors(name: str, diagnostic: JsonDict) -> list[str]:
    errors: list[str] = []
    if diagnostic.get("schema") != _CONTROL_CERTIFICATE_SCHEMAS[name]:
        errors.append("schema")
    if diagnostic.get("kind") != name:
        errors.append("kind")
    state = str(diagnostic.get("check_state") or "")
    level = str(diagnostic.get("certificate_level") or "")
    if state not in _CONTROL_CERTIFICATE_STATES:
        errors.append("check_state")
    if level not in _CONTROL_CERTIFICATE_LEVELS or _CONTROL_CERTIFICATE_LEVELS[
        level
    ] > _CONTROL_CERTIFICATE_LEVELS[_CONTROL_CERTIFICATE_NATURAL_MAXIMUM[name]]:
        errors.append("certificate_level")
    if state in {"missing", "invalid"}:
        return sorted(set(errors))
    unmet = diagnostic.get("conditions_not_met")
    if state == "conditions_not_met" and (
        not isinstance(unmet, list) or not any(str(item).strip() for item in unmet)
    ):
        errors.append("conditions_not_met")
    if name == "terminal_sensitivity":
        errors.extend(_validate_terminal_sensitivity_certificate(diagnostic, state, level))
    elif name == "green_certificate":
        errors.extend(_validate_green_certificate(diagnostic, state, level))
    else:
        errors.extend(_validate_posterior_certificate(diagnostic, state, level))
    return sorted(set(errors))


def _validate_terminal_sensitivity_certificate(
    diagnostic: JsonDict,
    state: str,
    level: str,
) -> list[str]:
    errors: list[str] = []
    decay = _optional_float(diagnostic.get("decay_rate"))
    r_squared = _optional_float(diagnostic.get("r_squared"))
    interval = diagnostic.get("bootstrap_ci")
    interval_lower = (
        _optional_float(interval[0])
        if isinstance(interval, list) and len(interval) == 2
        else None
    )
    records = diagnostic.get("records")
    horizons = diagnostic.get("distinct_horizons")
    floor = _optional_float(diagnostic.get("floor"))
    if floor is None:
        floor = 1e-15
    if floor <= 0.0:
        errors.append("floor")
    if decay is None:
        errors.append("decay_rate")
    if r_squared is None:
        errors.append("r_squared")
    if not _valid_interval(interval):
        errors.append("bootstrap_ci")
    if (
        not isinstance(records, list)
        or not records
        or any(not _valid_terminal_record(row, floor=floor) for row in records)
    ):
        errors.append("records")
    horizon_values = _positive_ints(horizons) if isinstance(horizons, list) else []
    if (
        not isinstance(horizons, list)
        or len(set(horizon_values)) < 3
        or (
            isinstance(records, list)
            and sorted(set(_terminal_record_horizons(records)))
            != sorted(set(horizon_values))
        )
    ):
        errors.append("distinct_horizons")
    record_count = diagnostic.get("record_count")
    if (
        isinstance(record_count, bool)
        or not isinstance(record_count, int)
        or not isinstance(records, list)
        or record_count != len(records)
    ):
        errors.append("record_count")
    if level != "empirical_only":
        errors.append("certificate_level")
    if isinstance(records, list) and records:
        recomputed = _recompute_terminal_summary(records)
        if recomputed is None:
            errors.append("records")
        else:
            if decay is None or not _close(decay, recomputed["decay_rate"]):
                errors.append("decay_rate")
            if r_squared is None or not _close(r_squared, recomputed["r_squared"]):
                errors.append("r_squared")
            if recomputed["seed_metadata_consistent"] is not True:
                errors.append("seed_metadata")
            recomputed_groups = recomputed["groups"]
            if state == "passed" and (
                not isinstance(recomputed_groups, list)
                or any(
                    int(group["distinct_horizon_count"]) < 3
                    or float(group["decay_rate"]) <= 1e-10
                    or float(group["r_squared"]) < 0.5
                    for group in recomputed_groups
                )
            ):
                errors.append("group_pass_conditions")
    if _valid_interval(interval) and decay is not None:
        assert isinstance(interval, list)
        lower = _optional_float(interval[0])
        upper = _optional_float(interval[1])
        if lower is None or upper is None or not lower <= decay <= upper:
            errors.append("bootstrap_ci")
    if state == "passed" and (
        decay is None
        or decay <= 1e-10
        or r_squared is None
        or r_squared < 0.5
        or not _valid_interval(interval)
        or interval_lower is None
        or interval_lower <= 0.0
    ):
        errors.append("passed_conditions")
    return errors


def _validate_green_certificate(
    diagnostic: JsonDict,
    state: str,
    level: str,
) -> list[str]:
    errors: list[str] = []
    dimension = _optional_positive_int(diagnostic.get("dimension"))
    stable = _optional_nonnegative_int(diagnostic.get("stable_dimension"))
    unstable = _optional_nonnegative_int(diagnostic.get("unstable_dimension"))
    hyperbolicity = _optional_float(diagnostic.get("hyperbolicity_margin"))
    sigma_min = _optional_float(diagnostic.get("boundary_sigma_min"))
    recovery = _optional_float(diagnostic.get("maximum_recovery_residual"))
    horizons = diagnostic.get("horizons")
    moduli = diagnostic.get("eigenvalue_moduli")
    if (
        dimension is None
        or stable is None
        or unstable is None
        or stable > dimension
        or unstable > dimension
        or stable + unstable > dimension
    ):
        errors.append("stable_unstable_dimension")
    if hyperbolicity is None:
        errors.append("hyperbolicity_margin")
    modulus_values = _finite_nonnegative_values(moduli)
    if modulus_values is None or not modulus_values:
        errors.append("eigenvalue_moduli")
    else:
        recomputed_margin = min(abs(value - 1.0) for value in modulus_values)
        if hyperbolicity is None or not _close(hyperbolicity, recomputed_margin):
            errors.append("hyperbolicity_margin")
        if dimension is None or len(modulus_values) != dimension:
            errors.append("eigenvalue_moduli")
        else:
            tolerance = 1e-8
            derived_stable = sum(value < 1.0 - tolerance for value in modulus_values)
            derived_unstable = sum(value > 1.0 + tolerance for value in modulus_values)
            derived_center = dimension - derived_stable - derived_unstable
            if (
                stable != derived_stable
                or unstable != derived_unstable
                or (state == "passed" and derived_center != 0)
            ):
                errors.append("stable_unstable_dimension")
    if sigma_min is None:
        errors.append("boundary_sigma_min")
    if recovery is None or recovery < 0.0:
        errors.append("maximum_recovery_residual")
    horizon_sigmas: list[float] = []
    horizon_recoveries: list[float] = []
    horizon_passes: list[bool] = []
    if not isinstance(horizons, list) or not horizons:
        errors.append("horizons")
    else:
        for row in horizons:
            if not isinstance(row, dict):
                errors.append("horizons")
                break
            row_sigma = _optional_float(row.get("boundary_sigma_min"))
            row_recovery = _optional_float(row.get("coefficient_recovery_residual"))
            row_passed = row.get("passed")
            if (
                _optional_positive_int(row.get("horizon")) is None
                or row_sigma is None
                or row_sigma < 0.0
                or row_recovery is None
                or row_recovery < 0.0
                or not isinstance(row_passed, bool)
            ):
                errors.append("horizons")
                break
            horizon_sigmas.append(row_sigma)
            horizon_recoveries.append(row_recovery)
            horizon_passes.append(row_passed)
    if horizon_sigmas and (
        sigma_min is None or not _close(sigma_min, min(horizon_sigmas))
    ):
        errors.append("boundary_sigma_min")
    if horizon_recoveries and (
        recovery is None or not _close(recovery, max(horizon_recoveries))
    ):
        errors.append("maximum_recovery_residual")
    if state == "passed" and horizon_passes and not all(horizon_passes):
        errors.append("horizons")
    if state == "passed" and (
        hyperbolicity is None
        or hyperbolicity <= 1e-8
        or stable is None
        or stable < 1
        or unstable is None
        or unstable < 1
        or dimension is None
        or stable + unstable != dimension
        or sigma_min is None
        or sigma_min <= 1e-8
        or recovery is None
        or recovery > 1e-8
        or not horizon_passes
        or not all(horizon_passes)
    ):
        errors.append("passed_conditions")
    if level == "certificate_verified" and (
        diagnostic.get("premises_complete") is not True
        or not str(diagnostic.get("verified_scope") or "").strip()
    ):
        errors.append("verified_provenance")
    if state == "passed" and level not in {"surrogate_consistent", "certificate_verified"}:
        errors.append("certificate_level")
    if state == "conditions_not_met" and level != "empirical_only":
        errors.append("certificate_level")
    return errors


def _validate_posterior_certificate(
    diagnostic: JsonDict,
    state: str,
    level: str,
) -> list[str]:
    errors: list[str] = []
    epsilon = _optional_float(diagnostic.get("residual_norm_upper"))
    beta = _optional_float(diagnostic.get("jacobian_inverse_norm_upper"))
    lipschitz = _optional_float(diagnostic.get("jacobian_lipschitz_upper"))
    radius = _optional_float(diagnostic.get("neighborhood_radius"))
    eta = _optional_float(diagnostic.get("eta"))
    contraction = _optional_float(diagnostic.get("K"))
    h_value = _optional_float(diagnostic.get("h"))
    existence_radius = _optional_float(diagnostic.get("existence_radius"))
    h_margin = _optional_float(diagnostic.get("h_margin"))
    neighborhood_margin = _optional_float(diagnostic.get("neighborhood_margin"))
    if epsilon is None or epsilon < 0.0:
        errors.append("residual_norm_upper")
    if beta is None or beta <= 0.0:
        errors.append("jacobian_inverse_norm_upper")
    if lipschitz is None or lipschitz < 0.0:
        errors.append("jacobian_lipschitz_upper")
    if radius is None or radius <= 0.0:
        errors.append("neighborhood_radius")
    if eta is None or beta is None or epsilon is None or not _close(eta, beta * epsilon):
        errors.append("eta")
    if contraction is None or beta is None or lipschitz is None or not _close(
        contraction, beta * lipschitz
    ):
        errors.append("K")
    if h_value is None or eta is None or contraction is None or not _close(
        h_value, eta * contraction
    ):
        errors.append("h")
    expected_radius: float | None = None
    if eta is not None and contraction is not None and h_value is not None and h_value <= 0.5:
        expected_radius = (
            eta
            if contraction == 0.0
            else 2.0 * eta / (1.0 + math.sqrt(max(0.0, 1.0 - 2.0 * h_value)))
        )
        if existence_radius is None or not _close(existence_radius, expected_radius):
            errors.append("existence_radius")
    if h_value is None or h_margin is None or not _close(h_margin, 0.5 - h_value):
        errors.append("h_margin")
    if expected_radius is None:
        if existence_radius is not None or neighborhood_margin is not None:
            errors.append("neighborhood_margin")
    elif (
        radius is None
        or existence_radius is None
        or neighborhood_margin is None
        or not _close(neighborhood_margin, radius - existence_radius)
    ):
        errors.append("neighborhood_margin")
    if state == "passed" and (
        h_value is None
        or h_value > 0.5
        or existence_radius is None
        or radius is None
        or existence_radius > radius
    ):
        errors.append("passed_conditions")
    if level == "certificate_verified":
        provenance = _dict(diagnostic.get("bound_provenance"))
        if (
            diagnostic.get("provenance_complete") is not True
            or provenance.get("kind") != "certified_bounds"
            or provenance.get("conservative") is not True
            or not str(provenance.get("scope") or "").strip()
            or not str(provenance.get("source") or "").strip()
        ):
            errors.append("verified_provenance")
    if state == "passed" and level not in {
        "surrogate_consistent",
        "certificate_verified",
        "insufficient_evidence",
    }:
        errors.append("certificate_level")
    if state == "conditions_not_met" and level not in {
        "surrogate_consistent",
        "insufficient_evidence",
    }:
        errors.append("certificate_level")
    return errors


def _positive_ints(values: list[object]) -> list[int]:
    return [
        value
        for value in values
        if isinstance(value, int) and not isinstance(value, bool) and value > 0
    ]


def _finite_nonnegative_values(value: object) -> list[float] | None:
    if not isinstance(value, list):
        return None
    converted = [_optional_float(item) for item in value]
    if any(item is None or item < 0.0 for item in converted):
        return None
    return [cast(float, item) for item in converted]


def _optional_nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _valid_terminal_record(value: object, *, floor: float) -> bool:
    if not isinstance(value, dict):
        return False
    horizon = _optional_positive_int(value.get("horizon"))
    early_step = _optional_nonnegative_int(value.get("early_step"))
    distance = _optional_positive_int(value.get("distance_to_terminal"))
    perturbation = _optional_float(value.get("perturbation_norm"))
    control_delta = _optional_float(value.get("control_delta_norm"))
    sensitivity = _optional_float(value.get("sensitivity"))
    log_sensitivity = _optional_float(value.get("log_sensitivity"))
    shape_valid = bool(
        horizon is not None
        and early_step is not None
        and early_step < horizon
        and distance == horizon - early_step
        and perturbation is not None
        and perturbation > 0.0
        and control_delta is not None
        and control_delta >= 0.0
        and sensitivity is not None
        and sensitivity >= 0.0
        and log_sensitivity is not None
    )
    if not shape_valid:
        return False
    assert perturbation is not None
    assert control_delta is not None
    assert sensitivity is not None
    assert log_sensitivity is not None
    expected_sensitivity = control_delta / perturbation
    return _close(sensitivity, expected_sensitivity) and _close(
        log_sensitivity,
        math.log(max(expected_sensitivity, floor)),
    )


def _terminal_record_horizons(records: list[object]) -> list[int]:
    return [
        value
        for row in records
        if isinstance(row, dict)
        for value in [_optional_positive_int(row.get("horizon"))]
        if value is not None
    ]


def _recompute_terminal_summary(records: list[object]) -> JsonDict | None:
    grouped: dict[tuple[str, int, str, str], dict[int, list[float]]] = {}
    seed_presence: dict[tuple[str, int, str, str], list[bool]] = {}
    for raw in records:
        if not isinstance(raw, dict):
            return None
        horizon = _optional_positive_int(raw.get("horizon"))
        early_step = _optional_nonnegative_int(raw.get("early_step"))
        log_sensitivity = _optional_float(raw.get("log_sensitivity"))
        if horizon is None or early_step is None or log_sensitivity is None:
            return None
        key = (
            str(raw.get("intervention_kind") or "terminal_objective"),
            early_step,
            str(raw.get("checkpoint") or ""),
            str(raw.get("model") or ""),
        )
        seed_presence.setdefault(key, []).append("seed" in raw)
        grouped.setdefault(key, {}).setdefault(horizon - early_step, []).append(
            log_sensitivity
        )
    fits: list[JsonDict] = []
    for distance_rows in grouped.values():
        points = [
            (float(distance), sum(values) / len(values))
            for distance, values in sorted(distance_rows.items())
        ]
        fit = _fit_line(points)
        if fit is None:
            return None
        fit["distinct_horizon_count"] = len(points)
        fits.append(fit)
    if not fits:
        return None
    return {
        "decay_rate": sum(float(fit["decay_rate"]) for fit in fits) / len(fits),
        "r_squared": min(float(fit["r_squared"]) for fit in fits),
        "groups": fits,
        "seed_metadata_consistent": all(
            not any(values) or all(values) for values in seed_presence.values()
        ),
    }


def _fit_line(points: list[tuple[float, float]]) -> JsonDict | None:
    if len(points) < 2:
        return None
    mean_x = sum(point[0] for point in points) / len(points)
    mean_y = sum(point[1] for point in points) / len(points)
    denominator = sum((point[0] - mean_x) ** 2 for point in points)
    if denominator <= 0.0:
        return None
    slope = sum(
        (point[0] - mean_x) * (point[1] - mean_y) for point in points
    ) / denominator
    intercept = mean_y - slope * mean_x
    residual = sum(
        (point[1] - (intercept + slope * point[0])) ** 2 for point in points
    )
    total = sum((point[1] - mean_y) ** 2 for point in points)
    r_squared = 1.0 if total <= 1e-24 and residual <= 1e-24 else (
        0.0 if total <= 1e-24 else 1.0 - residual / total
    )
    return {"decay_rate": -slope, "r_squared": r_squared}


def _close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-8, abs_tol=1e-12)


def _certificate_summary(checks: JsonDict, policy: JsonDict) -> JsonDict:
    rows: JsonDict = {
        name: _dict(checks.get(name)) for name in _CONTROL_CERTIFICATES
    }
    applicable = [row for row in rows.values() if row.get("applicable") is not False]
    if any(row.get("check_state") == "conditions_not_met" for row in applicable):
        overall_state = "conditions_not_met"
    elif any(row.get("passed") is False for row in applicable):
        overall_state = "insufficient_evidence"
    elif applicable:
        overall_state = "passed"
    else:
        overall_state = "not_applicable"
    levels = [
        str(row.get("certificate_level"))
        for row in applicable
        if str(row.get("certificate_level") or "") in _CONTROL_CERTIFICATE_LEVELS
        and row.get("evidence_status") != "invalid_certificate_schema"
    ]
    return {
        "schema": "prompt_control_lab.control_certificate_summary.v1",
        "overall_state": overall_state,
        "minimum_required_level": _minimum_control_certificate_level(policy),
        "effective_minimum_levels": {
            name: _effective_control_certificate_minimum(
                name,
                _minimum_control_certificate_level(policy),
            )
            for name in _CONTROL_CERTIFICATES
        },
        "highest_recorded_level": (
            max(levels, key=lambda value: _CONTROL_CERTIFICATE_LEVELS[value])
            if levels
            else "not_applicable"
        ),
        "checks": rows,
        "claim_boundary": (
            "Certificate results are scoped to their recorded surrogate and premises; they do "
            "not override score, slice, provenance, or other gate failures."
        ),
    }


def _decision(checks: JsonDict, *, missing: list[str]) -> str:
    values = [value for value in checks.values() if isinstance(value, dict)]
    if any(_is_observed_hold_failure(cast(JsonDict, value)) for value in values):
        return "hold"
    if missing:
        return "insufficient_evidence"
    if any(
        value.get("severity") == "insufficient" and value.get("passed") is False
        for value in values
    ):
        return "insufficient_evidence"
    if any(value.get("severity") == "review" and value.get("passed") is False for value in values):
        return "needs_review"
    return "pass"


def _is_observed_hold_failure(check: JsonDict) -> bool:
    if check.get("severity") != "fail" or check.get("passed") is not False:
        return False
    violations = check.get("violations")
    if isinstance(violations, list) and bool(violations):
        return True
    for key in ("observed", "increase"):
        value = check.get(key)
        if _optional_float(value) is not None:
            return True
        if isinstance(value, str) and value.strip().lower() not in {
            "",
            "unknown",
            "unavailable",
            "not_applicable",
        }:
            return True
    return False


def _build_attribution(comparison: JsonDict, checks: JsonDict) -> JsonDict:
    dimensions = [
        ("task_score", "mechanism", "Task performance changed across matched checkpoints."),
        ("paired_uncertainty", "uncertainty", "Paired uncertainty was measured."),
        ("resource_cost", "decision", "Token and latency changes were measured."),
        ("trajectory_stability", "stability", "Hidden-state drift changed after training."),
        ("soft_hard_deployment", "boundary", "Deployment projection risk was recorded."),
        ("generation_mismatch", "boundary", "Teacher-forced and free-generation behavior differ."),
        ("selective_risk", "uncertainty", "Risk-coverage behavior was measured."),
        (
            "prompt_reachability",
            "mechanism",
            "Checkpoint training moved the recorded prompt-conditioned representation.",
        ),
        (
            "readout_alignment",
            "mechanism",
            "Answer-space alignment was compared between training-time and generated behavior.",
        ),
        (
            "prompt_routing",
            "boundary",
            "Routing evidence records whether a controlled prompt-path intervention was available.",
        ),
        (
            "prompt_projection",
            "boundary",
            "Projection evidence records deployment loss when a learned prompt is discretized.",
        ),
        (
            "prompt_stability",
            "stability",
            "Prompt-conditioned trajectory drift was compared across checkpoints.",
        ),
        (
            "terminal_sensitivity",
            "stability",
            "Terminal-objective influence on early controls was measured across horizons.",
        ),
        (
            "green_certificate",
            "stability",
            "Hyperbolicity and scaled boundary transversality were checked on a named surrogate.",
        ),
        (
            "posterior_certificate",
            "uncertainty",
            "Residual and local derivative bounds were checked for a scoped posterior radius.",
        ),
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
                "confidence": _check_confidence(check),
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


def _plain_summary(
    decision: str,
    checks: JsonDict,
    *,
    missing: list[str],
    invalid: list[str],
) -> str:
    task_passed = _dict(checks.get("task_score")).get("passed") is True
    if decision == "pass":
        return "The candidate checkpoint meets the recorded performance and diagnostic policy."
    if decision == "insufficient_evidence":
        if missing and invalid:
            return (
                "The checkpoint decision is incomplete because required evidence is missing and "
                "recorded evidence failed validity checks."
            )
        if missing:
            return (
                "The checkpoint decision is incomplete because required diagnostic evidence is "
                "missing."
            )
        if invalid:
            return (
                "The checkpoint decision is incomplete because recorded evidence is invalid or "
                "outside configured validity bounds."
            )
        return "The checkpoint decision is incomplete because evidence is insufficient."
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


def _check_confidence(check: JsonDict) -> str:
    if check.get("applicable") is False:
        return "not_applicable"
    if check.get("severity") == "insufficient" or check.get("evidence_status") in {
        "insufficient_evidence",
        "unknown",
    }:
        return "low"
    if check.get("passed") in {True, False}:
        return "medium"
    return "unknown"


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


def _model_key(checkpoint: JsonDict) -> tuple[str, str, str, str]:
    return (
        str(checkpoint.get("provider") or ""),
        str(checkpoint.get("model_id") or ""),
        str(checkpoint.get("model_revision") or ""),
        str(checkpoint.get("model_snapshot_sha256") or ""),
    )


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
