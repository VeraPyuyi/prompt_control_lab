"""One-command ecosystem bridge demo for bundled external-tool exports."""

from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path

from promptcontrollab.core.files import JsonDict, ensure_dir, read_json, write_json
from promptcontrollab.external_evidence import ExternalTool, build_external_evidence
from promptcontrollab.ingest import ingest_prompt_optimizer_assets
from promptcontrollab.research_workflow import run_research_diagnostics


@dataclass(frozen=True)
class EcosystemDemoSpec:
    tool: ExternalTool
    filename: str
    candidate_filename: str | None = None
    score_name: str | None = None
    baseline_prompt_id: str | None = None
    candidate_prompt_id: str | None = None
    baseline_name: str | None = None
    candidate_name: str | None = None
    baseline_experiment: str | None = None
    candidate_experiment: str | None = None


@dataclass(frozen=True)
class PromptOptimizerAssetSpec:
    tool: str
    filename: str


DEMO_SPECS: tuple[EcosystemDemoSpec, ...] = (
    EcosystemDemoSpec(
        tool="promptfoo",
        filename="promptfoo_results.json",
        baseline_prompt_id="baseline",
        candidate_prompt_id="candidate",
    ),
    EcosystemDemoSpec(
        tool="langfuse",
        filename="langfuse_export.json",
        score_name="exact_match",
        baseline_name="baseline",
        candidate_name="candidate",
    ),
    EcosystemDemoSpec(
        tool="langsmith",
        filename="langsmith_runs.csv",
        score_name="exact_match",
        baseline_experiment="baseline",
        candidate_experiment="candidate",
    ),
    EcosystemDemoSpec(
        tool="deepeval",
        filename="deepeval_baseline.json",
        candidate_filename="deepeval_candidate.json",
        score_name="exact_match",
    ),
)

ASSET_SPECS: tuple[PromptOptimizerAssetSpec, ...] = (
    PromptOptimizerAssetSpec(
        tool="prompt-optimizer",
        filename="prompt_optimizer_favorites.json",
    ),
)


def run_ecosystem_demo(
    *,
    examples_dir: Path,
    out_dir: Path,
    split_hash: str = "external-demo-split",
    provider: str = "openai",
    model: str = "gpt-4o-mini-20260601",
    bootstrap_samples: int = 1000,
    permutation_samples: int = 1000,
) -> JsonDict:
    """Run all bundled external bridge examples into one reviewer-facing directory."""

    if not examples_dir.exists():
        msg = f"External examples directory does not exist: {examples_dir}"
        raise ValueError(msg)
    if out_dir.exists() and any(out_dir.iterdir()):
        msg = f"Ecosystem demo output directory must be empty: {out_dir}"
        raise ValueError(msg)
    ensure_dir(out_dir)

    runs: list[JsonDict] = []
    for spec in DEMO_SPECS:
        source = examples_dir / spec.filename
        if not source.exists():
            msg = f"Missing {spec.tool} example export: {source}"
            raise ValueError(msg)
        candidate_source = examples_dir / (spec.candidate_filename or spec.filename)
        if not candidate_source.exists():
            msg = f"Missing {spec.tool} candidate example export: {candidate_source}"
            raise ValueError(msg)
        tool_dir = out_dir / spec.tool
        provider_value = f"{provider}:{model}" if spec.tool == "promptfoo" else provider
        build_external_evidence(
            tool=spec.tool,
            baseline_input=source,
            candidate_input=candidate_source,
            out_dir=tool_dir,
            score_name=spec.score_name,
            provider=provider_value,
            model=model,
            baseline_prompt_id=spec.baseline_prompt_id,
            candidate_prompt_id=spec.candidate_prompt_id,
            baseline_name=spec.baseline_name,
            candidate_name=spec.candidate_name,
            baseline_experiment=spec.baseline_experiment,
            candidate_experiment=spec.candidate_experiment,
            split_hash=split_hash,
            title=f"PromptControlLab {spec.tool} Evidence Demo",
            bootstrap_samples=bootstrap_samples,
            permutation_samples=permutation_samples,
        )
        bridge = read_json(tool_dir / "bridge_summary.json")
        runs.append(
            {
                "tool": spec.tool,
                "source": str(source),
                "out_dir": str(tool_dir),
                "recommendation": bridge.get("recommendation"),
                "evidence_tier": bridge.get("evidence_tier"),
                "validity": bridge.get("validity"),
                "claim_check_status": bridge.get("claim_check_status"),
                "missing_evidence": bridge.get("missing_evidence", []),
                "next_actions": bridge.get("next_actions", []),
                "result_path": str(tool_dir / "evidence_from_result.json"),
                "bridge_summary_path": str(tool_dir / "bridge_summary.md"),
                "bridge_summary_html_path": str(tool_dir / "bridge_summary.html"),
                "report_html_path": str(tool_dir / "report.html"),
            }
        )
    for asset_spec in ASSET_SPECS:
        runs.append(_run_prompt_optimizer_asset_bridge(examples_dir, out_dir, asset_spec))

    payload: JsonDict = {
        "kind": "ecosystem_demo",
        "examples_dir": str(examples_dir),
        "out_dir": str(out_dir),
        "positioning": (
            "prompt_control_lab acts as a prompt optimization evidence auditor on top of "
            "external eval and observability exports."
        ),
        "runs": runs,
        "next_steps": [
            "Open ecosystem_scorecard.html and read Market readiness first.",
            "Open each bridge_summary.html to see what the external tool supplied.",
            "Open each evidence_card.html to inspect the prompt optimization evidence.",
            "Open each claim_check.html to see the strongest supported claim.",
            "Open report.html or the local UI Research Overview for reviewer-facing inspection.",
        ],
    }
    write_json(out_dir / "ecosystem_demo.json", payload)
    diagnostics = run_research_diagnostics(
        run_dir=out_dir,
        mode="ecosystem_demo",
        diagnostics_dir=out_dir / "diagnostics",
        summary_dir=out_dir,
    )
    payload["research_diagnostics_path"] = str(out_dir / "research_diagnostics.json")
    payload["research_diagnostics_md_path"] = str(out_dir / "research_diagnostics.md")
    payload["research_diagnostics_html_path"] = str(out_dir / "research_diagnostics.html")
    payload["research_bundle_html_path"] = str(out_dir / "research_bundle.html")
    payload["research_diagnostic_type"] = diagnostics.get("diagnostic_type")
    scorecard = _write_scorecard(out_dir=out_dir, payload=payload, diagnostics=diagnostics)
    payload["ecosystem_scorecard_path"] = scorecard["json_path"]
    payload["ecosystem_scorecard_md_path"] = scorecard["markdown_path"]
    payload["ecosystem_scorecard_html_path"] = scorecard["html_path"]
    write_json(out_dir / "ecosystem_demo.json", payload)
    (out_dir / "README.md").write_text(_render_readme(payload), encoding="utf-8")
    return payload


