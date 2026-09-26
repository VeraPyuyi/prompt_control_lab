"""Unified change review across prompts, models, agents, and checkpoints."""

from __future__ import annotations

import html
import json
import math
from pathlib import Path

from promptcontrollab.control.control_analysis import analyze_attribution, analyze_stability
from promptcontrollab.core.files import JsonDict, ensure_dir, read_json, write_json

_CHANGE_KINDS = {
    "auto",
    "prompt_change",
    "model_change",
    "agent_change",
    "checkpoint_change",
}
_REVIEW_MODES = {"shadow"}
_COMPARABLE_METRICS = (
    "mean_score",
    "score",
    "accuracy",
    "tests_pass_rate",
    "mean_total_tokens",
    "mean_tool_calls",
    "mean_touched_files",
    "mean_unnecessary_file_edits",
    "mean_duration_seconds",
    "mean_tokens",
    "mean_latency_ms",
    "generation_mismatch",
    "selective_aurc",
    "trajectory_drift",
)
_QUESTIONS = [
    "What changed?",
    "What was observed?",
    "What most likely explains the difference?",
    "How reliable is the evidence?",
    "What cannot be concluded?",
    "What should happen next?",
]


def review_changes(
    *,
    baseline_dir: Path,
    candidate_dir: Path,
    out_dir: Path,
    kind: str = "auto",
    mode: str = "shadow",
) -> JsonDict:
    """Compare two recorded runs and write a bounded, reviewer-facing artifact set.

    The review identifies observed associations and comparison confounders. It does not
    establish causal attribution, and shadow mode never alters either source run.
    """

    if kind not in _CHANGE_KINDS:
        raise ValueError(f"Unsupported change kind: {kind}")
    if mode not in _REVIEW_MODES:
        raise ValueError(f"Unsupported review mode: {mode}")
    _validate_sources(baseline_dir, candidate_dir, out_dir)

    baseline = _load_run(baseline_dir, "baseline")
    candidate = _load_run(candidate_dir, "candidate")
    change_kind = _detect_kind(baseline, candidate) if kind == "auto" else kind
    ensure_dir(out_dir)

    validity = _comparison_validity(baseline, candidate, change_kind)
    write_json(out_dir / "comparison_validity.json", validity)

    attribution = analyze_attribution(
        candidate,
        candidate["events"],
        baseline_run=baseline,
        baseline_artifacts={"events": baseline["events"]},
    ).to_json()
    stability = _review_stability(candidate)
    write_json(out_dir / "attribution.json", attribution)
    write_json(out_dir / "stability.json", stability)

    decision, reasons, next_action = _decision(
        baseline=baseline,
        candidate=candidate,
        validity=validity,
        stability=stability,
    )
    trace = _decision_trace(
        validity=validity,
        baseline=baseline,
        candidate=candidate,
        stability=stability,
        decision=decision,
    )
    feedback = _human_feedback(
        change_kind=change_kind,
        validity=validity,
        attribution=attribution,
        stability=stability,
        baseline=baseline,
        candidate=candidate,
        decision=decision,
        next_action=next_action,
    )
    write_json(out_dir / "decision_trace.json", trace)
    write_json(out_dir / "human_feedback.json", feedback)

    payload: JsonDict = {
        "schema": "prompt_control_lab.change_review.v1",
        "change_kind": change_kind,
        "mode": mode,
        "enforcement": "observe_only",
        "downstream_modified": False,
        "baseline_run": str(baseline_dir),
        "candidate_run": str(candidate_dir),
        "decision": decision,
        "reasons": reasons,
        "next_action": next_action,
        "observations": {
            "baseline_score": _score(baseline["metrics"]),
            "candidate_score": _score(candidate["metrics"]),
            "metric_deltas": _metric_deltas(
                baseline["metrics"],
                candidate["metrics"],
            ),
            "stability_state": stability.get("state"),
            "candidate_gate": candidate["posttrain_gate"].get("decision")
            or candidate["gate"].get("status"),
        },
        "coverage": {
            "baseline_manifest": bool(baseline["manifest"]),
            "candidate_manifest": bool(candidate["manifest"]),
            "baseline_metrics": bool(baseline["metrics"]),
            "candidate_metrics": bool(candidate["metrics"]),
            "baseline_events": bool(baseline["events"]),
            "candidate_events": bool(candidate["events"]),
            "baseline_gate": bool(baseline["gate"] or baseline["posttrain_gate"]),
            "candidate_gate": bool(candidate["gate"] or candidate["posttrain_gate"]),
        },
        "artifacts": [
            "comparison_validity.json",
            "attribution.json",
            "stability.json",
            "decision_trace.json",
            "human_feedback.json",
            "report.md",
            "report.html",
        ],
        "claim_boundary": (
            "This review describes recorded associations and decision evidence. "
            "It does not establish a unique causal explanation."
        ),
    }
    write_json(out_dir / "change_review.json", payload)
    _write_report(out_dir, payload, feedback, trace)
    return payload


