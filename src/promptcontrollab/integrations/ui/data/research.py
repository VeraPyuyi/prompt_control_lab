"""Research, evidence, and ecosystem artifact readers."""

from __future__ import annotations

from pathlib import Path

from promptcontrollab.audit.claim_check import CLAIM_LABELS, CLAIM_REQUIREMENTS, TIER_ORDER
from promptcontrollab.core.files import JsonDict
from promptcontrollab.integrations.ui.data.common import _mapping, _nonnegative_int
from promptcontrollab.integrations.ui.data.constants import PEOC_STATUSES
from promptcontrollab.integrations.ui.data.run import first_comparison


def peoc_status_summary(detail: JsonDict, language: str = "en") -> JsonDict:
    """Return fail-closed status counts and claim scope for a PEOC import.

    A section counts as available only when its explicit status is exactly
    ``available``. Negative, partial, unknown, and malformed states never get
    promoted to positive evidence.
    """

    evidence = _mapping(detail.get("peoc_evidence"))
    case = _mapping(detail.get("peoc_case_study"))
    counts = {status: 0 for status in PEOC_STATUSES}
    sections = evidence.get("sections")
    if evidence and isinstance(sections, dict):
        for payload in sections.values():
            section = _mapping(payload)
            status = str(section.get("status") or "missing")
            if status in counts:
                counts[status] += 1
            else:
                counts["missing"] += 1
    else:
        raw_counts = case.get("status_counts")
        if isinstance(raw_counts, dict):
            for status in PEOC_STATUSES:
                counts[status] = _nonnegative_int(raw_counts.get(status))

    claim_boundary = _mapping(evidence.get("claim_boundary"))
    full_support = claim_boundary.get("full_research_support") is True
    claim_status = str(claim_boundary.get("status") or "unknown")
    statement = str(claim_boundary.get("statement") or "")
    if evidence:
        if language == "zh":
            statement = (
                "导入证据支持完整研究能力集合。"
                if full_support
                else "导入证据不支持完整研究能力集合。"
            )
    elif language == "zh":
        statement = str(case.get("safe_claim_zh") or statement)
    else:
        statement = str(case.get("safe_claim") or statement)

    manifest_hash = str(
        _mapping(evidence.get("bundle")).get("manifest_sha256")
        or _mapping(detail.get("source_manifest")).get("manifest_sha256")
        or case.get("source_manifest_sha256")
        or case.get("manifest_hash")
        or ""
    )
    return {
        **counts,
        "total": sum(counts.values()),
        "has_real_evidence": bool(case or evidence),
        "manifest_sha256": manifest_hash,
        "full_research_support": full_support,
        "claim_status": claim_status,
        "statement": statement,
    }


def peoc_method_rows(detail: JsonDict) -> list[JsonDict]:
    """Return public-safe hard-evaluation method rows from a PEOC import."""

    evidence = _mapping(detail.get("peoc_evidence"))
    if evidence:
        hard = _peoc_section(detail, "hard_evaluation")
        if hard.get("status") != "available":
            return []
        rows = _mapping(hard.get("observations")).get("rows")
    else:
        case = _mapping(detail.get("peoc_case_study"))
        rows = case.get("hard_method_rows")
        hard_summary = _mapping(case.get("hard_summary"))
        if not isinstance(rows, list) or hard_summary.get("status") != "available":
            return []
    if not isinstance(rows, list):
        return []

    fields = ("model", "task", "method", "n", "mean", "sd", "budget", "T", "L0")
    return [
        {field: item.get(field) for field in fields}
        for item in rows
        if isinstance(item, dict)
    ]


