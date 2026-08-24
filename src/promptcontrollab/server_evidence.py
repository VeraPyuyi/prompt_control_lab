"""Read-only discovery and normalization for dispersed diagnostic evidence."""

from __future__ import annotations

import hashlib
import html
import json
import math
import shutil
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from promptcontrollab.evidence_profiles import (
    EvidenceProfile,
    get_evidence_profile,
)
from promptcontrollab.evidence_profiles import (
    evidence_profile_registry as _evidence_profile_registry,
)
from promptcontrollab.files import JsonDict, ensure_dir, read_json, stable_digest, write_json

MANIFEST_SCHEMA = "prompt_control_lab.server_evidence_manifest.v1"
MATRIX_SCHEMA = "prompt_control_lab.evidence_matrix.v1"
REPORT_SCHEMA = "prompt_control_lab.interpretability_report.v1"

ADAPTERS = (
    "agent_episode",
    "deployment_gate",
    "generation_aware",
    "riccati_ass_hyp",
    "selective_risk",
    "soft_hard_tv",
    "turnpike_a800",
)

_CHUNK_SIZE = 1024 * 1024


def evidence_profile_registry() -> dict[str, EvidenceProfile]:
    """Expose the profile registry beside the scanner public API."""

    return _evidence_profile_registry()


@dataclass(frozen=True)
class EvidenceImportOptions:
    """Options for importing a previously scanned evidence manifest."""

    manifest_path: Path
    out_dir: Path
    portable: bool = False
    overwrite: bool = False


def scan_evidence_root(*, root: Path, profile: str = "peoc-server") -> JsonDict:
    """Discover and hash known evidence files without loading model artifacts."""

    resolved_root = root.resolve()
    if not resolved_root.is_dir():
        msg = f"Evidence root is not a directory: {resolved_root}"
        raise ValueError(msg)
    profile_spec = get_evidence_profile(profile)

    if profile != "peoc-server":
        return _scan_adapter_profile(resolved_root, profile_spec.name)

    discovered: dict[str, tuple[str, str]] = {}
    for adapter, patterns in _profile_patterns().items():
        for pattern in patterns:
            for path in resolved_root.glob(pattern):
                if not path.is_file():
                    continue
                resolved = path.resolve()
                if not resolved.is_relative_to(resolved_root):
                    continue
                relative = resolved.relative_to(resolved_root).as_posix()
                discovered[relative] = (adapter, _source_role(adapter, resolved))

    sources: list[JsonDict] = []
    for relative_path in sorted(discovered):
        adapter, role = discovered[relative_path]
        path = resolved_root / relative_path
        size, digest = _file_integrity(path)
        sources.append(
            {
                "adapter": adapter,
                "role": role,
                "relative_path": relative_path,
                "resolved_path": str(path.resolve()),
                "bytes": size,
                "sha256": digest,
                "media_type": _media_type(path),
                "availability": "available",
                "load_policy": _load_policy(path),
            }
        )

    adapter_counts = Counter(str(row["adapter"]) for row in sources)
    manifest: JsonDict = {
        "schema": MANIFEST_SCHEMA,
        "profile": profile,
        "classification": "private_local",
        "root": {"resolved_path": str(resolved_root)},
        "sources": sources,
        "adapter_counts": {adapter: adapter_counts.get(adapter, 0) for adapter in ADAPTERS},
        "warnings": [
            f"No source discovered for adapter `{adapter}`."
            for adapter in ADAPTERS
            if adapter_counts.get(adapter, 0) == 0
        ],
    }
    manifest["snapshot_sha256"] = f"sha256:{stable_digest(_snapshot_identity(manifest))}"
    return manifest


def _scan_adapter_profile(root: Path, profile: str) -> JsonDict:
    profile_spec = get_evidence_profile(profile)
    discovered: dict[str, tuple[str, str]] = {}
    for adapter in profile_spec.adapters:
        for pattern in adapter.patterns:
            search_patterns = (
                (pattern,)
                if pattern.startswith("**/")
                else (pattern, f"**/{pattern}")
            )
            for search_pattern in search_patterns:
                for candidate in root.glob(search_pattern):
                    if not candidate.is_file():
                        continue
                    resolved = candidate.resolve()
                    if not resolved.is_relative_to(root):
                        continue
                    relative = resolved.relative_to(root).as_posix()
                    discovered[relative] = (
                        adapter.name,
                        adapter.source_role(resolved),
                    )
    sources: list[JsonDict] = []
    for relative in sorted(discovered):
        adapter_name, role = discovered[relative]
        path = root / relative
        size, digest, canonical_digest = _adapter_file_integrity(path)
        sources.append(
            {
                "adapter": adapter_name,
                "role": role,
                "relative_path": relative,
                "resolved_path": str(path.resolve()),
                "bytes": size,
                "sha256": digest,
                "canonical_sha256": canonical_digest,
                "media_type": _media_type(path),
                "availability": "available",
                "load_policy": _adapter_load_policy(path),
            }
        )
    counts = Counter(str(row["adapter"]) for row in sources)
    manifest: JsonDict = {
        "schema": profile_spec.manifest_schema,
        "profile": profile,
        "classification": "private_local",
        "root": {"resolved_path": str(root)},
        "sources": sources,
        "adapter_counts": {
            adapter: counts.get(adapter, 0) for adapter in profile_spec.adapter_names
        },
        "warnings": [
            f"No source discovered for adapter `{adapter}`."
            for adapter in profile_spec.adapter_names
            if counts.get(adapter, 0) == 0
        ],
    }
    manifest["snapshot_sha256"] = f"sha256:{stable_digest(_snapshot_identity(manifest))}"
    return manifest


def _adapter_file_integrity(path: Path) -> tuple[int, str, str]:
    if path.suffix.lower() not in {".json", ".jsonl"}:
        size, digest = _file_integrity(path)
        return size, digest, digest
    content = path.read_bytes()
    digest = "sha256:" + hashlib.sha256(content).hexdigest()
    return len(content), digest, _canonical_source_digest(path, content, digest)


def _canonical_source_digest(path: Path, content: bytes, fallback: str) -> str:
    try:
        if path.suffix.lower() == ".json":
            value = json.loads(content.decode("utf-8-sig"))
            return f"sha256:{stable_digest(value)}"
        if path.suffix.lower() == ".jsonl":
            values = [
                json.loads(line)
                for line in content.decode("utf-8-sig").splitlines()
                if line.strip()
            ]
            return f"sha256:{stable_digest(values)}"
    except (UnicodeError, json.JSONDecodeError):
        return fallback
    return fallback


def _adapter_load_policy(path: Path) -> str:
    if path.suffix.lower() in {".pt", ".pth", ".pkl", ".pickle"}:
        return "metadata_only_never_deserialize"
    if path.suffix.lower() == ".npz":
        return "hash_only_by_default"
    return "structured_read"


def import_evidence_manifest(options: EvidenceImportOptions) -> JsonDict:
    """Verify and normalize a scanner manifest into a self-contained run."""

    manifest = read_json(options.manifest_path)
    _validate_manifest(manifest)
    protected = [options.manifest_path]
    root_value = manifest.get("root")
    if isinstance(root_value, dict) and isinstance(root_value.get("resolved_path"), str):
        protected.append(Path(root_value["resolved_path"]))
    validate_evidence_destination(options.out_dir, protected_roots=protected)
    if manifest.get("profile") != "peoc-server":
        return _import_adapter_manifest(manifest, options)
    if options.out_dir.is_symlink():
        msg = f"Evidence output cannot be a symbolic link: {options.out_dir}"
        raise ValueError(msg)
    out_dir = options.out_dir.resolve()
    _prepare_output(out_dir, overwrite=options.overwrite)

    verified_sources = _verify_sources(manifest)
    findings = [
        cast(JsonDict, _normalize_non_finite(finding))
        for finding in _build_findings(verified_sources)
    ]
    diagnostics = [_matrix_row(adapter, verified_sources, findings) for adapter in ADAPTERS]
    counts = Counter(str(row["support_status"]) for row in diagnostics)
    matrix: JsonDict = {
        "schema": MATRIX_SCHEMA,
        "profile": manifest["profile"],
        "snapshot_sha256": manifest["snapshot_sha256"],
        "diagnostics": diagnostics,
        "status_counts": dict(sorted(counts.items())),
    }
    report: JsonDict = {
        "schema": REPORT_SCHEMA,
        "profile": manifest["profile"],
        "snapshot_sha256": manifest["snapshot_sha256"],
        "findings": findings,
        "interpretation_roles": sorted(
            {str(entry["interpretation_role"]) for entry in findings}
        ),
        "boundary": (
            "These findings are observable diagnostics and fitted-surrogate explanations. "
            "They do not prove universal improvement or hidden-model causal mechanisms."
        ),
    }
    claim_check = _claim_check(findings)
    public_manifest = _public_source_manifest(manifest)

    write_json(out_dir / "source_manifest.json", manifest)
    write_json(out_dir / "public_source_manifest.json", public_manifest)
    write_json(out_dir / "evidence_matrix.json", matrix)
    write_json(out_dir / "interpretability_report.json", report)
    write_json(out_dir / "claim_check.json", claim_check)
    (out_dir / "interpretability_report.html").write_text(
        render_interpretability_html(report, matrix), encoding="utf-8"
    )
    if options.portable:
        _write_portable_bundle(out_dir)
    run_manifest: JsonDict = {
        "schema": "prompt_control_lab.evidence_run.v1",
        "mode": "evidence_import",
        "profile": manifest["profile"],
        "source_snapshot_sha256": manifest["snapshot_sha256"],
        "artifacts": [
            "source_manifest.json",
            "public_source_manifest.json",
            "evidence_matrix.json",
            "interpretability_report.json",
            "interpretability_report.html",
            "claim_check.json",
        ],
    }
    write_json(out_dir / "manifest.json", run_manifest)
    return {
        "schema": "prompt_control_lab.evidence_import_result.v1",
        "output_dir": str(out_dir),
        "source_count": len(verified_sources),
        "finding_count": len(findings),
        "snapshot_sha256": manifest["snapshot_sha256"],
    }