def _validate_sources(baseline: Path, candidate: Path, out: Path) -> None:
    for label, path in (("baseline", baseline), ("candidate", candidate)):
        if not path.is_dir():
            raise ValueError(f"Missing {label} run directory: {path}")
    resolved_out = out.resolve(strict=False)
    for source in (baseline.resolve(), candidate.resolve()):
        overlaps = (
            resolved_out == source
            or resolved_out in source.parents
            or source in resolved_out.parents
        )
        if overlaps:
            raise ValueError("Change review output must not overlap either source run")
    if out.exists() and any(out.iterdir()):
        raise ValueError(f"Change review output directory must be empty: {out}")


def _load_run(run_dir: Path, fallback_id: str) -> JsonDict:
    manifest = _read_optional(run_dir / "manifest.json")
    control_run = _read_optional(run_dir / "control_run.json")
    merged = dict(manifest)
    for key, value in control_run.items():
        merged.setdefault(key, value)
    metrics = _read_optional(run_dir / "metrics.json") or _read_optional(
        run_dir / "candidate" / "metrics.json"
    )
    return {
        **merged,
        "run_id": str(merged.get("run_id") or run_dir.name or fallback_id),
        "manifest": manifest,
        "metrics": metrics,
        "gate": _read_optional(run_dir / "gate_result.json"),
        "posttrain_gate": _read_optional(run_dir / "posttrain_gate.json"),
        "events": _read_events(run_dir / "events.jsonl"),
        "prompt": _identity(merged, "prompt", ("prompt_hash", "prompt_id", "prompt_version")),
        "model_identity": _model_identity(merged),
        "agent_identity": _agent_identity(merged),
        "checkpoint_identity": _checkpoint_identity(merged),
        "split_hash": _nested_string(merged, "split", "split_hash")
        or _string(merged.get("split_hash")),
        "metric_identity": _string(merged.get("metric")),
    }


def _read_optional(path: Path) -> JsonDict:
    return read_json(path) if path.is_file() else {}


def _read_events(path: Path) -> list[JsonDict]:
    if not path.is_file():
        return []
    rows: list[JsonDict] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"Expected an object in {path}:{line_number}")
        rows.append(value)
    return rows


def _detect_kind(baseline: JsonDict, candidate: JsonDict) -> str:
    if _changed(baseline["checkpoint_identity"], candidate["checkpoint_identity"]):
        return "checkpoint_change"
    if _changed(baseline["agent_identity"], candidate["agent_identity"]):
        return "agent_change"
    if _changed(baseline["model_identity"], candidate["model_identity"]):
        return "model_change"
    return "prompt_change"


def _review_stability(candidate: JsonDict) -> JsonDict:
    """Keep independent-run repeatability separate from within-run convergence."""

    if candidate.get("capture") != "aggregate_public_safe":
        return analyze_stability(candidate, candidate["events"]).to_json()
    metrics = candidate.get("metrics")
    metric_values = metrics if isinstance(metrics, dict) else {}
    return {
        "schema": "prompt_control_lab.stability_report.v1",
        "run_id": candidate.get("run_id") or "unknown",
        "state": "insufficient_evidence",
        "signals": {
            "evidence_scope": "aggregate_independent_runs",
            "sample_count": metric_values.get("count"),
            "success_rate": _score(metric_values),
            "tests_pass_rate": metric_values.get("tests_pass_rate"),
            "confidence": "low",
        },
        "summary": (
            "Repeated-run outcomes were recorded, but aggregate samples do not establish "
            "within-run convergence, oscillation, or divergence."
        ),
    }


