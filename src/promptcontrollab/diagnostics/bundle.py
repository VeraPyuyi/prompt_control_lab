"""Build, verify, and summarize research diagnostic artifact bundles."""

from __future__ import annotations

import hashlib
from pathlib import Path

from promptcontrollab.core.files import JsonDict, ensure_dir, read_json, write_json
from promptcontrollab.diagnostics.bundle_renderers import (
    _render_research_bundle_verification_markdown,
    render_research_bundle_index_html,
    render_research_bundle_index_markdown,
    render_research_bundle_verification_html,
)
from promptcontrollab.diagnostics.common import (
    _dedupe_remediation,
    _read_optional_json,
    _remediation_list,
)
from promptcontrollab.diagnostics.constants import PAPER_MAPPING, PAPER_REMEDIATION


def write_research_bundle_index(run_dir: Path) -> JsonDict:
    """Write a browser-first index for the research evidence bundle."""

    ensure_dir(run_dir)
    payload = build_research_bundle_index(run_dir)
    out_path = run_dir / "research_bundle.html"
    out_path.write_text(render_research_bundle_index_html(payload), encoding="utf-8")
    markdown_path = run_dir / "research_bundle.md"
    markdown_path.write_text(
        render_research_bundle_index_markdown(payload),
        encoding="utf-8",
    )
    zh_path = run_dir / "research_bundle.zh.html"
    zh_path.write_text(
        render_research_bundle_index_html(payload, language="zh"),
        encoding="utf-8",
    )
    payload["html_path"] = str(out_path)
    payload["markdown_path"] = str(markdown_path)
    payload["html_zh_path"] = str(zh_path)
    write_json(run_dir / "research_bundle.json", payload)
    return payload


def verify_research_bundle_index(run_dir: Path) -> JsonDict:
    """Verify hashes recorded in an existing research bundle index."""

    bundle_path = run_dir / "research_bundle.json"
    if not bundle_path.exists():
        msg = f"Research bundle index does not exist: {bundle_path}"
        raise ValueError(msg)
    bundle = read_json(bundle_path)
    artifacts = bundle.get("artifacts")
    rows = artifacts if isinstance(artifacts, list) else []
    results = [_verify_bundle_artifact(run_dir=run_dir, item=item) for item in rows]
    checked = [item for item in results if item.get("status") in {"ok", "mismatch", "missing"}]
    mismatches = [item for item in results if item.get("status") == "mismatch"]
    missing = [item for item in results if item.get("status") == "missing"]
    payload: JsonDict = {
        "kind": "research_bundle_verification",
        "run_dir": str(run_dir),
        "bundle_path": str(bundle_path),
        "status": "pass" if not mismatches and not missing else "fail",
        "checked_count": len(checked),
        "ok_count": sum(1 for item in results if item.get("status") == "ok"),
        "mismatch_count": len(mismatches),
        "missing_count": len(missing),
        "unchecked_count": sum(1 for item in results if item.get("status") == "unchecked"),
        "self_index_count": sum(1 for item in results if item.get("status") == "self_index"),
        "results": results,
        "boundary": (
            "This check verifies recorded SHA-256 values for linked evidence artifacts. "
            "It is tamper-evidence for this local bundle, not a cryptographic signature "
            "or proof of scientific sufficiency."
        ),
    }
    write_json(run_dir / "research_bundle_verification.json", payload)
    (run_dir / "research_bundle_verification.md").write_text(
        _render_research_bundle_verification_markdown(payload),
        encoding="utf-8",
    )
    (run_dir / "research_bundle_verification.html").write_text(
        render_research_bundle_verification_html(payload),
        encoding="utf-8",
    )
    return payload


def _verify_bundle_artifact(*, run_dir: Path, item: object) -> JsonDict:
    if not isinstance(item, dict):
        return {"path": "", "status": "unchecked", "reason": "invalid artifact row"}
    relative = str(item.get("path") or "")
    path = run_dir / relative
    expected = item.get("sha256")
    if item.get("generated_index_artifact"):
        return {
            "path": relative,
            "status": "self_index",
            "expected_sha256": expected,
            "reason": "generated index artifacts are not self-hashed",
        }
    if not expected:
        return {
            "path": relative,
            "status": "unchecked",
            "expected_sha256": None,
            "reason": "no recorded sha256",
        }
    if not path.exists() or not path.is_file():
        return {
            "path": relative,
            "status": "missing",
            "expected_sha256": expected,
            "actual_sha256": None,
        }
    actual = _sha256_file(path)
    return {
        "path": relative,
        "status": "ok" if actual == expected else "mismatch",
        "expected_sha256": expected,
        "actual_sha256": actual,
        "bytes": path.stat().st_size,
    }