def write_ecosystem_scorecard(*, run_dir: Path, out_path: Path | None = None) -> JsonDict:
    """Regenerate the cross-tool ecosystem scorecard for an existing demo run."""

    demo_path = run_dir / "ecosystem_demo.json"
    if not demo_path.exists():
        msg = f"Ecosystem demo manifest does not exist: {demo_path}"
        raise ValueError(msg)
    payload = read_json(demo_path)
    diagnostics_path = run_dir / "research_diagnostics.json"
    if diagnostics_path.exists():
        diagnostics = read_json(diagnostics_path)
    else:
        diagnostics = run_research_diagnostics(
            run_dir=run_dir,
            mode="ecosystem_scorecard",
            diagnostics_dir=run_dir / "diagnostics",
            summary_dir=run_dir,
        )
    return _write_scorecard(
        out_dir=run_dir,
        payload=payload,
        diagnostics=diagnostics,
        out_path=out_path,
    )


def _run_prompt_optimizer_asset_bridge(
    examples_dir: Path,
    out_dir: Path,
    spec: PromptOptimizerAssetSpec,
) -> JsonDict:
    source = examples_dir / spec.filename
    if not source.exists():
        msg = f"Missing {spec.tool} example export: {source}"
        raise ValueError(msg)
    tool_dir = out_dir / spec.tool
    payload = ingest_prompt_optimizer_assets(source_path=source, out_dir=tool_dir)
    bridge = _write_prompt_optimizer_bridge_summary(
        tool_dir=tool_dir,
        source=source,
        ingest_payload=payload,
    )
    return {
        "tool": spec.tool,
        "source": str(source),
        "out_dir": str(tool_dir),
        "recommendation": bridge.get("recommendation"),
        "evidence_tier": bridge.get("evidence_tier"),
        "validity": bridge.get("validity"),
        "claim_check_status": bridge.get("claim_check_status"),
        "missing_evidence": bridge.get("missing_evidence", []),
        "next_actions": bridge.get("next_actions", []),
        "result_path": str(tool_dir / "prompt_assets.json"),
        "bridge_summary_path": str(tool_dir / "bridge_summary.md"),
        "bridge_summary_html_path": str(tool_dir / "bridge_summary.html"),
        "prompt_assets_html_path": str(tool_dir / "prompt_assets.html"),
        "gap_plan_html_path": str(tool_dir / "prompt_optimizer_gap_plan.html"),
    }


def _write_prompt_optimizer_bridge_summary(
    *,
    tool_dir: Path,
    source: Path,
    ingest_payload: JsonDict,
) -> JsonDict:
    bridge: JsonDict = {
        "requested_tool": "prompt-optimizer",
        "validity": "not_scored",
        "evidence_tier": "asset_bridge",
        "claim_check_status": "not_applicable",
        "recommendation": "score_imported_assets_before_claiming_improvement",
        "paired_n": None,
        "mean_delta": None,
        "asset_count": ingest_payload.get("asset_count"),
        "source": str(source),
        "missing_evidence": [
            "paired_predictions",
            "metrics",
            "comparison_validity",
            "paired_statistics",
            "claim_check",
        ],
        "next_actions": ingest_payload.get("next_actions", []),
        "boundary": ingest_payload.get(
            "boundary",
            "prompt-optimizer exports are prompt assets, not scored eval evidence.",
        ),
    }
    write_json(tool_dir / "bridge_summary.json", bridge)
    (tool_dir / "bridge_summary.md").write_text(
        _render_prompt_optimizer_bridge_markdown(bridge),
        encoding="utf-8",
    )
    (tool_dir / "bridge_summary.html").write_text(
        _render_prompt_optimizer_bridge_html(bridge),
        encoding="utf-8",
    )
    return bridge


def _render_prompt_optimizer_bridge_markdown(payload: JsonDict) -> str:
    missing = _string_list(payload.get("missing_evidence"))
    actions = _string_list(payload.get("next_actions"))
    lines = [
        "# prompt-optimizer Asset Bridge",
        "",
        "This bundle imports prompt-optimizer favorites/templates as prompt assets.",
        (
            "It does **not** claim that any prompt improved, because no paired "
            "predictions or metrics were supplied."
        ),
        "",
        "## Status",
        "",
        f"- Validity: `{payload.get('validity')}`",
        f"- Evidence tier: `{payload.get('evidence_tier')}`",
        f"- Claim check: `{payload.get('claim_check_status')}`",
        f"- Asset count: `{payload.get('asset_count')}`",
        "",
        "## Missing evidence before an improvement claim",
        "",
        *[f"- {item}" for item in missing],
        "",
        "## Next actions",
        "",
        *[f"- {item}" for item in actions],
        "",
        "## Boundary",
        "",
        str(payload.get("boundary") or ""),
        "",
    ]
    return "\n".join(lines)


def _render_prompt_optimizer_bridge_html(payload: JsonDict) -> str:
    body = _render_prompt_optimizer_bridge_markdown(payload)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>prompt-optimizer Asset Bridge</title>
  <style>
    body {{
      margin: 0;
      background: #f7f9fc;
      color: #18212f;
      font: 15px/1.6 system-ui, sans-serif;
    }}
    main {{ max-width: 920px; margin: 0 auto; padding: 40px 24px; }}
    pre {{
      white-space: pre-wrap;
      background: #fff;
      border: 1px solid #d9e1ec;
      border-radius: 12px;
      padding: 22px;
    }}
  </style>
