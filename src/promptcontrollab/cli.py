"""Command line interface for PromptControlLab."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from promptcontrollab.agent_run import build_agent_run_manifest
from promptcontrollab.artifact_export import export_report_zip
from promptcontrollab.audit_diff import run_audit_diff
from promptcontrollab.config import (
    get_config_bool,
    get_config_float,
    get_config_int,
    get_config_list,
    get_config_path,
    get_config_str,
    load_project_config,
)
from promptcontrollab.doctor import format_doctor, run_doctor
from promptcontrollab.errors import PromptControlLabError
from promptcontrollab.evaluation import run_import_eval
from promptcontrollab.explain import generate_explanation
from promptcontrollab.files import JsonDict, ensure_dir, write_json
from promptcontrollab.gate import run_gate
from promptcontrollab.history import compare_history, index_history
from promptcontrollab.ingest import (
    ingest_auto_results,
    ingest_langfuse_results,
    ingest_langsmith_results,
    ingest_promptfoo_results,
)
from promptcontrollab.model_drift import run_model_drift
from promptcontrollab.model_identity import detect_model_identity
from promptcontrollab.plugin_installer import install_plugin
from promptcontrollab.pr_summary import write_pr_summary
from promptcontrollab.prompt_context import load_prompt_context
from promptcontrollab.prompt_diff import render_prompt_diff
from promptcontrollab.prompt_guard import guard_prompt
from promptcontrollab.prompt_improver import improve_prompt
from promptcontrollab.reporting import generate_report
from promptcontrollab.research_workflow import run_research_diagnostics, write_research_demo
from promptcontrollab.riccati import analyze_riccati
from promptcontrollab.run_comparison import compare_runs
from promptcontrollab.soft_hard import analyze_soft_hard
from promptcontrollab.splitting import load_tasks, make_split, write_split
from promptcontrollab.statistics import compare_prediction_files
from promptcontrollab.templates import write_example_project
from promptcontrollab.trajectory import analyze_trajectory
from promptcontrollab.tv_soft import summarize_tv_soft
from promptcontrollab.validity import run_comparison_validity
from promptcontrollab.workflow import (
    config_metric,
    load_analyze_config,
    resolve_analyze_paths,
    run_quick_analysis,
)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (PromptControlLabError, ValueError, OSError) as exc:
        print(f"pcl: error: {exc}", file=sys.stderr)
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""

    parser = argparse.ArgumentParser(
        prog="pcl",
        description="PromptControlLab prompt evaluation and diagnostics toolkit.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    start_parser = subcommands.add_parser(
        "start",
        help="Beginner mode: choose a scenario and get guided output.",
    )
    start_parser.add_argument(
        "--choice",
        choices=["improve", "guard", "analyze"],
        default=None,
        help="Skip the menu and choose a beginner scenario.",
    )
    start_parser.add_argument("--prompt", default=None, help="Prompt string for improve/guard.")
    start_parser.add_argument("--prompt-file", type=Path, default=None, help="Prompt text file.")
    start_parser.add_argument("--run", type=Path, default=None, help="Optional run directory.")
    start_parser.add_argument("--out", type=Path, default=None, help="Optional output directory.")
    start_parser.add_argument("--policy", type=Path, default=None, help="Optional guard policy.")
    start_parser.add_argument(
        "--profile",
        choices=["general", "coding", "research"],
        default="coding",
        help="Prompt profile used when choice is guard.",
    )
    start_parser.add_argument(
        "--token-mode",
        choices=["balanced", "aggressive"],
        default="balanced",
        help="Token-cost mode used for prompt rewriting.",
    )
    start_parser.add_argument("--max-tokens", type=int, default=None)
    start_parser.add_argument("--config", type=Path, default=None, help="Config for analyze mode.")
    start_parser.set_defaults(func=_cmd_start)

    init_parser = subcommands.add_parser("init", help="Create an example project.")
    init_parser.add_argument("--path", type=Path, default=Path("."), help="Project directory.")
    init_parser.set_defaults(func=_cmd_init)

    ingest_parser = subcommands.add_parser(
        "ingest",
        help="Import external eval-tool results into PromptControlLab artifacts.",
    )
    ingest_subcommands = ingest_parser.add_subparsers(dest="ingest_command", required=True)
    auto_ingest = ingest_subcommands.add_parser(
        "auto",
        help="Auto-detect Promptfoo/Langfuse/LangSmith exports and import them.",
    )
    auto_ingest.add_argument("--input", type=Path, required=True, help="External export file.")
    auto_ingest.add_argument("--out", type=Path, required=True, help="PCL run directory.")
    auto_ingest.add_argument("--prompt-id", default=None, help="Promptfoo prompt filter.")
    auto_ingest.add_argument("--name", default=None, help="Langfuse observation name filter.")
    auto_ingest.add_argument("--experiment", default=None, help="LangSmith experiment filter.")
    auto_ingest.add_argument("--score-name", default=None, help="Langfuse/LangSmith score filter.")
    auto_ingest.add_argument("--model", default=None, help="Model id filter.")
    auto_ingest.add_argument("--provider", default=None, help="Provider filter.")
    auto_ingest.add_argument("--method", default=None, help="Method name written to predictions.")
    auto_ingest.set_defaults(func=_cmd_ingest_auto)
    promptfoo_ingest = ingest_subcommands.add_parser(
        "promptfoo",
        help="Import `promptfoo eval --output results.json` output.",
    )
    promptfoo_ingest.add_argument("--input", type=Path, required=True, help="Promptfoo JSON file.")
    promptfoo_ingest.add_argument("--out", type=Path, required=True, help="PCL run directory.")
    promptfoo_ingest.add_argument(
        "--prompt-id",
        default=None,
        help="Promptfoo prompt id/label to import when the file contains multiple prompts.",
    )
    promptfoo_ingest.add_argument(
        "--provider",
        default=None,
        help="Promptfoo provider id to import when the file contains multiple providers.",
    )
    promptfoo_ingest.add_argument(
        "--method",
        default=None,
        help="Method name written to PCL predictions. Defaults to the prompt id.",
    )
    promptfoo_ingest.set_defaults(func=_cmd_ingest_promptfoo)
    langfuse_ingest = ingest_subcommands.add_parser(
        "langfuse",
        help="Import Langfuse observations/traces JSON export.",
    )
    langfuse_ingest.add_argument("--input", type=Path, required=True, help="Langfuse JSON file.")
    langfuse_ingest.add_argument("--out", type=Path, required=True, help="PCL run directory.")
    langfuse_ingest.add_argument(
        "--name",
        default=None,
        help="Langfuse observation/generation name to import when multiple names exist.",
    )
    langfuse_ingest.add_argument(
        "--score-name",
        default=None,
        help="Langfuse score name to import when multiple score names exist.",
    )
    langfuse_ingest.add_argument(
        "--model",
        default=None,
        help="Model id filter to import when the file contains multiple models.",
    )
    langfuse_ingest.add_argument(
        "--provider",
        default=None,
        help="Provider filter to import when the file contains multiple providers.",
    )
    langfuse_ingest.add_argument(
        "--method",
        default=None,
        help="Method name written to PCL predictions. Defaults to the Langfuse name.",
    )
    langfuse_ingest.set_defaults(func=_cmd_ingest_langfuse)
    langsmith_ingest = ingest_subcommands.add_parser(
        "langsmith",
        help="Import LangSmith experiment JSON/CSV export.",
    )
    langsmith_ingest.add_argument(
        "--input",
        type=Path,
        required=True,
        help="LangSmith export file.",
    )
    langsmith_ingest.add_argument("--out", type=Path, required=True, help="PCL run directory.")
    langsmith_ingest.add_argument(
        "--experiment",
        default=None,
        help="LangSmith experiment/session name to import when multiple experiments exist.",
    )
    langsmith_ingest.add_argument(
        "--score-name",
        default=None,
        help="LangSmith score column/key to import when multiple scores exist.",
    )
    langsmith_ingest.add_argument(
        "--model",
        default=None,
        help="Model id filter to import when the file contains multiple models.",
    )
    langsmith_ingest.add_argument(
        "--provider",
        default=None,
        help="Provider filter to import when the file contains multiple providers.",
    )
    langsmith_ingest.add_argument(
        "--method",
        default=None,
        help="Method name written to PCL predictions. Defaults to the experiment name.",
    )
    langsmith_ingest.set_defaults(func=_cmd_ingest_langsmith)

    improve_parser = subcommands.add_parser(
        "improve",
        help="Improve one prompt with simple offline rules.",
    )
    improve_parser.add_argument("--prompt", default=None, help="Prompt string to improve.")
    improve_parser.add_argument("--prompt-file", type=Path, default=None, help="Prompt text file.")
    improve_parser.add_argument("--run", type=Path, default=None, help="Optional run directory.")
    improve_parser.add_argument("--out", type=Path, default=None, help="Optional output directory.")
    improve_parser.add_argument(
        "--goal",
        default="stability",
        help="accuracy, format, or stability.",
    )
    improve_parser.add_argument("--language", choices=["auto", "zh", "en"], default="auto")
    improve_parser.add_argument("--style", choices=["simple", "strict", "stable"], default="stable")
    improve_parser.add_argument(
        "--token-mode",
        choices=["balanced", "aggressive"],
        default="balanced",
        help="Token-cost mode. Balanced preserves key constraints; aggressive is shorter.",
    )
    improve_parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Optional estimated-token budget for the rewritten prompt.",
    )
    improve_parser.set_defaults(func=_cmd_improve)

    guard_parser = subcommands.add_parser(
        "guard",
        help="Guard and improve one prompt before an IDE or CLI agent uses it.",
    )
    guard_parser.add_argument("--prompt", default=None, help="Prompt string to guard.")
    guard_parser.add_argument("--prompt-file", type=Path, default=None, help="Prompt text file.")
    guard_parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read prompt text from stdin. Useful for hooks and wrappers.",
    )
    guard_parser.add_argument("--run", type=Path, default=None, help="Optional run directory.")
    guard_parser.add_argument(
        "--policy",
        type=Path,
        default=None,
        help="Optional guard policy YAML.",
    )
    guard_parser.add_argument(
        "--mode",
        choices=["suggest", "auto", "gate"],
        default="suggest",
        help="suggest returns a recommendation, auto marks it auto-usable, gate can block.",
    )
    guard_parser.add_argument(
        "--profile",
        choices=["general", "coding", "research"],
        default="general",
        help="Prompt profile for context-specific guardrails.",
    )
    guard_parser.add_argument("--language", choices=["auto", "zh", "en"], default="auto")
    guard_parser.add_argument(
        "--token-mode",
        choices=["balanced", "aggressive"],
        default="balanced",
        help="Token-cost mode passed to the prompt improver.",
    )
    guard_parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Optional estimated-token budget for the guarded prompt.",
    )
    guard_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit stable JSON for IDE hooks and wrappers.",
    )
    guard_parser.set_defaults(func=_cmd_guard)

    model_parser = subcommands.add_parser(
        "model-detect",
        help="Detect public model id from an API response, prediction file, or declared model.",
    )
    model_parser.add_argument("--response", type=Path, default=None, help="API response JSON file.")
    model_parser.add_argument(
        "--predictions",
        type=Path,
        default=None,
        help="Raw predictions JSONL with optional model/provider fields.",
    )
    model_parser.add_argument("--model", default=None, help="Declared model id, such as gpt-5.2.")
    model_parser.add_argument("--provider", default=None, help="Provider hint, such as openai.")
    model_parser.add_argument("--api-version", default=None, help="Optional API version string.")
    model_parser.add_argument("--request-id", default=None, help="Provider request id, if known.")
    model_parser.add_argument("--request-json", type=Path, default=None, help="Request JSON file.")
    model_parser.add_argument("--request-sha256", default=None, help="Precomputed request hash.")
    model_parser.add_argument("--response-sha256", default=None, help="Precomputed response hash.")
    model_parser.add_argument(
        "--provider-log-reference",
        default=None,
        help="Provider-side log or usage record reference.",
    )
    model_parser.add_argument(
        "--signed-receipt",
        default=None,
        help="Provider signed receipt id or digest, if available.",
    )
    model_parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify public model metadata when the provider exposes a supported endpoint.",
    )
    model_parser.add_argument("--out", type=Path, default=None, help="Optional JSON output path.")
    model_parser.set_defaults(func=_cmd_model_detect)

    drift_parser = subcommands.add_parser(
        "model-drift",
        help="Compare model provenance between a current run and a previous run.",
    )
    drift_parser.add_argument("--run", type=Path, required=True, help="Current run directory.")
    drift_parser.add_argument("--history", type=Path, required=True, help="Previous run directory.")
    drift_parser.add_argument("--out", type=Path, required=True, help="model_drift.json output.")
    drift_parser.set_defaults(func=_cmd_model_drift)

    validity_parser = subcommands.add_parser(
        "validity",
        help="Audit whether a baseline/candidate run comparison is clean prompt-only evidence.",
    )
    validity_parser.add_argument(
        "--baseline",
        type=Path,
        required=True,
        help="Baseline run directory.",
    )
    validity_parser.add_argument(
        "--candidate",
        type=Path,
        required=True,
        help="Candidate run directory.",
    )
    validity_parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="comparison_validity.json output path. A sibling .md report is also written.",
    )
    validity_parser.set_defaults(func=_cmd_validity)

    compare_runs_parser = subcommands.add_parser(
        "compare-runs",
        help="Compare two scored run directories and generate stats, validity, and report.",
    )
    compare_runs_parser.add_argument(
        "--baseline",
        type=Path,
        required=True,
        help="Baseline run directory.",
    )
    compare_runs_parser.add_argument(
        "--candidate",
        type=Path,
        required=True,
        help="Candidate run directory.",
    )
    compare_runs_parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Comparison run directory.",
    )
    compare_runs_parser.add_argument("--title", default="PromptControlLab Run Comparison")
    compare_runs_parser.add_argument("--seed", type=int, default=0)
    compare_runs_parser.add_argument("--bootstrap-samples", type=int, default=1000)
    compare_runs_parser.add_argument("--permutation-samples", type=int, default=1000)
    compare_runs_parser.set_defaults(func=_cmd_compare_runs)

    audit_parser = subcommands.add_parser(
        "audit-diff",
        help="Audit what an AI coding agent changed between two git refs.",
    )
    audit_parser.add_argument("--repo", type=Path, default=Path("."), help="Git repository path.")
    audit_parser.add_argument("--before", required=True, help="Base git ref.")
    audit_parser.add_argument("--after", required=True, help="Head git ref.")
    audit_parser.add_argument("--out", type=Path, required=True, help="Audit output directory.")
    audit_parser.add_argument(
        "--expected-path",
        action="append",
        default=[],
        help="Expected changed path prefix. Repeat for multiple allowed scopes.",
    )
    audit_parser.add_argument(
        "--test-command",
        action="append",
        default=[],
        help=(
            "Test command to execute without shell syntax and record. "
            "Repeat for multiple commands."
        ),
    )
    audit_parser.add_argument(
        "--allow-shell-test-command",
        action="store_true",
        help="Allow --test-command to run through the shell. Use only with trusted input.",
    )
    audit_parser.add_argument(
        "--test-timeout",
        type=int,
        default=120,
        help="Timeout in seconds for each --test-command.",
    )
    audit_parser.add_argument(
        "--tests-run",
        action="append",
        default=[],
        help="Previously run test command to record without executing.",
    )
    audit_parser.add_argument(
        "--tests-passed",
        choices=["true", "false"],
        default=None,
        help="Whether externally run tests passed.",
    )
    audit_parser.add_argument(
        "--sarif",
        type=Path,
        default=None,
        help="Optional SARIF output path.",
    )
    audit_parser.add_argument(
        "--secret-scanner",
        choices=["builtin", "gitleaks", "trufflehog"],
        default="builtin",
        help=(
            "Secret scanner to use. builtin scans added diff lines; "
            "gitleaks/trufflehog scan the current workspace."
        ),
    )
    audit_parser.set_defaults(func=_cmd_audit_diff)

    history_parser = subcommands.add_parser("history", help="Index or compare runs.")
    history_subcommands = history_parser.add_subparsers(dest="history_command", required=True)
    history_index = history_subcommands.add_parser("index", help="Build a run history index.")
    history_index.add_argument("--runs", type=Path, required=True, help="Runs directory.")
    history_index.add_argument("--out", type=Path, required=True, help="history_index.json path.")
    history_index.set_defaults(func=_cmd_history_index)
    history_compare = history_subcommands.add_parser("compare", help="Compare two run dirs.")
    history_compare.add_argument("--a", type=Path, required=True, help="Older run directory.")
    history_compare.add_argument("--b", type=Path, required=True, help="Newer run directory.")
    history_compare.add_argument(
        "--out",
        type=Path,
        required=True,
        help="history_compare.json path.",
    )
    history_compare.set_defaults(func=_cmd_history_compare)

    agent_parser = subcommands.add_parser("agent-run", help="Build agent run manifests.")
    agent_subcommands = agent_parser.add_subparsers(dest="agent_command", required=True)
    agent_build = agent_subcommands.add_parser("build", help="Build agent_run.json.")
    agent_build.add_argument("--run", type=Path, required=True, help="PromptControlLab run dir.")
    agent_build.add_argument("--audit", type=Path, default=None, help="Audit output directory.")
    agent_build.add_argument("--agent", required=True, help="Agent name, such as codex.")
    agent_build.add_argument("--out", type=Path, required=True, help="agent_run.json output path.")
    agent_build.add_argument("--policy", default=None, help="Policy path or id used for the run.")
    agent_build.set_defaults(func=_cmd_agent_run_build)

    summary_parser = subcommands.add_parser("pr-summary", help="Build PR review summary artifacts.")
    summary_parser.add_argument("--audit", type=Path, default=None, help="audit_result.json path.")
    summary_parser.add_argument("--gate", type=Path, default=None, help="gate_result.json path.")
    summary_parser.add_argument(
        "--agent-run",
        type=Path,
        default=None,
        help="agent_run.json path.",
    )
    summary_parser.add_argument("--out", type=Path, default=None, help="Markdown output path.")
    summary_parser.add_argument("--json-out", type=Path, default=None, help="JSON output path.")
    summary_parser.set_defaults(func=_cmd_pr_summary)

    github_app_parser = subcommands.add_parser("github-app", help="Run GitHub App bot commands.")
    github_app_subcommands = github_app_parser.add_subparsers(
        dest="github_app_command",
        required=True,
    )
    github_serve = github_app_subcommands.add_parser("serve", help="Serve webhook endpoint.")
    github_serve.add_argument("--host", default="0.0.0.0", help="Host address.")
    github_serve.add_argument("--port", type=int, default=8080, help="Port number.")
    github_serve.set_defaults(func=_cmd_github_app_serve)

    install_parser = subcommands.add_parser(
        "install-plugin",
        help="Install local IDE/CLI integration templates.",
    )
    install_parser.add_argument(
        "plugin",
        choices=["codex", "cursor", "claude-code", "github-action", "all"],
    )
    install_parser.add_argument("--target", type=Path, default=None, help="Override install path.")
    install_parser.add_argument("--force", action="store_true", help="Overwrite existing files.")
    install_parser.set_defaults(func=_cmd_install_plugin)

    doctor_parser = subcommands.add_parser("doctor", help="Check local setup and integrations.")
    doctor_parser.add_argument("--json", action="store_true", help="Emit stable JSON.")
    doctor_parser.set_defaults(func=_cmd_doctor)

    ui_parser = subcommands.add_parser("ui", help="Launch the local Streamlit dashboard.")
    ui_parser.add_argument("--runs", type=Path, default=None, help="Runs directory.")
    ui_parser.add_argument("--policy", type=Path, default=None, help="Optional guard policy.")
    ui_parser.add_argument("--host", default="localhost", help="Host address.")
    ui_parser.add_argument("--port", type=int, default=8501, help="Port number.")
    ui_parser.add_argument("--language", choices=["en", "zh"], default="en")
    ui_parser.add_argument("--no-browser", action="store_true", help="Do not open a browser.")
    ui_parser.set_defaults(func=_cmd_ui)

    export_parser = subcommands.add_parser(
        "export-report",
        help="Zip recognized artifacts from one run directory.",
    )
    export_parser.add_argument("--run", type=Path, required=True, help="Run directory.")
    export_parser.add_argument("--out", type=Path, required=True, help="Zip output path.")
    export_parser.set_defaults(func=_cmd_export_report)

    research_demo_parser = subcommands.add_parser(
        "research-demo",
        help="Create a synthetic paper-style demo and run all research diagnostics.",
    )
    research_demo_parser.add_argument("--out", type=Path, required=True, help="Demo run directory.")
    research_demo_parser.add_argument("--seed", type=int, default=0, help="Synthetic fixture seed.")
    research_demo_parser.set_defaults(func=_cmd_research_demo)

    diagnose_parser = subcommands.add_parser(
        "diagnose",
        help="Run paper-derived soft-hard, trajectory, Riccati, and tv-soft diagnostics.",
    )
    diagnose_parser.add_argument("--run", type=Path, default=None, help="Run dir with inputs/.")
    diagnose_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Diagnostics output directory. Defaults to <run>/diagnostics.",
    )
    diagnose_parser.add_argument("--soft", type=Path, default=None, help=".npz with array `soft`.")
    diagnose_parser.add_argument(
        "--vocab",
        type=Path,
        default=None,
        help=".npz with array `embeddings`.",
    )
    diagnose_parser.add_argument(
        "--states",
        type=Path,
        default=None,
        help=".npz with array `states`.",
    )
    diagnose_parser.add_argument("--matrices", type=Path, default=None, help=".npz with A/B/Q/R.")
    diagnose_parser.add_argument(
        "--tv-predictions",
        type=Path,
        default=None,
        help="Scored predictions JSONL for tv-soft summary.",
    )
    diagnose_parser.add_argument("--baseline-method", default="static")
    diagnose_parser.add_argument("--tail", type=int, default=1)
    diagnose_parser.add_argument("--iterations", type=int, default=200)
    diagnose_parser.set_defaults(func=_cmd_diagnose)

    analyze_parser = subcommands.add_parser(
        "analyze",
        help="Quick Mode: run split, eval, stats, explanation, gate, and report.",
    )
    analyze_parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="promptcontrol YAML file.",
    )
    analyze_parser.add_argument("--data", type=Path, default=None, help="Task JSONL file.")
    analyze_parser.add_argument(
        "--baseline-predictions",
        type=Path,
        default=None,
        help="Baseline raw predictions JSONL.",
    )
    analyze_parser.add_argument(
        "--candidate-predictions",
        type=Path,
        default=None,
        help="Candidate raw predictions JSONL.",
    )
    analyze_parser.add_argument("--out", type=Path, default=None, help="Quick run directory.")
    analyze_parser.add_argument("--metric", default=None, help="Deterministic metric name.")
    analyze_parser.add_argument("--baseline-model", default=None, help="Baseline model id.")
    analyze_parser.add_argument("--candidate-model", default=None, help="Candidate model id.")
    analyze_parser.add_argument("--baseline-provider", default=None, help="Baseline provider.")
    analyze_parser.add_argument("--candidate-provider", default=None, help="Candidate provider.")
    analyze_parser.add_argument("--api-version", default=None, help="Optional shared API version.")
    analyze_parser.add_argument("--prompt-id", default=None, help="Stable prompt id.")
    analyze_parser.add_argument("--prompt-file", type=Path, default=None, help="Prompt text file.")
    analyze_parser.add_argument("--prompt-version", default=None, help="Prompt version string.")
    analyze_parser.add_argument(
        "--baseline-prompt-id",
        default=None,
        help="Stable baseline prompt id for prompt-only validity checks.",
    )
    analyze_parser.add_argument(
        "--baseline-prompt-file",
        type=Path,
        default=None,
        help="Baseline prompt text file for prompt-only validity checks.",
    )
    analyze_parser.add_argument(
        "--baseline-prompt-version",
        default=None,
        help="Baseline prompt version string.",
    )
    analyze_parser.add_argument(
        "--candidate-prompt-id",
        default=None,
        help="Stable candidate prompt id for prompt-only validity checks.",
    )
    analyze_parser.add_argument(
        "--candidate-prompt-file",
        type=Path,
        default=None,
        help="Candidate prompt text file for prompt-only validity checks.",
    )
    analyze_parser.add_argument(
        "--candidate-prompt-version",
        default=None,
        help="Candidate prompt version string.",
    )
    analyze_parser.add_argument(
        "--verify-model",
        action="store_true",
        help="Verify public model metadata for supported providers.",
    )
    analyze_parser.add_argument("--train-ratio", type=float, default=None)
    analyze_parser.add_argument("--val-ratio", type=float, default=None)
    analyze_parser.add_argument("--seed", type=int, default=None)
    analyze_parser.add_argument("--bootstrap-samples", type=int, default=None)
    analyze_parser.add_argument("--permutation-samples", type=int, default=None)
    analyze_parser.add_argument(
        "--explain-level",
        choices=["plain", "technical"],
        default=None,
        help="Explanation detail level.",
    )
    analyze_parser.add_argument(
        "--policy",
        "--gate-policy",
        dest="policy",
        type=Path,
        default=None,
        help="Optional gate policy YAML.",
    )
    analyze_parser.add_argument("--title", default=None)
    analyze_parser.set_defaults(func=_cmd_analyze)

    split_parser = subcommands.add_parser("split", help="Create train/val/withheld split manifest.")
    split_parser.add_argument("--data", type=Path, required=True, help="Task JSONL file.")
    split_parser.add_argument("--out", type=Path, required=True, help="Run directory.")
    split_parser.add_argument("--train-ratio", type=float, default=0.5)
    split_parser.add_argument("--val-ratio", type=float, default=0.25)
    split_parser.add_argument("--seed", type=int, default=0)
    split_parser.set_defaults(func=_cmd_split)

    eval_parser = subcommands.add_parser("eval", help="Import and score model outputs.")
    eval_parser.add_argument("--data", type=Path, required=True, help="Task JSONL file.")
    eval_parser.add_argument(
        "--predictions",
        type=Path,
        required=True,
        help="Raw predictions JSONL.",
    )
    eval_parser.add_argument("--out", type=Path, required=True, help="Run directory.")
    eval_parser.add_argument("--metric", default="exact_match", help="Deterministic metric name.")
    eval_parser.add_argument("--method", default="candidate", help="Prompt/method name.")
    eval_parser.add_argument("--model", default=None, help="Model id used to produce predictions.")
    eval_parser.add_argument(
        "--provider",
        default=None,
        help="Provider used to produce predictions.",
    )
    eval_parser.add_argument("--api-version", default=None, help="Optional API version string.")
    eval_parser.add_argument(
        "--verify-model",
        action="store_true",
        help="Verify public model metadata for supported providers.",
    )
    eval_parser.set_defaults(func=_cmd_eval)

    stats_parser = subcommands.add_parser(
        "stats",
        help="Compare baseline and candidate predictions.",
    )
    stats_parser.add_argument("--baseline", type=Path, required=True, help="Baseline scored JSONL.")
    stats_parser.add_argument(
        "--candidate",
        type=Path,
        required=True,
        help="Candidate scored JSONL.",
    )
    stats_parser.add_argument("--out", type=Path, required=True, help="stats.json output path.")
    stats_parser.add_argument("--seed", type=int, default=0)
    stats_parser.add_argument("--bootstrap-samples", type=int, default=1000)
    stats_parser.add_argument("--permutation-samples", type=int, default=1000)
    stats_parser.set_defaults(func=_cmd_stats)

    report_parser = subcommands.add_parser("report", help="Generate Markdown and HTML reports.")
    report_parser.add_argument("--run", type=Path, required=True, help="Run directory.")
    report_parser.add_argument("--title", default="PromptControlLab Report")
    report_parser.set_defaults(func=_cmd_report)

    explain_parser = subcommands.add_parser(
        "explain",
        help="Generate plain or technical explanation.json for a run.",
    )
    explain_parser.add_argument("--run", type=Path, required=True, help="Run directory.")
    explain_parser.add_argument("--level", choices=["plain", "technical"], default="plain")
    explain_parser.set_defaults(func=_cmd_explain)

    gate_parser = subcommands.add_parser("gate", help="Evaluate a run against policy thresholds.")
    gate_parser.add_argument("--run", type=Path, required=True, help="Run directory.")
    gate_parser.add_argument("--policy", type=Path, default=None, help="Gate policy YAML.")
    gate_parser.set_defaults(func=_cmd_gate)

    soft_parser = subcommands.add_parser("soft-hard", help="Analyze soft-to-hard projection risk.")
    soft_parser.add_argument("--soft", type=Path, required=True, help=".npz with array `soft`.")
    soft_parser.add_argument(
        "--vocab",
        type=Path,
        required=True,
        help=".npz with array `embeddings`.",
    )
    soft_parser.add_argument("--out", type=Path, required=True, help="Diagnostics directory.")
    soft_parser.add_argument("--explain-level", choices=["plain", "technical"], default=None)
    soft_parser.set_defaults(func=_cmd_soft_hard)

    traj_parser = subcommands.add_parser(
        "trajectory",
        help="Analyze hidden-state trajectory drift.",
    )
    traj_parser.add_argument("--states", type=Path, required=True, help=".npz with array `states`.")
    traj_parser.add_argument("--out", type=Path, required=True, help="Diagnostics directory.")
    traj_parser.add_argument("--tail", type=int, default=3)
    traj_parser.add_argument("--explain-level", choices=["plain", "technical"], default=None)
    traj_parser.set_defaults(func=_cmd_trajectory)

    riccati_parser = subcommands.add_parser("riccati", help="Analyze Riccati surrogate stability.")
    riccati_parser.add_argument("--matrices", type=Path, default=None, help=".npz with A/B/Q/R.")
    riccati_parser.add_argument("--trajectory", type=Path, default=None, help=".npz with states.")
    riccati_parser.add_argument("--out", type=Path, required=True, help="Diagnostics directory.")
    riccati_parser.add_argument("--iterations", type=int, default=200)
    riccati_parser.add_argument("--explain-level", choices=["plain", "technical"], default=None)
    riccati_parser.set_defaults(func=_cmd_riccati)

    tv_parser = subcommands.add_parser("tv-soft", help="Summarize time-varying soft-control lane.")
    tv_parser.add_argument(
        "--predictions",
        type=Path,
        required=True,
        help="Scored predictions JSONL.",
    )
    tv_parser.add_argument("--out", type=Path, required=True, help="Diagnostics directory.")
    tv_parser.add_argument("--baseline-method", default="static")
    tv_parser.add_argument("--explain-level", choices=["plain", "technical"], default=None)
    tv_parser.set_defaults(func=_cmd_tv_soft)
    return parser


def _cmd_init(args: argparse.Namespace) -> None:
    write_example_project(args.path)
    print(f"Created PromptControlLab example at {args.path}")


def _cmd_ingest_auto(args: argparse.Namespace) -> None:
    payload = ingest_auto_results(
        source_path=args.input,
        out_dir=args.out,
        prompt_id=args.prompt_id,
        name=args.name,
        experiment=args.experiment,
        score_name=args.score_name,
        model=args.model,
        provider=args.provider,
        method=args.method,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_ingest_promptfoo(args: argparse.Namespace) -> None:
    payload = ingest_promptfoo_results(
        source_path=args.input,
        out_dir=args.out,
        prompt_id=args.prompt_id,
        provider=args.provider,
        method=args.method,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_ingest_langfuse(args: argparse.Namespace) -> None:
    payload = ingest_langfuse_results(
        source_path=args.input,
        out_dir=args.out,
        name=args.name,
        score_name=args.score_name,
        model=args.model,
        provider=args.provider,
        method=args.method,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_ingest_langsmith(args: argparse.Namespace) -> None:
    payload = ingest_langsmith_results(
        source_path=args.input,
        out_dir=args.out,
        experiment=args.experiment,
        score_name=args.score_name,
        model=args.model,
        provider=args.provider,
        method=args.method,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_start(args: argparse.Namespace) -> None:
    choice = _start_choice(args.choice)
    if choice == "improve":
        prompt = _read_start_prompt(args.prompt, args.prompt_file)
        print("Beginner mode: improve a prompt")
        context = load_prompt_context(args.run)
        improvement = improve_prompt(
            prompt,
            context=context,
            goal="stability",
            language="auto",
            style="stable",
            token_mode=args.token_mode,
            max_tokens=args.max_tokens,
        )
        print(
            _format_improvement_output(
                improvement.improved_prompt,
                improvement.changes,
                improvement.token_report.to_json(),
            )
        )
        if args.out is not None:
            ensure_dir(args.out)
            (args.out / "improved_prompt.txt").write_text(
                improvement.improved_prompt + "\n",
                encoding="utf-8",
            )
            write_json(args.out / "prompt_improvement.json", improvement.to_json())
            (args.out / "prompt_diff.md").write_text(
                render_prompt_diff(improvement),
                encoding="utf-8",
            )
        return

    if choice == "guard":
        prompt = _read_start_prompt(args.prompt, args.prompt_file)
        print("Beginner mode: guard a prompt")
        result = guard_prompt(
            prompt,
            context=load_prompt_context(args.run),
            mode="suggest",
            profile=args.profile,
            token_mode=args.token_mode,
            max_tokens=args.max_tokens,
            policy_path=args.policy,
        )
        print(_format_guard_output(result.to_json()))
        return

    print("Beginner mode: create a prompt evaluation report")
    if args.config is not None:
        analyze_args = argparse.Namespace(
            config=args.config,
            data=None,
            baseline_predictions=None,
            candidate_predictions=None,
            out=args.out,
            metric=None,
            train_ratio=None,
            val_ratio=None,
            seed=None,
            bootstrap_samples=None,
            permutation_samples=None,
            explain_level=None,
            policy=args.policy,
            title=None,
            baseline_model=None,
            candidate_model=None,
            baseline_provider=None,
            candidate_provider=None,
            api_version=None,
            verify_model=False,
            prompt_id=None,
            prompt_file=None,
            prompt_version=None,
            baseline_prompt_id=None,
            baseline_prompt_file=None,
            baseline_prompt_version=None,
            candidate_prompt_id=None,
            candidate_prompt_file=None,
            candidate_prompt_version=None,
        )
        _cmd_analyze(analyze_args)
        return
    print(
        "\n".join(
            [
                "To create your first report, run:",
                "",
                "  pcl init --path demo",
                "  cd demo",
                "  pcl analyze --config promptcontrol.example.yaml --out runs/quick",
                "",
                "Result: a report.md/report.html that says whether the prompt change "
                "is worth keeping.",
            ]
        )
    )


def _cmd_improve(args: argparse.Namespace) -> None:
    prompt = _read_improve_prompt(args.prompt, args.prompt_file)
    context = load_prompt_context(args.run)
    improvement = improve_prompt(
        prompt,
        context=context,
        goal=args.goal,
        language=args.language,
        style=args.style,
        token_mode=args.token_mode,
        max_tokens=args.max_tokens,
    )
    print(
        _format_improvement_output(
            improvement.improved_prompt,
            improvement.changes,
            improvement.token_report.to_json(),
        )
    )
    if args.out is not None:
        ensure_dir(args.out)
        (args.out / "improved_prompt.txt").write_text(
            improvement.improved_prompt + "\n",
            encoding="utf-8",
        )
        write_json(args.out / "prompt_improvement.json", improvement.to_json())
        (args.out / "prompt_diff.md").write_text(
            render_prompt_diff(improvement),
            encoding="utf-8",
        )


def _cmd_guard(args: argparse.Namespace) -> None:
    prompt = _read_guard_prompt(args.prompt, args.prompt_file, args.stdin)
    context = load_prompt_context(args.run)
    project_config, project_config_path = load_project_config()
    policy_path = args.policy or _config_path(
        project_config,
        project_config_path,
        "guard_policy",
    )
    result = guard_prompt(
        prompt,
        context=context,
        mode=args.mode,
        profile=args.profile,
        token_mode=args.token_mode,
        max_tokens=args.max_tokens,
        language=args.language,
        policy_path=policy_path,
    )
    payload = result.to_json()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return
    print(_format_guard_output(payload))


def _cmd_model_detect(args: argparse.Namespace) -> None:
    sources = sum(value is not None for value in [args.response, args.predictions, args.model])
    if sources != 1:
        msg = "Provide exactly one of --response, --predictions, or --model"
        raise ValueError(msg)
    identity = detect_model_identity(
        provider=args.provider,
        model_id=args.model,
        response_path=args.response,
        predictions_path=args.predictions,
        api_version=args.api_version,
        verify=args.verify,
        request_id=args.request_id,
        request_path=args.request_json,
        request_sha256=args.request_sha256,
        response_sha256=args.response_sha256,
        provider_log_reference=args.provider_log_reference,
        signed_receipt=args.signed_receipt,
    )
    payload = identity.to_json()
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    if args.out is not None:
        write_json(args.out, payload)


def _cmd_model_drift(args: argparse.Namespace) -> None:
    payload = run_model_drift(run_dir=args.run, history_dir=args.history, out_path=args.out)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_validity(args: argparse.Namespace) -> None:
    payload = run_comparison_validity(
        baseline_dir=args.baseline,
        candidate_dir=args.candidate,
        out_path=args.out,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_compare_runs(args: argparse.Namespace) -> None:
    payload = compare_runs(
        baseline_dir=args.baseline,
        candidate_dir=args.candidate,
        out_dir=args.out,
        title=args.title,
        seed=args.seed,
        bootstrap_samples=args.bootstrap_samples,
        permutation_samples=args.permutation_samples,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_audit_diff(args: argparse.Namespace) -> None:
    project_config, _project_config_path = load_project_config(args.repo)
    expected_paths = list(args.expected_path) or get_config_list(project_config, "expected_paths")
    test_commands = list(args.test_command) or get_config_list(project_config, "test_commands")
    payload = run_audit_diff(
        repo=args.repo,
        before=args.before,
        after=args.after,
        out_dir=args.out,
        expected_paths=expected_paths,
        test_commands=test_commands,
        tests_run=list(args.tests_run),
        tests_passed=_optional_bool(args.tests_passed),
        test_timeout=args.test_timeout,
        allow_shell_test_command=args.allow_shell_test_command,
        sarif_path=args.sarif,
        secret_scanner=args.secret_scanner,
    )
    print(f"Wrote audit artifacts to {args.out}")
    print(f"Human review required: {payload['human_review_required']}")


def _cmd_history_index(args: argparse.Namespace) -> None:
    payload = index_history(runs_dir=args.runs, out_path=args.out)
    print(f"Wrote history index to {args.out} ({len(payload['runs'])} runs)")


def _cmd_history_compare(args: argparse.Namespace) -> None:
    compare_history(a_dir=args.a, b_dir=args.b, out_path=args.out)
    print(f"Wrote history comparison to {args.out}")


def _cmd_agent_run_build(args: argparse.Namespace) -> None:
    build_agent_run_manifest(
        run_dir=args.run,
        audit_dir=args.audit,
        agent=args.agent,
        out_path=args.out,
        policy=args.policy,
    )
    print(f"Wrote agent run manifest to {args.out}")


def _cmd_pr_summary(args: argparse.Namespace) -> None:
    payload = write_pr_summary(
        audit_path=args.audit,
        gate_path=args.gate,
        agent_run_path=args.agent_run,
        markdown_path=args.out,
        json_path=args.json_out,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_github_app_serve(args: argparse.Namespace) -> None:
    from promptcontrollab.github_app import serve_github_app

    serve_github_app(host=args.host, port=args.port)


def _cmd_install_plugin(args: argparse.Namespace) -> None:
    payload = install_plugin(args.plugin, target=args.target, force=args.force)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_doctor(args: argparse.Namespace) -> None:
    payload = run_doctor()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(format_doctor(payload))


def _cmd_ui(args: argparse.Namespace) -> None:
    project_config, project_config_path = load_project_config()
    runs_dir = args.runs or _config_path(project_config, project_config_path, "runs_dir") or Path(
        "runs"
    )
    policy_path = args.policy or _config_path(
        project_config,
        project_config_path,
        "guard_policy",
    )
    default_view = get_config_str(project_config, "ui.default_view", "workflows")
    missing = [
        module
        for module in ["streamlit", "plotly"]
        if importlib.util.find_spec(module) is None
    ]
    if missing:
        msg = (
            f"pcl ui requires optional UI dependencies ({', '.join(missing)} missing). "
            "Install them with "
            '`pip install -e ".[ui]"` or `uv pip install -e ".[ui]"`.'
        )
        raise PromptControlLabError(msg)
    app_path = Path(__file__).resolve().parent / "ui" / "app.py"
    env = os.environ.copy()
    env["PCL_UI_RUNS"] = str(runs_dir)
    env["PCL_UI_POLICY"] = str(policy_path) if policy_path is not None else ""
    env["PCL_UI_LANGUAGE"] = args.language
    env["PCL_UI_DEFAULT_VIEW"] = default_view
    env["PCL_UI_CONFIG"] = str(project_config_path) if project_config_path is not None else ""
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        f"--server.address={args.host}",
        f"--server.port={args.port}",
        f"--server.headless={str(args.no_browser).lower()}",
        "--browser.gatherUsageStats=false",
        "--client.toolbarMode=viewer",
    ]
    try:
        subprocess.run(command, env=env, check=True)
    except KeyboardInterrupt:
        return
    except subprocess.CalledProcessError as exc:
        msg = f"Streamlit exited with status {exc.returncode}"
        raise PromptControlLabError(msg) from exc


def _cmd_export_report(args: argparse.Namespace) -> None:
    payload = export_report_zip(run_dir=args.run, zip_path=args.out)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_research_demo(args: argparse.Namespace) -> None:
    payload = write_research_demo(out_dir=args.out, seed=args.seed)
    diagnostics = payload.get("diagnostics", {})
    diagnostic_names = sorted(diagnostics) if isinstance(diagnostics, dict) else []
    print(f"Wrote research demo to {args.out}")
    print(f"Diagnostics: {', '.join(diagnostic_names)}")
    print(f"Report: {args.out / 'research_diagnostics.md'}")


def _cmd_diagnose(args: argparse.Namespace) -> None:
    summary_dir = args.run if args.run is not None else args.out
    payload = run_research_diagnostics(
        run_dir=args.run,
        mode="diagnose",
        soft_path=args.soft,
        vocab_path=args.vocab,
        states_path=args.states,
        matrices_path=args.matrices,
        tv_predictions_path=args.tv_predictions,
        diagnostics_dir=args.out,
        summary_dir=summary_dir,
        baseline_method=args.baseline_method,
        tail=args.tail,
        iterations=args.iterations,
    )
    print(f"Wrote research diagnostics to {payload['diagnostics_dir']}")
    print(f"Report: {Path(str(payload['summary_dir'])) / 'research_diagnostics.md'}")


def _cmd_analyze(args: argparse.Namespace) -> None:
    project_config, project_config_path = load_project_config()
    config = load_analyze_config(args.config) if args.config is not None else {}
    paths = (
        resolve_analyze_paths(config, config_path=args.config) if args.config is not None else {}
    )
    data_path = _path_arg(args.data, paths.get("data"), "data")
    baseline_path = _path_arg(
        args.baseline_predictions,
        paths.get("baseline_predictions"),
        "baseline-predictions",
    )
    candidate_path = _path_arg(
        args.candidate_predictions,
        paths.get("candidate_predictions"),
        "candidate-predictions",
    )
    config_out = None
    if args.config is not None:
        config_out = get_config_path(config, "out", base_dir=args.config.parent)
    out_dir = _path_arg(args.out, config_out, "out")
    project_gate_policy = _config_path(project_config, project_config_path, "gate_policy")
    policy_path = args.policy if args.policy is not None else paths.get("gate_policy")
    if policy_path is None:
        policy_path = project_gate_policy
    metric = args.metric if args.metric is not None else config_metric(config, "exact_match")
    baseline_model = args.baseline_model or get_config_str(config, "baseline_model", "")
    candidate_model = args.candidate_model or get_config_str(config, "candidate_model", "")
    baseline_provider = args.baseline_provider or get_config_str(config, "baseline_provider", "")
    candidate_provider = args.candidate_provider or get_config_str(config, "candidate_provider", "")
    api_version = args.api_version or get_config_str(config, "api_version", "")
    train_ratio = (
        args.train_ratio
        if args.train_ratio is not None
        else get_config_float(config, "train_ratio", 0.5)
    )
    val_ratio = (
        args.val_ratio
        if args.val_ratio is not None
        else get_config_float(config, "val_ratio", 0.25)
    )
    seed = args.seed if args.seed is not None else get_config_int(config, "seed", 0)
    bootstrap_samples = (
        args.bootstrap_samples
        if args.bootstrap_samples is not None
        else get_config_int(config, "bootstrap_samples", 1000)
    )
    permutation_samples = (
        args.permutation_samples
        if args.permutation_samples is not None
        else get_config_int(config, "permutation_samples", 1000)
    )
    explain_level = (
        args.explain_level
        if args.explain_level is not None
        else get_config_str(config, "explain_level", "plain")
    )
    title = (
        args.title
        if args.title is not None
        else get_config_str(config, "title", "PromptControlLab Quick Analysis")
    )
    verify_model = args.verify_model or get_config_bool(config, "verify_model", False)
    prompt_id = args.prompt_id or get_config_str(config, "prompt_id", "")
    config_prompt_file = None
    if args.config is not None:
        config_prompt_file = paths.get("prompt_file")
    prompt_file = args.prompt_file if args.prompt_file is not None else config_prompt_file
    prompt_version = args.prompt_version or get_config_str(config, "prompt_version", "")
    baseline_prompt_id = args.baseline_prompt_id or get_config_str(
        config,
        "baseline_prompt_id",
        "",
    )
    candidate_prompt_id = args.candidate_prompt_id or get_config_str(
        config,
        "candidate_prompt_id",
        "",
    )
    baseline_prompt_file = args.baseline_prompt_file
    candidate_prompt_file = args.candidate_prompt_file
    if args.config is not None:
        if baseline_prompt_file is None:
            baseline_prompt_file = paths.get("baseline_prompt_file")
        if candidate_prompt_file is None:
            candidate_prompt_file = paths.get("candidate_prompt_file")
    baseline_prompt_version = args.baseline_prompt_version or get_config_str(
        config,
        "baseline_prompt_version",
        "",
    )
    candidate_prompt_version = args.candidate_prompt_version or get_config_str(
        config,
        "candidate_prompt_version",
        "",
    )
    run_quick_analysis(
        data_path=data_path,
        baseline_predictions_path=baseline_path,
        candidate_predictions_path=candidate_path,
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
        baseline_provider=baseline_provider or None,
        baseline_model=baseline_model or None,
        candidate_provider=candidate_provider or None,
        candidate_model=candidate_model or None,
        api_version=api_version or None,
        verify_model=verify_model,
        prompt_id=prompt_id or None,
        prompt_file=prompt_file,
        prompt_version=prompt_version or None,
        baseline_prompt_id=baseline_prompt_id or None,
        baseline_prompt_file=baseline_prompt_file,
        baseline_prompt_version=baseline_prompt_version or None,
        candidate_prompt_id=candidate_prompt_id or None,
        candidate_prompt_file=candidate_prompt_file,
        candidate_prompt_version=candidate_prompt_version or None,
    )
    print(f"Wrote quick analysis artifacts to {out_dir}")


def _cmd_split(args: argparse.Namespace) -> None:
    tasks = load_tasks(args.data)
    split = make_split(
        tasks,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        seed=args.seed,
    )
    write_split(args.out / "splits.json", split)
    print(f"Wrote split manifest to {args.out / 'splits.json'}")


def _cmd_eval(args: argparse.Namespace) -> None:
    run_import_eval(
        data_path=args.data,
        predictions_path=args.predictions,
        out_dir=args.out,
        metric=args.metric,
        method=args.method,
        provider=args.provider,
        model_id=args.model,
        api_version=args.api_version,
        verify_model=args.verify_model,
    )
    print(f"Wrote scored predictions and metrics to {args.out}")


def _cmd_stats(args: argparse.Namespace) -> None:
    compare_prediction_files(
        baseline_path=args.baseline,
        candidate_path=args.candidate,
        out_path=args.out,
        seed=args.seed,
        bootstrap_samples=args.bootstrap_samples,
        permutation_samples=args.permutation_samples,
    )
    print(f"Wrote statistical comparison to {args.out}")


def _cmd_report(args: argparse.Namespace) -> None:
    md_path, html_path = generate_report(args.run, title=args.title)
    print(f"Wrote reports to {md_path} and {html_path}")


def _cmd_explain(args: argparse.Namespace) -> None:
    generate_explanation(args.run, level=args.level)
    print(f"Wrote explanation to {args.run / 'explanation.json'}")


def _cmd_gate(args: argparse.Namespace) -> None:
    project_config, project_config_path = load_project_config()
    policy_path = args.policy or _config_path(project_config, project_config_path, "gate_policy")
    if policy_path is None:
        msg = "Missing required --policy argument or .promptcontrol.yaml gate_policy"
        raise ValueError(msg)
    run_gate(args.run, policy_path=policy_path)
    print(f"Wrote gate result to {args.run / 'gate_result.json'}")


def _cmd_soft_hard(args: argparse.Namespace) -> None:
    analyze_soft_hard(soft_path=args.soft, vocab_path=args.vocab, out_dir=args.out)
    _maybe_refresh_explanation(args.out, args.explain_level)
    print(f"Wrote soft-hard diagnostics to {args.out}")


def _cmd_trajectory(args: argparse.Namespace) -> None:
    analyze_trajectory(states_path=args.states, out_dir=args.out, tail=args.tail)
    _maybe_refresh_explanation(args.out, args.explain_level)
    print(f"Wrote trajectory diagnostics to {args.out}")


def _cmd_riccati(args: argparse.Namespace) -> None:
    analyze_riccati(
        matrices_path=args.matrices,
        trajectory_path=args.trajectory,
        out_dir=args.out,
        iterations=args.iterations,
    )
    _maybe_refresh_explanation(args.out, args.explain_level)
    print(f"Wrote Riccati diagnostics to {args.out}")


def _cmd_tv_soft(args: argparse.Namespace) -> None:
    summarize_tv_soft(
        predictions_path=args.predictions,
        out_dir=args.out,
        baseline_method=args.baseline_method,
    )
    _maybe_refresh_explanation(args.out, args.explain_level)
    print(f"Wrote time-varying soft-control summary to {args.out}")


def _path_arg(value: Path | None, config_value: Path | None, name: str) -> Path:
    path = value if value is not None else config_value
    if path is None:
        msg = f"Missing required --{name} argument or config key"
        raise ValueError(msg)
    return path


def _config_path(config: JsonDict, config_path: Path | None, key: str) -> Path | None:
    if config_path is None:
        return None
    return get_config_path(config, key, base_dir=config_path.parent)


def _maybe_refresh_explanation(out_dir: Path, level: str | None) -> None:
    if level is None:
        return
    run_dir = out_dir.parent if out_dir.name == "diagnostics" else out_dir
    generate_explanation(run_dir, level=level)


def _read_improve_prompt(prompt: str | None, prompt_file: Path | None) -> str:
    if prompt is not None and prompt_file is not None:
        msg = "Use either --prompt or --prompt-file, not both"
        raise ValueError(msg)
    if prompt is None and prompt_file is None:
        msg = "Provide --prompt or --prompt-file"
        raise ValueError(msg)
    if prompt_file is not None:
        return prompt_file.read_text(encoding="utf-8")
    if prompt is None:
        msg = "Provide --prompt or --prompt-file"
        raise ValueError(msg)
    return prompt


def _read_guard_prompt(prompt: str | None, prompt_file: Path | None, use_stdin: bool) -> str:
    sources = sum(source is not None for source in [prompt, prompt_file]) + int(use_stdin)
    if sources != 1:
        msg = "Provide exactly one of --prompt, --prompt-file, or --stdin"
        raise ValueError(msg)
    if use_stdin:
        return sys.stdin.read()
    if prompt_file is not None:
        return prompt_file.read_text(encoding="utf-8")
    if prompt is None:
        msg = "Provide exactly one of --prompt, --prompt-file, or --stdin"
        raise ValueError(msg)
    return prompt


def _optional_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    return value == "true"


def _format_guard_output(payload: JsonDict) -> str:
    lines = [
        "PromptControlLab Guard",
        "",
        f"Decision: {payload['action']}",
        f"Risk: {payload['risk_level']}",
        f"Profile: {payload['profile']}",
        f"Required review: {payload.get('required_review', False)}",
        f"Risk categories: {payload.get('risk_categories', [])}",
        "",
        "Plain summary:",
        str(payload.get("plain_summary", "Review the guarded prompt before sending.")),
        "",
        "Why:",
    ]
    lines.extend(f"- {reason}" for reason in payload["reasons"])
    lines += [
        "",
        "Suggested prompt:",
        "",
        str(payload["improved_prompt"]),
        "",
        "Next steps:",
    ]
    lines.extend(_guard_next_steps(payload))
    violations = payload.get("policy_violations", [])
    if violations:
        lines += ["", "Policy violations:"]
        lines.extend(
            f"- {item.get('id')}: {item.get('message')} ({item.get('severity')})"
            for item in violations
            if isinstance(item, dict)
        )
    token_report = payload["token_report"]
    lines += [
        "",
        "Estimated token cost:",
        f"- Original prompt: {token_report['original_estimated_tokens']}",
        f"- Guarded prompt: {token_report['improved_estimated_tokens']}",
        f"- Token mode: {token_report['token_mode']}",
    ]
    if token_report["max_tokens"] is not None:
        lines.append(f"- Max tokens: {token_report['max_tokens']}")
        lines.append(f"- Within budget: {payload['within_budget']}")
    return "\n".join(lines)


def _guard_next_steps(payload: JsonDict) -> list[str]:
    if payload["action"] == "block":
        return [
            "Revise the prompt before sending it to the agent.",
            "Add scope, target files, failing behavior, and verification steps.",
        ]
    if payload.get("required_review", False):
        return [
            "Have a human review the risky parts before agent execution.",
            "Tighten scope and add a concrete test or verification command.",
        ]
    return [
        "Use the suggested prompt directly, or copy the missing context into your original prompt.",
        "Keep the JSON output for wrappers or IDE integrations when automation is needed.",
    ]


def _format_improvement_output(
    improved_prompt: str,
    changes: list[str],
    token_report: JsonDict,
) -> str:
    lines = ["Optimized prompt:", "", improved_prompt, "", "Why it changed:"]
    lines.extend(f"- {change}" for change in changes)
    lines += [
        "",
        "Estimated token cost:",
        f"- Original prompt: {token_report['original_estimated_tokens']}",
        f"- Optimized prompt: {token_report['improved_estimated_tokens']}",
        f"- Token mode: {token_report['token_mode']}",
    ]
    if token_report["max_tokens"] is not None:
        lines.append(f"- Max tokens: {token_report['max_tokens']}")
        lines.append(f"- Within budget: {token_report['within_budget']}")
    return "\n".join(lines)


def _start_choice(value: str | None) -> str:
    if value is not None:
        return value
    print(
        "\n".join(
            [
                "What do you want to do?",
                "1) Make my prompt clearer",
                "2) Check a prompt before sending it to an AI tool",
                "3) Compare prompts and create a report",
            ]
        )
    )
    raw = input("Choose 1, 2, or 3: ").strip().lower()
    choices = {
        "1": "improve",
        "improve": "improve",
        "2": "guard",
        "guard": "guard",
        "3": "analyze",
        "analyze": "analyze",
    }
    if raw not in choices:
        msg = "Choose 1, 2, or 3"
        raise ValueError(msg)
    return choices[raw]


def _read_start_prompt(prompt: str | None, prompt_file: Path | None) -> str:
    if prompt is not None or prompt_file is not None:
        return _read_improve_prompt(prompt, prompt_file)
    return input("Paste your prompt: ")
