"""Prompt optimization evidence-card generation."""

from __future__ import annotations

import html
from collections.abc import Sequence
from pathlib import Path

from promptcontrollab.core.files import JsonDict, ensure_dir, write_json
from promptcontrollab.evaluation.report_model import ReportModel


def build_evidence_card(run_dir: Path) -> JsonDict:
    """Build a compact evidence card from a PromptControlLab run directory."""

    model = ReportModel.from_run(run_dir)
    sections = {
        "protocol_hygiene": _protocol_hygiene(model),
        "statistical_evidence": _statistical_evidence(model),
        "comparison_validity": _comparison_validity(model),
        "prompt_optimizer_scaffold": _prompt_optimizer_scaffold(model),
        "deployment_diagnostics": _deployment_diagnostics(model),
        "paper_replication_evidence": _paper_replication_evidence(model),
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
    paper = sections["paper_replication_evidence"]
    if paper.get("status") != "skipped" and isinstance(paper.get("safe_claim"), str):
        tier["claim_language"] = paper["safe_claim"]
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
    resolved_html = resolved_markdown.with_suffix(".html")
    ensure_dir(resolved_json.parent)
    ensure_dir(resolved_markdown.parent)
    card["json_path"] = str(resolved_json)
    card["markdown_path"] = str(resolved_markdown)
    card["html_path"] = str(resolved_html)
    write_json(resolved_json, card)
    resolved_markdown.write_text(render_evidence_card_markdown(card), encoding="utf-8")
    resolved_html.write_text(render_evidence_card_html(card), encoding="utf-8")
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
        f"- Claim scope: {_markdown_text(card.get('claim_scope', ''))}",
        f"- Safe claim language: {_markdown_text(card.get('claim_language', ''))}",
        f"- Summary: {_markdown_text(card.get('summary', ''))}",
        f"- Next tier missing: `{card.get('next_tier_missing', [])}`",
        f"- Run directory: {_markdown_code(card.get('run_dir', ''))}",
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
        "## Prompt optimizer eval scaffold",
        "",
        *_section_lines(_section(sections_dict, "prompt_optimizer_scaffold")),
        "",
        "## Deployment diagnostics",
        "",
        *_section_lines(_section(sections_dict, "deployment_diagnostics")),
        "",
        "## Paper replication evidence",
        "",
        *_section_lines(_section(sections_dict, "paper_replication_evidence")),
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


def render_evidence_card_html(card: JsonDict) -> str:
    """Render a browser-readable evidence card."""

    sections = card.get("sections")
    sections_dict = sections if isinstance(sections, dict) else {}
    section_cards = "\n".join(
        _section_html(title=title, section=_section(sections_dict, key))
        for key, title in [
            ("protocol_hygiene", "Protocol hygiene"),
            ("statistical_evidence", "Statistical evidence"),
            ("comparison_validity", "Prompt-only comparison validity"),
            ("prompt_optimizer_scaffold", "Prompt optimizer eval scaffold"),
            ("deployment_diagnostics", "Deployment diagnostics"),
            ("paper_replication_evidence", "Paper replication evidence"),
            ("hidden_state_diagnostics", "Hidden-state diagnostics"),
            ("riccati_surrogate", "Riccati surrogate"),
            ("time_varying_control", "Time-varying soft-control"),
        ]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Prompt Optimization Evidence Card</title>
  <style>
    :root {{
      --bg: #f6f8fb;
      --panel: #ffffff;
      --ink: #18212f;
      --muted: #667085;
      --line: #d9e1ec;
      --blue: #2563eb;
      --green-bg: #eaf8ef;
      --green: #166534;
      --amber-bg: #fff7df;
      --amber: #92400e;
      --red-bg: #feecec;
      --red: #991b1b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 15px/1.55 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 40px 24px 56px; }}
    .hero {{
      background: linear-gradient(135deg, #ffffff 0%, #eef5ff 100%);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 28px;
      box-shadow: 0 14px 38px rgba(24, 33, 47, 0.08);
    }}
    h1 {{ margin: 0 0 10px; font-size: clamp(28px, 4vw, 44px); line-height: 1.05; }}
    h2 {{ margin: 0 0 12px; font-size: 18px; }}
    p {{ margin: 0; color: var(--muted); }}
    .meta {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
      margin-top: 22px;
    }}
    .card, .section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 16px;
    }}
    .label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; }}
    .value {{ margin-top: 6px; font-weight: 700; overflow-wrap: anywhere; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 14px;
      margin-top: 24px;
    }}
    table {{ width: 100%; border-collapse: collapse; }}
    td {{ border-top: 1px solid var(--line); padding: 8px 0; vertical-align: top; }}
    td:first-child {{ width: 42%; color: var(--muted); padding-right: 12px; }}
    code {{
      display: inline-block;
      max-width: 100%;
      overflow-wrap: anywhere;
      padding: 2px 6px;
      border-radius: 6px;
      background: #eef2f7;
      color: #26364d;
      font-size: 12px;
    }}
    .badge {{
      display: inline-flex;
      border-radius: 999px;
      padding: 3px 9px;
      font-size: 12px;
      font-weight: 700;
    }}
    .pass, .supported {{ background: var(--green-bg); color: var(--green); }}
    .review, .needs_review, .missing {{ background: var(--amber-bg); color: var(--amber); }}
    .fail, .not_supported, .insufficient_evidence {{
      background: var(--red-bg);
      color: var(--red);
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>Prompt Optimization Evidence Card</h1>
      <p>{_html_text(card.get("summary", ""))}</p>
      <div class="meta">
        {_meta_card("Recommendation", _badge(card.get("recommendation")))}
        {_meta_card("Evidence tier", _html_text(card.get("evidence_tier", "unknown")))}
        {_meta_card("Run directory", _html_text(card.get("run_dir", "")))}
      </div>
    </section>
    <section class="grid">
      {_claim_scope_html(card)}
      {section_cards}
    </section>
    <section class="section" style="margin-top: 24px;">
      <h2>Boundary</h2>
      <p>{_html_text(card.get("boundary", ""))}</p>
    </section>
  </main>
</body>
</html>
"""


def _claim_scope_html(card: JsonDict) -> str:
    missing = card.get("next_tier_missing")
    missing_text = ", ".join(str(item) for item in missing) if isinstance(missing, list) else ""
    rows = [
        ("Claim scope", card.get("claim_scope", "")),
        ("Safe claim language", card.get("claim_language", "")),
        ("Next tier missing", missing_text),
    ]
    return _table_section_html(title="Claim scope", rows=rows)


def _section_html(*, title: str, section: JsonDict) -> str:
    if not section:
        return _table_section_html(title=title, rows=[("Status", "missing")])
    return _table_section_html(title=title, rows=list(section.items()))


def _table_section_html(*, title: str, rows: Sequence[tuple[object, object]]) -> str:
    body = "\n".join(
        f"<tr><td>{_html_text(_title(str(key)))}</td><td>{_html_value(value)}</td></tr>"
        for key, value in rows
    )
    return f'<section class="section"><h2>{_html_text(title)}</h2><table>{body}</table></section>'


def _meta_card(label: str, value_html: str) -> str:
    return (
        '<div class="card">'
        f'<div class="label">{_html_text(label)}</div>'
        f'<div class="value">{value_html}</div>'
        "</div>"
    )


def _badge(value: object) -> str:
    text = str(value or "")
    css = text.replace("-", "_")
    return f'<span class="badge {html.escape(css, quote=True)}">{_html_text(text)}</span>'


def _html_value(value: object) -> str:
    return f"<code>{_html_text(_format_value(value))}</code>"


def _html_text(value: object) -> str:
    return html.escape(str(value or ""))


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


def _prompt_optimizer_scaffold(model: ReportModel) -> JsonDict:
    has_context = bool(
        model.prompt_assets
        or model.prompt_optimizer_gap_plan
        or (model.run_dir / "eval_scaffold").exists()
    )
    if not has_context:
        return {
            "status": "skipped",
            "reason": "No prompt-optimizer asset import or eval scaffold was recorded.",
        }
    payload = model.scaffold_check
    if not payload:
        return {
            "status": "review",
            "reason": "Prompt-optimizer eval scaffold exists but scaffold_check.json is missing.",
            "expected_artifact": "eval_scaffold/scaffold_check.json",
        }
    scaffold_status = str(payload.get("status") or "unknown")
    issues = payload.get("issues")
    issue_count = len(issues) if isinstance(issues, list) else 0
    if scaffold_status == "pass":
        status = "pass"
    elif scaffold_status == "fail":
        status = "fail"
    else:
        status = "review"
    return {
        "status": status,
        "scaffold_status": scaffold_status,
        "issue_count": issue_count,
        "task_count": payload.get("task_count"),
        "baseline_prediction_count": payload.get("baseline_prediction_count"),
        "candidate_prediction_count": payload.get("candidate_prediction_count"),
        "prompt_file_count": payload.get("prompt_file_count"),
        "reason": (
            "Scaffold is ready for paired scoring."
            if scaffold_status == "pass"
            else "Scaffold must be completed before treating prompt assets as scored evidence."
        ),
    }


def _paper_replication_evidence(model: ReportModel) -> JsonDict:
    """Summarize bounded PEOC replication evidence for the evidence card."""

    if not model.peoc_evidence and "peoc_evidence.json" not in model.artifacts:
        return {
            "status": "skipped",
            "origin": "none",
            "reason": "No peoc_evidence.json artifact found; paper replication review was skipped.",
        }

    raw_sections = model.peoc_evidence.get("sections")
    evidence_sections = raw_sections if isinstance(raw_sections, dict) else {}
    section_names = [
        "hard_evaluation",
        "riccati",
        "soft_evaluation",
        "soft_hard",
        "stage_heterogeneity",
        "trajectory",
    ]
    allowed_statuses = {
        "available",
        "failed_validation",
        "missing",
        "partial",
        "unusable",
    }
    section_statuses: JsonDict = {}
    for name in section_names:
        section = evidence_sections.get(name)
        section_dict = section if isinstance(section, dict) else {}
        raw_status = str(section_dict.get("status") or "missing")
        section_statuses[name] = raw_status if raw_status in allowed_statuses else "unusable"

    counts = {
        status: sum(1 for value in section_statuses.values() if value == status)
        for status in [
            "available",
            "partial",
            "unusable",
            "failed_validation",
            "missing",
        ]
    }
    boundary_value = model.peoc_evidence.get("claim_boundary")
    boundary = boundary_value if isinstance(boundary_value, dict) else {}
    if not boundary:
        case_boundary = model.peoc_case_study.get("claim_boundary")
        boundary = case_boundary if isinstance(case_boundary, dict) else {}
    declared_full_support = boundary.get("full_research_support") is True
    all_sections_available = all(section_statuses[name] == "available" for name in section_names)
    full_support = declared_full_support and all_sections_available
    failed_validation_count = counts["failed_validation"]
    if failed_validation_count:
        status = "not_supported"
        reason = (
            f"The imported PEOC evidence contains {failed_validation_count} failed validation "
            "section(s). Failed validation is negative evidence and cannot be treated as a pass."
        )
    elif declared_full_support and not all_sections_available:
        status = "review"
        reason = (
            "The imported PEOC claim boundary declares full research support, but one or more "
            "required sections are not available; PromptControlLab therefore fails closed."
        )
    elif not full_support:
        status = "review"
        reason = (
            "The imported PEOC claim boundary does not support the complete research capability "
            "set; missing, partial, or unusable sections require review."
        )
    else:
        status = "review"
        reason = (
            "The real PEOC bundle is imported aggregate evidence and requires reviewer "
            "interpretation within its recorded tasks, models, seeds, and protocol."
        )

    return {
        "status": status,
        "origin": "real",
        "input_source": "peoc_nmi_replication_bundle",
        "available_count": counts["available"],
        "partial_count": counts["partial"],
        "unusable_count": counts["unusable"],
        "failed_validation_count": failed_validation_count,
        "missing_count": counts["missing"],
        "status_counts": counts,
        "section_statuses": section_statuses,
        "full_research_support": full_support,
        "safe_claim": _peoc_safe_claim(
            case_study=model.peoc_case_study,
            boundary=boundary,
            full_support=full_support,
        ),
        "reason": reason,
        "claim_boundary": _public_import_value(boundary),
    }


def _hidden_state_diagnostics(model: ReportModel) -> JsonDict:
    trajectory = model.diagnostics.get("trajectory", {})
    research = model.research_diagnostics
    inputs = research.get("inputs") if isinstance(research, dict) else {}
    input_payload = inputs.get("hidden_states") if isinstance(inputs, dict) else {}
    input_dict = input_payload if isinstance(input_payload, dict) else {}
    if not trajectory and not input_dict:
        imported = _peoc_trajectory_summary(model)
        if imported:
            return imported
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
        imported = _peoc_hard_method_summary(model)
        if imported:
            return imported
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


def _peoc_trajectory_summary(model: ReportModel) -> JsonDict:
    sections_value = model.peoc_evidence.get("sections")
    sections = sections_value if isinstance(sections_value, dict) else {}
    trajectory_value = sections.get("trajectory")
    trajectory = trajectory_value if isinstance(trajectory_value, dict) else {}
    source_status = str(trajectory.get("status") or "missing")
    if source_status == "missing":
        return {}

    selected_value = model.peoc_case_study.get("selected_trajectory_pair")
    selected_pair = selected_value if isinstance(selected_value, dict) else {}
    if not selected_pair:
        observations_value = trajectory.get("observations")
        observations = observations_value if isinstance(observations_value, dict) else {}
        headline_value = observations.get("headline_pair")
        selected_pair = headline_value if isinstance(headline_value, dict) else {}
    if not selected_pair and source_status not in {"partial", "unusable"}:
        return {}
    return {
        "status": "review",
        "input_source": "peoc_nmi_replication_bundle",
        "evidence_kind": "imported_trajectory_summary",
        "source_status": source_status,
        "selected_pair": _public_import_value(selected_pair),
        "reason": (
            "This is an imported PEOC trajectory summary, not a fresh PromptControlLab "
            "operational-fit diagnostic; it cannot receive pass status."
        ),
    }


def _peoc_hard_method_summary(model: ReportModel) -> JsonDict:
    if not model.peoc_evidence:
        return {}
    sections_value = model.peoc_evidence.get("sections")
    sections = sections_value if isinstance(sections_value, dict) else {}
    hard_value = sections.get("hard_evaluation")
    hard = hard_value if isinstance(hard_value, dict) else {}
    if not hard or str(hard.get("status") or "missing") == "missing":
        return {}
    observations_value = hard.get("observations")
    observations = observations_value if isinstance(observations_value, dict) else {}
    summary_value = model.peoc_case_study.get("hard_summary")
    summary = summary_value if isinstance(summary_value, dict) else {}
    methods_value = summary.get("methods", observations.get("methods"))
    methods = [str(method) for method in methods_value] if isinstance(methods_value, list) else []
    rows_value = model.peoc_case_study.get("hard_method_rows", observations.get("rows"))
    rows = rows_value if isinstance(rows_value, list) else []
    if not methods:
        methods = sorted(
            {str(row.get("method")) for row in rows if isinstance(row, dict) and row.get("method")}
        )
    if not methods and not rows:
        return {}
    return {
        "status": "review",
        "input_source": "peoc_nmi_replication_bundle",
        "evidence_kind": "aggregate_summary",
        "source_status": hard.get("status"),
        "methods": methods,
        "method_rows": _public_import_value(rows),
        "reason": (
            "Imported hard-evaluation aggregates are task-, model-, method-, and "
            "protocol-specific; no universally best time-varying method is inferred."
        ),
    }


def _peoc_safe_claim(
    *,
    case_study: JsonDict,
    boundary: JsonDict,
    full_support: bool,
) -> str:
    case_value = case_study.get("safe_claim")
    case_claim = case_value.strip() if isinstance(case_value, str) else ""
    if case_claim:
        if full_support or _is_fail_closed_claim(case_claim):
            return case_claim
        return _bounded_peoc_claim()
    statement_value = boundary.get("statement")
    statement = statement_value.strip() if isinstance(statement_value, str) else ""
    if statement and (full_support or _is_fail_closed_claim(statement)):
        return statement
    if full_support:
        return (
            "The imported PEOC evidence is bounded to its recorded tasks, models, seeds, "
            "and protocol; reviewer interpretation is still required."
        )
    return _bounded_peoc_claim()


def _bounded_peoc_claim() -> str:
    return (
        "The imported real PEOC evidence supports only task-, model-, seed-, and "
        "protocol-bounded findings; it does not support a complete research claim."
    )


def _is_fail_closed_claim(value: str) -> bool:
    normalized = " ".join(value.lower().split())
    explicit_negative = any(
        phrase in normalized
        for phrase in [
            "cannot support",
            "does not support",
            "not a proof",
            "not support",
        ]
    )
    return not _sounds_like_full_support(normalized) and (
        explicit_negative or "bounded" in normalized
    )


def _sounds_like_full_support(value: str) -> bool:
    normalized = " ".join(value.lower().split())
    return any(
        phrase in normalized
        for phrase in [
            "all research claims",
            "complete research capability",
            "every research claim",
            "fully support",
            "full support",
            "full research support",
            "supports the complete research",
            "supports complete research",
        ]
    )


def _public_import_value(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): _public_import_value(item)
            for key, item in value.items()
            if str(key) not in {"resolved_path", "bundle_root", "source_path"}
        }
    if isinstance(value, list):
        return [_public_import_value(item) for item in value]
    return value


def _recommendation(sections: dict[str, JsonDict]) -> str:
    paper = sections["paper_replication_evidence"]
    legacy_sections = [
        section for name, section in sections.items() if name != "paper_replication_evidence"
    ]
    statuses = [section.get("status") for section in legacy_sections]
    validity = sections["comparison_validity"].get("status")
    if "fail" in statuses or validity == "invalid":
        return "not_supported"
    if paper.get("status") == "not_supported":
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
    recommendation = "supported" if all(required) else "needs_review"
    if (
        recommendation == "supported"
        and paper.get("status") != "skipped"
        and paper.get("full_research_support") is not True
    ):
        return "needs_review"
    return recommendation


def _evidence_tier(sections: dict[str, JsonDict], recommendation: str) -> JsonDict:
    """Classify the strongest claim supported by the assembled evidence sections."""

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
    paper = sections["paper_replication_evidence"]
    peoc_full_support_blocked = (
        paper.get("status") != "skipped" and paper.get("full_research_support") is not True
    )
    research_sections = [
        "protocol_hygiene",
        "deployment_diagnostics",
        "hidden_state_diagnostics",
        "riccati_surrogate",
        "time_varying_control",
    ]

    if (
        has_pairing
        and has_protocol
        and has_deployment
        and has_hidden
        and has_riccati
        and has_tv
        and not peoc_full_support_blocked
    ):
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
        next_tier_missing = _missing_for_sections(sections, research_sections)
        if peoc_full_support_blocked:
            next_tier_missing.append("paper_replication_evidence")
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
            "next_tier_missing": next_tier_missing,
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
    return [f"- {_title(key)}: {_markdown_code(value)}" for key, value in section.items()]


def _title(value: str) -> str:
    return value.replace("_", " ").capitalize()


def _format_value(value: object) -> str:
    if isinstance(value, (dict, list)):
        import json

        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _markdown_text(value: object) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ")
    return html.escape(text, quote=False).replace("`", "&#96;")


def _markdown_code(value: object) -> str:
    return f"`{_markdown_text(_format_value(value))}`"


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