def _comparison_validity(
    baseline: JsonDict,
    candidate: JsonDict,
    change_kind: str,
) -> JsonDict:
    """Check whether only the identity expected for this comparison changed."""

    expected = change_kind.removesuffix("_change")
    checks: JsonDict = {}
    dimensions = {
        "prompt": (baseline["prompt"], candidate["prompt"]),
        "model": (baseline["model_identity"], candidate["model_identity"]),
        "agent": (baseline["agent_identity"], candidate["agent_identity"]),
        "checkpoint": (baseline["checkpoint_identity"], candidate["checkpoint_identity"]),
        "split": (baseline["split_hash"], candidate["split_hash"]),
        "metric": (baseline["metric_identity"], candidate["metric_identity"]),
    }
    blocking: list[str] = []
    review: list[str] = []
    for name, (old, new) in dimensions.items():
        known = bool(old) and bool(new)
        changed = _changed(old, new) if known else "unknown"
        if name == expected:
            status = "pass" if changed is True else "review"
            meaning = (
                f"The expected {name} identity changed."
                if status == "pass"
                else f"The expected {name} change could not be verified."
            )
        elif changed is True:
            status = "fail" if name in {"model", "split", "metric"} else "review"
            meaning = f"The {name} identity also changed and may confound this comparison."
        elif changed == "unknown":
            status = "review"
            meaning = f"The {name} identity was not recorded on both runs."
        else:
            status = "pass"
            meaning = f"The recorded {name} identity stayed the same."
        checks[name] = {
            "status": status,
            "changed": changed,
            "baseline": old,
            "candidate": new,
            "what_this_means": meaning,
        }
        if status == "fail":
            blocking.append(meaning)
        elif status == "review":
            review.append(meaning)
    validity = "invalid" if blocking else "needs_review" if review else "clean"
    return {
        "schema": "prompt_control_lab.change_comparison_validity.v1",
        "change_kind": change_kind,
        "validity": validity,
        "checks": checks,
        "blocking_issues": blocking,
        "review_items": review,
        "plain_summary": (
            "The recorded identities support the requested change comparison."
            if validity == "clean"
            else "Review the recorded identity gaps or confounders before attributing the result."
        ),
    }


def _decision(
    *,
    baseline: JsonDict,
    candidate: JsonDict,
    validity: JsonDict,
    stability: JsonDict,
) -> tuple[str, list[str], str]:
    """Combine gate, validity, stability, and metric evidence conservatively.

    A positive score change cannot override a blocking candidate gate, invalid
    comparison, unstable run, or non-finite metric. The returned rationale and
    next action preserve that evidence boundary for reviewer-facing reports.
    """
    old_score = _score(baseline["metrics"])
    new_score = _score(candidate["metrics"])
    state = _string(stability.get("state")) or "insufficient_evidence"
    gate_decision = _string(candidate["posttrain_gate"].get("decision")) or _string(
        candidate["gate"].get("status")
    )
    if _contains_nonfinite(baseline["metrics"]) or _contains_nonfinite(candidate["metrics"]):
        return (
            "insufficient_evidence",
            ["One or more recorded metrics are non-finite and cannot support a decision."],
            "Replace invalid metric values and rerun the review.",
        )
    if gate_decision in {"hold", "fail"}:
        return (
            "hold",
            ["The recorded candidate post-training gate or deployment gate requires a hold."],
            "Inspect the candidate gate decision trace before promotion.",
        )
    if gate_decision == "insufficient_evidence":
        return (
            "insufficient_evidence",
            ["The candidate gate reports insufficient evidence."],
            "Collect the evidence required by the candidate gate before promotion.",
        )
    if gate_decision in {"needs_review", "review"}:
        return (
            "needs_review",
            ["The candidate gate requires human review."],
            "Resolve the candidate gate review items before promotion.",
        )
    if old_score is not None and new_score is not None and new_score < old_score:
        return "hold", ["The candidate score regressed."], "Inspect regressions before promotion."
    if state == "diverging":
        return "hold", ["Candidate execution signals are diverging."], "Inspect run stability."
    if not baseline["metrics"] and not candidate["metrics"] and not candidate["events"]:
        return (
            "insufficient_evidence",
            ["No score or execution evidence was recorded."],
            "Collect metrics or execution events and rerun the review.",
        )
    if validity.get("validity") != "clean" or state in {"stalled", "oscillating"}:
        return (
            "needs_review",
            ["Comparison validity or stability evidence needs human review."],
            "Resolve the listed evidence gaps before promotion.",
        )
    return "pass", ["No blocking issue was observed in the recorded evidence."], (
        "Keep the review artifact with the release decision."
    )


