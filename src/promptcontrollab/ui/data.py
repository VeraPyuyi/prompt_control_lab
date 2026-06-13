"""Artifact readers for the local Streamlit dashboard."""

from __future__ import annotations

import json
from pathlib import Path

from promptcontrollab.claim_check import CLAIM_LABELS, CLAIM_REQUIREMENTS, TIER_ORDER
from promptcontrollab.files import JsonDict, read_json
from promptcontrollab.report_model import ReportModel

RUN_ARTIFACTS = [
    "manifest.json",
    "stats.json",
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
    "research_bundle_verification.json",
    "research_bundle_verification.html",
    "research_diagnostics.json",
    "research_gap_plan.json",
    "research_gap_status.json",
    "evidence_card.json",
    "claim_check.json",
    "evidence_from_result.json",
    "bridge_summary.json",
    "ecosystem_demo.json",
    "ecosystem_scorecard.json",
    "ecosystem_scorecard.html",
]

RUN_LEVEL_ARTIFACTS = [
    "manifest.json",
    "stats.json",
    "gate_result.json",
    "comparison_validity.json",
    "explanation.json",
    "model_drift.json",
    "audit_result.json",
    "agent_run.json",
    "research_bundle.json",
    "research_bundle.html",
    "research_bundle_verification.json",
    "research_bundle_verification.html",
    "research_diagnostics.json",
    "research_gap_plan.json",
    "research_gap_status.json",
    "evidence_card.json",
    "claim_check.json",
    "evidence_from_result.json",
    "bridge_summary.json",
    "ecosystem_demo.json",
    "ecosystem_scorecard.json",
    "ecosystem_scorecard.html",
]


def list_runs(runs_dir: Path) -> list[JsonDict]:
    """List run directories under ``runs_dir``."""

    if not runs_dir.exists():
        return []
    runs: list[JsonDict] = []
    for child in sorted(runs_dir.iterdir(), key=lambda path: path.name):
        if child.is_dir() and _has_any_artifact(child):
            runs.append({"name": child.name, "path": str(child)})
    if runs:
        return runs
    if _has_run_level_artifact(runs_dir):
        return [{"name": runs_dir.name, "path": str(runs_dir)}]
    if _has_any_artifact(runs_dir):
        return [{"name": runs_dir.name, "path": str(runs_dir)}]
    for child in sorted(runs_dir.iterdir(), key=lambda path: path.name):
        if child.is_dir():
            runs.append({"name": child.name, "path": str(child)})
    return runs


def load_run_detail(run_dir: Path) -> JsonDict:
    """Load all known artifacts for one run directory."""

    model = ReportModel.from_run(run_dir)
    return {
        "name": run_dir.name,
        "path": str(run_dir),
        "has_artifacts": model.has_artifacts,
        "artifacts": model.artifacts,
        "manifest": model.manifest,
        "stats": model.stats,
        "splits": model.splits,
        "gate": model.gate,
        "comparison_validity": model.comparison_validity,
        "explanation": model.explanation,
        "model_drift": model.model_drift,
        "audit": model.audit,
        "history_index": model.history_index,
        "history_compare": model.history_compare,
        "agent_run": model.agent_run,
        "research_diagnostics": model.research_diagnostics,
        "research_gap_plan": model.research_gap_plan,
        "research_gap_status": model.research_gap_status,
        "evidence_card": model.evidence_card,
        "claim_check": model.claim_check,
        "external_evidence": model.external_evidence,
        "bridge_summary": model.bridge_summary,
        "ecosystem_demo": model.ecosystem_demo,
        "ecosystem_scorecard": model.ecosystem_scorecard,
        "diagnostics": model.diagnostics,
        "baseline_metrics": model.baseline_metrics,
        "candidate_metrics": model.candidate_metrics,
        "metrics": model.metrics,
        "candidate_score": model.candidate_score,
        "baseline_score": model.baseline_score,
        "first_comparison": model.first_comparison,
        "mean_delta": model.mean_delta,
        "bootstrap_ci": model.bootstrap_ci,
        "permutation_p_value": model.permutation_p_value,
        "holm_adjusted_p_value": model.holm_adjusted_p_value,
        "empty_state": (
            "Run `pcl analyze` with a config, for example "
            "`pcl analyze --config promptcontrol.example.yaml --out runs/quick`, "
            "or select a run directory with PromptControlLab artifacts."
        ),
    }


