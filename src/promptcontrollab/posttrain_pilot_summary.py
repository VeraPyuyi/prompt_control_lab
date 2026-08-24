"""Cross-seed summaries for the controlled post-training pilot."""

from __future__ import annotations

import html
from pathlib import Path
from statistics import mean

from promptcontrollab.files import JsonDict, read_json, write_json
from promptcontrollab.posttrain_pilot import aggregate_pilot_decisions


def write_pilot_summary(root: Path, *, seeds: tuple[int, ...]) -> JsonDict:
    """Aggregate initial-to-mid/final gates without weakening any seed decision."""

    stages = ("mid", "final")
    gates: list[JsonDict] = []
    missing: list[str] = []
    gate_traces: list[JsonDict] = []
    stage_decisions: JsonDict = {}
    stage_deltas: dict[str, list[float]] = {stage: [] for stage in stages}
    for seed in seeds:
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
                    "gate_path": str(gate_path.resolve()),
                }
            )
            gate_traces.append(
                {
                    "seed": seed,
                    "stage": stage,
                    "decision": decision,
                    "checks": trace.get("checks", []),
                    "source": str(trace_path.resolve()),
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
    payload: JsonDict = {
        "schema": "prompt_control_lab.posttrain_sft_pilot_summary.v1",
        "decision": decision,
        "seeds": list(seeds),
        "checkpoint_run_count": len(seeds) * 3,
        "gate_count": len(gates),
        "stage_decisions": stage_decisions,
        "score_delta_by_stage": delta_summary,
        "gates": gates,
        "missing_gates": missing,
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