</head>
<body><main><pre>{html.escape(body)}</pre></main></body>
</html>
"""


def _write_scorecard(
    *,
    out_dir: Path,
    payload: JsonDict,
    diagnostics: JsonDict,
    out_path: Path | None = None,
) -> JsonDict:
    rows = _scorecard_rows(out_dir=out_dir, payload=payload, diagnostics=diagnostics)
    evidence_matrix = _pcl_evidence_matrix(rows)
    market_map = _extended_market_map()
    json_path = _scorecard_json_path(out_dir=out_dir, out_path=out_path)
    ensure_dir(json_path.parent)
    md_path = json_path.with_suffix(".md")
    html_path = json_path.with_suffix(".html")
    scorecard: JsonDict = {
        "kind": "ecosystem_scorecard",
        "positioning": (
            "Promptfoo, DeepEval, LangSmith, Langfuse, and prompt-optimizer remain the systems "
            "of record for evals, tests, traces, observability, security checks, and prompt "
            "assets. PCL adds the research evidence layer for prompt optimization claims."
        ),
        "tool_count": len(rows),
        "rows": rows,
        "pcl_evidence_matrix": evidence_matrix,
        "market_map": market_map,
        "market_readiness": _market_readiness_summary(market_map),
        "recommended_review_order": [
            "Open ecosystem_scorecard.html for the cross-tool summary.",
            "Use ecosystem_scorecard.md for plain-text review.",
            "Use the extended market map only for positioning; imported rows are the evidence.",
            "Open each bridge_summary.html for tool-specific provenance.",
            "Open evidence_card.html and claim_check.html before making an optimization claim.",
            "Open research_gap_plan.html, run the reviewed commands, then run pcl gap-status.",
        ],
        "boundary": (
            "This scorecard summarizes evidence coverage. It does not claim that PCL "
            "replaces external eval, tracing, observability, or security-testing platforms."
        ),
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "html_path": str(html_path),
    }
    write_json(json_path, scorecard)
    md_path.write_text(_render_scorecard(scorecard), encoding="utf-8")
    html_path.write_text(_render_scorecard_html(scorecard), encoding="utf-8")
    return scorecard


def _scorecard_json_path(*, out_dir: Path, out_path: Path | None) -> Path:
    if out_path is None:
        return out_dir / "ecosystem_scorecard.json"
    if out_path.suffix:
        return out_path
    return out_path / "ecosystem_scorecard.json"


def _scorecard_rows(*, out_dir: Path, payload: JsonDict, diagnostics: JsonDict) -> list[JsonDict]:
    diagnostic_rows = _diagnostic_rows_by_tool(diagnostics)
    rows: list[JsonDict] = []
    runs = payload.get("runs")
    if not isinstance(runs, list):
        return rows
    for run in runs:
        if not isinstance(run, dict):
            continue
        tool = str(run.get("tool") or "external")
        tool_dir = Path(str(run.get("out_dir") or out_dir / tool))
        bridge_path = tool_dir / "bridge_summary.json"
        bridge = read_json(bridge_path) if bridge_path.exists() else {}
        diagnostic = diagnostic_rows.get(tool, {})
        gap_status = _gap_status_summary(tool_dir)
        artifact_links = _scorecard_artifact_links(out_dir=out_dir, tool_dir=tool_dir)
        rows.append(
            {
                "tool": tool,
                "display_name": _display_tool_name(tool),
                "external_strength": _external_strength(tool),
                "pcl_adds": _pcl_adds(tool),
                "validity": bridge.get("validity") or run.get("validity"),
                "evidence_tier": bridge.get("evidence_tier") or run.get("evidence_tier"),
                "claim_check_status": bridge.get("claim_check_status")
                or run.get("claim_check_status"),
                "recommendation": bridge.get("recommendation") or run.get("recommendation"),
                "paired_n": bridge.get("paired_n"),
                "mean_delta": bridge.get("mean_delta"),
                "research_bundle_integrity": _bundle_integrity(tool_dir),
                "missing_paper_diagnostics": diagnostic.get(
                    "missing_paper_diagnostics",
                    bridge.get("missing_paper_diagnostics", []),
                ),
                "research_gap_plan": _relative_to(
                    out_dir,
                    _preferred_artifact(tool_dir, "research_gap_plan", "html", "md"),
                )
                if _preferred_artifact(tool_dir, "research_gap_plan", "html", "md").exists()
                else "",
                "gap_status_command": f"pcl gap-status --run {_relative_to(out_dir, tool_dir)}",
                "gap_status": gap_status.get("status"),
                "gap_complete_count": gap_status.get("complete_count"),
                "gap_missing_count": gap_status.get("missing_count"),
                "gap_status_path": _relative_to(
                    out_dir,
                    _preferred_artifact(tool_dir, "research_gap_status", "html", "md"),
                )
                if _preferred_artifact(tool_dir, "research_gap_status", "html", "md").exists()
                else "",
                "open_first": _relative_to(
                    out_dir,
                    _preferred_artifact(tool_dir, "bridge_summary", "html", "md"),
                ),
                "artifact_links": artifact_links,
            }
        )
    return rows


def _scorecard_artifact_links(*, out_dir: Path, tool_dir: Path) -> list[JsonDict]:
    candidates = [
        ("Bridge summary", _preferred_artifact(tool_dir, "bridge_summary", "html", "md")),
        ("Research bundle", tool_dir / "research_bundle.html"),
        ("Evidence card", _preferred_artifact(tool_dir, "evidence_card", "html", "md")),
        ("Claim check", _preferred_artifact(tool_dir, "claim_check", "html", "md")),
        ("HTML report", tool_dir / "report.html"),
        ("Prompt assets", _preferred_artifact(tool_dir, "prompt_assets", "html", "md")),
        (
            "Prompt-optimizer gap plan",
            _preferred_artifact(tool_dir, "prompt_optimizer_gap_plan", "html", "md"),
        ),
        ("Gap plan", _preferred_artifact(tool_dir, "research_gap_plan", "html", "md")),
        ("Gap status", _preferred_artifact(tool_dir, "research_gap_status", "html", "md")),
    ]
    return [
        {"label": label, "path": _relative_to(out_dir, path)}
        for label, path in candidates
        if path.exists()
    ]


def _preferred_artifact(tool_dir: Path, stem: str, *suffixes: str) -> Path:
    for suffix in suffixes:
        path = tool_dir / f"{stem}.{suffix}"
        if path.exists():
            return path
    return tool_dir / f"{stem}.{suffixes[-1] if suffixes else 'md'}"


def _pcl_evidence_matrix(rows: list[JsonDict]) -> list[JsonDict]:
    """Return a compact matrix of PCL-added evidence per external tool."""

    matrix: list[JsonDict] = []
    for row in rows:
        missing = row.get("missing_paper_diagnostics")
        missing_list = missing if isinstance(missing, list) else []
        integrity = row.get("research_bundle_integrity")
        integrity_dict = integrity if isinstance(integrity, dict) else {}
        evidence_card = _artifact_status(row, "Evidence card")
        claim_check = _artifact_status(row, "Claim check")
        research_bundle = _artifact_status(row, "Research bundle")
        matrix.append(
            {
                "tool": row.get("tool", ""),
                "display_name": row.get("display_name", ""),
                "prompt_only_validity": row.get("validity") or "unknown",
                "paired_stats": "recorded"
                if row.get("paired_n") is not None or row.get("mean_delta") is not None
                else "unknown",
                "evidence_card": evidence_card["status"],
                "evidence_card_path": evidence_card["path"],
                "claim_check": row.get("claim_check_status") or claim_check["status"],
                "claim_check_path": claim_check["path"],
                "research_bundle": research_bundle["status"],
                "research_bundle_path": research_bundle["path"],
                "bundle_hash_status": integrity_dict.get("status", "unknown"),
                "bundle_verification": integrity_dict.get("verification_status", "not_checked"),
                "gap_status": row.get("gap_status") or "not_checked",
                "missing_paper_diagnostic_count": len(missing_list),
                "missing_paper_diagnostics": list(missing_list),
                "next_command": row.get("gap_status_command", ""),
            }
        )
    return matrix


def _extended_market_map() -> list[JsonDict]:
    """Return positioning-only rows for adjacent tools not imported by the demo."""

    return [
        {
            "tool": "Braintrust",
            "strong_lane": "Eval datasets, experiments, traces, and human review workflows.",
            "pcl_should_learn": "Fast experiment UX and reviewer-friendly comparison pages.",
            "pcl_owns": "Paper-diagnostic evidence for prompt optimization claims.",
            "pcl_product_move": "Improve reviewer workflow and experiment comparison UX.",
            "priority": "P1",
            "status": "positioning_only_not_imported",
        },
        {
            "tool": "Arize Phoenix",
            "strong_lane": (
                "Open-source observability, tracing, evaluation, and retrieval analysis."
            ),
            "pcl_should_learn": "Trace-first debugging and rich local investigation views.",
            "pcl_owns": "Prompt-only validity, control diagnostics, and soft-hard risk reports.",
            "pcl_product_move": "Deepen trace and audit UI without becoming a tracing platform.",
            "priority": "P2",
            "status": "positioning_only_not_imported",
        },
        {
            "tool": "OpenAI Evals",
            "strong_lane": "Canonical eval harness patterns and reusable benchmark definitions.",
            "pcl_should_learn": "Portable eval schemas and clear task/result separation.",
            "pcl_owns": (
                "Tri-split hygiene, prompt identity, and evidence cards around eval outputs."
            ),
            "pcl_product_move": "Keep import and scaffold contracts portable for eval harnesses.",
            "priority": "P1",
            "status": "positioning_only_not_imported",
        },
        {
            "tool": "Humanloop",
            "strong_lane": "Historical prompt management and evaluation workflow reference.",
            "pcl_should_learn": "Prompt lifecycle UX, registry language, and review workflows.",
            "pcl_owns": "Local research diagnostics and provenance-first export artifacts.",
            "pcl_product_move": (
                "Keep local registry language clear without hosted-platform sprawl."
            ),
            "priority": "P3",
            "status": "historical_sunset_reference_not_imported",
        },
    ]


def _market_readiness_summary(market_map: list[JsonDict]) -> JsonDict:
    """Return a compact action summary derived from adjacent-market positioning."""

    prioritized_moves = [
        {
            "priority": row.get("priority", ""),
            "tool": row.get("tool", ""),
            "move": row.get("pcl_product_move", ""),
        }
        for row in market_map
        if str(row.get("priority", "")) in {"P1", "P2"}
    ]
    return {
        "status": "early_adopter_ready",
        "recommended_positioning": (
            "Lead with paper diagnostics and evidence for prompt-optimization claims; "
            "import outputs from eval, observability, and prompt-writing tools instead "
            "of rebuilding their full workflows."
        ),
        "best_first_users": [
            "Prompt optimization researchers who need reproducible paper diagnostics.",
            (
                "LLM evaluation teams that already use Promptfoo, DeepEval, LangSmith, "
                "Langfuse, or similar tools."
            ),
            "AI coding-agent teams that need local evidence before rollout.",
        ],
        "do_not_build": [
            "A full tracing or observability platform.",
            "A hosted prompt-management SaaS.",
            "A generic prompt-writing editor.",
        ],
        "next_moves": prioritized_moves,
    }


def _artifact_status(row: JsonDict, label: str) -> JsonDict:
    links = row.get("artifact_links")
    if not isinstance(links, list):
        return {"status": "missing", "path": ""}
    for item in links:
        if not isinstance(item, dict):
            continue
        if item.get("label") == label and item.get("path"):
            return {"status": "present", "path": item.get("path")}
    return {"status": "missing", "path": ""}


def _gap_status_summary(tool_dir: Path) -> JsonDict:
    path = tool_dir / "research_gap_status.json"
    if not path.exists():
        return {
            "status": "not_checked",
            "complete_count": None,
            "missing_count": None,
        }
    payload = read_json(path)
    return {
        "status": payload.get("status", "unknown"),
        "complete_count": payload.get("complete_count"),
        "missing_count": payload.get("missing_count"),
    }


def _bundle_integrity(tool_dir: Path) -> JsonDict:
    path = tool_dir / "research_bundle.json"
    if not path.exists():
        return {"status": "missing", "missing_html_count": None}
    payload = read_json(path)
    missing = payload.get("missing_html_artifacts")
    missing_list = missing if isinstance(missing, list) else []
    hashed = int(payload.get("hashed_artifact_count") or 0)
    return {
        "status": "hashed" if hashed else "present_without_hashes",
        "artifact_count": payload.get("artifact_count"),
        "present_artifact_count": payload.get("present_artifact_count"),
        "hashed_artifact_count": hashed,
        "missing_html_artifacts": missing_list,
        "missing_html_count": len(missing_list),
        **_bundle_verification_summary(tool_dir),
    }


def _bundle_verification_summary(tool_dir: Path) -> JsonDict:
    path = tool_dir / "research_bundle_verification.json"
    if not path.exists():
        return {
            "verification_status": "not_checked",
            "verification_path": "",
        }
    payload = read_json(path)
    return {
        "verification_status": payload.get("status", "unknown"),
        "verification_path": str(path),
        "verification_checked_count": payload.get("checked_count"),
        "verification_mismatch_count": payload.get("mismatch_count"),
        "verification_missing_count": payload.get("missing_count"),
    }


def _relative_to(base: Path, path: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return str(path)


def _diagnostic_rows_by_tool(diagnostics: JsonDict) -> dict[str, JsonDict]:
    diagnostic_payload = diagnostics.get("diagnostics")
    if not isinstance(diagnostic_payload, dict):
        return {}
    ecosystem = diagnostic_payload.get("ecosystem_bridge")
    if not isinstance(ecosystem, dict):
        return {}
    runs = ecosystem.get("runs")
    if not isinstance(runs, list):
        return {}
    rows: dict[str, JsonDict] = {}
    for row in runs:
        if not isinstance(row, dict):
            continue
        tool = row.get("tool")
        if isinstance(tool, str) and tool:
            rows[tool] = row
    return rows


def _external_strength(tool: str) -> str:
    values = {
        "promptfoo": "LLM evals, red-team/security tests, provider matrices, and CI reports.",
        "langfuse": "Open-source tracing, prompt management, scores, costs, and self-hosting.",
        "langsmith": "Agent tracing, datasets, online/offline evals, debugging, and deployment.",
        "deepeval": "Local LLM evaluation test runs, metric scores, reasons, and CI artifacts.",
        "prompt-optimizer": (
            "Prompt rewriting UX, prompt favorites/templates, and prompt asset management."
        ),
    }
    return values.get(tool, "External eval or observability export.")


def _pcl_adds(tool: str) -> str:
    values = {
        "promptfoo": (
            "Paired uncertainty, prompt-only validity, evidence cards, claim checks, "
            "and paper-diagnostic gap closure."
        ),
        "langfuse": (
            "Export-to-evidence conversion, paired validity checks, local evidence cards, "
            "and diagnostics outside trace platforms."
        ),
        "langsmith": (
            "Prompt optimization evidence bundles that separate prompt effects from model, "
            "metric, and split confounds."
        ),
        "deepeval": (
            "Paired prompt evidence, protocol hygiene, claim checks, and paper-diagnostic "
            "follow-up planning on top of DeepEval local TestRun JSON."
        ),
        "prompt-optimizer": (
            "Prompt asset provenance, content hashes, and an explicit gap plan for collecting "
            "paired eval evidence before claiming improvement."
        ),
    }
    return values.get(tool, "Paired prompt optimization evidence and diagnostics.")


def _display_tool_name(tool: str) -> str:
    values = {
        "promptfoo": "Promptfoo",
        "langfuse": "Langfuse",
        "langsmith": "LangSmith",
        "deepeval": "DeepEval",
        "prompt-optimizer": "prompt-optimizer",
    }
    return values.get(tool, tool)


def _render_scorecard(payload: JsonDict) -> str:
    lines = [
        "# Ecosystem Scorecard",
        "",
        str(payload.get("positioning", "")),
        "",
        "## PCL-added evidence matrix",
        "",
        (
            "| Tool | Prompt-only validity | Paired stats | Evidence card | Claim check | "
            "Research bundle | Bundle verification | Gap status | Missing diagnostics | "
            "Next command |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    matrix_rows = payload.get("pcl_evidence_matrix")
    if isinstance(matrix_rows, list):
        for row in matrix_rows:
            if not isinstance(row, dict):
                continue
            missing = row.get("missing_paper_diagnostics")
            missing_text = (
                ", ".join(str(item) for item in missing)
                if isinstance(missing, list)
                else str(missing or "")
            )
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row.get("display_name", "")),
                        str(row.get("prompt_only_validity", "")),
                        str(row.get("paired_stats", "")),
                        _artifact_status_markdown(
                            row.get("evidence_card"),
                            row.get("evidence_card_path"),
                        ),
                        _artifact_status_markdown(
                            row.get("claim_check"),
                            row.get("claim_check_path"),
                        ),
                        _artifact_status_markdown(
                            row.get("research_bundle"),
                            row.get("research_bundle_path"),
                        ),
                        str(row.get("bundle_verification", "")),
                        str(row.get("gap_status", "")),
                        missing_text,
                        f"`{row.get('next_command', '')}`",
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Cross-tool summary",
            "",
            (
                "| Tool | External strength | What PCL adds | Validity | Evidence tier | "
                "Gap status | Bundle integrity | Reviewer artifacts | Missing paper diagnostics |"
            ),
            "|---|---|---|---|---|---|---|---|---|",
        ]
    )
    rows = payload.get("rows")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            missing = row.get("missing_paper_diagnostics")
            missing_text = (
                ", ".join(str(item) for item in missing)
                if isinstance(missing, list)
                else str(missing or "")
            )
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row.get("display_name", "")),
                        str(row.get("external_strength", "")),
                        str(row.get("pcl_adds", "")),
                        str(row.get("validity", "")),
                        str(row.get("evidence_tier", "")),
                        str(row.get("gap_status", "")),
                        _bundle_integrity_markdown(row.get("research_bundle_integrity")),
                        _artifact_links_markdown(row.get("artifact_links")),
                        missing_text,
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Gap closure commands",
            "",
            "| Tool | Open first | Gap status command |",
            "|---|---|---|",
        ]
    )
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            gap_status = str(row.get("gap_status", ""))
            if row.get("gap_missing_count") is not None:
                gap_status = f"{gap_status} ({row.get('gap_missing_count')} missing)"
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row.get("display_name", "")),
                        f"`{row.get('open_first', '')}`",
                        f"{gap_status}; `{row.get('gap_status_command', '')}`",
                    ]
                )
                + " |"
            )
    readiness = payload.get("market_readiness")
    if isinstance(readiness, dict):
        lines.extend(_market_readiness_markdown_lines(readiness))
    market_map = payload.get("market_map")
    lines.extend(
        [
            "",
            "## Extended market map (not imported in this demo)",
            "",
            (
                "These rows are positioning references only. They are not imported evidence "
                "bundles and should not be used as direct benchmark results."
            ),
            "",
            (
                "| Tool | Strong lane | What PCL should learn | What PCL still owns | "
                "PCL product move | Priority | Status |"
            ),
            "|---|---|---|---|---|---|---|",
        ]
    )
    if isinstance(market_map, list):
        for row in market_map:
            if not isinstance(row, dict):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row.get("tool", "")),
                        str(row.get("strong_lane", "")),
                        str(row.get("pcl_should_learn", "")),
                        str(row.get("pcl_owns", "")),
                        str(row.get("pcl_product_move", "")),
                        str(row.get("priority", "")),
                        str(row.get("status", "")),
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Recommended review order",
            "",
            *[f"- {item}" for item in _string_list(payload.get("recommended_review_order"))],
            "",
            "## Boundary",
            "",
            str(payload.get("boundary", "")),
            "",
        ]
    )
    return "\n".join(lines)


def _market_readiness_markdown_lines(readiness: JsonDict) -> list[str]:
    lines = [
        "",
        "## Market readiness",
        "",
        f"- Status: `{readiness.get('status', '')}`",
        f"- Recommended positioning: {readiness.get('recommended_positioning', '')}",
        "- Best first users:",
        *[f"  - {item}" for item in _string_list(readiness.get("best_first_users"))],
        "- Do not build:",
        *[f"  - {item}" for item in _string_list(readiness.get("do_not_build"))],
        "- Next moves:",
    ]
    next_moves = readiness.get("next_moves")
    if isinstance(next_moves, list):
        for item in next_moves:
            if not isinstance(item, dict):
                continue
            lines.append(
                "  - "
                f"{item.get('priority', '')} {item.get('tool', '')}: "
                f"{item.get('move', '')}"
            )
    return lines


def _artifact_status_markdown(status: object, path: object) -> str:
    status_text = str(status or "")
    path_text = str(path or "")
    if path_text:
        return f"{status_text}: [{path_text}]({path_text})"
    return status_text


def _artifact_links_markdown(value: object) -> str:
    if not isinstance(value, list):
        return ""
    links: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "")
        path = str(item.get("path") or "")
        if label and path:
            links.append(f"[{label}]({path})")
    return "<br>".join(links)


def _render_scorecard_html(payload: JsonDict) -> str:
    rows = _scorecard_html_rows(payload.get("rows"))
    matrix_rows = _scorecard_html_rows(payload.get("pcl_evidence_matrix"))
    market_rows = _scorecard_html_rows(payload.get("market_map"))
    readiness = payload.get("market_readiness")
    readiness_html = (
        _render_market_readiness_html(readiness) if isinstance(readiness, dict) else ""
    )
    summary = _scorecard_summary(rows)
    matrix_table_rows = "\n".join(_render_matrix_html_row(row) for row in matrix_rows)
    table_rows = "\n".join(_render_scorecard_html_row(row) for row in rows)
    market_table_rows = "\n".join(_render_market_map_html_row(row) for row in market_rows)
    review_items = "\n".join(
        f"<li>{_html_text(item)}</li>"
        for item in _string_list(payload.get("recommended_review_order"))
    )
    boundary = _html_text(payload.get("boundary", ""))
    positioning = _html_text(payload.get("positioning", ""))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>prompt_control_lab Ecosystem Scorecard</title>
  <style>
    :root {{
      color-scheme: light;
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
    main {{
      max-width: 1220px;
      margin: 0 auto;
      padding: 40px 24px 56px;
    }}
    .hero {{
      background: linear-gradient(135deg, #ffffff 0%, #eef5ff 100%);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 28px;
      box-shadow: 0 14px 38px rgba(24, 33, 47, 0.08);
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: clamp(28px, 4vw, 46px);
      line-height: 1.05;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 34px 0 14px;
      font-size: 22px;
      letter-spacing: 0;
    }}
    p {{ margin: 0; color: var(--muted); }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 14px;
      margin-top: 22px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 16px;
    }}
    .card strong {{
      display: block;
      font-size: 28px;
      line-height: 1;
      margin-bottom: 8px;
    }}
    .card span {{ color: var(--muted); }}
    .table-wrap {{
      overflow-x: auto;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 12px;
    }}
    table {{
      width: 100%;
      min-width: 1280px;
      border-collapse: collapse;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 12px 14px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #f0f4fa;
      color: #344054;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    code {{
      display: inline-block;
      max-width: 280px;
      overflow-wrap: anywhere;
      padding: 2px 6px;
      border-radius: 6px;
      background: #eef2f7;
      color: #26364d;
      font-size: 12px;
    }}
    a {{ color: var(--blue); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .badge {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 3px 9px;
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }}
    .good {{ background: var(--green-bg); color: var(--green); }}
    .warn {{ background: var(--amber-bg); color: var(--amber); }}
    .bad {{ background: var(--red-bg); color: var(--red); }}
    .neutral {{ background: #edf2f7; color: #475467; }}
    .muted {{ color: var(--muted); }}
    .two-col {{
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(260px, 0.8fr);
      gap: 18px;
    }}
    @media (max-width: 900px) {{
      .two-col {{ grid-template-columns: 1fr; }}
      main {{ padding: 22px 14px 40px; }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>Ecosystem Scorecard</h1>
      <p>{positioning}</p>
      <div class="summary">
        <div class="card">
          <strong>{summary["tool_count"]}</strong><span>tools imported</span>
        </div>
        <div class="card">
          <strong>{summary["valid_count"]}</strong><span>valid evidence rows</span>
        </div>
        <div class="card">
          <strong>{summary["needs_work_count"]}</strong><span>gap rows needing work</span>
        </div>
        <div class="card">
          <strong>{summary["missing_diagnostic_count"]}</strong><span>missing diagnostics</span>
        </div>
      </div>
    </section>

    <h2>PCL-added evidence matrix</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Tool</th>
            <th>Prompt-only validity</th>
            <th>Paired stats</th>
            <th>Evidence card</th>
            <th>Claim check</th>
            <th>Research bundle</th>
            <th>Bundle verification</th>
            <th>Gap status</th>
            <th>Missing diagnostics</th>
            <th>Next command</th>
          </tr>
        </thead>
        <tbody>
          {matrix_table_rows}
        </tbody>
      </table>
    </div>

    <h2>Cross-tool positioning</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Tool</th>
            <th>External strength</th>
            <th>What PCL adds</th>
            <th>Validity</th>
            <th>Evidence</th>
            <th>Gap</th>
            <th>Bundle integrity</th>
            <th>Reviewer artifacts</th>
            <th>Missing diagnostics</th>
            <th>Open first</th>
            <th>Next command</th>
          </tr>
        </thead>
        <tbody>
          {table_rows}
        </tbody>
      </table>
    </div>

    <section class="two-col">
      <div>
        <h2>Recommended review order</h2>
        <div class="card"><ol>{review_items}</ol></div>
      </div>
      <div>
        <h2>Boundary</h2>
        <div class="card"><p>{boundary}</p></div>
      </div>
    </section>

    {readiness_html}

    <h2>Extended market map (not imported in this demo)</h2>
    <p>
      These rows are positioning references only. They are not imported evidence bundles
      and should not be used as direct benchmark results.
    </p>
    <div class="table-wrap" style="margin-top: 14px;">
      <table>
        <thead>
          <tr>
            <th>Tool</th>
            <th>Strong lane</th>
            <th>What PCL should learn</th>
            <th>What PCL still owns</th>
            <th>PCL product move</th>
            <th>Priority</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {market_table_rows}
        </tbody>
      </table>
    </div>
  </main>
</body>
</html>
"""