def first_comparison(stats: JsonDict) -> JsonDict:
    """Return the primary comparison from a stats artifact.

    Current ``stats.json`` files store comparison metrics in ``comparisons[0]``.
    Older UI fixtures used top-level comparison fields, so keep that shape
    readable for existing artifacts.
    """

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


def research_diagnostic_rows(detail: JsonDict) -> list[JsonDict]:
    """Return normalized rows for the paper-derived research overview."""

    diagnostics = detail.get("diagnostics")
    diagnostics_dict = diagnostics if isinstance(diagnostics, dict) else {}
    specs = [
        (
            "soft_hard",
            "soft-hard gap",
            "Soft prompt deployability",
            _soft_hard_signal,
        ),
        (
            "hidden_states",
            "hidden-state input",
            "HF/local activation source",
            _hidden_state_signal,
        ),
        (
            "trajectory",
            "trajectory",
            "Hidden-state stability",
            _trajectory_signal,
        ),
        (
            "riccati",
            "Riccati surrogate",
            "Finite-dimensional control probe",
            _riccati_signal,
        ),
        (
            "tv_soft",
            "tv-soft lane",
            "Time-varying control structure",
            _tv_soft_signal,
        ),
    ]
    rows: list[JsonDict] = []
    for key, label, meaning, signal_fn in specs:
        payload = (
            _hidden_state_payload(detail)
            if key == "hidden_states"
            else diagnostics_dict.get(key)
        )
        payload_dict = payload if isinstance(payload, dict) else {}
        available = bool(payload_dict)
        rows.append(
            {
                "key": key,
                "diagnostic": label,
                "status": "available" if available else "missing",
                "meaning": meaning,
                "signal": signal_fn(payload_dict) if available else "not run",
                "artifact": f"diagnostics/{key}.json",
            }
        )
    return rows