def _decision_trace(
    *,
    validity: JsonDict,
    baseline: JsonDict,
    candidate: JsonDict,
    stability: JsonDict,
    decision: str,
) -> JsonDict:
    """Build the inspectable checks that support the reviewer-facing decision."""

    old_score = _score(baseline["metrics"])
    new_score = _score(candidate["metrics"])
    delta = None if old_score is None or new_score is None else new_score - old_score
    metric_deltas = _metric_deltas(baseline["metrics"], candidate["metrics"])
    candidate_gate = candidate["posttrain_gate"].get("decision") or candidate["gate"].get(
        "status"
    )
    invalid_metrics = _contains_nonfinite(baseline["metrics"]) or _contains_nonfinite(
        candidate["metrics"]
    )
    return {
        "schema": "prompt_control_lab.change_review_decision_trace.v1",
        "decision": decision,
        "checks": [
            {
                "check": "comparison_validity",
                "observed": validity.get("validity"),
                "status": "passed" if validity.get("validity") == "clean" else "triggered",
                "evidence": ["comparison_validity.json"],
            },
            {
                "check": "score_delta",
                "observed": delta,
                "status": (
                    "invalid"
                    if invalid_metrics
                    else "missing"
                    if delta is None
                    else "passed"
                    if delta >= 0
                    else "triggered"
                ),
                "evidence": ["baseline/metrics.json", "candidate/metrics.json"],
            },
            {
                "check": "stability",
                "observed": stability.get("state"),
                "status": (
                    "triggered"
                    if stability.get("state") in {"diverging", "stalled", "oscillating"}
                    else "passed"
                ),
                "evidence": ["stability.json"],
            },
            {
                "check": "candidate_gate",
                "observed": candidate_gate,
                "status": (
                    "missing"
                    if not candidate_gate
                    else "passed"
                    if candidate_gate in {"pass", "passed", "allow", "success"}
                    else "triggered"
                ),
                "evidence": ["candidate/posttrain_gate.json", "candidate/gate_result.json"],
            },
            {
                "check": "secondary_metric_deltas",
                "observed": metric_deltas,
                "status": "observed" if metric_deltas else "missing",
                "evidence": ["baseline/metrics.json", "candidate/metrics.json"],
            },
        ],
    }


def _human_feedback(
    *,
    change_kind: str,
    validity: JsonDict,
    attribution: JsonDict,
    stability: JsonDict,
    baseline: JsonDict,
    candidate: JsonDict,
    decision: str,
    next_action: str,
) -> JsonDict:
    changed = [
        str(item.get("factor"))
        for item in attribution.get("factors", [])
        if isinstance(item, dict) and item.get("changed") is True
    ]
    old_score = _score(baseline.get("metrics"))
    new_score = _score(candidate.get("metrics"))
    score_observation = (
        "score evidence was not recorded"
        if old_score is None or new_score is None
        else f"score changed from {old_score:.6g} to {new_score:.6g}"
    )
    secondary_observation = _metric_delta_summary(
        _metric_deltas(baseline.get("metrics"), candidate.get("metrics"))
    )
    candidate_gate = candidate.get("posttrain_gate") or candidate.get("gate") or {}
    gate_value = candidate_gate.get("decision") or candidate_gate.get("status")
    gate_observation = f"; candidate gate={gate_value}" if gate_value else ""
    answers = {
        _QUESTIONS[0]: change_kind,
        _QUESTIONS[1]: (
            f"{score_observation}{secondary_observation}; "
            f"stability={stability.get('state')}{gate_observation}."
        ),
        _QUESTIONS[2]: ", ".join(changed) if changed else change_kind,
        _QUESTIONS[3]: (
            f"identity comparison={validity.get('validity') or 'unknown'}; "
            f"execution stability={stability.get('state') or 'unknown'}"
        ),
        _QUESTIONS[4]: "The evidence does not establish a unique causal explanation.",
        _QUESTIONS[5]: next_action,
    }
    return {
        "schema": "prompt_control_lab.human_feedback.v1",
        "questions": list(_QUESTIONS),
        "answers": answers,
    }


def _write_report(
    out_dir: Path,
    review: JsonDict,
    feedback: JsonDict,
    trace: JsonDict,
) -> None:
    answers = feedback.get("answers")
    answer_dict = answers if isinstance(answers, dict) else {}
    lines = [
        "# PromptControlLab Change Review",
        "",
        f"- Change kind: `{review.get('change_kind')}`",
        f"- Decision: `{review.get('decision')}`",
        f"- Mode: `{review.get('mode')}` (observation only)",
        "",
    ]
    for question in _QUESTIONS:
        lines.extend([f"## {question}", "", str(answer_dict.get(question) or "Unknown."), ""])
    lines.extend(["## Claim boundary", "", str(review.get("claim_boundary")), ""])
    markdown = "\n".join(lines)
    (out_dir / "report.md").write_text(markdown, encoding="utf-8")
    cards = "".join(_answer_card(question, answer_dict.get(question)) for question in _QUESTIONS)
    decision = html.escape(str(review.get("decision")))
    trace_text = html.escape(json.dumps(trace, indent=2))
    document = (
        "<!doctype html><html><head><meta charset='utf-8'><title>Change Review</title>"
        "<style>body{font-family:system-ui;max-width:1100px;margin:auto;padding:32px;"
        "background:#f7f7f5;color:#1d2525}"
        "header{border-bottom:3px solid #1f766e;padding-bottom:20px}"
        "section{padding:18px 0;border-bottom:1px solid #d7dddd}"
        "code{background:#e8eeec;padding:2px 5px}h1,h2{letter-spacing:0}</style></head><body>"
        "<header><h1>PromptControlLab Change Review</h1>"
        f"<p>Decision: <strong>{decision}</strong></p></header>"
        f"{cards}<section><h2>Decision trace</h2><pre>{trace_text}</pre></section>"
        "</body></html>"
    )
    (out_dir / "report.html").write_text(document, encoding="utf-8")


