from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from promptcontrollab.ui.data import list_runs, load_run_detail


def test_control_navigation_has_fixed_order_and_before_default() -> None:
    from promptcontrollab.ui import app

    assert app.PRIMARY_VIEW_ORDER == (
        "before",
        "run",
        "mechanism",
        "stability",
        "training",
        "evidence",
        "decision",
        "history",
    )
    assert app.DEFAULT_PRIMARY_VIEW == "before"
    assert app._ordered_views("history") == list(app.PRIMARY_VIEW_ORDER)
    assert app._resolve_primary_view("") == "before"
    assert app._resolve_primary_view("research") == "evidence"


def test_control_navigation_labels_are_localized() -> None:
    from promptcontrollab.ui import app

    assert app.primary_view_labels("en") == [
        "Before",
        "Run",
        "Mechanism",
        "Stability",
        "Training Gate",
        "Evidence Scope",
        "Decision",
        "History",
    ]
    assert app.primary_view_labels("zh") == [
        "执行前",
        "运行中",
        "机制解释",
        "稳定性",
        "训练门禁",
        "证据边界",
        "决策",
        "历史",
    ]


def test_legacy_research_and_peoc_render_under_evidence_scope() -> None:
    from promptcontrollab.ui import app

    assert app.legacy_sections_for("before") == ("guard", "tutorial")
    assert app.legacy_sections_for("run") == ("workflows",)
    assert app.legacy_sections_for("stability") == ("drift", "audit")
    assert app.legacy_sections_for("training") == ("posttrain",)
    assert app.legacy_sections_for("decision") == ("report",)
    assert app.legacy_sections_for("history") == ("history",)
    assert app.legacy_sections_for("evidence") == ("research",)
    assert all(
        "research" not in app.legacy_sections_for(view)
        for view in app.PRIMARY_VIEW_ORDER
        if view != "evidence"
    )


def test_interpretability_and_posttrain_artifacts_are_loaded_for_core_views(
    tmp_path: Path,
) -> None:
    from promptcontrollab.ui.data import evidence_matrix_rows, interpretability_rows

    run = tmp_path / "runs" / "diagnostic"
    _write_json(
        run / "interpretability_report.json",
        {
            "findings": [
                {
                    "adapter": "turnpike_a800",
                    "interpretation_role": "stability",
                    "observation": "Decay differs by task family.",
                    "explanation": "Task heterogeneity changes the trajectory signature.",
                    "confidence": "medium",
                    "scope": "Recorded tasks.",
                    "claim_boundary": "Not global convergence proof.",
                    "next_action": "Add matched seeds.",
                }
            ]
        },
    )
    _write_json(
        run / "evidence_matrix.json",
        {
            "diagnostics": [
                {
                    "adapter": "turnpike_a800",
                    "support_status": "observed",
                    "interpretation_role": "stability",
                }
            ]
        },
    )
    _write_json(run / "posttrain_gate.json", {"decision": "needs_review"})
    _write_json(run / "checkpoint_comparison.json", {"score_delta": 0.1})
    _write_json(
        run / "mechanism_attribution.json",
        {"findings": [{"dimension": "trajectory_stability", "confidence": "medium"}]},
    )

    detail = load_run_detail(run)

    assert detail["posttrain_gate"]["decision"] == "needs_review"
    assert detail["checkpoint_comparison"]["score_delta"] == 0.1
    assert interpretability_rows(detail)[0]["role"] == "stability"
    assert evidence_matrix_rows(detail)[0]["status"] == "observed"


