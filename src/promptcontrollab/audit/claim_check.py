"""Claim-scope checks for prompt optimization evidence bundles."""

from __future__ import annotations

import html
from pathlib import Path

from promptcontrollab.core.files import JsonDict, ensure_dir, write_json
from promptcontrollab.evidence_card import build_evidence_card

CLAIM_REQUIREMENTS = {
    "paired": 2,
    "partial-research": 3,
    "full-research": 4,
}

CLAIM_LABELS = {
    "paired": "paired comparison",
    "partial-research": "partial research diagnostic",
    "full-research": "full research diagnostic",
}

TIER_ORDER = {
    "tier_0_insufficient_or_contradicted": 0,
    "tier_1_incomplete_comparison": 1,
    "tier_2_paired_comparison": 2,
    "tier_3_partial_research_diagnostics": 3,
    "tier_4_full_research_diagnostics": 4,
}


def run_claim_check(
    run_dir: Path,
    *,
    claim: str,
    out_path: Path | None = None,
) -> JsonDict:
    """Check whether recorded artifacts support a requested claim scope."""

    normalized_claim = _normalize_claim(claim)
    card = build_evidence_card(run_dir)
    tier_name = str(card.get("evidence_tier", "tier_0_insufficient_or_contradicted"))
    tier_value = TIER_ORDER.get(tier_name, 0)
    required_tier = CLAIM_REQUIREMENTS[normalized_claim]
    recommendation = str(card.get("recommendation", "needs_review"))
    status = _status(tier_value, required_tier, recommendation)
    payload: JsonDict = {
        "kind": "prompt_optimization_claim_check",
        "run_dir": str(run_dir),
        "requested_claim": normalized_claim,
        "required_evidence_tier": required_tier,
        "status": status,
        "reason": _reason(
            status=status,
            claim=normalized_claim,
            tier_name=tier_name,
            tier_value=tier_value,
            required_tier=required_tier,
            recommendation=recommendation,
        ),
        "evidence_tier": tier_name,
        "claim_scope": card.get("claim_scope", ""),
        "safe_claim": card.get("claim_language", ""),
        "recommendation": recommendation,
        "next_tier_missing": card.get("next_tier_missing", []),
        "missing_artifacts": card.get("missing_artifacts", []),
        "artifacts": card.get("artifacts", {}),
        "boundary": card.get("boundary", ""),
    }
    if out_path is not None:
        ensure_dir(out_path.parent)
        markdown_path = out_path.with_suffix(".md")
        html_path = out_path.with_suffix(".html")
        payload["json_path"] = str(out_path)
        payload["markdown_path"] = str(markdown_path)
        payload["html_path"] = str(html_path)
        write_json(out_path, payload)
        markdown_path.write_text(render_claim_check_markdown(payload), encoding="utf-8")
        html_path.write_text(render_claim_check_html(payload), encoding="utf-8")
    return payload


def render_claim_check_markdown(payload: JsonDict) -> str:
    """Render a claim-check result for reviewers."""

    lines = [
        "# Prompt Optimization Claim Check",
        "",
        f"- Requested claim: `{payload.get('requested_claim', '')}`",
        f"- Status: `{payload.get('status', 'needs_review')}`",
        f"- Evidence tier: `{payload.get('evidence_tier', 'unknown')}`",
        f"- Claim scope: {payload.get('claim_scope', '')}",
        f"- Reason: {payload.get('reason', '')}",
        f"- Safe claim: {payload.get('safe_claim', '')}",
        f"- Next tier missing: `{payload.get('next_tier_missing', [])}`",
        f"- Run directory: `{payload.get('run_dir', '')}`",
        "",
        "## Boundary",
        "",
        str(payload.get("boundary", "")),
        "",
    ]
    return "\n".join(lines)


