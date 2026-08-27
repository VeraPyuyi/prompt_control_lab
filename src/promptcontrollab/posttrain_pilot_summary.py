"""Cross-seed summaries for the controlled post-training pilot."""

from __future__ import annotations

import html
from collections import Counter
from pathlib import Path
from statistics import mean

from promptcontrollab.core.files import JsonDict, read_json, write_json
from promptcontrollab.posttrain_pilot import aggregate_pilot_decisions


def write_pilot_summary(root: Path, *, seeds: tuple[int, ...]) -> JsonDict:
    """Aggregate initial-to-mid/final gates without weakening any seed decision."""

    stages = ("mid", "final")
    gates: list[JsonDict] = []
    missing: list[str] = []
    gate_traces: list[JsonDict] = []
    stage_decisions: JsonDict = {}
    stage_deltas: dict[str, list[float]] = {stage: [] for stage in stages}
    checkpoint_metrics: dict[str, list[JsonDict]] = {
        stage: [] for stage in ("initial", *stages)
    }
    missing_checkpoints: list[str] = []
    for seed in seeds:
        for checkpoint_stage in ("initial", *stages):
            checkpoint_dir = root / f"seed-{seed}" / f"checkpoint-{checkpoint_stage}"
            measurements = _checkpoint_measurements(checkpoint_dir)
            if measurements is None:
                missing_checkpoints.append(str(checkpoint_dir.relative_to(root)))
            else:
                checkpoint_metrics[checkpoint_stage].append(measurements)
        for stage in stages:
            gate_dir = root / f"seed-{seed}" / "gates" / f"initial-to-{stage}"
            gate_path = gate_dir / "posttrain_gate.json"
            comparison_path = gate_dir / "checkpoint_comparison.json"
            trace_path = gate_dir / "decision_trace.json"
            if not gate_path.is_file() or not comparison_path.is_file() or not trace_path.is_file():
                missing.append(str(gate_dir.relative_to(root)))
                continue
            gate = read_json(gate_path)
            comparison = read_json(comparison_path)
            trace = read_json(trace_path)
            decision = str(gate.get("decision", "insufficient_evidence"))
            score_delta = _optional_float(comparison.get("score_delta"))
            if score_delta is not None:
                stage_deltas[stage].append(score_delta)
            gates.append(
                {
                    "seed": seed,
                    "stage": stage,
                    "decision": decision,
                    "score_delta": score_delta,
                    "capability_profile": gate.get("capability_profile"),
                    "summary": gate.get("plain_summary"),
                    "gate_path": str(gate_path.relative_to(root).as_posix()),
                }
            )
            gate_traces.append(
                {
                    "seed": seed,
                    "stage": stage,
                    "decision": decision,
                    "checks": trace.get("checks", []),
                    "source": str(trace_path.relative_to(root).as_posix()),
                }
            )
    for stage in stages:
        decisions = [str(row["decision"]) for row in gates if row["stage"] == stage]
        if len(decisions) != len(seeds):
            decisions.append("insufficient_evidence")
        stage_decisions[stage] = aggregate_pilot_decisions(decisions)
    all_decisions = [str(row["decision"]) for row in gates]
    if missing:
        all_decisions.append("insufficient_evidence")
    decision = aggregate_pilot_decisions(all_decisions)
    delta_summary = {
        stage: _numeric_summary(values) for stage, values in stage_deltas.items()
    }
    checkpoint_summary = {
        stage: _summarize_checkpoint_measurements(rows)
        for stage, rows in checkpoint_metrics.items()
    }
    actual_checkpoint_count = sum(len(rows) for rows in checkpoint_metrics.values())
    payload: JsonDict = {
        "schema": "prompt_control_lab.posttrain_sft_pilot_summary.v1",
        "decision": decision,
        "seeds": list(seeds),
        "planned_checkpoint_run_count": len(seeds) * 3,
        "checkpoint_run_count": actual_checkpoint_count,
        "gate_count": len(gates),
        "stage_decisions": stage_decisions,
        "score_delta_by_stage": delta_summary,
        "checkpoint_metrics_by_stage": checkpoint_summary,
        "gates": gates,
        "missing_gates": missing,
        "missing_checkpoints": missing_checkpoints,
        "claim_boundary": (
            "This summary conservatively aggregates observed checkpoint evidence across seeds. "
            "It does not establish a causal training mechanism."
        ),
    }
    trace_payload: JsonDict = {
        "schema": "prompt_control_lab.posttrain_pilot_decision_trace.v1",
        "decision": decision,
        "aggregation_order": [
            "hold",
            "insufficient_evidence",
            "needs_review",
            "pass",
        ],
        "gate_traces": gate_traces,
        "missing_gates": missing,
    }
    write_json(root / "pilot_summary.json", payload)
    write_json(root / "decision_trace.json", trace_payload)
    (root / "pilot_summary.html").write_text(_render_html(payload), encoding="utf-8")
    return payload