def _import_adapter_manifest(manifest: JsonDict, options: EvidenceImportOptions) -> JsonDict:
    verified = _verify_sources(manifest)
    reconciliation: JsonDict = {
        "schema": "prompt_control_lab.source_reconciliation.v1",
        "profile": manifest["profile"],
        "status_counts": {"single_source": len(verified)},
        "sources": [
            {
                "adapter": row.get("adapter"),
                "relative_path": row.get("relative_path"),
                "status": "single_source",
            }
            for row in verified
        ],
    }
    return _write_adapter_run(
        manifest=manifest,
        verified_sources=verified,
        out_dir=options.out_dir,
        portable=options.portable,
        overwrite=options.overwrite,
        reconciliation=reconciliation,
    )


def merge_evidence_manifests(
    *,
    primary: Path,
    secondary: Path,
    out_dir: Path,
    portable: bool = False,
    overwrite: bool = False,
) -> JsonDict:
    """Reconcile two scanner manifests using canonical structured-data identity."""

    if primary.is_dir() or secondary.is_dir():
        if not primary.is_dir() or not secondary.is_dir():
            raise ValueError("Evidence merge inputs must both be manifests or both be run dirs")
        validate_evidence_destination(out_dir, protected_roots=(primary, secondary))
        return _merge_portable_runs(
            primary=primary,
            secondary=secondary,
            out_dir=out_dir,
            portable=portable,
            overwrite=overwrite,
        )
    primary_manifest = read_json(primary)
    secondary_manifest = read_json(secondary)
    _validate_manifest(primary_manifest)
    _validate_manifest(secondary_manifest)
    protected_roots: list[Path] = [primary, secondary]
    for manifest in (primary_manifest, secondary_manifest):
        root_value = manifest.get("root")
        if isinstance(root_value, dict) and isinstance(
            root_value.get("resolved_path"), str
        ):
            protected_roots.append(Path(root_value["resolved_path"]))
    validate_evidence_destination(out_dir, protected_roots=protected_roots)
    profile = str(primary_manifest["profile"])
    if secondary_manifest.get("profile") != profile:
        raise ValueError("Evidence merge requires matching profiles")
    if profile == "peoc-server":
        raise ValueError("Evidence merge currently requires an adapter-registry profile")
    primary_rows = _verify_sources(primary_manifest)
    secondary_rows = _verify_sources(secondary_manifest)
    primary_by_key = {_source_key(row): row for row in primary_rows}
    secondary_by_key = {_source_key(row): row for row in secondary_rows}
    merged: list[JsonDict] = []
    reconciliation_rows: list[JsonDict] = []
    status_counts: Counter[str] = Counter()
    for key in sorted(set(primary_by_key) | set(secondary_by_key)):
        first = primary_by_key.get(key)
        second = secondary_by_key.get(key)
        if first is None:
            assert second is not None
            status = "secondary_only"
            merged.append({**second, "reconciliation_status": status})
        elif second is None:
            status = "primary_only"
            merged.append({**first, "reconciliation_status": status})
        elif first.get("canonical_sha256") == second.get("canonical_sha256"):
            status = "canonical_equivalent"
            merged.append({**first, "reconciliation_status": status})
        else:
            status = "requires_reanalysis"
            merged.extend(
                [
                    {**first, "reconciliation_status": status},
                    {**second, "reconciliation_status": status},
                ]
            )
        status_counts[status] += 1
        reconciliation_rows.append(
            {
                "adapter": key[0],
                "relative_path": key[1],
                "status": status,
                "primary_canonical_sha256": (
                    first.get("canonical_sha256") if first is not None else None
                ),
                "secondary_canonical_sha256": (
                    second.get("canonical_sha256") if second is not None else None
                ),
            }
        )
    reconciliation: JsonDict = {
        "schema": "prompt_control_lab.source_reconciliation.v1",
        "profile": profile,
        "status_counts": dict(sorted(status_counts.items())),
        "sources": reconciliation_rows,
    }
    merged_manifest: JsonDict = {
        "schema": get_evidence_profile(profile).manifest_schema,
        "profile": profile,
        "classification": "private_local_reconciled",
        "root": {"resolved_path": "multiple_verified_roots"},
        "sources": [_source_manifest_row(row) for row in merged],
        "snapshot_sha256": f"sha256:{stable_digest(reconciliation_rows)}",
        "source_snapshots": [
            primary_manifest.get("snapshot_sha256"),
            secondary_manifest.get("snapshot_sha256"),
        ],
    }
    result = _write_adapter_run(
        manifest=merged_manifest,
        verified_sources=merged,
        out_dir=out_dir,
        portable=portable,
        overwrite=overwrite,
        reconciliation=reconciliation,
    )
    result["conflict_count"] = status_counts.get("requires_reanalysis", 0)
    return result