def research_status_counts(detail: JsonDict) -> dict[str, int]:
    """Return available/missing diagnostic counts for the research overview."""

    counts: dict[str, int] = {}
    for row in research_diagnostic_rows(detail):
        status = str(row.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def research_evidence_map(detail: JsonDict) -> list[JsonDict]:
    """Return a left-to-right evidence path for the paper-derived research workflow."""

    diagnostics = detail.get("diagnostics")
    diagnostics_dict = diagnostics if isinstance(diagnostics, dict) else {}
    stats = detail.get("stats")
    stats_dict = stats if isinstance(stats, dict) else {}
    comparison = first_comparison(stats_dict)
    validity = detail.get("comparison_validity")
    validity_dict = validity if isinstance(validity, dict) else {}
    claim = claim_check_summary(detail)
    return [
        _map_node(
            key="tri_split",
            label="Tri-split",
            status="ready" if detail.get("splits") or _manifest_has_split(detail) else "missing",
            summary=_split_summary(detail),
        ),
        _map_node(
            key="paired_stats",
            label="Paired stats",
            status="ready" if comparison else "missing",
            summary=_comparison_summary(comparison),
        ),
        _map_node(
            key="comparison_validity",
            label="Validity",
            status=_validity_status(validity_dict),
            summary=str(validity_dict.get("validity") or validity_dict.get("status") or "not run"),
        ),
        _map_node(
            key="soft_hard",
            label="Soft-hard",
            status="ready" if isinstance(diagnostics_dict.get("soft_hard"), dict) else "missing",
            summary=_soft_hard_signal(diagnostics_dict.get("soft_hard", {})),
        ),
        _map_node(
            key="trajectory",
            label="Trajectory",
            status="ready" if isinstance(diagnostics_dict.get("trajectory"), dict) else "missing",
            summary=_trajectory_signal(diagnostics_dict.get("trajectory", {})),
        ),
        _map_node(
            key="riccati",
            label="Riccati",
            status="ready" if isinstance(diagnostics_dict.get("riccati"), dict) else "missing",
            summary=_riccati_signal(diagnostics_dict.get("riccati", {})),
        ),
        _map_node(
            key="tv_soft",
            label="TV-soft",
            status="ready" if isinstance(diagnostics_dict.get("tv_soft"), dict) else "missing",
            summary=_tv_soft_signal(diagnostics_dict.get("tv_soft", {})),
        ),
        _map_node(
            key="claim_check",
            label="Claim",
            status=_claim_map_status(claim),
            summary=_claim_map_summary(claim),
        ),
    ]


def evidence_card_rows(detail: JsonDict) -> list[JsonDict]:
    """Return normalized evidence-card section rows for the research overview."""

    card = detail.get("evidence_card")
    if not isinstance(card, dict):
        return []
    sections = card.get("sections")
    if not isinstance(sections, dict):
        return []
    rows: list[JsonDict] = []
    for name, raw_section in sections.items():
        if not isinstance(raw_section, dict):
            continue
        rows.append(
            {
                "section": str(name).replace("_", " "),
                "status": raw_section.get("status", "unknown"),
                "signal": _evidence_signal(str(name), raw_section),
            }
        )
    return rows


def claim_check_summary(detail: JsonDict) -> JsonDict:
    """Return the reviewer-facing claim-check summary for the research overview."""

    payload = detail.get("claim_check")
    if not isinstance(payload, dict) or not payload:
        return {}
    missing = payload.get("next_tier_missing")
    return {
        "requested_claim": payload.get("requested_claim"),
        "status": payload.get("status"),
        "evidence_tier": payload.get("evidence_tier"),
        "safe_claim": payload.get("safe_claim"),
        "reason": payload.get("reason"),
        "next_tier_missing": missing if isinstance(missing, list) else [],
    }


def claim_evidence_ladder(detail: JsonDict) -> list[JsonDict]:
    """Return claim-scope ladder rows for paired/partial/full research claims."""

    claim = claim_check_summary(detail)
    evidence_card = detail.get("evidence_card")
    evidence_dict = evidence_card if isinstance(evidence_card, dict) else {}
    tier_name = str(
        claim.get("evidence_tier")
        or evidence_dict.get("evidence_tier")
        or "tier_0_insufficient_or_contradicted"
    )
    tier_value = TIER_ORDER.get(tier_name, 0)
    recommendation = str(
        claim.get("recommendation") or evidence_dict.get("recommendation") or "unknown"
    )
    requested_claim = str(claim.get("requested_claim") or "")
    missing = claim.get("next_tier_missing")
    missing_items = missing if isinstance(missing, list) else []
    rows: list[JsonDict] = []
    for claim_name, required_tier in CLAIM_REQUIREMENTS.items():
        status = _claim_ladder_status(
            tier_value=tier_value,
            required_tier=required_tier,
            recommendation=recommendation,
        )
        rows.append(
            {
                "claim": claim_name,
                "label": CLAIM_LABELS.get(claim_name, claim_name),
                "required_tier": required_tier,
                "current_tier": tier_name,
                "status": status,
                "requested": claim_name == requested_claim,
                "missing": list(missing_items) if status == "missing" else [],
            }
        )
    return rows


def external_bridge_summary(detail: JsonDict) -> JsonDict:
    """Return a compact external-tool bridge summary for the research overview."""

    bridge = detail.get("bridge_summary")
    bridge_dict = bridge if isinstance(bridge, dict) else {}
    external = detail.get("external_evidence")
    external_dict = external if isinstance(external, dict) else {}
    if not bridge_dict and not external_dict:
        return {}
    detected = bridge_dict.get("detected_tools") or external_dict.get("detected_tools") or []
    added = bridge_dict.get("pcl_added_evidence") or []
    missing = bridge_dict.get("missing_evidence") or bridge_dict.get("next_tier_missing") or []
    next_actions = bridge_dict.get("next_actions") or external_dict.get("next_actions") or []
    return {
        "tool": external_dict.get("tool") or bridge_dict.get("requested_tool") or "external",
        "detected_tools": detected if isinstance(detected, list) else [],
        "recommendation": bridge_dict.get("recommendation", ""),
        "evidence_tier": bridge_dict.get("evidence_tier", ""),
        "validity": bridge_dict.get("validity", ""),
        "claim_check_status": bridge_dict.get("claim_check_status", ""),
        "claim_check_requested_claim": bridge_dict.get("claim_check_requested_claim", ""),
        "pcl_added_evidence": added if isinstance(added, list) else [],
        "pcl_added_count": len(added) if isinstance(added, list) else 0,
        "missing_evidence": missing if isinstance(missing, list) else [],
        "next_actions": next_actions if isinstance(next_actions, list) else [],
    }


def ecosystem_demo_rows(detail: JsonDict) -> list[JsonDict]:
    """Return one row per external-tool bundle in an ecosystem demo run."""

    payload = detail.get("ecosystem_demo")
    if not isinstance(payload, dict):
        return []
    runs = payload.get("runs")
    if not isinstance(runs, list):
        return []
    rows: list[JsonDict] = []
    for item in runs:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "tool": item.get("tool", ""),
                "validity": item.get("validity", ""),
                "evidence_tier": item.get("evidence_tier", ""),
                "claim_check_status": item.get("claim_check_status", ""),
                "open_first": item.get("bridge_summary_path", ""),
                "report_html": item.get("report_html_path", ""),
            }
        )
    return rows


