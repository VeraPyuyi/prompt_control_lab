from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _event(sequence: int, event_type: str, **payload: object) -> dict[str, object]:
    return {
        "sequence": sequence,
        "event_type": event_type,
        "payload": payload,
    }


def _harness_tool_projection(
    *, name: str, call_id: str, argument_hash: str
) -> dict[str, object]:
    return {
        "call_id": call_id,
        "root_call_id": call_id,
        "name": name,
        "argument_hash": argument_hash,
        "argument_keys": ["path"],
    }


def _harness_session_projection(
    sequence: int,
    event_type: str,
    **payload: object,
) -> dict[str, object]:
    return {
        "sequence": sequence,
        "event_type": f"session/{event_type}",
        "payload": {
            "event_type": event_type,
            "harness_sequence": sequence,
            "harness_time_ms": 1_700_000_000_000 + sequence,
            "turn": 1,
            "step": sequence,
            **payload,
        },
    }


def _argument_hash(fill: str) -> str:
    return f"sha256:{fill * 64}"


def _fully_observed_run(run_id: str) -> dict[str, object]:
    return {
        "run_id": run_id,
        "authorization": "agent-scoped",
        "prompt_hash": "sha256:prompt",
        "provider": "deepseek",
        "model": "deepseek-chat",
        "agent": "deepseek-harness",
        "metadata": {
            "api_params": {"temperature": 0.0},
            "data": "tasks.jsonl",
            "split_hash": "split-a",
            "tools": ["read"],
            "policy_hash": "sha256:policy-a",
            "agent_version": "0.1.0",
            "git_commit": "abc123",
            "tests": {"commands": ["pytest"], "passed": True},
            "seed": 7,
        },
    }


def _complete_safe_control_evidence(
    run: dict[str, object],
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    list[dict[str, object]],
]:
    from promptcontrollab.control_analysis import analyze_attribution, analyze_stability
    from promptcontrollab.control_protocol import PreflightDecision

    run_id = str(run["run_id"])
    baseline = _fully_observed_run(f"{run_id}-baseline")
    events = [
        _event(1, "agent/request", usage={"total_tokens": 100, "context_tokens": 100}),
        _event(2, "step/completed", status="completed"),
        _event(3, "tests/result", passed=True),
    ]
    preflight = PreflightDecision(
        run_id=run_id,
        decision="allow",
        risk_level="low",
        required_review=False,
        summary="Guard analysis found no review requirement.",
        improved_prompt="Use the bounded implementation plan.",
        prompt_hash="sha256:prompt",
        capture_mode="redacted",
        details={
            "authorization_scope": "agent-scoped",
            "guard": {
                "action": "allow",
                "risk_level": "low",
                "required_review": False,
                "risk_categories": [],
                "policy_violations": [],
                "within_budget": True,
            },
        },
    )
    return (
        preflight.to_json(),
        analyze_attribution(run, events, baseline_run=baseline).to_json(),
        analyze_stability(run, events).to_json(),
        events,
    )


def test_attribution_compares_all_supported_factors_without_causal_claims() -> None:
    from promptcontrollab.control_analysis import analyze_attribution

    baseline = {
        "run_id": "baseline",
        "prompt_hash": "sha256:old",
        "provider": "deepseek",
        "model": "deepseek-chat",
        "agent": "deepseek-harness",
        "metadata": {
            "api_params": {"temperature": 0.0},
            "data": "tasks.jsonl",
            "split_hash": "split-a",
            "tools": ["read", "pytest"],
            "policy_hash": "sha256:policy-a",
            "agent_version": "0.1.0",
            "git_commit": "abc123",
            "tests": {"command": "pytest", "passed": True},
            "seed": 7,
        },
    }
    current = {
        "run_id": "candidate",
        "prompt_hash": "sha256:new",
        "provider": "deepseek",
        "model": "deepseek-reasoner",
        "agent": "deepseek-harness",
        "metadata": {
            "api_params": {"temperature": 0.2},
            "data": "tasks.jsonl",
            "split_hash": "split-a",
            "tools": ["read", "pytest"],
            "policy_hash": "sha256:policy-b",
            "agent_version": "0.2.0",
            "git_commit": "def456",
            "tests": {"command": "pytest", "passed": True},
            "seed": 7,
        },
    }

    report = analyze_attribution(current, [], baseline_run=baseline)

    factors = {item["factor"]: item for item in report.factors}
    assert set(factors) == {
        "prompt",
        "model",
        "api_parameters",
        "data_split",
        "tools",
        "policy",
        "agent",
        "git_commit",
        "tests",
        "seed",
    }
    assert factors["prompt"]["changed"] is True
    assert factors["prompt"]["impact"] == "medium"
    assert factors["model"]["changed"] is True
    assert factors["model"]["impact"] == "high"
    assert factors["data_split"]["changed"] is False
    assert factors["data_split"]["impact"] == "low"
    assert factors["tools"]["changed"] is False
    assert factors["policy"]["changed"] is True
    assert all(item["confidence"] in {"low", "medium", "high"} for item in factors.values())
    assert all(isinstance(item["evidence"], list) for item in factors.values())
    assert report.status == "changes_observed"
    assert "does not establish causation" in report.summary


