"""Control-run, provenance, and certificate data readers."""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from promptcontrollab.control.control_protocol import REDACTED, redact_sensitive
from promptcontrollab.core.files import JsonDict
from promptcontrollab.integrations.ui.data.common import _mapping
from promptcontrollab.integrations.ui.data.constants import PROMPT_REACH_ARTIFACTS

_HIDDEN_DISPLAY_KEYS = {
    "analysis",
    "chain_of_thought",
    "chainofthought",
    "cot",
    "hidden_reasoning",
    "reasoning",
    "reasoning_content",
    "thinking",
    "thoughts",
}


_SAFE_AUTHORIZATION_VALUES = {
    "agent",
    "agent-full",
    "agent-scoped",
    "inspect",
    "inspect-only",
    "model",
    "model-scoped",
}


def interpretability_rows(detail: JsonDict) -> list[JsonDict]:
    """Normalize explanation-first evidence findings for UI tables and cards."""

    report_value = detail.get("interpretability_report")
    report = report_value if isinstance(report_value, dict) else {}
    findings = report.get("findings")
    if not isinstance(findings, list):
        return []
    rows: list[JsonDict] = []
    for raw in findings:
        if not isinstance(raw, dict):
            continue
        finding = cast(JsonDict, raw)
        rows.append(
            {
                "adapter": finding.get("adapter") or finding.get("dimension"),
                "role": finding.get("interpretation_role"),
                "status": finding.get("support_status"),
                "confidence": finding.get("confidence"),
                "observation": finding.get("observation"),
                "explanation": finding.get("explanation"),
                "observed": finding.get("observation"),
                "explains": finding.get("explanation"),
                "scope": finding.get("scope"),
                "claim_boundary": finding.get("claim_boundary"),
                "does_not_prove": finding.get("claim_boundary"),
                "next_action": finding.get("next_action"),
            }
        )
    return rows


def control_certificate_interpretation_rows(
    detail: JsonDict,
    language: str = "en",
) -> list[JsonDict]:
    """Return bounded interpretation records for the three control certificates."""

    diagnostics_value = detail.get("diagnostics")
    diagnostics = diagnostics_value if isinstance(diagnostics_value, dict) else {}
    labels = {
        "en": {
            "terminal_sensitivity": "Terminal sensitivity",
            "green_certificate": "Green certificate",
            "posterior_certificate": "Posterior certificate",
        },
        "zh": {
            "terminal_sensitivity": "终端敏感度",
            "green_certificate": "Green 边界证书",
            "posterior_certificate": "局部后验证书",
        },
    }
    lang = "zh" if language == "zh" else "en"
    roles = {
        "terminal_sensitivity": "stability",
        "green_certificate": "stability",
        "posterior_certificate": "uncertainty",
    }
    rows: list[JsonDict] = []
    for name in ("terminal_sensitivity", "green_certificate", "posterior_certificate"):
        value = diagnostics.get(name)
        if not isinstance(value, dict) or not value:
            continue
        level = str(value.get("certificate_level") or "insufficient_evidence")
        rows.append(
            {
                "adapter": name,
                "diagnostic": labels[lang][name],
                "role": roles[name],
                "status": value.get("check_state") or "unknown",
                "confidence": _certificate_confidence(level),
                "certificate_level": level,
                "observed": value.get("observation") or _certificate_observation(name, value),
                "explains": value.get("explanation") or "A scoped control signal was recorded.",
                "does_not_prove": value.get("claim_boundary")
                or "This result does not prove the full language model.",
                "next_action": value.get("next_action")
                or "Retain the artifact and inspect its premise record.",
            }
        )
    return rows


def terminal_sensitivity_rows(detail: JsonDict) -> list[JsonDict]:
    """Return terminal-sensitivity records suitable for a distance-decay chart."""

    payload = _control_certificate_payload(detail, "terminal_sensitivity")
    records = payload.get("records")
    rows = [cast(JsonDict, row) for row in records if isinstance(row, dict)] if isinstance(
        records, list
    ) else []
    return sorted(
        [
            {
                "horizon": row.get("horizon"),
                "early_step": row.get("early_step"),
                "distance_to_terminal": row.get("distance_to_terminal"),
                "sensitivity": row.get("sensitivity"),
                "log_sensitivity": row.get("log_sensitivity"),
                "intervention_kind": row.get("intervention_kind"),
                "checkpoint": row.get("checkpoint"),
                "model": row.get("model"),
            }
            for row in rows
        ],
        key=lambda row: (
            int(row.get("distance_to_terminal") or 0),
            int(row.get("early_step") or 0),
        ),
    )


