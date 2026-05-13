from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from promptcontrollab.cli import main
from promptcontrollab.files import write_jsonl


def test_cli_example_flow(tmp_path: Path) -> None:
    demo = tmp_path / "demo"
    assert main(["init", "--path", str(demo)]) == 0
    assert (
        main(
            [
                "split",
                "--data",
                str(demo / "examples" / "tasks.jsonl"),
                "--out",
                str(demo / "runs" / "candidate"),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "eval",
                "--data",
                str(demo / "examples" / "tasks.jsonl"),
                "--predictions",
                str(demo / "examples" / "predictions_baseline.jsonl"),
                "--out",
                str(demo / "runs" / "baseline"),
                "--method",
                "baseline",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "eval",
                "--data",
                str(demo / "examples" / "tasks.jsonl"),
                "--predictions",
                str(demo / "examples" / "predictions_candidate.jsonl"),
                "--out",
                str(demo / "runs" / "candidate"),
                "--method",
                "candidate",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "stats",
                "--baseline",
                str(demo / "runs" / "baseline" / "predictions.jsonl"),
                "--candidate",
                str(demo / "runs" / "candidate" / "predictions.jsonl"),
                "--out",
                str(demo / "runs" / "candidate" / "stats.json"),
                "--bootstrap-samples",
                "10",
                "--permutation-samples",
                "10",
            ]
        )
        == 0
    )
    assert main(["report", "--run", str(demo / "runs" / "candidate")]) == 0
    assert (demo / "runs" / "candidate" / "report.md").exists()


def test_cli_quick_analyze_explain_and_report(tmp_path: Path) -> None:
    demo = tmp_path / "demo"
    run = demo / "runs" / "quick"
    assert main(["init", "--path", str(demo)]) == 0

    assert (
        main(
            [
                "analyze",
                "--data",
                str(demo / "examples" / "tasks.jsonl"),
                "--baseline-predictions",
                str(demo / "examples" / "predictions_baseline.jsonl"),
                "--candidate-predictions",
                str(demo / "examples" / "predictions_candidate.jsonl"),
                "--metric",
                "exact_match",
                "--out",
                str(run),
                "--bootstrap-samples",
                "10",
                "--permutation-samples",
                "10",
                "--explain-level",
                "plain",
            ]
        )
        == 0
    )

    expected_files = [
        "splits.json",
        "baseline/metrics.json",
        "candidate/metrics.json",
        "stats.json",
        "explanation.json",
        "report.md",
        "report.html",
    ]
    for relative_path in expected_files:
        assert (run / relative_path).exists()

    explanation = json.loads((run / "explanation.json").read_text(encoding="utf-8"))
    assert explanation["level"] == "plain"
    assert explanation["overall_summary"]["verdict"] in {"keep", "review", "hold"}
    assert explanation["data_hygiene"]["has_leakage"] is False
    assert explanation["example_changes"]["fixed_ids"] == ["arith-2"]

    report = (run / "report.md").read_text(encoding="utf-8")
    assert "Deployment Recommendation" in report
    assert "Recommendation:" in report
    assert "Quick Mode Explanation" in report
    assert "What this means" in report
    html = (run / "report.html").read_text(encoding="utf-8")
    assert "recommendation-card" in html
    assert "dashboard-card" in html
    assert "Prompt-only comparison validity" in html
    assert "Gate failures/review items" in html
    assert "Full Markdown Audit" in html
    assert "Sample changes" in html
    assert "arith-2" in html

    assert main(["explain", "--run", str(run), "--level", "technical"]) == 0
    technical = json.loads((run / "explanation.json").read_text(encoding="utf-8"))
    assert technical["level"] == "technical"
    assert "artifact_paths" in technical