def _checkpoint_measurements(checkpoint_dir: Path) -> JsonDict | None:
    if not (checkpoint_dir / "manifest.json").is_file() or not (
        checkpoint_dir / "metrics.json"
    ).is_file():
        return None
    metrics = read_json(checkpoint_dir / "metrics.json")
    diagnostics = checkpoint_dir / "diagnostics"
    return {
        "mean_score": _optional_float(metrics.get("mean_score")),
        "mean_tokens": _optional_float(metrics.get("mean_tokens")),
        "mean_latency_ms": _optional_float(metrics.get("mean_latency_ms")),
        "generation_saturation_rate": _optional_float(
            metrics.get("generation_saturation_rate")
        ),
        "trajectory_drift": _read_number(diagnostics / "trajectory.json", "mean_step_drift"),
        "generation_mismatch": _read_number(diagnostics / "generation_mismatch.json", "gap"),
        "selective_aurc": _read_number(diagnostics / "selective_risk.json", "observed_aurc"),
        "reachability_shift": _read_number(
            diagnostics / "prompt_reachability.json",
            "representation_shift_l2_normalized",
        ),
        "readout_alignment_gap": _read_number(
            diagnostics / "readout_alignment.json",
            "alignment_gap",
        ),
        "prompt_stability_drift": _read_number(
            diagnostics / "prompt_stability.json",
            "mean_step_drift",
        ),
        "routing_status": _read_text(
            diagnostics / "prompt_routing.json",
            "evidence_status",
            default="unknown",
        ),
        "projection_status": _read_text(
            diagnostics / "prompt_projection.json",
            "applicability",
            default="unknown",
        ),
    }


def _summarize_checkpoint_measurements(rows: list[JsonDict]) -> JsonDict:
    numeric_keys = (
        "mean_score",
        "mean_tokens",
        "mean_latency_ms",
        "generation_saturation_rate",
        "trajectory_drift",
        "generation_mismatch",
        "selective_aurc",
        "reachability_shift",
        "readout_alignment_gap",
        "prompt_stability_drift",
    )
    payload: JsonDict = {
        key: _numeric_summary(
            [float(row[key]) for row in rows if isinstance(row.get(key), int | float)]
        )
        for key in numeric_keys
    }
    payload["routing_status_counts"] = dict(
        sorted(Counter(str(row.get("routing_status", "unknown")) for row in rows).items())
    )
    payload["projection_status_counts"] = dict(
        sorted(Counter(str(row.get("projection_status", "unknown")) for row in rows).items())
    )
    return payload


def _read_number(path: Path, key: str) -> float | None:
    if not path.is_file():
        return None
    return _optional_float(read_json(path).get(key))


def _read_text(path: Path, key: str, *, default: str) -> str:
    if not path.is_file():
        return default
    value = str(read_json(path).get(key, "")).strip()
    return value or default


def _numeric_summary(values: list[float]) -> JsonDict:
    if not values:
        return {"count": 0, "mean": None, "min": None, "max": None}
    return {
        "count": len(values),
        "mean": round(mean(values), 12),
        "min": min(values),
        "max": max(values),
    }


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _render_html(payload: JsonDict) -> str:
    decision = html.escape(str(payload["decision"]))
    claim_boundary = html.escape(str(payload["claim_boundary"]))
    rows = "".join(
        "<tr>"
        f"<td>{row.get('seed')}</td><td>{html.escape(str(row.get('stage')))}</td>"
        f"<td>{html.escape(str(row.get('decision')))}</td>"
        f"<td>{html.escape(str(row.get('score_delta')))}</td></tr>"
        for row in payload.get("gates", [])
        if isinstance(row, dict)
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width"><title>SFT pilot summary</title><style>
body{{font-family:Arial,sans-serif;background:#f4f7fb;color:#172b4d;margin:0}}
main{{max-width:1080px;margin:auto;padding:32px}}header{{background:#153e75;color:white;padding:24px}}
table{{width:100%;border-collapse:collapse;background:white;margin-top:20px}}
th,td{{padding:10px;border:1px solid #d9e2ec;text-align:left}}</style></head><body><main>
<header><h1>Controlled SFT checkpoint pilot</h1>
<p>Decision: <b>{decision}</b></p></header>
<table><thead><tr><th>Seed</th><th>Stage</th><th>Decision</th><th>Score delta</th></tr></thead>
<tbody>{rows}</tbody></table><p>{claim_boundary}</p>
</main></body></html>"""