def green_certificate_rows(detail: JsonDict) -> list[JsonDict]:
    """Return sampled Green boundary margins for charting."""

    payload = _control_certificate_payload(detail, "green_certificate")
    horizons = payload.get("horizons")
    rows = [cast(JsonDict, row) for row in horizons if isinstance(row, dict)] if isinstance(
        horizons, list
    ) else []
    return sorted(
        [
            {
                "horizon": row.get("horizon"),
                "boundary_sigma_min": row.get("boundary_sigma_min"),
                "recovery_residual": row.get("coefficient_recovery_residual"),
                "passed": row.get("passed"),
            }
            for row in rows
        ],
        key=lambda row: int(row.get("horizon") or 0),
    )


def posterior_certificate_metrics(detail: JsonDict) -> JsonDict:
    """Return the local posterior scalar margins shown by the dashboard."""

    payload = _control_certificate_payload(detail, "posterior_certificate")
    return {
        "certificate_level": payload.get("certificate_level"),
        "check_state": payload.get("check_state"),
        "h": payload.get("h"),
        "existence_radius": payload.get("existence_radius"),
        "neighborhood_margin": payload.get("neighborhood_margin"),
    }


def _control_certificate_payload(detail: JsonDict, name: str) -> JsonDict:
    """Normalize control certificate payload values for dashboard use."""
    diagnostics = detail.get("diagnostics")
    if not isinstance(diagnostics, dict):
        return {}
    payload = diagnostics.get(name)
    return payload if isinstance(payload, dict) else {}


def _certificate_confidence(level: str) -> str:
    """Normalize certificate confidence values for dashboard use."""
    return {
        "certificate_verified": "high",
        "surrogate_consistent": "medium",
        "empirical_only": "low",
        "not_applicable": "not_applicable",
        "insufficient_evidence": "unknown",
    }.get(level, "unknown")


def _certificate_observation(name: str, payload: JsonDict) -> str:
    """Normalize certificate observation values for dashboard use."""
    if name == "terminal_sensitivity":
        return f"decay_rate={payload.get('decay_rate')}; R2={payload.get('r_squared')}"
    if name == "green_certificate":
        return (
            f"spectral_gap={payload.get('hyperbolicity_margin')}; "
            f"sigma_min={payload.get('boundary_sigma_min')}"
        )
    return (
        f"h={payload.get('h')}; radius={payload.get('existence_radius')}; "
        f"margin={payload.get('neighborhood_margin')}"
    )


def prompt_reach_interpretation_rows(
    detail: JsonDict,
    language: str = "en",
) -> list[JsonDict]:
    """Normalize the five prompt-reach diagnostics into explanation-first rows."""

    artifacts_value = detail.get("prompt_reach_artifacts")
    artifacts = artifacts_value if isinstance(artifacts_value, dict) else {}
    rows: list[JsonDict] = []
    for name in PROMPT_REACH_ARTIFACTS:
        raw = artifacts.get(name)
        if not isinstance(raw, dict):
            continue
        payload = cast(JsonDict, raw)
        defaults = _prompt_reach_defaults(name, language)
        status = (
            payload.get("support_status")
            or payload.get("evidence_status")
            or payload.get("applicability")
            or "unknown"
        )
        rows.append(
            {
                "adapter": name,
                "role": payload.get("interpretation_role") or defaults["role"],
                "status": status,
                "confidence": payload.get("confidence") or "unknown",
                "observed": (
                    payload.get("observation")
                    or payload.get("reason")
                    or _prompt_reach_metric_observation(name, payload, language)
                ),
                "explains": payload.get("explanation") or defaults["explains"],
                "does_not_prove": payload.get("claim_boundary")
                or defaults["does_not_prove"],
                "next_action": payload.get("next_action") or defaults["next_action"],
                "metrics": payload.get("metrics") or {},
            }
        )
    return rows