def test_control_artifacts_load_safely_and_make_a_control_only_run_visible(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "deepseek-session"
    _write_json(
        run / "control_run.json",
        {
            "run_id": "control-1",
            "status": "finalized",
            "provider": "deepseek",
            "model": "deepseek-chat",
            "agent": "deepseek-harness",
            "metadata": {"api_key": "secret-key"},
        },
    )
    _write_json(run / "preflight.json", {"decision": "allow", "risk_level": "low"})
    _write_json(run / "decision.json", {"decision": "allow", "next_action": "Review."})
    _write_json(run / "provider_result.json", {"usage": {"total_tokens": 21}})
    _write_json(run / "audit_result.json", {"changed_files": ["src/app.py"]})
    _write_json(run / "attribution.json", {"status": "changes_observed"})
    _write_json(run / "stability.json", {"state": "converging"})
    _write(run / "report.md", "# Control report\n")
    _write(run / "report.html", "<h1>Control report</h1>\n")
    _write(
        run / "events.jsonl",
        "\n".join(
            [
                json.dumps(
                    {
                        "sequence": 3,
                        "event_type": "agent/response",
                        "payload": {"reasoning": "private chain", "total_tokens": 21},
                    }
                ),
                "{malformed-json",
                json.dumps(
                    {
                        "sequence": 1,
                        "event_type": "session/start",
                        "payload": {"api_key": "event-secret"},
                    }
                ),
                json.dumps(
                    {
                        "sequence": 2,
                        "event_type": "harness/turn-start",
                        "payload": {"turn": 1},
                    }
                ),
            ]
        )
        + "\n",
    )

    assert list_runs(tmp_path / "runs") == [{"name": run.name, "path": str(run)}]

    detail = load_run_detail(run)

    assert detail["has_artifacts"] is True
    assert detail["control_run"]["metadata"]["api_key"] == "[REDACTED]"
    assert [event["sequence"] for event in detail["events"]] == [1, 2, 3]
    assert detail["events"][0]["payload"]["api_key"] == "[REDACTED]"
    assert detail["events"][2]["payload"]["reasoning"] == "[REDACTED]"
    assert {
        "control_run.json",
        "events.jsonl",
        "preflight.json",
        "attribution.json",
        "stability.json",
        "decision.json",
        "provider_result.json",
        "audit_result.json",
        "report.md",
        "report.html",
    }.issubset(set(detail["artifacts"]))


def test_control_artifact_loading_tolerates_missing_files(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "started"
    _write_json(run / "control_run.json", {"run_id": "started-1", "status": "initialized"})

    detail = load_run_detail(run)

    assert detail["events"] == []
    assert detail["preflight"] == {}
    assert detail["attribution"] == {}
    assert detail["stability"] == {}
    assert detail["decision"] == {}
    assert detail["provider_result"] == {}


def test_display_helpers_remove_hidden_reasoning_prompts_and_credentials() -> None:
    from promptcontrollab.ui.data import redact_for_display, safe_display_text

    payload = {
        "api_key": "sk-private-value-1234567890",
        "reasoning": "hidden chain of thought",
        "reasoning_content": "private analysis",
        "prompt": "raw user prompt",
        "authorization": "agent-full",
        "usage": {"input_tokens": 5, "reasoning_tokens": 2},
        "message": "Authorization: Bearer secret-bearer-token-1234",
    }

    safe = redact_for_display(payload)
    rendered = safe_display_text(payload)

    assert safe["api_key"] == "[REDACTED]"
    assert safe["reasoning"] == "[REDACTED]"
    assert safe["reasoning_content"] == "[REDACTED]"
    assert safe["prompt"] == "[REDACTED]"
    assert safe["authorization"] == "agent-full"
    assert safe["usage"] == {"input_tokens": 5, "reasoning_tokens": 2}
    assert "hidden chain" not in rendered
    assert "private analysis" not in rendered
    assert "raw user prompt" not in rendered
    assert "secret-bearer" not in rendered


def test_deepseek_harness_view_derives_observable_control_run_evidence(tmp_path: Path) -> None:
    from promptcontrollab.ui.data import deepseek_harness_view

    run = tmp_path / "run"
    _write(run / "report.md", "# Report\n")
    _write(run / "report.html", "<h1>Report</h1>\n")
    detail: dict[str, Any] = {
        "path": str(run),
        "control_run": {
            "run_id": "control-1",
            "status": "finalized",
            "authorization": "agent",
            "provider": "deepseek",
            "model": "deepseek-chat",
            "agent": "deepseek-harness",
            "metadata": {"harness_session_id": "session-7"},
        },
        "preflight": {
            "decision": "allow",
            "risk_level": "low",
            "required_review": False,
            "summary": "No configured policy gate matched.",
        },
        "events": [
            _event(11, "session/finalized", status="completed"),
            _event(1, "session/start", status="started"),
            _event(2, "harness/turn-start", turn=1),
            _event(3, "preflight/completed", decision="allow", risk_level="low"),
            _event(
                4,
                "tools/pre-execute",
                tool="read",
                decision="allow",
                arguments={"path": "src/app.py"},
            ),
            _event(
                5,
                "tools/pre-execute",
                tool="read",
                decision="allow",
                arguments={"path": "src/app.py"},
            ),
            _event(
                6,
                "tools/pre-execute",
                tool="read",
                decision="allow",
                arguments={"path": "src/app.py"},
            ),
            _event(7, "tools/post-execute", tool="edit", path="src/app.py"),
            _event(8, "test/completed", tool="pytest", passed=True),
            _event(
                9,
                "agent/response",
                provider="deepseek",
                model="deepseek-chat",
                usage={"input_tokens": 12, "output_tokens": 9, "total_tokens": 21},
                latency_ms=48.5,
                cost_usd=0.004,
            ),
            _event(10, "harness/guard", guard="repeat-tool-reminder"),
        ],
        "provider_result": {
            "provider": "deepseek",
            "requested_model": "deepseek-chat",
            "model_id": "deepseek-chat-202608",
            "request_id": "request-9",
            "usage": {"input_tokens": 12, "output_tokens": 9, "total_tokens": 21},
            "latency_ms": 48.5,
            "cost_usd": 0.004,
            "provenance_evidence": [
                {"type": "observed_model_field", "confidence": 1.0}
            ],
            "raw_metadata": {"reasoning": "must not render"},
        },
        "attribution": {
            "status": "changes_observed",
            "summary": "Observed factors changed; this does not establish causation.",
            "factors": [{"factor": "tools", "changed": True, "impact": "medium"}],
        },
        "stability": {
            "state": "stalled",
            "summary": "Recorded calls repeat without stable progress.",
            "signals": {
                "confidence": "medium",
                "observed_events": 11,
                "repeated_tool_calls": {
                    "tool": "read",
                    "max_repetitions": 3,
                    "observed_tools": ["read"],
                },
                "request_failures": {"errors": 0, "retries": 0},
                "file_churn": {
                    "max_edits_per_file": 1,
                    "files": [{"path": "src/app.py", "edits": 1}],
                },
                "test_trend": {"outcomes": ["pass"], "transitions": 0, "final": "pass"},
                "progress": {"completed_markers": 2},
                "harness_guard_signals": [
                    {"kind": "repeat_tool", "source": "repeat-tool-reminder", "sequence": 10}
                ],
            },
        },
        "decision": {
            "decision": "suggest",
            "next_action": "Inspect the repeated read calls.",
            "reasons": ["Observable repetition crossed the configured threshold."],
        },
        "audit": {
            "changed_files": ["src/app.py", "tests/test_app.py"],
            "tests_run": ["pytest"],
            "tests_passed": True,
        },
    }

    view = deepseek_harness_view(detail)

    assert view["identity"] == {
        "run_id": "control-1",
        "session_id": "session-7",
        "status": "finalized",
        "authorization": "agent",
        "agent": "deepseek-harness",
    }
    assert [row["sequence"] for row in view["timeline"]] == list(range(1, 12))
    assert view["timeline"][1]["turn"] == 1
    assert view["gates"][0]["scope"] == "prompt"
    assert {row["scope"] for row in view["gates"]} == {"prompt", "tool"}
    assert view["provider"]["observed_model"] == "deepseek-chat-202608"
    assert view["provider"]["provenance"][0]["type"] == "observed_model_field"
    assert view["usage"]["total_tokens"] == 21
    assert view["usage"]["latency_ms"] == pytest.approx(48.5)
    assert view["usage"]["cost"] == pytest.approx(0.004)
    assert view["repeated_tool_calls"] == [
        {
            "tool": "read",
            "count": 3,
            "start_sequence": 4,
            "end_sequence": 6,
            "same_arguments": True,
        }
    ]
    assert view["stability"]["state"] == "stalled"
    assert view["stability"]["confidence"] == "medium"
    assert {row["kind"] for row in view["changes"]} == {"file", "test"}
    assert view["guard_signals"] == [
        {"kind": "repeat_tool", "source": "repeat-tool-reminder", "sequence": 10}
    ]
    assert view["recommendation"]["decision"] == "suggest"
    assert "does not prove causality or safety" in view["recommendation"]["boundary"]
    assert {row["name"] for row in view["report_links"]} == {"report.md", "report.html"}
    assert "must not render" not in json.dumps(view, sort_keys=True)


def test_control_event_timeline_chart_uses_sequence_and_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from promptcontrollab.ui import charts

    captured: dict[str, Any] = {}

    def fake_scatter(rows: list[dict[str, object]], **kwargs: object) -> SimpleNamespace:
        captured["rows"] = rows
        captured["kwargs"] = kwargs
        return SimpleNamespace(rows=rows, kwargs=kwargs)

    monkeypatch.setattr(charts, "_plotly_express", lambda: SimpleNamespace(scatter=fake_scatter))

    figure = charts.control_event_timeline(
        [
            {"sequence": 2, "phase": "turn", "event": "harness/turn-start"},
            {"sequence": 1, "phase": "session", "event": "session/start"},
        ],
        title="Run timeline",
    )

    assert [row["sequence"] for row in figure.rows] == [1, 2]
    assert captured["kwargs"] == {
        "x": "sequence",
        "y": "phase",
        "color": "event",
        "hover_name": "event",
        "title": "Run timeline",
    }


def test_control_signal_chart_renders_bounded_observable_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from promptcontrollab.ui import charts

    captured: dict[str, Any] = {}

    def fake_bar(rows: list[dict[str, object]], **kwargs: object) -> SimpleNamespace:
        captured["rows"] = rows
        captured["kwargs"] = kwargs
        return SimpleNamespace(rows=rows, kwargs=kwargs)

    monkeypatch.setattr(charts, "_plotly_express", lambda: SimpleNamespace(bar=fake_bar))

    figure = charts.control_signal_bar(
        [
            {"signal": "request errors", "value": 1},
            {"signal": "repeated calls", "value": 3},
        ],
        title="Observable signals",
    )

    assert figure.rows == [
        {"signal": "repeated calls", "value": 3},
        {"signal": "request errors", "value": 1},
    ]
    assert captured["kwargs"] == {
        "x": "signal",
        "y": "value",
        "title": "Observable signals",
    }


def test_streamlit_entry_selects_before_from_fixed_primary_navigation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from promptcontrollab.ui import app

    rendered: list[str] = []

    class FakeSidebar:
        def text_input(self, _label: str, value: str) -> str:
            return value

        def selectbox(
            self,
            label: str,
            options: list[str],
            index: int = 0,
        ) -> str:
            if label == "Language / 语言":
                return "English"
            return options[index]

        def checkbox(self, _label: str, value: bool = False) -> bool:
            return value

        def caption(self, _value: str) -> None:
            return None

    class FakeStreamlit:
        sidebar = FakeSidebar()

        def __init__(self) -> None:
            self.query_params: dict[str, str] = {}
            self.navigation: dict[str, object] = {}

        def set_page_config(self, **_kwargs: object) -> None:
            return None

        def markdown(self, *_args: object, **_kwargs: object) -> None:
            return None

        def warning(self, _message: str) -> None:
            return None

        def code(self, *_args: object, **_kwargs: object) -> None:
            return None

        def radio(
            self,
            label: str,
            options: list[str],
            *,
            index: int,
            horizontal: bool,
            label_visibility: str,
        ) -> str:
            self.navigation = {
                "label": label,
                "options": options,
                "index": index,
                "horizontal": horizontal,
                "label_visibility": label_visibility,
            }
            return options[index]

    fake = FakeStreamlit()
    monkeypatch.setattr(app, "_streamlit", lambda: fake)
    monkeypatch.setattr(app, "list_runs", lambda _path: [])
    monkeypatch.setattr(
        app,
        "_render_view",
        lambda _st, name, *_args, **_kwargs: rendered.append(name),
    )

    app.main()

    assert fake.navigation == {
        "label": "Primary navigation",
        "options": app.primary_view_labels("en"),
        "index": 0,
        "horizontal": True,
        "label_visibility": "collapsed",
    }
    assert rendered == ["before"]


def test_recommendation_card_escapes_values_and_preserves_evidence_boundary() -> None:
    from promptcontrollab.ui.components import recommendation_card_html

    rendered = recommendation_card_html(
        decision="needs_review<script>",
        next_action="Inspect <files>.",
        reasons=["Observed change only."],
        boundary="This does not prove causality or safety.",
    )

    assert "pcl-recommendation needs-review" in rendered
    assert "needs_review&lt;script&gt;" in rendered
    assert "Inspect &lt;files&gt;." in rendered
    assert "Observed change only." in rendered
    assert "This does not prove causality or safety." in rendered
    assert "<script>" not in rendered


def _event(sequence: int, event_type: str, **payload: object) -> dict[str, object]:
    return {
        "sequence": sequence,
        "event_type": event_type,
        "timestamp": f"2026-08-23T00:00:{sequence:02d}Z",
        "payload": payload,
    }


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: object) -> None:
    _write(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