def _merge_portable_runs(
    *,
    primary: Path,
    secondary: Path,
    out_dir: Path,
    portable: bool,
    overwrite: bool,
) -> JsonDict:
    primary_artifacts = _load_verified_evidence_artifacts(primary)
    secondary_artifacts = _load_verified_evidence_artifacts(secondary)
    primary_manifest = primary_artifacts["public_source_manifest.json"]
    secondary_manifest = secondary_artifacts["public_source_manifest.json"]
    profile_name = str(primary_manifest.get("profile", ""))
    if not profile_name or secondary_manifest.get("profile") != profile_name:
        raise ValueError("Portable evidence merge requires matching profiles")
    profile = get_evidence_profile(profile_name)
    primary_sources = _public_sources(primary_manifest)
    secondary_sources = _public_sources(secondary_manifest)
    primary_by_key = {_public_source_key(row): row for row in primary_sources}
    secondary_by_key = {_public_source_key(row): row for row in secondary_sources}
    status_counts: Counter[str] = Counter()
    reconciliation_rows: list[JsonDict] = []
    conflict_adapters: set[str] = set()
    merged_sources: list[JsonDict] = []
    for key in sorted(set(primary_by_key) | set(secondary_by_key)):
        first = primary_by_key.get(key)
        second = secondary_by_key.get(key)
        if first is None:
            assert second is not None
            status = "secondary_only"
            selected = second
        elif second is None:
            status = "primary_only"
            selected = first
        elif first.get("canonical_sha256") == second.get("canonical_sha256"):
            status = "canonical_equivalent"
            selected = first
        else:
            status = "requires_reanalysis"
            selected = first
            conflict_adapters.add(key[0])
        status_counts[status] += 1
        merged_sources.append({**selected, "reconciliation_status": status})
        reconciliation_rows.append(
            {
                "adapter": key[0],
                "source_path_sha256": key[1],
                "status": status,
                "primary_canonical_sha256": (
                    first.get("canonical_sha256") if first is not None else None
                ),
                "secondary_canonical_sha256": (
                    second.get("canonical_sha256") if second is not None else None
                ),
            }
        )
    findings: list[JsonDict] = []
    for adapter in profile.adapter_names:
        first = primary_artifacts[f"{adapter}.json"]
        second = secondary_artifacts[f"{adapter}.json"]
        first_status = str(first.get("support_status", "unavailable"))
        second_status = str(second.get("support_status", "unavailable"))
        selected = first if first_status == "observed" else second
        quality_flags = sorted(
            {
                str(flag)
                for finding in (first, second)
                for flag in finding.get("quality_flags", [])
                if isinstance(flag, str)
            }
        )
        if "observed" in {first_status, second_status}:
            support_status = "observed"
            confidence = "medium"
        elif "requires_reanalysis" in {first_status, second_status}:
            support_status = "requires_reanalysis"
            confidence = "low"
        else:
            support_status = "unavailable"
            confidence = "unknown"
        if adapter in conflict_adapters:
            support_status = "requires_reanalysis"
            confidence = "low"
            if "source_conflict" not in quality_flags:
                quality_flags.append("source_conflict")
        has_source_overlap = any(
            row.get("adapter") == adapter
            and row.get("status") == "canonical_equivalent"
            for row in reconciliation_rows
        )
        first_metrics = _dict_value(first.get("metrics"))
        second_metrics = _dict_value(second.get("metrics"))
        if has_source_overlap:
            metrics = first_metrics if first_status == "observed" else second_metrics
            aggregation_method = "single_summary_with_overlapping_sources"
            metrics_scope = (
                "Primary and secondary summaries are preserved separately because their source "
                "sets overlap; the displayed summary is not a joint aggregate."
            )
        else:
            metrics = _pool_metric_summaries(first_metrics, second_metrics)
            aggregation_method = "count_weighted_non_overlapping_numeric_summary"
            metrics_scope = "Primary and secondary source sets are non-overlapping."
        finding: JsonDict = {
            **selected,
            "support_status": support_status,
            "confidence": confidence,
            "quality_flags": quality_flags,
            "metrics": metrics,
            "metric_sets": {"primary": first_metrics, "secondary": second_metrics},
            "aggregation_method": aggregation_method,
            "metrics_scope": metrics_scope,
            "source_comparison": {
                "primary_support_status": first.get("support_status"),
                "secondary_support_status": second.get("support_status"),
                "primary_metrics": first.get("metrics", {}),
                "secondary_metrics": second.get("metrics", {}),
            },
            "source_evidence": [
                row for row in merged_sources if row.get("adapter") == adapter
            ],
        }
        findings.append(finding)
    reconciliation: JsonDict = {
        "schema": "prompt_control_lab.source_reconciliation.v1",
        "profile": profile_name,
        "status_counts": dict(sorted(status_counts.items())),
        "sources": reconciliation_rows,
    }
    merged_manifest: JsonDict = {
        "schema": "prompt_control_lab.public_evidence_source_manifest.v1",
        "classification": "public_derived_reconciled",
        "profile": profile_name,
        "snapshot_sha256": f"sha256:{stable_digest(reconciliation_rows)}",
        "sources": merged_sources,
        "boundary": "Only path hashes and derived numeric summaries are retained.",
    }
    result = _write_derived_findings_run(
        manifest=merged_manifest,
        findings=findings,
        reconciliation=reconciliation,
        out_dir=out_dir,
        portable=portable,
        overwrite=overwrite,
    )
    result["conflict_count"] = status_counts.get("requires_reanalysis", 0)
    return result


def _write_derived_findings_run(
    *,
    manifest: JsonDict,
    findings: list[JsonDict],
    reconciliation: JsonDict,
    out_dir: Path,
    portable: bool,
    overwrite: bool,
) -> JsonDict:
    _prepare_adapter_output(out_dir, overwrite=overwrite)
    resolved_out = out_dir.resolve()
    profile = get_evidence_profile(str(manifest["profile"]))
    for finding in findings:
        write_json(resolved_out / f"{finding['adapter']}.json", finding)
    diagnostics = [
        {
            "adapter": finding["adapter"],
            "source_count": len(finding.get("source_evidence", [])),
            "support_status": finding["support_status"],
            "interpretation_role": finding["interpretation_role"],
            "confidence": finding["confidence"],
            "next_action": finding["next_action"],
        }
        for finding in findings
    ]
    matrix: JsonDict = {
        "schema": "prompt_control_lab.evidence_matrix.v2",
        "profile": manifest["profile"],
        "snapshot_sha256": manifest["snapshot_sha256"],
        "diagnostics": diagnostics,
        "status_counts": dict(
            sorted(Counter(str(row["support_status"]) for row in diagnostics).items())
        ),
    }
    report: JsonDict = {
        "schema": "prompt_control_lab.interpretability_report.v2",
        "profile": manifest["profile"],
        "snapshot_sha256": manifest["snapshot_sha256"],
        "findings": findings,
        "interpretation_roles": sorted(
            {str(entry["interpretation_role"]) for entry in findings}
        ),
        "boundary": (
            "The reconciled package compares independently verified derived evidence. It does "
            "not prove a unique causal mechanism."
        ),
    }
    gaps: JsonDict = {
        "schema": "prompt_control_lab.source_gap_report.v1",
        "profile": manifest["profile"],
        "gaps": [
            {
                "adapter": finding["adapter"],
                "support_status": finding["support_status"],
                "quality_flags": finding.get("quality_flags", []),
                "next_action": finding["next_action"],
            }
            for finding in findings
            if finding["support_status"] != "observed"
        ],
    }
    write_json(resolved_out / "source_manifest.json", manifest)
    write_json(resolved_out / "public_source_manifest.json", manifest)
    write_json(resolved_out / "source_reconciliation.json", reconciliation)
    write_json(resolved_out / "source_gap_report.json", gaps)
    write_json(resolved_out / "evidence_matrix.json", matrix)
    write_json(resolved_out / "interpretability_report.json", report)
    write_json(resolved_out / "claim_check.json", _claim_check(findings))
    (resolved_out / "interpretability_report.html").write_text(
        render_interpretability_html(report, matrix), encoding="utf-8"
    )
    artifact_names = [
        "source_manifest.json",
        "public_source_manifest.json",
        "source_reconciliation.json",
        "source_gap_report.json",
        "evidence_matrix.json",
        "interpretability_report.json",
        "interpretability_report.html",
        "claim_check.json",
        *(f"{adapter}.json" for adapter in profile.adapter_names),
    ]
    if portable:
        _write_adapter_portable_bundle(
            resolved_out,
            artifact_names,
            profile=str(manifest["profile"]),
            snapshot_sha256=str(manifest["snapshot_sha256"]),
        )
    artifact_sha256 = _artifact_sha256(resolved_out, artifact_names)
    write_json(
        resolved_out / "manifest.json",
        {
            "schema": "prompt_control_lab.evidence_run.v2",
            "mode": "evidence_merge",
            "profile": manifest["profile"],
            "source_snapshot_sha256": manifest["snapshot_sha256"],
            "artifacts": artifact_names,
            "artifact_sha256": artifact_sha256,
        },
    )
    return {
        "schema": "prompt_control_lab.evidence_import_result.v2",
        "output_dir": str(resolved_out),
        "source_count": len(manifest.get("sources", [])),
        "finding_count": len(findings),
        "snapshot_sha256": manifest["snapshot_sha256"],
    }


def _public_sources(manifest: JsonDict) -> list[JsonDict]:
    sources = manifest.get("sources")
    if not isinstance(sources, list):
        raise ValueError("Public evidence manifest sources must be a list")
    return [cast(JsonDict, row) for row in sources if isinstance(row, dict)]


def _public_source_key(row: JsonDict) -> tuple[str, str]:
    return (str(row.get("adapter", "")), str(row.get("source_path_sha256", "")))


def _dict_value(value: object) -> JsonDict:
    return cast(JsonDict, value) if isinstance(value, dict) else {}


def _pool_metric_summaries(primary: JsonDict, secondary: JsonDict) -> JsonDict:
    pooled: JsonDict = {}
    for name in sorted(set(primary) | set(secondary)):
        first = _dict_value(primary.get(name))
        second = _dict_value(secondary.get(name))
        summaries = [summary for summary in (first, second) if summary]
        if len(summaries) == 1:
            pooled[name] = summaries[0]
            continue
        counts = [summary.get("count") for summary in summaries]
        means = [summary.get("mean") for summary in summaries]
        minima = [summary.get("min") for summary in summaries]
        maxima = [summary.get("max") for summary in summaries]
        if not (
            all(
                isinstance(value, int) and not isinstance(value, bool) and value >= 0
                for value in counts
            )
            and all(_finite_number(value) for value in means)
            and all(_finite_number(value) for value in minima)
            and all(_finite_number(value) for value in maxima)
        ):
            pooled[name] = {"primary": first, "secondary": second}
            continue
        valid_counts = cast(list[int], counts)
        valid_means = cast(list[int | float], means)
        valid_minima = cast(list[int | float], minima)
        valid_maxima = cast(list[int | float], maxima)
        total = sum(valid_counts)
        if total == 0:
            pooled[name] = {"count": 0, "mean": None, "min": None, "max": None}
            continue
        weighted = sum(
            count * float(mean_value)
            for count, mean_value in zip(valid_counts, valid_means, strict=True)
        )
        pooled[name] = {
            "count": total,
            "mean": weighted / total,
            "min": min(float(value) for value in valid_minima),
            "max": max(float(value) for value in valid_maxima),
        }
    return pooled