def decision_trace_interpretation_rows(
    detail: JsonDict,
    language: str = "en",
) -> list[JsonDict]:
    """Normalize post-training decision checks into the same four-part UI contract."""

    trace_value = detail.get("decision_trace")
    trace = trace_value if isinstance(trace_value, dict) else {}
    checks = trace.get("checks")
    if isinstance(checks, dict):
        check_rows = [
            {"check": name, **cast(JsonDict, value)}
            for name, value in checks.items()
            if isinstance(value, dict)
        ]
    elif isinstance(checks, list):
        check_rows = [cast(JsonDict, value) for value in checks if isinstance(value, dict)]
    else:
        check_rows = []
    boundary = str(
        trace.get("claim_boundary")
        or (
            "The gate trace records configured checks; it does not prove causality or safety."
            if language == "en"
            else "门禁轨迹记录的是已配置检查, 不能证明因果关系或安全性。"
        )
    )
    rows: list[JsonDict] = []
    for check in check_rows:
        impact = str(check.get("impact") or "none")
        explanation = (
            f"This check contributes {impact} to the recorded checkpoint decision."
            if language == "en"
            else f"这项检查对已记录的 checkpoint 决策产生 {impact} 影响。"
        )
        evidence = check.get("evidence")
        rows.append(
            {
                "adapter": check.get("check") or "unnamed_check",
                "role": "decision",
                "status": check.get("status") or "unknown",
                "confidence": check.get("confidence") or "unknown",
                "observed": check.get("observed"),
                "explains": check.get("explanation") or explanation,
                "does_not_prove": boundary,
                "next_action": check.get("next_action")
                or (
                    "Review the recorded evidence for this check."
                    if language == "en"
                    else "复核这项检查对应的已记录证据。"
                ),
                "threshold": check.get("threshold"),
                "evidence": evidence if isinstance(evidence, list) else [],
            }
        )
    return rows


def _load_prompt_reach_artifacts(run_dir: Path) -> tuple[JsonDict, list[str]]:
    """Load prompt reach artifacts data for the dashboard."""
    artifacts: JsonDict = {}
    paths: list[str] = []
    for name in PROMPT_REACH_ARTIFACTS:
        for relative in (Path(f"{name}.json"), Path("diagnostics") / f"{name}.json"):
            payload = _read_control_json(run_dir / relative)
            if payload:
                artifacts[name] = payload
                paths.append(relative.as_posix())
                break
    return artifacts, paths


def _prompt_reach_metric_observation(
    name: str,
    payload: JsonDict,
    language: str,
) -> str:
    """Normalize prompt reach metric observation values for dashboard use."""
    fields = {
        "prompt_reachability": ("representation_shift_l2_normalized", "score_delta"),
        "readout_alignment": ("alignment_gap", "teacher_forced_score", "free_generation_score"),
        "prompt_routing": (),
        "prompt_projection": (),
        "prompt_stability": ("mean_step_drift",),
    }[name]
    values = [f"{key}={payload[key]}" for key in fields if payload.get(key) is not None]
    if values:
        prefix = "Recorded" if language == "en" else "已记录"
        return f"{prefix}: {', '.join(values)}."
    return (
        "The artifact is present, but it contains no concise supported observation."
        if language == "en"
        else "该 artifact 已存在, 但没有可简洁展示的受支持观测值。"
    )


