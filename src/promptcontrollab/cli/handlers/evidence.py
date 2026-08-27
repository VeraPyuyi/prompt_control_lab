"""Evidence command handlers and terminal formatters."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path

from promptcontrollab.audit.claim_check import run_claim_check
from promptcontrollab.core.errors import PromptControlLabError
from promptcontrollab.core.files import JsonDict, ensure_dir, read_json, write_json
from promptcontrollab.diagnostics.research_workflow import (
    write_peoc_research_gap_plan,
    write_research_bundle_index,
    write_research_gap_status,
)
from promptcontrollab.evidence.evidence_card import write_evidence_card
from promptcontrollab.evidence.evidence_gate import run_evidence_gate
from promptcontrollab.evidence.external_evidence import (
    attach_evidence_gate_to_audit,
    build_external_evidence,
    build_external_evidence_audit,
    verify_source_inputs,
)
from promptcontrollab.evidence.ingest import (
    ingest_auto_results,
    ingest_deepeval_results,
    ingest_langfuse_results,
    ingest_langsmith_results,
    ingest_prompt_optimizer_assets,
    ingest_promptfoo_results,
)
from promptcontrollab.evidence.peoc_import import (
    PeocImportOptions,
    PeocSourceOverrides,
    import_peoc_bundle,
)
from promptcontrollab.evidence.posttrain_export import export_posttrain_pilot
from promptcontrollab.evidence.posttrain_gate import run_posttrain_gate
from promptcontrollab.evidence.posttrain_pilot import (
    PilotInputs,
    build_sft_pilot_plan,
    write_model_provenance,
)
from promptcontrollab.evidence.posttrain_pilot_data import (
    load_gsm8k_jsonl,
    prepare_sft_pilot_data,
    prepare_sft_pilot_data_from_huggingface,
)
from promptcontrollab.evidence.posttrain_pilot_runner import execute_sft_pilot
from promptcontrollab.evidence.server_evidence import (
    EvidenceImportOptions,
    import_evidence_manifest,
    merge_evidence_manifests,
    scan_evidence_root,
    validate_evidence_destination,
)

_PEOC_DOWNSTREAM_ARTIFACTS = (
    "evidence_card.json",
    "evidence_card.md",
    "evidence_card.html",
    "claim_check.json",
    "claim_check.md",
    "claim_check.html",
    "research_gap_plan.json",
    "research_gap_plan.md",
    "research_gap_plan.html",
    "research_gap_commands.ps1",
    "research_gap_commands.sh",
    "research_gap_status.json",
    "research_gap_status.md",
    "research_gap_status.html",
    "research_bundle.json",
    "research_bundle.md",
    "research_bundle.html",
    "research_bundle.zh.html",
    "research_bundle_verification.json",
    "research_bundle_verification.md",
    "research_bundle_verification.html",
)


def _cmd_ingest_auto(args: argparse.Namespace) -> None:
    """Execute the ingest auto command handler."""
    payload = ingest_auto_results(
        source_path=args.input,
        out_dir=args.out,
        prompt_id=args.prompt_id,
        name=args.name,
        experiment=args.experiment,
        score_name=args.score_name,
        model=args.model,
        provider=args.provider,
        method=args.method,
        asset_id=args.asset_id,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_ingest_promptfoo(args: argparse.Namespace) -> None:
    """Execute the ingest promptfoo command handler."""
    payload = ingest_promptfoo_results(
        source_path=args.input,
        out_dir=args.out,
        prompt_id=args.prompt_id,
        provider=args.provider,
        method=args.method,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_ingest_langfuse(args: argparse.Namespace) -> None:
    """Execute the ingest langfuse command handler."""
    payload = ingest_langfuse_results(
        source_path=args.input,
        out_dir=args.out,
        name=args.name,
        score_name=args.score_name,
        model=args.model,
        provider=args.provider,
        method=args.method,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_ingest_langsmith(args: argparse.Namespace) -> None:
    """Execute the ingest langsmith command handler."""
    payload = ingest_langsmith_results(
        source_path=args.input,
        out_dir=args.out,
        experiment=args.experiment,
        score_name=args.score_name,
        model=args.model,
        provider=args.provider,
        method=args.method,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_ingest_deepeval(args: argparse.Namespace) -> None:
    """Execute the ingest deepeval command handler."""
    payload = ingest_deepeval_results(
        source_path=args.input,
        out_dir=args.out,
        score_name=args.score_name,
        model=args.model,
        provider=args.provider,
        method=args.method,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_ingest_prompt_optimizer(args: argparse.Namespace) -> None:
    """Execute the ingest prompt optimizer command handler."""
    payload = ingest_prompt_optimizer_assets(
        source_path=args.input,
        out_dir=args.out,
        asset_id=args.asset_id,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_evidence_from(args: argparse.Namespace) -> None:
    """Execute the evidence from command handler."""
    payload = build_external_evidence(
        tool=args.tool,
        baseline_input=args.baseline_input,
        candidate_input=args.candidate_input,
        out_dir=args.out,
        score_name=args.score_name,
        provider=args.provider,
        baseline_provider=args.baseline_provider,
        candidate_provider=args.candidate_provider,
        model=args.model,
        baseline_model=args.baseline_model,
        candidate_model=args.candidate_model,
        baseline_prompt_id=args.baseline_prompt_id,
        candidate_prompt_id=args.candidate_prompt_id,
        baseline_name=args.baseline_name,
        candidate_name=args.candidate_name,
        baseline_experiment=args.baseline_experiment,
        candidate_experiment=args.candidate_experiment,
        split_hash=args.split_hash,
        baseline_method=args.baseline_method,
        candidate_method=args.candidate_method,
        title=args.title,
        seed=args.seed,
        bootstrap_samples=args.bootstrap_samples,
        permutation_samples=args.permutation_samples,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_evidence_audit(args: argparse.Namespace) -> None:
    """Execute the evidence audit command handler."""
    payload = build_external_evidence_audit(
        tool=args.tool,
        baseline_input=args.baseline_input,
        candidate_input=args.candidate_input,
        out_dir=args.out,
        score_name=args.score_name,
        provider=args.provider,
        baseline_provider=args.baseline_provider,
        candidate_provider=args.candidate_provider,
        model=args.model,
        baseline_model=args.baseline_model,
        candidate_model=args.candidate_model,
        baseline_prompt_id=args.baseline_prompt_id,
        candidate_prompt_id=args.candidate_prompt_id,
        baseline_name=args.baseline_name,
        candidate_name=args.candidate_name,
        baseline_experiment=args.baseline_experiment,
        candidate_experiment=args.candidate_experiment,
        split_hash=args.split_hash,
        baseline_method=args.baseline_method,
        candidate_method=args.candidate_method,
        title=args.title,
        seed=args.seed,
        bootstrap_samples=args.bootstrap_samples,
        permutation_samples=args.permutation_samples,
    )
    gate_payload = run_evidence_gate(run_dir=args.out)
    payload = attach_evidence_gate_to_audit(out_dir=args.out, gate_payload=gate_payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_source_verify(args: argparse.Namespace) -> None:
    """Execute the source verify command handler."""
    payload = verify_source_inputs(run_dir=args.run, out_path=args.out)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    if args.strict and payload.get("status") != "pass":
        msg = (
            "Source input verification failed in strict mode: "
            f"status={payload.get('status')}, "
            f"mismatches={payload.get('mismatch_count')}, "
            f"missing={payload.get('missing_count')}, "
            f"unchecked={payload.get('unchecked_count')}"
        )
        raise PromptControlLabError(msg)


def _cmd_evidence_gate(args: argparse.Namespace) -> None:
    """Execute the evidence gate command handler."""
    payload = run_evidence_gate(
        run_dir=args.run,
        out_path=args.out,
        require_source=args.require_source,
        allow_missing_bundle=args.allow_missing_bundle,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    if args.strict and payload.get("status") != "pass":
        msg = f"Evidence gate failed in strict mode: status={payload.get('status')}"
        raise PromptControlLabError(msg)


def _cmd_evidence_scan(args: argparse.Namespace) -> None:
    """Execute the evidence scan command handler."""
    validate_evidence_destination(args.out, protected_roots=(args.root,))
    payload = scan_evidence_root(root=args.root, profile=args.profile)
    write_json(args.out, payload)
    summary = {
        "schema": "prompt_control_lab.evidence_scan_result.v1",
        "manifest_path": str(args.out.resolve()),
        "source_count": len(payload.get("sources", [])),
        "adapter_counts": payload.get("adapter_counts", {}),
        "snapshot_sha256": payload.get("snapshot_sha256"),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_evidence_import(args: argparse.Namespace) -> None:
    """Execute the evidence import command handler."""
    payload = import_evidence_manifest(
        EvidenceImportOptions(
            manifest_path=args.manifest,
            out_dir=args.out,
            portable=args.portable,
            overwrite=args.overwrite,
        )
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_evidence_merge(args: argparse.Namespace) -> None:
    """Execute the evidence merge command handler."""
    payload = merge_evidence_manifests(
        primary=args.primary,
        secondary=args.secondary,
        out_dir=args.out,
        portable=args.portable,
        overwrite=args.overwrite,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_posttrain_gate(args: argparse.Namespace) -> None:
    """Execute the posttrain gate command handler."""
    payload = run_posttrain_gate(
        baseline_dir=args.baseline,
        candidate_dir=args.candidate,
        policy_path=args.policy,
        out_dir=args.out,
        capability=args.capability,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_posttrain_pilot(args: argparse.Namespace) -> None:
    """Execute the posttrain pilot command handler."""
    inputs = PilotInputs(
        model_path=args.model,
        train_path=args.train,
        validation_path=args.validation,
        withheld_path=args.withheld,
        format_fixture_path=args.format_fixture,
        out_dir=args.out,
        model_provenance_path=args.model_provenance,
        runtime_root=args.runtime_root,
        seeds=tuple(args.seeds or (0, 1, 2)),
        max_steps=args.max_steps,
    )
    if not args.execute:
        plan = build_sft_pilot_plan(inputs)
        ensure_dir(args.out)
        protocol_path = args.out / "pilot_protocol.json"
        write_json(protocol_path, plan)
        print(json.dumps({"status": "plan_only", "protocol": str(protocol_path)}, indent=2))
        return
    if args.approval is None:
        raise ValueError("--execute requires an expiring --approval resource record")
    lock_file = args.lock_file or args.runtime_root / "locks" / "sft-pilot.lock"
    execute_sft_pilot(
        inputs,
        approval_path=args.approval,
        gpu=args.gpu,
        lock_file=lock_file,
    )
    protocol_path = args.out / "pilot_protocol.json"
    print(json.dumps({"status": "complete", "protocol": str(protocol_path)}, indent=2))


def _cmd_posttrain_pilot_export(args: argparse.Namespace) -> None:
    """Execute the posttrain pilot export command handler."""
    payload = export_posttrain_pilot(run_dir=args.run, out_dir=args.out)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_posttrain_model_provenance(args: argparse.Namespace) -> None:
    """Execute the posttrain model provenance command handler."""
    payload = write_model_provenance(
        args.model,
        model_id=args.model_id,
        revision=args.revision,
        manifest_path=args.out,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_posttrain_pilot_prepare(args: argparse.Namespace) -> None:
    """Execute the posttrain pilot prepare command handler."""
    offline_paths = (args.gsm8k_train_jsonl, args.gsm8k_test_jsonl)
    if any(path is not None for path in offline_paths) and not all(
        path is not None for path in offline_paths
    ):
        raise ValueError(
            "Offline preparation requires both --gsm8k-train-jsonl and --gsm8k-test-jsonl"
        )
    if all(path is not None for path in offline_paths):
        payload = prepare_sft_pilot_data(
            train_rows=load_gsm8k_jsonl(args.gsm8k_train_jsonl),
            test_rows=load_gsm8k_jsonl(args.gsm8k_test_jsonl),
            out_dir=args.out,
            dataset_id=args.dataset_id,
            dataset_revision=args.dataset_revision,
            selection_seed=args.selection_seed,
            source_mode="offline_jsonl",
        )
    else:
        payload = prepare_sft_pilot_data_from_huggingface(
            out_dir=args.out,
            dataset_id=args.dataset_id,
            dataset_revision=args.dataset_revision,
            selection_seed=args.selection_seed,
        )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_research_import_peoc(args: argparse.Namespace) -> None:
    """Execute the research import peoc command handler."""
    overrides = PeocSourceOverrides(
        hard_summary=args.hard_summary,
        trajectory_files=tuple(args.trajectory_file),
        heterogeneity_summary=args.heterogeneity_summary,
    )
    requested_output_dir = args.out.resolve()
    _preflight_peoc_downstream_artifacts(
        requested_output_dir,
        overwrite=args.overwrite,
    )
    result = import_peoc_bundle(
        PeocImportOptions(
            bundle_root=args.bundle,
            out_dir=args.out,
            overrides=overrides,
            portable=args.portable,
            language=args.language,
            overwrite=args.overwrite,
        )
    )
    output_dir = Path(str(result["output_dir"]))
    transaction_dir: Path | None = None
    backups: list[tuple[Path, Path]] = []
    try:
        transaction_dir, backups = _begin_peoc_downstream_transaction(output_dir)
        evidence_card = write_evidence_card(output_dir)
        claim_check = run_claim_check(
            output_dir,
            claim="full-research",
            out_path=output_dir / "claim_check.json",
        )
        gap_plan = write_peoc_research_gap_plan(output_dir)
        gap_status = write_research_gap_status(run_dir=output_dir)
        research_bundle = write_research_bundle_index(output_dir)
        case_study = read_json(output_dir / "research_case_study.json")
    except Exception as exc:
        recovery_error = _rollback_peoc_downstream_transaction(
            output_dir,
            transaction_dir=transaction_dir,
            backups=backups,
        )
        recovery_note = (
            " Previous downstream artifacts were restored."
            if recovery_error is None
            else (
                " Automatic downstream rollback was incomplete: "
                f"{recovery_error}. Recovery files remain at {transaction_dir}."
            )
        )
        msg = (
            f"{exc}; primary import artifacts remain at {output_dir}, but downstream "
            f"evidence chain was not completed.{recovery_note}"
        )
        raise PromptControlLabError(msg) from exc
    else:
        _commit_peoc_downstream_transaction(transaction_dir)
    result["downstream"] = {
        "evidence_card": {
            "path": str(output_dir / "evidence_card.html"),
            "recommendation": evidence_card.get("recommendation"),
            "evidence_tier": evidence_card.get("evidence_tier"),
        },
        "claim_check": {
            "path": str(output_dir / "claim_check.html"),
            "status": claim_check.get("status"),
        },
        "research_gap_plan": {
            "path": str(output_dir / "research_gap_plan.html"),
            "action_count": gap_plan.get("action_count"),
        },
        "research_gap_status": {
            "path": str(output_dir / "research_gap_status.html"),
            "status": gap_status.get("status"),
        },
        "research_bundle": {
            "path": str(output_dir / "research_bundle.html"),
            "status": research_bundle.get("status"),
        },
    }
    print(
        _format_peoc_import_output(
            result=result,
            case_study=case_study,
            language=args.language,
        )
    )


def _begin_peoc_downstream_transaction(
    output_dir: Path,
) -> tuple[Path, list[tuple[Path, Path]]]:
    """Move the previous downstream chain aside until its replacement succeeds."""

    transaction_dir = Path(
        tempfile.mkdtemp(
            dir=output_dir.parent,
            prefix=f".{output_dir.name}.peoc-downstream-",
        )
    )
    backup_dir = transaction_dir / "backup"
    backup_dir.mkdir()
    backups: list[tuple[Path, Path]] = []
    try:
        for name in _PEOC_DOWNSTREAM_ARTIFACTS:
            source = output_dir / name
            if not source.exists() and not source.is_symlink():
                continue
            if source.is_dir() and not source.is_symlink():
                raise ValueError(
                    f"Generated PEOC downstream artifact path became a directory: {source}"
                )
            backup = backup_dir / name
            os.replace(source, backup)
            backups.append((source, backup))
    except Exception as exc:
        recovery_error = _rollback_peoc_downstream_transaction(
            output_dir,
            transaction_dir=transaction_dir,
            backups=backups,
            remove_generated=False,
        )
        if recovery_error is not None:
            raise PromptControlLabError(
                "Could not begin the PEOC downstream transaction and automatic "
                f"recovery was incomplete: {recovery_error}. Recovery files remain "
                f"at {transaction_dir}."
            ) from exc
        raise
    return transaction_dir, backups


def _rollback_peoc_downstream_transaction(
    output_dir: Path,
    *,
    transaction_dir: Path | None,
    backups: list[tuple[Path, Path]],
    remove_generated: bool = True,
) -> str | None:
    if transaction_dir is None:
        return None
    errors: list[str] = []
    if remove_generated:
        for name in _PEOC_DOWNSTREAM_ARTIFACTS:
            path = output_dir / name
            try:
                if path.is_symlink() or path.is_file():
                    path.unlink()
                elif path.exists():
                    errors.append(f"cannot remove directory collision {path}")
            except OSError as exc:
                errors.append(f"cannot remove generated artifact {path}: {exc}")
    for destination, backup in reversed(backups):
        try:
            if destination.exists() or destination.is_symlink():
                errors.append(f"cannot restore over existing path {destination}")
                continue
            os.replace(backup, destination)
        except OSError as exc:
            errors.append(f"cannot restore {destination}: {exc}")
    if errors:
        return "; ".join(errors)
    try:
        shutil.rmtree(transaction_dir)
    except OSError as exc:
        return f"cannot remove completed rollback directory: {exc}"
    return None


def _commit_peoc_downstream_transaction(transaction_dir: Path | None) -> None:
    if transaction_dir is None:
        return
    try:
        shutil.rmtree(transaction_dir)
    except OSError as exc:
        raise PromptControlLabError(
            "PEOC downstream artifacts were generated, but the transaction backup "
            f"could not be removed: {transaction_dir}: {exc}"
        ) from exc


def _preflight_peoc_downstream_artifacts(output_dir: Path, *, overwrite: bool) -> None:
    paths = [output_dir / name for name in _PEOC_DOWNSTREAM_ARTIFACTS]
    directory_collisions = [
        str(path) for path in paths if path.exists() and path.is_dir() and not path.is_symlink()
    ]
    if directory_collisions:
        joined = ", ".join(directory_collisions)
        raise ValueError(
            "Generated PEOC downstream artifact paths collide with directories and cannot "
            f"be replaced: {joined}"
        )
    existing = [str(path) for path in paths if path.exists() or path.is_symlink()]
    if existing and not overwrite:
        joined = ", ".join(existing)
        raise ValueError(
            "Generated PEOC downstream artifacts already exist; pass --overwrite to replace "
            f"only those artifacts: {joined}"
        )


def _format_peoc_import_output(
    *,
    result: JsonDict,
    case_study: JsonDict,
    language: str,
) -> str:
    """Implement the  format peoc import output CLI workflow helper."""
    output_dir = Path(str(result.get("output_dir", "")))
    case_study_path = output_dir / "research_case_study.html"
    source_count = int(result.get("source_count", 0))
    status_counts = result.get("status_counts")
    statuses = status_counts if isinstance(status_counts, dict) else {}
    downstream_value = result.get("downstream")
    downstream = downstream_value if isinstance(downstream_value, dict) else {}
    evidence_value = downstream.get("evidence_card")
    evidence = evidence_value if isinstance(evidence_value, dict) else {}
    claim_value = downstream.get("claim_check")
    claim = claim_value if isinstance(claim_value, dict) else {}
    plan_value = downstream.get("research_gap_plan")
    plan = plan_value if isinstance(plan_value, dict) else {}
    gap_value = downstream.get("research_gap_status")
    gap = gap_value if isinstance(gap_value, dict) else {}
    bundle_value = downstream.get("research_bundle")
    bundle = bundle_value if isinstance(bundle_value, dict) else {}
    boundary_value = result.get("claim_boundary")
    boundary = boundary_value if isinstance(boundary_value, dict) else {}
    boundary_status = str(boundary.get("status", "unknown"))
    full_support = str(bool(boundary.get("full_research_support", False))).lower()
    blocking = _format_peoc_blocking_sections(boundary.get("blocking_sections"))
    warning_rows = case_study.get("warnings")
    warnings = warning_rows if isinstance(warning_rows, list) else []
    warning_counts: dict[str, int] = {}
    for warning in warnings:
        code = str(warning.get("code", "unknown")) if isinstance(warning, dict) else "unknown"
        warning_counts[code] = warning_counts.get(code, 0) + 1
    warning_summary = sorted(
        warning_counts.items(),
        key=lambda item: (-item[1], item[0]),
    )
    status_order = [
        "available",
        "partial",
        "unusable",
        "failed_validation",
        "missing",
    ]
    status_lines = [
        f"  - {status.upper()}: {int(statuses.get(status, 0))}"
        for status in status_order
        if status in statuses
    ]
    warning_lines = [f"  - {code}: {count}" for code, count in warning_summary[:8]]
    if len(warning_summary) > 8:
        warning_lines.append(f"  - other_codes: {len(warning_summary) - 8}")
    if language == "zh":
        safe_claim = (
            "当前证据只支持在已导入的任务、模型、种子和实验协议范围内报告结果; "
            "不能据此声称完整研究支持或通用基准结论。"
        )
        lines = [
            "PEOC 研究证据导入",
            "证据来源: REAL PEOC BUNDLE",
            f"输出目录: {output_dir}",
            f"源文件数量: {source_count}",
            "状态计数:",
            *status_lines,
            f"最强安全结论: {safe_claim}",
            (
                "结论边界: "
                f"full_research_support={full_support}; "
                f"status={boundary_status}; 阻断部分={blocking}"
            ),
            f"警告: {len(warnings)} 条, 归为 {len(warning_counts)} 类",
            *warning_lines,
            f"案例报告: {case_study_path}",
            (
                f"证据卡: {evidence.get('path', output_dir / 'evidence_card.html')} "
                f"(recommendation={evidence.get('recommendation', 'unknown')})"
            ),
            (
                f"主张检查: {claim.get('path', output_dir / 'claim_check.html')} "
                f"(status={claim.get('status', 'unknown')})"
            ),
            (
                f"研究缺口计划: {plan.get('path', output_dir / 'research_gap_plan.html')} "
                f"(actions={plan.get('action_count', 'unknown')})"
            ),
            (
                f"研究缺口状态: {gap.get('path', output_dir / 'research_gap_status.html')} "
                f"(status={gap.get('status', 'unknown')})"
            ),
            (
                f"研究证据包: {bundle.get('path', output_dir / 'research_bundle.html')} "
                f"(status={bundle.get('status', 'unknown')})"
            ),
            "下一步:",
            "  - 先打开研究证据包, 再按顺序查看案例、证据卡和主张检查。",
        ]
        return "\n".join(lines)

    safe_claim = str(
        case_study.get(
            "safe_claim",
            (
                "The imported evidence supports only task-, model-, seed-, and "
                "protocol-bounded findings."
            ),
        )
    )
    lines = [
        "PEOC research evidence import",
        "Evidence source: REAL PEOC BUNDLE",
        f"Output directory: {output_dir}",
        f"Source count: {source_count}",
        "Status counts:",
        *status_lines,
        f"Strongest safe claim: {safe_claim}",
        (
            "Claim boundary: "
            f"full_research_support={full_support}; "
            f"status={boundary_status}; blocking_sections={blocking}"
        ),
        f"Warnings: {len(warnings)} total across {len(warning_counts)} code(s)",
        *warning_lines,
        f"Case study: {case_study_path}",
        (
            f"Evidence card: {evidence.get('path', output_dir / 'evidence_card.html')} "
            f"(recommendation={evidence.get('recommendation', 'unknown')})"
        ),
        (
            f"Claim check: {claim.get('path', output_dir / 'claim_check.html')} "
            f"(status={claim.get('status', 'unknown')})"
        ),
        (
            f"Research gap plan: {plan.get('path', output_dir / 'research_gap_plan.html')} "
            f"(actions={plan.get('action_count', 'unknown')})"
        ),
        (
            f"Research gap status: {gap.get('path', output_dir / 'research_gap_status.html')} "
            f"(status={gap.get('status', 'unknown')})"
        ),
        (
            f"Research bundle: {bundle.get('path', output_dir / 'research_bundle.html')} "
            f"(status={bundle.get('status', 'unknown')})"
        ),
        "Next:",
        "  - Open the research bundle, then review the case study, evidence card, and claim check.",
    ]
    return "\n".join(lines)


def _format_peoc_blocking_sections(value: object) -> str:
    if not isinstance(value, list) or not value:
        return "none"
    entries: list[str] = []
    for item in value:
        if isinstance(item, dict):
            section = str(item.get("section", "unknown"))
            status = str(item.get("status", "unknown"))
            entries.append(f"{section}={status}")
        else:
            entries.append(str(item))
    return ", ".join(entries)


def _cmd_evidence_card(args: argparse.Namespace) -> None:
    """Execute the evidence card command handler."""
    payload = write_evidence_card(args.run, markdown_path=args.out, json_path=args.json_out)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