def _artifact_sha256(root: Path, names: Iterable[str]) -> JsonDict:
    return {
        name: _file_integrity(root / name)[1]
        for name in sorted(names)
    }


def _write_adapter_portable_bundle(
    source: Path,
    artifact_names: list[str],
    *,
    profile: str,
    snapshot_sha256: str,
) -> None:
    portable_dir = source / "portable"
    ensure_dir(portable_dir)
    public_names = [name for name in artifact_names if name != "source_manifest.json"]
    for name in public_names:
        shutil.copyfile(source / name, portable_dir / name)
    write_json(
        portable_dir / "portable_manifest.json",
        {
            "schema": "prompt_control_lab.portable_evidence_bundle.v1",
            "profile": profile,
            "source_snapshot_sha256": snapshot_sha256,
            "artifacts": public_names,
            "artifact_sha256": _artifact_sha256(portable_dir, public_names),
        },
    )


def _load_verified_evidence_artifacts(root: Path) -> dict[str, JsonDict]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"Portable evidence input must be a real directory: {root}")
    sentinel = (
        root / "portable_manifest.json"
        if (root / "portable_manifest.json").is_file()
        else root / "manifest.json"
    )
    if sentinel.is_symlink() or not sentinel.is_file():
        raise ValueError(f"Evidence artifact digest manifest is missing: {root}")
    metadata = read_json(sentinel)
    if metadata.get("schema") not in {
        "prompt_control_lab.portable_evidence_bundle.v1",
        "prompt_control_lab.evidence_run.v2",
    }:
        raise ValueError(f"Unsupported evidence artifact digest manifest: {sentinel}")
    profile_name = metadata.get("profile")
    if not isinstance(profile_name, str) or not profile_name:
        raise ValueError("Evidence artifact digest manifest is missing profile")
    profile = get_evidence_profile(profile_name)
    digests = metadata.get("artifact_sha256")
    if not isinstance(digests, dict):
        raise ValueError("Evidence artifact digest manifest is missing artifact_sha256")
    required = {
        "public_source_manifest.json",
        *(f"{adapter}.json" for adapter in profile.adapter_names),
    }
    if not required <= set(digests):
        missing = ", ".join(sorted(required - set(digests)))
        raise ValueError(f"Evidence artifact digest manifest is incomplete: {missing}")
    parsed: dict[str, JsonDict] = {}
    for raw_name, expected in sorted(digests.items()):
        if not isinstance(raw_name, str) or Path(raw_name).name != raw_name:
            raise ValueError("Evidence artifact digest manifest contains an unsafe path")
        if not isinstance(expected, str) or not expected.startswith("sha256:"):
            raise ValueError(f"Evidence artifact digest is invalid: {raw_name}")
        path = root / raw_name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Evidence artifact is missing or unsafe: {path}")
        content = path.read_bytes()
        observed = "sha256:" + hashlib.sha256(content).hexdigest()
        if observed != expected:
            raise ValueError(f"Evidence artifact digest mismatch: {raw_name}")
        if path.suffix.lower() == ".json":
            value = json.loads(content.decode("utf-8-sig"))
            if not isinstance(value, dict):
                raise ValueError(f"Evidence artifact must contain a JSON object: {raw_name}")
            parsed[raw_name] = cast(JsonDict, value)
    source_manifest = parsed["public_source_manifest.json"]
    if source_manifest.get("profile") != profile_name:
        raise ValueError("Evidence artifact profile does not match its source manifest")
    if source_manifest.get("snapshot_sha256") != metadata.get("source_snapshot_sha256"):
        raise ValueError("Evidence artifact snapshot does not match its source manifest")
    return parsed


def _write_adapter_run(
    *,
    manifest: JsonDict,
    verified_sources: list[JsonDict],
    out_dir: Path,
    portable: bool,
    overwrite: bool,
    reconciliation: JsonDict,
) -> JsonDict:
    _prepare_adapter_output(out_dir, overwrite=overwrite)
    resolved_out = out_dir.resolve()
    profile = get_evidence_profile(str(manifest["profile"]))
    findings = []
    for adapter in profile.adapters:
        rows = [row for row in verified_sources if row.get("adapter") == adapter.name]
        finding = cast(JsonDict, _normalize_non_finite(adapter.build(rows)))
        findings.append(finding)
        write_json(resolved_out / f"{adapter.name}.json", finding)
    diagnostics = [
        {
            "adapter": finding["adapter"],
            "source_count": len(
                [
                    row
                    for row in verified_sources
                    if row.get("adapter") == finding["adapter"]
                ]
            ),
            "support_status": finding["support_status"],
            "interpretation_role": finding["interpretation_role"],
            "confidence": finding["confidence"],
            "next_action": finding["next_action"],
        }
        for finding in findings
    ]
    counts = Counter(str(row["support_status"]) for row in diagnostics)
    matrix: JsonDict = {
        "schema": "prompt_control_lab.evidence_matrix.v2",
        "profile": manifest["profile"],
        "snapshot_sha256": manifest["snapshot_sha256"],
        "diagnostics": diagnostics,
        "status_counts": dict(sorted(counts.items())),
    }
    report: JsonDict = {
        "schema": "prompt_control_lab.interpretability_report.v2",
        "profile": manifest["profile"],
        "snapshot_sha256": manifest["snapshot_sha256"],
        "findings": findings,
        "interpretation_roles": sorted(
            {str(entry["interpretation_role"]) for entry in findings}
        ),
        "boundary": (
            "These observations support bounded mechanism, stability, and deployment "
            "interpretation. They do not prove a unique causal mechanism."
        ),
    }
    gaps: JsonDict = {
        "schema": "prompt_control_lab.source_gap_report.v1",
        "profile": manifest["profile"],
        "gaps": [
            {
                "adapter": finding["adapter"],
                "support_status": finding["support_status"],
                "quality_flags": finding.get("quality_flags", []),
                "next_action": finding["next_action"],
            }
            for finding in findings
            if finding["support_status"] != "observed"
        ],
    }
    write_json(resolved_out / "source_manifest.json", manifest)
    write_json(resolved_out / "public_source_manifest.json", _public_source_manifest(manifest))
    write_json(resolved_out / "source_reconciliation.json", reconciliation)
    write_json(resolved_out / "source_gap_report.json", gaps)
    write_json(resolved_out / "evidence_matrix.json", matrix)
    write_json(resolved_out / "interpretability_report.json", report)
    write_json(resolved_out / "claim_check.json", _claim_check(findings))
    (resolved_out / "interpretability_report.html").write_text(
        render_interpretability_html(report, matrix), encoding="utf-8"
    )
    artifact_names = [
        "source_manifest.json",
        "public_source_manifest.json",
        "source_reconciliation.json",
        "source_gap_report.json",
        "evidence_matrix.json",
        "interpretability_report.json",
        "interpretability_report.html",
        "claim_check.json",
        *(f"{adapter}.json" for adapter in profile.adapter_names),
    ]
    if portable:
        _write_adapter_portable_bundle(
            resolved_out,
            artifact_names,
            profile=str(manifest["profile"]),
            snapshot_sha256=str(manifest["snapshot_sha256"]),
        )
    artifact_sha256 = _artifact_sha256(resolved_out, artifact_names)
    write_json(
        resolved_out / "manifest.json",
        {
            "schema": "prompt_control_lab.evidence_run.v2",
            "mode": "evidence_import",
            "profile": manifest["profile"],
            "source_snapshot_sha256": manifest["snapshot_sha256"],
            "artifacts": artifact_names,
            "artifact_sha256": artifact_sha256,
        },
    )
    return {
        "schema": "prompt_control_lab.evidence_import_result.v2",
        "output_dir": str(resolved_out),
        "source_count": len(verified_sources),
        "finding_count": len(findings),
        "snapshot_sha256": manifest["snapshot_sha256"],
    }


def _source_key(row: JsonDict) -> tuple[str, str]:
    return (str(row.get("adapter", "")), str(row.get("relative_path", "")))


def _source_manifest_row(row: JsonDict) -> JsonDict:
    return {
        key: value
        for key, value in row.items()
        if key != "verified_path" and not key.startswith("_verified_")
    }


