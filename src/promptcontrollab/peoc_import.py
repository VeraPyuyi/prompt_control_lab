"""Discover source files in a real PEOC evidence bundle."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TypeGuard, cast

from promptcontrollab.files import JsonDict

HARD_SUMMARY = Path(
    "experiments/redesign_v2/results_server_pull_20260524/"
    "strong_main_grid/summary_acc_hard_test.json"
)
SOFT_SUMMARY = Path(
    "experiments/redesign_v2/results_server_pull_20260524/"
    "strong_main_grid/summary_soft_segmented.json"
)
HETEROGENEITY_SUMMARY = Path("experiments/redesign_v2/stage_heterogeneity/shi_r27_summary.json")
TRAJECTORY_ROOT = Path("experiments/turnpike_trace/results_a800")

_MANIFEST = Path("README_MANIFEST.md")
_CHUNK_SIZE = 1024 * 1024
_SEED_PATTERN = re.compile(r"_s(-?\d+)\.json$")


@dataclass(frozen=True)
class PeocSourceOverrides:
    """Optional source selections within a PEOC bundle."""

    hard_summary: Path | None = None
    trajectory_files: tuple[Path, ...] = ()
    heterogeneity_summary: Path | None = None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(_CHUNK_SIZE):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def discover_peoc_sources(
    bundle_root: Path,
    overrides: PeocSourceOverrides,
) -> JsonDict:
    """Discover and hash the selected sources in a PEOC evidence bundle."""

    root = bundle_root.resolve()
    if not root.is_dir():
        msg = f"PEOC bundle root is not a directory: {root}"
        raise ValueError(msg)

    manifest_path = _resolve_bundle_path(root, _MANIFEST, label="bundle manifest")
    _require_file(manifest_path, label="bundle manifest README_MANIFEST.md")

    sources: list[JsonDict] = [
        _source_row(
            root,
            manifest_path,
            role="bundle_manifest",
            media_type="text/markdown",
            selection="required",
        )
    ]

    hard_selection = overrides.hard_summary or HARD_SUMMARY
    hard_path = _resolve_bundle_path(root, hard_selection, label="hard-test summary")
    _require_file(hard_path, label="hard-test summary")
    sources.append(
        _source_row(
            root,
            hard_path,
            role="hard_test_summary",
            media_type="application/json",
            selection="override" if overrides.hard_summary is not None else "default",
        )
    )

    soft_path = _resolve_bundle_path(root, SOFT_SUMMARY, label="soft segmented summary")
    if soft_path.is_file():
        sources.append(
            _source_row(
                root,
                soft_path,
                role="soft_segmented_summary",
                media_type="application/json",
                selection="default",
            )
        )

    heterogeneity_selection = overrides.heterogeneity_summary or HETEROGENEITY_SUMMARY
    heterogeneity_path = _resolve_bundle_path(
        root,
        heterogeneity_selection,
        label="stage heterogeneity summary",
    )
    if overrides.heterogeneity_summary is not None:
        _require_file(heterogeneity_path, label="stage heterogeneity summary")
    if heterogeneity_path.is_file():
        sources.append(
            _source_row(
                root,
                heterogeneity_path,
                role="stage_heterogeneity",
                media_type="application/json",
                selection=(
                    "override" if overrides.heterogeneity_summary is not None else "default"
                ),
            )
        )

    trajectory_paths, trajectory_selection = _trajectory_sources(root, overrides)
    for trajectory_path in trajectory_paths:
        sources.append(
            _source_row(
                root,
                trajectory_path,
                role=_trajectory_role(trajectory_path),
                media_type="application/json",
                selection=trajectory_selection,
            )
        )
    for trajectory_path in trajectory_paths:
        binary_path = _resolve_existing_sibling(root, trajectory_path.with_suffix(".npz"))
        if binary_path is not None:
            sources.append(
                _source_row(
                    root,
                    binary_path,
                    role="trajectory_binary",
                    media_type="application/octet-stream",
                    selection="sibling",
                )
            )

    return {
        "schema": "prompt_control_lab.peoc_source_manifest.v1",
        "bundle": {
            "resolved_path": str(root),
            "manifest_relative_path": _MANIFEST.as_posix(),
            "manifest_sha256": _sha256_file(manifest_path),
        },
        "sources": sources,
        "warnings": [],
    }


def build_peoc_evidence(bundle_root: Path, source_manifest: JsonDict) -> JsonDict:
    """Normalize discovered PEOC sources into fail-closed research evidence."""

    root = bundle_root.resolve()
    if not root.is_dir():
        msg = f"PEOC bundle root is not a directory: {root}"
        raise ValueError(msg)

    sources = _manifest_sources(source_manifest)
    warnings: list[JsonDict] = []
    finite_manifest = _finite_json(
        source_manifest,
        warnings,
        source_role="source_manifest",
        relative_path=None,
    )
    hard = _build_hard_section(root, sources, warnings)
    soft = _build_soft_section(root, sources, warnings)
    trajectory = _build_trajectory_section(root, sources, warnings)
    stage = _build_stage_section(root, sources, warnings)
    riccati = _missing_section(
        "No Riccati/DARE diagnostic source was discovered in this PEOC bundle."
    )
    soft_hard = _missing_section(
        "No soft-to-hard projection diagnostic source was discovered in this PEOC bundle."
    )
    sections: JsonDict = {
        "hard_evaluation": hard,
        "soft_evaluation": soft,
        "trajectory": trajectory,
        "stage_heterogeneity": stage,
        "riccati": riccati,
        "soft_hard": soft_hard,
    }
    blocking_sections = [
        {"section": name, "status": section["status"]}
        for name, section in sections.items()
        if isinstance(section, dict) and section.get("status") != "available"
    ]
    warnings.sort(key=_warning_sort_key)

    return {
        "schema": "prompt_control_lab.peoc_evidence.v1",
        "bundle": cast(JsonDict, finite_manifest).get("bundle", {}),
        "source_manifest": finite_manifest,
        "warnings": warnings,
        "sections": sections,
        "claim_boundary": {
            "full_research_support": not blocking_sections,
            "status": "supported" if not blocking_sections else "not_supported",
            "blocking_sections": blocking_sections,
            "statement": (
                "Evidence supports the complete research capability set."
                if not blocking_sections
                else "The imported bundle does not support the complete research capability set."
            ),
        },
    }


def _build_hard_section(
    root: Path,
    sources: list[JsonDict],
    warnings: list[JsonDict],
) -> JsonDict:
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
        reason = _summary_row_exclusion_reason(raw_row, normalized_row)
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
    limitations = [
        "Aggregate hard-test results do not establish universal prompt superiority."
    ]
    if excluded_rows:
        limitations.append("Rows without a finite mean and positive sample count were excluded.")
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
    source = _first_source(sources, "soft_segmented_summary")
    if source is None:
        return _missing_section(
            "No segmented soft-evaluation summary was discovered in this PEOC bundle."
        )
    raw, error = _read_optional_json(root, source)
    if error is not None or not isinstance(raw, dict) or not isinstance(raw.get("summary"), list):
        return _invalid_optional_section(
            source,
            warnings,
            error or "expected top-level summary list",
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
        reason = _summary_row_exclusion_reason(raw_row, normalized_row)
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
    trajectory_sources = [
        source
        for source in sources
        if source.get("role") in {"trajectory_stationary", "trajectory_heterogeneous"}
    ]
    binary_sources = [
        source for source in sources if source.get("role") == "trajectory_binary"
    ]
    if not trajectory_sources:
        return _missing_section("No trajectory summary was discovered in this PEOC bundle.")

    entries: list[JsonDict] = []
    grouped: dict[tuple[str, int], dict[str, JsonDict]] = {}
    for source in trajectory_sources:
        role = str(source.get("role"))
        raw, error = _read_optional_json(root, source)
        if error is not None or not isinstance(raw, dict):
            entries.append(
                _invalid_trajectory_entry(
                    source,
                    warnings,
                    error or "expected a JSON object",
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
            "binary_references": _trajectory_binary_references(source, binary_sources),
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
    status = "available" if headline_pair is not None else "unusable"
    limitations = [
        "Trajectory decay is a diagnostic signal, not proof of operational model stability.",
        "Sibling NPZ files are referenced and hashed only; they are not loaded or copied.",
    ]
    if headline_pair is None:
        limitations.append("No complete stationary/heterogeneous model-and-seed pair was usable.")
    return _section(
        origin="real",
        status=status,
        source_roles=sorted(
            {str(source.get("role")) for source in trajectory_sources}
        ),
        observations={
            "entries": entries,
            "pairs": pairs,
            "headline_pair": headline_pair,
            "binary_references": [_source_reference(source) for source in binary_sources],
        },
        limitations=limitations,
    )


def _build_stage_section(
    root: Path,
    sources: list[JsonDict],
    warnings: list[JsonDict],
) -> JsonDict:
    source = _first_source(sources, "stage_heterogeneity")
    if source is None:
        return _missing_section(
            "No stage-heterogeneity validation summary was discovered in this PEOC bundle."
        )
    raw, error = _read_optional_json(root, source)
    if error is not None or not isinstance(raw, dict):
        return _invalid_optional_section(
            source,
            warnings,
            error or "expected a JSON object",
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
) -> JsonDict:
    role = str(source.get("role", "optional_source"))
    _append_invalid_optional_warning(warnings, source, error)
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
) -> JsonDict:
    _append_invalid_optional_warning(warnings, source, error)
    return {
        "origin": "real",
        "status": "unusable",
        "display_status": _display_status("real", "unusable"),
        "role": source.get("role"),
        "source": _source_reference(source),
        "error": error,
        "binary_references": [],
    }


def _append_invalid_optional_warning(
    warnings: list[JsonDict],
    source: JsonDict,
    error: str,
) -> None:
    warnings.append(
        {
            "code": "invalid_optional_source",
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


def _read_required_json(root: Path, source: JsonDict, *, label: str) -> object:
    path = _source_path(root, source, label=label)
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        msg = f"Invalid required {label} {path}: {exc}"
        raise ValueError(msg) from exc


def _read_optional_json(root: Path, source: JsonDict) -> tuple[object | None, str | None]:
    role = str(source.get("role", "optional source"))
    try:
        path = _source_path(root, source, label=role)
        return json.loads(path.read_text(encoding="utf-8-sig")), None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, str(exc)


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


def _summary_row_exclusion_reason(raw_row: object, normalized_row: object) -> str | None:
    if not isinstance(raw_row, dict) or not isinstance(normalized_row, dict):
        return "row_not_object"
    raw_n = raw_row.get("n")
    n = normalized_row.get("n")
    if isinstance(raw_n, float) and not math.isfinite(raw_n):
        return "non_finite_n"
    if not _is_number(n):
        return "invalid_n"
    if float(n) <= 0:
        return "non_positive_n"
    raw_mean = raw_row.get("mean")
    mean = normalized_row.get("mean")
    if isinstance(raw_mean, float) and not math.isfinite(raw_mean):
        return "non_finite_mean"
    if not _is_number(mean):
        return "invalid_mean"
    return None


def _is_number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _distinct_strings(rows: list[JsonDict], key: str) -> list[str]:
    return sorted(
        {
            value
            for row in rows
            if isinstance((value := row.get(key)), str) and value
        }
    )


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


def _trajectory_binary_references(
    trajectory_source: JsonDict,
    binary_sources: list[JsonDict],
) -> list[JsonDict]:
    trajectory_path = Path(_relative_path(trajectory_source))
    references = [
        _source_reference(source)
        for source in binary_sources
        if Path(_relative_path(source)).with_suffix(".json") == trajectory_path
    ]
    references.sort(key=lambda row: str(row.get("relative_path", "")))
    return references


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
    return {
        "role": role,
        "relative_path": path.relative_to(root).as_posix(),
        "resolved_path": str(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
        "media_type": media_type,
        "selection": selection,
        "copied_path": None,
    }