def peoc_trajectory_rows(detail: JsonDict) -> list[JsonDict]:
    """Return the selected stationary/heterogeneous trajectory comparison."""

    evidence = _mapping(detail.get("peoc_evidence"))
    if evidence:
        trajectory = _peoc_section(detail, "trajectory")
        if trajectory.get("status") != "available":
            return []
        pair = _mapping(_mapping(trajectory.get("observations")).get("headline_pair"))
    else:
        case = _mapping(detail.get("peoc_case_study"))
        if case.get("trajectory_status") != "available":
            return []
        pair = _mapping(case.get("selected_trajectory_pair"))
    model = str(pair.get("model") or "")
    seed = pair.get("seed")
    rows: list[JsonDict] = []
    for lane in ("stationary", "heterogeneous"):
        payload = _mapping(pair.get(lane))
        if payload.get("status") != "available":
            continue
        summary = _mapping(payload.get("summary")) or payload
        source = _mapping(payload.get("source"))
        rows.append(
            {
                "lane": lane,
                "model": model or str(payload.get("model") or ""),
                "seed": seed if seed is not None else payload.get("seed"),
                "alpha_emp_mean": summary.get("alpha_emp_mean"),
                "R2_mean": summary.get("R2_mean"),
                "hidden_dim": summary.get("hidden_dim"),
                "samples": summary.get("n_streams") or summary.get("n_prompts"),
                "source": str(payload.get("relative_path") or source.get("relative_path") or ""),
            }
        )
    return rows


def peoc_limitation_rows(detail: JsonDict, language: str = "en") -> list[JsonDict]:
    """Return non-positive PEOC sections with localized limitations."""

    evidence = _mapping(detail.get("peoc_evidence"))
    rows: list[JsonDict] = []
    if not evidence:
        case = _mapping(detail.get("peoc_case_study"))
        limited = case.get("limited_sections")
    else:
        limited = None
    if isinstance(limited, list):
        for item in limited:
            payload = _mapping(item)
            status = str(payload.get("status") or "missing")
            if status == "available":
                continue
            limitation = payload.get("limitation_zh") if language == "zh" else None
            rows.append(
                {
                    "section": str(payload.get("section") or "unknown"),
                    "status": status,
                    "origin": str(payload.get("origin") or "unknown"),
                    "limitation": str(limitation or payload.get("limitation") or ""),
                }
            )
        return rows

    sections = evidence.get("sections")
    if not isinstance(sections, dict):
        return []
    for name, item in sections.items():
        payload = _mapping(item)
        status = str(payload.get("status") or "missing")
        if status == "available":
            continue
        limitations = payload.get("limitations")
        message = ""
        if isinstance(limitations, list) and limitations:
            message = str(limitations[0])
        rows.append(
            {
                "section": str(name),
                "status": status if status in PEOC_STATUSES else "missing",
                "origin": str(payload.get("origin") or "unknown"),
                "limitation": message,
            }
        )
    return rows


def _peoc_section(detail: JsonDict, name: str) -> JsonDict:
    """Normalize peoc section values for dashboard use."""
    evidence = _mapping(detail.get("peoc_evidence"))
    sections = evidence.get("sections")
    return _mapping(sections.get(name)) if isinstance(sections, dict) else {}