def build_research_bundle_index(run_dir: Path) -> JsonDict:
    """Collect known research artifacts into one navigable index payload."""

    artifacts = _bundle_artifacts(run_dir)
    present_artifacts = [item for item in artifacts if item.get("exists")]
    hashed_artifacts = [item for item in present_artifacts if item.get("sha256")]
    diagnostics = _read_optional_research_json(run_dir / "research_diagnostics.json")
    evidence = _read_optional_research_json(run_dir / "evidence_card.json")
    claim = _read_optional_research_json(run_dir / "claim_check.json")
    gap_status = _read_optional_research_json(run_dir / "research_gap_status.json")
    gap_plan = _read_optional_research_json(run_dir / "research_gap_plan.json")
    peoc_evidence = _read_optional_research_json(run_dir / "peoc_evidence.json")
    peoc_case_study = _read_optional_research_json(run_dir / "research_case_study.json")
    manifest = _read_optional_research_json(run_dir / "manifest.json")
    diagnostics_payload = diagnostics.get("diagnostics")
    diagnostics_dict = diagnostics_payload if isinstance(diagnostics_payload, dict) else {}
    status = _bundle_status(
        evidence=evidence,
        claim=claim,
        gap_status=gap_status,
        gap_plan=gap_plan,
    )
    evidence_tier = evidence.get("evidence_tier") or claim.get("evidence_tier")
    peoc_origin = _peoc_evidence_origin(
        evidence=peoc_evidence,
        case_study=peoc_case_study,
        manifest=manifest,
    )
    claim_status = claim.get("status")
    gap_status_value = gap_status.get("status") or ("planned" if gap_plan else "not_planned")
    expected = [
        "research_diagnostics.html",
        "evidence_card.html",
        "claim_check.html",
        "research_gap_plan.html",
        "research_gap_status.html",
        "report.html",
    ]
    return {
        "kind": "research_bundle_index",
        "run_dir": str(run_dir),
        "status": status,
        "recommendation": evidence.get("recommendation") or claim.get("status") or "review",
        **({"evidence_origin": peoc_origin} if peoc_origin else {}),
        "evidence_tier": evidence_tier,
        "evidence_tier_label": _readable_bundle_evidence_tier(str(evidence_tier or "")),
        "evidence_tier_label_zh": _readable_bundle_evidence_tier(
            str(evidence_tier or ""),
            language="zh",
        ),
        "claim_check_status": claim_status,
        "claim_language": claim.get("safe_claim_language") or evidence.get("claim_language"),
        "diagnostic_type": diagnostics.get("diagnostic_type") or diagnostics.get("mode"),
        "diagnostics_present": sorted(diagnostics_dict),
        "gap_status": gap_status_value,
        "gap_complete_count": gap_status.get("complete_count"),
        "gap_missing_count": gap_status.get("missing_count"),
        "plain_summary": _research_bundle_plain_summary(
            status=status,
            evidence_tier=evidence_tier,
            claim_status=claim_status,
            diagnostics_present=sorted(diagnostics_dict),
            gap_status=gap_status_value,
            language="en",
        ),
        "plain_summary_zh": _research_bundle_plain_summary(
            status=status,
            evidence_tier=evidence_tier,
            claim_status=claim_status,
            diagnostics_present=sorted(diagnostics_dict),
            gap_status=gap_status_value,
            language="zh",
        ),
        "review_order": _bundle_review_order(run_dir),
        "artifacts": artifacts,
        "artifact_count": len(artifacts),
        "present_artifact_count": len(present_artifacts),
        "hashed_artifact_count": len(hashed_artifacts),
        "missing_html_artifacts": [name for name in expected if not (run_dir / name).exists()],
        "boundary": (
            "This index is a navigation aid. It does not add evidence beyond the linked "
            "artifacts and does not prove scientific sufficiency."
        ),
    }