def ecosystem_scorecard_rows(detail: JsonDict) -> list[JsonDict]:
    """Return cross-tool scorecard rows for ecosystem demo runs."""

    payload = detail.get("ecosystem_scorecard")
    if not isinstance(payload, dict):
        return []
    raw_rows = payload.get("rows")
    if not isinstance(raw_rows, list):
        return []
    rows: list[JsonDict] = []
    for item in raw_rows:
        if not isinstance(item, dict):
            continue
        missing = item.get("missing_paper_diagnostics")
        rows.append(
            {
                "tool": item.get("display_name") or item.get("tool", ""),
                "external_strength": item.get("external_strength", ""),
                "pcl_adds": item.get("pcl_adds", ""),
                "validity": item.get("validity", ""),
                "evidence_tier": item.get("evidence_tier", ""),
                "missing_paper_diagnostics": ", ".join(str(part) for part in missing)
                if isinstance(missing, list)
                else str(missing or ""),
                "gap_status": item.get("gap_status", ""),
                "gap_complete_count": item.get("gap_complete_count", ""),
                "gap_missing_count": item.get("gap_missing_count", ""),
                "gap_status_path": item.get("gap_status_path", ""),
                "open_first": item.get("open_first", ""),
                "gap_status_command": item.get("gap_status_command", ""),
            }
        )
    return rows


def evidence_gap_rows(detail: JsonDict) -> list[JsonDict]:
    """Return paper-evidence gap rows from ``pcl diagnose`` external bridge output."""

    research = detail.get("research_diagnostics")
    if not isinstance(research, dict):
        return []
    diagnostics = research.get("diagnostics")
    if not isinstance(diagnostics, dict):
        return []
    ecosystem = diagnostics.get("ecosystem_bridge")
    if isinstance(ecosystem, dict):
        runs = ecosystem.get("runs")
        if isinstance(runs, list):
            return [_evidence_gap_row(item) for item in runs if isinstance(item, dict)]
    external = diagnostics.get("external_bridge")
    if isinstance(external, dict) and external:
        return [_evidence_gap_row(external)]
    return []


def evidence_gap_action_rows(detail: JsonDict) -> list[JsonDict]:
    """Return copy-paste remediation commands for missing paper diagnostics."""

    research = detail.get("research_diagnostics")
    if not isinstance(research, dict):
        return []
    diagnostics = research.get("diagnostics")
    if not isinstance(diagnostics, dict):
        return []
    ecosystem = diagnostics.get("ecosystem_bridge")
    if isinstance(ecosystem, dict):
        return _action_rows(ecosystem.get("paper_gap_remediation"))
    external = diagnostics.get("external_bridge")
    if isinstance(external, dict):
        return _action_rows(external.get("paper_gap_remediation"))
    return []


def research_gap_plan_rows(detail: JsonDict) -> list[JsonDict]:
    """Return rows from a standalone research gap plan artifact."""

    plan = detail.get("research_gap_plan")
    if not isinstance(plan, dict):
        return []
    return _action_rows(plan.get("actions"))


