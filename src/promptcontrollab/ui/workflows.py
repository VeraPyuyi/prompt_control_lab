"""Allowlisted workflow actions for the local Streamlit cockpit."""

from __future__ import annotations

import shlex
from collections.abc import Callable
from pathlib import Path

from promptcontrollab.agent_run import build_agent_run_manifest
from promptcontrollab.artifact_export import export_report_zip
from promptcontrollab.audit_diff import run_audit_diff
from promptcontrollab.files import JsonDict, ensure_dir, write_json
from promptcontrollab.gate import run_gate
from promptcontrollab.pr_summary import write_pr_summary
from promptcontrollab.prompt_context import load_prompt_context
from promptcontrollab.prompt_guard import guard_prompt
from promptcontrollab.workflow import run_quick_analysis

ExecutionRunner = Callable[[], JsonDict]


def run_guard_workflow(
    *,
    prompt: str,
    out_dir: Path,
    execution_mode: str,
    confirmed: bool,
    overwrite: bool,
    policy_path: Path | None = None,
    profile: str = "coding",
    mode: str = "suggest",
    token_mode: str = "balanced",
    max_tokens: int | None = None,
    language: str = "auto",
) -> JsonDict:
    """Run or preview the Guard Prompt workflow."""

    outputs = [out_dir / "guard_result.json", out_dir / "guarded_prompt.txt"]
    command = _command(
        [
            "pcl",
            "guard",
            "--prompt",
            prompt,
            "--profile",
            profile,
            "--mode",
            mode,
            "--token-mode",
            token_mode,
            "--language",
            language,
            *(_option("--max-tokens", str(max_tokens)) if max_tokens is not None else []),
            *(_path_option("--policy", policy_path)),
            "--json",
        ]
    )

    def runner() -> JsonDict:
        result = guard_prompt(
            prompt,
            context=load_prompt_context(None),
            mode=mode,
            profile=profile,
            token_mode=token_mode,
            max_tokens=max_tokens,
            language=language,
            policy_path=policy_path,
        ).to_json()
        ensure_dir(out_dir)
        write_json(out_dir / "guard_result.json", result)
        (out_dir / "guarded_prompt.txt").write_text(
            str(result.get("improved_prompt", "")) + "\n",
            encoding="utf-8",
        )
        return {"guard": result}

    return _handle_execution(
        name="guard",
        command=command,
        outputs=outputs,
        execution_mode=execution_mode,
        confirmed=confirmed,
        overwrite=overwrite,
        runner=runner,
    )


def run_analyze_workflow(
    *,
    data_path: Path,
    baseline_predictions_path: Path,
    candidate_predictions_path: Path,
    out_dir: Path,
    execution_mode: str,
    confirmed: bool,
    overwrite: bool,
    policy_path: Path | None = None,
    metric: str = "exact_match",
    train_ratio: float = 0.6,
    val_ratio: float = 0.2,
    seed: int = 0,
    bootstrap_samples: int = 1000,
    permutation_samples: int = 1000,
    explain_level: str = "plain",
    title: str = "PromptControlLab Quick Analysis",
) -> JsonDict:
    """Run or preview Quick Mode analysis from the local UI."""

    outputs = [
        out_dir / "splits.json",
        out_dir / "baseline" / "metrics.json",
        out_dir / "candidate" / "metrics.json",
        out_dir / "stats.json",
        out_dir / "explanation.json",
        out_dir / "report.md",
        out_dir / "report.html",
    ]
    if policy_path is not None:
        outputs.append(out_dir / "gate_result.json")
    command = _command(
        [
            "pcl",
            "analyze",
            "--data",
            str(data_path),
            "--baseline-predictions",
            str(baseline_predictions_path),
            "--candidate-predictions",
            str(candidate_predictions_path),
            "--out",
            str(out_dir),
            "--metric",
            metric,
            "--train-ratio",
            str(train_ratio),
            "--val-ratio",
            str(val_ratio),
            "--seed",
            str(seed),
            "--bootstrap-samples",
            str(bootstrap_samples),
            "--permutation-samples",
            str(permutation_samples),
            "--explain-level",
            explain_level,
            *(_path_option("--policy", policy_path)),
        ]
    )

    def runner() -> JsonDict:
        run_quick_analysis(
            data_path=data_path,
            baseline_predictions_path=baseline_predictions_path,
            candidate_predictions_path=candidate_predictions_path,
            out_dir=out_dir,
            metric=metric,
            train_ratio=train_ratio,
            val_ratio=val_ratio,
            seed=seed,
            bootstrap_samples=bootstrap_samples,
            permutation_samples=permutation_samples,
            explain_level=explain_level,
            title=title,
            policy_path=policy_path,
        )
        return {"run_dir": str(out_dir)}

    return _handle_execution(
        name="analyze",
        command=command,
        outputs=outputs,
        execution_mode=execution_mode,
        confirmed=confirmed,
        overwrite=overwrite,
        runner=runner,
    )


def run_gate_workflow(
    *,
    run_dir: Path,
    policy_path: Path,
    execution_mode: str,
    confirmed: bool,
    overwrite: bool,
) -> JsonDict:
    """Run or preview a gate check."""

    output = run_dir / "gate_result.json"
    command = _command(["pcl", "gate", "--run", str(run_dir), "--policy", str(policy_path)])

    def runner() -> JsonDict:
        return {"gate": run_gate(run_dir, policy_path=policy_path)}

    return _handle_execution(
        name="gate",
        command=command,
        outputs=[output],
        execution_mode=execution_mode,
        confirmed=confirmed,
        overwrite=overwrite,
        runner=runner,
    )