def _prompt_reach_defaults(name: str, language: str) -> JsonDict:
    """Normalize prompt reach defaults values for dashboard use."""
    english: dict[str, JsonDict] = {
        "prompt_reachability": {
            "role": "mechanism",
            "explains": "How reachable prompt-conditioned representations differ across runs.",
            "does_not_prove": "It does not prove a unique causal representation path.",
            "next_action": "Compare matched checkpoints and seeds.",
        },
        "readout_alignment": {
            "role": "mechanism",
            "explains": "How closely the recorded readout agrees with generated answers.",
            "does_not_prove": "It does not identify a unique hidden mechanism.",
            "next_action": "Inspect tasks with the largest alignment gap.",
        },
        "prompt_routing": {
            "role": "boundary",
            "explains": "Whether routing-specific evidence was recorded.",
            "does_not_prove": "Without an intervention, it does not prove a routing mechanism.",
            "next_action": "Add a controlled routing intervention if routing is material.",
        },
        "prompt_projection": {
            "role": "boundary",
            "explains": "Whether soft-to-hard prompt projection is applicable and measured.",
            "does_not_prove": "A not-applicable result says nothing about other deployment paths.",
            "next_action": "Run projection diagnostics only for soft-prompt deployment.",
        },
        "prompt_stability": {
            "role": "stability",
            "explains": "How consistent the observed prompt-conditioned trajectory is.",
            "does_not_prove": "It is not a global model stability guarantee.",
            "next_action": "Compare matched seeds and heterogeneous task slices.",
        },
    }
    chinese: dict[str, JsonDict] = {
        "prompt_reachability": {
            "role": "mechanism",
            "explains": "不同运行中, Prompt 条件表示的可达范围如何变化。",
            "does_not_prove": "它不能证明唯一的因果表示路径。",
            "next_action": "比较配对 checkpoint 与多个 seed。",
        },
        "readout_alignment": {
            "role": "mechanism",
            "explains": "已记录 readout 与自由生成答案的对齐程度。",
            "does_not_prove": "它不能识别唯一的隐藏机制。",
            "next_action": "检查 alignment gap 最大的任务。",
        },
        "prompt_routing": {
            "role": "boundary",
            "explains": "是否记录了与 Prompt 路由直接相关的证据。",
            "does_not_prove": "没有受控干预时, 不能证明存在特定路由机制。",
            "next_action": "如果路由很重要, 应增加受控路由干预。",
        },
        "prompt_projection": {
            "role": "boundary",
            "explains": "soft-to-hard Prompt 投影是否适用并被测量。",
            "does_not_prove": "不适用结果不能说明其他部署路径的风险。",
            "next_action": "仅在部署 soft prompt 时运行投影诊断。",
        },
        "prompt_stability": {
            "role": "stability",
            "explains": "观测到的 Prompt 条件轨迹是否一致。",
            "does_not_prove": "它不是模型全局稳定性保证。",
            "next_action": "比较多个匹配 seed 和异质任务切片。",
        },
    }
    return (english if language == "en" else chinese)[name]


def evidence_matrix_rows(detail: JsonDict) -> list[JsonDict]:
    """Normalize evidence availability and interpretation roles."""

    matrix_value = detail.get("evidence_matrix")
    matrix = matrix_value if isinstance(matrix_value, dict) else {}
    diagnostics = matrix.get("diagnostics")
    if not isinstance(diagnostics, list):
        return []
    rows: list[JsonDict] = []
    for raw in diagnostics:
        if not isinstance(raw, dict):
            continue
        item = cast(JsonDict, raw)
        rows.append(
            {
                "adapter": item.get("adapter"),
                "status": item.get("support_status"),
                "role": item.get("interpretation_role"),
                "confidence": item.get("confidence"),
                "sources": item.get("source_count"),
                "next_action": item.get("next_action"),
            }
        )
    return rows


def redact_for_display(value: Any) -> Any:
    """Return a recursively redacted value suitable for local UI rendering."""

    if isinstance(value, Mapping):
        result: JsonDict = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
            if normalized in _HIDDEN_DISPLAY_KEYS:
                result[key] = REDACTED
                continue
            if (
                normalized == "authorization"
                and isinstance(item, str)
                and item.lower() in _SAFE_AUTHORIZATION_VALUES
            ):
                result[key] = item
                continue
            key_probe = redact_sensitive({key: "display-safe-probe"})
            result[key] = (
                REDACTED
                if key_probe.get(key) == REDACTED
                else redact_for_display(item)
            )
        return result
    if isinstance(value, list | tuple):
        return [redact_for_display(item) for item in value]
    return redact_sensitive(value)


def safe_display_text(value: object) -> str:
    """Serialize a value after applying the UI's display redaction policy."""

    safe = redact_for_display(value)
    if isinstance(safe, str):
        return safe
    return json.dumps(safe, ensure_ascii=False, sort_keys=True, default=str)


def load_jsonl_safe(path: Path) -> list[JsonDict]:
    """Load object records from JSONL, skipping malformed lines and sorting by sequence."""

    if not path.exists():
        return []
    records: list[tuple[int, JsonDict]] = []
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError):
        return []
    for line_number, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(value, dict):
            records.append((line_number, cast(JsonDict, redact_for_display(value))))
    records.sort(key=lambda item: (_event_sequence(item[1]), item[0]))
    return [record for _, record in records]


