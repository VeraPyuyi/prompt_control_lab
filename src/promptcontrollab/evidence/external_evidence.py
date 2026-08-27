"""One-command evidence workflow for external eval/observability exports."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Literal

from promptcontrollab.core.files import JsonDict, ensure_dir, read_json, write_json
from promptcontrollab.diagnostics.research_workflow import (
    run_research_diagnostics,
    verify_research_bundle_index,
    write_research_bundle_index,
    write_research_gap_status,
)
from promptcontrollab.evaluation.run_comparison import compare_runs
from promptcontrollab.evidence.external_rendering import (
    _render_bridge_summary,
    _render_evidence_audit_markdown,
    _render_source_input_verification_markdown,
)
from promptcontrollab.evidence.external_rendering import (
    render_bridge_summary_html as render_bridge_summary_html,
)
from promptcontrollab.evidence.external_rendering import (
    render_evidence_audit_html as render_evidence_audit_html,
)
from promptcontrollab.evidence.external_rendering import (
    render_source_input_verification_html as render_source_input_verification_html,
)
from promptcontrollab.evidence.ingest import (
    ingest_auto_results,
    ingest_deepeval_results,
    ingest_langfuse_results,
    ingest_langsmith_results,
    ingest_promptfoo_results,
)

ExternalTool = Literal["auto", "promptfoo", "langfuse", "langsmith", "deepeval"]


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
    source_inputs = [
        _source_input_provenance(
            role="baseline",
            source_path=baseline_input,
            import_payload=baseline_payload,
        ),
        _source_input_provenance(
            role="candidate",
            source_path=candidate_input,
            import_payload=candidate_payload,
        ),
    ]
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
        source_inputs=source_inputs,
    )
    payload: JsonDict = {
        "kind": "external_evidence",
        "tool": tool,
        "detected_tools": bridge_summary.get("detected_tools", []),
        "source_inputs": source_inputs,
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
            "html_path": str(out_dir / "bridge_summary.html"),
            "recommendation": bridge_summary.get("recommendation"),
            "evidence_tier": bridge_summary.get("evidence_tier"),
            "claim_scope": bridge_summary.get("claim_scope"),
            "validity": bridge_summary.get("validity"),
            "missing_evidence": bridge_summary.get("missing_evidence", []),
        },
        "copied_artifacts": [str(path) for path in copied_artifacts],
        "next_actions": [
            "Open bridge_summary.html to see what the external tool supplied and what PCL added.",
            "Open evidence_card.html for the compact prompt optimization evidence card.",
            "Open report.html for the full comparison dashboard.",
            "Review imports/baseline and imports/candidate if provenance looks incomplete.",
        ],
    }
    write_json(out_dir / "evidence_from_result.json", payload)
    diagnostics = run_research_diagnostics(
        run_dir=out_dir,
        mode="external_evidence",
        diagnostics_dir=out_dir / "diagnostics",
        summary_dir=out_dir,
    )
    payload["research_diagnostics_path"] = str(out_dir / "research_diagnostics.json")
    payload["research_diagnostics_md_path"] = str(out_dir / "research_diagnostics.md")
    payload["research_diagnostics_html_path"] = str(out_dir / "research_diagnostics.html")
    payload["research_bundle_html_path"] = str(out_dir / "research_bundle.html")
    payload["research_diagnostic_type"] = diagnostics.get("diagnostic_type")
    payload["research_bundle_integrity"] = _research_bundle_integrity(out_dir)
    _attach_gap_plan_paths(payload, diagnostics)
    bridge_summary = _attach_research_diagnostics_to_bridge_summary(
        out_dir=out_dir,
        bridge_summary=bridge_summary,
        diagnostics=diagnostics,
    )
    payload["bridge_summary"]["research_diagnostics_path"] = bridge_summary.get(
        "research_diagnostics_path"
    )
    payload["bridge_summary"]["research_diagnostics_html_path"] = bridge_summary.get(
        "research_diagnostics_html_path"
    )
    payload["bridge_summary"]["research_bundle_html_path"] = bridge_summary.get(
        "research_bundle_html_path"
    )
    payload["bridge_summary"]["research_bundle_integrity"] = bridge_summary.get(
        "research_bundle_integrity"
    )
    payload["bridge_summary"]["research_diagnostic_type"] = bridge_summary.get(
        "research_diagnostic_type"
    )
    payload["bridge_summary"]["missing_paper_diagnostics"] = bridge_summary.get(
        "missing_paper_diagnostics", []
    )
    payload["bridge_summary"]["paper_gap_remediation"] = bridge_summary.get(
        "paper_gap_remediation", []
    )
    payload["bridge_summary"]["research_gap_plan_path"] = bridge_summary.get(
        "research_gap_plan_path"
    )
    payload["bridge_summary"]["research_gap_plan_md_path"] = bridge_summary.get(
        "research_gap_plan_md_path"
    )
    payload["bridge_summary"]["research_gap_plan_html_path"] = bridge_summary.get(
        "research_gap_plan_html_path"
    )
    payload["next_actions"].insert(
        3,
        "Open research_bundle.html as the browser-first research evidence index.",
    )
    payload["next_actions"].insert(
        4,
        "Open research_diagnostics.html for paper-evidence gap coverage.",
    )
    write_json(out_dir / "evidence_from_result.json", payload)
    return payload


def build_external_evidence_audit(
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
    title: str = "PromptControlLab External Evidence Audit",
    seed: int = 0,
    bootstrap_samples: int = 1000,
    permutation_samples: int = 1000,
) -> JsonDict:
    """Import external exports and close the browser-first evidence audit loop."""

    evidence = build_external_evidence(
        tool=tool,
        baseline_input=baseline_input,
        candidate_input=candidate_input,
        out_dir=out_dir,
        score_name=score_name,
        provider=provider,
        baseline_provider=baseline_provider,
        candidate_provider=candidate_provider,
        model=model,
        baseline_model=baseline_model,
        candidate_model=candidate_model,
        baseline_prompt_id=baseline_prompt_id,
        candidate_prompt_id=candidate_prompt_id,
        baseline_name=baseline_name,
        candidate_name=candidate_name,
        baseline_experiment=baseline_experiment,
        candidate_experiment=candidate_experiment,
        split_hash=split_hash,
        baseline_method=baseline_method,
        candidate_method=candidate_method,
        title=title,
        seed=seed,
        bootstrap_samples=bootstrap_samples,
        permutation_samples=permutation_samples,
    )
    gap_status = write_research_gap_status(run_dir=out_dir)
    bridge_summary_path = out_dir / "bridge_summary.json"
    bridge_summary = read_json(bridge_summary_path) if bridge_summary_path.exists() else {}
    source_verification = verify_source_inputs(run_dir=out_dir)
    payload: JsonDict = {
        "kind": "external_evidence_audit",
        "tool": tool,
        "out_dir": str(out_dir),
        "json_path": str(out_dir / "evidence_audit_result.json"),
        "markdown_path": str(out_dir / "evidence_audit_result.md"),
        "html_path": str(out_dir / "evidence_audit_result.html"),
        "evidence_from_result_path": str(out_dir / "evidence_from_result.json"),
        "bridge_summary_path": str(out_dir / "bridge_summary.md"),
        "bridge_summary_html_path": str(out_dir / "bridge_summary.html"),
        "research_bundle_path": str(out_dir / "research_bundle.html"),
        "research_diagnostics_path": str(out_dir / "research_diagnostics.html"),
        "research_gap_status_path": str(out_dir / "research_gap_status.html"),
        "source_input_verification_path": str(out_dir / "source_input_verification.html"),
        "research_bundle_verification_path": str(out_dir / "research_bundle_verification.html"),
        "detected_tools": evidence.get("detected_tools", []),
        "source_inputs": evidence.get("source_inputs", []),
        "claim_scope": bridge_summary.get("claim_scope"),
        "evidence_tier": bridge_summary.get("evidence_tier"),
        "validity": bridge_summary.get("validity"),
        "gap_status": {
            "status": gap_status.get("status"),
            "complete_count": gap_status.get("complete_count"),
            "missing_count": gap_status.get("missing_count"),
        },
        "source_verification": _source_verification_summary(source_verification),
        "bundle_verification": {},
        "missing_paper_diagnostics": bridge_summary.get("missing_paper_diagnostics", []),
        "next_actions": [
            ("Open evidence_audit_result.html for the reviewer-facing audit summary."),
            "Open bridge_summary.html to see what the external tool supplied and what PCL added.",
            "Open research_bundle.html as the browser-first evidence index.",
            (
                "Open research_gap_status.html to see which paper-derived diagnostics "
                "are still missing."
            ),
            (
                "Open source_input_verification.html to confirm the original external "
                "exports still match recorded hashes."
            ),
            (
                "Open research_bundle_verification.html to confirm the linked evidence "
                "package still matches recorded hashes."
            ),
        ],
        "boundary": (
            "This workflow audits prompt-optimization evidence from external exports. "
            "It does not replace the external tool's tracing, security testing, or "
            "production monitoring."
        ),
    }
    _write_evidence_audit_artifacts(out_dir, payload)
    write_research_bundle_index(out_dir)
    verification = verify_research_bundle_index(out_dir)
    bridge_summary = _refresh_bridge_integrity_after_verification(out_dir)
    payload.update(
        {
            "claim_scope": bridge_summary.get("claim_scope"),
            "evidence_tier": bridge_summary.get("evidence_tier"),
            "validity": bridge_summary.get("validity"),
            "missing_paper_diagnostics": bridge_summary.get(
                "missing_paper_diagnostics",
                [],
            ),
            "bundle_verification": {
                "status": verification.get("status"),
                "checked_count": verification.get("checked_count"),
                "mismatch_count": verification.get("mismatch_count"),
                "missing_count": verification.get("missing_count"),
            },
            "source_verification": _source_verification_summary(source_verification),
        }
    )
    _write_evidence_audit_artifacts(out_dir, payload)
    return payload


def verify_source_inputs(*, run_dir: Path, out_path: Path | None = None) -> JsonDict:
    """Verify external source export files against recorded ``source_inputs`` hashes."""

    source_inputs, source_artifact = _load_source_inputs(run_dir)
    results = [
        _verify_source_input(run_dir=run_dir, item=item)
        for item in source_inputs
        if isinstance(item, dict)
    ]
    checked = [item for item in results if item.get("status") in {"ok", "mismatch", "missing"}]
    mismatches = [item for item in results if item.get("status") == "mismatch"]
    missing = [item for item in results if item.get("status") == "missing"]
    unchecked = [item for item in results if item.get("status") == "unchecked"]
    if not source_inputs:
        status = "missing_source_inputs"
    elif mismatches or missing:
        status = "fail"
    elif unchecked:
        status = "needs_review"
    else:
        status = "pass"

    json_path = out_path or (run_dir / "source_input_verification.json")
    markdown_path = json_path.with_suffix(".md")
    html_path = json_path.with_suffix(".html")
    payload: JsonDict = {
        "kind": "source_input_verification",
        "run_dir": str(run_dir),
        "source_artifact": source_artifact,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "html_path": str(html_path),
        "status": status,
        "checked_count": len(checked),
        "ok_count": sum(1 for item in results if item.get("status") == "ok"),
        "mismatch_count": len(mismatches),
        "missing_count": len(missing),
        "unchecked_count": len(unchecked),
        "results": results,
        "boundary": (
            "This check verifies recorded SHA-256 values for original external export files. "
            "It is tamper-evidence for local source inputs, not proof of provider-side logs "
            "or hidden model internals."
        ),
    }
    write_json(json_path, payload)
    markdown_path.write_text(_render_source_input_verification_markdown(payload), encoding="utf-8")
    html_path.write_text(render_source_input_verification_html(payload), encoding="utf-8")
    return payload


def _write_evidence_audit_artifacts(out_dir: Path, payload: JsonDict) -> None:
    write_json(out_dir / "evidence_audit_result.json", payload)
    (out_dir / "evidence_audit_result.md").write_text(
        _render_evidence_audit_markdown(payload),
        encoding="utf-8",
    )
    (out_dir / "evidence_audit_result.html").write_text(
        render_evidence_audit_html(payload),
        encoding="utf-8",
    )


def attach_evidence_gate_to_audit(*, out_dir: Path, gate_payload: JsonDict) -> JsonDict:
    """Attach evidence-gate status to an existing evidence-audit summary."""

    path = out_dir / "evidence_audit_result.json"
    if not path.exists():
        return {}
    payload = read_json(path)
    evidence_gate = {
        "status": gate_payload.get("status"),
        "summary": gate_payload.get("summary"),
        "json_path": gate_payload.get("json_path"),
        "markdown_path": gate_payload.get("markdown_path"),
        "html_path": gate_payload.get("html_path"),
    }
    payload["evidence_gate"] = evidence_gate
    payload["evidence_gate_path"] = gate_payload.get("html_path")
    payload["evidence_gate_json_path"] = gate_payload.get("json_path")
    next_actions = payload.get("next_actions")
    gate_action = "Open evidence_gate_result.html for the combined CI/reviewer gate."
    if isinstance(next_actions, list) and gate_action not in next_actions:
        next_actions.insert(
            1,
            gate_action,
        )
    _write_evidence_audit_artifacts(out_dir, payload)
    return payload


def _refresh_bridge_integrity_after_verification(out_dir: Path) -> JsonDict:
    """Update bridge summary so it reflects the latest bundle verification artifact."""

    path = out_dir / "bridge_summary.json"
    if not path.exists():
        return {}
    payload = read_json(path)
    payload["research_bundle_integrity"] = _research_bundle_integrity(out_dir)
    write_json(path, payload)
    (out_dir / "bridge_summary.md").write_text(_render_bridge_summary(payload), encoding="utf-8")
    (out_dir / "bridge_summary.html").write_text(
        render_bridge_summary_html(payload),
        encoding="utf-8",
    )
    return payload


def _load_source_inputs(run_dir: Path) -> tuple[list[object], str | None]:
    for name in ["evidence_audit_result.json", "evidence_from_result.json", "bridge_summary.json"]:
        path = run_dir / name
        if not path.exists():
            continue
        payload = read_json(path)
        source_inputs = payload.get("source_inputs")
        if isinstance(source_inputs, list):
            return source_inputs, str(path)
    return [], None


def _verify_source_input(*, run_dir: Path, item: JsonDict) -> JsonDict:
    role = item.get("role")
    path_text = str(item.get("path") or "")
    resolved_path_text = str(item.get("resolved_path") or "")
    expected = item.get("sha256")
    base: JsonDict = {
        "role": role,
        "source_tool": item.get("source_tool"),
        "path": path_text,
        "recorded_resolved_path": resolved_path_text,
        "path_kind": item.get("path_kind"),
        "expected_sha256": expected,
        "import_count": item.get("import_count"),
    }
    if not path_text:
        return {**base, "status": "unchecked", "reason": "no source path recorded"}
    if not isinstance(expected, str) or not expected:
        return {**base, "status": "unchecked", "reason": "no recorded sha256"}
    path = _resolve_source_path(
        path_text=path_text,
        run_dir=run_dir,
        resolved_path_text=resolved_path_text,
    )
    if not path.exists() or not path.is_file():
        return {
            **base,
            "status": "missing",
            "actual_sha256": None,
            "resolved_path": str(path),
        }
    actual = f"sha256:{_sha256_file(path)}"
    return {
        **base,
        "status": "ok" if actual == expected else "mismatch",
        "actual_sha256": actual,
        "resolved_path": str(path),
        "bytes": path.stat().st_size,
    }


def _resolve_source_path(*, path_text: str, run_dir: Path, resolved_path_text: str = "") -> Path:
    if resolved_path_text:
        resolved_path = Path(resolved_path_text)
        if resolved_path.is_absolute() and resolved_path.exists():
            return resolved_path
    path = Path(path_text)
    if path.is_absolute() or path.exists():
        return path
    candidates = [run_dir / path, run_dir.parent / path]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return path


def _attach_research_diagnostics_to_bridge_summary(
    *,
    out_dir: Path,
    bridge_summary: JsonDict,
    diagnostics: JsonDict,
) -> JsonDict:
    """Add the generated paper-evidence gap report to bridge summary artifacts."""

    external = _external_diagnostic_payload(diagnostics)
    missing = external.get("missing_paper_diagnostics")
    missing_list = missing if isinstance(missing, list) else []
    remediation = external.get("paper_gap_remediation")
    remediation_list = remediation if isinstance(remediation, list) else []
    payload = dict(bridge_summary)
    payload["research_diagnostics_path"] = str(out_dir / "research_diagnostics.json")
    payload["research_diagnostics_md_path"] = str(out_dir / "research_diagnostics.md")
    payload["research_diagnostics_html_path"] = str(out_dir / "research_diagnostics.html")
    payload["research_bundle_html_path"] = str(out_dir / "research_bundle.html")
    payload["research_bundle_integrity"] = _research_bundle_integrity(out_dir)
    payload["research_diagnostic_type"] = diagnostics.get("diagnostic_type")
    payload["missing_paper_diagnostics"] = missing_list
    payload["paper_gap_remediation"] = remediation_list
    _attach_gap_plan_paths(payload, diagnostics)
    added = payload.get("pcl_added_evidence")
    added_list = list(added) if isinstance(added, list) else []
    if "paper_evidence_gap_diagnosis" not in added_list:
        added_list.append("paper_evidence_gap_diagnosis")
    payload["pcl_added_evidence"] = added_list
    next_actions = payload.get("next_actions")
    next_action_list = list(next_actions) if isinstance(next_actions, list) else []
    bundle_action = "Open research_bundle.html as the browser-first research evidence index."
    if bundle_action not in next_action_list:
        next_action_list.insert(1, bundle_action)
    action = "Open research_diagnostics.html for paper-evidence gap coverage."
    if action not in next_action_list:
        next_action_list.insert(1, action)
    payload["next_actions"] = next_action_list
    write_json(out_dir / "bridge_summary.json", payload)
    (out_dir / "bridge_summary.md").write_text(_render_bridge_summary(payload), encoding="utf-8")
    (out_dir / "bridge_summary.html").write_text(
        render_bridge_summary_html(payload),
        encoding="utf-8",
    )
    return payload


def _research_bundle_integrity(run_dir: Path) -> JsonDict:
    bundle_path = run_dir / "research_bundle.json"
    if not bundle_path.exists():
        return {
            "status": "missing",
            "json_path": str(bundle_path),
            "html_path": str(run_dir / "research_bundle.html"),
        }
    bundle = read_json(bundle_path)
    missing_html = bundle.get("missing_html_artifacts")
    missing_html_list = missing_html if isinstance(missing_html, list) else []
    hashed = int(bundle.get("hashed_artifact_count") or 0)
    present = int(bundle.get("present_artifact_count") or 0)
    return {
        "status": "hashed" if hashed else "present_without_hashes",
        "json_path": str(bundle_path),
        "html_path": str(run_dir / "research_bundle.html"),
        "artifact_count": bundle.get("artifact_count"),
        "present_artifact_count": present,
        "hashed_artifact_count": hashed,
        "missing_html_artifacts": missing_html_list,
        "missing_html_count": len(missing_html_list),
        **_research_bundle_verification_summary(run_dir),
    }


def _research_bundle_verification_summary(run_dir: Path) -> JsonDict:
    path = run_dir / "research_bundle_verification.json"
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


def _source_verification_summary(payload: JsonDict) -> JsonDict:
    return {
        "status": payload.get("status"),
        "checked_count": payload.get("checked_count"),
        "ok_count": payload.get("ok_count"),
        "mismatch_count": payload.get("mismatch_count"),
        "missing_count": payload.get("missing_count"),
        "unchecked_count": payload.get("unchecked_count"),
        "html_path": payload.get("html_path"),
        "json_path": payload.get("json_path"),
    }


def _attach_gap_plan_paths(payload: JsonDict, diagnostics: JsonDict) -> None:
    artifacts = diagnostics.get("artifacts")
    artifacts_dict = artifacts if isinstance(artifacts, dict) else {}
    plan_path = artifacts_dict.get("research_gap_plan")
    plan_md_path = artifacts_dict.get("research_gap_plan_markdown")
    plan_html_path = artifacts_dict.get("research_gap_plan_html")
    commands_ps1 = artifacts_dict.get("research_gap_commands_ps1")
    commands_sh = artifacts_dict.get("research_gap_commands_sh")
    if plan_path:
        payload["research_gap_plan_path"] = plan_path
    if plan_md_path:
        payload["research_gap_plan_md_path"] = plan_md_path
    if plan_html_path:
        payload["research_gap_plan_html_path"] = plan_html_path
    if commands_ps1:
        payload["research_gap_commands_ps1_path"] = commands_ps1
    if commands_sh:
        payload["research_gap_commands_sh_path"] = commands_sh


def _external_diagnostic_payload(diagnostics: JsonDict) -> JsonDict:
    diagnostic_payload = diagnostics.get("diagnostics")
    if not isinstance(diagnostic_payload, dict):
        return {}
    external = diagnostic_payload.get("external_bridge")
    if isinstance(external, dict):
        return external
    return {}


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
    """Ingest one external result source into a normalized comparison run."""

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
    if tool == "deepeval":
        return ingest_deepeval_results(
            source_path=source_path,
            out_dir=out_dir,
            score_name=score_name,
            model=model,
            provider=provider,
            method=method,
        )
    msg = f"Unsupported external evidence tool: {tool}"
    raise ValueError(msg)


def _source_input_provenance(
    *,
    role: str,
    source_path: Path,
    import_payload: JsonDict,
) -> JsonDict:
    """Record immutable provenance for an external source export."""

    resolved_path = source_path.resolve()
    payload: JsonDict = {
        "role": role,
        "path": str(source_path),
        "resolved_path": str(resolved_path),
        "path_kind": "absolute" if source_path.is_absolute() else "relative",
        "bytes": source_path.stat().st_size,
        "sha256": f"sha256:{_sha256_file(source_path)}",
    }
    if isinstance(import_payload.get("source_tool"), str):
        payload["source_tool"] = import_payload["source_tool"]
    if isinstance(import_payload.get("count"), int):
        payload["import_count"] = import_payload["count"]
    for key in ["prompt_id", "name", "experiment", "score_name", "model", "provider"]:
        value = import_payload.get(key)
        if isinstance(value, str) and value:
            payload[key] = value
    return payload


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        "evidence_card.html",
        "claim_check.json",
        "claim_check.md",
        "claim_check.html",
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
    source_inputs: list[JsonDict],
) -> JsonDict:
    """Write the bounded cross-tool evidence summary and companion artifacts."""

    evidence_card = _read_optional_json(comparison_dir / "evidence_card.json")
    claim_check = _read_optional_json(comparison_dir / "claim_check.json")
    validity = _read_optional_json(comparison_dir / "comparison_validity.json")
    stats = _read_optional_json(comparison_dir / "stats.json")
    comparison = _first_comparison(stats)
    detected_tools = _detected_tools(requested_tool, baseline_payload, candidate_payload)
    missing = evidence_card.get("missing_artifacts")
    missing_evidence = missing if isinstance(missing, list) else []
    payload: JsonDict = {
        "kind": "external_bridge_summary",
        "html_path": str(out_dir / "bridge_summary.html"),
        "requested_tool": requested_tool,
        "detected_tools": detected_tools,
        "source_inputs": source_inputs,
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
            "claim_scope_check",
            "local_archivable_report",
        ],
        "recommendation": evidence_card.get("recommendation", "needs_review"),
        "evidence_tier": evidence_card.get("evidence_tier", "unknown"),
        "claim_scope": evidence_card.get("claim_scope", ""),
        "claim_language": evidence_card.get("claim_language", ""),
        "claim_check_status": claim_check.get("status", "missing"),
        "claim_check_requested_claim": claim_check.get("requested_claim", "paired"),
        "claim_check_safe_claim": claim_check.get("safe_claim", ""),
        "next_tier_missing": evidence_card.get("next_tier_missing", []),
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
    (out_dir / "bridge_summary.html").write_text(
        render_bridge_summary_html(payload),
        encoding="utf-8",
    )
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
        "deepeval": {
            "tool": "deepeval",
            "display_name": "DeepEval",
            "role": "local LLM test runs, metric scores, reasons, and CI-style eval artifacts",
            "pcl_adds": (
                "paired prompt optimization evidence, prompt-only validity, and "
                "paper-diagnostic gap tracking"
            ),
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
        (
            "Archive imports/, comparison/, evidence_card.html, claim_check.html, "
            "and report.html together."
        ),
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