def _render_market_readiness_html(readiness: JsonDict) -> str:
    next_moves = readiness.get("next_moves")
    move_rows = ""
    if isinstance(next_moves, list):
        move_rows = "\n".join(
            _render_market_readiness_move_html(item)
            for item in next_moves
            if isinstance(item, dict)
        )
    return f"""
    <h2>Market readiness</h2>
    <section class="two-col">
      <div class="card">
        <p><strong>Status:</strong> <code>{_html_text(readiness.get("status", ""))}</code></p>
        <p style="margin-top: 12px;">{_html_text(readiness.get("recommended_positioning", ""))}</p>
      </div>
      <div class="card">
        <p><strong>Best first users</strong></p>
        {_html_unordered_list(readiness.get("best_first_users"))}
        <p style="margin-top: 12px;"><strong>Do not build</strong></p>
        {_html_unordered_list(readiness.get("do_not_build"))}
      </div>
    </section>
    <div class="table-wrap" style="margin-top: 14px;">
      <table>
        <thead>
          <tr><th>Priority</th><th>Tool</th><th>Next move</th></tr>
        </thead>
        <tbody>{move_rows}</tbody>
      </table>
    </div>
"""


def _render_market_readiness_move_html(row: JsonDict) -> str:
    return (
        "<tr>"
        f"<td>{_html_text(row.get('priority', ''))}</td>"
        f"<td><strong>{_html_text(row.get('tool', ''))}</strong></td>"
        f"<td>{_html_text(row.get('move', ''))}</td>"
        "</tr>"
    )