def research_gap_script_rows(detail: JsonDict) -> list[JsonDict]:
    """Return review-first gap command script artifacts for display."""

    artifacts = detail.get("artifacts")
    artifact_list = [str(item) for item in artifacts] if isinstance(artifacts, list) else []
    rows: list[JsonDict] = []
    for name in ["research_gap_plan.md", "research_gap_commands.ps1", "research_gap_commands.sh"]:
        if name in artifact_list:
            rows.append({"artifact": name, "purpose": _gap_script_purpose(name)})
    return rows


def research_gap_status_rows(detail: JsonDict) -> list[JsonDict]:
    """Return rows from ``research_gap_status.json``."""

    status = detail.get("research_gap_status")
    if not isinstance(status, dict):
        return []
    actions = status.get("actions")
    if not isinstance(actions, list):
        return []
    rows: list[JsonDict] = []
    for item in actions:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "step": item.get("step"),
                "diagnostic": item.get("concept", ""),
                "status": item.get("status", ""),
                "artifact": item.get("artifact", ""),
                "command": item.get("command", ""),
            }
        )
    return rows


def _gap_script_purpose(name: str) -> str:
    if name.endswith(".md"):
        return "reviewable evidence-gap handoff plan"
    return "review-first command script; edit placeholders before use"


def _action_rows(value: object) -> list[JsonDict]:
    if not isinstance(value, list):
        return []
    rows: list[JsonDict] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        required = item.get("required_inputs")
        required_inputs = (
            ", ".join(str(part) for part in required) if isinstance(required, list) else ""
        )
        rows.append(
            {
                "missing_diagnostic": item.get("concept", ""),
                "required_inputs": required_inputs,
                "command": item.get("command", ""),
                "artifact": item.get("artifact", ""),
                "explains": item.get("explains", ""),
            }
        )
    return rows


def _evidence_gap_row(item: JsonDict) -> JsonDict:
    missing = item.get("missing_paper_diagnostics")
    missing_list = [str(value) for value in missing] if isinstance(missing, list) else []
    return {
        "tool": item.get("display_name") or item.get("tool", ""),
        "validity": item.get("validity", ""),
        "evidence_tier": item.get("evidence_tier", ""),
        "claim_check_status": item.get("claim_check_status", ""),
        "missing_count": len(missing_list),
        "missing_paper_diagnostics": ", ".join(missing_list),
        "open_first": item.get("bridge_summary_path", ""),
        "report_html": item.get("report_html_path", ""),
    }


def history_rows(detail: JsonDict) -> list[JsonDict]:
    """Return normalized history rows for tables and trend charts."""

    history = detail.get("history_index")
    if not isinstance(history, dict):
        return []
    runs = history.get("runs")
    if not isinstance(runs, list):
        return []
    rows: list[JsonDict] = []
    for index, item in enumerate(runs, start=1):
        if not isinstance(item, dict):
            continue
        model = item.get("model")
        model_dict = model if isinstance(model, dict) else {}
        prompt = item.get("prompt_identity")
        prompt_dict = prompt if isinstance(prompt, dict) else {}
        rows.append(
            {
                "order": index,
                "run": item.get("run_name"),
                "gate_status": item.get("gate_status"),
                "mean_score": item.get("mean_score"),
                "risk_level": item.get("risk_level"),
                "review_required": item.get("review_required"),
                "provider": model_dict.get("provider"),
                "model": model_dict.get("model_id"),
                "prompt_hash": prompt_dict.get("prompt_hash"),
                "risk_categories": item.get("risk_categories", []),
            }
        )
    return rows


def _soft_hard_signal(payload: JsonDict) -> str:
    risk = payload.get("risk", "unknown")
    distance = payload.get("mean_projection_distance")
    return f"risk={risk}; mean distance={distance}"


def _hidden_state_signal(payload: JsonDict) -> str:
    source = payload.get("source", "unknown")
    model_id = payload.get("model_id")
    shape = payload.get("states_shape")
    if model_id:
        return f"source={source}; model={model_id}; shape={shape}"
    return f"source={source}; shape={shape}"


