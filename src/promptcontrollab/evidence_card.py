"""Prompt optimization evidence-card generation."""

from __future__ import annotations

from pathlib import Path

from promptcontrollab.files import JsonDict, ensure_dir, write_json
from promptcontrollab.report_model import ReportModel


def build_evidence_card(run_dir: Path) -> JsonDict:
    """Build a compact evidence card from a PromptControlLab run directory."""

    model = ReportModel.from_run(run_dir)
    sections = {
        "protocol_hygiene": _protocol_hygiene(model),
        "statistical_evidence": _statistical_evidence(model),
        "comparison_validity": _comparison_validity(model),
        "deployment_diagnostics": _deployment_diagnostics(model),
        "hidden_state_diagnostics": _hidden_state_diagnostics(model),
        "riccati_surrogate": _riccati_surrogate(model),
        "time_varying_control": _time_varying_control(model),
    }
    missing = [
        name
        for name, section in sections.items()
        if isinstance(section, dict) and section.get("status") == "missing"
    ]
    recommendation = _recommendation(sections)
    tier = _evidence_tier(sections, recommendation)
    return {
        "kind": "prompt_optimization_evidence_card",
        "run_dir": str(run_dir),
        "recommendation": recommendation,
        "evidence_tier": tier["evidence_tier"],
        "claim_scope": tier["claim_scope"],
        "claim_language": tier["claim_language"],
        "next_tier_missing": tier["next_tier_missing"],
        "summary": _summary(recommendation, sections, missing, tier),
        "sections": sections,
        "missing_artifacts": missing,
        "artifacts": model.artifacts,
        "boundary": (
            "This evidence card summarizes recorded PromptControlLab artifacts. It supports "
            "review of prompt optimization evidence, but it is not a proof of universal prompt "
            "improvement or full language-model stability."
        ),
    }


def write_evidence_card(
    run_dir: Path,
    *,
    markdown_path: Path | None = None,
    json_path: Path | None = None,
) -> JsonDict:
    """Write evidence-card JSON and Markdown artifacts."""

    card = build_evidence_card(run_dir)
    resolved_json = json_path or (run_dir / "evidence_card.json")
    resolved_markdown = markdown_path or (run_dir / "evidence_card.md")
    ensure_dir(resolved_json.parent)
    ensure_dir(resolved_markdown.parent)
    write_json(resolved_json, card)
    resolved_markdown.write_text(render_evidence_card_markdown(card), encoding="utf-8")
    card["json_path"] = str(resolved_json)
    card["markdown_path"] = str(resolved_markdown)
    return card


def render_evidence_card_markdown(card: JsonDict) -> str:
    """Render a readable evidence card."""

    sections = card.get("sections")
    sections_dict = sections if isinstance(sections, dict) else {}
    lines = [
        "# Prompt Optimization Evidence Card",
        "",
        f"- Recommendation: `{card.get('recommendation', 'needs_review')}`",
        f"- Evidence tier: `{card.get('evidence_tier', 'unknown')}`",
        f"- Claim scope: {card.get('claim_scope', '')}",
        f"- Safe claim language: {card.get('claim_language', '')}",
        f"- Summary: {card.get('summary', '')}",
        f"- Next tier missing: `{card.get('next_tier_missing', [])}`",
        f"- Run directory: `{card.get('run_dir', '')}`",
        "",
        "## Protocol hygiene",
        "",
        *_section_lines(_section(sections_dict, "protocol_hygiene")),
        "",
        "## Statistical evidence",
        "",
        *_section_lines(_section(sections_dict, "statistical_evidence")),
        "",
        "## Prompt-only comparison validity",
        "",
        *_section_lines(_section(sections_dict, "comparison_validity")),
        "",
        "## Deployment diagnostics",
        "",
        *_section_lines(_section(sections_dict, "deployment_diagnostics")),
        "",
        "## Hidden-state diagnostics",
        "",
        *_section_lines(_section(sections_dict, "hidden_state_diagnostics")),
        "",
        "## Riccati surrogate",
        "",
        *_section_lines(_section(sections_dict, "riccati_surrogate")),
        "",
        "## Time-varying soft-control",
        "",
        *_section_lines(_section(sections_dict, "time_varying_control")),
        "",
        "## Boundary",
        "",
        str(card.get("boundary", "")),
        "",
    ]
    return "\n".join(lines)


def _protocol_hygiene(model: ReportModel) -> JsonDict:
    if not model.splits:
        return {"status": "missing", "reason": "No splits.json artifact found."}
    leakage = model.splits.get("leakage")
    leakage_dict = leakage if isinstance(leakage, dict) else {}
    has_leakage = leakage_dict.get("has_leakage")
    status = "fail" if has_leakage is True else "pass"
    return {
        "status": status,
        "split_hash": model.splits.get("split_hash"),
        "counts": model.splits.get("counts", {}),
        "leakage_detected": has_leakage,
    }