def deepseek_harness_view(detail: JsonDict) -> JsonDict:
    """Derive a bounded, display-safe DeepSeek Harness view from control artifacts."""

    safe = cast(JsonDict, redact_for_display(detail))
    control_run = _mapping(safe.get("control_run"))
    metadata = _mapping(control_run.get("metadata"))
    events = sorted(_mapping_rows(safe.get("events")), key=_event_sequence)
    preflight = _mapping(safe.get("preflight"))
    provider_result = _mapping(safe.get("provider_result"))
    stability = _mapping(safe.get("stability"))
    attribution = _mapping(safe.get("attribution"))
    decision = _mapping(safe.get("decision"))
    audit = _mapping(safe.get("audit") or safe.get("audit_result"))
    return {
        "identity": {
            "run_id": _text(control_run.get("run_id")),
            "session_id": _text(metadata.get("harness_session_id") or metadata.get("session_id")),
            "status": _text(control_run.get("status")) or "unknown",
            "authorization": _text(control_run.get("authorization")) or "unknown",
            "agent": _text(control_run.get("agent")) or "unknown",
        },
        "timeline": _timeline_rows(events),
        "gates": _gate_rows(preflight, events),
        "provider": _provider_view(control_run, provider_result, events),
        "usage": _usage_view(provider_result, events),
        "repeated_tool_calls": _repeated_tool_rows(events, stability),
        "stability": _stability_view(stability),
        "attribution": {
            "status": _text(attribution.get("status")) or "insufficient_evidence",
            "summary": safe_display_text(attribution.get("summary") or ""),
            "factors": _mapping_rows(attribution.get("factors")),
        },
        "changes": _change_rows(events, audit),
        "guard_signals": _guard_signal_rows(events, stability),
        "recommendation": _recommendation_view(decision, preflight),
        "report_links": _report_link_rows(safe),
    }


def _read_control_json(path: Path) -> JsonDict:
    """Read control json data without exposing unsafe content."""
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return {}
    if not isinstance(value, dict):
        return {}
    return cast(JsonDict, redact_for_display(value))


def _event_sequence(event: JsonDict) -> int:
    """Normalize event sequence values for dashboard use."""
    value = event.get("sequence")
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return 2**63 - 1


def _mapping_rows(value: object) -> list[JsonDict]:
    """Normalize mapping rows values for dashboard use."""
    if not isinstance(value, list):
        return []
    return [_mapping(item) for item in value if isinstance(item, Mapping)]


def _text(value: object) -> str:
    """Normalize text values for dashboard use."""
    if value is None:
        return ""
    return safe_display_text(value) if isinstance(value, str) else str(value)


def _number(value: object) -> int | float | None:
    """Normalize number values for dashboard use."""
    if isinstance(value, int | float) and not isinstance(value, bool):
        return value
    return None


def _timeline_rows(events: list[JsonDict]) -> list[JsonDict]:
    """Normalize timeline rows values for dashboard use."""
    rows: list[JsonDict] = []
    for event in events:
        payload = _mapping(event.get("payload"))
        event_type = _text(event.get("event_type")) or "unknown"
        lowered = event_type.lower()
        phase = "event"
        if "session" in lowered:
            phase = "session"
        elif "turn" in lowered:
            phase = "turn"
        elif "preflight" in lowered:
            phase = "prompt gate"
        elif "tool" in lowered:
            phase = "tool"
        elif "test" in lowered:
            phase = "test"
        elif "guard" in lowered:
            phase = "guard"
        elif "agent" in lowered or "provider" in lowered:
            phase = "provider"
        turn = payload.get("turn", payload.get("turn_index", payload.get("turn_id")))
        rows.append(
            {
                "sequence": _event_sequence(event),
                "timestamp": _text(event.get("timestamp")),
                "phase": phase,
                "event": event_type,
                "turn": turn,
                "subject": _tool_name(payload)
                or _text(payload.get("model") or payload.get("agent")),
                "status": _text(
                    payload.get("decision")
                    or payload.get("status")
                    or payload.get("outcome")
                    or payload.get("risk_level")
                ),
            }
        )
    return rows