def _trajectory_signal(payload: JsonDict) -> str:
    signal = payload.get("turnpike_like_signal")
    slope = payload.get("log_decay_slope")
    return f"turnpike={signal}; slope={slope}"


def _riccati_signal(payload: JsonDict) -> str:
    stable = payload.get("stable_surrogate")
    radius = payload.get("closed_loop_spectral_radius")
    return f"stable={stable}; rho={radius}"


def _tv_soft_signal(payload: JsonDict) -> str:
    deltas = payload.get("delta_vs_baseline")
    if isinstance(deltas, dict) and deltas:
        best_key = max(deltas, key=lambda key: float(deltas.get(key) or 0.0))
        return f"best delta={best_key}:{deltas.get(best_key)}"
    means = payload.get("method_means")
    return f"method means={len(means) if isinstance(means, dict) else 0}"


def _map_node(*, key: str, label: str, status: str, summary: str) -> JsonDict:
    return {"key": key, "label": label, "status": status, "summary": summary}


def _manifest_has_split(detail: JsonDict) -> bool:
    manifest = detail.get("manifest")
    if not isinstance(manifest, dict):
        return False
    return bool(
        manifest.get("split_hash")
        or manifest.get("split")
        or manifest.get("splits")
        or manifest.get("split_manifest")
    )


def _split_summary(detail: JsonDict) -> str:
    splits = detail.get("splits")
    if isinstance(splits, dict) and splits:
        return str(splits.get("split_hash") or splits.get("hash") or "recorded")
    manifest = detail.get("manifest")
    if isinstance(manifest, dict):
        return str(manifest.get("split_hash") or manifest.get("split") or "recorded")
    return "not recorded"


def _comparison_summary(comparison: JsonDict) -> str:
    if not comparison:
        return "not run"
    delta = comparison.get("mean_delta")
    p_value = comparison.get("permutation_p_value")
    if p_value is None:
        return f"delta={delta}"
    return f"delta={delta}; p={p_value}"


def _validity_status(payload: JsonDict) -> str:
    if not payload:
        return "missing"
    value = str(payload.get("validity") or payload.get("status") or "").lower()
    if value in {"clean", "pass", "valid", "prompt_only"}:
        return "ready"
    if value in {"blocked", "invalid", "fail", "failed"}:
        return "blocked"
    return "needs_review"


def _claim_map_status(claim: JsonDict) -> str:
    if not claim:
        return "missing"
    status = str(claim.get("status") or "").lower()
    if status == "pass":
        return "ready"
    if status == "fail":
        return "blocked"
    if status == "needs_review":
        return "needs-review"
    return "missing"


def _claim_map_summary(claim: JsonDict) -> str:
    if not claim:
        return "not run"
    requested = str(claim.get("requested_claim") or "")
    status = str(claim.get("status") or "")
    if requested or status:
        return f"{requested}: {status}".strip(": ")
    return "not run"


def _evidence_signal(section_name: str, payload: JsonDict) -> str:
    if section_name == "statistical_evidence":
        return (
            f"delta={payload.get('mean_delta')}; "
            f"p={payload.get('permutation_p_value')}"
        )
    if section_name == "comparison_validity":
        prompt_only = payload.get("prompt_only_comparison")
        return f"validity={payload.get('status')}; prompt-only={prompt_only}"
    if section_name == "deployment_diagnostics":
        return f"soft-hard risk={payload.get('soft_hard_risk')}"
    if section_name == "hidden_state_diagnostics":
        return (
            f"source={payload.get('input_source')}; "
            f"turnpike={payload.get('turnpike_like_signal')}"
        )
    if section_name == "riccati_surrogate":
        return (
            f"stable={payload.get('stable_surrogate')}; "
            f"rho={payload.get('closed_loop_spectral_radius')}"
        )
    if section_name == "time_varying_control":
        return (
            f"best={payload.get('best_delta_method')}; "
            f"delta={payload.get('best_delta')}"
        )
    return str(payload.get("reason") or payload.get("status") or "")