def _html_unordered_list(value: object) -> str:
    items = _string_list(value)
    if not items:
        return "<p class=\"muted\">None recorded.</p>"
    return "<ul>" + "".join(f"<li>{_html_text(item)}</li>" for item in items) + "</ul>"


def _scorecard_html_rows(value: object) -> list[JsonDict]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _scorecard_summary(rows: list[JsonDict]) -> JsonDict:
    return {
        "tool_count": len(rows),
        "valid_count": sum(1 for row in rows if str(row.get("validity")) == "valid"),
        "needs_work_count": sum(
            1 for row in rows if str(row.get("gap_status")) == "needs_work"
        ),
        "missing_diagnostic_count": sum(
            len(row.get("missing_paper_diagnostics", []))
            for row in rows
            if isinstance(row.get("missing_paper_diagnostics"), list)
        ),
    }


def _render_matrix_html_row(row: JsonDict) -> str:
    missing = row.get("missing_paper_diagnostics")
    missing_text = (
        ", ".join(str(item) for item in missing)
        if isinstance(missing, list)
        else str(missing or "")
    )
    return (
        "<tr>"
        f"<td><strong>{_html_text(row.get('display_name', ''))}</strong></td>"
        f"<td>{_html_badge(row.get('prompt_only_validity'))}</td>"
        f"<td>{_html_badge(row.get('paired_stats'))}</td>"
        f"<td>{_html_artifact_status(row.get('evidence_card'), row.get('evidence_card_path'))}</td>"
        f"<td>{_html_artifact_status(row.get('claim_check'), row.get('claim_check_path'))}</td>"
        "<td>"
        f"{_html_artifact_status(row.get('research_bundle'), row.get('research_bundle_path'))}"
        "</td>"
        f"<td>{_html_badge(row.get('bundle_verification'))}</td>"
        f"<td>{_html_badge(row.get('gap_status'))}</td>"
        f"<td class=\"muted\">{_html_text(missing_text)}</td>"
        f"<td><code>{_html_text(row.get('next_command', ''))}</code></td>"
        "</tr>"
    )