def validate_evidence_destination(
    output: Path,
    *,
    protected_roots: Iterable[Path] = (),
) -> Path:
    """Reject evidence writes that overlap source inputs or protected project roots."""

    expanded = output.expanduser()
    if expanded.is_symlink():
        raise ValueError(f"Evidence output cannot be a symbolic link: {expanded}")
    resolved = expanded.resolve()
    if resolved.parent == resolved:
        raise ValueError(f"Evidence output cannot be a filesystem root: {resolved}")
    if resolved == Path.cwd().resolve():
        raise ValueError("Evidence output cannot replace the current working directory")
    if resolved.is_dir() and (resolved / ".git").exists():
        raise ValueError(f"Evidence output cannot replace a Git repository root: {resolved}")
    for raw in protected_roots:
        protected = raw.expanduser().resolve()
        if protected.is_file():
            if protected == resolved or protected.is_relative_to(resolved):
                raise ValueError(
                    f"Evidence output overlaps an input artifact: {protected}"
                )
            continue
        if resolved.is_relative_to(protected) or protected.is_relative_to(resolved):
            raise ValueError(f"Evidence output overlaps a protected source root: {protected}")
    return resolved


def _prepare_adapter_output(out_dir: Path, *, overwrite: bool) -> None:
    resolved = validate_evidence_destination(out_dir)
    if resolved.exists() and not resolved.is_dir():
        raise ValueError(f"Evidence output must be a directory: {resolved}")
    if not resolved.exists() or not any(resolved.iterdir()):
        ensure_dir(resolved)
        return
    if not overwrite:
        raise ValueError(f"Evidence output already exists: {resolved}")

    manifest_path = resolved / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError(
            f"Refusing to overwrite a directory that is not a PromptControlLab evidence run: "
            f"{resolved}"
        )
    try:
        manifest = read_json(manifest_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(
            f"Refusing to overwrite a directory with an invalid evidence sentinel: {resolved}"
        ) from exc
    if manifest.get("schema") not in {
        "prompt_control_lab.evidence_run.v1",
        "prompt_control_lab.evidence_run.v2",
    }:
        raise ValueError(
            f"Refusing to overwrite a directory that is not a PromptControlLab evidence run: "
            f"{resolved}"
        )
    artifact_names = manifest.get("artifacts", [])
    if not isinstance(artifact_names, list) or not all(
        isinstance(name, str) and Path(name).name == name for name in artifact_names
    ):
        raise ValueError("Evidence run sentinel contains unsafe artifact paths")
    known = {
        "manifest.json",
        "source_manifest.json",
        "public_source_manifest.json",
        "source_reconciliation.json",
        "source_gap_report.json",
        "evidence_matrix.json",
        "interpretability_report.json",
        "interpretability_report.html",
        "claim_check.json",
        "portable",
        *artifact_names,
    }
    unknown = sorted(path.name for path in resolved.iterdir() if path.name not in known)
    if unknown:
        raise ValueError(
            "Refusing to overwrite evidence output with unowned files: "
            + ", ".join(unknown)
        )
    for path in list(resolved.iterdir()):
        if path.name == "portable":
            if path.is_symlink() or not path.is_dir():
                raise ValueError(f"Portable evidence destination is unsafe: {path}")
            shutil.rmtree(path)
        elif path.is_dir():
            raise ValueError(f"Unexpected directory in evidence output: {path}")
        else:
            path.unlink()
    ensure_dir(resolved)


def render_interpretability_html(report: JsonDict, matrix: JsonDict) -> str:
    """Render a dependency-free explanation-first evidence report."""

    cards = []
    for raw in report.get("findings", []):
        if not isinstance(raw, dict):
            continue
        entry = cast(JsonDict, raw)
        cards.append(
            "<section class='card'>"
            f"<div class='meta'>{_escape(entry.get('interpretation_role'))} / "
            f"{_escape(entry.get('confidence'))}</div>"
            f"<h2>{_escape(entry.get('adapter'))}</h2>"
            f"<h3>Observed</h3><p>{_escape(entry.get('observation'))}</p>"
            f"<h3>What it explains</h3><p>{_escape(entry.get('explanation'))}</p>"
            f"<h3>Boundary</h3><p>{_escape(entry.get('claim_boundary'))}</p>"
            f"<h3>Next</h3><p>{_escape(entry.get('next_action'))}</p>"
            "</section>"
        )
    count_text = ", ".join(
        f"{_escape(key)}={_escape(value)}"
        for key, value in cast(JsonDict, matrix.get("status_counts", {})).items()
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Interpretability evidence</title><style>
body{{font-family:Arial,sans-serif;margin:0;background:#f5f7fa;color:#16202a}}
main{{max-width:1120px;margin:auto;padding:32px}}
.summary{{padding:18px;background:#102a43;color:white}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px;margin-top:20px}}
.card{{background:white;border:1px solid #d9e2ec;border-radius:8px;padding:18px;
overflow-wrap:anywhere}}
.meta{{color:#287271;font-weight:700}} h2{{font-size:20px}} h3{{font-size:14px;margin-bottom:4px}}
p{{line-height:1.5;margin-top:0}}
</style></head><body><main><div class="summary"><h1>Interpretability evidence</h1>
<p>{_escape(report.get('boundary'))}</p><p>{count_text}</p></div><div class="grid">
{''.join(cards)}</div></main></body></html>"""


def _profile_patterns() -> dict[str, tuple[str, ...]]:
    prefixes = ("", "prompt_eng/")

    def variants(suffix: str) -> tuple[str, ...]:
        return tuple(f"{prefix}{suffix}" for prefix in prefixes)

    return {
        "turnpike_a800": variants("experiments/turnpike_trace/results_a800/*.json")
        + variants("experiments/turnpike_trace/results_a800/*.npz"),
        "riccati_ass_hyp": variants("theory/results/ass_hyp_verify_stationary_*.json"),
        "soft_hard_tv": variants("experiments/redo_a_fair_deployment/REDO_A_REPORT.json")
        + variants("experiments/redo_a_fair_deployment/QAT_EXT_REPORT_FINAL.json")
        + variants("experiments/redo_a_fair_deployment/**/*.pt"),
        "deployment_gate": variants(
            "experiments/p0_control_to_deployment/production_v2/audit/*.json"
        ),
        "generation_aware": variants("experiments/generation_aware_control/**/*.json"),
        "selective_risk": variants(
            "experiments/p4_selective_risk_seed_holdout/p4_selective_risk_report.json"
        ),
        "agent_episode": (
            "verifiable-dynamics-workspace/schemas/repair_episode.schema.json",
            "../verifiable-dynamics-workspace/schemas/repair_episode.schema.json",
        ),
    }


def _source_role(adapter: str, path: Path) -> str:
    name = path.name.lower()
    if path.suffix.lower() in {".pt", ".npz"}:
        return "binary_support"
    if adapter == "turnpike_a800":
        return "trajectory_heterogeneous" if "gsm8k" in name else "trajectory_stationary"
    if adapter == "soft_hard_tv":
        return "qat_summary" if "qat" in name else "deployment_comparison"
    if adapter == "deployment_gate" and "confirmatory" in name:
        return "confirmatory_analysis"
    if adapter == "deployment_gate":
        return "protocol_audit"
    if adapter == "generation_aware":
        return "generation_mismatch_record"
    if adapter == "agent_episode":
        return "episode_schema"
    return "diagnostic_summary"


def _file_integrity(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(_CHUNK_SIZE):
            size += len(chunk)
            digest.update(chunk)
    return size, f"sha256:{digest.hexdigest()}"


def _media_type(path: Path) -> str:
    return {
        ".json": "application/json",
        ".jsonl": "application/x-jsonlines",
        ".csv": "text/csv",
        ".npz": "application/x-npz",
        ".pt": "application/x-pytorch",
    }.get(path.suffix.lower(), "application/octet-stream")


def _load_policy(path: Path) -> str:
    if path.suffix.lower() == ".pt":
        return "metadata_only_weights_only_required"
    if path.suffix.lower() == ".npz":
        return "hash_only_by_default"
    return "structured_read"


def _snapshot_identity(manifest: JsonDict) -> JsonDict:
    raw_sources = manifest.get("sources")
    sources: list[JsonDict] = []
    if isinstance(raw_sources, list):
        for raw in raw_sources:
            if not isinstance(raw, dict):
                continue
            row = cast(JsonDict, raw)
            identity = {
                key: row.get(key)
                for key in (
                    "adapter",
                    "role",
                    "relative_path",
                    "bytes",
                    "sha256",
                    "media_type",
                    "load_policy",
                )
            }
            if "canonical_sha256" in row:
                identity["canonical_sha256"] = row.get("canonical_sha256")
            sources.append(identity)
    return {
        "schema": manifest["schema"],
        "profile": manifest["profile"],
        "sources": sorted(sources, key=lambda row: str(row.get("relative_path", ""))),
    }


def _validate_manifest(manifest: JsonDict) -> None:
    profile_name = manifest.get("profile")
    if not isinstance(profile_name, str):
        raise ValueError("Evidence manifest is missing profile")
    profile = get_evidence_profile(profile_name)
    if manifest.get("schema") != profile.manifest_schema:
        msg = f"Expected `{profile.manifest_schema}` evidence manifest"
        raise ValueError(msg)
    if not isinstance(manifest.get("sources"), list):
        msg = "Evidence manifest `sources` must be a list"
        raise ValueError(msg)
    snapshot = manifest.get("snapshot_sha256")
    expected = f"sha256:{stable_digest(_snapshot_identity(manifest))}"
    if snapshot != expected:
        msg = "Evidence manifest snapshot_sha256 does not match its source identity"
        raise ValueError(msg)


def _public_source_manifest(manifest: JsonDict) -> JsonDict:
    public_sources: list[JsonDict] = []
    for raw in cast(list[object], manifest.get("sources", [])):
        if not isinstance(raw, dict):
            continue
        row = cast(JsonDict, raw)
        relative = str(row.get("relative_path", ""))
        public_sources.append(
            {
                "adapter": row.get("adapter"),
                "role": row.get("role"),
                "source_path_sha256": (
                    f"sha256:{hashlib.sha256(relative.encode('utf-8')).hexdigest()}"
                ),
                "bytes": row.get("bytes"),
                "sha256": row.get("sha256"),
                "canonical_sha256": row.get("canonical_sha256"),
                "media_type": row.get("media_type"),
                "load_policy": row.get("load_policy"),
            }
        )
    return {
        "schema": "prompt_control_lab.public_evidence_source_manifest.v1",
        "classification": "public_derived",
        "profile": manifest.get("profile"),
        "snapshot_sha256": manifest.get("snapshot_sha256"),
        "sources": public_sources,
        "boundary": "Source paths and raw source content are intentionally excluded.",
    }


def _verify_sources(manifest: JsonDict) -> list[JsonDict]:
    root_value = manifest.get("root")
    if not isinstance(root_value, dict) or not isinstance(root_value.get("resolved_path"), str):
        msg = "Evidence manifest root is missing `resolved_path`"
        raise ValueError(msg)
    root = Path(root_value["resolved_path"]).resolve()
    verified: list[JsonDict] = []
    for raw in manifest["sources"]:
        if not isinstance(raw, dict):
            msg = "Evidence manifest source rows must be objects"
            raise ValueError(msg)
        row = cast(JsonDict, raw)
        relative = row.get("relative_path")
        if not isinstance(relative, str):
            msg = "Evidence source is missing relative_path"
            raise ValueError(msg)
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            msg = f"Evidence source escapes the declared root: {relative}"
            raise ValueError(msg)
        if not path.is_file():
            msg = f"Evidence source is missing: {path}"
            raise ValueError(msg)
        content: bytes | None = None
        if path.suffix.lower() in {".json", ".jsonl"}:
            content = path.read_bytes()
            size = len(content)
            digest = "sha256:" + hashlib.sha256(content).hexdigest()
        else:
            size, digest = _file_integrity(path)
        if size != row.get("bytes") or digest != row.get("sha256"):
            msg = f"Evidence source changed after scan: {relative}"
            raise ValueError(msg)
        if "canonical_sha256" in row:
            canonical = (
                _canonical_source_digest(path, content, digest)
                if content is not None
                else digest
            )
            if canonical != row.get("canonical_sha256"):
                msg = f"Evidence canonical digest changed after scan: {relative}"
                raise ValueError(msg)
        verified.append(
            {
                **row,
                "verified_path": str(path),
                "_verified_content": content,
            }
        )
    return verified


def _build_findings(sources: list[JsonDict]) -> list[JsonDict]:
    grouped = {
        adapter: [row for row in sources if row["adapter"] == adapter]
        for adapter in ADAPTERS
    }
    builders: dict[str, Callable[[list[JsonDict]], JsonDict]] = {
        "turnpike_a800": _turnpike_finding,
        "riccati_ass_hyp": _riccati_finding,
        "soft_hard_tv": _soft_hard_finding,
        "deployment_gate": _deployment_finding,
        "generation_aware": _generation_finding,
        "selective_risk": _selective_risk_finding,
        "agent_episode": _agent_episode_finding,
    }
    return [builders[adapter](grouped[adapter]) for adapter in ADAPTERS]


def _base_finding(
    *,
    adapter: str,
    role: str,
    status: str,
    observation: str,
    explanation: str,
    confidence: str,
    scope: str,
    boundary: str,
    next_action: str,
    source_rows: list[JsonDict],
    raw_status: object = None,
    metrics: JsonDict | None = None,
    raw_statistics: list[JsonDict] | None = None,
) -> JsonDict:
    return {
        "id": adapter,
        "adapter": adapter,
        "support_status": status,
        "interpretation_role": role,
        "observation": observation,
        "explanation": explanation,
        "confidence": confidence,
        "scope": scope,
        "claim_boundary": boundary,
        "next_action": next_action,
        "source_evidence": [_source_evidence_ref(row) for row in source_rows],
        "raw_status": raw_status,
        "metrics": metrics or {},
        "raw_statistics": raw_statistics or _collect_raw_statistics(source_rows),
    }


def _missing_finding(adapter: str, role: str) -> JsonDict:
    return _base_finding(
        adapter=adapter,
        role=role,
        status="unavailable",
        observation="No matching source was discovered in this snapshot.",
        explanation="The diagnostic cannot be interpreted from the current evidence root.",
        confidence="unknown",
        scope="Current scanned evidence snapshot only.",
        boundary="Absence in the snapshot is not evidence that the mechanism is absent.",
        next_action=f"Provide a valid source for the `{adapter}` adapter and rescan.",
        source_rows=[],
    )


def _json_payloads(rows: Iterable[JsonDict]) -> list[tuple[JsonDict, JsonDict]]:
    payloads: list[tuple[JsonDict, JsonDict]] = []
    for row in rows:
        if Path(str(row["relative_path"])).suffix.lower() != ".json":
            continue
        content = row.get("_verified_content")
        if not isinstance(content, bytes):
            continue
        value = json.loads(content.decode("utf-8-sig"))
        if isinstance(value, dict):
            payloads.append((row, cast(JsonDict, value)))
    return payloads


def _validated_payloads(
    adapter: str,
    rows: Iterable[JsonDict],
) -> tuple[list[tuple[JsonDict, JsonDict]], int]:
    payloads = _json_payloads(rows)
    valid = [item for item in payloads if _valid_adapter_payload(adapter, *item)]
    return valid, len(payloads) - len(valid)


def _valid_adapter_payload(adapter: str, row: JsonDict, payload: JsonDict) -> bool:
    if adapter == "turnpike_a800":
        alpha = payload.get("alpha_emp_mean")
        r_squared = payload.get("R2_mean")
        count_values = [payload[key] for key in ("n_streams", "n_prompts") if key in payload]
        return (
            _bounded_number(alpha, minimum=0.0)
            and _bounded_number(r_squared, maximum=1.0)
            and all(_positive_integer(value) for value in count_values)
        )
    if adapter == "riccati_ass_hyp":
        return _valid_dare_records(payload.get("ASS_HYP_via_DARE"))
    if adapter == "soft_hard_tv":
        has_rows = any(
            isinstance(payload.get(key), int)
            and not isinstance(payload.get(key), bool)
            and int(cast(int, payload[key])) > 0
            for key in ("n_seed_rows", "n_rows", "n_cells")
        )
        return has_rows and bool(_statistics_in_value(payload))
    if adapter == "deployment_gate":
        if row.get("role") != "confirmatory_analysis":
            return isinstance(payload.get("status"), str)
        return (
            isinstance(payload.get("interpretation"), str)
            and bool(str(payload["interpretation"]).strip())
            and isinstance(payload.get("n_rows"), int)
            and not isinstance(payload.get("n_rows"), bool)
            and int(cast(int, payload["n_rows"])) > 0
            and isinstance(payload.get("all_validity_gates_passed"), bool)
        )
    if adapter == "generation_aware":
        return isinstance(payload.get("status"), str) and bool(str(payload["status"]).strip())
    if adapter == "selective_risk":
        return (
            isinstance(payload.get("status"), str)
            and isinstance(payload.get("n_seed_rows"), int)
            and not isinstance(payload.get("n_seed_rows"), bool)
            and int(cast(int, payload["n_seed_rows"])) > 0
            and _bounded_number(payload.get("observed_aurc"), minimum=0.0, maximum=1.0)
            and _bounded_number(payload.get("random_mean_aurc"), minimum=0.0, maximum=1.0)
            and (
                "accuracy_at_20pct" not in payload
                or _bounded_number(
                    payload.get("accuracy_at_20pct"), minimum=0.0, maximum=1.0
                )
            )
        )
    if adapter == "agent_episode":
        return (
            isinstance(payload.get("$schema"), str)
            and bool(str(payload["$schema"]).strip())
            and isinstance(payload.get("title"), str)
            and bool(str(payload["title"]).strip())
        )
    return False


def _statistics_in_value(value: object) -> list[object]:
    found: list[object] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if _statistic_field(str(key).lower(), item):
                found.append(item)
            found.extend(_statistics_in_value(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_statistics_in_value(item))
    return found


def _source_evidence_ref(row: JsonDict) -> JsonDict:
    relative = str(row.get("relative_path", ""))
    return {
        "role": row.get("role"),
        "source_sha256": row.get("sha256"),
        "source_path_sha256": f"sha256:{hashlib.sha256(relative.encode('utf-8')).hexdigest()}",
    }


def _collect_raw_statistics(rows: Iterable[JsonDict]) -> list[JsonDict]:
    records: list[JsonDict] = []
    for row, payload in _json_payloads(rows):
        _walk_statistics(
            payload,
            pointer="",
            source_sha256=str(row.get("sha256", "")),
            records=records,
        )
    return records


def _walk_statistics(
    value: object,
    *,
    pointer: str,
    source_sha256: str,
    records: list[JsonDict],
) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            escaped_key = str(key).replace("~", "~0").replace("/", "~1")
            child_pointer = f"{pointer}/{escaped_key}"
            normalized = str(key).lower()
            if _statistic_field(normalized, item):
                records.append(
                    {
                        "field": str(key),
                        "json_pointer": child_pointer,
                        "source_sha256": source_sha256,
                        "value": _normalize_non_finite(item),
                    }
                )
            _walk_statistics(
                item,
                pointer=child_pointer,
                source_sha256=source_sha256,
                records=records,
            )
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _walk_statistics(
                item,
                pointer=f"{pointer}/{index}",
                source_sha256=source_sha256,
                records=records,
            )


def _statistic_field(name: str, value: object) -> bool:
    if name in {"p", "p_value", "pvalue", "mean_diff", "effect", "effect_size"}:
        return _finite_number(value)
    if "ci" in name or "interval" in name:
        return (
            isinstance(value, list)
            and len(value) == 2
            and all(_finite_number(item) for item in value)
        )
    return False


def _turnpike_finding(rows: list[JsonDict]) -> JsonDict:
    if not rows:
        return _missing_finding("turnpike_a800", "stability")
    payloads, invalid_count = _validated_payloads("turnpike_a800", rows)
    stationary = [payload for row, payload in payloads if row["role"] == "trajectory_stationary"]
    heterogeneous = [
        payload for row, payload in payloads if row["role"] == "trajectory_heterogeneous"
    ]
    metrics: JsonDict = {
        "stationary_count": len(stationary),
        "heterogeneous_count": len(heterogeneous),
        "stationary_alpha_mean": _mean_field(stationary, "alpha_emp_mean"),
        "heterogeneous_alpha_mean": _mean_field(heterogeneous, "alpha_emp_mean"),
        "stationary_r2_mean": _mean_field(stationary, "R2_mean"),
        "heterogeneous_r2_mean": _mean_field(heterogeneous, "R2_mean"),
        "invalid_source_count": invalid_count,
    }
    if not payloads:
        status = "requires_reanalysis"
    else:
        status = "observed" if stationary and heterogeneous else "mixed"
    return _base_finding(
        adapter="turnpike_a800",
        role="stability",
        status=status,
        observation=(
            f"Discovered {len(stationary)} stationary and {len(heterogeneous)} heterogeneous "
            "trajectory summaries."
        ),
        explanation=(
            "The contrast characterizes how representation decay changes with task stationarity "
            "and heterogeneity."
        ),
        confidence="medium" if stationary and heterogeneous else "low",
        scope="Recorded model/task trajectories in the scanned A800 results.",
        boundary=(
            "Turnpike-like decay is a trajectory diagnostic, not proof of global language-model "
            "convergence."
        ),
        next_action="Compare matched models, seeds, layers, and task families before generalizing.",
        source_rows=rows,
        raw_status="observed",
        metrics=metrics,
    )


def _riccati_finding(rows: list[JsonDict]) -> JsonDict:
    if not rows:
        return _missing_finding("riccati_ass_hyp", "stability")
    validated, invalid_count = _validated_payloads("riccati_ass_hyp", rows)
    payloads = [payload for _, payload in validated]
    dare_records = sum(_sequence_size(payload.get("ASS_HYP_via_DARE")) for payload in payloads)
    return _base_finding(
        adapter="riccati_ass_hyp",
        role="stability",
        status="observed" if dare_records else "requires_reanalysis",
        observation=(
            f"Discovered {len(payloads)} surrogate summaries with {dare_records} DARE records."
        ),
        explanation=(
            "The fitted reduced systems show how a local control surrogate responds to feedback "
            "and regularization choices."
        ),
        confidence="medium" if dare_records else "low",
        scope="Finite-dimensional fitted surrogate and its recorded fit window.",
        boundary="Closed-loop spectral radius does not prove stability of the operational LLM.",
        next_action="Audit fit residuals, conditioning, rank, and sensitivity before comparison.",
        source_rows=rows,
        raw_status="DARE_RECORDED" if dare_records else "DARE_MISSING",
        metrics={
            "summary_count": len(payloads),
            "dare_record_count": dare_records,
            "invalid_source_count": invalid_count,
        },
    )


def _soft_hard_finding(rows: list[JsonDict]) -> JsonDict:
    if not rows:
        return _missing_finding("soft_hard_tv", "mechanism")
    payloads, invalid_count = _validated_payloads("soft_hard_tv", rows)
    structured = [payload for _, payload in payloads]
    seed_rows = sum(_integer_field(payload, ("n_seed_rows", "n_rows")) for payload in structured)
    cells = sum(_integer_field(payload, ("n_cells",)) for payload in structured)
    uncertain = any(_contains_uncertain_interval(payload) for payload in structured)
    return _base_finding(
        adapter="soft_hard_tv",
        role="mechanism",
        status=(
            "requires_reanalysis"
            if not structured
            else "inconclusive" if uncertain else "mixed"
        ),
        observation=(
            f"Discovered {len(structured)} structured summaries, {seed_rows} recorded rows, "
            f"{cells} grouped cells, and {len(rows) - len(structured)} binary artifacts."
        ),
        explanation=(
            "Matched static, time-varying, shuffled, QAT, soft, and hard comparisons separate "
            "temporal structure from capacity and projection effects."
        ),
        confidence="medium" if structured else "low",
        scope="Recorded models, tasks, methods, seeds, and deployment projections only.",
        boundary=(
            "A mixed or interval-crossing comparison characterizes mechanism uncertainty; it "
            "does not establish universal optimizer superiority."
        ),
        next_action=(
            "Use paired cells and matched parameter budgets when interpreting each contrast."
        ),
        source_rows=rows,
        raw_status="MIXED_OR_SCOPE_DEPENDENT" if uncertain else "RECORDED",
        metrics={
            "structured_summary_count": len(structured),
            "seed_row_count": seed_rows,
            "cell_count": cells,
            "binary_artifact_count": len(rows) - len(structured),
            "invalid_source_count": invalid_count,
        },
    )


def _deployment_finding(rows: list[JsonDict]) -> JsonDict:
    if not rows:
        return _missing_finding("deployment_gate", "decision")
    payloads, invalid_count = _validated_payloads("deployment_gate", rows)
    analysis = next(
        (payload for row, payload in payloads if row["role"] == "confirmatory_analysis"), {}
    )
    interpretation = str(analysis.get("interpretation") or "REQUIRES_REANALYSIS")
    return _base_finding(
        adapter="deployment_gate",
        role="decision",
        status=(
            "requires_reanalysis"
            if not analysis
            else "inconclusive" if "FAIL_CLOSED" in interpretation else "observed"
        ),
        observation=(
            f"The recorded deployment analysis reports `{interpretation}` across "
            f"{analysis.get('n_rows', 'unknown')} rows."
        ),
        explanation=(
            "The protocol explains why structurally valid evidence can still require review when "
            "the mechanism or primary interaction is not sufficiently supported."
        ),
        confidence="high" if analysis else "low",
        scope="The frozen validator, hashes, tasks, models, and decision policy in this run.",
        boundary=(
            "Fail-closed is an evidence-constrained decision, not a statement of universal failure."
        ),
        next_action=(
            "Inspect the primary interaction and mechanism-health fields before deployment."
        ),
        source_rows=rows,
        raw_status=interpretation,
        metrics={
            "row_count": analysis.get("n_rows"),
            "all_validity_gates_passed": analysis.get("all_validity_gates_passed"),
            "invalid_source_count": invalid_count,
        },
    )


def _generation_finding(rows: list[JsonDict]) -> JsonDict:
    if not rows:
        return _missing_finding("generation_aware", "boundary")
    validated, invalid_count = _validated_payloads("generation_aware", rows)
    payloads = [payload for _, payload in validated]
    statuses = Counter(
        str(payload.get("status")) for payload in payloads if payload.get("status") is not None
    )
    return _base_finding(
        adapter="generation_aware",
        role="boundary",
        status="inconclusive" if statuses else "requires_reanalysis",
        observation=f"Discovered {len(payloads)} records with status counts {dict(statuses)}.",
        explanation=(
            "The records map where teacher-forced, mixed, and free-generation behavior diverge "
            "and where a proposed correction remains unsettled."
        ),
        confidence="medium" if statuses else "low",
        scope="Recorded generation-aware pilots and their locked stopping rules.",
        boundary="Pilot status does not prove a general remedy for train-generation mismatch.",
        next_action=(
            "Compare matched held-out rollouts only after the pilot gate permits continuation."
        ),
        source_rows=rows,
        raw_status=dict(statuses),
        metrics={
            "record_count": len(payloads),
            "status_counts": dict(statuses),
            "invalid_source_count": invalid_count,
        },
    )


def _selective_risk_finding(rows: list[JsonDict]) -> JsonDict:
    if not rows:
        return _missing_finding("selective_risk", "uncertainty")
    payloads, invalid_count = _validated_payloads("selective_risk", rows)
    payload = payloads[0][1] if payloads else {}
    status = str(payload.get("status") or "UNCLASSIFIED")
    return _base_finding(
        adapter="selective_risk",
        role="uncertainty",
        status=(
            "requires_reanalysis"
            if not payloads
            else "observed" if status == "SELECTIVE_RISK_PASS" else "mixed"
        ),
        observation=(
            f"Recorded selective-risk status `{status}` with "
            f"{payload.get('n_seed_rows', 'unknown')} "
            "seed rows."
        ),
        explanation=(
            "Risk-coverage behavior estimates whether restricting automation to higher-confidence "
            "cases improves reliability."
        ),
        confidence="medium" if payloads else "low",
        scope="The locked risk score, coverage rule, tasks, models, and held-out protocol.",
        boundary="Selective accuracy is not calibrated safety outside the evaluated distribution.",
        next_action="Monitor AURC and fixed-coverage accuracy under model and task drift.",
        source_rows=rows,
        raw_status=status,
        metrics={
            key: payload.get(key)
            for key in [
                "n_seed_rows",
                "observed_aurc",
                "random_mean_aurc",
                "accuracy_at_20pct",
                "accuracy_at_20pct_cluster_ci_lo",
                "accuracy_at_20pct_cluster_ci_hi",
            ]
        }
        | {"invalid_source_count": invalid_count},
    )


def _agent_episode_finding(rows: list[JsonDict]) -> JsonDict:
    if not rows:
        return _missing_finding("agent_episode", "mechanism")
    payloads, invalid_count = _validated_payloads("agent_episode", rows)
    title = payloads[0][1].get("title") if payloads else None
    return _base_finding(
        adapter="agent_episode",
        role="mechanism",
        status="observed" if payloads else "requires_reanalysis",
        observation=f"Discovered {len(payloads)} agent episode schema source(s); title={title!r}.",
        explanation=(
            "The episode structure links prompts, actions, verifier evidence, tests, and per-round "
            "state without treating one score as the full explanation."
        ),
        confidence="medium" if payloads else "low",
        scope="Schema capability only until populated episodes are imported.",
        boundary="A schema defines auditable fields; it does not validate an agent by itself.",
        next_action="Map ControlRun and ControlEvent records into versioned episode instances.",
        source_rows=rows,
        raw_status="SCHEMA_AVAILABLE" if payloads else "SCHEMA_UNREADABLE",
        metrics={"schema_count": len(payloads), "invalid_source_count": invalid_count},
    )


def _matrix_row(adapter: str, sources: list[JsonDict], findings: list[JsonDict]) -> JsonDict:
    finding = next(entry for entry in findings if entry["adapter"] == adapter)
    rows = [row for row in sources if row["adapter"] == adapter]
    return {
        "adapter": adapter,
        "source_count": len(rows),
        "support_status": finding["support_status"],
        "interpretation_role": finding["interpretation_role"],
        "confidence": finding["confidence"],
        "next_action": finding["next_action"],
    }


def _claim_check(findings: list[JsonDict]) -> JsonDict:
    available = [entry for entry in findings if entry["support_status"] == "observed"]
    pending = [
        entry for entry in findings if entry["support_status"] == "requires_reanalysis"
    ]
    return {
        "schema": "prompt_control_lab.interpretability_claim_check.v1",
        "status": "bounded_interpretation_available" if available else "insufficient_evidence",
        "mechanism_interpretation_available": any(
            entry["interpretation_role"] in {"mechanism", "stability", "boundary"}
            for entry in available
        ),
        "decision_evidence_available": any(
            entry["interpretation_role"] == "decision" for entry in available
        ),
        "observed_diagnostic_count": len(available),
        "requires_reanalysis_count": len(pending),
        "universal_improvement_supported": False,
        "allowed_claims": [
            "Recorded diagnostics can characterize mechanisms, stability, uncertainty, and scope.",
            "Decision artifacts can explain why a run passed, required review, or stopped.",
        ],
        "disallowed_claims": [
            "The imported evidence proves universal prompt or checkpoint improvement.",
            "A fitted surrogate proves global stability of the operational language model.",
        ],
    }


def _write_portable_bundle(out_dir: Path) -> None:
    portable_dir = out_dir / "portable"
    if portable_dir.is_symlink():
        msg = f"Portable evidence destination cannot be a symbolic link: {portable_dir}"
        raise ValueError(msg)
    ensure_dir(portable_dir)
    for name in (
        "public_source_manifest.json",
        "evidence_matrix.json",
        "interpretability_report.json",
        "interpretability_report.html",
        "claim_check.json",
    ):
        shutil.copyfile(out_dir / name, portable_dir / name)


def _prepare_output(out_dir: Path, *, overwrite: bool) -> None:
    _prepare_adapter_output(out_dir, overwrite=overwrite)


def _mean_field(payloads: list[JsonDict], key: str) -> float | None:
    values = [float(payload[key]) for payload in payloads if _finite_number(payload.get(key))]
    return sum(values) / len(values) if values else None


def _finite_number(value: object) -> bool:
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _bounded_number(
    value: object,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> bool:
    if not _finite_number(value):
        return False
    number = float(cast(int | float, value))
    return (minimum is None or number >= minimum) and (maximum is None or number <= maximum)


def _positive_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _valid_dare_records(value: object) -> bool:
    if isinstance(value, list):
        records = value
    elif isinstance(value, dict):
        records = [value]
    else:
        return False
    if not records:
        return False
    for record in records:
        if not isinstance(record, dict):
            return False
        success = record.get("success", record.get("dare_success"))
        if not isinstance(success, bool):
            return False
        rho = record.get("rho_A_cl", record.get("rho_closed_loop"))
        if success is True and not _bounded_number(rho, minimum=0.0):
            return False
        if rho is not None and not _bounded_number(rho, minimum=0.0):
            return False
        scale = record.get("R_scale", record.get("R"))
        if scale is None or not _bounded_number(scale, minimum=0.0):
            return False
        if "rho_open_subspace" in record and not _bounded_number(
            record.get("rho_open_subspace"), minimum=0.0
        ):
            return False
        if "alpha_theory" in record and not _bounded_number(
            record.get("alpha_theory"), minimum=0.0
        ):
            return False
    return True


def _normalize_non_finite(value: object) -> object:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(key): _normalize_non_finite(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_non_finite(item) for item in value]
    return value


def _sequence_size(value: object) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    return 0


def _integer_field(payload: JsonDict, keys: tuple[str, ...]) -> int:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return 0


def _contains_uncertain_interval(value: object) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower()
            if ("ci" in normalized or "interval" in normalized) and _crosses_zero(item):
                return True
            if (
                normalized in {"p", "p_value", "pvalue"}
                and _finite_number(item)
                and float(cast(float, item)) >= 0.05
            ):
                return True
            if _contains_uncertain_interval(item):
                return True
    elif isinstance(value, list):
        return any(_contains_uncertain_interval(item) for item in value)
    return False


def _crosses_zero(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(_finite_number(item) for item in value)
        and float(value[0]) <= 0 <= float(value[1])
    )


def _escape(value: object) -> str:
    return html.escape(str(value if value is not None else ""))
