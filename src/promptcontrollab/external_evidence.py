"""One-command evidence workflow for external eval/observability exports."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal

from promptcontrollab.files import JsonDict, ensure_dir, read_json, write_json
from promptcontrollab.ingest import (
    ingest_auto_results,
    ingest_langfuse_results,
    ingest_langsmith_results,
    ingest_promptfoo_results,
)
from promptcontrollab.run_comparison import compare_runs

ExternalTool = Literal["auto", "promptfoo", "langfuse", "langsmith"]


def build_external_evidence(
    *,
    tool: ExternalTool,
    baseline_input: Path,
    candidate_input: Path,
    out_dir: Path,
    score_name: str | None = None,
    provider: str | None = None,
    baseline_provider: str | None = None,
    candidate_provider: str | None = None,
    model: str | None = None,
    baseline_model: str | None = None,
    candidate_model: str | None = None,
    baseline_prompt_id: str | None = None,
    candidate_prompt_id: str | None = None,
    baseline_name: str | None = None,
    candidate_name: str | None = None,
    baseline_experiment: str | None = None,
    candidate_experiment: str | None = None,
    split_hash: str | None = None,
    baseline_method: str = "baseline",
    candidate_method: str = "candidate",
    title: str = "PromptControlLab External Evidence",
    seed: int = 0,
    bootstrap_samples: int = 1000,
    permutation_samples: int = 1000,
) -> JsonDict:
    """Import two external exports, compare them, and write a compact evidence bundle."""

    if out_dir.exists() and any(out_dir.iterdir()):
        msg = f"External evidence output directory must be empty: {out_dir}"
        raise ValueError(msg)
    ensure_dir(out_dir)

    imports_dir = out_dir / "imports"
    baseline_dir = imports_dir / "baseline"
    candidate_dir = imports_dir / "candidate"
    baseline_payload = _ingest_one(
        tool=tool,
        source_path=baseline_input,
        out_dir=baseline_dir,
        score_name=score_name,
        provider=baseline_provider or provider,
        model=baseline_model or model,
        prompt_id=baseline_prompt_id,
        name=baseline_name,
        experiment=baseline_experiment,
        method=baseline_method,
    )
    candidate_payload = _ingest_one(
        tool=tool,
        source_path=candidate_input,
        out_dir=candidate_dir,
        score_name=score_name,
        provider=candidate_provider or provider,
        model=candidate_model or model,
        prompt_id=candidate_prompt_id,
        name=candidate_name,
        experiment=candidate_experiment,
        method=candidate_method,
    )
    _patch_manifest(
        baseline_dir,
        split_hash=split_hash,
        prompt_id=baseline_prompt_id,
    )
    _patch_manifest(
        candidate_dir,
        split_hash=split_hash,
        prompt_id=candidate_prompt_id,
    )

    comparison_dir = out_dir / "comparison"
    comparison_payload = compare_runs(
        baseline_dir=baseline_dir,
        candidate_dir=candidate_dir,
        out_dir=comparison_dir,
        title=title,
        seed=seed,
        bootstrap_samples=bootstrap_samples,
        permutation_samples=permutation_samples,
    )
    copied_artifacts = _copy_headline_artifacts(comparison_dir=comparison_dir, out_dir=out_dir)
    bridge_summary = _write_bridge_summary(
        out_dir=out_dir,
        requested_tool=tool,
        baseline_payload=baseline_payload,
        candidate_payload=candidate_payload,
        comparison_dir=comparison_dir,
    )
    payload: JsonDict = {
        "kind": "external_evidence",
        "tool": tool,
        "detected_tools": bridge_summary.get("detected_tools", []),
        "out_dir": str(out_dir),
        "imports_dir": str(imports_dir),
        "baseline_import": baseline_payload,
        "candidate_import": candidate_payload,
        "comparison_dir": str(comparison_dir),
        "comparison": {
            "stats_path": comparison_payload.get("stats_path"),
            "comparison_validity_path": comparison_payload.get("comparison_validity_path"),
            "evidence_card_path": comparison_payload.get("evidence_card_path"),
            "report_md": comparison_payload.get("report_md"),
            "report_html": comparison_payload.get("report_html"),
            "evidence_card": comparison_payload.get("evidence_card"),
        },
        "bridge_summary": {
            "json_path": str(out_dir / "bridge_summary.json"),
            "markdown_path": str(out_dir / "bridge_summary.md"),
            "recommendation": bridge_summary.get("recommendation"),
            "validity": bridge_summary.get("validity"),
            "missing_evidence": bridge_summary.get("missing_evidence", []),
        },
        "copied_artifacts": [str(path) for path in copied_artifacts],
        "next_actions": [
            "Open bridge_summary.md to see what the external tool supplied and what PCL added.",
            "Open evidence_card.md for the compact prompt optimization evidence card.",
            "Open report.html for the full comparison dashboard.",
            "Review imports/baseline and imports/candidate if provenance looks incomplete.",
        ],
    }
    write_json(out_dir / "evidence_from_result.json", payload)
    return payload


def _ingest_one(
    *,
    tool: ExternalTool,
    source_path: Path,
    out_dir: Path,
    score_name: str | None,
    provider: str | None,
    model: str | None,
    prompt_id: str | None,
    name: str | None,
    experiment: str | None,
    method: str,
) -> JsonDict:
    if tool == "auto":
        return ingest_auto_results(
            source_path=source_path,
            out_dir=out_dir,
            prompt_id=prompt_id,
            name=name,
            experiment=experiment,
            score_name=score_name,
            model=model,
            provider=provider,
            method=method,
        )
    if tool == "promptfoo":
        return ingest_promptfoo_results(
            source_path=source_path,
            out_dir=out_dir,
            prompt_id=prompt_id,
            provider=provider,
            method=method,
        )
    if tool == "langfuse":
        return ingest_langfuse_results(
            source_path=source_path,
            out_dir=out_dir,
            name=name,
            score_name=score_name,
            model=model,
            provider=provider,
            method=method,
        )
    if tool == "langsmith":
        return ingest_langsmith_results(
            source_path=source_path,
            out_dir=out_dir,
            experiment=experiment,
            score_name=score_name,
            model=model,
            provider=provider,
            method=method,
        )
    msg = f"Unsupported external evidence tool: {tool}"
    raise ValueError(msg)


def _patch_manifest(
    run_dir: Path,
    *,
    split_hash: str | None,
    prompt_id: str | None,
) -> None:
    manifest_path = run_dir / "manifest.json"
    manifest = read_json(manifest_path)
    if split_hash:
        manifest["split_hash"] = split_hash
    if prompt_id:
        prompt = manifest.get("prompt")
        prompt_payload = prompt if isinstance(prompt, dict) else {}
        prompt_payload.setdefault("prompt_id", prompt_id)
        manifest["prompt"] = prompt_payload
    write_json(manifest_path, manifest)


def _copy_headline_artifacts(*, comparison_dir: Path, out_dir: Path) -> list[Path]:
    names = [
        "evidence_card.json",
        "evidence_card.md",
        "report.md",
        "report.html",
        "stats.json",
        "comparison_validity.json",
        "comparison_validity.md",
    ]
    copied: list[Path] = []
    for name in names:
        source = comparison_dir / name
        if not source.exists():
            continue
        target = out_dir / name
        shutil.copy2(source, target)
        copied.append(target)
    return copied


def _write_bridge_summary(
    *,
    out_dir: Path,
    requested_tool: ExternalTool,
    baseline_payload: JsonDict,
    candidate_payload: JsonDict,
    comparison_dir: Path,
) -> JsonDict:
    evidence_card = _read_optional_json(comparison_dir / "evidence_card.json")
    validity = _read_optional_json(comparison_dir / "comparison_validity.json")
    stats = _read_optional_json(comparison_dir / "stats.json")
    comparison = _first_comparison(stats)
    detected_tools = _detected_tools(requested_tool, baseline_payload, candidate_payload)
    missing = evidence_card.get("missing_artifacts")
    missing_evidence = missing if isinstance(missing, list) else []
    payload: JsonDict = {
        "kind": "external_bridge_summary",
        "requested_tool": requested_tool,
        "detected_tools": detected_tools,
        "source_tool_roles": [_tool_role(tool) for tool in detected_tools],
        "pcl_role": (
            "PCL converts external eval/observability exports into a paired prompt "
            "optimization evidence bundle with statistics, prompt-only validity checks, "
            "and paper-derived diagnostic hooks."
        ),
        "pcl_added_evidence": [
            "paired_bootstrap_confidence_interval",
            "paired_permutation_p_value",
            "holm_adjusted_p_value",
            "prompt_only_comparison_validity",
            "evidence_card",
            "local_archivable_report",
        ],
        "recommendation": evidence_card.get("recommendation", "needs_review"),
        "summary": evidence_card.get("summary", ""),
        "validity": validity.get("validity", "unknown"),
        "prompt_only_comparison": validity.get("prompt_only_comparison"),
        "mean_delta": comparison.get("mean_delta"),
        "bootstrap_ci": comparison.get("bootstrap_ci"),
        "permutation_p_value": comparison.get("permutation_p_value"),
        "holm_adjusted_p_value": comparison.get("holm_adjusted_p_value"),
        "paired_n": comparison.get("n"),
        "missing_evidence": missing_evidence,
        "review_items": validity.get("review_items", []),
        "blocking_issues": validity.get("blocking_issues", []),
        "next_actions": _bridge_next_actions(
            recommendation=str(evidence_card.get("recommendation", "needs_review")),
            validity=str(validity.get("validity", "unknown")),
            missing_evidence=missing_evidence,
        ),
        "boundary": (
            "This bridge does not replace the external tool. It records how external "
            "results were converted into PCL artifacts and highlights whether the "
            "result is strong enough for a prompt optimization claim."
        ),
    }
    write_json(out_dir / "bridge_summary.json", payload)
    (out_dir / "bridge_summary.md").write_text(_render_bridge_summary(payload), encoding="utf-8")
    return payload


def _read_optional_json(path: Path) -> JsonDict:
    if not path.exists():
        return {}
    return read_json(path)


def _first_comparison(stats: JsonDict) -> JsonDict:
    comparisons = stats.get("comparisons")
    if isinstance(comparisons, list) and comparisons and isinstance(comparisons[0], dict):
        return comparisons[0]
    return stats


def _detected_tools(
    requested_tool: ExternalTool,
    baseline_payload: JsonDict,
    candidate_payload: JsonDict,
) -> list[str]:
    values = [
        baseline_payload.get("source_tool"),
        candidate_payload.get("source_tool"),
    ]
    tools = [str(value) for value in values if isinstance(value, str) and value]
    if not tools and requested_tool != "auto":
        tools = [requested_tool]
    return sorted(set(tools))


def _tool_role(tool: str) -> JsonDict:
    roles = {
        "promptfoo": {
            "tool": "promptfoo",
            "display_name": "Promptfoo",
            "role": "evals, provider matrices, red-team/security tests, and CI reports",
            "pcl_adds": (
                "paired statistical evidence, prompt-only validity, and paper-style diagnostics"
            ),
        },
        "langfuse": {
            "tool": "langfuse",
            "display_name": "Langfuse",
            "role": (
                "open-source tracing, prompt management, scores, costs, and self-hosted "
                "observability"
            ),
            "pcl_adds": (
                "export-to-evidence conversion, paired validity checks, and local evidence cards"
            ),
        },
        "langsmith": {
            "tool": "langsmith",
            "display_name": "LangSmith",
            "role": "agent tracing, datasets, online/offline evals, and production debugging",
            "pcl_adds": "prompt optimization evidence cards and comparison confound checks",
        },
    }
    return roles.get(
        tool,
        {
            "tool": tool,
            "display_name": tool,
            "role": "external eval or observability export",
            "pcl_adds": "paired prompt optimization evidence and diagnostics",
        },
    )


def _bridge_next_actions(
    *,
    recommendation: str,
    validity: str,
    missing_evidence: list[object],
) -> list[str]:
    actions = [
        "Archive imports/, comparison/, evidence_card.md, and report.html together.",
    ]
    if validity != "clean":
        actions.append(
            "Fix comparison-validity review items before claiming a clean prompt-only comparison."
        )
    if missing_evidence:
        actions.append("Run the missing diagnostics that matter for your claim.")
    if recommendation == "supported" and validity == "clean":
        actions.append(
            "Use the evidence card as reviewer-facing support, with the stated boundary."
        )
    else:
        actions.append("Treat this as useful evidence, not a final benchmark claim.")
    return actions


def _render_bridge_summary(payload: JsonDict) -> str:
    lines = [
        "# External Evidence Bridge Summary",
        "",
        f"- Requested tool: `{payload.get('requested_tool')}`",
        f"- Detected tools: `{payload.get('detected_tools', [])}`",
        f"- Recommendation: `{payload.get('recommendation')}`",
        f"- Validity: `{payload.get('validity')}`",
        f"- Paired n: `{payload.get('paired_n')}`",
        f"- Mean delta: `{payload.get('mean_delta')}`",
        f"- Bootstrap CI: `{payload.get('bootstrap_ci')}`",
        f"- Permutation p-value: `{payload.get('permutation_p_value')}`",
        f"- Holm-adjusted p-value: `{payload.get('holm_adjusted_p_value')}`",
        "",
        "## Tool roles",
        "",
    ]
    roles = payload.get("source_tool_roles")
    if isinstance(roles, list):
        for role in roles:
            if not isinstance(role, dict):
                continue
            lines.extend(
                [
                    f"### {role.get('display_name') or role.get('tool')}",
                    "",
                    f"- External tool role: {role.get('role')}",
                    f"- What PCL adds: {role.get('pcl_adds')}",
                    "",
                ]
            )
    lines.extend(
        [
            "## PCL added evidence",
            "",
            *[f"- `{item}`" for item in _string_list(payload.get("pcl_added_evidence"))],
            "",
            "## Missing or review evidence",
            "",
            f"- Missing evidence: `{payload.get('missing_evidence', [])}`",
            f"- Review items: `{payload.get('review_items', [])}`",
            f"- Blocking issues: `{payload.get('blocking_issues', [])}`",
            "",
            "## Next actions",
            "",
            *[f"- {item}" for item in _string_list(payload.get("next_actions"))],
            "",
            "## Boundary",
            "",
            str(payload.get("boundary", "")),
            "",
        ]
    )
    return "\n".join(lines)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]