def run_audit_workflow(
    *,
    repo: Path,
    before: str,
    after: str,
    out_dir: Path,
    execution_mode: str,
    confirmed: bool,
    overwrite: bool,
    expected_paths: list[str] | None = None,
    tests_run: list[str] | None = None,
    tests_passed: bool | None = None,
) -> JsonDict:
    """Run or preview an audit-diff action without shell test execution."""

    outputs = [out_dir / "audit_result.json", out_dir / "audit_summary.md"]
    command = _command(
        [
            "pcl",
            "audit-diff",
            "--repo",
            str(repo),
            "--before",
            before,
            "--after",
            after,
            "--out",
            str(out_dir),
            *[part for path in expected_paths or [] for part in ["--expected-path", path]],
            *[part for item in tests_run or [] for part in ["--tests-run", item]],
            *(
                ["--tests-passed", "true" if tests_passed else "false"]
                if tests_passed is not None
                else []
            ),
        ]
    )

    def runner() -> JsonDict:
        return {
            "audit": run_audit_diff(
                repo=repo,
                before=before,
                after=after,
                out_dir=out_dir,
                expected_paths=expected_paths,
                tests_run=tests_run,
                tests_passed=tests_passed,
                test_commands=[],
            )
        }

    return _handle_execution(
        name="audit-diff",
        command=command,
        outputs=outputs,
        execution_mode=execution_mode,
        confirmed=confirmed,
        overwrite=overwrite,
        runner=runner,
    )


def build_agent_run_workflow(
    *,
    run_dir: Path,
    audit_dir: Path | None,
    agent: str,
    out_path: Path,
    execution_mode: str,
    confirmed: bool,
    overwrite: bool,
    policy: str | None = None,
) -> JsonDict:
    """Run or preview agent_run.json generation."""

    command = _command(
        [
            "pcl",
            "agent-run",
            "build",
            "--run",
            str(run_dir),
            *(_path_option("--audit", audit_dir)),
            "--agent",
            agent,
            "--out",
            str(out_path),
            *(_option("--policy", policy) if policy else []),
        ]
    )

    def runner() -> JsonDict:
        return {
            "agent_run": build_agent_run_manifest(
                run_dir=run_dir,
                audit_dir=audit_dir,
                agent=agent,
                out_path=out_path,
                policy=policy,
            )
        }

    return _handle_execution(
        name="agent-run",
        command=command,
        outputs=[out_path],
        execution_mode=execution_mode,
        confirmed=confirmed,
        overwrite=overwrite,
        runner=runner,
    )


def run_pr_summary_workflow(
    *,
    audit_path: Path | None,
    gate_path: Path | None,
    agent_run_path: Path | None,
    markdown_path: Path | None,
    json_path: Path | None,
    execution_mode: str,
    confirmed: bool,
    overwrite: bool,
) -> JsonDict:
    """Run or preview PR summary generation."""

    outputs = [path for path in [markdown_path, json_path] if path is not None]
    command = _command(
        [
            "pcl",
            "pr-summary",
            *(_path_option("--audit", audit_path)),
            *(_path_option("--gate", gate_path)),
            *(_path_option("--agent-run", agent_run_path)),
            *(_path_option("--out", markdown_path)),
            *(_path_option("--json-out", json_path)),
        ]
    )

    def runner() -> JsonDict:
        return {
            "pr_summary": write_pr_summary(
                audit_path=audit_path,
                gate_path=gate_path,
                agent_run_path=agent_run_path,
                markdown_path=markdown_path,
                json_path=json_path,
            )
        }

    return _handle_execution(
        name="pr-summary",
        command=command,
        outputs=outputs,
        execution_mode=execution_mode,
        confirmed=confirmed,
        overwrite=overwrite,
        runner=runner,
    )


def export_report_zip_workflow(
    *,
    run_dir: Path,
    zip_path: Path,
    execution_mode: str,
    confirmed: bool,
    overwrite: bool,
) -> JsonDict:
    """Export known run artifacts to a zip archive."""

    command = _command(["pcl", "export-report", "--run", str(run_dir), "--out", str(zip_path)])

    def runner() -> JsonDict:
        return {"export": export_report_zip(run_dir=run_dir, zip_path=zip_path)}

    return _handle_execution(
        name="export-report",
        command=command,
        outputs=[zip_path],
        execution_mode=execution_mode,
        confirmed=confirmed,
        overwrite=overwrite,
        runner=runner,
    )


def _handle_execution(
    *,
    name: str,
    command: str,
    outputs: list[Path],
    execution_mode: str,
    confirmed: bool,
    overwrite: bool,
    runner: ExecutionRunner,
) -> JsonDict:
    _validate_execution_mode(execution_mode)
    payload: JsonDict = {
        "workflow": name,
        "command": command,
        "outputs": [str(path) for path in outputs],
        "existing_outputs": [str(path) for path in outputs if path.exists()],
    }
    if execution_mode == "command":
        return {"status": "command", **payload}
    if execution_mode == "confirm" and not confirmed:
        return {"status": "preview", **payload}
    if payload["existing_outputs"] and not overwrite:
        msg = "Output artifacts already exist; enable overwrite to replace them."
        raise ValueError(msg)
    result = runner()
    return {"status": "completed", **payload, **result}


def _validate_execution_mode(execution_mode: str) -> None:
    if execution_mode not in {"confirm", "auto", "command"}:
        msg = f"Unknown execution mode `{execution_mode}`."
        raise ValueError(msg)


def _command(parts: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in parts)


def _option(flag: str, value: str) -> list[str]:
    return [flag, value]


def _path_option(flag: str, path: Path | None) -> list[str]:
    return [flag, str(path)] if path is not None else []