def test_attribution_uses_baseline_artifacts_and_reports_unknown_evidence() -> None:
    from promptcontrollab.control_analysis import analyze_attribution

    report = analyze_attribution(
        {"run_id": "candidate", "metadata": {"seed": "malformed"}},
        [{"event_type": "agent/request", "payload": {"provider": "deepseek"}}],
        baseline_artifacts={
            "control_run": {
                "run_id": "baseline",
                "provider": "deepseek",
                "model": "deepseek-chat",
            }
        },
    )

    factors = {item["factor"]: item for item in report.factors}
    assert factors["model"]["changed"] == "unknown"
    assert factors["model"]["confidence"] == "low"
    assert factors["seed"]["changed"] == "unknown"
    assert report.status == "insufficient_evidence"


def test_attribution_combines_evidence_distributed_across_baseline_artifacts() -> None:
    from promptcontrollab.control_analysis import analyze_attribution

    current = {
        "run_id": "candidate",
        "prompt_hash": "sha256:prompt",
        "provider": "deepseek",
        "model": "deepseek-chat",
        "agent": "deepseek-harness",
        "metadata": {
            "api_params": {"temperature": 0.0},
            "data": "tasks.jsonl",
            "split_hash": "split-a",
            "tools": ["read"],
            "policy_hash": "sha256:policy-a",
            "agent_version": "0.1.0",
            "git_commit": "abc123",
            "tests": {"commands": ["pytest"], "passed": True},
            "seed": 11,
        },
    }
    report = analyze_attribution(
        current,
        [],
        baseline_artifacts={
            "control_run": {
                "run_id": "baseline",
                "prompt_hash": "sha256:prompt",
                "provider": "deepseek",
                "model": "deepseek-chat",
            },
            "manifest": {
                "api_params": {"temperature": 0.0},
                "data": "tasks.jsonl",
                "split_hash": "split-a",
                "tools": ["read"],
                "seed": 11,
            },
            "agent_run": {
                "agent": "deepseek-harness",
                "agent_version": "0.1.0",
                "git_commit": "abc123",
                "policy_detail": {"sha256": "sha256:policy-a"},
            },
            "audit_result": {"tests_run": ["pytest"], "tests_passed": True},
        },
    )

    factors = {item["factor"]: item for item in report.factors}
    assert all(item["changed"] is False for item in factors.values())
    assert report.status == "no_changes_observed"


def test_data_split_is_unknown_when_either_component_is_missing() -> None:
    from promptcontrollab.control_analysis import analyze_attribution

    both_missing_split = analyze_attribution(
        {"run_id": "candidate", "metadata": {"data": "tasks.jsonl"}},
        [],
        baseline_run={"run_id": "baseline", "metadata": {"data": "tasks.jsonl"}},
    )
    current_missing_data = analyze_attribution(
        {"run_id": "candidate", "metadata": {"split_hash": "split-a"}},
        [],
        baseline_run={
            "run_id": "baseline",
            "metadata": {"data": "tasks.jsonl", "split_hash": "split-a"},
        },
    )

    first = {item["factor"]: item for item in both_missing_split.factors}["data_split"]
    second = {item["factor"]: item for item in current_missing_data.factors}["data_split"]
    assert first["changed"] == "unknown"
    assert first["impact"] == "unknown"
    assert "unknown" in first["summary"].lower()
    assert second["changed"] == "unknown"