def research_overview_path(detail: JsonDict) -> Path | None:
    """Return the generated research overview SVG path for the selected run."""

    artifacts = detail.get("artifacts")
    artifact_list = [str(item) for item in artifacts] if isinstance(artifacts, list) else []
    if "research_overview.svg" not in artifact_list:
        return None
    run_path = detail.get("path")
    if not isinstance(run_path, str) or not run_path:
        return None
    candidate = Path(run_path) / "research_overview.svg"
    return candidate if candidate.exists() else None


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
        (
            "terminal_sensitivity",
            "terminal sensitivity",
            "Early-control response to terminal perturbations",
            _terminal_certificate_signal,
        ),
        (
            "green_certificate",
            "Green certificate",
            "Hyperbolic splitting and boundary transversality",
            _green_certificate_signal,
        ),
        (
            "posterior_certificate",
            "posterior certificate",
            "Local residual and derivative bound check",
            _posterior_certificate_signal,
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


def research_insight_rows(detail: JsonDict, language: str = "en") -> list[JsonDict]:
    """Return plain-language explanations for paper-derived diagnostics."""

    lang = "zh" if language == "zh" else "en"
    diagnostics = detail.get("diagnostics")
    diagnostics_dict = diagnostics if isinstance(diagnostics, dict) else {}
    specs: list[tuple[str, str, JsonDict]] = [
        (
            "soft_hard",
            "diagnostics/soft_hard.json",
            _diagnostic_payload(diagnostics_dict, "soft_hard"),
        ),
        ("hidden_states", "inputs/hidden_states.npz", _hidden_state_payload(detail)),
        (
            "trajectory",
            "diagnostics/trajectory.json",
            _diagnostic_payload(diagnostics_dict, "trajectory"),
        ),
        (
            "riccati",
            "diagnostics/riccati.json",
            _diagnostic_payload(diagnostics_dict, "riccati"),
        ),
        (
            "tv_soft",
            "diagnostics/tv_soft.json",
            _diagnostic_payload(diagnostics_dict, "tv_soft"),
        ),
    ]
    rows: list[JsonDict] = []
    for key, artifact, payload in specs:
        payload_dict = payload if isinstance(payload, dict) else {}
        rows.append(
            {
                "diagnostic": _research_label(key, lang),
                "checks": _research_check(key, lang),
                "result": _research_result(key, payload_dict, lang),
                "interpretation": _research_interpretation(key, payload_dict, lang),
                "next_action": _research_next_action(key, payload_dict, artifact, lang),
            }
        )
    return rows


def research_at_a_glance_rows(detail: JsonDict, language: str = "en") -> list[JsonDict]:
    """Return localized rows from ``research_diagnostics.at_a_glance``."""

    research = detail.get("research_diagnostics")
    research_dict = research if isinstance(research, dict) else {}
    summary = research_dict.get("at_a_glance")
    if not isinstance(summary, dict) or not summary:
        return []

    labels = {
        "en": {
            "mode": "Mode",
            "diagnostics_ready": "Diagnostics ready",
            "control_certificates_ready": "Control certificates ready",
            "hidden_state_input": "Hidden-state input",
            "evidence_recommendation": "Evidence recommendation",
            "evidence_tier": "Evidence tier",
            "claim_status": "Claim status",
            "safe_claim": "Safe claim",
            "open_first": "Open first",
            "next_action": "Next action",
        },
        "zh": {
            "mode": "模式",
            "diagnostics_ready": "诊断覆盖",
            "control_certificates_ready": "控制证书覆盖",
            "hidden_state_input": "Hidden-state 输入",
            "evidence_recommendation": "证据建议",
            "evidence_tier": "证据层级",
            "claim_status": "主张状态",
            "safe_claim": "安全主张",
            "open_first": "先打开",
            "next_action": "下一步",
        },
    }
    lang = "zh" if language == "zh" else "en"
    ordered_keys = [
        "mode",
        "diagnostics_ready",
        "control_certificates_ready",
        "hidden_state_input",
        "evidence_recommendation",
        "evidence_tier",
        "claim_status",
        "safe_claim",
        "open_first",
        "next_action",
    ]
    rows: list[JsonDict] = []
    for key in ordered_keys:
        value = summary.get(key)
        if value is None or value == "":
            continue
        rows.append({"field": labels[lang][key], "value": str(value)})
    return rows


def _diagnostic_payload(diagnostics: JsonDict, key: str) -> JsonDict:
    """Normalize diagnostic payload values for dashboard use."""
    payload = diagnostics.get(key)
    return payload if isinstance(payload, dict) else {}


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
    gate = evidence_gate_summary(detail)
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
            key="evidence_gate",
            label="Evidence gate",
            status=_evidence_gate_map_status(gate),
            summary=str(gate.get("summary") or gate.get("status") or "not run"),
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


def evidence_gate_summary(detail: JsonDict) -> JsonDict:
    """Return the required/advisory evidence-gate status for the research overview."""

    payload = detail.get("evidence_gate")
    if not isinstance(payload, dict) or not payload:
        return {}
    required = payload.get("required_checks")
    advisory = payload.get("advisory_checks")
    return {
        "status": payload.get("status"),
        "summary": payload.get("summary"),
        "required_checks": required if isinstance(required, dict) else {},
        "advisory_checks": advisory if isinstance(advisory, dict) else {},
    }


def evidence_gate_rows(detail: JsonDict) -> list[JsonDict]:
    """Return rows for evidence-gate required and advisory checks."""

    summary = evidence_gate_summary(detail)
    rows: list[JsonDict] = []
    for group in ["required_checks", "advisory_checks"]:
        checks = summary.get(group)
        if not isinstance(checks, dict):
            continue
        for name, raw_check in checks.items():
            check = raw_check if isinstance(raw_check, dict) else {}
            rows.append(
                {
                    "group": group.replace("_", " "),
                    "check": str(name).replace("_", " "),
                    "status": check.get("status", "unknown"),
                    "summary": check.get("summary", ""),
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


def ecosystem_evidence_matrix_rows(detail: JsonDict) -> list[JsonDict]:
    """Return PCL-added evidence matrix rows for ecosystem scorecards."""

    payload = detail.get("ecosystem_scorecard")
    if not isinstance(payload, dict):
        return []
    raw_rows = payload.get("pcl_evidence_matrix")
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
                "prompt_only_validity": item.get("prompt_only_validity", ""),
                "paired_stats": item.get("paired_stats", ""),
                "evidence_card": item.get("evidence_card", ""),
                "claim_check": item.get("claim_check", ""),
                "research_bundle": item.get("research_bundle", ""),
                "bundle_verification": item.get("bundle_verification", ""),
                "gap_status": item.get("gap_status", ""),
                "missing_count": item.get("missing_paper_diagnostic_count", ""),
                "missing_paper_diagnostics": ", ".join(str(part) for part in missing)
                if isinstance(missing, list)
                else str(missing or ""),
                "next_command": item.get("next_command", ""),
            }
        )
    return rows


def ecosystem_market_map_rows(detail: JsonDict) -> list[JsonDict]:
    """Return positioning-only adjacent-market rows from ecosystem scorecards."""

    payload = detail.get("ecosystem_scorecard")
    if not isinstance(payload, dict):
        return []
    raw_rows = payload.get("market_map")
    if not isinstance(raw_rows, list):
        return []
    rows: list[JsonDict] = []
    for item in raw_rows:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "tool": item.get("tool", ""),
                "strong_lane": item.get("strong_lane", ""),
                "pcl_should_learn": item.get("pcl_should_learn", ""),
                "pcl_still_owns": item.get("pcl_owns", ""),
                "pcl_product_move": item.get("pcl_product_move", ""),
                "priority": item.get("priority", ""),
                "status": item.get("status", ""),
            }
        )
    return rows