def _gate_rows(preflight: JsonDict, events: list[JsonDict]) -> list[JsonDict]:
    """Normalize gate rows values for dashboard use."""
    rows: list[JsonDict] = []
    preflight_event = next(
        (
            event
            for event in events
            if "preflight" in _text(event.get("event_type")).lower()
        ),
        {},
    )
    if preflight:
        rows.append(
            {
                "sequence": _event_sequence(preflight_event) if preflight_event else None,
                "scope": "prompt",
                "subject": "prompt hash",
                "decision": _text(preflight.get("decision")) or "unknown",
                "risk": _text(preflight.get("risk_level")) or "unknown",
                "review_required": preflight.get("required_review"),
            }
        )
    elif preflight_event:
        payload = _mapping(preflight_event.get("payload"))
        rows.append(
            {
                "sequence": _event_sequence(preflight_event),
                "scope": "prompt",
                "subject": "prompt hash",
                "decision": _text(payload.get("decision")) or "unknown",
                "risk": _text(payload.get("risk_level")) or "unknown",
                "review_required": payload.get("required_review"),
            }
        )
    for event in events:
        event_type = _text(event.get("event_type")).lower()
        if "tools/pre-execute" not in event_type and not event_type.endswith("tool/request"):
            continue
        payload = _mapping(event.get("payload"))
        rows.append(
            {
                "sequence": _event_sequence(event),
                "scope": "tool",
                "subject": _tool_name(payload) or "unknown tool",
                "decision": _text(payload.get("decision") or payload.get("action")) or "recorded",
                "risk": _text(payload.get("risk_level")) or "unknown",
                "review_required": payload.get("required_review"),
            }
        )
    return rows


def _provider_view(
    control_run: JsonDict,
    provider_result: JsonDict,
    events: list[JsonDict],
) -> JsonDict:
    """Normalize provider view values for dashboard use."""
    response_payload: JsonDict = {}
    for event in events:
        if _text(event.get("event_type")).lower().endswith("agent/response"):
            response_payload = _mapping(event.get("payload"))
    provenance = []
    for item in _mapping_rows(provider_result.get("provenance_evidence")):
        provenance.append(
            {
                key: item.get(key)
                for key in ("type", "source", "confidence", "model_id")
                if item.get(key) is not None
            }
        )
    return {
        "provider": _text(
            provider_result.get("provider")
            or response_payload.get("provider")
            or control_run.get("provider")
        ),
        "requested_model": _text(
            provider_result.get("requested_model") or control_run.get("model")
        ),
        "observed_model": _text(
            provider_result.get("model_id")
            or response_payload.get("model")
            or control_run.get("model")
        ),
        "request_id": _text(
            provider_result.get("request_id") or response_payload.get("request_id")
        ),
        "provenance": provenance,
        "warnings": [safe_display_text(item) for item in provider_result.get("warnings", [])]
        if isinstance(provider_result.get("warnings"), list)
        else [],
    }


def _usage_view(provider_result: JsonDict, events: list[JsonDict]) -> JsonDict:
    """Normalize usage view values for dashboard use."""
    usage = _mapping(provider_result.get("usage"))
    response_payload: JsonDict = {}
    for event in events:
        if _text(event.get("event_type")).lower().endswith("agent/response"):
            response_payload = _mapping(event.get("payload"))
    event_usage = _mapping(response_payload.get("usage"))
    return {
        "input_tokens": _number(usage.get("input_tokens"))
        or _number(event_usage.get("input_tokens")),
        "output_tokens": _number(usage.get("output_tokens"))
        or _number(event_usage.get("output_tokens")),
        "total_tokens": _number(usage.get("total_tokens"))
        or _number(event_usage.get("total_tokens"))
        or _find_numeric(response_payload, ("total_tokens", "token_count")),
        "cached_tokens": _number(usage.get("cached_tokens"))
        or _number(event_usage.get("cached_tokens")),
        "reasoning_tokens": _number(usage.get("reasoning_tokens"))
        or _number(event_usage.get("reasoning_tokens")),
        "cost": _find_numeric(provider_result, ("cost", "cost_usd", "estimated_cost"))
        or _find_numeric(response_payload, ("cost", "cost_usd", "estimated_cost")),
        "latency_ms": _number(provider_result.get("latency_ms"))
        or _find_numeric(response_payload, ("latency_ms", "duration_ms", "elapsed_ms")),
    }


def _find_numeric(value: Mapping[str, object], keys: tuple[str, ...]) -> int | float | None:
    """Normalize find numeric values for dashboard use."""
    for key in keys:
        number = _number(value.get(key))
        if number is not None:
            return number
    for nested_key in ("usage", "metrics", "result", "metadata", "raw_metadata"):
        nested = value.get(nested_key)
        if isinstance(nested, Mapping):
            found = _find_numeric({str(key): item for key, item in nested.items()}, keys)
            if found is not None:
                return found
    return None