def _render_scorecard_html_row(row: JsonDict) -> str:
    missing = row.get("missing_paper_diagnostics")
    missing_text = (
        ", ".join(str(item) for item in missing)
        if isinstance(missing, list)
        else str(missing or "")
    )
    gap_status = str(row.get("gap_status") or "")
    if row.get("gap_missing_count") is not None:
        gap_status = f"{gap_status} ({row.get('gap_missing_count')} missing)"
    return (
        "<tr>"
        f"<td><strong>{_html_text(row.get('display_name', ''))}</strong></td>"
        f"<td>{_html_text(row.get('external_strength', ''))}</td>"
        f"<td>{_html_text(row.get('pcl_adds', ''))}</td>"
        f"<td>{_html_badge(row.get('validity'))}</td>"
        f"<td>{_html_badge(row.get('evidence_tier'))}</td>"
        f"<td>{_html_badge(gap_status)}</td>"
        f"<td>{_html_text(_bundle_integrity_markdown(row.get('research_bundle_integrity')))}</td>"
        f"<td>{_html_artifact_links(row.get('artifact_links'))}</td>"
        f"<td class=\"muted\">{_html_text(missing_text)}</td>"
        f"<td>{_html_link(row.get('open_first'))}</td>"
        f"<td><code>{_html_text(row.get('gap_status_command', ''))}</code></td>"
        "</tr>"
    )