def ecosystem_market_readiness(detail: JsonDict) -> JsonDict:
    """Return compact market-readiness guidance from ecosystem scorecards."""

    payload = detail.get("ecosystem_scorecard")
    if not isinstance(payload, dict):
        return {}
    readiness = payload.get("market_readiness")
    return readiness if isinstance(readiness, dict) else {}


def prompt_asset_summary(detail: JsonDict) -> JsonDict:
    """Return a compact summary for prompt-optimizer asset import runs."""

    bundle = detail.get("prompt_assets")
    if not isinstance(bundle, dict) or not bundle:
        return {}
    return {
        "source_tool": bundle.get("source_tool", ""),
        "asset_count": bundle.get("asset_count", 0),
        "evaluation_status": bundle.get("evaluation_status", ""),
        "source_sha256": bundle.get("source_sha256", ""),
        "boundary": bundle.get("boundary", ""),
    }


def prompt_asset_rows(detail: JsonDict) -> list[JsonDict]:
    """Return one row per imported prompt asset candidate."""

    bundle = detail.get("prompt_assets")
    if not isinstance(bundle, dict):
        return []
    assets = bundle.get("assets")
    if not isinstance(assets, list):
        return []
    rows: list[JsonDict] = []
    for item in assets:
        if not isinstance(item, dict):
            continue
        tags = item.get("tags")
        model_or_source = item.get("model_or_source")
        model_dict = model_or_source if isinstance(model_or_source, dict) else {}
        rows.append(
            {
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "type": item.get("source_type", ""),
                "tags": ", ".join(str(part) for part in tags) if isinstance(tags, list) else "",
                "model": model_dict.get("model_name", ""),
                "use_count": item.get("use_count", ""),
                "has_original": item.get("has_original_content", False),
                "content_hash": item.get("content_hash", ""),
            }
        )
    return rows