def _claim_ladder_status(
    *,
    tier_value: int,
    required_tier: int,
    recommendation: str,
) -> str:
    if tier_value < required_tier:
        return "missing"
    if recommendation == "supported":
        return "supported"
    if recommendation in {"not_supported", "insufficient_evidence"}:
        return "blocked"
    return "needs_review"


def _hidden_state_payload(detail: JsonDict) -> JsonDict:
    research = detail.get("research_diagnostics")
    if isinstance(research, dict):
        inputs = research.get("inputs")
        if isinstance(inputs, dict):
            hidden = inputs.get("hidden_states")
            if isinstance(hidden, dict) and hidden:
                return hidden
    artifacts = detail.get("artifacts")
    if isinstance(artifacts, list) and "inputs/hidden_states.npz" in artifacts:
        return {"source": "provided_npz", "path": "inputs/hidden_states.npz"}
    diagnostics = detail.get("diagnostics")
    if isinstance(diagnostics, dict) and isinstance(diagnostics.get("trajectory"), dict):
        return {"source": "inferred_from_trajectory", "path": None}
    return {}


def filter_history_rows(
    rows: list[JsonDict],
    *,
    only_review_required: bool = False,
    only_high_risk: bool = False,
    provider: str = "",
    model: str = "",
) -> list[JsonDict]:
    """Filter normalized history rows for dashboard views."""

    provider_filter = provider.strip().lower()
    model_filter = model.strip().lower()
    filtered: list[JsonDict] = []
    for row in rows:
        if only_review_required and not row.get("review_required"):
            continue
        if only_high_risk and row.get("risk_level") != "high":
            continue
        if provider_filter and provider_filter not in str(row.get("provider") or "").lower():
            continue
        if model_filter and model_filter not in str(row.get("model") or "").lower():
            continue
        filtered.append(row)
    return filtered


def audit_detail_sections(audit: JsonDict) -> dict[str, list[JsonDict]]:
    """Return high-signal audit detail sections for display."""

    return {
        "secret_findings": _dict_rows(audit.get("secret_findings")),
        "secret_scanner": [{"value": str(audit.get("secret_scanner", "builtin"))}],
        "sarif_path": [{"path": str(audit.get("sarif_path", ""))}]
        if audit.get("sarif_path")
        else [],
        "dependency_files_changed": _path_rows(audit.get("dependency_files_changed")),
        "lockfiles_changed": _path_rows(audit.get("lockfiles_changed")),
        "workflow_files_changed": _path_rows(audit.get("workflow_files_changed")),
        "deleted_test_files": _path_rows(audit.get("deleted_test_files")),
        "unexpected_files": _path_rows(audit.get("unexpected_files")),
        "test_results": _dict_rows(audit.get("test_results")),
    }


def changed_line_rows(audit: JsonDict) -> list[JsonDict]:
    """Return changed-line rows annotated with the highest visible audit risk."""

    changed_lines = audit.get("changed_lines")
    if not isinstance(changed_lines, dict):
        return []
    secret_paths = _paths_from_findings(audit.get("secret_findings"))
    workflow_paths = set(_strings(audit.get("workflow_files_changed")))
    dependency_paths = set(_strings(audit.get("dependency_files_changed")))
    lockfile_paths = set(_strings(audit.get("lockfiles_changed")))
    deleted_test_paths = set(_strings(audit.get("deleted_test_files")))
    dangerous_paths = set(_strings(audit.get("dangerous_paths")))
    rows: list[JsonDict] = []
    for path in sorted(str(item) for item in changed_lines):
        counts = changed_lines.get(path)
        counts_dict = counts if isinstance(counts, dict) else {}
        rows.append(
            {
                "file": path,
                "added": counts_dict.get("added", 0),
                "deleted": counts_dict.get("deleted", 0),
                "risk": _file_risk(
                    path,
                    secret_paths=secret_paths,
                    workflow_paths=workflow_paths,
                    dependency_paths=dependency_paths,
                    lockfile_paths=lockfile_paths,
                    deleted_test_paths=deleted_test_paths,
                    dangerous_paths=dangerous_paths,
                ),
            }
        )
    return rows


def guard_download_payloads(result: JsonDict) -> dict[str, str]:
    """Return text payloads for Guard tab download buttons."""

    return {
        "guard_result.json": json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        "improved_prompt.txt": str(result.get("improved_prompt", "")) + "\n",
    }


