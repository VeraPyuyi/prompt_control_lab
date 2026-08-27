from __future__ import annotations

import io
from pathlib import Path

from promptcontrollab.cli import main
from promptcontrollab.files import read_json, read_jsonl


class _InteractiveInput(io.StringIO):
    def isatty(self) -> bool:
        return True


class _NonInteractiveInput(io.StringIO):
    def isatty(self) -> bool:
        return False


def test_control_requires_explicit_authorization_when_noninteractive(
    tmp_path: Path,
    monkeypatch: object,
    capsys: object,
) -> None:
    monkeypatch.setattr("promptcontrollab.cli.legacy.sys.stdin", _NonInteractiveInput())  # type: ignore[attr-defined]
    result = main(
        [
            "control",
            "--prompt",
            "Answer the question.",
            "--out",
            str(tmp_path / "run"),
        ]
    )
    assert result == 2
    assert "--authorization is required in non-interactive mode" in capsys.readouterr().err  # type: ignore[attr-defined]
    assert not (tmp_path / "run").exists()


def test_control_inspect_writes_complete_artifact_skeleton(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "inspect"
    assert (
        main(
            [
                "control",
                "--prompt",
                "Summarize the input in one sentence.",
                "--authorization",
                "inspect",
                "--out",
                str(run_dir),
                "--provider",
                "deepseek",
                "--model",
                "fixture-model",
            ]
        )
        == 0
    )

    expected = {
        "control_run.json",
        "events.jsonl",
        "preflight.json",
        "attribution.json",
        "stability.json",
        "decision.json",
        "report.md",
        "report.html",
    }
    assert expected.issubset({path.name for path in run_dir.iterdir()})
    run = read_json(run_dir / "control_run.json")
    assert run["schema"] == "prompt_control_lab.control_run.v1"
    assert run["authorization"] == "inspect"
    assert run["status"] == "finalized"
    assert run["provider"] == "deepseek"
    assert read_json(run_dir / "decision.json")["decision"] == "inspect_only"
    assert read_json(run_dir / "stability.json")["state"] == "insufficient_evidence"
    events = read_jsonl(run_dir / "events.jsonl")
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert [event["event_type"] for event in events] == [
        "session/start",
        "preflight/completed",
        "session/finalized",
    ]
    assert (run_dir.parent / ".prompt_control_lab" / "runs.sqlite3").exists()


def test_control_default_capture_persists_hashes_not_prompt_text(tmp_path: Path) -> None:
    raw_prompt = "RAW-PROMPT-MARKER-DO-NOT-PERSIST"
    run_dir = tmp_path / "runs" / "redacted"
    assert (
        main(
            [
                "control",
                "--prompt",
                raw_prompt,
                "--authorization",
                "inspect",
                "--out",
                str(run_dir),
            ]
        )
        == 0
    )

    preflight = read_json(run_dir / "preflight.json")
    assert preflight["capture_mode"] == "redacted"
    assert preflight["improved_prompt"] == "[REDACTED]"
    assert preflight["prompt_hash"].startswith("sha256:")
    assert preflight["improved_prompt_hash"].startswith("sha256:")
    persisted = (run_dir / "preflight.json").read_text(encoding="utf-8") + (
        run_dir / "events.jsonl"
    ).read_text(encoding="utf-8")
    assert raw_prompt not in persisted


def test_control_reuses_guard_policy_and_blocks_high_risk_prompt(tmp_path: Path) -> None:
    policy = tmp_path / "guard.policy.yaml"
    policy.write_text(
        "\n".join(
            [
                "profile: coding",
                "block_at: high",
                "review_at: medium",
                "rule.forbidden_zone.severity: high",
                "rule.forbidden_zone.category: custom_policy",
                "rule.forbidden_zone.patterns: forbidden-zone",
                "rule.forbidden_zone.message: This target requires manual approval.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    run_dir = tmp_path / "runs" / "blocked"
    assert (
        main(
            [
                "control",
                "--prompt",
                "Modify forbidden-zone and run tests.",
                "--authorization",
                "agent-scoped",
                "--policy",
                str(policy),
                "--out",
                str(run_dir),
            ]
        )
        == 0
    )
    preflight = read_json(run_dir / "preflight.json")
    assert preflight["decision"] == "block"
    assert preflight["details"]["guard"]["risk_categories"] == ["custom_policy"]
    assert read_json(run_dir / "decision.json")["decision"] == "blocked"


def test_control_model_authorization_requires_provider_and_model(
    tmp_path: Path,
    capsys: object,
) -> None:
    run_dir = tmp_path / "runs" / "model"
    result = main(
        [
            "control",
            "--prompt",
            "Answer the question.",
            "--authorization",
            "model",
            "--out",
            str(run_dir),
        ]
    )
    assert result == 2
    assert "--provider and --model" in capsys.readouterr().err  # type: ignore[attr-defined]
    assert not run_dir.exists()


def test_control_tty_previews_then_asks_for_authorization(
    tmp_path: Path,
    monkeypatch: object,
    capsys: object,
) -> None:
    monkeypatch.setattr(  # type: ignore[attr-defined]
        "promptcontrollab.cli.legacy.sys.stdin",
        _InteractiveInput("inspect\n"),
    )
    run_dir = tmp_path / "runs" / "interactive"
    assert (
        main(
            [
                "control",
                "--prompt",
                "Summarize the input.",
                "--out",
                str(run_dir),
            ]
        )
        == 0
    )
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "Preflight preview" in output
    assert "Estimated prompt tokens:" in output
    assert "Provider/model: not selected" in output
    assert "inspect: diagnostics only; no model, tool, or file execution" in output
    assert "agent-scoped: adapter actions constrained by project policy" in output
    assert "PromptControlLab does not sandbox agent file access" in output
    assert "Authorization [inspect/model/agent-scoped/agent-full]" in output
    assert read_json(run_dir / "control_run.json")["authorization"] == "inspect"