def _tool_name(payload: JsonDict) -> str:
    """Normalize tool name values for dashboard use."""
    for key in ("tool", "tool_name", "name"):
        value = payload.get(key)
        if isinstance(value, str):
            return safe_display_text(value)
        if isinstance(value, Mapping) and isinstance(value.get("name"), str):
            return safe_display_text(value["name"])
    return ""


def _repeated_tool_rows(events: list[JsonDict], stability: JsonDict) -> list[JsonDict]:
    """Normalize repeated tool rows values for dashboard use."""
    observations: list[tuple[str, str, int]] = []
    for event in events:
        event_type = _text(event.get("event_type")).lower()
        if not (
            "tools/pre-execute" in event_type
            or event_type.endswith("tool/call")
            or event_type.endswith("tool/request")
        ):
            continue
        payload = _mapping(event.get("payload"))
        tool = _tool_name(payload)
        if not tool:
            continue
        arguments = payload.get("arguments", payload.get("input", payload.get("args", {})))
        signature = safe_display_text(arguments)
        observations.append((tool, signature, _event_sequence(event)))
    rows: list[JsonDict] = []
    index = 0
    while index < len(observations):
        tool, signature, start_sequence = observations[index]
        end = index + 1
        while end < len(observations) and observations[end][:2] == (tool, signature):
            end += 1
        count = end - index
        if count >= 2:
            rows.append(
                {
                    "tool": tool,
                    "count": count,
                    "start_sequence": start_sequence,
                    "end_sequence": observations[end - 1][2],
                    "same_arguments": True,
                }
            )
        index = end
    if rows:
        return rows
    signals = _mapping(stability.get("signals"))
    repeated = _mapping(signals.get("repeated_tool_calls"))
    max_repetitions = repeated.get("max_repetitions")
    if (
        isinstance(max_repetitions, int)
        and not isinstance(max_repetitions, bool)
        and max_repetitions >= 2
    ):
        return [
            {
                "tool": _text(repeated.get("tool")) or "unknown tool",
                "count": max_repetitions,
                "start_sequence": None,
                "end_sequence": None,
                "same_arguments": True,
            }
        ]
    return []


def _stability_view(stability: JsonDict) -> JsonDict:
    """Normalize stability view values for dashboard use."""
    signals = _mapping(stability.get("signals"))
    repeated = _mapping(signals.get("repeated_tool_calls"))
    failures = _mapping(signals.get("request_failures"))
    churn = _mapping(signals.get("file_churn"))
    tests = _mapping(signals.get("test_trend"))
    progress = _mapping(signals.get("progress"))
    return {
        "state": _text(stability.get("state")) or "insufficient_evidence",
        "summary": safe_display_text(stability.get("summary") or ""),
        "confidence": _text(signals.get("confidence")) or "unknown",
        "observed_events": signals.get("observed_events", 0),
        "signal_counts": [
            {"signal": "repeated calls", "value": repeated.get("max_repetitions", 0)},
            {"signal": "request errors", "value": failures.get("errors", 0)},
            {"signal": "request retries", "value": failures.get("retries", 0)},
            {"signal": "file edits", "value": churn.get("max_edits_per_file", 0)},
            {"signal": "test transitions", "value": tests.get("transitions", 0)},
            {"signal": "completed markers", "value": progress.get("completed_markers", 0)},
        ],
    }


def _change_rows(events: list[JsonDict], audit: JsonDict) -> list[JsonDict]:
    """Normalize change rows values for dashboard use."""
    file_counts: Counter[str] = Counter()
    tests: list[JsonDict] = []
    for event in events:
        event_type = _text(event.get("event_type")).lower()
        payload = _mapping(event.get("payload"))
        tool = _tool_name(payload).lower()
        if any(marker in event_type or marker in tool for marker in ("edit", "write", "patch")):
            file_counts.update(_paths(payload))
        if "test" in event_type or any(marker in tool for marker in ("pytest", "test")):
            passed = payload.get("passed", payload.get("tests_passed"))
            status = "pass" if passed is True else "fail" if passed is False else _text(
                payload.get("status") or payload.get("outcome")
            ) or "recorded"
            tests.append(
                {
                    "kind": "test",
                    "item": _tool_name(payload) or "recorded test",
                    "status": status,
                    "count": 1,
                    "sequence": _event_sequence(event),
                }
            )
    for key in ("changed_files", "touched_files"):
        value = audit.get(key)
        if isinstance(value, list):
            file_counts.update(safe_display_text(item) for item in value if isinstance(item, str))
    audit_tests = audit.get("tests_run")
    if isinstance(audit_tests, list):
        audit_status = audit.get("tests_passed")
        for name in audit_tests:
            if isinstance(name, str):
                tests.append(
                    {
                        "kind": "test",
                        "item": safe_display_text(name),
                        "status": "pass" if audit_status is True else "fail"
                        if audit_status is False
                        else "recorded",
                        "count": 1,
                        "sequence": None,
                    }
                )
    files = [
        {"kind": "file", "item": path, "status": "changed", "count": count, "sequence": None}
        for path, count in sorted(file_counts.items())
    ]
    return [*files, *tests]


