"""Plain-language interpretation helpers for research diagnostics."""

from __future__ import annotations

from pathlib import Path

from promptcontrollab.core.files import JsonDict
from promptcontrollab.diagnostics.common import _read_optional_json


def _interpret_diagnostics(diagnostics: JsonDict) -> list[str]:
    interpretations: list[str] = []
    soft = diagnostics.get("soft_hard")
    if isinstance(soft, dict):
        interpretations.append(
            f"Soft-to-hard projection risk is {soft.get('risk')} with mean distance "
            f"{soft.get('mean_projection_distance')}."
        )
    trajectory = diagnostics.get("trajectory")
    if isinstance(trajectory, dict):
        interpretations.append(
            "Trajectory turnpike-like signal is "
            f"{trajectory.get('turnpike_like_signal')} with log-decay slope "
            f"{trajectory.get('log_decay_slope')}."
        )
    riccati = diagnostics.get("riccati")
    if isinstance(riccati, dict):
        interpretations.append(
            "Riccati surrogate stable="
            f"{riccati.get('stable_surrogate')} with spectral radius "
            f"{riccati.get('closed_loop_spectral_radius')}."
        )
    tv_soft = diagnostics.get("tv_soft")
    if isinstance(tv_soft, dict):
        interpretations.append(
            "Time-varying soft-control comparison recorded method means and deltas vs baseline."
        )
    for key, label in (
        ("terminal_sensitivity", "Terminal sensitivity"),
        ("green_certificate", "Green certificate"),
        ("posterior_certificate", "Posterior certificate"),
    ):
        diagnostic = diagnostics.get(key)
        if isinstance(diagnostic, dict):
            interpretations.append(
                f"{label} state={diagnostic.get('check_state')} at level "
                f"{diagnostic.get('certificate_level')}."
            )
    return interpretations


def _plain_language_research_insights(payload: JsonDict) -> list[JsonDict]:
    diagnostics = payload.get("diagnostics")
    diagnostics_dict = diagnostics if isinstance(diagnostics, dict) else {}
    inputs = payload.get("inputs")
    inputs_dict = inputs if isinstance(inputs, dict) else {}
    hidden = inputs_dict.get("hidden_states")
    hidden_dict = hidden if isinstance(hidden, dict) else {}
    specs: list[tuple[str, str, JsonDict]] = [
        ("soft_hard", "diagnostics/soft_hard.json", _payload_dict(diagnostics_dict, "soft_hard")),
        ("hidden_states", "inputs/hidden_states.npz", hidden_dict),
        (
            "trajectory",
            "diagnostics/trajectory.json",
            _payload_dict(diagnostics_dict, "trajectory"),
        ),
        ("riccati", "diagnostics/riccati.json", _payload_dict(diagnostics_dict, "riccati")),
        ("tv_soft", "diagnostics/tv_soft.json", _payload_dict(diagnostics_dict, "tv_soft")),
        (
            "terminal_sensitivity",
            "diagnostics/terminal_sensitivity.json",
            _payload_dict(diagnostics_dict, "terminal_sensitivity"),
        ),
        (
            "green_certificate",
            "diagnostics/green_certificate.json",
            _payload_dict(diagnostics_dict, "green_certificate"),
        ),
        (
            "posterior_certificate",
            "diagnostics/posterior_certificate.json",
            _payload_dict(diagnostics_dict, "posterior_certificate"),
        ),
    ]
    return [
        {
            "diagnostic": _plain_diagnostic_label(key),
            "checks": _plain_diagnostic_check(key),
            "result": _plain_diagnostic_result(key, row_payload),
            "interpretation": _plain_diagnostic_interpretation(key, row_payload),
            "next_action": _plain_diagnostic_next_action(key, row_payload, artifact),
        }
        for key, artifact, row_payload in specs
    ]