def prompt_optimizer_gap_rows(detail: JsonDict) -> list[JsonDict]:
    """Return evidence gaps for prompt-optimizer asset imports."""

    plan = detail.get("prompt_optimizer_gap_plan")
    if not isinstance(plan, dict):
        return []
    missing = plan.get("missing_evidence")
    if not isinstance(missing, list):
        return []
    commands = plan.get("recommended_commands")
    command_list = [str(item) for item in commands] if isinstance(commands, list) else []
    rows: list[JsonDict] = []
    for index, item in enumerate(missing):
        rows.append(
            {
                "missing_evidence": str(item),
                "suggested_command": command_list[index] if index < len(command_list) else "",
            }
        )
    return rows


def scaffold_check_summary(detail: JsonDict) -> JsonDict:
    """Return a compact scaffold readiness summary for prompt-optimizer imports."""

    payload = detail.get("scaffold_check")
    if not isinstance(payload, dict) or not payload:
        return {}
    issues = payload.get("issues")
    issue_count = len(issues) if isinstance(issues, list) else 0
    return {
        "status": payload.get("status", "unknown"),
        "issue_count": issue_count,
        "task_count": payload.get("task_count", 0),
        "baseline_prediction_count": payload.get("baseline_prediction_count", 0),
        "candidate_prediction_count": payload.get("candidate_prediction_count", 0),
        "prompt_file_count": payload.get("prompt_file_count", 0),
        "boundary": payload.get("boundary", ""),
        "html_path": payload.get("html_path", "eval_scaffold/scaffold_check.html"),
    }


def scaffold_check_issue_rows(detail: JsonDict) -> list[JsonDict]:
    """Return scaffold check issues for display."""

    payload = detail.get("scaffold_check")
    if not isinstance(payload, dict):
        return []
    issues = payload.get("issues")
    if not isinstance(issues, list):
        return []
    rows: list[JsonDict] = []
    for item in issues:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "severity": item.get("severity", ""),
                "code": item.get("code", ""),
                "path": item.get("path", ""),
                "message": item.get("message", ""),
            }
        )
    return rows


def scaffold_check_action_rows(detail: JsonDict) -> list[JsonDict]:
    """Return next actions from a scaffold check artifact."""

    payload = detail.get("scaffold_check")
    if not isinstance(payload, dict):
        return []
    actions = payload.get("next_actions")
    if not isinstance(actions, list):
        return []
    return [{"next_action": str(action)} for action in actions]


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
    """Normalize gap script purpose values for dashboard use."""
    if name.endswith(".md"):
        return "reviewable evidence-gap handoff plan"
    return "review-first command script; edit placeholders before use"


def _action_rows(value: object) -> list[JsonDict]:
    """Normalize action rows values for dashboard use."""
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
    """Normalize evidence gap row values for dashboard use."""
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


def _soft_hard_signal(payload: JsonDict) -> str:
    """Normalize soft hard signal values for dashboard use."""
    risk = payload.get("risk", "unknown")
    distance = payload.get("mean_projection_distance")
    return f"risk={risk}; mean distance={distance}"


def _hidden_state_signal(payload: JsonDict) -> str:
    """Normalize hidden state signal values for dashboard use."""
    source = payload.get("source", "unknown")
    model_id = payload.get("model_id")
    shape = payload.get("states_shape")
    if model_id:
        return f"source={source}; model={model_id}; shape={shape}"
    return f"source={source}; shape={shape}"