def _paths(payload: JsonDict) -> list[str]:
    """Normalize paths values for dashboard use."""
    paths: set[str] = set()
    containers = [payload]
    for key in ("arguments", "input", "result"):
        nested = payload.get(key)
        if isinstance(nested, Mapping):
            containers.append(_mapping(nested))
    for container in containers:
        for key in ("path", "file", "file_path", "files", "changed_files", "touched_files"):
            value = container.get(key)
            if isinstance(value, str):
                paths.add(safe_display_text(value))
            elif isinstance(value, list):
                paths.update(safe_display_text(item) for item in value if isinstance(item, str))
    return sorted(paths)


def _guard_signal_rows(events: list[JsonDict], stability: JsonDict) -> list[JsonDict]:
    """Normalize guard signal rows values for dashboard use."""
    rows: list[JsonDict] = []
    signals = _mapping(stability.get("signals"))
    for item in _mapping_rows(signals.get("harness_guard_signals")):
        rows.append(
            {
                "kind": _text(item.get("kind")) or "guard",
                "source": _text(item.get("source")) or "harness",
                "sequence": item.get("sequence"),
            }
        )
    for event in events:
        payload = _mapping(event.get("payload"))
        source = _text(payload.get("guard") or payload.get("source"))
        combined = " ".join((_text(event.get("event_type")), source)).lower()
        kind = "repeat_tool" if "repeat-tool" in combined or "repeat_tool" in combined else (
            "timeout" if "timeout" in combined else ""
        )
        if kind:
            rows.append(
                {"kind": kind, "source": source or "harness", "sequence": _event_sequence(event)}
            )
    unique: dict[tuple[object, object, object], JsonDict] = {}
    for row in rows:
        unique[(row.get("kind"), row.get("source"), row.get("sequence"))] = row
    return sorted(unique.values(), key=lambda row: int(row.get("sequence") or 0))


def _recommendation_view(decision: JsonDict, preflight: JsonDict) -> JsonDict:
    """Normalize recommendation view values for dashboard use."""
    if decision:
        reasons = decision.get("reasons")
        return {
            "decision": _text(decision.get("decision")) or "insufficient_evidence",
            "next_action": safe_display_text(decision.get("next_action") or ""),
            "reasons": [safe_display_text(item) for item in reasons]
            if isinstance(reasons, list)
            else [],
            "boundary": (
                "Recommendation based on recorded observable evidence; it does not prove "
                "causality or safety."
            ),
        }
    return {
        "decision": _text(preflight.get("decision")) or "insufficient_evidence",
        "next_action": "Complete the run before relying on a final recommendation.",
        "reasons": [safe_display_text(preflight.get("summary"))]
        if preflight.get("summary")
        else [],
        "boundary": (
            "Recommendation based on recorded observable evidence; it does not prove "
            "causality or safety."
        ),
    }


def _report_link_rows(detail: JsonDict) -> list[JsonDict]:
    """Normalize report link rows values for dashboard use."""
    raw_path = detail.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        return []
    run_dir = Path(raw_path)
    names = (
        "report.html",
        "report.md",
        "audit_result.json",
        "evidence_card.html",
        "claim_check.html",
        "research_case_study.html",
        "research_bundle.html",
    )
    rows: list[JsonDict] = []
    for name in names:
        path = run_dir / name
        if path.is_file():
            resolved = path.resolve()
            rows.append(
                {
                    "name": name,
                    "path": str(resolved),
                    "href": resolved.as_uri(),
                }
            )
    return rows
