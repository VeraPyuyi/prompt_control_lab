"""Deterministic attribution, stability, and control-decision diagnostics.

The functions in this module operate only on recorded, observable metadata and
events. They identify associations and comparison validity risks; they do not
claim causal attribution or infer hidden model state.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from itertools import pairwise
from typing import cast

from promptcontrollab.control_protocol import (
    AttributionReport,
    ControlDecision,
    PreflightDecision,
    StabilityReport,
)
from promptcontrollab.files import JsonDict

_MISSING = object()
_MAX_EVIDENCE = 8
_THRESHOLDS: JsonDict = {
    "repeated_tool_calls": 3,
    "request_errors": 3,
    "request_retries": 2,
    "file_edits_per_path": 3,
    "test_transitions": 2,
    "growth_ratio": 2.0,
    "token_growth_ratio": 2.0,
    "context_growth_ratio": 2.0,
    "high_confidence_events": 6,
}
_FACTOR_IMPACT = {
    "prompt": "medium",
    "model": "high",
    "api_parameters": "medium",
    "data_split": "high",
    "tools": "medium",
    "policy": "high",
    "agent": "medium",
    "git_commit": "medium",
    "tests": "medium",
    "seed": "low",
}
_HARNESS_GUARD_KINDS = {
    "repeat_tool_reminder": "repeat_tool",
    "tool_timeout": "timeout",
}


@dataclass(frozen=True)
class _Observed:
    value: object = _MISSING
    source: str = "missing"
    confidence: str = "low"

    @property
    def known(self) -> bool:
        return self.value is not _MISSING


def analyze_attribution(
    run: object,
    events: object,
    *,
    baseline_run: object | None = None,
    baseline_artifacts: Mapping[str, object] | None = None,
) -> AttributionReport:
    """Compare recorded run factors without making causal claims."""

    current_run = _as_dict(run)
    current_events = _normalize_events(events)
    baseline = _baseline_dict(baseline_run, baseline_artifacts)
    baseline_events = _normalize_events(
        baseline_artifacts.get("events", []) if baseline_artifacts else []
    )
    run_id = _run_id(current_run)
    factors: list[JsonDict] = []
    for factor in _FACTOR_IMPACT:
        current_value = _observe_factor(factor, current_run, current_events)
        baseline_value = _observe_factor(factor, baseline, baseline_events)
        factors.append(_compare_factor(factor, current_value, baseline_value))

    changed_count = sum(item["changed"] is True for item in factors)
    unknown_count = sum(item["changed"] == "unknown" for item in factors)
    if changed_count:
        status = "changes_observed"
        summary = (
            f"Observed differences in {changed_count} of {len(factors)} recorded factors. "
            "These associations identify comparison confounders; this evidence does not "
            "establish causation."
        )
    elif unknown_count:
        status = "insufficient_evidence"
        summary = (
            f"{unknown_count} of {len(factors)} factors could not be compared from the "
            "available artifacts. Missing evidence does not establish equivalence or causation."
        )
    else:
        status = "no_changes_observed"
        summary = (
            "No differences were observed in the recorded comparison factors. This does not "
            "establish causation or prove that unrecorded conditions were identical."
        )
    return AttributionReport(run_id=run_id, status=status, factors=factors, summary=summary)


def analyze_stability(run: object, events: object) -> StabilityReport:
    """Classify observable run behavior using bounded, deterministic heuristics."""

    run_id = _run_id(_as_dict(run))
    normalized = _normalize_events(events)
    tool_names, tool_signatures = _tool_observations(normalized)
    repeated_tool, max_tool_repetitions = _max_consecutive(tool_signatures)
    errors, retries = _request_failures(normalized)
    file_counts = _file_edit_counts(normalized)
    max_file_edits = max(file_counts.values(), default=0)
    tests = _test_outcomes(normalized)
    transitions = sum(left != right for left, right in pairwise(tests))
    tokens = _numeric_series(normalized, ("total_tokens", "token_count"))
    context = _numeric_series(
        normalized,
        ("context_tokens", "input_tokens", "prompt_tokens", "context_length"),
    )
    latency = _numeric_series(normalized, ("latency_ms", "duration_ms", "elapsed_ms"))
    costs = _numeric_series(normalized, ("cost", "cost_usd", "estimated_cost"))
    progress = _progress_markers(normalized, tests)
    token_growth = _growth_signal(tokens)
    context_growth = _growth_signal(context)
    latest_completion = _latest_completion_sequence(normalized)
    latest_adverse = _latest_adverse_sequence(
        normalized,
        token_growth=token_growth,
        context_growth=context_growth,
    )
    guard_signals = _harness_guard_signals(normalized)
    safety_signals = _safety_signals(normalized)
    meaningful_events = _meaningful_event_count(normalized)
    confidence = _stability_confidence(meaningful_events, guard_signals)

    signals: JsonDict = {
        "observed_events": len(normalized),
        "meaningful_events": meaningful_events,
        "repeated_tool_calls": {
            "tool": repeated_tool,
            "max_repetitions": max_tool_repetitions,
            "observed_tools": tool_names[:_MAX_EVIDENCE],
        },
        "request_failures": {"errors": errors, "retries": retries},
        "file_churn": {
            "max_edits_per_file": max_file_edits,
            "files": [
                {"path": path, "edits": count}
                for path, count in sorted(
                    file_counts.items(), key=lambda item: (-item[1], item[0])
                )[:_MAX_EVIDENCE]
            ],
        },
        "test_trend": {
            "outcomes": tests[:_MAX_EVIDENCE],
            "transitions": transitions,
            "final": tests[-1] if tests else "unknown",
        },
        "token_growth": token_growth,
        "context_growth": context_growth,
        "latency_growth": _growth_signal(latency),
        "cost_growth": _growth_signal(costs),
        "progress": {
            "completed_markers": progress,
            "latest_completion_sequence": latest_completion,
            "latest_adverse_sequence": latest_adverse,
            "completion_is_current": latest_completion is not None
            and (latest_adverse is None or latest_completion >= latest_adverse),
        },
        "harness_guard_signals": guard_signals,
        "safety_signals": safety_signals,
        "confidence": confidence,
        "thresholds": dict(_THRESHOLDS),
    }
    state = _classify_stability(signals)
    return StabilityReport(
        run_id=run_id,
        state=state,
        signals=signals,
        summary=_stability_summary(state, confidence),
    )


def make_control_decision(
    run: object,
    *,
    preflight: object | None = None,
    attribution: object | None = None,
    stability: object | None = None,
    events: object = (),
) -> ControlDecision:
    """Combine preflight and observable diagnostics into a conservative action."""

    run_data = _as_dict(run)
    run_id = _run_id(run_data)
    preflight_data = _as_dict(preflight)
    attribution_data = _as_dict(attribution)
    stability_data = _as_dict(stability)
    normalized_events = _normalize_events(events)
    denied_tools = _denied_tools(normalized_events)
    preflight_decision = _lower_string(preflight_data.get("decision"))
    risk_level = _lower_string(preflight_data.get("risk_level"))
    required_review_value = preflight_data.get("required_review")
    required_review = required_review_value is True
    preflight_summary = _safe_summary(preflight_data.get("summary"))

    if preflight_decision in {"block", "blocked", "deny", "denied"} or risk_level == "high":
        reasons = [preflight_summary or "The preflight result is high risk or blocked."]
        return ControlDecision(
            run_id=run_id,
            decision="block",
            next_action="Revise the request or obtain explicit approval before execution.",
            reasons=reasons,
        )
    if denied_tools:
        return ControlDecision(
            run_id=run_id,
            decision="block",
            next_action="Do not execute the denied tool; revise the request or policy scope.",
            reasons=[f"Tool execution was denied: {', '.join(denied_tools)}."],
        )
    if required_review:
        return ControlDecision(
            run_id=run_id,
            decision="needs_review",
            next_action="Complete the required human review before model or tool execution.",
            reasons=[preflight_summary or "The preflight policy requires human review."],
        )
    if risk_level == "medium":
        return ControlDecision(
            run_id=run_id,
            decision="needs_review",
            next_action="Review the medium-risk preflight evidence before execution.",
            reasons=[preflight_summary or "The preflight risk level is medium."],
        )

    state = _lower_string(stability_data.get("state")) or "insufficient_evidence"
    stability_signals = _as_dict(stability_data.get("signals"))
    stability_confidence = _lower_string(stability_signals.get("confidence"))
    safety_signals = stability_signals.get("safety_signals")
    has_safety_signals = isinstance(safety_signals, list) and bool(safety_signals)
    if state == "diverging" and stability_confidence == "high" and has_safety_signals:
        return ControlDecision(
            run_id=run_id,
            decision="block",
            next_action="Stop the run and inspect the recorded safety and divergence evidence.",
            reasons=["High-confidence divergence coincides with recorded safety signals."],
        )
    if state == "diverging":
        return ControlDecision(
            run_id=run_id,
            decision="needs_review",
            next_action="Pause execution and review errors, growth, churn, and test evidence.",
            reasons=["Observable run signals are classified as diverging."],
        )
    if has_safety_signals:
        return ControlDecision(
            run_id=run_id,
            decision="needs_review",
            next_action="Review the recorded safety evidence before continuing.",
            reasons=["Observable safety signals require human review."],
        )

    high_impact_changes = _high_impact_changes(attribution_data)
    if high_impact_changes:
        return ControlDecision(
            run_id=run_id,
            decision="needs_review",
            next_action="Review comparison validity before attributing the observed outcome.",
            reasons=[
                "High-impact recorded factors changed: " + ", ".join(high_impact_changes) + "."
            ],
        )
    if state in {"stalled", "oscillating"}:
        return ControlDecision(
            run_id=run_id,
            decision="suggest",
            next_action="Inspect the stability evidence and adjust the prompt, tools, or limits.",
            reasons=[f"Observable run signals are classified as {state}."],
        )
    if state == "converging":
        explicit_safe_preflight = (
            preflight_decision == "allow"
            and risk_level == "low"
            and required_review_value is False
        )
        adequate_stability = stability_confidence in {"medium", "high"}
        explicit_no_safety_signals = isinstance(safety_signals, list) and not safety_signals
        complete_preflight = _complete_safe_preflight(preflight_data, run_data)
        complete_attribution = _complete_attribution_evidence(attribution_data, run_id)
        complete_stability = _complete_stability_evidence(stability_data, run_id)
        if (
            explicit_safe_preflight
            and adequate_stability
            and explicit_no_safety_signals
            and complete_preflight
            and complete_attribution
            and complete_stability
        ):
            return ControlDecision(
                run_id=run_id,
                decision="allow",
                next_action="Continue under the current authorization and policy scope.",
                reasons=["Observable progress and test signals are consistent with convergence."],
            )
        return ControlDecision(
            run_id=run_id,
            decision="suggest",
            next_action="Complete the missing preflight or stability evidence before execution.",
            reasons=["The evidence required for an explicit allow decision is incomplete."],
        )
    return ControlDecision(
        run_id=run_id,
        decision="suggest",
        next_action="Collect more execution evidence before making a stronger decision.",
        reasons=["There is insufficient observable evidence for a stability conclusion."],
    )


def _as_dict(value: object) -> JsonDict:
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    to_json = getattr(value, "to_json", None)
    if callable(to_json):
        try:
            converted = to_json()
        except (AttributeError, TypeError, ValueError):
            return {}
        if isinstance(converted, Mapping):
            return {str(key): item for key, item in converted.items()}
    return {}


def _run_id(run: JsonDict) -> str:
    value = run.get("run_id")
    return value if isinstance(value, str) and value else "unknown"


def _normalize_events(events: object) -> list[JsonDict]:
    if isinstance(events, (str, bytes, Mapping)) or events is None:
        return []
    if not isinstance(events, Iterable):
        return []
    normalized: list[tuple[int, int, JsonDict]] = []
    for position, raw in enumerate(events):
        event = _as_dict(raw)
        event_type = event.get("event_type")
        payload = event.get("payload", {})
        if not isinstance(event_type, str) or not isinstance(payload, Mapping):
            continue
        sequence = event.get("sequence")
        order = (
            sequence
            if isinstance(sequence, int) and not isinstance(sequence, bool)
            else position + 1
        )
        normalized.append(
            (
                order,
                position,
                {
                    "sequence": order,
                    "event_type": event_type,
                    "payload": {str(key): item for key, item in payload.items()},
                },
            )
        )
    return [item[2] for item in sorted(normalized, key=lambda item: (item[0], item[1]))]


def _baseline_dict(
    baseline_run: object | None,
    baseline_artifacts: Mapping[str, object] | None,
) -> JsonDict:
    combined: JsonDict = {}
    metadata: JsonDict = {}
    if baseline_artifacts:
        for name in ("manifest", "agent_run", "audit_result", "control_run", "run"):
            artifact = _as_dict(baseline_artifacts.get(name))
            if not artifact:
                continue
            combined[name] = artifact
            for key, value in artifact.items():
                combined.setdefault(key, value)
                metadata.setdefault(key, value)
            artifact_metadata = artifact.get("metadata")
            if isinstance(artifact_metadata, Mapping):
                for key, value in artifact_metadata.items():
                    metadata.setdefault(str(key), value)
    direct = _as_dict(baseline_run)
    direct_metadata = direct.get("metadata")
    if isinstance(direct_metadata, Mapping):
        metadata.update({str(key): value for key, value in direct_metadata.items()})
    combined.update(direct)
    if metadata:
        combined["metadata"] = metadata
    return combined


def _observe_factor(
    factor: str,
    run: JsonDict,
    events: list[JsonDict],
) -> _Observed:
    observers = {
        "prompt": _observe_prompt,
        "model": _observe_model,
        "api_parameters": _observe_api_parameters,
        "data_split": _observe_data_split,
        "tools": _observe_tools,
        "policy": _observe_policy,
        "agent": _observe_agent,
        "git_commit": _observe_git_commit,
        "tests": _observe_tests,
        "seed": _observe_seed,
    }
    return observers[factor](run, events)


def _compare_factor(factor: str, current: _Observed, baseline: _Observed) -> JsonDict:
    if not current.known or not baseline.known:
        missing = []
        if not current.known:
            missing.append("current")
        if not baseline.known:
            missing.append("baseline")
        return {
            "factor": factor,
            "changed": "unknown",
            "impact": "unknown",
            "confidence": "low",
            "evidence": [f"Missing {', '.join(missing)} evidence for {factor}."],
            "summary": f"Whether {factor} changed is unknown from the recorded artifacts.",
        }
    changed = current.value != baseline.value
    confidence = _minimum_confidence(current.confidence, baseline.confidence)
    evidence = [
        f"Current {factor} ({current.source}): {_display(current.value)}",
        f"Baseline {factor} ({baseline.source}): {_display(baseline.value)}",
    ]
    if changed:
        summary = f"Recorded {factor} values differ; this is a confounder, not a causal claim."
        impact = _FACTOR_IMPACT[factor]
    else:
        summary = f"No difference was observed in the recorded {factor} values."
        impact = "low"
    return {
        "factor": factor,
        "changed": changed,
        "impact": impact,
        "confidence": confidence,
        "evidence": evidence,
        "summary": summary,
    }


def _observe_prompt(run: JsonDict, events: list[JsonDict]) -> _Observed:
    del events
    return _first_path(
        run,
        ("prompt_hash",),
        ("prompt", "prompt_hash"),
        ("prompt", "hash"),
        ("metadata", "prompt_hash"),
        ("metadata", "prompt", "prompt_hash"),
    )


def _observe_model(run: JsonDict, events: list[JsonDict]) -> _Observed:
    provider = _first_path(run, ("provider",), ("metadata", "provider"))
    model = _first_path(run, ("model",), ("model_id",), ("metadata", "model"))
    source = "run metadata"
    confidence = "high"
    if not provider.known or not model.known:
        for event in reversed(events):
            if event["event_type"] != "agent/request":
                continue
            payload = cast(JsonDict, event["payload"])
            if not provider.known:
                provider = _first_path(payload, ("provider",))
            if not model.known:
                model = _first_path(payload, ("model",), ("model_id",))
            source = "agent/request event"
            confidence = "medium"
            break
    if not provider.known or not model.known:
        return _Observed()
    return _Observed(
        {"provider": provider.value, "model": model.value},
        source,
        confidence,
    )


def _observe_api_parameters(run: JsonDict, events: list[JsonDict]) -> _Observed:
    direct = _first_path(
        run,
        ("api_params",),
        ("api_parameters",),
        ("metadata", "api_params"),
        ("metadata", "api_parameters"),
        ("metadata", "request", "parameters"),
    )
    if direct.known and isinstance(direct.value, Mapping):
        return direct
    for event in reversed(events):
        if event["event_type"] == "agent/request":
            payload = cast(JsonDict, event["payload"])
            observed = _first_path(payload, ("api_params",), ("parameters",))
            if observed.known and isinstance(observed.value, Mapping):
                return _Observed(observed.value, "agent/request event", "medium")
    return _Observed()


def _observe_data_split(run: JsonDict, events: list[JsonDict]) -> _Observed:
    del events
    data = _first_path(
        run,
        ("data",),
        ("dataset",),
        ("data_path",),
        ("metadata", "data"),
        ("metadata", "dataset"),
        ("metadata", "data_path"),
    )
    split = _first_path(
        run,
        ("split",),
        ("split_hash",),
        ("metadata", "split"),
        ("metadata", "split_hash"),
    )
    if not data.known or not split.known:
        return _Observed()
    return _Observed(
        {
            "data": data.value,
            "split": split.value,
        },
        "run metadata",
        "high",
    )


def _observe_tools(run: JsonDict, events: list[JsonDict]) -> _Observed:
    direct = _first_path(run, ("tools",), ("metadata", "tools"), ("metadata", "tool_names"))
    if direct.known and isinstance(direct.value, list) and not direct.value:
        return _Observed([], "run metadata", "high")
    direct_tools = _string_values(direct.value) if direct.known else []
    event_tools, _ = _tool_observations(events)
    tools = sorted(set(direct_tools or event_tools))
    if not tools:
        return _Observed()
    if direct_tools:
        return _Observed(tools, "run metadata", "high")
    return _Observed(tools, "tool events", "medium")


def _observe_policy(run: JsonDict, events: list[JsonDict]) -> _Observed:
    del events
    return _first_path(
        run,
        ("policy_hash",),
        ("policy", "sha256"),
        ("policy", "hash"),
        ("policy_detail", "sha256"),
        ("policy",),
        ("agent_run", "policy_detail", "sha256"),
        ("metadata", "policy_hash"),
        ("metadata", "policy_detail", "sha256"),
        ("metadata", "policy"),
        ("metadata", "policy_path"),
    )


def _observe_agent(run: JsonDict, events: list[JsonDict]) -> _Observed:
    del events
    name = _first_path(run, ("agent",), ("metadata", "agent"), ("metadata", "agent_name"))
    version = _first_path(run, ("agent_version",), ("metadata", "agent_version"))
    if not name.known or not version.known:
        return _Observed()
    return _Observed(
        {"name": name.value, "version": version.value},
        "run metadata",
        "high",
    )


def _observe_git_commit(run: JsonDict, events: list[JsonDict]) -> _Observed:
    del events
    return _first_path(
        run,
        ("git_commit",),
        ("commit",),
        ("metadata", "git_commit"),
        ("metadata", "commit"),
    )


def _observe_tests(run: JsonDict, events: list[JsonDict]) -> _Observed:
    direct = _first_path(
        run,
        ("tests",),
        ("test_results",),
        ("metadata", "tests"),
        ("metadata", "test_results"),
    )
    if direct.known and isinstance(direct.value, (Mapping, list, str, bool)):
        normalized = _normalize_test_record(direct.value)
        if normalized:
            return _Observed(normalized, direct.source, direct.confidence)
    audit = _first_path(run, ("audit_result",), ("metadata", "audit_result"))
    if audit.known and isinstance(audit.value, Mapping):
        normalized = _normalize_test_record(audit.value)
        if normalized:
            return _Observed(normalized, "audit_result", "high")
    normalized_root = _normalize_test_record(run)
    if normalized_root:
        return _Observed(normalized_root, "run test fields", "high")
    outcomes = _test_outcomes(events)
    if outcomes:
        return _Observed({"outcomes": outcomes, "final": outcomes[-1]}, "test events", "medium")
    return _Observed()


def _normalize_test_record(value: object) -> JsonDict:
    if isinstance(value, Mapping):
        commands = value.get("commands", value.get("tests_run", value.get("command")))
        passed = value.get("passed", value.get("tests_passed"))
        normalized: JsonDict = {}
        if isinstance(commands, str) and commands:
            normalized["commands"] = [commands]
        elif isinstance(commands, list):
            string_commands = [item for item in commands if isinstance(item, str) and item]
            if string_commands:
                normalized["commands"] = string_commands
        if isinstance(passed, bool):
            normalized["passed"] = passed
        return normalized
    if isinstance(value, str) and value:
        return {"commands": [value]}
    if isinstance(value, bool):
        return {"passed": value}
    return {}


def _observe_seed(run: JsonDict, events: list[JsonDict]) -> _Observed:
    del events
    observed = _first_path(run, ("seed",), ("metadata", "seed"))
    if not observed.known or not _is_number(observed.value):
        return _Observed()
    return observed


def _first_path(mapping: JsonDict, *paths: tuple[str, ...]) -> _Observed:
    for path in paths:
        value: object = mapping
        for part in path:
            if not isinstance(value, Mapping) or part not in value:
                value = _MISSING
                break
            value = value[part]
        if value is not _MISSING and value is not None and value != "":
            return _Observed(value, ".".join(path), "high")
    return _Observed()


def _tool_observations(events: list[JsonDict]) -> tuple[list[str], list[str]]:
    names: list[str] = []
    signatures: list[str] = []
    for event in events:
        event_type = cast(str, event["event_type"]).lower()
        if not (
            "tools/pre-execute" in event_type
            or event_type.endswith("tool/call")
            or event_type.endswith("tool/request")
        ):
            continue
        payload = cast(JsonDict, event["payload"])
        name = _tool_name(payload)
        if not name:
            continue
        names.append(name)
        signatures.append(f"{name}:{_tool_argument_signature(payload)}")
    return names, signatures


def _tool_argument_signature(payload: JsonDict) -> str:
    containers: list[Mapping[str, object]] = []
    tool = payload.get("tool")
    if isinstance(tool, Mapping):
        containers.append(tool)
    containers.append(payload)

    for container in containers:
        argument_hash = container.get("argument_hash")
        if isinstance(argument_hash, str) and argument_hash:
            return f"argument_hash:{argument_hash}"
    for container in containers:
        for key in ("arguments", "input", "args"):
            if key in container:
                return _stable_json(container[key])
    return _stable_json({})


def _tool_name(payload: JsonDict) -> str:
    for key in ("tool", "tool_name", "name"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
        if isinstance(value, Mapping):
            nested = value.get("name")
            if isinstance(nested, str) and nested:
                return nested
    return ""


def _max_consecutive(values: list[str]) -> tuple[str | None, int]:
    best_value: str | None = None
    best_count = 0
    previous: str | None = None
    current_count = 0
    for value in values:
        if value == previous:
            current_count += 1
        else:
            previous = value
            current_count = 1
        if current_count > best_count:
            best_value = value.split(":", 1)[0]
            best_count = current_count
    return best_value, best_count


def _request_failures(events: list[JsonDict]) -> tuple[int, int]:
    errors = 0
    retries = 0
    for event in events:
        event_type = cast(str, event["event_type"]).lower()
        payload = cast(JsonDict, event["payload"])
        if "request-error" in event_type or "request/error" in event_type:
            errors += 1
        if "retry" in event_type or payload.get("retry") is True:
            retries += 1
    return errors, retries


def _file_edit_counts(events: list[JsonDict]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for event in events:
        event_type = cast(str, event["event_type"]).lower()
        payload = cast(JsonDict, event["payload"])
        tool = _tool_name(payload).lower()
        if not any(marker in event_type or marker in tool for marker in ("edit", "write", "patch")):
            continue
        for path in _paths_from_payload(payload):
            counts[path] += 1
    return counts


def _paths_from_payload(payload: JsonDict) -> list[str]:
    paths: list[str] = []
    containers = [payload]
    for key in ("arguments", "input", "result"):
        nested = payload.get(key)
        if isinstance(nested, Mapping):
            containers.append({str(item_key): item for item_key, item in nested.items()})
    for container in containers:
        for key in ("path", "file", "file_path", "files", "changed_files", "touched_files"):
            value = container.get(key)
            if isinstance(value, str) and value:
                paths.append(value)
            elif isinstance(value, list):
                paths.extend(item for item in value if isinstance(item, str) and item)
    return sorted(set(paths))


def _test_outcomes(events: list[JsonDict]) -> list[str]:
    outcomes: list[str] = []
    for event in events:
        event_type = cast(str, event["event_type"]).lower()
        payload = cast(JsonDict, event["payload"])
        tool = _tool_name(payload).lower()
        if "test" not in event_type and not any(name in tool for name in ("pytest", "test")):
            continue
        passed = payload.get("passed", payload.get("tests_passed"))
        if isinstance(passed, bool):
            outcomes.append("pass" if passed else "fail")
            continue
        status = _lower_string(payload.get("status", payload.get("outcome")))
        if status in {"pass", "passed", "success", "succeeded"}:
            outcomes.append("pass")
        elif status in {"fail", "failed", "failure", "error"}:
            outcomes.append("fail")
    return outcomes


def _numeric_series(events: list[JsonDict], keys: tuple[str, ...]) -> list[float]:
    values: list[float] = []
    for event in events:
        payload = cast(JsonDict, event["payload"])
        value = _find_numeric(payload, keys)
        if value is not None and value >= 0:
            values.append(value)
    return values


def _find_numeric(payload: Mapping[str, object], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = payload.get(key)
        if _is_number(value):
            return float(cast(int | float, value))
    for nested_key in ("usage", "metrics", "result", "metadata"):
        nested = payload.get(nested_key)
        if isinstance(nested, Mapping):
            found = _find_numeric(nested, keys)
            if found is not None:
                return found
    return None


def _growth_signal(values: list[float]) -> JsonDict:
    if len(values) < 2 or values[0] <= 0:
        return {"samples": len(values), "ratio": None, "monotonic_increases": 0}
    increases = sum(right > left for left, right in pairwise(values))
    return {
        "samples": len(values),
        "ratio": round(values[-1] / values[0], 4),
        "monotonic_increases": increases,
    }


def _progress_markers(events: list[JsonDict], tests: list[str]) -> int:
    count = 0
    for event in events:
        event_type = cast(str, event["event_type"]).lower()
        payload = cast(JsonDict, event["payload"])
        status = _lower_string(payload.get("progress", payload.get("status")))
        if any(
            marker in event_type
            for marker in ("step/completed", "task/completed", "session/finalized")
        ) or status in {"completed", "done", "succeeded"}:
            count += 1
    if tests and tests[-1] == "pass":
        count += 1
    return count


def _latest_completion_sequence(events: list[JsonDict]) -> int | None:
    latest: int | None = None
    for event in events:
        event_type = cast(str, event["event_type"]).lower()
        payload = cast(JsonDict, event["payload"])
        status = _lower_string(payload.get("progress", payload.get("status")))
        completed = any(
            marker in event_type
            for marker in ("step/completed", "task/completed", "session/finalized")
        ) or status in {"completed", "done", "succeeded"}
        if not completed and "test" in event_type:
            passed = payload.get("passed", payload.get("tests_passed"))
            outcome = _lower_string(payload.get("status", payload.get("outcome")))
            completed = passed is True or outcome in {"pass", "passed", "success", "succeeded"}
        if completed:
            latest = cast(int, event["sequence"])
    return latest


def _latest_adverse_sequence(
    events: list[JsonDict],
    *,
    token_growth: JsonDict,
    context_growth: JsonDict,
) -> int | None:
    sequences: list[int] = []
    for event in events:
        event_type = cast(str, event["event_type"]).lower()
        payload = cast(JsonDict, event["payload"])
        if (
            "request-error" in event_type
            or "request/error" in event_type
            or "retry" in event_type
            or payload.get("retry") is True
        ):
            sequences.append(cast(int, event["sequence"]))
    if _growth_exceeds(
        token_growth,
        cast(float, _THRESHOLDS["token_growth_ratio"]),
    ):
        latest = _latest_numeric_sequence(events, ("total_tokens", "token_count"))
        if latest is not None:
            sequences.append(latest)
    if _growth_exceeds(
        context_growth,
        cast(float, _THRESHOLDS["context_growth_ratio"]),
    ):
        latest = _latest_numeric_sequence(
            events,
            ("context_tokens", "input_tokens", "prompt_tokens", "context_length"),
        )
        if latest is not None:
            sequences.append(latest)
    return max(sequences, default=None)


def _latest_numeric_sequence(
    events: list[JsonDict],
    keys: tuple[str, ...],
) -> int | None:
    latest: int | None = None
    for event in events:
        payload = cast(JsonDict, event["payload"])
        if _find_numeric(payload, keys) is not None:
            latest = cast(int, event["sequence"])
    return latest


def _harness_guard_signals(events: list[JsonDict]) -> list[JsonDict]:
    signals: list[JsonDict] = []
    for event in events:
        event_type = cast(str, event["event_type"]).lower()
        payload = cast(JsonDict, event["payload"])
        source = _harness_guard_source(payload, event_type)
        projected = payload.get("harness_guard_signals")
        projected_kinds: list[str] = []
        if isinstance(projected, list):
            projected_kinds = [
                kind
                for item in projected
                if (kind := _HARNESS_GUARD_KINDS.get(_lower_string(item))) is not None
            ]
        if projected_kinds:
            signals.extend(
                {
                    "kind": kind,
                    "source": source,
                    "sequence": event["sequence"],
                }
                for kind in projected_kinds
            )
            continue
        message = _lower_string(payload.get("message"))
        combined = " ".join((event_type, source, message))
        kind = ""
        if "repeat-tool" in combined or "repeat_tool" in combined:
            kind = "repeat_tool"
        elif "timeout" in combined or "timed out" in combined:
            kind = "timeout"
        if kind:
            signals.append(
                {
                    "kind": kind,
                    "source": source or event_type,
                    "sequence": event["sequence"],
                }
            )
    return signals[:_MAX_EVIDENCE]


def _harness_guard_source(payload: JsonDict, event_type: str) -> str:
    guard = _lower_string(payload.get("guard"))
    if guard:
        return guard
    source = payload.get("source")
    if isinstance(source, Mapping):
        plugin = _lower_string(source.get("plugin"))
        if plugin:
            return plugin
        source_kind = _lower_string(source.get("kind"))
        if source_kind:
            return source_kind
    else:
        source_text = _lower_string(source)
        if source_text:
            return source_text
    return event_type


def _safety_signals(events: list[JsonDict]) -> list[JsonDict]:
    signals: list[JsonDict] = []
    risky_categories = {
        "security",
        "destructive",
        "destructive_change",
        "secret",
        "data_exposure",
        "production",
    }
    for event in events:
        payload = cast(JsonDict, event["payload"])
        categories = set(_string_values(payload.get("risk_categories")))
        risk_level = _lower_string(payload.get("risk_level"))
        decision = _lower_string(payload.get("decision", payload.get("action")))
        matched = sorted(categories & risky_categories)
        if risk_level == "high" or matched or decision in {"deny", "block"}:
            signals.append(
                {
                    "category": matched[0] if matched else risk_level or decision,
                    "sequence": event["sequence"],
                }
            )
    return signals[:_MAX_EVIDENCE]


def _meaningful_event_count(events: list[JsonDict]) -> int:
    markers = ("agent/", "tools/", "tool/", "test", "step/", "task/", "guard/")
    return sum(
        any(marker in cast(str, event["event_type"]).lower() for marker in markers)
        for event in events
    )


def _stability_confidence(meaningful_events: int, guards: list[JsonDict]) -> str:
    if meaningful_events >= cast(int, _THRESHOLDS["high_confidence_events"]):
        return "high"
    if meaningful_events >= 3 or guards:
        return "medium"
    return "low"


def _classify_stability(signals: JsonDict) -> str:
    observed = cast(int, signals["observed_events"])
    meaningful = cast(int, signals["meaningful_events"])
    repeated = cast(JsonDict, signals["repeated_tool_calls"])
    failures = cast(JsonDict, signals["request_failures"])
    churn = cast(JsonDict, signals["file_churn"])
    tests = cast(JsonDict, signals["test_trend"])
    progress = cast(JsonDict, signals["progress"])
    guards = cast(list[JsonDict], signals["harness_guard_signals"])
    errors = cast(int, failures["errors"])
    retries = cast(int, failures["retries"])
    completed_markers = cast(int, progress["completed_markers"])
    completed = completed_markers if progress.get("completion_is_current") is True else 0
    growth_signals = [
        cast(JsonDict, signals["token_growth"]),
        cast(JsonDict, signals["context_growth"]),
        cast(JsonDict, signals["latency_growth"]),
        cast(JsonDict, signals["cost_growth"]),
    ]
    growing = sum(
        isinstance(item.get("ratio"), (int, float))
        and cast(float, item["ratio"]) >= cast(float, _THRESHOLDS["growth_ratio"])
        for item in growth_signals
    )
    token_growing = _growth_exceeds(
        cast(JsonDict, signals["token_growth"]),
        cast(float, _THRESHOLDS["token_growth_ratio"]),
    )
    context_growing = _growth_exceeds(
        cast(JsonDict, signals["context_growth"]),
        cast(float, _THRESHOLDS["context_growth_ratio"]),
    )
    if observed < 2 or meaningful < 2:
        return "insufficient_evidence"
    if (
        errors >= cast(int, _THRESHOLDS["request_errors"])
        and retries >= cast(int, _THRESHOLDS["request_retries"])
        and completed == 0
    ) or (growing >= 2 and errors >= 2 and completed == 0) or (
        (token_growing or context_growing)
        and errors >= 2
        and retries >= cast(int, _THRESHOLDS["request_retries"])
        and completed == 0
    ):
        return "diverging"
    if cast(int, tests["transitions"]) >= cast(int, _THRESHOLDS["test_transitions"]):
        return "oscillating"
    if (
        cast(int, repeated["max_repetitions"])
        >= cast(int, _THRESHOLDS["repeated_tool_calls"])
        and completed == 0
    ) or guards or (errors >= 2 and completed == 0):
        return "stalled"
    if tests["final"] == "pass" or completed > 0:
        return "converging"
    if cast(int, churn["max_edits_per_file"]) >= cast(
        int, _THRESHOLDS["file_edits_per_path"]
    ):
        return "oscillating"
    if meaningful >= 3 and completed == 0:
        return "stalled"
    return "insufficient_evidence"


def _growth_exceeds(signal: JsonDict, threshold: float) -> bool:
    ratio = signal.get("ratio")
    return isinstance(ratio, (int, float)) and not isinstance(ratio, bool) and ratio >= threshold


def _stability_summary(state: str, confidence: str) -> str:
    descriptions = {
        "converging": "Recorded progress or test outcomes are consistent with convergence.",
        "stalled": "Recorded retries, repeated actions, or Harness guard signals indicate a stall.",
        "oscillating": (
            "Recorded tests, tools, or file edits alternate or repeat without stable progress."
        ),
        "diverging": "Recorded errors and resource or churn growth indicate divergence.",
        "insufficient_evidence": (
            "There is not enough observable execution evidence to classify stability."
        ),
    }
    return f"{descriptions[state]} Confidence is {confidence}; no hidden-state claim is made."


def _denied_tools(events: list[JsonDict]) -> list[str]:
    denied: list[str] = []
    for event in events:
        if cast(str, event["event_type"]).lower() != "tools/pre-execute":
            continue
        payload = cast(JsonDict, event["payload"])
        decision = _lower_string(payload.get("decision", payload.get("action")))
        if decision in {"deny", "denied", "block", "blocked"}:
            denied.append(_tool_name(payload) or "unknown tool")
    return sorted(set(denied))


def _high_impact_changes(attribution: JsonDict) -> list[str]:
    factors = attribution.get("factors")
    if not isinstance(factors, list):
        return []
    changed: list[str] = []
    for raw in factors:
        factor = _as_dict(raw)
        name = factor.get("factor")
        if (
            isinstance(name, str)
            and factor.get("changed") is True
            and factor.get("impact") == "high"
            and factor.get("confidence") == "high"
        ):
            changed.append(name)
    return sorted(set(changed))


def _complete_safe_preflight(preflight: JsonDict, run: JsonDict) -> bool:
    if preflight.get("schema") != PreflightDecision.SCHEMA:
        return False
    if preflight.get("run_id") != _run_id(run):
        return False
    if (
        _lower_string(preflight.get("decision")) != "allow"
        or _lower_string(preflight.get("risk_level")) != "low"
        or preflight.get("required_review") is not False
        or not _safe_summary(preflight.get("summary"))
    ):
        return False
    prompt_hash = preflight.get("prompt_hash")
    improved_prompt_hash = preflight.get("improved_prompt_hash")
    if not isinstance(prompt_hash, str) or not prompt_hash:
        return False
    if not isinstance(improved_prompt_hash, str) or not improved_prompt_hash:
        return False
    if not isinstance(preflight.get("improved_prompt"), str):
        return False
    if preflight.get("capture_mode") not in {"redacted", "full"}:
        return False
    recorded_prompt_hash = run.get("prompt_hash")
    if isinstance(recorded_prompt_hash, str) and recorded_prompt_hash != prompt_hash:
        return False

    details = _as_dict(preflight.get("details"))
    authorization_scope = details.get("authorization_scope")
    if not isinstance(authorization_scope, str) or not authorization_scope:
        return False
    recorded_scope = run.get("authorization")
    if isinstance(recorded_scope, str) and recorded_scope != authorization_scope:
        return False
    guard = _as_dict(details.get("guard"))
    if (
        _lower_string(guard.get("action")) != "allow"
        or _lower_string(guard.get("risk_level")) != "low"
        or guard.get("required_review") is not False
        or guard.get("within_budget") is False
    ):
        return False
    risk_categories = guard.get("risk_categories")
    policy_violations = guard.get("policy_violations")
    return (
        isinstance(risk_categories, list)
        and all(isinstance(item, str) for item in risk_categories)
        and isinstance(policy_violations, list)
        and all(isinstance(item, Mapping) for item in policy_violations)
    )


def _complete_attribution_evidence(attribution: JsonDict, run_id: str) -> bool:
    if attribution.get("schema") != AttributionReport.SCHEMA:
        return False
    if attribution.get("run_id") != run_id or not _safe_summary(attribution.get("summary")):
        return False
    factors = attribution.get("factors")
    if not isinstance(factors, list) or len(factors) != len(_FACTOR_IMPACT):
        return False

    observed: dict[str, object] = {}
    changed_count = 0
    unknown_count = 0
    for raw in factors:
        factor = _as_dict(raw)
        name = factor.get("factor")
        changed = factor.get("changed")
        if not isinstance(name, str) or name not in _FACTOR_IMPACT or name in observed:
            return False
        if changed is True:
            expected_impact = _FACTOR_IMPACT[name]
            changed_count += 1
        elif changed is False:
            expected_impact = "low"
        elif changed == "unknown":
            expected_impact = "unknown"
            unknown_count += 1
        else:
            return False
        evidence = factor.get("evidence")
        if (
            factor.get("impact") != expected_impact
            or factor.get("confidence") not in {"low", "medium", "high"}
            or not isinstance(evidence, list)
            or not evidence
            or not all(isinstance(item, str) for item in evidence)
            or not _safe_summary(factor.get("summary"))
        ):
            return False
        observed[name] = changed

    if set(observed) != set(_FACTOR_IMPACT):
        return False
    expected_status = (
        "changes_observed"
        if changed_count
        else "insufficient_evidence" if unknown_count else "no_changes_observed"
    )
    high_impact_factors = {
        name for name, impact in _FACTOR_IMPACT.items() if impact == "high"
    }
    return attribution.get("status") == expected_status and all(
        observed[name] is False for name in high_impact_factors
    )


def _complete_stability_evidence(stability: JsonDict, run_id: str) -> bool:
    if stability.get("schema") != StabilityReport.SCHEMA:
        return False
    if stability.get("run_id") != run_id:
        return False
    state = _lower_string(stability.get("state"))
    signals = _as_dict(stability.get("signals"))
    confidence = _lower_string(signals.get("confidence"))
    if confidence not in {"medium", "high"}:
        return False
    if stability.get("summary") != _stability_summary(state, confidence):
        return False
    if signals.get("thresholds") != _THRESHOLDS:
        return False
    if not all(
        _is_non_negative_int(signals.get(name))
        for name in ("observed_events", "meaningful_events")
    ):
        return False

    repeated = _as_dict(signals.get("repeated_tool_calls"))
    failures = _as_dict(signals.get("request_failures"))
    churn = _as_dict(signals.get("file_churn"))
    tests = _as_dict(signals.get("test_trend"))
    progress = _as_dict(signals.get("progress"))
    if not all(
        _is_non_negative_int(value)
        for value in (
            repeated.get("max_repetitions"),
            failures.get("errors"),
            failures.get("retries"),
            churn.get("max_edits_per_file"),
            tests.get("transitions"),
            progress.get("completed_markers"),
        )
    ):
        return False
    for name in ("token_growth", "context_growth", "latency_growth", "cost_growth"):
        growth = _as_dict(signals.get(name))
        ratio = growth.get("ratio")
        if (
            not _is_non_negative_int(growth.get("samples"))
            or not _is_non_negative_int(growth.get("monotonic_increases"))
            or (
                ratio is not None
                and (not _is_number(ratio) or cast(int | float, ratio) < 0)
            )
        ):
            return False
    if not isinstance(tests.get("outcomes"), list) or not isinstance(tests.get("final"), str):
        return False
    if not isinstance(repeated.get("observed_tools"), list):
        return False
    if not isinstance(churn.get("files"), list):
        return False
    guards = signals.get("harness_guard_signals")
    safety = signals.get("safety_signals")
    if not isinstance(guards, list) or not all(isinstance(item, Mapping) for item in guards):
        return False
    if not isinstance(safety, list) or not all(isinstance(item, Mapping) for item in safety):
        return False
    try:
        return _classify_stability(signals) == state
    except (KeyError, TypeError, ValueError):
        return False


def _is_non_negative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _minimum_confidence(left: str, right: str) -> str:
    ranks = {"low": 0, "medium": 1, "high": 2}
    return left if ranks[left] <= ranks[right] else right


def _display(value: object) -> str:
    rendered = _stable_json(value)
    if len(rendered) > 160:
        return rendered[:157] + "..."
    return rendered


def _stable_json(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return repr(value)


def _string_values(value: object) -> list[str]:
    if isinstance(value, str) and value:
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    return []


def _lower_string(value: object) -> str:
    return value.strip().lower() if isinstance(value, str) else ""


def _safe_summary(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
