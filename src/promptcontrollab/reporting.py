"""Human-readable report generation."""

from __future__ import annotations

import html
from pathlib import Path

from promptcontrollab.files import JsonDict
from promptcontrollab.report_model import ReportModel


def generate_report(run_dir: Path, *, title: str) -> tuple[Path, Path]:
    """Generate Markdown and HTML reports for a run directory."""

    model = ReportModel.from_run(run_dir)
    markdown = render_markdown(
        title=title,
        manifest=model.manifest,
        metrics=model.metrics,
        stats=model.stats,
        splits=model.splits,
        explanation=model.explanation,
        gate=model.gate,
        comparison_validity=model.comparison_validity,
        diagnostics=model.diagnostics,
        evidence_card=model.evidence_card,
        claim_check=model.claim_check,
        first_comparison=model.first_comparison,
    )
    md_path = run_dir / "report.md"
    html_path = run_dir / "report.html"
    md_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(render_html(markdown, title=title), encoding="utf-8")
    return md_path, html_path


def render_markdown(
    *,
    title: str,
    manifest: JsonDict,
    metrics: JsonDict,
    stats: JsonDict,
    splits: JsonDict,
    explanation: JsonDict,
    gate: JsonDict,
    comparison_validity: JsonDict,
    diagnostics: dict[str, JsonDict],
    evidence_card: JsonDict | None = None,
    claim_check: JsonDict | None = None,
    first_comparison: JsonDict | None = None,
) -> str:
    """Render a compact diagnostic report."""

    lines: list[str] = [f"# {title}", ""]
    lines += _deployment_recommendation_lines(explanation, gate)
    if evidence_card:
        lines += _evidence_card_lines(evidence_card)
    if claim_check:
        lines += _claim_check_lines(claim_check)
    if manifest:
        lines += [
            "## Run",
            "",
            f"- Method: `{manifest.get('method', 'unknown')}`",
            f"- Metric: `{manifest.get('metric', 'unknown')}`",
            f"- Tool version: `{manifest.get('tool_version', 'unknown')}`",
        ]
        lines += _model_identity_lines(manifest)
        lines.append("")
    if splits:
        leakage = splits.get("leakage", {})
        has_leakage = (
            leakage.get("has_leakage", "unknown") if isinstance(leakage, dict) else "unknown"
        )
        lines += [
            "## Split Hygiene",
            "",
            f"- Split hash: `{splits.get('split_hash', 'missing')}`",
            f"- Counts: `{splits.get('counts', {})}`",
            f"- Leakage detected: `{has_leakage}`",
            "",
            "This section explains whether train, validation, and withheld examples were "
            "kept apart.",
            "",
        ]
    if explanation:
        summary = explanation.get("overall_summary", {})
        hygiene = explanation.get("data_hygiene", {})
        examples = explanation.get("example_changes", {})
        next_action = explanation.get("next_action", {})
        lines += [
            "## Quick Mode Explanation",
            "",
            f"- Verdict: `{_get(summary, 'verdict')}`",
            f"- Mean delta: `{_get(summary, 'mean_delta')}`",
            f"- What this means: {_get(summary, 'what_this_means')}",
            f"- Data leakage detected: `{_get(hygiene, 'has_leakage')}`",
            f"- Fixed examples: `{_get(examples, 'fixed_ids')}`",
            f"- Broken examples: `{_get(examples, 'broken_ids')}`",
            f"- Next action: `{_get(next_action, 'recommendation')}`",
            "",
            "This section turns the raw artifacts into a direct explanation for readers who "
            "do not want to inspect every JSON file first.",
            "",
        ]
    if gate:
        lines += [
            "## Gate Result",
            "",
            f"- Status: `{gate.get('status', 'unknown')}`",
            f"- Meaning: {gate.get('what_this_means', '')}",
            "",
            "This section explains whether the run passed the configured policy thresholds.",
            "",
        ]
    if comparison_validity:
        lines += _comparison_validity_lines(comparison_validity)
    if metrics:
        lines += [
            "## Metrics",
            "",
            f"- Count: `{metrics.get('count', 0)}`",
            f"- Mean score: `{metrics.get('mean_score', 0.0)}`",
            f"- Slice scores: `{metrics.get('by_slice', {})}`",
            "",
            "This section shows how the prompt performed overall and by task slice.",
            "",
        ]
    if stats:
        lines += ["## Statistical Comparison", ""]
        comparisons = stats.get("comparisons", [])
        rendered = False
        if isinstance(comparisons, list):
            for comparison in comparisons:
                if isinstance(comparison, dict):
                    rendered = True
                    lines += [
                        f"- Mean delta: `{comparison.get('mean_delta')}`",
                        f"- Bootstrap CI: `{comparison.get('bootstrap_ci')}`",
                        f"- Permutation p-value: `{comparison.get('permutation_p_value')}`",
                        f"- Holm-adjusted p-value: `{comparison.get('holm_adjusted_p_value')}`",
                        f"- Interpretation: `{comparison.get('interpretation')}`",
                    ]
        if not rendered and first_comparison:
            lines += [
                f"- Mean delta: `{first_comparison.get('mean_delta')}`",
                f"- Bootstrap CI: `{first_comparison.get('bootstrap_ci')}`",
                f"- Permutation p-value: `{first_comparison.get('permutation_p_value')}`",
                f"- Holm-adjusted p-value: `{first_comparison.get('holm_adjusted_p_value')}`",
                f"- Interpretation: `{first_comparison.get('interpretation')}`",
            ]
        lines += [
            "",
            "This section explains whether the observed change is reliable or still uncertain.",
            "",
        ]
    if diagnostics:
        lines += ["## Diagnostics", ""]
        for name, payload in sorted(diagnostics.items()):
            lines += [f"### {name}", "", f"```json\n{_pretty(payload)}\n```", ""]
        lines += [
            "Diagnostics explain deployment risk, trajectory drift, surrogate stability, or "
            "time-varying control behavior depending on which commands were run.",
            "",
        ]
    lines += [
        "## What To Check Next",
        "",
        "- If the withheld score regressed, inspect the affected task slices before keeping "
        "the prompt.",
        "- If the confidence interval crosses zero, treat the apparent change as uncertain.",
        "- If soft-hard or trajectory diagnostics are high risk, inspect deployment assumptions.",
        "",
    ]
    return "\n".join(lines)


