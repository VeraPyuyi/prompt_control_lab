"""Read-only discovery and normalization for dispersed diagnostic evidence."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from promptcontrollab.core.files import JsonDict, ensure_dir, read_json, stable_digest, write_json
from promptcontrollab.evidence.evidence_profiles import (
    EvidenceProfile,
    get_evidence_profile,
)
from promptcontrollab.evidence.evidence_profiles import (
    evidence_profile_registry as _evidence_profile_registry,
)
from promptcontrollab.evidence.server.analysis import (
    _build_findings,
    _claim_check,
    _file_integrity,
    _finite_number,
    _load_policy,
    _matrix_row,
    _media_type,
    _normalize_non_finite,
    _prepare_output,
    _profile_patterns,
    _public_source_manifest,
    _snapshot_identity,
    _source_role,
    _validate_manifest,
    _write_portable_bundle,
)
from promptcontrollab.evidence.server.analysis import (
    _verify_sources as _verify_sources,
)
from promptcontrollab.evidence.server.analysis import (
    render_interpretability_html as render_interpretability_html,
)
from promptcontrollab.evidence.server.constants import (
    ADAPTERS as ADAPTERS,
)
from promptcontrollab.evidence.server.constants import (
    CHUNK_SIZE,
)
from promptcontrollab.evidence.server.constants import (
    MANIFEST_SCHEMA as MANIFEST_SCHEMA,
)
from promptcontrollab.evidence.server.constants import (
    MATRIX_SCHEMA as MATRIX_SCHEMA,
)
from promptcontrollab.evidence.server.constants import (
    REPORT_SCHEMA as REPORT_SCHEMA,
)
from promptcontrollab.evidence.server.destination import (
    _prepare_adapter_output,
)
from promptcontrollab.evidence.server.destination import (
    validate_evidence_destination as validate_evidence_destination,
)
from promptcontrollab.evidence.server.digest import _canonical_source_digest

_CHUNK_SIZE = CHUNK_SIZE


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
    """Scan one evidence profile and record source metadata without executing artifacts."""

    profile_spec = get_evidence_profile(profile)
    discovered: dict[str, tuple[str, str]] = {}
    for adapter in profile_spec.adapters:
        for pattern in adapter.patterns:
            search_patterns = (
                (pattern,) if pattern.startswith("**/") else (pattern, f"**/{pattern}")
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
        "interpretation_roles": sorted({str(entry["interpretation_role"]) for entry in findings}),
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
        if isinstance(root_value, dict) and isinstance(root_value.get("resolved_path"), str):
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
    """Merge two verified portable evidence runs with explicit reconciliation."""

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
            row.get("adapter") == adapter and row.get("status") == "canonical_equivalent"
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
            "source_evidence": [row for row in merged_sources if row.get("adapter") == adapter],
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
    """Write a derived evidence run from reconciled findings and source metadata."""

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
        "interpretation_roles": sorted({str(entry["interpretation_role"]) for entry in findings}),
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
    return {name: _file_integrity(root / name)[1] for name in sorted(names)}


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
    """Load artifacts only after validating their portable manifest and boundaries."""

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
    """Write normalized adapter findings, reports, and optional portable sources."""

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
                [row for row in verified_sources if row.get("adapter") == finding["adapter"]]
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
        "interpretation_roles": sorted({str(entry["interpretation_role"]) for entry in findings}),
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