def _readable_bundle_evidence_tier(value: str, *, language: str = "en") -> str:
    if language == "zh":
        labels = {
            "tier_0_insufficient_or_contradicted": "证据不足或互相矛盾",
            "tier_1_incomplete_comparison": "比较证据不完整",
            "tier_2_paired_comparison": "成对比较证据",
            "tier_3_partial_research_diagnostics": "部分研究诊断",
            "tier_4_full_research_diagnostics": "完整研究诊断",
        }
        return labels.get(value, value.replace("_", " ") if value else "未记录")
    labels = {
        "tier_0_insufficient_or_contradicted": "insufficient or contradicted evidence",
        "tier_1_incomplete_comparison": "incomplete comparison",
        "tier_2_paired_comparison": "paired comparison",
        "tier_3_partial_research_diagnostics": "partial research diagnostics",
        "tier_4_full_research_diagnostics": "full research diagnostics",
    }
    return labels.get(value, value.replace("_", " ") if value else "not recorded")


def _research_bundle_plain_summary(
    *,
    status: str,
    evidence_tier: object,
    claim_status: object,
    diagnostics_present: list[str],
    gap_status: str,
    language: str = "en",
) -> list[str]:
    diagnostics = ", ".join(
        _readable_diagnostic_name(name, language=language) for name in diagnostics_present
    )
    if language == "zh":
        diagnostics_text = diagnostics or "还没有论文诊断"
        tier = _readable_bundle_evidence_tier(str(evidence_tier or ""), language="zh")
        claim = _readable_bundle_status(str(claim_status or "missing"), language="zh")
        gap = _readable_bundle_status(gap_status, language="zh")
        bundle = _readable_bundle_status(status, language="zh")
        return [
            "先打开 research_diagnostics.html, 用直白语言查看论文诊断。",
            f"当前证据层级是 {tier}, 主张检查状态是 {claim}。",
            f"包含的诊断: {diagnostics_text}。",
            f"gap 状态是 {gap}, 证据包状态是 {bundle}。",
            (
                "在提出较强的 prompt optimization 主张前, 先看 claim_check.html; "
                "这个页面是证据导航, 不是证明本身。"
            ),
        ]
    diagnostics_text = diagnostics or "no paper diagnostics yet"
    tier = _readable_bundle_evidence_tier(str(evidence_tier or ""), language="en")
    claim = _readable_bundle_status(str(claim_status or "missing"), language="en")
    gap = _readable_bundle_status(gap_status, language="en")
    bundle = _readable_bundle_status(status, language="en")
    return [
        ("Start with research_diagnostics.html to see the paper-derived checks in plain language."),
        f"This bundle currently has {tier} with claim check status {claim}.",
        f"Included diagnostics: {diagnostics_text}.",
        f"Gap status is {gap} and bundle status is {bundle}.",
        (
            "Use claim_check.html before making a broad prompt-optimization claim; "
            "the bundle is evidence navigation, not a proof by itself."
        ),
    ]


def _readable_diagnostic_name(name: str, *, language: str = "en") -> str:
    if language == "zh":
        labels = {
            "soft_hard": "soft-hard gap",
            "trajectory": "hidden-state trajectory",
            "riccati": "Riccati surrogate",
            "tv_soft": "time-varying soft-control",
            "terminal_sensitivity": "终端敏感度",
            "green_certificate": "Green 边界证书",
            "posterior_certificate": "局部后验证书",
        }
        return labels.get(name, name.replace("_", "-"))
    labels = {
        "soft_hard": "soft-hard gap",
        "trajectory": "hidden-state trajectory",
        "riccati": "Riccati surrogate",
        "tv_soft": "time-varying soft-control",
        "terminal_sensitivity": "terminal sensitivity",
        "green_certificate": "Green boundary certificate",
        "posterior_certificate": "posterior local certificate",
    }
    return labels.get(name, name.replace("_", "-"))


def _readable_bundle_status(value: str, *, language: str = "en") -> str:
    if language == "zh":
        labels = {
            "pass": "通过",
            "supported": "已支持",
            "review": "需要复查",
            "needs_review": "需要复查",
            "needs_work": "需要补证据",
            "not_planned": "未规划补证据",
            "gap_status_not_checked": "尚未检查 gap 状态",
            "incomplete": "不完整",
            "missing": "缺失",
        }
        return labels.get(value, value.replace("_", " ") if value else "缺失")
    labels = {
        "pass": "pass",
        "supported": "supported",
        "review": "needs review",
        "needs_review": "needs review",
        "needs_work": "needs work",
        "not_planned": "not planned",
        "gap_status_not_checked": "gap status not checked",
        "incomplete": "incomplete",
        "missing": "missing",
    }
    return labels.get(value, value.replace("_", " ") if value else "missing")