def test_agent_factor_is_unknown_when_either_version_is_missing() -> None:
    from promptcontrollab.control_analysis import analyze_attribution

    reports = [
        analyze_attribution(
            {"run_id": "both-missing", "agent": "deepseek-harness"},
            [],
            baseline_run={"run_id": "baseline", "agent": "deepseek-harness"},
        ),
        analyze_attribution(
            {"run_id": "current-missing", "agent": "deepseek-harness"},
            [],
            baseline_run={
                "run_id": "baseline",
                "agent": "deepseek-harness",
                "agent_version": "0.1.0",
            },
        ),
        analyze_attribution(
            {
                "run_id": "baseline-missing",
                "agent": "deepseek-harness",
                "agent_version": "0.1.0",
            },
            [],
            baseline_run={"run_id": "baseline", "agent": "deepseek-harness"},
        ),
    ]

    for report in reports:
        agent = {item["factor"]: item for item in report.factors}["agent"]
        assert agent["changed"] == "unknown"
        assert agent["impact"] == "unknown"
        assert agent["confidence"] == "low"


def test_explicit_empty_tools_is_a_known_no_tools_inventory() -> None:
    from promptcontrollab.control_analysis import analyze_attribution

    unchanged = analyze_attribution(
        {"run_id": "no-tools", "tools": []},
        [],
        baseline_run={"run_id": "baseline", "tools": []},
    )
    changed = analyze_attribution(
        {"run_id": "no-tools", "tools": []},
        [],
        baseline_run={"run_id": "baseline", "tools": ["read"]},
    )

    unchanged_tools = {item["factor"]: item for item in unchanged.factors}["tools"]
    changed_tools = {item["factor"]: item for item in changed.factors}["tools"]
    assert unchanged_tools["changed"] is False
    assert unchanged_tools["confidence"] == "high"
    assert changed_tools["changed"] is True
    assert changed_tools["impact"] == "medium"


@dataclass
class _EventObject:
    sequence: int
    event_type: str
    payload: dict[str, object]

    def to_json(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "event_type": self.event_type,
            "payload": self.payload,
        }


def test_analysis_accepts_event_objects_and_sorts_by_sequence() -> None:
    from promptcontrollab.control_analysis import analyze_stability

    events = [
        _EventObject(3, "tests/result", {"passed": True}),
        _EventObject(1, "agent/request", {"usage": {"total_tokens": 100}}),
        _EventObject(2, "step/completed", {"progress": "completed"}),
    ]

    report = analyze_stability({"run_id": "run-objects"}, events)

    assert report.state == "converging"
    assert report.signals["test_trend"]["final"] == "pass"
    assert report.signals["progress"]["completed_markers"] >= 1


def test_stability_returns_insufficient_evidence_for_missing_or_malformed_events() -> None:
    from promptcontrollab.control_analysis import analyze_stability

    report = analyze_stability(
        {"run_id": "sparse"},
        [None, {"payload": "not-an-object"}, {"event_type": 42}],
    )

    assert report.state == "insufficient_evidence"
    assert report.signals["observed_events"] == 0
    assert "observable execution evidence" in report.summary


def test_stability_classifies_stalled_and_consumes_harness_guard_signals() -> None:
    from promptcontrollab.control_analysis import analyze_stability

    events = [
        _event(1, "tools/pre-execute", tool="read", arguments={"path": "src/app.py"}),
        _event(2, "tools/pre-execute", tool="read", arguments={"path": "src/app.py"}),
        _event(3, "tools/pre-execute", tool="read", arguments={"path": "src/app.py"}),
        _event(
            4,
            "guard/signal",
            guard="repeat-tool-reminder",
            message="Harness emitted its repeat-tool reminder.",
        ),
    ]

    report = analyze_stability({"run_id": "stalled"}, events)

    assert report.state == "stalled"
    assert report.signals["repeated_tool_calls"]["max_repetitions"] == 3
    assert report.signals["harness_guard_signals"][0]["kind"] == "repeat_tool"
    assert report.signals["thresholds"]["repeated_tool_calls"] == 3