def _research_at_a_glance(payload: JsonDict, *, summary_dir: Path | None = None) -> JsonDict:
    existing = payload.get("at_a_glance")
    if summary_dir is None and isinstance(existing, dict) and existing:
        return existing

    diagnostics = payload.get("diagnostics")
    diagnostics_dict = diagnostics if isinstance(diagnostics, dict) else {}
    ready_keys = [
        key
        for key in ["soft_hard", "trajectory", "riccati", "tv_soft"]
        if isinstance(diagnostics_dict.get(key), dict)
    ]
    certificate_keys = [
        key
        for key in ["terminal_sensitivity", "green_certificate", "posterior_certificate"]
        if isinstance(diagnostics_dict.get(key), dict)
    ]
    inputs = payload.get("inputs")
    inputs_dict = inputs if isinstance(inputs, dict) else {}
    hidden_state_input = (
        "present" if isinstance(inputs_dict.get("hidden_states"), dict) else "missing"
    )
    evidence = _read_optional_json(summary_dir / "evidence_card.json") if summary_dir else {}
    claim = _read_optional_json(summary_dir / "claim_check.json") if summary_dir else {}
    gap_plan = _read_optional_json(summary_dir / "research_gap_plan.json") if summary_dir else {}
    gap_status = (
        _read_optional_json(summary_dir / "research_gap_status.json") if summary_dir else {}
    )
    claim_status = str(claim.get("status") or "not run")
    evidence_recommendation = str(evidence.get("recommendation") or "not run")
    open_first = _research_open_first(
        evidence=evidence,
        claim=claim,
        gap_plan=gap_plan,
        gap_status=gap_status,
    )
    return {
        "mode": str(payload.get("mode") or "unknown"),
        "diagnostics_ready": f"{len(ready_keys)}/4",
        "control_certificates_ready": f"{len(certificate_keys)}/3",
        "hidden_state_input": hidden_state_input,
        "evidence_recommendation": evidence_recommendation,
        "evidence_tier": str(
            claim.get("evidence_tier") or evidence.get("evidence_tier") or "not run"
        ),
        "claim_status": claim_status,
        "safe_claim": str(claim.get("safe_claim") or "not checked"),
        "open_first": open_first,
        "next_action": _research_next_report_action(
            evidence_recommendation=evidence_recommendation,
            claim_status=claim_status,
            open_first=open_first,
        ),
    }


def _research_open_first(
    *,
    evidence: JsonDict,
    claim: JsonDict,
    gap_plan: JsonDict,
    gap_status: JsonDict,
) -> str:
    if gap_plan and gap_status.get("status") != "complete":
        return "research_gap_plan.html"
    if evidence.get("recommendation") == "supported" and claim.get("status") == "pass":
        return "research_bundle.html"
    if claim:
        return "claim_check.html"
    if evidence:
        return "evidence_card.html"
    return "research_diagnostics.html"


def _research_next_report_action(
    *,
    evidence_recommendation: str,
    claim_status: str,
    open_first: str,
) -> str:
    if evidence_recommendation == "supported" and claim_status == "pass":
        return "Share the research bundle, evidence card, and claim check together."
    if open_first == "research_gap_plan.html":
        return "Close the listed evidence gaps, then rerun `pcl diagnose`."
    if claim_status in {"fail", "needs_review"}:
        return "Read claim_check.html before making a broad prompt-optimization claim."
    return "Read research_diagnostics.html and add missing diagnostics before claiming improvement."


def _payload_dict(payload: JsonDict, key: str) -> JsonDict:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def _plain_diagnostic_label(key: str) -> str:
    return {
        "soft_hard": "Soft-to-hard gap",
        "hidden_states": "Hidden-state input",
        "trajectory": "Trajectory stability",
        "riccati": "Riccati surrogate",
        "tv_soft": "Time-varying soft-control",
        "terminal_sensitivity": "Terminal sensitivity",
        "green_certificate": "Green certificate",
        "posterior_certificate": "Posterior certificate",
    }[key]


def _plain_diagnostic_check(key: str) -> str:
    return {
        "soft_hard": "Can a soft prompt be deployed as hard tokens without a large gap?",
        "hidden_states": "Do we have explicit activation inputs for trajectory diagnostics?",
        "trajectory": "Does the hidden-state path drift or show turnpike-like decay?",
        "riccati": "Is the fitted finite-dimensional control surrogate internally stable?",
        "tv_soft": "Does time-varying structure beat static, shuffled, or random controls?",
        "terminal_sensitivity": "Do terminal changes have exponentially less early influence?",
        "green_certificate": "Is the reduced recurrence hyperbolic with transverse boundaries?",
        "posterior_certificate": "Do the recorded local residual and derivative bounds close?",
    }[key]