def _read_optional_research_json(path: Path) -> JsonDict:
    if not path.exists():
        return {}
    return read_json(path)


def _peoc_evidence_origin(
    *,
    evidence: JsonDict,
    case_study: JsonDict,
    manifest: JsonDict,
) -> str | None:
    case_origin = case_study.get("evidence_origin")
    if isinstance(case_origin, str) and case_origin:
        return case_origin
    manifest_origin = manifest.get("evidence_origin")
    if manifest.get("adapter") == "peoc" and isinstance(manifest_origin, str) and manifest_origin:
        return manifest_origin
    sections_value = evidence.get("sections")
    if isinstance(sections_value, dict) and any(
        isinstance(section, dict) and section.get("origin") == "real"
        for section in sections_value.values()
    ):
        return "real"
    return None


def _bundle_status(
    *,
    evidence: JsonDict,
    claim: JsonDict,
    gap_status: JsonDict,
    gap_plan: JsonDict,
) -> str:
    if claim.get("status") == "fail":
        return "needs_review"
    if gap_status.get("status") == "needs_work":
        return "needs_work"
    if gap_plan and not gap_status:
        return "gap_status_not_checked"
    if evidence.get("recommendation") == "supported" and claim.get("status") == "pass":
        return "supported"
    if evidence or claim:
        return "review"
    return "incomplete"


def _bundle_review_order(run_dir: Path) -> list[JsonDict]:
    """Build the ordered reviewer entry points available in one research run."""

    candidates = [
        (
            "Evidence audit",
            "evidence_audit_result.html",
            "One-command audit summary for external imports, gaps, and bundle verification.",
        ),
        (
            "Bridge summary",
            "bridge_summary.html",
            "External-tool provenance, PCL-added evidence, and next review actions.",
        ),
        (
            "Start here",
            "research_diagnostics.html",
            "Paper-derived diagnostic coverage and missing evidence.",
        ),
    ]
    if (run_dir / "peoc_evidence.json").exists() or (run_dir / "research_case_study.html").exists():
        candidates.append(
            (
                "Real PEOC case study",
                "research_case_study.html",
                "Imported real replication results, limitations, and claim boundary.",
            )
        )
    candidates.extend(
        [
            ("Evidence card", "evidence_card.html", "Compact prompt optimization evidence card."),
            (
                "Claim check",
                "claim_check.html",
                "Strongest claim currently supported by the artifact bundle.",
            ),
            (
                "Gap plan",
                "research_gap_plan.html",
                "Commands and inputs needed to close missing paper diagnostics.",
            ),
            (
                "Gap status",
                "research_gap_status.html",
                "Whether expected gap-closing artifacts currently exist.",
            ),
            ("Full report", "report.html", "Full run comparison report when available."),
        ]
    )
    return [
        {
            "label": label,
            "path": path,
            "exists": (run_dir / path).exists(),
            "explains": explains,
        }
        for label, path, explains in candidates
    ]


def _bundle_artifacts(run_dir: Path) -> list[JsonDict]:
    """Describe the expected research-bundle artifacts and their availability."""

    names = [
        "research_bundle.html",
        "research_bundle.md",
        "research_bundle.zh.html",
        "research_bundle.json",
        "research_overview.svg",
        "source_manifest.json",
        "peoc_evidence.json",
        "research_case_study.html",
        "research_case_study.md",
        "research_case_study.json",
        "evidence_audit_result.html",
        "evidence_audit_result.md",
        "evidence_audit_result.json",
        "evidence_gate_result.html",
        "evidence_gate_result.md",
        "evidence_gate_result.json",
        "research_bundle_verification.html",
        "research_bundle_verification.md",
        "research_bundle_verification.json",
        "source_input_verification.html",
        "source_input_verification.md",
        "source_input_verification.json",
        "research_diagnostics.html",
        "research_diagnostics.md",
        "research_diagnostics.json",
        "bridge_summary.html",
        "bridge_summary.md",
        "bridge_summary.json",
        "evidence_card.html",
        "evidence_card.md",
        "evidence_card.json",
        "claim_check.html",
        "claim_check.md",
        "claim_check.json",
        "research_gap_plan.html",
        "research_gap_plan.md",
        "research_gap_plan.json",
        "research_gap_status.html",
        "research_gap_status.md",
        "research_gap_status.json",
        "report.html",
        "report.md",
        "eval_scaffold/README.md",
        "eval_scaffold/prompt_optimizer_eval_scaffold.json",
        "eval_scaffold/promptcontrol.prompt_optimizer.example.yaml",
        "eval_scaffold/tasks.template.jsonl",
        "eval_scaffold/baseline_predictions.template.jsonl",
        "eval_scaffold/candidate_predictions.template.jsonl",
        "eval_scaffold/scaffold_check.html",
        "eval_scaffold/scaffold_check.md",
        "eval_scaffold/scaffold_check.json",
    ]
    names.extend(_eval_scaffold_prompt_artifacts(run_dir))
    return [_bundle_artifact_row(run_dir=run_dir, name=name) for name in names]