def _statistical_evidence(model: ReportModel) -> JsonDict:
    comparison = model.first_comparison
    if not comparison:
        return {"status": "missing", "reason": "No stats.json comparison found."}
    mean_delta = model.mean_delta
    ci = model.bootstrap_ci
    p_value = model.permutation_p_value
    holm = model.holm_adjusted_p_value
    status = "review"
    if mean_delta is not None and mean_delta < 0:
        status = "fail"
    else:
        lower = _ci_lower(ci)
        if mean_delta is not None and mean_delta > 0 and lower is not None:
            status = "pass" if lower > 0 else "review"
    return {
        "status": status,
        "mean_delta": mean_delta,
        "bootstrap_ci": ci,
        "permutation_p_value": p_value,
        "holm_adjusted_p_value": holm,
        "interpretation": comparison.get("interpretation"),
    }


def _comparison_validity(model: ReportModel) -> JsonDict:
    payload = model.comparison_validity
    if not payload:
        return {"status": "missing", "reason": "No comparison_validity.json artifact found."}
    validity = payload.get("validity", "unknown")
    status = "pass" if validity == "clean" else "fail" if validity == "invalid" else "review"
    return {
        "status": validity,
        "gate_status": status,
        "prompt_only_comparison": payload.get("prompt_only_comparison"),
        "blocking_issues": payload.get("blocking_issues", []),
        "review_items": payload.get("review_items", []),
        "plain_summary": payload.get("plain_summary"),
    }


def _deployment_diagnostics(model: ReportModel) -> JsonDict:
    soft = model.diagnostics.get("soft_hard", {})
    if not soft:
        return {"status": "missing", "reason": "No diagnostics/soft_hard.json artifact found."}
    risk = soft.get("risk", "unknown")
    status = "pass" if risk == "low" else "fail" if risk == "high" else "review"
    return {
        "status": status,
        "soft_hard_risk": risk,
        "mean_projection_distance": soft.get("mean_projection_distance"),
        "max_projection_distance": soft.get("max_projection_distance"),
    }


def _hidden_state_diagnostics(model: ReportModel) -> JsonDict:
    trajectory = model.diagnostics.get("trajectory", {})
    research = model.research_diagnostics
    inputs = research.get("inputs") if isinstance(research, dict) else {}
    input_payload = inputs.get("hidden_states") if isinstance(inputs, dict) else {}
    input_dict = input_payload if isinstance(input_payload, dict) else {}
    if not trajectory and not input_dict:
        return {
            "status": "missing",
            "reason": "No hidden-state input or trajectory artifact found.",
        }
    status = "pass" if trajectory.get("turnpike_like_signal") is True else "review"
    if not trajectory:
        status = "review"
    return {
        "status": status,
        "input_source": input_dict.get("source"),
        "model_id": input_dict.get("model_id"),
        "states_shape": input_dict.get("states_shape"),
        "pool": input_dict.get("pool"),
        "turnpike_like_signal": trajectory.get("turnpike_like_signal"),
        "log_decay_slope": trajectory.get("log_decay_slope"),
        "decay_r2": trajectory.get("decay_r2"),
    }


def _riccati_surrogate(model: ReportModel) -> JsonDict:
    riccati = model.diagnostics.get("riccati", {})
    if not riccati:
        return {"status": "missing", "reason": "No diagnostics/riccati.json artifact found."}
    stable = riccati.get("stable_surrogate")
    return {
        "status": "pass" if stable is True else "review",
        "stable_surrogate": stable,
        "closed_loop_spectral_radius": riccati.get("closed_loop_spectral_radius"),
        "theory_decay_rate": riccati.get("theory_decay_rate"),
    }


def _time_varying_control(model: ReportModel) -> JsonDict:
    tv_soft = model.diagnostics.get("tv_soft", {})
    if not tv_soft:
        return {"status": "missing", "reason": "No diagnostics/tv_soft.json artifact found."}
    deltas = tv_soft.get("delta_vs_baseline")
    deltas_dict = deltas if isinstance(deltas, dict) else {}
    best_method = _best_delta_method(deltas_dict)
    return {
        "status": "pass" if best_method else "review",
        "method_means": tv_soft.get("method_means", {}),
        "delta_vs_baseline": deltas_dict,
        "best_delta_method": best_method,
        "best_delta": deltas_dict.get(best_method) if best_method else None,
    }


def _recommendation(sections: dict[str, JsonDict]) -> str:
    statuses = [section.get("status") for section in sections.values()]
    validity = sections["comparison_validity"].get("status")
    if "fail" in statuses or validity == "invalid":
        return "not_supported"
    if statuses.count("missing") == len(statuses):
        return "insufficient_evidence"
    required = [
        sections["statistical_evidence"].get("status") == "pass",
        validity == "clean",
        sections["deployment_diagnostics"].get("status") in {"pass", "missing"},
        sections["hidden_state_diagnostics"].get("status") in {"pass", "review", "missing"},
        sections["riccati_surrogate"].get("status") in {"pass", "missing"},
    ]
    return "supported" if all(required) else "needs_review"


