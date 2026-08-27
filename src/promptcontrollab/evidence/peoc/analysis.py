"""PEOC source validation and bounded case-study construction."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import TypeGuard, cast

from promptcontrollab.core.files import JsonDict
from promptcontrollab.evidence.peoc.common import (
    PeocSourceOverrides,
    _file_integrity,
    _sha256_bytes,
    _strict_json_text,
    _TrajectoryBinaryResults,
)
from promptcontrollab.evidence.peoc.constants import MANIFEST, SEED_PATTERN, TRAJECTORY_ROOT

_MANIFEST = MANIFEST
_SEED_PATTERN = SEED_PATTERN


def _build_case_study(
    source_manifest: JsonDict,
    evidence: JsonDict,
) -> JsonDict:
    """Build a bounded case study from validated PEOC evidence sections."""

    sections = evidence.get("sections")
    section_rows = sections if isinstance(sections, dict) else {}
    status_counts = _status_counts(section_rows)
    hard = _section_dict(section_rows, "hard_evaluation")
    hard_observations = _dict_value(hard.get("observations"))
    trajectory = _section_dict(section_rows, "trajectory")
    trajectory_observations = _dict_value(trajectory.get("observations"))
    stage = _section_dict(section_rows, "stage_heterogeneity")
    stage_observations = _dict_value(stage.get("observations"))
    bundle = _dict_value(source_manifest.get("bundle"))
    source_inventory = [
        {
            "role": str(source.get("role", "")),
            "relative_path": _relative_path(source),
            "sha256": source.get("sha256"),
            "bytes": source.get("bytes"),
        }
        for source in sorted(
            _manifest_sources(source_manifest),
            key=lambda row: (_relative_path(row), str(row.get("role", ""))),
        )
    ]
    limited_sections = _limited_sections(section_rows)
    claim_boundary = _public_json(evidence.get("claim_boundary"))
    if not isinstance(claim_boundary, dict):
        claim_boundary = {}
    warnings = [
        item
        for item in [
            *_warning_rows(source_manifest.get("warnings")),
            *_warning_rows(evidence.get("warnings")),
        ]
    ]
    warnings.sort(key=_warning_sort_key)
    hard_rows = [
        cast(JsonDict, _public_json(row)) for row in _dict_rows(hard_observations.get("rows"))
    ]
    selected_pair = _trajectory_case_pair(_dict_value(trajectory_observations.get("headline_pair")))
    limitations = _case_limitations(section_rows)

    return {
        "schema": "prompt_control_lab.peoc_case_study.v1",
        "evidence_source": "REAL PEOC BUNDLE",
        "evidence_origin": "real",
        "manifest_hash": bundle.get("manifest_sha256"),
        "source_manifest_sha256": _sha256_bytes(_strict_json_text(source_manifest).encode("utf-8")),
        "status_counts": status_counts,
        "hard_summary": {
            "status": hard.get("status"),
            "metric": hard_observations.get("metric"),
            "row_count": hard_observations.get("row_count"),
            "valid_row_count": hard_observations.get("valid_row_count"),
            "excluded_row_count": hard_observations.get("excluded_row_count"),
            "models": hard_observations.get("models", []),
            "tasks": hard_observations.get("tasks", []),
            "methods": hard_observations.get("methods", []),
        },
        "hard_method_rows": hard_rows,
        "trajectory_status": trajectory.get("status"),
        "selected_trajectory_pair": selected_pair,
        "stage_validation": {
            "status": stage.get("status"),
            "display_status": stage.get("display_status"),
            "verdict": stage_observations.get("verdict"),
            "held_spearman_rho": stage_observations.get("held_spearman_rho"),
            "held_bootstrap_ci": stage_observations.get("held_bootstrap_ci"),
            "source": _case_source(_dict_value(stage_observations.get("source"))),
        },
        "limited_sections": limited_sections,
        "source_inventory": source_inventory,
        "safe_claim": _safe_claim(section_rows, selected_pair),
        "safe_claim_zh": _safe_claim_zh(section_rows, selected_pair),
        "limitations": limitations,
        "limitations_zh": _case_limitations_zh(section_rows),
        "warnings": [_public_json(warning) for warning in warnings],
        "claim_boundary": claim_boundary,
    }


def _status_counts(sections: JsonDict) -> JsonDict:
    counts: JsonDict = {
        "available": 0,
        "failed_validation": 0,
        "missing": 0,
        "partial": 0,
        "unusable": 0,
    }
    for section in sections.values():
        if not isinstance(section, dict):
            continue
        status = str(section.get("status", "unusable"))
        counts[status] = int(counts.get(status, 0)) + 1
    return counts


def _limited_sections(sections: JsonDict) -> list[JsonDict]:
    rows: list[JsonDict] = []
    for name, value in sorted(sections.items()):
        if not isinstance(value, dict) or value.get("status") == "available":
            continue
        limitations = value.get("limitations")
        limitation_values = limitations if isinstance(limitations, list) else []
        status = str(value.get("status", "unusable"))
        rows.append(
            {
                "section": name,
                "origin": value.get("origin"),
                "status": status,
                "display_status": value.get("display_status"),
                "limitation": (
                    str(limitation_values[0])
                    if limitation_values
                    else "This evidence section is not available for a positive claim."
                ),
                "limitation_zh": _status_limitation_zh(status),
            }
        )
    return rows


def _trajectory_case_pair(pair: JsonDict) -> JsonDict:
    if not pair:
        return {}
    return {
        "model": pair.get("model"),
        "normalized_model": pair.get("normalized_model"),
        "seed": pair.get("seed"),
        "stationary": _trajectory_case_arm(_dict_value(pair.get("stationary"))),
        "heterogeneous": _trajectory_case_arm(_dict_value(pair.get("heterogeneous"))),
    }


def _trajectory_case_arm(entry: JsonDict) -> JsonDict:
    if not entry:
        return {}
    summary = _dict_value(entry.get("summary"))
    source = _case_source(_dict_value(entry.get("source")))
    return {
        "status": entry.get("status"),
        "relative_path": source.get("relative_path"),
        "sha256": source.get("sha256"),
        "bytes": source.get("bytes"),
        "hidden_dim": summary.get("hidden_dim"),
        "alpha_emp_mean": summary.get("alpha_emp_mean"),
        "alpha_emp_std": summary.get("alpha_emp_std"),
        "R2_mean": summary.get("R2_mean"),
        "R2_std": summary.get("R2_std"),
        "n_streams": summary.get("n_streams"),
        "n_prompts": summary.get("n_prompts"),
        "binary_references": [
            _case_source(reference) for reference in _dict_rows(entry.get("binary_references"))
        ],
    }


def _case_source(source: JsonDict) -> JsonDict:
    return {
        "role": source.get("role"),
        "relative_path": source.get("relative_path"),
        "sha256": source.get("sha256"),
        "bytes": source.get("bytes"),
    }


def _safe_claim(sections: JsonDict, pair: JsonDict) -> str:
    statements = [
        (
            "This bounded case study reports the imported PEOC measurements and "
            "their recorded limitations; it is not a universal benchmark."
        )
    ]
    hard = _section_dict(sections, "hard_evaluation")
    if hard.get("status") == "available":
        statements.append(
            "The hard-test summary contains task-, model-, and method-specific results."
        )
    trajectory = _section_dict(sections, "trajectory")
    if trajectory.get("status") == "available":
        stationary = _dict_value(pair.get("stationary"))
        heterogeneous = _dict_value(pair.get("heterogeneous"))
        stationary_alpha = stationary.get("alpha_emp_mean")
        heterogeneous_alpha = heterogeneous.get("alpha_emp_mean")
        if (
            _is_number(stationary_alpha)
            and _is_number(heterogeneous_alpha)
            and stationary_alpha > heterogeneous_alpha
        ):
            statements.append(
                "For the selected paired summaries, stationary arithmetic traces report "
                "a stronger fitted decay signature than heterogeneous GSM8K traces."
            )
    stage = _section_dict(sections, "stage_heterogeneity")
    if stage.get("status") == "failed_validation":
        statements.append("The stage-heterogeneity validation reported FAIL.")
    soft = _section_dict(sections, "soft_evaluation")
    if soft.get("status") == "unusable":
        statements.append("The segmented soft summary is unusable for a positive claim.")
    return " ".join(statements)


def _safe_claim_zh(sections: JsonDict, pair: JsonDict) -> str:
    statements = ["本案例只报告导入的 PEOC 测量结果及其限制, 不代表通用基准结论。"]
    if _section_dict(sections, "hard_evaluation").get("status") == "available":
        statements.append("Hard-test 汇总提供了任务、模型和方法层面的具体结果。")
    trajectory = _section_dict(sections, "trajectory")
    if trajectory.get("status") == "available":
        stationary = _dict_value(pair.get("stationary"))
        heterogeneous = _dict_value(pair.get("heterogeneous"))
        stationary_alpha = stationary.get("alpha_emp_mean")
        heterogeneous_alpha = heterogeneous.get("alpha_emp_mean")
        if (
            _is_number(stationary_alpha)
            and _is_number(heterogeneous_alpha)
            and stationary_alpha > heterogeneous_alpha
        ):
            statements.append("在选中的配对汇总中, 平稳算术轨迹的拟合衰减信号强于异质 GSM8K 轨迹。")
    if _section_dict(sections, "stage_heterogeneity").get("status") == ("failed_validation"):
        statements.append("阶段异质性验证的记录结果为 FAIL。")
    if _section_dict(sections, "soft_evaluation").get("status") == "unusable":
        statements.append("分段 soft 汇总不能用于支持正向结论。")
    return "".join(statements)


def _case_limitations(sections: JsonDict) -> list[str]:
    values = [
        "The import packages existing evidence; it introduces no new scientific result.",
        ("Diagnostics are bounded to the imported tasks, models, seeds, and recorded protocol."),
        (
            "Trajectory decay is diagnostic evidence, not proof of universal "
            "turnpike behavior or operational stability."
        ),
    ]
    for section in sections.values():
        if not isinstance(section, dict):
            continue
        limitations = section.get("limitations")
        if not isinstance(limitations, list):
            continue
        values.extend(str(value) for value in limitations)
    return list(dict.fromkeys(values))


def _case_limitations_zh(sections: JsonDict) -> list[str]:
    values = [
        "该导入流程只整理已有证据, 不产生新的科学结果。",
        "诊断结论只适用于导入记录中的任务、模型、随机种子和实验协议。",
        "轨迹衰减属于诊断信号, 不等于普遍 turnpike 规律或运行稳定性的证明。",
    ]
    values.extend(
        _status_limitation_zh(str(section.get("status", "unusable")))
        for section in sections.values()
        if isinstance(section, dict) and section.get("status") != "available"
    )
    return list(dict.fromkeys(values))


def _status_limitation_zh(status: str) -> str:
    return {
        "failed_validation": "该部分的真实验证结果未通过, 不能作为正向证据。",
        "missing": "导入的 PEOC bundle 中没有发现该部分的证据。",
        "partial": "该部分只有部分证据可用, 仍需人工检查缺失或损坏来源。",
        "unusable": "该部分虽然有真实来源, 但当前数据不可用于支持正向结论。",
    }.get(status, "该证据部分当前不能用于支持正向结论。")


def _section_dict(sections: JsonDict, name: str) -> JsonDict:
    return _dict_value(sections.get(name))


def _dict_value(value: object) -> JsonDict:
    return value if isinstance(value, dict) else {}


def _dict_rows(value: object) -> list[JsonDict]:
    if not isinstance(value, list):
        return []
    return [cast(JsonDict, row) for row in value if isinstance(row, dict)]


def _warning_rows(value: object) -> list[JsonDict]:
    return _dict_rows(value)


def _public_json(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): _public_json(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) != "resolved_path"
        }
    if isinstance(value, list):
        return [_public_json(item) for item in value]
    return value


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _build_hard_section(
    root: Path,
    sources: list[JsonDict],
    warnings: list[JsonDict],
) -> JsonDict:
    """Build the hard-evaluation section from its verified source summary."""

    source = _first_source(sources, "hard_test_summary")
    if source is None:
        raise ValueError("Missing required hard-test summary source in source manifest")
    raw = _read_required_json(root, source, label="hard-test summary")
    if not isinstance(raw, dict) or not isinstance(raw.get("summary"), list):
        path = _source_path(root, source, label="hard-test summary")
        msg = f"Invalid required hard-test summary {path}: expected top-level summary list"
        raise ValueError(msg)

    relative_path = _relative_path(source)
    normalized = _finite_json(
        raw,
        warnings,
        source_role="hard_test_summary",
        relative_path=relative_path,
    )
    payload = cast(JsonDict, normalized)
    summary = cast(list[object], payload["summary"])
    valid_rows: list[JsonDict] = []
    excluded_rows: list[JsonDict] = []
    for index, row in enumerate(summary):
        normalized_row = row if isinstance(row, dict) else {"value": row}
        raw_row = raw["summary"][index]
        reason = _summary_row_exclusion_reason(
            raw_row,
            normalized_row,
            default_metric=payload.get("metric"),
        )
        if reason is None:
            valid_rows.append(cast(JsonDict, normalized_row))
        else:
            excluded_rows.append(
                {
                    "index": index,
                    "reason": reason,
                    "row": normalized_row,
                }
            )

    tests = payload.get("tests")
    source_tests = tests if isinstance(tests, list) else []
    status = "available" if valid_rows else "unusable"
    limitations = ["Aggregate hard-test results do not establish universal prompt superiority."]
    if excluded_rows:
        limitations.append(
            "Rows missing required identity/statistical fields, containing invalid values, "
            "or using out-of-range bounded metrics were excluded."
        )
    return _section(
        origin="real",
        status=status,
        source_roles=["hard_test_summary"],
        observations={
            "source": _source_reference(source),
            "metric": payload.get("metric"),
            "row_count": len(summary),
            "valid_row_count": len(valid_rows),
            "excluded_row_count": len(excluded_rows),
            "models": _distinct_strings(valid_rows, "model"),
            "tasks": _distinct_strings(valid_rows, "task"),
            "methods": _distinct_strings(valid_rows, "method"),
            "rows": valid_rows,
            "excluded_rows": excluded_rows,
            "source_tests": source_tests,
        },
        limitations=limitations,
    )


def _build_soft_section(
    root: Path,
    sources: list[JsonDict],
    warnings: list[JsonDict],
) -> JsonDict:
    """Build the optional soft-evaluation section with explicit evidence limits."""

    source = _first_source(sources, "soft_segmented_summary")
    if source is None:
        return _missing_section(
            "No segmented soft-evaluation summary was discovered in this PEOC bundle."
        )
    raw, error, warning_code = _read_optional_json(root, source)
    if error is not None or not isinstance(raw, dict) or not isinstance(raw.get("summary"), list):
        return _invalid_optional_section(
            source,
            warnings,
            error or "expected top-level summary list",
            warning_code=warning_code or "invalid_optional_source",
        )

    normalized = _finite_json(
        raw,
        warnings,
        source_role="soft_segmented_summary",
        relative_path=_relative_path(source),
    )
    payload = cast(JsonDict, normalized)
    summary = cast(list[object], payload["summary"])
    valid_rows: list[JsonDict] = []
    excluded_rows: list[JsonDict] = []
    zero_count_rows = 0
    for index, row in enumerate(summary):
        normalized_row = row if isinstance(row, dict) else {"value": row}
        raw_row = raw["summary"][index]
        reason = _summary_row_exclusion_reason(
            raw_row,
            normalized_row,
            default_metric=payload.get("metric"),
        )
        if reason is None:
            valid_rows.append(cast(JsonDict, normalized_row))
        else:
            if reason == "non_positive_n":
                zero_count_rows += 1
            excluded_rows.append({"index": index, "reason": reason, "row": normalized_row})

    status = "available" if valid_rows else "unusable"
    limitations = [
        "Segmented soft evaluation is unusable when no row has a positive sample count."
        if not valid_rows
        else "Soft evaluation remains specific to the imported tasks, models, and protocol."
    ]
    return _section(
        origin="real",
        status=status,
        source_roles=["soft_segmented_summary"],
        observations={
            "source": _source_reference(source),
            "metric": payload.get("metric"),
            "summary_row_count": len(summary),
            "valid_row_count": len(valid_rows),
            "zero_count_row_count": zero_count_rows,
            "rows": summary,
            "valid_rows": valid_rows,
            "excluded_rows": excluded_rows,
            "source_tests": payload.get("tests") if isinstance(payload.get("tests"), list) else [],
        },
        limitations=limitations,
    )


def _build_trajectory_section(
    root: Path,
    sources: list[JsonDict],
    warnings: list[JsonDict],
) -> JsonDict:
    """Build trajectory findings from verified summaries and binary artifacts."""

    trajectory_sources = [
        source
        for source in sources
        if source.get("role") in {"trajectory_stationary", "trajectory_heterogeneous"}
    ]
    binary_sources = [source for source in sources if source.get("role") == "trajectory_binary"]
    if not trajectory_sources:
        return _missing_section("No trajectory summary was discovered in this PEOC bundle.")

    entries: list[JsonDict] = []
    grouped: dict[tuple[str, int], dict[str, JsonDict]] = {}
    binary_results = _verify_trajectory_binaries(root, binary_sources, warnings)
    for source in trajectory_sources:
        role = str(source.get("role"))
        binary_key = Path(_relative_path(source)).as_posix()
        binary_references = binary_results.valid.get(binary_key, [])
        invalid_binary_references = binary_results.invalid.get(binary_key, [])
        raw, error, warning_code = _read_optional_json(root, source)
        if error is not None or not isinstance(raw, dict):
            entries.append(
                _invalid_trajectory_entry(
                    source,
                    warnings,
                    error or "expected a JSON object",
                    warning_code=warning_code or "invalid_optional_source",
                    binary_references=binary_references,
                    invalid_binary_references=invalid_binary_references,
                )
            )
            continue
        normalized = _finite_json(
            raw,
            warnings,
            source_role=role,
            relative_path=_relative_path(source),
        )
        payload = cast(JsonDict, normalized)
        model = payload.get("model")
        seed, seed_source = _trajectory_seed(payload, source)
        if not isinstance(model, str) or not model.strip() or seed is None:
            entries.append(
                _invalid_trajectory_entry(
                    source,
                    warnings,
                    "trajectory summary requires a model and integer seed or _s<seed> filename",
                    warning_code="invalid_optional_source",
                    binary_references=binary_references,
                    invalid_binary_references=invalid_binary_references,
                )
            )
            continue
        scientific_error = _trajectory_summary_error(payload, role)
        if scientific_error is not None:
            entries.append(
                _invalid_trajectory_entry(
                    source,
                    warnings,
                    scientific_error,
                    warning_code="invalid_scientific_payload",
                    binary_references=binary_references,
                    invalid_binary_references=invalid_binary_references,
                )
            )
            continue
        normalized_model = _normalize_model_id(model)
        entry: JsonDict = {
            "origin": "real",
            "status": "available",
            "display_status": _display_status("real", "available"),
            "role": role,
            "source": _source_reference(source),
            "model": model,
            "normalized_model": normalized_model,
            "seed": seed,
            "seed_source": seed_source,
            "summary": payload,
            "binary_references": binary_references,
            "invalid_binary_references": invalid_binary_references,
        }
        entries.append(entry)
        grouped.setdefault((normalized_model, seed), {})[role] = entry

    pairs: list[JsonDict] = []
    for (normalized_model, seed), pair_entries in sorted(grouped.items()):
        stationary = pair_entries.get("trajectory_stationary")
        heterogeneous = pair_entries.get("trajectory_heterogeneous")
        if stationary is None or heterogeneous is None:
            continue
        pairs.append(
            {
                "model": stationary["model"],
                "normalized_model": normalized_model,
                "seed": seed,
                "stationary": stationary,
                "heterogeneous": heterogeneous,
            }
        )
    headline_pair = _headline_trajectory_pair(pairs)
    has_unusable_source = any(entry.get("status") != "available" for entry in entries)
    invalid_binary_references = binary_results.all_invalid
    if headline_pair is None:
        status = "unusable"
    elif has_unusable_source or invalid_binary_references:
        status = "partial"
    else:
        status = "available"
    limitations = [
        "Trajectory decay is a diagnostic signal, not proof of operational model stability.",
        "Sibling NPZ files are referenced and hashed only; they are not loaded or copied.",
    ]
    if headline_pair is None:
        limitations.append("No complete stationary/heterogeneous model-and-seed pair was usable.")
    elif status == "partial":
        limitations.append(
            "A complete pair is available, but at least one discovered trajectory source "
            "or binary reference is unusable."
        )
    return _section(
        origin="real",
        status=status,
        source_roles=sorted({str(source.get("role")) for source in trajectory_sources}),
        observations={
            "entries": entries,
            "pairs": pairs,
            "headline_pair": headline_pair,
            "binary_references": binary_results.all_valid,
            "invalid_binary_references": invalid_binary_references,
        },
        limitations=limitations,
    )


def _build_stage_section(
    root: Path,
    sources: list[JsonDict],
    warnings: list[JsonDict],
) -> JsonDict:
    """Build the stage-heterogeneity section from validated source evidence."""

    source = _first_source(sources, "stage_heterogeneity")
    if source is None:
        return _missing_section(
            "No stage-heterogeneity validation summary was discovered in this PEOC bundle."
        )
    raw, error, warning_code = _read_optional_json(root, source)
    if error is not None or not isinstance(raw, dict):
        return _invalid_optional_section(
            source,
            warnings,
            error or "expected a JSON object",
            warning_code=warning_code or "invalid_optional_source",
        )
    normalized = _finite_json(
        raw,
        warnings,
        source_role="stage_heterogeneity",
        relative_path=_relative_path(source),
    )
    payload = cast(JsonDict, normalized)
    verdict = payload.get("verdict")
    normalized_verdict = verdict.upper() if isinstance(verdict, str) else ""
    validation_error = _stage_validation_error(payload)
    if validation_error is not None:
        _append_optional_warning(
            warnings,
            source,
            validation_error,
            code="invalid_scientific_payload",
        )
        return _section(
            origin="real",
            status="unusable",
            source_roles=["stage_heterogeneity"],
            observations={
                "source": _source_reference(source),
                "verdict": verdict,
                "error": validation_error,
                "observed_keys": sorted(payload),
                "data": payload,
            },
            limitations=[
                "The stage-heterogeneity source lacks a complete, valid validation design.",
                "No positive evidence was inferred from the incomplete scientific payload.",
            ],
        )
    if normalized_verdict == "FAIL":
        status = "failed_validation"
    elif normalized_verdict == "PASS":
        status = "available"
    else:
        status = "unusable"
    return _section(
        origin="real",
        status=status,
        source_roles=["stage_heterogeneity"],
        observations={
            "source": _source_reference(source),
            "verdict": verdict,
            "held_spearman_rho": payload.get("held_spearman_rho"),
            "held_bootstrap_ci": payload.get("held_bootstrap_ci"),
            "cells": payload.get("cells"),
            "observed_keys": sorted(payload),
            "data": payload,
        },
        limitations=[
            (
                "A failed validation verdict is retained as negative evidence "
                "and does not support the diagnostic."
            )
            if status == "failed_validation"
            else "Stage-heterogeneity results apply only to the imported validation design."
        ],
    )


def _section(
    *,
    origin: str,
    status: str,
    source_roles: list[str],
    observations: JsonDict,
    limitations: list[str],
) -> JsonDict:
    return {
        "origin": origin,
        "status": status,
        "display_status": _display_status(origin, status),
        "source_roles": source_roles,
        "observations": observations,
        "limitations": limitations,
    }


def _missing_section(limitation: str) -> JsonDict:
    return _section(
        origin="none",
        status="missing",
        source_roles=[],
        observations={},
        limitations=[limitation, "No synthetic substitute was created."],
    )


def _invalid_optional_section(
    source: JsonDict,
    warnings: list[JsonDict],
    error: str,
    *,
    warning_code: str,
) -> JsonDict:
    role = str(source.get("role", "optional_source"))
    _append_optional_warning(warnings, source, error, code=warning_code)
    return _section(
        origin="real",
        status="unusable",
        source_roles=[role],
        observations={"source": _source_reference(source), "error": error},
        limitations=[
            "The real source was discovered but could not be parsed as usable evidence.",
            "No positive evidence was inferred from the invalid source.",
        ],
    )


def _invalid_trajectory_entry(
    source: JsonDict,
    warnings: list[JsonDict],
    error: str,
    *,
    warning_code: str,
    binary_references: list[JsonDict],
    invalid_binary_references: list[JsonDict],
) -> JsonDict:
    _append_optional_warning(warnings, source, error, code=warning_code)
    return {
        "origin": "real",
        "status": "unusable",
        "display_status": _display_status("real", "unusable"),
        "role": source.get("role"),
        "source": _source_reference(source),
        "error": error,
        "binary_references": binary_references,
        "invalid_binary_references": invalid_binary_references,
    }


def _append_optional_warning(
    warnings: list[JsonDict],
    source: JsonDict,
    error: str,
    *,
    code: str,
) -> None:
    warnings.append(
        {
            "code": code,
            "source_role": str(source.get("role", "optional_source")),
            "relative_path": _relative_path(source),
            "json_path": "$",
            "message": error,
        }
    )


def _manifest_sources(source_manifest: JsonDict) -> list[JsonDict]:
    sources = source_manifest.get("sources")
    if not isinstance(sources, list):
        raise ValueError("PEOC source manifest must contain a sources list")
    return [cast(JsonDict, source) for source in sources if isinstance(source, dict)]


def _first_source(sources: list[JsonDict], role: str) -> JsonDict | None:
    return next((source for source in sources if source.get("role") == role), None)


def _verify_bundle_manifest(
    root: Path,
    sources: list[JsonDict],
    source_manifest: JsonDict,
) -> None:
    source = _first_source(sources, "bundle_manifest")
    if source is None:
        raise ValueError("Missing required bundle manifest source row")
    relative_path = _relative_path(source)
    if relative_path != _MANIFEST.as_posix():
        msg = (
            "Bundle manifest source must reference README_MANIFEST.md, "
            f"not {relative_path or '<missing>'}"
        )
        raise ValueError(msg)
    path = _source_path(root, source, label="bundle manifest")
    try:
        observed_size, observed_sha256 = _file_integrity(path)
    except OSError as exc:
        msg = f"bundle manifest source changed after discovery: {path}: {exc}"
        raise ValueError(msg) from exc
    integrity_error = _source_integrity_error(
        source,
        observed_size,
        observed_sha256,
    )
    if integrity_error is not None:
        msg = f"bundle manifest source changed after discovery: {path}: {integrity_error}"
        raise ValueError(msg)

    bundle = source_manifest.get("bundle")
    if not isinstance(bundle, dict):
        raise ValueError("PEOC source manifest must contain bundle metadata")
    manifest_relative_path = bundle.get("manifest_relative_path")
    if manifest_relative_path != _MANIFEST.as_posix():
        msg = (
            "Bundle metadata must reference README_MANIFEST.md, "
            f"not {manifest_relative_path or '<missing>'}"
        )
        raise ValueError(msg)
    declared_sha256 = bundle.get("manifest_sha256")
    if declared_sha256 != observed_sha256:
        msg = (
            "bundle manifest hash changed after discovery: "
            f"expected {declared_sha256}, observed {observed_sha256}"
        )
        raise ValueError(msg)


def _read_required_json(root: Path, source: JsonDict, *, label: str) -> object:
    path = _source_path(root, source, label=label)
    try:
        data = path.read_bytes()
    except OSError as exc:
        msg = f"{label} source changed after discovery: {path}: {exc}"
        raise ValueError(msg) from exc
    integrity_error = _source_integrity_error(source, len(data), _sha256_bytes(data))
    if integrity_error is not None:
        msg = f"{label} source changed after discovery: {path}: {integrity_error}"
        raise ValueError(msg)
    try:
        return json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        msg = f"Invalid required {label} {path}: {exc}"
        raise ValueError(msg) from exc


def _read_optional_json(
    root: Path,
    source: JsonDict,
) -> tuple[object | None, str | None, str | None]:
    role = str(source.get("role", "optional source"))
    try:
        path = _source_path(root, source, label=role)
    except ValueError as exc:
        return None, str(exc), "invalid_optional_source"
    try:
        data = path.read_bytes()
    except OSError as exc:
        message = (
            f"{role} source changed after discovery: {_relative_path(source)}: {type(exc).__name__}"
        )
        return None, message, "source_integrity_mismatch"
    integrity_error = _source_integrity_error(source, len(data), _sha256_bytes(data))
    if integrity_error is not None:
        message = (
            f"{role} source changed after discovery: {_relative_path(source)}: {integrity_error}"
        )
        return None, message, "source_integrity_mismatch"
    try:
        return json.loads(data.decode("utf-8-sig")), None, None
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, str(exc), "invalid_optional_source"


def _source_path(root: Path, source: JsonDict, *, label: str) -> Path:
    relative_path = source.get("relative_path")
    if not isinstance(relative_path, str) or not relative_path:
        msg = f"{label} source is missing relative_path"
        raise ValueError(msg)
    return _resolve_bundle_path(root, Path(relative_path), label=label)


def _relative_path(source: JsonDict) -> str:
    value = source.get("relative_path")
    return str(value) if value is not None else ""


def _source_reference(source: JsonDict) -> JsonDict:
    keys = (
        "role",
        "relative_path",
        "resolved_path",
        "bytes",
        "sha256",
        "media_type",
        "selection",
        "copied_path",
    )
    return {key: source.get(key) for key in keys}


def _source_integrity_error(
    source: JsonDict,
    observed_size: int,
    observed_sha256: str,
) -> str | None:
    differences: list[str] = []
    expected_size = source.get("bytes")
    if isinstance(expected_size, int) and not isinstance(expected_size, bool):
        if expected_size != observed_size:
            differences.append(f"bytes expected {expected_size}, observed {observed_size}")
    elif expected_size is not None:
        differences.append(f"bytes metadata is invalid: {expected_size!r}")

    expected_sha256 = source.get("sha256")
    if not isinstance(expected_sha256, str) or not expected_sha256:
        differences.append("sha256 metadata is unavailable")
    elif expected_sha256 != observed_sha256:
        differences.append(f"sha256 expected {expected_sha256}, observed {observed_sha256}")
    return "; ".join(differences) if differences else None


def _finite_json(
    value: object,
    warnings: list[JsonDict],
    *,
    source_role: str,
    relative_path: str | None,
    json_path: str = "$",
) -> object:
    if isinstance(value, float) and not math.isfinite(value):
        warnings.append(
            {
                "code": "non_finite_value",
                "source_role": source_role,
                "relative_path": relative_path,
                "json_path": json_path,
                "message": "Non-finite numeric value was normalized to null.",
            }
        )
        return None
    if isinstance(value, dict):
        return {
            str(key): _finite_json(
                item,
                warnings,
                source_role=source_role,
                relative_path=relative_path,
                json_path=f"{json_path}.{key}",
            )
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, list):
        return [
            _finite_json(
                item,
                warnings,
                source_role=source_role,
                relative_path=relative_path,
                json_path=f"{json_path}[{index}]",
            )
            for index, item in enumerate(value)
        ]
    return value


def _summary_row_exclusion_reason(
    raw_row: object,
    normalized_row: object,
    *,
    default_metric: object,
) -> str | None:
    if not isinstance(raw_row, dict) or not isinstance(normalized_row, dict):
        return "row_not_object"
    for field in ("model", "task", "method"):
        value = normalized_row.get(field)
        if not isinstance(value, str) or not value.strip():
            return f"missing_{field}"
    metric = normalized_row.get("metric", default_metric)
    if not isinstance(metric, str) or not metric.strip():
        return "missing_metric"
    raw_n = raw_row.get("n")
    n = normalized_row.get("n")
    if isinstance(raw_n, float) and not math.isfinite(raw_n):
        return "non_finite_n"
    if not _is_number(n):
        return "invalid_n"
    if n <= 0:
        return "non_positive_n"
    raw_mean = raw_row.get("mean")
    mean = normalized_row.get("mean")
    if isinstance(raw_mean, float) and not math.isfinite(raw_mean):
        return "non_finite_mean"
    if not _is_number(mean):
        return "invalid_mean"
    if _is_bounded_score_metric(metric) and not 0 <= mean <= 1:
        return "mean_out_of_range"
    raw_sd = raw_row.get("sd")
    sd = normalized_row.get("sd")
    if isinstance(raw_sd, float) and not math.isfinite(raw_sd):
        return "non_finite_sd"
    if not _is_number(sd):
        return "invalid_sd"
    if sd < 0:
        return "negative_sd"
    return None


def _is_bounded_score_metric(metric: str) -> bool:
    normalized = metric.strip().lower().replace("-", "_")
    return any(
        token in normalized for token in ("accuracy", "acc_", "_acc", "exact_match", "success_rate")
    )


def _trajectory_summary_error(payload: JsonDict, role: str) -> str | None:
    numeric_fields = ("alpha_emp_mean", "alpha_emp_std", "R2_mean", "R2_std")
    for field in numeric_fields:
        value = payload.get(field)
        if not _is_number(value):
            return f"trajectory summary requires finite numeric {field}"
    if cast(float, payload["alpha_emp_std"]) < 0:
        return "trajectory summary requires non-negative alpha_emp_std"
    if cast(float, payload["R2_std"]) < 0:
        return "trajectory summary requires non-negative R2_std"
    if cast(float, payload["R2_mean"]) > 1:
        return "trajectory summary requires R2_mean <= 1"
    hidden_dim = payload.get("hidden_dim")
    if not _is_positive_integer(hidden_dim):
        return "trajectory summary requires a positive integer hidden_dim"

    if role == "trajectory_stationary":
        count_field = "n_streams"
        alpha_field = "per_stream_alphas"
        r2_field = "per_stream_R2"
    else:
        task = payload.get("task")
        if not isinstance(task, str) or not task.strip():
            return "heterogeneous trajectory summary requires a task"
        count_field = "n_prompts"
        alpha_field = "per_prompt_alphas"
        r2_field = "per_prompt_R2"
    if not _is_positive_integer(payload.get(count_field)):
        return f"trajectory summary requires a positive integer {count_field}"
    alpha_values = payload.get(alpha_field)
    r2_values = payload.get(r2_field)
    if not _finite_numeric_list(alpha_values):
        return f"trajectory summary requires a non-empty finite {alpha_field} array"
    if not _finite_numeric_list(r2_values):
        return f"trajectory summary requires a non-empty finite {r2_field} array"
    if len(cast(list[object], alpha_values)) != len(cast(list[object], r2_values)):
        return "trajectory per-sample alpha and R2 arrays must have equal lengths"
    if any(cast(float, value) > 1 for value in cast(list[object], r2_values)):
        return f"trajectory {r2_field} values must be <= 1"
    return None


def _stage_validation_error(payload: JsonDict) -> str | None:
    verdict = payload.get("verdict")
    if not isinstance(verdict, str) or verdict.upper() not in {"PASS", "FAIL"}:
        return "stage validation requires verdict PASS or FAIL"
    round_value = payload.get("round")
    if not _is_nonnegative_integer(round_value):
        return "stage validation requires a non-negative integer round"
    variant = payload.get("variant")
    if not isinstance(variant, str) or not variant.strip():
        return "stage validation requires a non-empty variant"
    rho = payload.get("held_spearman_rho")
    if not _is_number(rho) or not -1 <= rho <= 1:
        return "stage validation requires held_spearman_rho in [-1, 1]"
    interval = payload.get("held_bootstrap_ci")
    if not isinstance(interval, list) or len(interval) != 2:
        return "stage validation requires a two-value held_bootstrap_ci"
    if not all(_is_number(value) and -1 <= value <= 1 for value in interval):
        return "stage validation held_bootstrap_ci must contain finite values in [-1, 1]"
    lower, upper = cast(list[int | float], interval)
    if lower > upper:
        return "stage validation held_bootstrap_ci must be ordered"
    n_calib = payload.get("n_calib")
    n_held = payload.get("n_held")
    if not _is_positive_integer(n_calib) or not _is_positive_integer(n_held):
        return "stage validation requires positive integer n_calib and n_held"
    cells = payload.get("cells")
    if not isinstance(cells, list) or not cells:
        return "stage validation requires non-empty validation cells"
    split_counts = {"calib": 0, "held": 0}
    for index, cell in enumerate(cells):
        if not isinstance(cell, dict):
            return f"stage validation cell {index} must be an object"
        for field in ("model", "task", "split"):
            value = cell.get(field)
            if not isinstance(value, str) or not value.strip():
                return f"stage validation cell {index} requires {field}"
        split = str(cell["split"])
        if split not in split_counts:
            return f"stage validation cell {index} has unsupported split {split!r}"
        split_counts[split] += 1
        if not _is_number(cell.get("delta_tv_static_mean")):
            return f"stage validation cell {index} requires finite delta_tv_static_mean"
    if split_counts["calib"] != n_calib or split_counts["held"] != n_held:
        return "stage validation cell split counts do not match n_calib and n_held"
    return None


def _finite_numeric_list(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(_is_number(item) for item in value)


def _is_positive_integer(value: object) -> bool:
    return _is_nonnegative_integer(value) and cast(int, value) > 0


def _is_nonnegative_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _distinct_strings(rows: list[JsonDict], key: str) -> list[str]:
    return sorted({value for row in rows if isinstance((value := row.get(key)), str) and value})


def _trajectory_seed(payload: JsonDict, source: JsonDict) -> tuple[int | None, str | None]:
    value = payload.get("seed")
    if isinstance(value, int) and not isinstance(value, bool):
        return value, "json"
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value), "json"
    match = _SEED_PATTERN.search(Path(_relative_path(source)).name)
    if match is not None:
        return int(match.group(1)), "filename"
    return None, None


def _normalize_model_id(model: str) -> str:
    return model.strip().replace("__", "/").lower()


def _verify_trajectory_binaries(
    root: Path,
    binary_sources: list[JsonDict],
    warnings: list[JsonDict],
) -> _TrajectoryBinaryResults:
    """Validate trajectory binary metadata without executing source artifacts."""

    valid: dict[str, list[JsonDict]] = {}
    invalid: dict[str, list[JsonDict]] = {}
    all_valid: list[JsonDict] = []
    all_invalid: list[JsonDict] = []
    ordered_sources = sorted(
        binary_sources,
        key=lambda source: _relative_path(source),
    )
    for source in ordered_sources:
        owner = Path(_relative_path(source)).with_suffix(".json").as_posix()
        try:
            path = _source_path(root, source, label="trajectory binary")
            observed_size, observed_sha256 = _file_integrity(path)
            integrity_error = _source_integrity_error(
                source,
                observed_size,
                observed_sha256,
            )
        except (OSError, ValueError) as exc:
            integrity_error = f"{type(exc).__name__}: source could not be read or resolved"
        if integrity_error is None:
            reference = _source_reference(source)
            valid.setdefault(owner, []).append(reference)
            all_valid.append(reference)
            continue

        error = (
            "trajectory binary source changed after discovery: "
            f"{_relative_path(source)}: "
            f"{integrity_error}"
        )
        _append_optional_warning(
            warnings,
            source,
            error,
            code="source_integrity_mismatch",
        )
        unusable_reference: JsonDict = {
            "origin": "real",
            "status": "unusable",
            "display_status": _display_status("real", "unusable"),
            "source": _source_reference(source),
            "error": error,
        }
        invalid.setdefault(owner, []).append(unusable_reference)
        all_invalid.append(unusable_reference)
    return _TrajectoryBinaryResults(
        valid=valid,
        invalid=invalid,
        all_valid=all_valid,
        all_invalid=all_invalid,
    )


def _headline_trajectory_pair(pairs: list[JsonDict]) -> JsonDict | None:
    preferred = next(
        (
            pair
            for pair in pairs
            if pair.get("seed") == 0
            and "qwen2.5-7b-instruct" in str(pair.get("normalized_model", ""))
        ),
        None,
    )
    return preferred or (pairs[0] if pairs else None)


def _display_status(origin: str, status: str) -> str:
    if origin == "none":
        return status.upper().replace("_", " ")
    return f"{origin.upper()} / {status.upper().replace('_', ' ')}"


def _warning_sort_key(warning: JsonDict) -> tuple[str, str, str, str, str]:
    return (
        str(warning.get("code", "")),
        str(warning.get("source_role", "")),
        str(warning.get("relative_path", "")),
        str(warning.get("json_path", "")),
        str(warning.get("message", "")),
    )


def _trajectory_sources(
    root: Path,
    overrides: PeocSourceOverrides,
) -> tuple[list[Path], str]:
    if overrides.trajectory_files:
        paths = [
            _resolve_bundle_path(root, path, label="trajectory override")
            for path in overrides.trajectory_files
        ]
        for path in paths:
            _require_file(path, label="trajectory override")
            _trajectory_role(path)
        return paths, "override"

    trajectory_root = _resolve_bundle_path(root, TRAJECTORY_ROOT, label="trajectory root")
    if not trajectory_root.is_dir():
        return [], "default_glob"

    paths = [
        *trajectory_root.glob("stationary_arith_*.json"),
        *trajectory_root.glob("turnpike_gsm8k_*.json"),
    ]
    resolved_paths = [_resolve_bundle_path(root, path, label="trajectory source") for path in paths]
    resolved_paths.sort(key=lambda path: path.relative_to(root).as_posix())
    return resolved_paths, "default_glob"


def _trajectory_role(path: Path) -> str:
    if path.name.startswith("stationary_arith_"):
        return "trajectory_stationary"
    if path.name.startswith("turnpike_gsm8k_"):
        return "trajectory_heterogeneous"
    msg = f"Trajectory source filename must start with stationary_arith_ or turnpike_gsm8k_: {path}"
    raise ValueError(msg)


def _resolve_existing_sibling(root: Path, path: Path) -> Path | None:
    if not path.is_file():
        return None
    return _resolve_bundle_path(root, path, label="trajectory binary")


def _resolve_bundle_path(root: Path, path: Path, *, label: str) -> Path:
    candidate = path if path.is_absolute() else root / path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        msg = f"{label} must resolve inside PEOC bundle root {root}: {path}"
        raise ValueError(msg) from None
    return resolved


def _require_file(path: Path, *, label: str) -> None:
    if not path.is_file():
        msg = f"Missing required {label}: {path}"
        raise ValueError(msg)


def _source_row(
    root: Path,
    path: Path,
    *,
    role: str,
    media_type: str,
    selection: str,
) -> JsonDict:
    size, sha256 = _file_integrity(path)
    return {
        "role": role,
        "relative_path": path.relative_to(root).as_posix(),
        "resolved_path": str(path),
        "bytes": size,
        "sha256": sha256,
        "media_type": media_type,
        "selection": selection,
        "copied_path": None,
    }