def _render_market_map_html_row(row: JsonDict) -> str:
    return (
        "<tr>"
        f"<td><strong>{_html_text(row.get('tool', ''))}</strong></td>"
        f"<td>{_html_text(row.get('strong_lane', ''))}</td>"
        f"<td>{_html_text(row.get('pcl_should_learn', ''))}</td>"
        f"<td>{_html_text(row.get('pcl_owns', ''))}</td>"
        f"<td>{_html_text(row.get('pcl_product_move', ''))}</td>"
        f"<td>{_html_badge(row.get('priority'))}</td>"
        f"<td>{_html_badge(row.get('status'))}</td>"
        "</tr>"
    )


def _html_artifact_links(value: object) -> str:
    if not isinstance(value, list):
        return ""
    links: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "")
        path = str(item.get("path") or "")
        if label and path:
            links.append(_html_link_with_label(path=path, label=label))
    return "<br>".join(links)


def _html_artifact_status(status: object, path: object) -> str:
    status_html = _html_badge(status)
    path_text = str(path or "")
    if not path_text:
        return status_html
    return f"{status_html}<br>{_html_link(path_text)}"


def _bundle_integrity_markdown(value: object) -> str:
    if not isinstance(value, dict) or not value:
        return ""
    status = str(value.get("status") or "")
    present = value.get("present_artifact_count")
    total = value.get("artifact_count")
    hashed = value.get("hashed_artifact_count")
    missing = value.get("missing_html_count")
    verification = value.get("verification_status") or "not_checked"
    mismatches = value.get("verification_mismatch_count", 0)
    missing_verified = value.get("verification_missing_count", 0)
    return (
        f"{status}; present {present}/{total}; hashed {hashed}; "
        f"verify {verification}; mismatches {mismatches}; missing {missing_verified}; "
        f"missing html {missing}"
    )