def _evidence_tier(sections: dict[str, JsonDict], recommendation: str) -> JsonDict:
    if recommendation in {"not_supported", "insufficient_evidence"}:
        return {
            "evidence_tier": "tier_0_insufficient_or_contradicted",
            "claim_scope": "No positive prompt-optimization claim is supported.",
            "claim_language": (
                "The recorded artifacts are insufficient or contradictory; inspect blocking "
                "issues before making a prompt-improvement claim."
            ),
            "next_tier_missing": _missing_for_sections(
                sections,
                ["statistical_evidence", "comparison_validity"],
            ),
        }

    statistical_status = sections["statistical_evidence"].get("status")
    validity = sections["comparison_validity"].get("status")
    has_pairing = statistical_status in {"pass", "review"} and validity in {"clean", "needs_review"}
    has_deployment = sections["deployment_diagnostics"].get("status") != "missing"
    has_hidden = sections["hidden_state_diagnostics"].get("status") != "missing"
    has_riccati = sections["riccati_surrogate"].get("status") != "missing"
    has_tv = sections["time_varying_control"].get("status") != "missing"
    has_protocol = sections["protocol_hygiene"].get("status") != "missing"
    research_sections = [
        "protocol_hygiene",
        "deployment_diagnostics",
        "hidden_state_diagnostics",
        "riccati_surrogate",
        "time_varying_control",
    ]

    if has_pairing and has_protocol and has_deployment and has_hidden and has_riccati and has_tv:
        return {
            "evidence_tier": "tier_4_full_research_diagnostics",
            "claim_scope": (
                "Paired prompt comparison plus paper-derived deployment, trajectory, "
                "Riccati, and time-varying diagnostics."
            ),
            "claim_language": (
                "Recorded artifacts support the candidate within the configured research "
                "diagnostic protocol; this is still not a proof of global prompt optimality."
            ),
            "next_tier_missing": [],
        }

    if has_pairing and (has_deployment or has_hidden or has_riccati or has_tv):
        return {
            "evidence_tier": "tier_3_partial_research_diagnostics",
            "claim_scope": (
                "Paired prompt comparison with some paper-derived diagnostics, but not the "
                "full research diagnostic stack."
            ),
            "claim_language": (
                "Recorded artifacts support a bounded diagnostic claim; avoid calling it a "
                "complete prompt-control analysis until the missing diagnostics are added."
            ),
            "next_tier_missing": _missing_for_sections(sections, research_sections),
        }

    if has_pairing:
        return {
            "evidence_tier": "tier_2_paired_comparison",
            "claim_scope": (
                "Paired baseline/candidate output comparison with statistical and "
                "prompt-only-validity evidence."
            ),
            "claim_language": (
                "Recorded artifacts support a paired comparison claim only; they do not yet "
                "support soft-hard, hidden-state, Riccati, or time-varying diagnostic claims."
            ),
            "next_tier_missing": _missing_for_sections(sections, research_sections),
        }

    return {
        "evidence_tier": "tier_1_incomplete_comparison",
        "claim_scope": "Partial score or artifact review without a clean paired comparison.",
        "claim_language": (
            "Use this as an audit trail, not as evidence that the candidate prompt improved."
        ),
        "next_tier_missing": _missing_for_sections(
            sections,
            ["statistical_evidence", "comparison_validity"],
        ),
    }


def _missing_for_sections(sections: dict[str, JsonDict], names: list[str]) -> list[str]:
    return [name for name in names if sections[name].get("status") == "missing"]


def _summary(
    recommendation: str,
    sections: dict[str, JsonDict],
    missing: list[str],
    tier: JsonDict,
) -> str:
    if recommendation == "supported":
        if tier.get("evidence_tier") != "tier_4_full_research_diagnostics":
            return (
                "Recorded artifacts support the candidate within a bounded scope: "
                f"{tier.get('claim_scope')}"
            )
        return (
            "Recorded artifacts support the candidate under the configured prompt optimization "
            "evidence checks."
        )
    if recommendation == "not_supported":
        return "One or more recorded artifacts contradict clean support for the candidate."
    if recommendation == "insufficient_evidence":
        return "Too many core artifacts are missing to evaluate the prompt change."
    if missing:
        return (
            "Evidence is useful but incomplete; review missing artifacts before claiming support."
        )
    review_count = sum(1 for section in sections.values() if section.get("status") == "review")
    return f"Evidence needs review; {review_count} section(s) are uncertain."


def _section(value: dict[str, object], key: str) -> JsonDict:
    section = value.get(key)
    return section if isinstance(section, dict) else {}


def _section_lines(section: JsonDict) -> list[str]:
    if not section:
        return ["- Status: `missing`"]
    return [f"- {_title(key)}: `{_format_value(value)}`" for key, value in section.items()]


def _title(value: str) -> str:
    return value.replace("_", " ").capitalize()


def _format_value(value: object) -> str:
    if isinstance(value, (dict, list)):
        import json

        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _ci_lower(value: list[object] | None) -> float | None:
    if not value:
        return None
    first = value[0]
    return float(first) if isinstance(first, int | float) else None


def _best_delta_method(deltas: JsonDict) -> str | None:
    best_method: str | None = None
    best_value: float | None = None
    for method, raw_value in deltas.items():
        if not isinstance(raw_value, int | float):
            continue
        value = float(raw_value)
        if best_value is None or value > best_value:
            best_method = str(method)
            best_value = value
    return best_method