def test_native_harness_tool_projection_keeps_distinct_argument_hashes_distinct() -> None:
    from promptcontrollab.control_analysis import analyze_stability

    events = [
        _event(
            sequence,
            "tools/pre-execute",
            tool=_harness_tool_projection(
                name="read",
                call_id=f"call-{sequence}",
                argument_hash=_argument_hash(fill),
            ),
            decision="allow",
        )
        for sequence, fill in enumerate(("a", "b", "c"), start=1)
    ]

    report = analyze_stability({"run_id": "native-distinct-tools"}, events)

    assert report.signals["repeated_tool_calls"] == {
        "tool": "read",
        "max_repetitions": 1,
        "observed_tools": ["read", "read", "read"],
    }


def test_native_harness_session_projection_keeps_distinct_argument_hashes_distinct() -> None:
    from promptcontrollab.control_analysis import analyze_stability

    events = [
        _harness_session_projection(
            sequence,
            "tool/call",
            tool_name="read",
            call_id=f"call-{sequence}",
            argument_hash=_argument_hash(fill),
        )
        for sequence, fill in enumerate(("a", "b", "c"), start=1)
    ]

    report = analyze_stability({"run_id": "native-distinct-session-tools"}, events)

    assert report.signals["repeated_tool_calls"]["max_repetitions"] == 1


def test_native_harness_session_projection_still_detects_true_tool_repeats() -> None:
    from promptcontrollab.control_analysis import analyze_stability

    events = [
        _harness_session_projection(
            sequence,
            "tool/call",
            tool_name="read",
            call_id=f"call-{sequence}",
            argument_hash=_argument_hash("a"),
        )
        for sequence in range(1, 4)
    ]

    report = analyze_stability({"run_id": "native-repeated-tools"}, events)

    assert report.signals["repeated_tool_calls"]["tool"] == "read"
    assert report.signals["repeated_tool_calls"]["max_repetitions"] == 3
    assert report.state == "stalled"


def test_native_harness_guard_projection_enters_evidence_without_overclaiming() -> None:
    from promptcontrollab.control_analysis import analyze_stability

    events = [
        _harness_session_projection(
            1,
            "user/message",
            source={"kind": "plugin", "plugin": "repeat-tool-reminder"},
            harness_guard_signals=["repeat_tool_reminder", "unknown_future_signal"],
        ),
        _harness_session_projection(
            2,
            "tool/result",
            is_error=True,
            error={"name": "TimeoutError", "code": "TOOL_TIMEOUT"},
            harness_guard_signals=["tool_timeout"],
        ),
    ]

    report = analyze_stability({"run_id": "native-guards"}, events)

    assert report.signals["harness_guard_signals"] == [
        {
            "kind": "repeat_tool",
            "source": "repeat-tool-reminder",
            "sequence": 1,
        },
        {
            "kind": "timeout",
            "source": "session/tool/result",
            "sequence": 2,
        },
    ]
    assert report.state == "insufficient_evidence"
    assert "no hidden-state claim is made" in report.summary


def test_stability_classifies_oscillating_test_and_file_behavior() -> None:
    from promptcontrollab.control_analysis import analyze_stability

    events = [
        _event(1, "tools/post-execute", tool="edit", path="src/app.py"),
        _event(2, "tests/result", passed=True),
        _event(3, "tools/post-execute", tool="edit", path="src/app.py"),
        _event(4, "tests/result", passed=False),
        _event(5, "tools/post-execute", tool="edit", path="src/app.py"),
        _event(6, "tests/result", passed=True),
        _event(7, "tests/result", passed=False),
    ]

    report = analyze_stability({"run_id": "oscillating"}, events)

    assert report.state == "oscillating"
    assert report.signals["test_trend"]["transitions"] == 3
    assert report.signals["file_churn"]["max_edits_per_file"] == 3