def render_html(markdown: str, *, title: str) -> str:
    """Render a dependency-free HTML wrapper around the Markdown text."""

    escaped = html.escape(markdown)
    dashboard = _html_dashboard(markdown)
    return (
        "<!doctype html>\n"
        "<html><head><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:920px;margin:40px auto;"
        "line-height:1.55;padding:0 20px;background:#f8fafc;color:#0f172a}"
        "pre{background:#0f172a;color:#e2e8f0;padding:16px;overflow:auto;"
        "border-radius:8px}code{background:#e2e8f0;padding:2px 4px;border-radius:4px}"
        ".dashboard{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));"
        "gap:14px;margin:18px 0 26px}.dashboard-card{background:white;border:1px solid "
        "#e2e8f0;border-radius:8px;padding:14px 16px;box-shadow:0 1px 2px #0000000d}"
        ".dashboard-card h2{font-size:16px;margin:0 0 8px}.dashboard-card p{margin:6px 0}"
        ".recommendation-card{border-radius:10px;padding:16px 18px;margin:18px 0;"
        "border:1px solid #cbd5e1}.recommendation-card.green{background:#f0fdf4;"
        "border-color:#86efac}.recommendation-card.yellow{background:#fefce8;"
        "border-color:#fde047}.recommendation-card.red{background:#fef2f2;"
        "border-color:#fca5a5}.recommendation-card h2{margin:0 0 8px}"
        "table{border-collapse:collapse;width:100%;margin:12px 0 22px}"
        "td,th{border:1px solid #e2e8f0;padding:8px;text-align:left}"
        "th{background:#f8fafc}</style>"
        "</head><body>"
        f"<h1>{html.escape(title)}</h1>"
        f"{dashboard}"
        "<h2>Full Markdown Audit</h2>"
        f"<pre>{escaped}</pre>"
        "</body></html>\n"
    )