def _trajectory_signal(payload: JsonDict) -> str:
    """Normalize trajectory signal values for dashboard use."""
    signal = payload.get("turnpike_like_signal")
    slope = payload.get("log_decay_slope")
    return f"turnpike={signal}; slope={slope}"


def _riccati_signal(payload: JsonDict) -> str:
    """Normalize riccati signal values for dashboard use."""
    stable = payload.get("stable_surrogate")
    radius = payload.get("closed_loop_spectral_radius")
    return f"stable={stable}; rho={radius}"


def _tv_soft_signal(payload: JsonDict) -> str:
    """Normalize tv soft signal values for dashboard use."""
    deltas = payload.get("delta_vs_baseline")
    if isinstance(deltas, dict) and deltas:
        best_key = max(deltas, key=lambda key: float(deltas.get(key) or 0.0))
        return f"best delta={best_key}:{deltas.get(best_key)}"
    means = payload.get("method_means")
    return f"method means={len(means) if isinstance(means, dict) else 0}"


def _terminal_certificate_signal(payload: JsonDict) -> str:
    """Normalize terminal certificate signal values for dashboard use."""
    return (
        f"state={payload.get('check_state')}; alpha={payload.get('decay_rate')}; "
        f"R2={payload.get('r_squared')}"
    )


def _green_certificate_signal(payload: JsonDict) -> str:
    """Normalize green certificate signal values for dashboard use."""
    return (
        f"state={payload.get('check_state')}; gap={payload.get('hyperbolicity_margin')}; "
        f"sigma_min={payload.get('boundary_sigma_min')}"
    )


def _posterior_certificate_signal(payload: JsonDict) -> str:
    """Normalize posterior certificate signal values for dashboard use."""
    return (
        f"state={payload.get('check_state')}; h={payload.get('h')}; "
        f"radius={payload.get('existence_radius')}"
    )


def _research_label(key: str, language: str) -> str:
    """Normalize research label values for dashboard use."""
    labels = {
        "en": {
            "soft_hard": "Soft-to-hard gap",
            "hidden_states": "Hidden-state input",
            "trajectory": "Trajectory stability",
            "riccati": "Riccati surrogate",
            "tv_soft": "Time-varying soft-control",
        },
        "zh": {
            "soft_hard": "软转硬 gap",
            "hidden_states": "Hidden-state 输入",
            "trajectory": "轨迹稳定性",
            "riccati": "Riccati 代理模型",
            "tv_soft": "时变 soft-control",
        },
    }
    return labels[language][key]


def _research_check(key: str, language: str) -> str:
    """Normalize research check values for dashboard use."""
    checks = {
        "en": {
            "soft_hard": "Can a learned soft prompt survive hard-token deployment?",
            "hidden_states": "Do we have the activation source needed for trajectory diagnostics?",
            "trajectory": "Does the hidden-state path show drift or turnpike-like decay?",
            "riccati": "Is the fitted finite-dimensional control surrogate self-consistent?",
            "tv_soft": "Does time-varying structure beat static, shuffled, or random controls?",
        },
        "zh": {
            "soft_hard": "训练得到的 soft prompt 转成 hard token 后还可靠吗?",
            "hidden_states": "是否已有 trajectory 诊断需要的 hidden-state 输入?",
            "trajectory": "hidden-state 路径是否漂移, 或出现 turnpike-like 衰减?",
            "riccati": "拟合出的有限维控制代理模型是否自洽?",
            "tv_soft": "时变结构是否真的优于 static, shuffled 或 random control?",
        },
    }
    return checks[language][key]


def _research_result(key: str, payload: JsonDict, language: str) -> str:
    """Normalize research result values for dashboard use."""
    if not payload:
        return "Not measured yet." if language == "en" else "还没有测。"
    if key == "soft_hard":
        return _soft_hard_signal(payload)
    if key == "hidden_states":
        return _hidden_state_signal(payload)
    if key == "trajectory":
        return _trajectory_signal(payload)
    if key == "riccati":
        return _riccati_signal(payload)
    if key == "tv_soft":
        return _tv_soft_signal(payload)
    return "recorded" if language == "en" else "已记录"


