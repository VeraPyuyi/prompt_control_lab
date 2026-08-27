"""Markdown and HTML renderers for post-training gate decisions."""

from __future__ import annotations

import html

from promptcontrollab.core.files import JsonDict
from promptcontrollab.evidence.posttraining.common import _dict


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
<header><h1>Post-training checkpoint gate</h1><p>{_escape(gate.get("plain_summary"))}</p></header>
<div class="metrics"><div class="metric"><b>Decision</b><br>{_escape(gate.get("decision"))}</div>
<div class="metric"><b>Score delta</b><br>{_escape(comparison.get("score_delta"))}</div>
<div class="metric"><b>Missing artifacts</b><br>{len(gate.get("missing_artifacts", []))}</div></div>
<div class="grid">{"".join(cards)}</div><p>{_escape(gate.get("claim_boundary"))}</p>
</main></body></html>"""


def _escape(value: object) -> str:
    return html.escape(str(value if value is not None else ""))