def _pretty(value: JsonDict) -> str:
    import json

    return json.dumps(value, indent=2, sort_keys=True)


def _get(value: object, key: str) -> object:
    if isinstance(value, dict):
        return value.get(key, "missing")
    return "missing"


def _model_identity_lines(manifest: JsonDict) -> list[str]:
    lines: list[str] = []
    model = manifest.get("model")
    if isinstance(model, dict):
        lines.append(f"- Model: `{_model_label(model)}`")
        lines.append(f"- Model source: `{model.get('source', 'unknown')}`")
        lines.append(f"- Model verified: `{model.get('verified', False)}`")
        lines.append(f"- Provenance level: `{model.get('provenance_level', 'unknown')}`")

    baseline = manifest.get("baseline_model")
    candidate = manifest.get("candidate_model")
    if isinstance(baseline, dict) or isinstance(candidate, dict):
        baseline_dict = baseline if isinstance(baseline, dict) else {}
        candidate_dict = candidate if isinstance(candidate, dict) else {}
        lines.append(f"- Baseline model: `{_model_label(baseline_dict)}`")
        lines.append(f"- Candidate model: `{_model_label(candidate_dict)}`")
        lines.append(
            f"- Baseline provenance level: `{baseline_dict.get('provenance_level', 'unknown')}`"
        )
        lines.append(
            f"- Candidate provenance level: `{candidate_dict.get('provenance_level', 'unknown')}`"
        )

    warnings = manifest.get("model_warnings", [])
    if isinstance(warnings, list):
        for warning in warnings:
            lines.append(f"- Model warning: {warning}")
    if lines:
        lines.append(
            "- Model identity records the public model id in request/response artifacts; "
            "it does not prove a provider's hidden internal weight build."
        )
    return lines


def _comparison_validity_lines(payload: JsonDict) -> list[str]:
    lines = [
        "## Comparison Validity",
        "",
        f"- Validity: `{payload.get('validity', 'unknown')}`",
        f"- Prompt-only comparison: `{payload.get('prompt_only_comparison', 'unknown')}`",
        f"- Summary: {payload.get('plain_summary', '')}",
    ]
    lines += _issue_lines("Blocking issue", payload.get("blocking_issues"))
    lines += _issue_lines("Review item", payload.get("review_items"))
    lines += [
        "",
        "This section explains whether a baseline/candidate result can be interpreted "
        "as clean prompt-only evidence, or whether model, split, metric, prompt identity, "
        "or statistical evidence needs review.",
        "",
    ]
    return lines


def _evidence_card_lines(payload: JsonDict) -> list[str]:
    sections = payload.get("sections")
    section_statuses: list[str] = []
    if isinstance(sections, dict):
        for name, section in sorted(sections.items()):
            if isinstance(section, dict):
                section_statuses.append(f"{name}={section.get('status', 'unknown')}")
    missing = payload.get("missing_artifacts")
    return [
        "## Prompt Optimization Evidence Card",
        "",
        f"- Evidence recommendation: `{payload.get('recommendation', 'needs_review')}`",
        f"- Evidence tier: `{payload.get('evidence_tier', 'unknown')}`",
        f"- Claim scope: {payload.get('claim_scope', '')}",
        f"- Safe claim language: {payload.get('claim_language', '')}",
        f"- Evidence summary: {payload.get('summary', '')}",
        f"- Next tier missing: `{payload.get('next_tier_missing', [])}`",
        f"- Missing evidence: `{missing if isinstance(missing, list) else []}`",
        f"- Section statuses: `{', '.join(section_statuses)}`",
        "",
        "This section summarizes whether the recorded artifact bundle supports a prompt "
        "optimization claim across protocol hygiene, paired statistics, comparison validity, "
        "deployment risk, trajectory diagnostics, Riccati surrogate checks, and time-varying "
        "control evidence.",
        "",
    ]


