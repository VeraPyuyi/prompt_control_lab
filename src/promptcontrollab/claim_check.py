"""Claim-scope checks for prompt optimization evidence bundles."""

from __future__ import annotations

from pathlib import Path

from promptcontrollab.evidence_card import build_evidence_card
from promptcontrollab.files import JsonDict, ensure_dir, write_json

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
        write_json(out_path, payload)
        markdown_path = out_path.with_suffix(".md")
        markdown_path.write_text(render_claim_check_markdown(payload), encoding="utf-8")
        payload["json_path"] = str(out_path)
        payload["markdown_path"] = str(markdown_path)
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
