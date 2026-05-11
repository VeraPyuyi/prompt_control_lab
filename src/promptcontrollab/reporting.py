"""Human-readable report generation."""

from __future__ import annotations

import html
from pathlib import Path

from promptcontrollab.files import JsonDict, read_json


def generate_report(run_dir: Path, *, title: str) -> tuple[Path, Path]:
    """Generate Markdown and HTML reports for a run directory."""

    manifest = _read_optional_json(run_dir / "manifest.json")
    metrics = _read_optional_json(run_dir / "metrics.json")
    if not metrics:
        metrics = _read_optional_json(run_dir / "candidate" / "metrics.json")
    stats = _read_optional_json(run_dir / "stats.json")
    splits = _read_optional_json(run_dir / "splits.json")
    explanation = _read_optional_json(run_dir / "explanation.json")
    gate = _read_optional_json(run_dir / "gate_result.json")
    diagnostics = _collect_diagnostics(run_dir / "diagnostics")
    markdown = render_markdown(
        title=title,
        manifest=manifest,
        metrics=metrics,
        stats=stats,
        splits=splits,
        explanation=explanation,
        gate=gate,
        diagnostics=diagnostics,
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
    diagnostics: dict[str, JsonDict],
) -> str:
    """Render a compact diagnostic report."""

    lines: list[str] = [f"# {title}", ""]
    lines += _deployment_recommendation_lines(explanation, gate)
    if manifest:
        lines += [
            "## Run",
            "",
            f"- Method: `{manifest.get('method', 'unknown')}`",
            f"- Metric: `{manifest.get('metric', 'unknown')}`",
            f"- Tool version: `{manifest.get('tool_version', 'unknown')}`",
            "",
        ]
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
        if isinstance(comparisons, list):
            for comparison in comparisons:
                if isinstance(comparison, dict):
                    lines += [
                        f"- Mean delta: `{comparison.get('mean_delta')}`",
                        f"- Bootstrap CI: `{comparison.get('bootstrap_ci')}`",
                        f"- Permutation p-value: `{comparison.get('permutation_p_value')}`",
                        f"- Holm-adjusted p-value: `{comparison.get('holm_adjusted_p_value')}`",
                        f"- Interpretation: `{comparison.get('interpretation')}`",
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
    card = _html_recommendation_card(markdown)
    sample_changes = _html_sample_changes(markdown)
    return (
        "<!doctype html>\n"
        "<html><head><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:920px;margin:40px auto;"
        "line-height:1.55;padding:0 20px}pre{background:#f6f8fa;padding:16px;"
        "overflow:auto}code{background:#f6f8fa;padding:2px 4px}"
        ".recommendation-card{border-radius:10px;padding:16px 18px;margin:18px 0;"
        "border:1px solid #cbd5e1}.recommendation-card.green{background:#f0fdf4;"
        "border-color:#86efac}.recommendation-card.yellow{background:#fefce8;"
        "border-color:#fde047}.recommendation-card.red{background:#fef2f2;"
        "border-color:#fca5a5}.recommendation-card h2{margin:0 0 8px}"
        "table{border-collapse:collapse;width:100%;margin:12px 0 22px}"
        "td,th{border:1px solid #e2e8f0;padding:8px;text-align:left}"
        "th{background:#f8fafc}</style>"
        "</head><body>"
        f"{card}"
        f"{sample_changes}"
        f"<pre>{escaped}</pre>"
        "</body></html>\n"
    )


def _read_optional_json(path: Path) -> JsonDict:
    if not path.exists():
        return {}
    return read_json(path)


def _collect_diagnostics(path: Path) -> dict[str, JsonDict]:
    if not path.exists():
        return {}
    diagnostics: dict[str, JsonDict] = {}
    for item in sorted(path.glob("*.json")):
        diagnostics[item.stem] = read_json(item)
    return diagnostics


def _pretty(value: JsonDict) -> str:
    import json

    return json.dumps(value, indent=2, sort_keys=True)


def _get(value: object, key: str) -> object:
    if isinstance(value, dict):
        return value.get(key, "missing")
    return "missing"


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
    prefix = f"- {label}:"
    for line in markdown.splitlines():
        if line.startswith(prefix):
            value = line[len(prefix) :].strip()
            if value.startswith("`") and value.endswith("`"):
                value = value[1:-1]
            return value
    return None