def _claim_check_lines(payload: JsonDict) -> list[str]:
    return [
        "## Prompt Optimization Claim Check",
        "",
        f"- Requested claim: `{payload.get('requested_claim', '')}`",
        f"- Status: `{payload.get('status', 'needs_review')}`",
        f"- Evidence tier: `{payload.get('evidence_tier', 'unknown')}`",
        f"- Reason: {payload.get('reason', '')}",
        f"- Safe claim: {payload.get('safe_claim', '')}",
        f"- Next tier missing: `{payload.get('next_tier_missing', [])}`",
        "",
        "This section states what the current evidence tier can safely support. It is "
        "intended to prevent a paired eval result from being overstated as a full "
        "paper-derived prompt-control diagnostic claim.",
        "",
    ]


def _issue_lines(label: str, value: object) -> list[str]:
    if not isinstance(value, list) or not value:
        return []
    return [f"- {label}: {item}" for item in value]


def _model_label(model: JsonDict) -> str:
    provider = model.get("provider", "unknown")
    model_id = model.get("model_id", "unknown")
    return f"{provider}/{model_id}"


def _deployment_recommendation_lines(explanation: JsonDict, gate: JsonDict) -> list[str]:
    card = _deployment_card(explanation, gate)
    return [
        "## Deployment Recommendation",
        "",
        f"- Recommendation: `{card['recommendation']}`",
        f"- Status source: `{card['source']}`",
        f"- Risk color: `{card['color']}`",
        f"- Why: {card['reason']}",
        "",
        "This is the first-pass release decision. Use it as a prompt change gate: deploy, "
        "hold, or send to a human reviewer.",
        "",
    ]


def _deployment_card(explanation: JsonDict, gate: JsonDict) -> JsonDict:
    if gate:
        status = str(gate.get("status", "needs_review"))
        if status == "pass":
            return {
                "recommendation": "yes",
                "source": "gate_result.json",
                "color": "green",
                "reason": gate.get("plain_summary", gate.get("what_this_means", "")),
            }
        if status == "fail":
            return {
                "recommendation": "no",
                "source": "gate_result.json",
                "color": "red",
                "reason": gate.get("plain_summary", gate.get("what_this_means", "")),
            }
        return {
            "recommendation": "needs_review",
            "source": "gate_result.json",
            "color": "yellow",
            "reason": gate.get("plain_summary", gate.get("what_this_means", "")),
        }

    recommendation = explanation.get("deployment_recommendation", {})
    if isinstance(recommendation, dict):
        return {
            "recommendation": recommendation.get("label", "needs_review"),
            "source": "explanation.json",
            "color": recommendation.get("color", "yellow"),
            "reason": recommendation.get(
                "reason",
                recommendation.get("what_this_means", "Review the prompt before deployment."),
            ),
        }
    return {
        "recommendation": "needs_review",
        "source": "missing_artifacts",
        "color": "yellow",
        "reason": "No explanation or gate result is available yet.",
    }


def _html_recommendation_card(markdown: str) -> str:
    recommendation = _markdown_field(markdown, "Recommendation") or "needs_review"
    color = _markdown_field(markdown, "Risk color") or "yellow"
    reason = _markdown_field(markdown, "Why") or "Review the generated artifacts."
    safe_color = color if color in {"green", "yellow", "red"} else "yellow"
    return (
        f"<section class='recommendation-card {safe_color}'>"
        "<h2>Deployment Recommendation</h2>"
        f"<p><strong>{html.escape(recommendation)}</strong></p>"
        f"<p>{html.escape(reason)}</p>"
        "</section>"
    )