def _eval_scaffold_prompt_artifacts(run_dir: Path) -> list[str]:
    prompt_dir = run_dir / "eval_scaffold" / "prompts"
    if not prompt_dir.exists():
        return []
    return [
        str(path.relative_to(run_dir)).replace("\\", "/")
        for path in sorted(prompt_dir.glob("*.txt"))
        if path.is_file()
    ]


def _bundle_artifact_row(*, run_dir: Path, name: str) -> JsonDict:
    path = run_dir / name
    self_generated = name in {
        "research_bundle.html",
        "research_bundle.md",
        "research_bundle.zh.html",
        "research_bundle.json",
    }
    audit_summary = name.startswith("evidence_audit_result.") or name.startswith(
        "evidence_gate_result."
    )
    exists = path.exists() or self_generated
    row: JsonDict = {
        "path": name,
        "exists": exists,
        "role": _artifact_role(name),
    }
    if self_generated:
        row["generated_index_artifact"] = True
        if not path.exists():
            row["hash_status"] = "generated_during_refresh"
            return row
        row["hash_status"] = "self_index_not_hashed"
        return row
    if audit_summary and path.exists():
        row["bytes"] = path.stat().st_size
        row["hash_status"] = "audit_summary_not_hashed"
        return row
    if path.exists() and path.is_file():
        row["bytes"] = path.stat().st_size
        row["sha256"] = _sha256_file(path)
        row["hash_status"] = "hashed"
    return row


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _artifact_role(name: str) -> str:
    if name.endswith(".html"):
        return "browser_review"
    if name.endswith(".json"):
        return "automation"
    if name.endswith(".md"):
        return "text_review"
    return "artifact"


def _summarize_ecosystem_bundle(*, run_dir: Path, payload: JsonDict) -> JsonDict:
    runs = payload.get("runs")
    rows: list[JsonDict] = []
    if isinstance(runs, list):
        for item in runs:
            if not isinstance(item, dict):
                continue
            tool_dir = _ecosystem_tool_dir(run_dir=run_dir, item=item)
            rows.append(_summarize_external_bundle(run_dir=tool_dir, fallback=item))
    remediation_items: list[JsonDict] = []
    for row in rows:
        remediation_items.extend(_remediation_list(row.get("paper_gap_remediation")))
    remediation = _dedupe_remediation(remediation_items)
    return {
        "tool_count": len(rows),
        "runs": rows,
        "missing_research_diagnostics": sorted(
            {str(missing) for row in rows for missing in row.get("missing_paper_diagnostics", [])}
        ),
        "paper_gap_remediation": remediation,
        "review_first": [
            str(row.get("bridge_summary_path")) for row in rows if row.get("bridge_summary_path")
        ],
    }


def _ecosystem_tool_dir(*, run_dir: Path, item: JsonDict) -> Path:
    out_dir = item.get("out_dir")
    if isinstance(out_dir, str) and out_dir:
        candidate = Path(out_dir)
        if candidate.exists():
            return candidate
    tool = item.get("tool")
    if isinstance(tool, str) and tool:
        return run_dir / tool
    return run_dir


