from __future__ import annotations

import json
from pathlib import Path

import pytest

from promptcontrollab.cli import main
from promptcontrollab.plugin_installer import install_plugin
from promptcontrollab.providers import ProviderResponse


def test_providers_cli_lists_and_inspects_without_exposing_key(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "private-deepseek-key")

    assert main(["providers", "list", "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert "deepseek" in [item["id"] for item in listed]
    assert "private-deepseek-key" not in json.dumps(listed)

    assert main(["providers", "inspect", "deepseek", "--json"]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["configured"] is True
    assert "private-deepseek-key" not in json.dumps(inspected)


def test_providers_doctor_is_offline_unless_live_is_explicit(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "private-deepseek-key")
    called = False

    def fake_call(**kwargs: object) -> ProviderResponse:
        nonlocal called
        called = True
        raise AssertionError("offline doctor must not call provider")

    monkeypatch.setattr("promptcontrollab.providers.call_provider", fake_call)
    assert main(["providers", "doctor", "deepseek", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["live_checked"] is False
    assert called is False


def test_control_model_authorization_calls_provider_and_persists_safe_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    response = ProviderResponse(
        provider="deepseek",
        model_id="deepseek-observed",
        output_text="Public answer",
        request_id="request-1",
        usage={"input_tokens": 7, "output_tokens": 2, "total_tokens": 9},
        latency_ms=12.0,
        request_sha256="sha256:request",
        response_sha256="sha256:response",
        provenance_evidence=[{"type": "observed_model_field"}],
        raw_metadata={
            "finish_reason": "stop",
            "reasoning": "hidden chain of thought must not persist",
        },
        warnings=[],
    )

    def fake_call(**kwargs: object) -> ProviderResponse:
        assert kwargs["provider"] == "deepseek"
        assert kwargs["model"] == "deepseek-requested"
        assert kwargs["prompt"] == "Explain the result."
        return response

    monkeypatch.setattr("promptcontrollab.cli.call_provider", fake_call)
    out = tmp_path / "control"
    assert (
        main(
            [
                "control",
                "--prompt",
                "Explain the result.",
                "--authorization",
                "model",
                "--provider",
                "deepseek",
                "--model",
                "deepseek-requested",
                "--out",
                str(out),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["decision"]["decision"] == "suggest"
    provider_result = json.loads((out / "provider_result.json").read_text(encoding="utf-8"))
    assert provider_result["model_id"] == "deepseek-observed"
    assert provider_result["output_text"] == "Public answer"
    persisted = "\n".join(
        path.read_text(encoding="utf-8")
        for path in out.iterdir()
        if path.is_file()
    )
    assert "request-1" in persisted
    assert "Explain the result." not in persisted
    assert "hidden chain of thought must not persist" not in persisted
    events = [json.loads(line) for line in (out / "events.jsonl").read_text().splitlines()]
    assert [event["event_type"] for event in events] == [
        "session/start",
        "preflight/completed",
        "agent/request",
        "agent/response",
        "session/finalized",
    ]
    assert events[2]["payload"]["prompt_hash"].startswith("sha256:")
    assert events[3]["payload"]["response_sha256"] == "sha256:response"
    attribution = json.loads((out / "attribution.json").read_text(encoding="utf-8"))
    stability = json.loads((out / "stability.json").read_text(encoding="utf-8"))
    assert len(attribution["factors"]) == 10
    assert "thresholds" in stability["signals"]


def test_control_model_requires_provider_and_model_before_creating_run(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = tmp_path / "missing-model-metadata"

    assert (
        main(
            [
                "control",
                "--prompt",
                "Explain the result.",
                "--authorization",
                "model",
                "--out",
                str(out),
            ]
        )
        == 2
    )

    assert "--provider and --model" in capsys.readouterr().err
    assert not out.exists()


@pytest.mark.parametrize(
    ("severity", "expected_decision"),
    [("high", "blocked"), ("medium", "review_required")],
)
def test_control_model_preflight_gate_never_calls_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    severity: str,
    expected_decision: str,
) -> None:
    policy = tmp_path / f"{severity}.policy.yaml"
    policy.write_text(
        "\n".join(
            [
                "profile: general",
                "block_at: high",
                "review_at: medium",
                f"rule.execution_gate.severity: {severity}",
                "rule.execution_gate.category: authorization",
                "rule.execution_gate.patterns: gated-target",
                "rule.execution_gate.message: Explicit approval is required.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    called = False

    def unexpected_call(**kwargs: object) -> ProviderResponse:
        nonlocal called
        called = True
        raise AssertionError(f"provider must not be called: {kwargs}")

    monkeypatch.setattr("promptcontrollab.cli.call_provider", unexpected_call)
    out = tmp_path / f"control-{severity}"

    assert (
        main(
            [
                "control",
                "--prompt",
                "Inspect gated-target before execution.",
                "--authorization",
                "model",
                "--provider",
                "deepseek",
                "--model",
                "deepseek-test",
                "--policy",
                str(policy),
                "--out",
                str(out),
                "--json",
            ]
        )
        == 0
    )

    assert called is False
    assert not (out / "provider_result.json").exists()
    decision = json.loads((out / "decision.json").read_text(encoding="utf-8"))
    assert decision["decision"] == expected_decision


def test_harness_cli_init_replay_and_report(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    assert main(["harness", "init", "--project", str(project), "--json"]) == 0
    initialized = json.loads(capsys.readouterr().out)
    assert initialized["written"]

    session = tmp_path / "session.jsonl"
    session.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "seq": 1,
                        "type": "session/created",
                        "data": {"sessionId": "session-cli"},
                    }
                ),
                json.dumps(
                    {
                        "seq": 2,
                        "type": "user/message",
                        "data": {
                            "content": [
                                {"type": "text", "text": "Inspect src/app.py and run tests."}
                            ]
                        },
                    }
                ),
                json.dumps({"seq": 3, "type": "turn/end", "data": {"turn": 1}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    run_dir = project / "runs" / "replayed"
    assert (
        main(
            [
                "harness",
                "replay",
                "--session",
                str(session),
                "--out",
                str(run_dir),
                "--json",
            ]
        )
        == 0
    )
    replayed = json.loads(capsys.readouterr().out)
    assert replayed["harness_session_id"] == "session-cli"

    assert (
        main(
            [
                "harness",
                "report",
                "--runs",
                str(project / "runs"),
                "--session",
                "session-cli",
                "--json",
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["report_md"].endswith("report.md")


def test_install_plugin_accepts_deepseek_harness(tmp_path: Path) -> None:
    target = tmp_path / "deepseek-harness"
    assert main(["install-plugin", "deepseek-harness", "--target", str(target)]) == 0
    assert (target / "package.json").is_file()
    assert (target / "src" / "index.ts").is_file()


def test_install_plugin_deepseek_harness_default_and_all_layout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("promptcontrollab.plugin_installer.Path.home", lambda: tmp_path)

    installed = install_plugin("deepseek-harness")
    default_target = tmp_path / ".prompt_control_lab" / "deepseek-harness"
    assert installed["target"] == str(default_target)
    assert (default_target / "package.json").is_file()

    all_root = tmp_path / "all"
    all_result = install_plugin("all", target=all_root)
    installed_names = {str(item["plugin"]) for item in all_result["installed"]}
    assert installed_names == {
        "codex",
        "cursor",
        "claude-code",
        "github-action",
        "deepseek-harness",
    }
    assert (all_root / "deepseek-harness" / "src" / "index.ts").is_file()