def test_stability_classifies_diverging_from_bounded_observable_growth() -> None:
    from promptcontrollab.control_analysis import analyze_stability

    events = [
        _event(1, "agent/request", usage={"total_tokens": 100}, latency_ms=100, cost=0.01),
        _event(2, "agent/request-error", retry=True),
        _event(3, "agent/request", usage={"total_tokens": 220}, latency_ms=220, cost=0.03),
        _event(4, "agent/request-error", retry=True),
        _event(5, "agent/request", usage={"total_tokens": 450}, latency_ms=500, cost=0.08),
        _event(6, "agent/request-error", retry=True),
        _event(7, "tools/post-execute", tool="edit", path="src/auth.py"),
        _event(8, "tools/post-execute", tool="edit", path="src/auth.py"),
        _event(9, "tools/post-execute", tool="edit", path="src/auth.py"),
        _event(10, "tools/post-execute", tool="edit", path="src/auth.py"),
    ]

    report = analyze_stability({"run_id": "diverging"}, events)

    assert report.state == "diverging"
    assert report.signals["request_failures"]["errors"] == 3
    assert report.signals["token_growth"]["ratio"] == 4.5
    assert report.signals["latency_growth"]["ratio"] == 5.0
    assert report.signals["cost_growth"]["ratio"] == 8.0
    assert report.signals["confidence"] == "high"


def test_token_and_context_growth_are_independent_classification_evidence() -> None:
    from promptcontrollab.control_analysis import analyze_stability

    events = [
        _event(
            1,
            "agent/request",
            usage={"total_tokens": 100, "context_tokens": 100},
        ),
        _event(2, "agent/request-error", retry=True),
        _event(
            3,
            "agent/request",
            usage={"total_tokens": 110, "context_tokens": 250},
        ),
        _event(4, "agent/request-error", retry=True),
        _event(
            5,
            "agent/request",
            usage={"total_tokens": 120, "context_tokens": 400},
        ),
    ]

    report = analyze_stability({"run_id": "context-growth"}, events)

    assert report.signals["token_growth"]["ratio"] == 1.2
    assert report.signals["context_growth"]["ratio"] == 4.0
    assert report.signals["thresholds"]["token_growth_ratio"] == 2.0
    assert report.signals["thresholds"]["context_growth_ratio"] == 2.0
    assert report.state == "diverging"


def test_later_token_growth_and_errors_override_historical_completion() -> None:
    from promptcontrollab.control_analysis import analyze_stability

    report = analyze_stability(
        {"run_id": "stale-token-completion"},
        [
            _event(
                1,
                "agent/request",
                usage={"total_tokens": 100, "context_tokens": 100},
            ),
            _event(2, "step/completed", status="completed"),
            _event(3, "agent/request-error", retry=True),
            _event(
                4,
                "agent/request",
                usage={"total_tokens": 250, "context_tokens": 110},
            ),
            _event(5, "agent/request-error", retry=True),
            _event(
                6,
                "agent/request",
                usage={"total_tokens": 400, "context_tokens": 120},
            ),
        ],
    )

    assert report.signals["token_growth"]["ratio"] == 4.0
    assert report.signals["context_growth"]["ratio"] == 1.2
    assert report.state == "diverging"


def test_later_context_growth_and_errors_override_historical_completion() -> None:
    from promptcontrollab.control_analysis import analyze_stability

    report = analyze_stability(
        {"run_id": "stale-context-completion"},
        [
            _event(
                1,
                "agent/request",
                usage={"total_tokens": 100, "context_tokens": 100},
            ),
            _event(2, "step/completed", status="completed"),
            _event(3, "agent/request-error", retry=True),
            _event(
                4,
                "agent/request",
                usage={"total_tokens": 110, "context_tokens": 250},
            ),
            _event(5, "agent/request-error", retry=True),
            _event(
                6,
                "agent/request",
                usage={"total_tokens": 120, "context_tokens": 400},
            ),
        ],
    )

    assert report.signals["token_growth"]["ratio"] == 1.2
    assert report.signals["context_growth"]["ratio"] == 4.0
    assert report.state == "diverging"