def _summarize_external_bundle(*, run_dir: Path, fallback: JsonDict) -> JsonDict:
    bridge = _read_optional_json(run_dir / "bridge_summary.json")
    claim = _read_optional_json(run_dir / "claim_check.json")
    evidence = _read_optional_json(run_dir / "evidence_card.json")
    validity = _read_optional_json(run_dir / "comparison_validity.json")
    stats = _read_optional_json(run_dir / "stats.json")
    tool = _external_tool_name(bridge=bridge, fallback=fallback)
    coverage = _paper_coverage_rows(run_dir)
    missing_paper_diagnostics = [
        row["concept"]
        for row in coverage
        if row["category"] == "research_diagnostic" and row["status"] == "missing"
    ]
    paper_gap_remediation = [
        row["remediation"]
        for row in coverage
        if row["category"] in {"research_diagnostic", "research_input"}
        and row["status"] == "missing"
        and isinstance(row.get("remediation"), dict)
    ]
    return {
        "tool": tool,
        "display_name": _display_tool_name(tool),
        "run_dir": str(run_dir),
        "validity": bridge.get("validity") or validity.get("validity") or fallback.get("validity"),
        "evidence_tier": bridge.get("evidence_tier")
        or evidence.get("evidence_tier")
        or fallback.get("evidence_tier"),
        "claim_check_status": bridge.get("claim_check_status")
        or claim.get("status")
        or fallback.get("claim_check_status"),
        "recommendation": bridge.get("recommendation") or evidence.get("recommendation"),
        "mean_delta": bridge.get("mean_delta") or _first_stats_comparison(stats).get("mean_delta"),
        "permutation_p_value": bridge.get("permutation_p_value")
        or _first_stats_comparison(stats).get("permutation_p_value"),
        "paper_coverage": coverage,
        "missing_paper_diagnostics": missing_paper_diagnostics,
        "paper_gap_remediation": paper_gap_remediation,
        "missing_evidence": bridge.get("missing_evidence", fallback.get("missing_evidence", [])),
        "next_actions": bridge.get("next_actions", fallback.get("next_actions", [])),
        "bridge_summary_path": str(run_dir / "bridge_summary.html")
        if (run_dir / "bridge_summary.html").exists()
        else str(run_dir / "bridge_summary.md")
        if (run_dir / "bridge_summary.md").exists()
        else fallback.get("bridge_summary_path"),
        "report_html_path": str(run_dir / "report.html")
        if (run_dir / "report.html").exists()
        else fallback.get("report_html_path"),
    }


def _first_stats_comparison(stats: JsonDict) -> JsonDict:
    comparisons = stats.get("comparisons")
    if isinstance(comparisons, list) and comparisons and isinstance(comparisons[0], dict):
        return comparisons[0]
    return stats


def _external_tool_name(*, bridge: JsonDict, fallback: JsonDict) -> str:
    for value in [
        fallback.get("tool"),
        bridge.get("requested_tool"),
    ]:
        if isinstance(value, str) and value:
            return value
    detected = bridge.get("detected_tools")
    if isinstance(detected, list) and detected:
        first = detected[0]
        if isinstance(first, str) and first:
            return first
    return "external"


def _display_tool_name(tool: object) -> str:
    names = {
        "promptfoo": "Promptfoo",
        "langfuse": "Langfuse",
        "langsmith": "LangSmith",
        "deepeval": "DeepEval",
        "prompt-optimizer": "prompt-optimizer",
    }
    return names.get(str(tool), str(tool))


def _paper_coverage_rows(run_dir: Path) -> list[JsonDict]:
    rows: list[JsonDict] = []
    for item in PAPER_MAPPING:
        artifact = str(item["artifact"])
        present = (run_dir / artifact).exists()
        concept = str(item["concept"])
        row: JsonDict = {
            "concept": concept,
            "artifact": artifact,
            "status": "present" if present else "missing",
            "category": _paper_concept_category(concept),
            "commands": item.get("commands", []),
            "meaning": item.get("meaning", ""),
        }
        if not present:
            remediation = _paper_remediation_for(concept)
            if remediation:
                row["remediation"] = remediation
        rows.append(row)
    return rows


def _paper_concept_category(concept: str) -> str:
    if concept in {
        "soft-to-hard projection gap",
        "hidden-state trajectory",
        "Riccati surrogate",
        "time-varying soft-control lane",
    }:
        return "research_diagnostic"
    if concept == "HuggingFace hidden-state extraction":
        return "research_input"
    return "evidence_protocol"


def _paper_remediation_for(concept: str) -> JsonDict:
    remediation = PAPER_REMEDIATION.get(concept)
    if not isinstance(remediation, dict):
        return {}
    return {"concept": concept, **remediation}