def test_cli_gate_uses_policy_thresholds(tmp_path: Path) -> None:
    demo = tmp_path / "demo"
    run = demo / "runs" / "quick"
    policy = demo / "gate.policy.yaml"
    assert main(["init", "--path", str(demo)]) == 0
    assert (
        main(
            [
                "analyze",
                "--data",
                str(demo / "examples" / "tasks.jsonl"),
                "--baseline-predictions",
                str(demo / "examples" / "predictions_baseline.jsonl"),
                "--candidate-predictions",
                str(demo / "examples" / "predictions_candidate.jsonl"),
                "--out",
                str(run),
                "--bootstrap-samples",
                "10",
                "--permutation-samples",
                "10",
            ]
        )
        == 0
    )
    policy.write_text(
        "\n".join(
            [
                "min_candidate_score: 0.9",
                "max_regression: 0.0",
                "require_adjusted_p_below: 1.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert main(["gate", "--run", str(run), "--policy", str(policy)]) == 0
    gate = json.loads((run / "gate_result.json").read_text(encoding="utf-8"))
    assert gate["status"] == "pass"
    assert gate["plain_summary"].startswith("Deployment recommendation:")
    assert gate["checks"]["candidate_score"]["passed"] is True


def test_cli_gate_blocks_model_mismatch_when_policy_requires_it(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    (run / "manifest.json").write_text(
        json.dumps(
            {
                "baseline_model": {
                    "provider": "openai",
                    "model_id": "gpt-4o",
                    "verified": True,
                    "warnings": [],
                },
                "candidate_model": {
                    "provider": "openai",
                    "model_id": "gpt-5.2",
                    "verified": True,
                    "warnings": [],
                },
            }
        ),
        encoding="utf-8",
    )
    (run / "candidate").mkdir()
    (run / "candidate" / "metrics.json").write_text(
        json.dumps({"count": 1, "mean_score": 1.0, "by_slice": {"default": 1.0}}),
        encoding="utf-8",
    )
    policy = tmp_path / "gate.policy.yaml"
    policy.write_text(
        "\n".join(
            [
                "min_candidate_score: 0.9",
                "allowed_models: gpt-4o,gpt-5.2",
                "allowed_providers: openai",
                "block_if_model_mismatch: true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert main(["gate", "--run", str(run), "--policy", str(policy)]) == 0

    gate = json.loads((run / "gate_result.json").read_text(encoding="utf-8"))
    assert gate["status"] == "fail"
    assert gate["checks"]["model_provenance"]["passed"] is False
    assert "model_mismatch" in gate["checks"]["model_provenance"]["violations"]


def test_cli_gate_blocks_unknown_model_when_allow_list_is_set(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    (run / "manifest.json").write_text(json.dumps({"method": "candidate"}), encoding="utf-8")
    (run / "metrics.json").write_text(
        json.dumps({"count": 1, "mean_score": 1.0, "by_slice": {"default": 1.0}}),
        encoding="utf-8",
    )
    policy = tmp_path / "gate.policy.yaml"
    policy.write_text("allowed_models: gpt-5.2\n", encoding="utf-8")

    assert main(["gate", "--run", str(run), "--policy", str(policy)]) == 0

    gate = json.loads((run / "gate_result.json").read_text(encoding="utf-8"))
    assert gate["status"] == "fail"
    assert "model_unknown" in gate["checks"]["model_provenance"]["violations"]


def test_cli_analyze_reads_example_config(tmp_path: Path) -> None:
    demo = tmp_path / "demo"
    run = demo / "runs" / "from-config"
    assert main(["init", "--path", str(demo)]) == 0

    assert (
        main(
            [
                "analyze",
                "--config",
                str(demo / "promptcontrol.example.yaml"),
                "--out",
                str(run),
                "--bootstrap-samples",
                "10",
                "--permutation-samples",
                "10",
            ]
        )
        == 0
    )

    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == "quick"
    assert manifest["metric"] == "exact_match"


def test_cli_analyze_uses_configured_out_and_explain_level(tmp_path: Path) -> None:
    demo = tmp_path / "demo"
    assert main(["init", "--path", str(demo)]) == 0
    config = demo / "promptcontrol.technical.yaml"
    config.write_text(
        "\n".join(
            [
                "mode: quick",
                "data: examples/tasks.jsonl",
                "metric: exact_match",
                "baseline_predictions: examples/predictions_baseline.jsonl",
                "candidate_predictions: examples/predictions_candidate.jsonl",
                "out: runs/configured",
                "explain_level: technical",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "analyze",
                "--config",
                str(config),
                "--bootstrap-samples",
                "10",
                "--permutation-samples",
                "10",
            ]
        )
        == 0
    )

    explanation = json.loads(
        (demo / "runs" / "configured" / "explanation.json").read_text(encoding="utf-8")
    )
    assert explanation["level"] == "technical"
    assert "artifact_paths" in explanation


def test_cli_diagnostic_command_can_refresh_technical_explanation(tmp_path: Path) -> None:
    run = tmp_path / "run"
    predictions = tmp_path / "methods.jsonl"
    write_jsonl(
        predictions,
        [
            {
                "id": "a",
                "output": "x",
                "expected": "x",
                "score": 0.5,
                "slice": "s",
                "method": "static",
            },
            {
                "id": "b",
                "output": "x",
                "expected": "x",
                "score": 1.0,
                "slice": "s",
                "method": "time_varying",
            },
        ],
    )

    assert (
        main(
            [
                "tv-soft",
                "--predictions",
                str(predictions),
                "--out",
                str(run / "diagnostics"),
                "--explain-level",
                "technical",
            ]
        )
        == 0
    )

    explanation = json.loads((run / "explanation.json").read_text(encoding="utf-8"))
    assert explanation["level"] == "technical"
    assert "deployment_risk" in explanation


def test_cli_improve_prompt_string_outputs_plain_optimized_prompt(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["improve", "--prompt", "回答下面的问题"]) == 0
    captured = capsys.readouterr()
    assert "Optimized prompt:" in captured.out
    assert "请准确回答下面的问题" in captured.out
    assert "Why it changed:" in captured.out


def test_cli_improve_prompt_file_and_out_writes_artifacts(tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompt.txt"
    out_dir = tmp_path / "improve"
    prompt_file.write_text("Answer the user question.", encoding="utf-8")

    assert main(["improve", "--prompt-file", str(prompt_file), "--out", str(out_dir)]) == 0

    improved = (out_dir / "improved_prompt.txt").read_text(encoding="utf-8")
    payload = json.loads((out_dir / "prompt_improvement.json").read_text(encoding="utf-8"))
    diff = (out_dir / "prompt_diff.md").read_text(encoding="utf-8")
    assert "Please answer the user question accurately." in improved
    assert payload["plain_summary"].startswith("This rewrite")
    assert payload["language"] == "en"
    assert payload["original_prompt"] == "Answer the user question."
    assert "Added a clear task goal" in diff


def test_cli_improve_records_balanced_token_report(tmp_path: Path) -> None:
    out_dir = tmp_path / "improve"

    assert main(["improve", "--prompt", "Answer the user question.", "--out", str(out_dir)]) == 0

    payload = json.loads((out_dir / "prompt_improvement.json").read_text(encoding="utf-8"))
    token_report = payload["token_report"]
    assert token_report["token_mode"] == "balanced"
    assert token_report["original_estimated_tokens"] > 0
    assert token_report["improved_estimated_tokens"] > 0
    assert token_report["compression_applied"] is True
    assert token_report["estimate_note"] == "Estimated with a dependency-free heuristic."


def test_cli_improve_aggressive_max_tokens_makes_prompt_shorter(tmp_path: Path) -> None:
    balanced_dir = tmp_path / "balanced"
    aggressive_dir = tmp_path / "aggressive"

    assert (
        main(["improve", "--prompt", "Answer the user question.", "--out", str(balanced_dir)])
        == 0
    )
    assert (
        main(
            [
                "improve",
                "--prompt",
                "Answer the user question.",
                "--token-mode",
                "aggressive",
                "--max-tokens",
                "35",
                "--out",
                str(aggressive_dir),
            ]
        )
        == 0
    )

    balanced = json.loads((balanced_dir / "prompt_improvement.json").read_text(encoding="utf-8"))
    aggressive = json.loads(
        (aggressive_dir / "prompt_improvement.json").read_text(encoding="utf-8")
    )
    balanced_tokens = balanced["token_report"]["improved_estimated_tokens"]
    aggressive_report = aggressive["token_report"]
    assert aggressive_report["token_mode"] == "aggressive"
    assert aggressive_report["max_tokens"] == 35
    assert aggressive_report["within_budget"] is True
    assert aggressive_report["improved_estimated_tokens"] <= balanced_tokens
    assert "Reduced prompt length to lower estimated token cost." in aggressive["changes"]


def test_cli_improve_uses_run_context(tmp_path: Path) -> None:
    run = tmp_path / "run"
    (run / "diagnostics").mkdir(parents=True)
    (run / "explanation.json").write_text(
        json.dumps(
            {
                "failure_slices": {
                    "regressed": {"arithmetic": -0.25},
                    "improved": {},
                    "unchanged": {},
                },
                "example_changes": {
                    "fixed_ids": [],
                    "broken_ids": ["arith-2"],
                    "unchanged_ids": [],
                },
                "deployment_risk": {
                    "items": {"trajectory": {"mean_step_drift": 2.0}},
                },
            }
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "improve",
                "--prompt",
                "回答下面的问题",
                "--run",
                str(run),
                "--out",
                str(tmp_path / "improve"),
            ]
        )
        == 0
    )

    improved = (tmp_path / "improve" / "improved_prompt.txt").read_text(encoding="utf-8")
    assert "arithmetic" in improved
    assert "arith-2" in improved


def test_cli_improve_validates_prompt_source(tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("Answer the question.", encoding="utf-8")
    assert main(["improve"]) == 2
    assert main(["improve", "--prompt", "x", "--prompt-file", str(prompt_file)]) == 2


def test_cli_guard_json_suggests_improved_prompt(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["guard", "--prompt", "Fix this bug", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["action"] == "suggest"
    assert payload["risk_level"] in {"low", "medium", "high"}
    assert payload["profile"] == "general"
    assert "improved_prompt" in payload
    assert payload["improved_prompt"] != payload["original_prompt"]
    assert "plain_summary" in payload
    assert "add" in payload["plain_summary"].lower()
    assert payload["token_report"]["token_mode"] == "balanced"
    assert payload["reasons"]


def test_cli_guard_policy_blocks_destructive_coding_prompt(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    policy = tmp_path / "guard.policy.yaml"
    policy.write_text(
        "\n".join(
            [
                "profile: coding",
                "block_at: high",
                "review_at: medium",
                "required_fields: target_files,failing_behavior,test_plan,acceptance_criteria",
                "rule.destructive_action.severity: high",
                "rule.destructive_action.patterns: delete database|drop table|remove auth",
                "rule.destructive_action.message: Dangerous destructive request.",
                "rule.destructive_action.category: destructive_change",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "guard",
                "--prompt",
                "Delete database and remove auth",
                "--profile",
                "coding",
                "--mode",
                "gate",
                "--policy",
                str(policy),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["action"] == "block"
    assert payload["risk_level"] == "high"
    assert payload["required_review"] is True
    assert "destructive_change" in payload["risk_categories"]
    assert any(
        violation["id"] == "destructive_action" for violation in payload["policy_violations"]
    )


def test_cli_guard_builtin_dangerous_prompt_requires_review(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "guard",
                "--prompt",
                "Drop table users in prod and print env secrets",
                "--profile",
                "coding",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["risk_level"] == "high"
    assert payload["required_review"] is True
    assert "destructive_change" in payload["risk_categories"]
    assert "security" in payload["risk_categories"]


def test_cli_guard_safe_coding_prompt_remains_low_risk(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "guard",
                "--prompt",
                "Update docs/usage.md to clarify install steps and run pytest tests/test_cli.py.",
                "--profile",
                "coding",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["risk_level"] == "low"
    assert payload["required_review"] is False
    assert payload["policy_violations"] == []


def test_cli_guard_ignores_policy_rule_without_patterns(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    policy = tmp_path / "guard.policy.yaml"
    policy.write_text(
        "\n".join(
            [
                "profile: coding",
                "rule.incomplete_rule.severity: high",
                "rule.incomplete_rule.message: This should not match every prompt.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "guard",
                "--prompt",
                "Update docs/usage.md to clarify install steps and run pytest tests/test_cli.py.",
                "--profile",
                "coding",
                "--policy",
                str(policy),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["risk_level"] == "low"
    assert not any(
        violation["id"] == "incomplete_rule" for violation in payload["policy_violations"]
    )


def test_cli_guard_default_output_starts_with_plain_summary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["guard", "--prompt", "Fix this bug", "--profile", "coding"]) == 0
    output = capsys.readouterr().out
    assert "Plain summary:" in output
    assert "Add target files" in output


def test_cli_guard_chinese_prompt_uses_chinese_profile_hint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "guard",
                "--prompt",
                "修复这个 bug",
                "--profile",
                "coding",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert "目标文件" in payload["plain_summary"]
    assert "Focus on precise code changes" not in payload["improved_prompt"]
    assert "影响文件" in payload["improved_prompt"]


def test_cli_start_choice_improve_outputs_beginner_prompt(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["start", "--choice", "improve", "--prompt", "Answer the question"]) == 0
    output = capsys.readouterr().out
    assert "Beginner mode: improve a prompt" in output
    assert "Optimized prompt:" in output


def test_cli_start_interactive_guard_menu(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("2\nFix this bug\n"))
    assert main(["start"]) == 0
    output = capsys.readouterr().out
    assert "What do you want to do?" in output
    assert "Beginner mode: guard a prompt" in output
    assert "Plain summary:" in output


def test_cli_guard_gate_blocks_over_budget_prompt(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("Answer the user question."))
    assert (
        main(
            [
                "guard",
                "--stdin",
                "--mode",
                "gate",
                "--max-tokens",
                "8",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["action"] == "block"
    assert payload["within_budget"] is False
    assert "token_budget" in payload["risk_categories"]
    assert any("token budget" in reason for reason in payload["reasons"])


def test_claude_code_hook_emits_additional_context() -> None:
    hook = Path("plugins/claude-code/hooks/prompt_guard.py")
    event = {
        "hook_event_name": "UserPromptSubmit",
        "prompt": "Fix this bug",
    }
    completed = subprocess.run(
        [
            sys.executable,
            str(hook),
            "--mode",
            "suggest",
            "--profile",
            "coding",
        ],
        input=json.dumps(event),
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(completed.stdout)
    assert "additionalContext" in payload
    assert "prompt_control_lab" in payload["additionalContext"]
    assert "Coding profile adds file, test, and verification focus." in payload["additionalContext"]


def test_claude_code_hook_can_block_over_budget_prompt() -> None:
    hook = Path("plugins/claude-code/hooks/prompt_guard.py")
    event = {
        "hook_event_name": "UserPromptSubmit",
        "prompt": "Answer the user question.",
    }
    completed = subprocess.run(
        [
            sys.executable,
            str(hook),
            "--mode",
            "gate",
            "--max-tokens",
            "8",
        ],
        input=json.dumps(event),
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "block"
    assert "token budget" in payload["reason"]


def test_cursor_mcp_server_lists_and_calls_guard_prompt() -> None:
    server = Path("plugins/cursor/mcp_server.py")
    requests = "\n".join(
        [
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "guard_prompt",
                        "arguments": {
                            "prompt": "Fix this bug",
                            "profile": "coding",
                            "token_mode": "balanced",
                        },
                    },
                }
            ),
        ]
    )
    completed = subprocess.run(
        [sys.executable, str(server)],
        input=requests + "\n",
        text=True,
        capture_output=True,
        check=True,
    )
    responses = [json.loads(line) for line in completed.stdout.splitlines()]
    assert responses[1]["result"]["tools"][0]["name"] == "guard_prompt"
    tool_result = responses[2]["result"]["content"][0]["text"]
    assert "plain_summary" in tool_result
    assert "target files" in tool_result
