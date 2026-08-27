"""Interpretability analysis and rendering for imported evidence."""

from __future__ import annotations

import hashlib
import html
import json
import math
import shutil
from collections import Counter
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import cast

from promptcontrollab.core.files import JsonDict, ensure_dir, stable_digest
from promptcontrollab.evidence.evidence_profiles import get_evidence_profile
from promptcontrollab.evidence.server.constants import (
    ADAPTERS,
)
from promptcontrollab.evidence.server.constants import (
    CHUNK_SIZE as _CHUNK_SIZE,
)
from promptcontrollab.evidence.server.destination import _prepare_adapter_output
from promptcontrollab.evidence.server.digest import _canonical_source_digest


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
<p>{_escape(report.get("boundary"))}</p><p>{count_text}</p></div><div class="grid">
{"".join(cards)}</div></main></body></html>"""


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
                _canonical_source_digest(path, content, digest) if content is not None else digest
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
        adapter: [row for row in sources if row["adapter"] == adapter] for adapter in ADAPTERS
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
    """Check whether one adapter payload has finite, structurally valid evidence."""

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
                or _bounded_number(payload.get("accuracy_at_20pct"), minimum=0.0, maximum=1.0)
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
            "requires_reanalysis" if not structured else "inconclusive" if uncertain else "mixed"
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
            else "inconclusive"
            if "FAIL_CLOSED" in interpretation
            else "observed"
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
            else "observed"
            if status == "SELECTIVE_RISK_PASS"
            else "mixed"
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
    pending = [entry for entry in findings if entry["support_status"] == "requires_reanalysis"]
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