def _research_interpretation(key: str, payload: JsonDict, language: str) -> str:
    """Normalize research interpretation values for dashboard use."""
    if not payload:
        return (
            "This part of the paper evidence is missing."
            if language == "en"
            else "这部分论文证据还缺失。"
        )
    if key == "soft_hard":
        risk = str(payload.get("risk") or "unknown").lower()
        if risk in {"low", "pass", "safe"}:
            return (
                "Rounded hard prompts look less risky, but still need hard-prompt evaluation."
                if language == "en"
                else "转成 hard prompt 的风险较低, 但仍要用真实 hard prompt 复测。"
            )
        return (
            "Deployment may lose quality when soft prompts are projected to tokens."
            if language == "en"
            else "soft prompt 投影成 token 后可能损失效果, 部署前要谨慎。"
        )
    if key == "hidden_states":
        return (
            "Trajectory and Riccati diagnostics can only be trusted when this input is explicit."
            if language == "en"
            else "只有明确记录 hidden-state 输入, trajectory 和 Riccati 诊断才更可复查。"
        )
    if key == "trajectory":
        signal = payload.get("turnpike_like_signal")
        if signal is True:
            return (
                "The trace shows a turnpike-like signal worth comparing across slices."
                if language == "en"
                else "轨迹出现 turnpike-like 信号, 值得按任务 slice 继续比较。"
            )
        return (
            "The trace does not yet show a strong stability signature."
            if language == "en"
            else "目前还没有强稳定性信号, 可能需要更多 trace 或分 slice 检查。"
        )
    if key == "riccati":
        stable = payload.get("stable_surrogate")
        radius = payload.get("closed_loop_spectral_radius")
        radius_value = _float_or_none(radius)
        if stable is True or (radius_value is not None and radius_value < 1.0):
            return (
                "The fitted surrogate is internally stable on this reduced diagnostic model."
                if language == "en"
                else "降维代理模型在这次诊断中表现为内部稳定。"
            )
        return (
            "The surrogate should be reviewed before using it as supporting evidence."
            if language == "en"
            else "这个代理模型还需要复查, 暂时不宜作为强证据。"
        )
    if key == "tv_soft":
        best = _best_delta_key(payload)
        if best and "time" in best:
            return (
                "Time-varying structure may explain part of the gain."
                if language == "en"
                else "收益可能部分来自时变结构, 而不只是参数更多。"
            )
        return (
            "The current result does not isolate a clear time-varying advantage."
            if language == "en"
            else "当前结果还不能清楚证明时变结构带来优势。"
        )
    return "Recorded diagnostic evidence." if language == "en" else "已记录诊断证据。"


def _research_next_action(
    key: str,
    payload: JsonDict,
    artifact: str,
    language: str,
) -> str:
    """Normalize research next action values for dashboard use."""
    if not payload:
        command = _research_missing_command(key)
        if language == "zh":
            return f"运行 `{command}`, 生成 `{artifact}`。"
        return f"Run `{command}` to create `{artifact}`."
    if key == "soft_hard":
        return (
            "Keep the gap in the evidence bundle and retest the hard prompt."
            if language == "en"
            else "把 gap 写入证据包, 并用 hard prompt 再评测一次。"
        )
    if key == "hidden_states":
        return (
            "Use the same hidden-state source for trajectory and Riccati follow-ups."
            if language == "en"
            else "后续 trajectory 和 Riccati 诊断要继续使用同一 hidden-state 来源。"
        )
    if key == "trajectory":
        return (
            "Compare slopes by task slice before making a broad stability claim."
            if language == "en"
            else "先按任务 slice 比较 slope, 再决定是否提出稳定性主张。"
        )
    if key == "riccati":
        return (
            "Report it as a fitted surrogate probe, not as a proof about the full LM."
            if language == "en"
            else "把它表述为拟合代理探针, 不要说成完整 LM 的证明。"
        )
    if key == "tv_soft":
        return (
            "Compare static, shuffled, random, and time-varying lanes side by side."
            if language == "en"
            else "把 static、shuffled、random 和 time-varying 放在一起对比。"
        )
    return (
        "Keep this artifact with the run."
        if language == "en"
        else "把该 artifact 保留在 run 中。"
    )