def test_completion_after_adverse_growth_remains_converging() -> None:
    from promptcontrollab.control_analysis import analyze_stability

    report = analyze_stability(
        {"run_id": "current-completion"},
        [
            _event(
                1,
                "agent/request",
                usage={"total_tokens": 100, "context_tokens": 100},
            ),
            _event(2, "agent/request-error", retry=True),
            _event(
                3,
                "agent/request",
                usage={"total_tokens": 110, "context_tokens": 250},
            ),
            _event(4, "agent/request-error", retry=True),
            _event(
                5,
                "agent/request",
                usage={"total_tokens": 120, "context_tokens": 400},
            ),
            _event(6, "step/completed", status="completed"),
        ],
    )

    assert report.state == "converging"


def test_timeout_guard_is_evidence_for_stalled_not_a_reimplemented_guard() -> None:
    from promptcontrollab.control_analysis import analyze_stability

    report = analyze_stability(
        {"run_id": "timeout"},
        [
            _event(1, "agent/request", latency_ms=100),
            _event(2, "guard/timeout", guard="timeout-policy", elapsed_ms=30_000),
        ],
    )

    assert report.state == "stalled"
    assert report.signals["harness_guard_signals"] == [
        {
            "kind": "timeout",
            "source": "timeout-policy",
            "sequence": 2,
        }
    ]


def test_control_decision_blocks_high_risk_preflight_or_denied_tool() -> None:
    from promptcontrollab.control_analysis import make_control_decision

    high_risk = make_control_decision(
        {"run_id": "high-risk"},
        preflight={
            "decision": "suggest",
            "risk_level": "high",
            "required_review": False,
            "summary": "High-risk operation detected.",
        },
        stability={"state": "insufficient_evidence", "signals": {}},
        events=[],
    )
    denied = make_control_decision(
        {"run_id": "denied"},
        preflight={"decision": "allow", "risk_level": "low", "required_review": False},
        stability={"state": "converging", "signals": {}},
        events=[_event(1, "tools/pre-execute", decision="deny", tool="shell")],
    )

    assert high_risk.decision == "block"
    assert denied.decision == "block"
    assert any("denied" in reason.lower() for reason in denied.reasons)


def test_control_decision_preserves_required_review_and_attribution_validity() -> None:
    from promptcontrollab.control_analysis import make_control_decision

    decision = make_control_decision(
        {"run_id": "review"},
        preflight={
            "decision": "suggest",
            "risk_level": "medium",
            "required_review": True,
            "summary": "Target files are missing.",
        },
        attribution={
            "factors": [
                {
                    "factor": "model",
                    "changed": True,
                    "impact": "high",
                    "confidence": "high",
                    "evidence": ["Model IDs differ."],
                    "summary": "The comparison is not prompt-only.",
                }
            ]
        },
        stability={"state": "converging", "signals": {"confidence": "medium"}},
        events=[],
    )

    assert decision.decision == "needs_review"
    assert "Complete the required human review" in decision.next_action


def test_control_decision_handles_divergence_and_lower_risk_states_conservatively() -> None:
    from promptcontrollab.control_analysis import make_control_decision

    diverging = make_control_decision(
        {"run_id": "diverging"},
        preflight={"decision": "allow", "risk_level": "low", "required_review": False},
        stability={
            "state": "diverging",
            "signals": {"confidence": "high", "safety_signals": []},
        },
        events=[],
    )
    unsafe = make_control_decision(
        {"run_id": "unsafe"},
        preflight={"decision": "allow", "risk_level": "low", "required_review": False},
        stability={
            "state": "diverging",
            "signals": {
                "confidence": "high",
                "safety_signals": [{"category": "security", "sequence": 4}],
            },
        },
        events=[],
    )
    stalled = make_control_decision(
        {"run_id": "stalled"},
        preflight={"decision": "allow", "risk_level": "low", "required_review": False},
        stability={"state": "stalled", "signals": {"confidence": "medium"}},
        events=[],
    )
    converging_run = _fully_observed_run("converging")
    preflight, attribution, stability, events = _complete_safe_control_evidence(converging_run)
    converging = make_control_decision(
        converging_run,
        preflight=preflight,
        attribution=attribution,
        stability=stability,
        events=events,
    )

    assert diverging.decision == "needs_review"
    assert unsafe.decision == "block"
    assert stalled.decision == "suggest"
    assert converging.decision == "allow"