def _answer_card(question: str, answer: object) -> str:
    """Render one escaped report answer card."""

    return (
        f"<section><h2>{html.escape(question)}</h2>"
        f"<p>{html.escape(str(answer or 'Unknown.'))}</p></section>"
    )


def _identity(payload: JsonDict, nested: str, keys: tuple[str, ...]) -> JsonDict:
    result: JsonDict = {}
    nested_value = payload.get(nested)
    nested_dict = nested_value if isinstance(nested_value, dict) else {}
    for key in keys:
        value = nested_dict.get(key, payload.get(key))
        if value not in {None, ""}:
            result[key] = value
    return result


def _model_identity(payload: JsonDict) -> JsonDict:
    for key in ("model", "candidate_model", "baseline_model"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    model = _string(payload.get("model"))
    provider = _string(payload.get("provider"))
    return {key: value for key, value in {"model_id": model, "provider": provider}.items() if value}


def _agent_identity(payload: JsonDict) -> JsonDict:
    value = payload.get("agent")
    if isinstance(value, dict):
        return value
    name = _string(value)
    return {"agent": name} if name else {}


def _checkpoint_identity(payload: JsonDict) -> JsonDict:
    value = payload.get("checkpoint")
    if isinstance(value, dict):
        return value
    checkpoint_id = _string(payload.get("checkpoint_id"))
    return {"checkpoint_id": checkpoint_id} if checkpoint_id else {}


def _nested_string(payload: JsonDict, key: str, nested_key: str) -> str | None:
    value = payload.get(key)
    return _string(value.get(nested_key)) if isinstance(value, dict) else None


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _changed(old: object, new: object) -> bool:
    return old != new


def _score(metrics: object) -> float | None:
    if not isinstance(metrics, dict):
        return None
    for key in ("mean_score", "score", "accuracy"):
        value = metrics.get(key)
        if isinstance(value, int | float) and not isinstance(value, bool):
            number = float(value)
            return number if math.isfinite(number) else None
    return None


def _metric_deltas(baseline: object, candidate: object) -> JsonDict:
    """Return bounded numeric deltas for execution and evaluation metrics."""

    if not isinstance(baseline, dict) or not isinstance(candidate, dict):
        return {}
    result: JsonDict = {}
    for key in _COMPARABLE_METRICS:
        old = _number(baseline.get(key))
        new = _number(candidate.get(key))
        if old is None or new is None:
            continue
        delta = new - old
        result[key] = {
            "baseline": old,
            "candidate": new,
            "delta": delta,
            "direction": "increase" if delta > 0 else "decrease" if delta < 0 else "unchanged",
        }
    return result


def _metric_delta_summary(deltas: JsonDict) -> str:
    """Render a short execution-metric summary for the reviewer questions."""

    parts: list[str] = []
    for key in _COMPARABLE_METRICS:
        if key in {"mean_score", "score", "accuracy"}:
            continue
        value = deltas.get(key)
        if not isinstance(value, dict):
            continue
        direction = value.get("direction")
        old = _number(value.get("baseline"))
        new = _number(value.get("candidate"))
        if direction and old is not None and new is not None:
            verb = {
                "increase": "increased",
                "decrease": "decreased",
                "unchanged": "stayed unchanged",
            }.get(str(direction), str(direction))
            parts.append(f"{key} {verb} from {old:.6g} to {new:.6g}")
        if len(parts) == 4:
            break
    return "; " + "; ".join(parts) if parts else ""


def _number(value: object) -> float | None:
    """Return finite scalar-like metrics while excluding booleans."""

    if isinstance(value, int | float) and not isinstance(value, bool):
        number = float(value)
        if math.isfinite(number):
            return number
    return None


def _contains_nonfinite(value: object) -> bool:
    """Return whether a nested metrics payload contains NaN or infinity."""

    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, int | float):
        return not math.isfinite(float(value))
    if isinstance(value, dict):
        return any(_contains_nonfinite(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_nonfinite(item) for item in value)
    return False
