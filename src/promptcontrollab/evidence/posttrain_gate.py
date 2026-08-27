"""Evidence-aware checkpoint comparison and post-training gate."""

from __future__ import annotations

import math
from importlib import resources
from pathlib import Path
from typing import cast

from promptcontrollab.core.config import read_simple_yaml
from promptcontrollab.core.files import JsonDict, ensure_dir, read_json, write_json
from promptcontrollab.evidence.posttraining.certificates import (
    _control_certificate_check,
    _control_certificate_validation_errors,
    _effective_control_certificate_minimum,
    _minimum_control_certificate_level,
)
from promptcontrollab.evidence.posttraining.common import (
    _bool,
    _dict,
    _not_applicable_check,
    _optional_float,
    _optional_positive_int,
    _valid_interval,
)
from promptcontrollab.evidence.posttraining.constants import (
    CONTROL_CERTIFICATE_LEVELS as _CONTROL_CERTIFICATE_LEVELS,
)
from promptcontrollab.evidence.posttraining.constants import (
    CONTROL_CERTIFICATES as _CONTROL_CERTIFICATES,
)
from promptcontrollab.evidence.posttraining.rendering import (
    render_posttrain_html as render_posttrain_html,
)
from promptcontrollab.evidence.posttraining.rendering import (
    render_posttrain_markdown as render_posttrain_markdown,
)

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


def _build_decision_trace(
    checks: JsonDict,
    *,
    decision: str,
    capability_profile: str,
) -> JsonDict:
    """Build an auditable trace linking each gate check to its decision impact."""

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
    """Return malformed or internally inconsistent checkpoint evidence fields."""

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
            invalid.append("candidate:diagnostics.generation_mismatch.generation_saturation_rate")
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
        if _optional_float(reachability.get("representation_shift_l2_normalized")) is None:
            invalid.append(
                "candidate:diagnostics.prompt_reachability.representation_shift_l2_normalized"
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
        if (
            not projection_not_applicable
            and _optional_float(
                projection.get("projection_gap", projection.get("mean_projection_distance"))
            )
            is None
        ):
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
    """Evaluate post-training checks under the selected capability profile."""

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
    """Check whether checkpoint provenance supports a controlled comparison."""

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
    if (
        _bool(
            policy.get("require_split_hash_match"),
            key="require_split_hash_match",
            default=True,
        )
        and not split_match
    ):
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
            "Task score meets the checkpoint policy." if passed else "Task score is insufficient."
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
            "No slice exceeds the regression allowance." if not regressed else "Slices regressed."
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
            "Trajectory drift remains within policy." if passed else "Trajectory drift increased."
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
            "Generation mismatch meets policy." if passed else "Generation mismatch is too large."
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
                "Prompt routing remains insufficient because no routing intervention was available."
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


def _certificate_summary(checks: JsonDict, policy: JsonDict) -> JsonDict:
    rows: JsonDict = {name: _dict(checks.get(name)) for name in _CONTROL_CERTIFICATES}
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
        value.get("severity") == "insufficient" and value.get("passed") is False for value in values
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
    """Describe observed checkpoint changes without asserting strict causality."""

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


def _valid_sha256(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        return False
    digest = value.removeprefix("sha256:")
    return len(digest) == 64 and all(character in "0123456789abcdef" for character in digest)


def _valid_probability(value: object) -> bool:
    converted = _optional_float(value)
    return converted is not None and 0.0 <= converted <= 1.0


def _risk_rank(value: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(value, 3)


def _optional_json(path: Path) -> JsonDict:
    return read_json(path) if path.is_file() else {}