def test_control_decision_never_allows_incomplete_or_unsafe_evidence() -> None:
    from promptcontrollab.control_analysis import make_control_decision

    safe_run = _fully_observed_run("safe")
    preflight, attribution, stability, events = _complete_safe_control_evidence(safe_run)
    safe = make_control_decision(
        safe_run,
        preflight=preflight,
        attribution=attribution,
        stability=stability,
        events=events,
    )
    missing_preflight = make_control_decision(
        {"run_id": "missing-preflight"},
        stability={
            "state": "converging",
            "signals": {"confidence": "high", "safety_signals": []},
        },
    )
    suggested_preflight = make_control_decision(
        {"run_id": "suggested-preflight"},
        preflight={"decision": "suggest", "risk_level": "low", "required_review": False},
        stability={
            "state": "converging",
            "signals": {"confidence": "high", "safety_signals": []},
        },
    )
    low_confidence = make_control_decision(
        {"run_id": "low-confidence"},
        preflight={"decision": "allow", "risk_level": "low", "required_review": False},
        stability={
            "state": "converging",
            "signals": {"confidence": "low", "safety_signals": []},
        },
    )
    missing_safety_evidence = make_control_decision(
        {"run_id": "missing-safety"},
        preflight={"decision": "allow", "risk_level": "low", "required_review": False},
        stability={"state": "converging", "signals": {"confidence": "high"}},
    )
    safety_signal = make_control_decision(
        {"run_id": "safety-signal"},
        preflight={"decision": "allow", "risk_level": "low", "required_review": False},
        stability={
            "state": "converging",
            "signals": {
                "confidence": "high",
                "safety_signals": [{"category": "security", "sequence": 2}],
            },
        },
    )

    assert safe.decision == "allow"
    assert missing_preflight.decision == "suggest"
    assert suggested_preflight.decision == "suggest"
    assert low_confidence.decision == "suggest"
    assert missing_safety_evidence.decision == "suggest"
    assert safety_signal.decision == "needs_review"


def test_control_decision_requires_complete_analyzer_and_safety_evidence_to_allow() -> None:
    from promptcontrollab.control_analysis import make_control_decision

    run = _fully_observed_run("evidence-gate")
    preflight, attribution, stability, events = _complete_safe_control_evidence(run)

    asserted_stability = make_control_decision(
        run,
        preflight=preflight,
        attribution=attribution,
        stability={
            "state": "converging",
            "signals": {"confidence": "high", "safety_signals": []},
        },
        events=events,
    )
    missing_attribution = make_control_decision(
        run,
        preflight=preflight,
        stability=stability,
        events=events,
    )
    asserted_preflight = make_control_decision(
        run,
        preflight={"decision": "allow", "risk_level": "low", "required_review": False},
        attribution=attribution,
        stability=stability,
        events=events,
    )
    complete = make_control_decision(
        run,
        preflight=preflight,
        attribution=attribution,
        stability=stability,
        events=events,
    )

    assert asserted_stability.decision == "suggest"
    assert missing_attribution.decision == "suggest"
    assert asserted_preflight.decision == "suggest"
    assert complete.decision == "allow"


def test_analysis_is_deterministic_and_does_not_mutate_inputs() -> None:
    from promptcontrollab.control_analysis import analyze_attribution, analyze_stability

    run: dict[str, Any] = {"run_id": "stable", "prompt_hash": "sha256:x", "metadata": {}}
    events: list[dict[str, Any]] = [
        _event(2, "tests/result", passed=True),
        _event(1, "step/completed", status="completed"),
    ]
    original_run = {"run_id": "stable", "prompt_hash": "sha256:x", "metadata": {}}
    original_events = [dict(item) for item in events]

    first_attribution = analyze_attribution(run, events).to_json()
    second_attribution = analyze_attribution(run, events).to_json()
    first_stability = analyze_stability(run, events).to_json()
    second_stability = analyze_stability(run, events).to_json()

    assert first_attribution == second_attribution
    assert first_stability == second_stability
    assert run == original_run
    assert events == original_events