def _html_dashboard(markdown: str) -> str:
    baseline_model = html.escape(_markdown_field(markdown, "Baseline model") or "unknown")
    candidate_model = html.escape(_markdown_field(markdown, "Candidate model") or "unknown")
    verified = html.escape(_markdown_field(markdown, "Model verified") or "see manifest")
    count = html.escape(_markdown_field(markdown, "Count") or "missing")
    mean_score = html.escape(_markdown_field(markdown, "Mean score") or "missing")
    slice_scores = html.escape(_markdown_field(markdown, "Slice scores") or "missing")
    gate_status = html.escape(_markdown_field(markdown, "Status") or "missing")
    gate_meaning = html.escape(_markdown_field(markdown, "Meaning") or "No gate result found.")
    return (
        _html_recommendation_card(markdown)
        + "<section class='dashboard'>"
        + _html_dashboard_card(
            "Prompt-only comparison validity",
            _prompt_only_validity(markdown),
        )
        + _html_dashboard_card(
            "Prompt optimization evidence",
            _prompt_evidence_summary(markdown),
        )
        + _html_dashboard_card(
            "Model provenance",
            "<br>".join(
                [
                    f"Baseline: {baseline_model}",
                    f"Candidate: {candidate_model}",
                    f"Verified: {verified}",
                ]
            ),
        )
        + _html_dashboard_card(
            "Metrics summary",
            "<br>".join(
                [
                    f"Count: {count}",
                    f"Mean score: {mean_score}",
                    f"Slices: {slice_scores}",
                ]
            ),
        )
        + _html_dashboard_card(
            "Gate failures/review items",
            "<br>".join([f"Status: {gate_status}", f"Meaning: {gate_meaning}"]),
        )
        + _html_dashboard_card(
            "Actionable next steps",
            "Check model warnings, slice regressions, statistical uncertainty, and gate failures.",
        )
        + "</section>"
        + _html_sample_changes(markdown)
    )


def _html_dashboard_card(title: str, body: str) -> str:
    return (
        "<article class='dashboard-card'>"
        f"<h2>{html.escape(title)}</h2>"
        f"<p>{body}</p>"
        "</article>"
    )


def _prompt_only_validity(markdown: str) -> str:
    explicit = _markdown_field(markdown, "Validity")
    prompt_only = _markdown_field(markdown, "Prompt-only comparison")
    if explicit:
        return f"{explicit}; prompt-only={prompt_only or 'unknown'}."
    warnings = _markdown_fields(markdown, "Model warning")
    if any("not a clean prompt-only comparison" in warning for warning in warnings):
        return "Needs review: baseline and candidate model ids differ."
    if any("missing model identity" in warning for warning in warnings):
        return "Needs review: model identity is missing."
    return "Clean if baseline and candidate model ids match."


def _prompt_evidence_summary(markdown: str) -> str:
    recommendation = _markdown_field(markdown, "Evidence recommendation") or "missing"
    tier = _markdown_field(markdown, "Evidence tier") or "unknown"
    scope = _markdown_field(markdown, "Claim scope") or "unknown"
    summary = _markdown_field(markdown, "Evidence summary") or "Run `pcl evidence-card`."
    missing = _markdown_field(markdown, "Missing evidence") or "unknown"
    return (
        f"Recommendation: {html.escape(recommendation)}<br>"
        f"Tier: {html.escape(tier)}<br>"
        f"Scope: {html.escape(scope)}<br>"
        f"Summary: {html.escape(summary)}<br>"
        f"Missing: {html.escape(missing)}"
    )


def _html_sample_changes(markdown: str) -> str:
    fixed = _markdown_field(markdown, "Fixed examples") or "[]"
    broken = _markdown_field(markdown, "Broken examples") or "[]"
    return (
        "<section>"
        "<h2>Sample changes</h2>"
        "<table>"
        "<tr><th>Type</th><th>Example ids</th></tr>"
        f"<tr><td>Fixed</td><td>{html.escape(fixed)}</td></tr>"
        f"<tr><td>Broken</td><td>{html.escape(broken)}</td></tr>"
        "</table>"
        "</section>"
    )


def _markdown_field(markdown: str, label: str) -> str | None:
    values = _markdown_fields(markdown, label)
    return values[0] if values else None


def _markdown_fields(markdown: str, label: str) -> list[str]:
    prefix = f"- {label}:"
    values: list[str] = []
    for line in markdown.splitlines():
        if line.startswith(prefix):
            value = line[len(prefix) :].strip()
            if value.startswith("`") and value.endswith("`"):
                value = value[1:-1]
            values.append(value)
    return values