def risk_category_counts(detail: JsonDict) -> dict[str, int]:
    """Return risk category counts from guard/gate-style artifacts."""

    counts: dict[str, int] = {}
    for category in _extract_categories(detail.get("gate")):
        counts[category] = counts.get(category, 0) + 1
    for category in _extract_categories(detail.get("audit")):
        counts[category] = counts.get(category, 0) + 1
    return counts


def model_rows(detail: JsonDict) -> list[JsonDict]:
    """Return model provenance rows for display."""

    manifest = detail.get("manifest")
    if not isinstance(manifest, dict):
        return []
    rows: list[JsonDict] = []
    for label, key in [("baseline", "baseline_model"), ("candidate", "candidate_model")]:
        model = manifest.get(key)
        if isinstance(model, dict) and model:
            rows.append({"role": label, **model})
    model = manifest.get("model")
    if isinstance(model, dict) and model:
        rows.append({"role": "run", **model})
    return rows


def slice_rows(detail: JsonDict) -> list[JsonDict]:
    """Return baseline/candidate slice rows."""

    baseline = _by_slice(detail.get("baseline_metrics"))
    candidate = _by_slice(detail.get("candidate_metrics"))
    rows: list[JsonDict] = []
    for name in sorted(set(baseline) | set(candidate)):
        rows.append(
            {
                "slice": name,
                "baseline": baseline.get(name),
                "candidate": candidate.get(name),
            }
        )
    return rows


def _read_optional(path: Path) -> JsonDict:
    if not path.exists():
        return {}
    return read_json(path)


def _has_any_artifact(path: Path) -> bool:
    return any((path / name).exists() for name in RUN_ARTIFACTS)


def _has_run_level_artifact(path: Path) -> bool:
    return any((path / name).exists() for name in RUN_LEVEL_ARTIFACTS)


def _by_slice(value: object) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    raw = value.get("by_slice")
    if not isinstance(raw, dict):
        return {}
    result: dict[str, float] = {}
    for key, score in raw.items():
        if isinstance(score, int | float):
            result[str(key)] = float(score)
    return result


def _extract_categories(value: object) -> list[str]:
    if not isinstance(value, dict):
        return []
    categories: list[str] = []
    raw_categories = value.get("risk_categories")
    if isinstance(raw_categories, list):
        categories.extend(str(item) for item in raw_categories)
    checks = value.get("checks")
    if isinstance(checks, dict):
        for check in checks.values():
            if isinstance(check, dict):
                raw = check.get("risk_categories") or check.get("violations")
                if isinstance(raw, list):
                    categories.extend(str(item) for item in raw)
    if value.get("dangerous_paths"):
        categories.append("dangerous_path")
    if value.get("public_api_changed"):
        categories.append("public_api")
    return categories


def _path_rows(value: object) -> list[JsonDict]:
    if not isinstance(value, list):
        return []
    return [{"path": str(item)} for item in value]


def _dict_rows(value: object) -> list[JsonDict]:
    if not isinstance(value, list):
        return []
    rows: list[JsonDict] = []
    for item in value:
        if isinstance(item, dict):
            rows.append(dict(item))
        else:
            rows.append({"value": str(item)})
    return rows


def _strings(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _paths_from_findings(value: object) -> set[str]:
    paths: set[str] = set()
    if not isinstance(value, list):
        return paths
    for item in value:
        if isinstance(item, dict) and item.get("path"):
            paths.add(str(item["path"]))
    return paths


def _file_risk(
    path: str,
    *,
    secret_paths: set[str],
    workflow_paths: set[str],
    dependency_paths: set[str],
    lockfile_paths: set[str],
    deleted_test_paths: set[str],
    dangerous_paths: set[str],
) -> str:
    if path in secret_paths:
        return "secret"
    if path in dangerous_paths:
        return "dangerous_path"
    if path in workflow_paths:
        return "workflow"
    if path in dependency_paths:
        return "dependency"
    if path in lockfile_paths:
        return "lockfile"
    if path in deleted_test_paths:
        return "deleted_test"
    return "normal"