def render_claim_check_html(payload: JsonDict) -> str:
    """Render a browser-readable claim-check result."""

    rows = [
        ("Requested claim", payload.get("requested_claim", "")),
        ("Status", _badge(payload.get("status"))),
        ("Evidence tier", payload.get("evidence_tier", "unknown")),
        ("Claim scope", payload.get("claim_scope", "")),
        ("Reason", payload.get("reason", "")),
        ("Safe claim", payload.get("safe_claim", "")),
        ("Next tier missing", _joined(payload.get("next_tier_missing"))),
        ("Run directory", payload.get("run_dir", "")),
    ]
    table = "\n".join(
        "<tr>"
        f"<td>{_html_text(label)}</td>"
        f"<td>{value if _is_html_value(value) else _code(value)}</td>"
        "</tr>"
        for label, value in rows
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Prompt Optimization Claim Check</title>
  <style>
    :root {{
      --bg: #f6f8fb;
      --panel: #ffffff;
      --ink: #18212f;
      --muted: #667085;
      --line: #d9e1ec;
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
    main {{ max-width: 980px; margin: 0 auto; padding: 40px 24px 56px; }}
    .hero {{
      background: linear-gradient(135deg, #ffffff 0%, #eef5ff 100%);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 28px;
      box-shadow: 0 14px 38px rgba(24, 33, 47, 0.08);
    }}
    h1 {{ margin: 0 0 10px; font-size: clamp(28px, 4vw, 44px); line-height: 1.05; }}
    h2 {{ margin: 28px 0 12px; font-size: 20px; }}
    p {{ margin: 0; color: var(--muted); }}
    .panel {{
      margin-top: 22px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 18px;
    }}
    table {{ width: 100%; border-collapse: collapse; }}
    td {{ border-top: 1px solid var(--line); padding: 12px 0; vertical-align: top; }}
    td:first-child {{ width: 26%; color: var(--muted); padding-right: 18px; }}
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
    .pass {{ background: var(--green-bg); color: var(--green); }}
    .needs_review {{ background: var(--amber-bg); color: var(--amber); }}
    .fail {{ background: var(--red-bg); color: var(--red); }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>Prompt Optimization Claim Check</h1>
      <p>{_html_text(payload.get("reason", ""))}</p>
    </section>
    <section class="panel">
      <table>{table}</table>
    </section>
    <section class="panel">
      <h2>Boundary</h2>
      <p>{_html_text(payload.get("boundary", ""))}</p>
    </section>
  </main>
</body>
</html>
"""


def _is_html_value(value: object) -> bool:
    return isinstance(value, str) and value.startswith("<span ")


def _badge(value: object) -> str:
    text = str(value or "")
    css = text.replace("-", "_")
    return f'<span class="badge {html.escape(css, quote=True)}">{_html_text(text)}</span>'


def _code(value: object) -> str:
    return f"<code>{_html_text(value)}</code>"


def _joined(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value or "")


def _html_text(value: object) -> str:
    return html.escape(str(value or ""))


def _normalize_claim(claim: str) -> str:
    aliases = {
        "paired-comparison": "paired",
        "comparison": "paired",
        "research": "partial-research",
        "partial": "partial-research",
        "full": "full-research",
        "full-diagnostics": "full-research",
    }
    normalized = aliases.get(claim, claim)
    if normalized not in CLAIM_REQUIREMENTS:
        choices = ", ".join(sorted(CLAIM_REQUIREMENTS))
        msg = f"Unknown claim {claim!r}; expected one of: {choices}"
        raise ValueError(msg)
    return normalized


def _status(tier_value: int, required_tier: int, recommendation: str) -> str:
    if tier_value < required_tier:
        return "fail"
    if recommendation == "supported":
        return "pass"
    if recommendation in {"not_supported", "insufficient_evidence"}:
        return "fail"
    return "needs_review"


def _reason(
    *,
    status: str,
    claim: str,
    tier_name: str,
    tier_value: int,
    required_tier: int,
    recommendation: str,
) -> str:
    label = CLAIM_LABELS[claim]
    if status == "pass":
        return (
            f"The artifact bundle reaches {tier_name} and the evidence-card recommendation is "
            f"`supported`, so it supports the requested {label} claim."
        )
    if tier_value < required_tier:
        return (
            f"The artifact bundle is {tier_name}, which does not support the requested "
            f"{claim} claim. Required tier is at least {required_tier}."
        )
    return (
        f"The artifact bundle reaches the required tier for a {label} claim, but the "
        f"evidence-card recommendation is `{recommendation}` and needs review."
    )