def _plain_diagnostic_result(key: str, payload: JsonDict) -> str:
    if not payload:
        return "not measured"
    if key == "soft_hard":
        return (
            f"risk={payload.get('risk')}; mean distance={payload.get('mean_projection_distance')}"
        )
    if key == "hidden_states":
        return f"source={payload.get('source')}; shape={payload.get('states_shape')}"
    if key == "trajectory":
        return (
            f"turnpike={payload.get('turnpike_like_signal')}; "
            f"slope={payload.get('log_decay_slope')}"
        )
    if key == "riccati":
        return (
            f"stable={payload.get('stable_surrogate')}; "
            f"rho={payload.get('closed_loop_spectral_radius')}"
        )
    if key == "tv_soft":
        return f"best delta={_best_delta_key(payload) or 'not isolated'}"
    if key in {"terminal_sensitivity", "green_certificate", "posterior_certificate"}:
        return (
            f"state={payload.get('check_state')}; level={payload.get('certificate_level')}"
        )
    return "recorded"


def _plain_diagnostic_interpretation(key: str, payload: JsonDict) -> str:
    if not payload:
        return "This paper-evidence column is still missing."
    if key == "soft_hard":
        risk = str(payload.get("risk") or "unknown").lower()
        if risk in {"low", "pass", "safe"}:
            return "Hard-token deployment looks less risky, but should still be retested."
        return "Projection from soft vectors to hard tokens may lose quality."
    if key == "hidden_states":
        return "Trajectory and Riccati claims are easier to audit when this input is explicit."
    if key == "trajectory":
        if payload.get("turnpike_like_signal") is True:
            return "The trace shows a stability-like signal worth checking by task slice."
        return "The trace does not yet show a strong stability signature."
    if key == "riccati":
        radius = _float_or_none(payload.get("closed_loop_spectral_radius"))
        if payload.get("stable_surrogate") is True or (radius is not None and radius < 1.0):
            return "The fitted surrogate is internally stable on this reduced model."
        return "The surrogate needs review before supporting a stability claim."
    if key == "tv_soft":
        best = _best_delta_key(payload)
        if best and "time" in best:
            return "Time-varying structure may explain part of the gain."
        return "The current result does not isolate a time-varying advantage."
    if key in {"terminal_sensitivity", "green_certificate", "posterior_certificate"}:
        return str(
            payload.get("explanation")
            or "A bounded control-certificate result was recorded."
        )
    return "Recorded diagnostic evidence."


def _plain_diagnostic_next_action(key: str, payload: JsonDict, artifact: str) -> str:
    if not payload:
        return f"Run `{_plain_missing_command(key)}` to create `{artifact}`."
    if key == "soft_hard":
        return "Retest the rounded hard prompt before deployment."
    if key == "hidden_states":
        return "Use the same hidden-state source for trajectory and Riccati follow-ups."
    if key == "trajectory":
        return "Compare decay slopes by task slice before making broad claims."
    if key == "riccati":
        return "Report this as a fitted surrogate probe, not a full-LM proof."
    if key == "tv_soft":
        return "Compare static, shuffled, random, and time-varying lanes side by side."
    if key in {"terminal_sensitivity", "green_certificate", "posterior_certificate"}:
        return str(payload.get("next_action") or "Keep this scoped certificate artifact.")
    return "Keep this artifact with the run."


def _plain_missing_command(key: str) -> str:
    return {
        "soft_hard": "pcl soft-hard --run <selected-run>",
        "hidden_states": "pcl diagnose --run <selected-run>",
        "trajectory": "pcl trajectory --states inputs/hidden_states.npz --out diagnostics",
        "riccati": "pcl riccati --trajectory diagnostics/trajectory.json --out diagnostics",
        "tv_soft": "pcl tv-soft --config promptcontrol.example.yaml --out diagnostics",
        "terminal_sensitivity": (
            "pcl terminal-sensitivity --records inputs/terminal_interventions.jsonl "
            "--out diagnostics"
        ),
        "green_certificate": (
            "pcl green-certificate --surrogate inputs/green_surrogate.npz "
            "--horizon 16 --horizon 32 --horizon 64 --out diagnostics"
        ),
        "posterior_certificate": (
            "pcl posterior-certificate --input inputs/posterior_bounds.json --out diagnostics"
        ),
    }[key]


def _best_delta_key(payload: JsonDict) -> str:
    deltas = payload.get("delta_vs_baseline")
    if not isinstance(deltas, dict) or not deltas:
        return ""
    return str(max(deltas, key=lambda key: float(deltas.get(key) or 0.0)))


def _float_or_none(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