def _research_missing_command(key: str) -> str:
    """Normalize research missing command values for dashboard use."""
    commands = {
        "soft_hard": "pcl soft-hard --run <selected-run>",
        "hidden_states": "pcl diagnose --run <selected-run>",
        "trajectory": "pcl trajectory --states inputs/hidden_states.npz --out diagnostics",
        "riccati": "pcl riccati --trajectory diagnostics/trajectory.json --out diagnostics",
        "tv_soft": "pcl tv-soft --config promptcontrol.example.yaml --out diagnostics",
    }
    return commands.get(key, "pcl diagnose --run <selected-run>")


def _best_delta_key(payload: JsonDict) -> str:
    """Normalize best delta key values for dashboard use."""
    deltas = payload.get("delta_vs_baseline")
    if not isinstance(deltas, dict) or not deltas:
        return ""
    return str(max(deltas, key=lambda key: float(deltas.get(key) or 0.0)))


def _float_or_none(value: object) -> float | None:
    """Normalize float or none values for dashboard use."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _map_node(*, key: str, label: str, status: str, summary: str) -> JsonDict:
    """Normalize map node values for dashboard use."""
    return {"key": key, "label": label, "status": status, "summary": summary}


def _manifest_has_split(detail: JsonDict) -> bool:
    """Normalize manifest has split values for dashboard use."""
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
    """Normalize split summary values for dashboard use."""
    splits = detail.get("splits")
    if isinstance(splits, dict) and splits:
        return str(splits.get("split_hash") or splits.get("hash") or "recorded")
    manifest = detail.get("manifest")
    if isinstance(manifest, dict):
        return str(manifest.get("split_hash") or manifest.get("split") or "recorded")
    return "not recorded"


def _comparison_summary(comparison: JsonDict) -> str:
    """Normalize comparison summary values for dashboard use."""
    if not comparison:
        return "not run"
    delta = comparison.get("mean_delta")
    p_value = comparison.get("permutation_p_value")
    if p_value is None:
        return f"delta={delta}"
    return f"delta={delta}; p={p_value}"


def _validity_status(payload: JsonDict) -> str:
    """Normalize validity status values for dashboard use."""
    if not payload:
        return "missing"
    value = str(payload.get("validity") or payload.get("status") or "").lower()
    if value in {"clean", "pass", "valid", "prompt_only"}:
        return "ready"
    if value in {"blocked", "invalid", "fail", "failed"}:
        return "blocked"
    return "needs_review"


def _claim_map_status(claim: JsonDict) -> str:
    """Normalize claim map status values for dashboard use."""
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


def _evidence_gate_map_status(gate: JsonDict) -> str:
    """Normalize evidence gate map status values for dashboard use."""
    if not gate:
        return "missing"
    status = str(gate.get("status") or "").lower()
    if status == "pass":
        return "ready"
    if status == "fail":
        return "blocked"
    if status in {"needs_review", "needs-review"}:
        return "needs-review"
    return "missing"


def _claim_map_summary(claim: JsonDict) -> str:
    """Normalize claim map summary values for dashboard use."""
    if not claim:
        return "not run"
    requested = str(claim.get("requested_claim") or "")
    status = str(claim.get("status") or "")
    if requested or status:
        return f"{requested}: {status}".strip(": ")
    return "not run"


def _evidence_signal(section_name: str, payload: JsonDict) -> str:
    """Normalize evidence signal values for dashboard use."""
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
    """Normalize claim ladder status values for dashboard use."""
    if tier_value < required_tier:
        return "missing"
    if recommendation == "supported":
        return "supported"
    if recommendation in {"not_supported", "insufficient_evidence"}:
        return "blocked"
    return "needs_review"


def _hidden_state_payload(detail: JsonDict) -> JsonDict:
    """Normalize hidden state payload values for dashboard use."""
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