def _html_badge(value: object) -> str:
    text = str(value or "")
    return f'<span class="badge {_html_status_class(text)}">{_html_text(text)}</span>'


def _html_status_class(value: str) -> str:
    normalized = value.lower()
    if any(item in normalized for item in ["valid", "complete", "pass", "clean"]):
        return "good"
    if any(item in normalized for item in ["fail", "invalid", "blocked"]):
        return "bad"
    if any(
        item in normalized
        for item in ["needs", "missing", "unknown", "not_checked", "review"]
    ):
        return "warn"
    return "neutral"


def _html_link(value: object) -> str:
    text = str(value or "")
    if not text:
        return ""
    escaped = html.escape(text, quote=True)
    return f'<a href="{escaped}">{html.escape(text)}</a>'


def _html_link_with_label(*, path: str, label: str) -> str:
    escaped = html.escape(path, quote=True)
    return f'<a href="{escaped}">{_html_text(label)}</a>'


def _html_text(value: object) -> str:
    return html.escape(str(value or ""))


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _render_readme(payload: JsonDict) -> str:
    lines = [
        "# prompt_control_lab Ecosystem Demo",
        "",
        (
            "This directory shows how `prompt_control_lab` works as a prompt optimization "
            "evidence auditor for exports from Promptfoo, DeepEval, Langfuse, LangSmith, "
            "and prompt-optimizer."
        ),
        "",
        "It does not replace those tools. It adds paired statistics, prompt-only validity, "
        "evidence cards, claim checks, and research-diagnostic hooks on top of their exports.",
        "",
        (
            "Start with `ecosystem_scorecard.html` for the cross-tool positioning and "
            "gap-closure view. Use `ecosystem_scorecard.md` for plain-text review."
        ),
        "",
        "## Generated bundles",
        "",
        "| Tool | Validity | Evidence tier | Claim check | Open first |",
        "|---|---|---|---|---|",
    ]
    runs = payload.get("runs")
    if isinstance(runs, list):
        for run in runs:
            if not isinstance(run, dict):
                continue
            tool = run.get("tool", "")
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(tool),
                        str(run.get("validity", "")),
                        str(run.get("evidence_tier", "")),
                        str(run.get("claim_check_status", "")),
                        f"[bridge_summary.html]({tool}/bridge_summary.html)",
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Suggested review order",
            "",
            "1. Open `bridge_summary.html` for each tool.",
            "2. Open `research_bundle.html` for reviewer navigation.",
            "3. Check `evidence_card.html` for protocol and statistical evidence.",
            "4. Check `claim_check.html` before making any prompt optimization claim.",
            "5. Read `research_diagnostics.html` for paper-evidence gap coverage.",
            "6. Run `pcl gap-status --run <tool-dir>` after closing diagnostic gaps.",
            "7. Open `report.html` or `pcl ui --runs <this-dir>` for a visual review.",
            "",
        ]
    )
    return "\n".join(lines)
