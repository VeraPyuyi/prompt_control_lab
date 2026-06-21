"""Command line interface for PromptControlLab."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import webbrowser
from collections.abc import Sequence
from pathlib import Path

from promptcontrollab.agent_run import build_agent_run_manifest
from promptcontrollab.artifact_export import export_report_zip
from promptcontrollab.audit_diff import run_audit_diff
from promptcontrollab.claim_check import run_claim_check
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
from promptcontrollab.ecosystem_demo import run_ecosystem_demo, write_ecosystem_scorecard
from promptcontrollab.errors import PromptControlLabError
from promptcontrollab.evaluation import run_import_eval
from promptcontrollab.evidence_card import write_evidence_card
from promptcontrollab.evidence_gate import run_evidence_gate
from promptcontrollab.explain import generate_explanation
from promptcontrollab.external_evidence import (
    attach_evidence_gate_to_audit,
    build_external_evidence,
    build_external_evidence_audit,
    verify_source_inputs,
)
from promptcontrollab.files import JsonDict, ensure_dir, read_json, write_json
from promptcontrollab.gate import run_gate
from promptcontrollab.hf_hidden import extract_hidden_states
from promptcontrollab.history import compare_history, index_history
from promptcontrollab.ingest import (
    ingest_auto_results,
    ingest_deepeval_results,
    ingest_langfuse_results,
    ingest_langsmith_results,
    ingest_prompt_optimizer_assets,
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
from promptcontrollab.research_workflow import (
    run_research_diagnostics,
    verify_research_bundle_index,
    write_research_bundle_index,
    write_research_demo,
    write_research_gap_status,
)
from promptcontrollab.riccati import analyze_riccati
from promptcontrollab.run_comparison import compare_runs
from promptcontrollab.scaffold_check import write_scaffold_check
from promptcontrollab.soft_hard import analyze_soft_hard
from promptcontrollab.splitting import load_tasks, make_split, write_split
from promptcontrollab.statistics import compare_prediction_files
from promptcontrollab.templates import write_example_project, write_external_examples
from promptcontrollab.tool_choice import (
    adoption_path_rows,
    choose_tool_for_need,
    format_tool_choice,
    market_gap_action_rows,
    render_tool_choice_markdown,
    tool_choice_lanes,
)
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

    _ensure_utf8_for_windows_pipes()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (PromptControlLabError, ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"pcl: error: {exc}", file=sys.stderr)
        return 2
    return 0


def _ensure_utf8_for_windows_pipes() -> None:
    """Make redirected Windows CLI output readable in UTF-8 based tools."""

    _reconfigure_windows_pipe(sys.stdout)
    _reconfigure_windows_pipe(sys.stderr)


def _reconfigure_windows_pipe(stream: object, *, os_name: str | None = None) -> bool:
    if (os_name or os.name) != "nt":
        return False
    encoding = str(getattr(stream, "encoding", "") or "").lower().replace("_", "-")
    if "utf-8" in encoding or "utf8" in encoding:
        return False
    isatty = getattr(stream, "isatty", None)
    try:
        if callable(isatty) and isatty():
            return False
    except OSError:
        return False
    reconfigure = getattr(stream, "reconfigure", None)
    if not callable(reconfigure):
        return False
    try:
        reconfigure(encoding="utf-8", errors="replace")
    except (TypeError, ValueError, OSError):
        return False
    return True


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
        choices=[
            "demo",
            "research",
            "choose",
            "ecosystem",
            "import",
            "evidence",
            "improve",
            "guard",
            "analyze",
        ],
        default=None,
        help="Skip the menu and choose a beginner scenario.",
    )
    start_parser.add_argument(
        "--guide",
        action="store_true",
        help="Print a goal-based beginner guide and exit.",
    )
    start_parser.add_argument(
        "--language",
        choices=["en", "zh"],
        default="en",
        help="Language for beginner guide and menu text.",
    )
    start_parser.add_argument("--prompt", default=None, help="Prompt string for improve/guard.")
    start_parser.add_argument("--prompt-file", type=Path, default=None, help="Prompt text file.")
    start_parser.add_argument(
        "--need",
        default=None,
        help="Free-text need used when choice is choose.",
    )
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
    start_parser.add_argument(
        "--tool",
        choices=["auto", "promptfoo", "langfuse", "langsmith", "deepeval", "prompt-optimizer"],
        default="auto",
        help="External tool used when choice is import.",
    )
    start_parser.add_argument("--input", type=Path, default=None, help="External export file.")
    start_parser.add_argument("--prompt-id", default=None, help="Promptfoo prompt filter.")
    start_parser.add_argument("--name", default=None, help="Langfuse observation name filter.")
    start_parser.add_argument("--experiment", default=None, help="LangSmith experiment filter.")
    start_parser.add_argument("--score-name", default=None, help="External score/metric filter.")
    start_parser.add_argument("--model", default=None, help="External model id filter.")
    start_parser.add_argument("--provider", default=None, help="External provider filter.")
    start_parser.add_argument("--method", default=None, help="Method name written to predictions.")
    start_parser.add_argument("--asset-id", default=None, help="prompt-optimizer asset id filter.")
    start_parser.add_argument("--seed", type=int, default=0, help="Synthetic fixture seed.")
    start_parser.add_argument(
        "--open-report",
        action="store_true",
        help="Open the generated demo report in the default browser.",
    )
    start_parser.set_defaults(func=_cmd_start)

    quickstart_parser = subcommands.add_parser(
        "quickstart",
        help="Create a runnable demo project and quick report.",
    )
    quickstart_parser.add_argument(
        "--out",
        type=Path,
        default=Path("demo"),
        help="Demo project directory.",
    )
    quickstart_parser.add_argument(
        "--language",
        choices=["en", "zh"],
        default="en",
        help="Output language.",
    )
    quickstart_parser.add_argument("--seed", type=int, default=0, help="Synthetic fixture seed.")
    quickstart_parser.add_argument(
        "--open-report",
        action="store_true",
        help="Open the generated report in the default browser.",
    )
    quickstart_parser.set_defaults(func=_cmd_quickstart)

    choose_parser = subcommands.add_parser(
        "choose",
        help="Choose which adjacent tool to use first, and where PCL adds evidence.",
    )
    choose_parser.add_argument(
        "--need",
        default=None,
        help=(
            "Free-text need, such as security, prompt writing, observability, "
            "unit tests, or research evidence."
        ),
    )
    choose_parser.add_argument("--language", choices=["en", "zh"], default="en")
    choose_parser.add_argument("--json", action="store_true")
    choose_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write tool-choice JSON plus a sibling Markdown summary.",
    )
    choose_parser.set_defaults(func=_cmd_choose)

    init_parser = subcommands.add_parser("init", help="Create an example project.")
    init_parser.add_argument("--path", type=Path, default=Path("."), help="Project directory.")
    init_parser.set_defaults(func=_cmd_init)

    ingest_parser = subcommands.add_parser(
        "ingest",
        aliases=["import"],
        help="Import external eval-tool results or prompt assets into PromptControlLab artifacts.",
    )
    ingest_subcommands = ingest_parser.add_subparsers(dest="ingest_command", required=True)
    auto_ingest = ingest_subcommands.add_parser(
        "auto",
        help=(
            "Auto-detect Promptfoo/DeepEval/Langfuse/LangSmith scored exports or "
            "prompt-optimizer prompt assets and import them."
        ),
    )
    auto_ingest.add_argument("--input", type=Path, required=True, help="External export file.")
    auto_ingest.add_argument("--out", type=Path, required=True, help="PCL run directory.")
    auto_ingest.add_argument("--prompt-id", default=None, help="Promptfoo prompt filter.")
    auto_ingest.add_argument("--name", default=None, help="Langfuse observation name filter.")
    auto_ingest.add_argument("--experiment", default=None, help="LangSmith experiment filter.")
    auto_ingest.add_argument(
        "--score-name",
        default=None,
        help="Langfuse/LangSmith/DeepEval score or metric filter.",
    )
    auto_ingest.add_argument("--model", default=None, help="Model id filter.")
    auto_ingest.add_argument("--provider", default=None, help="Provider filter.")
    auto_ingest.add_argument("--method", default=None, help="Method name written to predictions.")
    auto_ingest.add_argument(
        "--asset-id",
        default=None,
        help="prompt-optimizer asset id/title filter when importing prompt assets.",
    )
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
    deepeval_ingest = ingest_subcommands.add_parser(
        "deepeval",
        help="Import DeepEval local TestRun JSON output.",
    )
    deepeval_ingest.add_argument("--input", type=Path, required=True, help="DeepEval JSON file.")
    deepeval_ingest.add_argument("--out", type=Path, required=True, help="PCL run directory.")
    deepeval_ingest.add_argument(
        "--score-name",
        default=None,
        help="DeepEval metric name to import when multiple metrics exist.",
    )
    deepeval_ingest.add_argument(
        "--model",
        default=None,
        help="Model id filter or override.",
    )
    deepeval_ingest.add_argument(
        "--provider",
        default=None,
        help="Provider filter or override.",
    )
    deepeval_ingest.add_argument(
        "--method",
        default=None,
        help="Method name written to PCL predictions. Defaults to the run name.",
    )
    deepeval_ingest.set_defaults(func=_cmd_ingest_deepeval)
    prompt_optimizer_ingest = ingest_subcommands.add_parser(
        "prompt-optimizer",
        help="Import prompt-optimizer favorites/templates as prompt assets, not scored evidence.",
    )
    prompt_optimizer_ingest.add_argument(
        "--input",
        type=Path,
        required=True,
        help="prompt-optimizer JSON export, such as favorites or template export.",
    )
    prompt_optimizer_ingest.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output directory for prompt_assets.json and gap plan artifacts.",
    )
    prompt_optimizer_ingest.add_argument(
        "--asset-id",
        default=None,
        help="Optional asset id or title to import from a multi-asset export.",
    )
    prompt_optimizer_ingest.set_defaults(func=_cmd_ingest_prompt_optimizer)

    scaffold_check_parser = subcommands.add_parser(
        "scaffold-check",
        help="Check whether a generated eval scaffold is ready for paired scoring.",
    )
    scaffold_source = scaffold_check_parser.add_mutually_exclusive_group(required=True)
    scaffold_source.add_argument(
        "--run",
        type=Path,
        help="Run directory containing eval_scaffold/.",
    )
    scaffold_source.add_argument(
        "--scaffold",
        type=Path,
        help="Path to an eval_scaffold directory.",
    )
    scaffold_check_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional JSON output path. Defaults to <eval_scaffold>/scaffold_check.json.",
    )
    scaffold_check_parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero unless the scaffold status is pass.",
    )
    scaffold_check_parser.set_defaults(func=_cmd_scaffold_check)

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

    evidence_from_parser = subcommands.add_parser(
        "evidence-from",
        help=(
            "Import baseline/candidate exports from Promptfoo, Langfuse, LangSmith, or DeepEval "
            "and generate a PCL evidence card."
        ),
    )
    evidence_from_parser.add_argument(
        "--tool",
        choices=["auto", "promptfoo", "langfuse", "langsmith", "deepeval"],
        default="auto",
        help="External export type. Use auto to detect each input file.",
    )
    evidence_from_parser.add_argument(
        "--baseline-input",
        type=Path,
        required=True,
        help="Baseline external export file.",
    )
    evidence_from_parser.add_argument(
        "--candidate-input",
        type=Path,
        required=True,
        help="Candidate external export file.",
    )
    evidence_from_parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Evidence bundle output directory.",
    )
    evidence_from_parser.add_argument(
        "--score-name",
        default=None,
        help="Langfuse/LangSmith/DeepEval score or metric name to import.",
    )
    evidence_from_parser.add_argument(
        "--provider",
        default=None,
        help="Provider filter shared by baseline and candidate.",
    )
    evidence_from_parser.add_argument("--baseline-provider", default=None)
    evidence_from_parser.add_argument("--candidate-provider", default=None)
    evidence_from_parser.add_argument(
        "--model",
        default=None,
        help="Model filter shared by baseline and candidate.",
    )
    evidence_from_parser.add_argument("--baseline-model", default=None)
    evidence_from_parser.add_argument("--candidate-model", default=None)
    evidence_from_parser.add_argument(
        "--baseline-prompt-id",
        default=None,
        help="Baseline Promptfoo prompt id, or prompt identity to record.",
    )
    evidence_from_parser.add_argument(
        "--candidate-prompt-id",
        default=None,
        help="Candidate Promptfoo prompt id, or prompt identity to record.",
    )
    evidence_from_parser.add_argument(
        "--baseline-name",
        default=None,
        help="Baseline Langfuse observation/name filter.",
    )
    evidence_from_parser.add_argument(
        "--candidate-name",
        default=None,
        help="Candidate Langfuse observation/name filter.",
    )
    evidence_from_parser.add_argument(
        "--baseline-experiment",
        default=None,
        help="Baseline LangSmith experiment filter.",
    )
    evidence_from_parser.add_argument(
        "--candidate-experiment",
        default=None,
        help="Candidate LangSmith experiment filter.",
    )
    evidence_from_parser.add_argument(
        "--split-hash",
        default=None,
        help="Optional shared split hash to record on both imported runs.",
    )
    evidence_from_parser.add_argument("--baseline-method", default="baseline")
    evidence_from_parser.add_argument("--candidate-method", default="candidate")
    evidence_from_parser.add_argument("--title", default="PromptControlLab External Evidence")
    evidence_from_parser.add_argument("--seed", type=int, default=0)
    evidence_from_parser.add_argument("--bootstrap-samples", type=int, default=1000)
    evidence_from_parser.add_argument("--permutation-samples", type=int, default=1000)
    evidence_from_parser.set_defaults(func=_cmd_evidence_from)

    evidence_audit_parser = subcommands.add_parser(
        "evidence-audit",
        help=(
            "Import external baseline/candidate exports, add PCL evidence, run gap-status, "
            "and verify the research bundle."
        ),
    )
    evidence_audit_parser.add_argument(
        "--tool",
        choices=["auto", "promptfoo", "langfuse", "langsmith", "deepeval"],
        default="auto",
        help="External export type. Use auto to detect each input file.",
    )
    evidence_audit_parser.add_argument(
        "--baseline-input",
        type=Path,
        required=True,
        help="Baseline external export file.",
    )
    evidence_audit_parser.add_argument(
        "--candidate-input",
        type=Path,
        required=True,
        help="Candidate external export file.",
    )
    evidence_audit_parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Evidence audit output directory.",
    )
    evidence_audit_parser.add_argument(
        "--score-name",
        default=None,
        help="Langfuse/LangSmith/DeepEval score or metric name to import.",
    )
    evidence_audit_parser.add_argument(
        "--provider",
        default=None,
        help="Provider filter shared by baseline and candidate.",
    )
    evidence_audit_parser.add_argument("--baseline-provider", default=None)
    evidence_audit_parser.add_argument("--candidate-provider", default=None)
    evidence_audit_parser.add_argument(
        "--model",
        default=None,
        help="Model filter shared by baseline and candidate.",
    )
    evidence_audit_parser.add_argument("--baseline-model", default=None)
    evidence_audit_parser.add_argument("--candidate-model", default=None)
    evidence_audit_parser.add_argument(
        "--baseline-prompt-id",
        default=None,
        help="Baseline Promptfoo prompt id, or prompt identity to record.",
    )
    evidence_audit_parser.add_argument(
        "--candidate-prompt-id",
        default=None,
        help="Candidate Promptfoo prompt id, or prompt identity to record.",
    )
    evidence_audit_parser.add_argument(
        "--baseline-name",
        default=None,
        help="Baseline Langfuse observation/name filter.",
    )
    evidence_audit_parser.add_argument(
        "--candidate-name",
        default=None,
        help="Candidate Langfuse observation/name filter.",
    )
    evidence_audit_parser.add_argument(
        "--baseline-experiment",
        default=None,
        help="Baseline LangSmith experiment filter.",
    )
    evidence_audit_parser.add_argument(
        "--candidate-experiment",
        default=None,
        help="Candidate LangSmith experiment filter.",
    )
    evidence_audit_parser.add_argument(
        "--split-hash",
        default=None,
        help="Optional shared split hash to record on both imported runs.",
    )
    evidence_audit_parser.add_argument("--baseline-method", default="baseline")
    evidence_audit_parser.add_argument("--candidate-method", default="candidate")
    evidence_audit_parser.add_argument(
        "--title",
        default="PromptControlLab External Evidence Audit",
    )
    evidence_audit_parser.add_argument("--seed", type=int, default=0)
    evidence_audit_parser.add_argument("--bootstrap-samples", type=int, default=1000)
    evidence_audit_parser.add_argument("--permutation-samples", type=int, default=1000)
    evidence_audit_parser.set_defaults(func=_cmd_evidence_audit)

    source_verify_parser = subcommands.add_parser(
        "source-verify",
        help="Verify original external export files against recorded source-input hashes.",
    )
    source_verify_parser.add_argument(
        "--run",
        type=Path,
        required=True,
        help="Run directory containing source_inputs provenance.",
    )
    source_verify_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional JSON output path. Markdown/HTML siblings are written next to it.",
    )
    source_verify_parser.add_argument(
        "--strict",
        action="store_true",
        help="Return a non-zero exit code when source verification does not pass.",
    )
    source_verify_parser.set_defaults(func=_cmd_source_verify)

    evidence_gate_parser = subcommands.add_parser(
        "evidence-gate",
        help="Run a CI/reviewer gate over source and research-bundle evidence.",
    )
    evidence_gate_parser.add_argument(
        "--run",
        type=Path,
        required=True,
        help="Run directory containing PCL evidence artifacts.",
    )
    evidence_gate_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional JSON output path. Markdown/HTML siblings are written next to it.",
    )
    evidence_gate_parser.add_argument(
        "--require-source",
        action="store_true",
        help="Fail when source input provenance is absent or not pass.",
    )
    evidence_gate_parser.add_argument(
        "--allow-missing-bundle",
        action="store_true",
        help="Return needs_review instead of fail when research_bundle.json is absent.",
    )
    evidence_gate_parser.add_argument(
        "--strict",
        action="store_true",
        help="Return a non-zero exit code when the evidence gate status is not pass.",
    )
    evidence_gate_parser.set_defaults(func=_cmd_evidence_gate)

    ecosystem_demo_parser = subcommands.add_parser(
        "ecosystem-demo",
        help="Run bundled Promptfoo/DeepEval/Langfuse/LangSmith bridge examples.",
    )
    ecosystem_demo_parser.add_argument(
        "--examples",
        type=Path,
        default=Path("examples/external"),
        help="Directory containing external export examples.",
    )
    ecosystem_demo_parser.add_argument(
        "--out",
        type=Path,
        default=Path("runs/ecosystem-demo"),
        help="Output directory for all bridge bundles.",
    )
    ecosystem_demo_parser.add_argument(
        "--split-hash",
        default="external-demo-split",
        help="Stable split hash recorded into imported manifests.",
    )
    ecosystem_demo_parser.add_argument("--provider", default="openai")
    ecosystem_demo_parser.add_argument("--model", default="gpt-4o-mini-20260601")
    ecosystem_demo_parser.add_argument("--bootstrap-samples", type=int, default=1000)
    ecosystem_demo_parser.add_argument("--permutation-samples", type=int, default=1000)
    ecosystem_demo_parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a concise market-readiness summary instead of the full JSON payload.",
    )
    ecosystem_demo_parser.set_defaults(func=_cmd_ecosystem_demo)

    ecosystem_scorecard_parser = subcommands.add_parser(
        "ecosystem-scorecard",
        help="Regenerate ecosystem_scorecard.json/md/html for an ecosystem bridge run.",
    )
    ecosystem_scorecard_parser.add_argument(
        "--run",
        type=Path,
        required=True,
        help="Existing ecosystem demo run directory.",
    )
    ecosystem_scorecard_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=(
            "Output JSON file or output directory. Defaults to "
            "<run>/ecosystem_scorecard.json."
        ),
    )
    ecosystem_scorecard_parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a concise market-readiness summary instead of the full JSON payload.",
    )
    ecosystem_scorecard_parser.set_defaults(func=_cmd_ecosystem_scorecard)

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
        "--evidence-gate",
        type=Path,
        default=None,
        help="evidence_gate_result.json path.",
    )
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
    research_demo_parser.add_argument("--language", choices=["en", "zh"], default="en")
    research_demo_parser.set_defaults(func=_cmd_research_demo)

    research_quickstart_parser = subcommands.add_parser(
        "research-quickstart",
        help="Create a paper-style research demo, run diagnose, and optionally open the bundle.",
    )
    research_quickstart_parser.add_argument(
        "--out",
        type=Path,
        default=Path("runs") / "research-demo",
        help="Demo run directory.",
    )
    research_quickstart_parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Synthetic fixture seed.",
    )
    research_quickstart_parser.add_argument("--language", choices=["en", "zh"], default="en")
    research_quickstart_parser.add_argument(
        "--open-report",
        action="store_true",
        help="Open the generated research bundle in the default browser.",
    )
    research_quickstart_parser.set_defaults(func=_cmd_research_quickstart)

    research_bundle_parser = subcommands.add_parser(
        "research-bundle",
        help="Refresh research_bundle.json/html for a run directory.",
    )
    research_bundle_parser.add_argument("--run", type=Path, required=True, help="Run directory.")
    research_bundle_parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify hashes in the existing bundle instead of refreshing it.",
    )
    research_bundle_parser.add_argument(
        "--strict",
        action="store_true",
        help="With --verify, return a non-zero exit code when bundle verification does not pass.",
    )
    research_bundle_parser.set_defaults(func=_cmd_research_bundle)

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
    diagnose_parser.add_argument("--language", choices=["en", "zh"], default="en")
    diagnose_parser.set_defaults(func=_cmd_diagnose)

    gap_status_parser = subcommands.add_parser(
        "gap-status",
        help="Check whether research_gap_plan actions have produced their expected artifacts.",
    )
    gap_status_parser.add_argument("--run", type=Path, required=True, help="Run directory.")
    gap_status_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output JSON file or directory. Defaults to <run>/research_gap_status.json.",
    )
    gap_status_parser.set_defaults(func=_cmd_gap_status)

    hidden_parser = subcommands.add_parser(
        "extract-hidden",
        help="Extract HuggingFace hidden states into a trajectory-compatible .npz file.",
    )
    hidden_parser.add_argument("--model", required=True, help="HuggingFace model id or path.")
    hidden_parser.add_argument(
        "--prompts",
        type=Path,
        required=True,
        help="Prompt JSONL or text file.",
    )
    hidden_parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output .npz path containing array `states`.",
    )
    hidden_parser.add_argument("--layer", type=int, default=-1)
    hidden_parser.add_argument(
        "--pool",
        choices=["last-token", "mean", "token-trajectory"],
        default="last-token",
    )
    hidden_parser.add_argument("--max-items", type=int, default=None)
    hidden_parser.add_argument("--max-length", type=int, default=512)
    hidden_parser.add_argument("--device", default="auto")
    hidden_parser.add_argument("--trust-remote-code", action="store_true")
    hidden_parser.set_defaults(func=_cmd_extract_hidden)

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

    evidence_parser = subcommands.add_parser(
        "evidence-card",
        help="Generate a prompt optimization evidence card from run artifacts.",
    )
    evidence_parser.add_argument("--run", type=Path, required=True, help="Run directory.")
    evidence_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Markdown output path. A sibling HTML file is also written.",
    )
    evidence_parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="JSON output path. Defaults to RUN/evidence_card.json.",
    )
    evidence_parser.set_defaults(func=_cmd_evidence_card)

    claim_parser = subcommands.add_parser(
        "claim-check",
        help="Check what prompt-optimization claim the run artifacts support.",
    )
    claim_parser.add_argument("--run", type=Path, required=True, help="Run directory.")
    claim_parser.add_argument(
        "--claim",
        choices=["paired", "partial-research", "full-research"],
        default="paired",
        help="Claim scope to check against recorded artifacts.",
    )
    claim_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional JSON output path. Sibling Markdown and HTML files are also written.",
    )
    claim_parser.set_defaults(func=_cmd_claim_check)

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
    print(_format_init_output(args.path))


def _format_init_output(
    path: Path,
    *,
    language: str = "en",
    quick_run: Path | None = None,
    history_index: Path | None = None,
) -> str:
    """Return concise next steps after creating an example project."""

    if language == "zh":
        lines = [
            f"已创建 PromptControlLab 示例项目: {path}",
        ]
        if quick_run is not None:
            lines.extend(
                [
                    f"已生成 quick report: {quick_run / 'report.html'}",
                    f"已生成 gate result: {quick_run / 'gate_result.json'}",
                    *_format_quick_run_summary(quick_run, language=language),
                ]
            )
        if history_index is not None:
            lines.append(f"已生成 history index: {history_index}")
        lines.extend(
            [
                "",
                "下一步:",
                f"  cd {path}",
                *(
                    [
                        "  打开 runs/quick/report.html 查看报告",
                        "  pcl ui --runs runs --policy examples/guard.policy.yaml",
                    ]
                    if quick_run is not None
                    else [
                        "  pcl start --guide --language zh",
                        "  pcl analyze --config promptcontrol.example.yaml --out runs/quick",
                        "  pcl ui --runs runs --policy examples/guard.policy.yaml",
                    ]
                ),
                "",
                "打开该目录里的 README.zh.md, 可以查看中文文件说明和可复制命令。",
            ]
        )
        return "\n".join(lines)

    lines = [
        f"Created PromptControlLab example at {path}",
    ]
    if quick_run is not None:
        lines.extend(
            [
                f"Generated quick report: {quick_run / 'report.html'}",
                f"Generated gate result: {quick_run / 'gate_result.json'}",
                *_format_quick_run_summary(quick_run, language=language),
            ]
        )
    if history_index is not None:
        lines.append(f"Generated history index: {history_index}")
    lines.extend(
        [
            "",
            "Next steps:",
            f"  cd {path}",
            *(
                [
                    "  Open runs/quick/report.html in your browser",
                    "  pcl ui --runs runs --policy examples/guard.policy.yaml",
                ]
                if quick_run is not None
                else [
                    "  pcl start --guide",
                    "  pcl analyze --config promptcontrol.example.yaml --out runs/quick",
                    "  pcl ui --runs runs --policy examples/guard.policy.yaml",
                ]
            ),
            "",
            "Open README.md in that folder for the file map and copy-paste paths. "
            "Chinese guide: README.zh.md.",
        ]
    )
    return "\n".join(lines)


def _open_html_report(path: Path, *, language: str = "en") -> None:
    """Open a generated HTML report in the user's default browser."""

    report_path = path.resolve()
    if not report_path.exists():
        raise ValueError(f"Report does not exist: {report_path}")
    opened = webbrowser.open(report_path.as_uri())
    if language == "zh":
        if opened:
            print(f"已在浏览器中打开报告: {report_path}")
        else:
            print(f"无法自动打开浏览器, 请手动打开: {report_path}")
    elif opened:
        print(f"Opened report in your browser: {report_path}")
    else:
        print(f"Could not open a browser automatically. Open manually: {report_path}")


def _format_quick_run_summary(quick_run: Path, *, language: str = "en") -> list[str]:
    """Return a compact terminal summary for a generated quick run."""

    gate = _read_json_if_exists(quick_run / "gate_result.json")
    metrics = _read_json_if_exists(quick_run / "candidate" / "metrics.json")
    stats = _read_json_if_exists(quick_run / "stats.json")
    comparison = _first_stats_comparison(stats)
    gate_status = str(gate.get("status") or "unknown")
    score = _format_optional_number(metrics.get("mean_score"))
    delta = _format_optional_number(comparison.get("mean_delta"), signed=True)
    if language == "zh":
        return [
            "Demo 结果摘要:",
            f"- Gate: {gate_status}",
            f"- Candidate score: {score}",
            f"- Mean delta: {delta}",
        ]
    return [
        "Demo result summary:",
        f"- Gate: {gate_status}",
        f"- Candidate score: {score}",
        f"- Mean delta: {delta}",
    ]


def _read_json_if_exists(path: Path) -> JsonDict:
    if not path.exists():
        return {}
    return read_json(path)


def _first_stats_comparison(stats: JsonDict) -> JsonDict:
    comparisons = stats.get("comparisons")
    if isinstance(comparisons, list) and comparisons and isinstance(comparisons[0], dict):
        return comparisons[0]
    return stats if isinstance(stats, dict) else {}


def _format_optional_number(value: object, *, signed: bool = False) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, int | float):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return value
    else:
        return str(value)
    if signed:
        return f"{number:+.3f}"
    return f"{number:.3f}"


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
        asset_id=args.asset_id,
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


def _cmd_ingest_deepeval(args: argparse.Namespace) -> None:
    payload = ingest_deepeval_results(
        source_path=args.input,
        out_dir=args.out,
        score_name=args.score_name,
        model=args.model,
        provider=args.provider,
        method=args.method,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_ingest_prompt_optimizer(args: argparse.Namespace) -> None:
    payload = ingest_prompt_optimizer_assets(
        source_path=args.input,
        out_dir=args.out,
        asset_id=args.asset_id,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_scaffold_check(args: argparse.Namespace) -> None:
    scaffold_dir = args.scaffold if args.scaffold is not None else args.run / "eval_scaffold"
    payload = write_scaffold_check(scaffold_dir=scaffold_dir, out_path=args.out)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    if args.strict and payload.get("status") != "pass":
        msg = f"Scaffold check failed in strict mode: status={payload.get('status')}"
        raise PromptControlLabError(msg)


def _cmd_evidence_from(args: argparse.Namespace) -> None:
    payload = build_external_evidence(
        tool=args.tool,
        baseline_input=args.baseline_input,
        candidate_input=args.candidate_input,
        out_dir=args.out,
        score_name=args.score_name,
        provider=args.provider,
        baseline_provider=args.baseline_provider,
        candidate_provider=args.candidate_provider,
        model=args.model,
        baseline_model=args.baseline_model,
        candidate_model=args.candidate_model,
        baseline_prompt_id=args.baseline_prompt_id,
        candidate_prompt_id=args.candidate_prompt_id,
        baseline_name=args.baseline_name,
        candidate_name=args.candidate_name,
        baseline_experiment=args.baseline_experiment,
        candidate_experiment=args.candidate_experiment,
        split_hash=args.split_hash,
        baseline_method=args.baseline_method,
        candidate_method=args.candidate_method,
        title=args.title,
        seed=args.seed,
        bootstrap_samples=args.bootstrap_samples,
        permutation_samples=args.permutation_samples,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_evidence_audit(args: argparse.Namespace) -> None:
    payload = build_external_evidence_audit(
        tool=args.tool,
        baseline_input=args.baseline_input,
        candidate_input=args.candidate_input,
        out_dir=args.out,
        score_name=args.score_name,
        provider=args.provider,
        baseline_provider=args.baseline_provider,
        candidate_provider=args.candidate_provider,
        model=args.model,
        baseline_model=args.baseline_model,
        candidate_model=args.candidate_model,
        baseline_prompt_id=args.baseline_prompt_id,
        candidate_prompt_id=args.candidate_prompt_id,
        baseline_name=args.baseline_name,
        candidate_name=args.candidate_name,
        baseline_experiment=args.baseline_experiment,
        candidate_experiment=args.candidate_experiment,
        split_hash=args.split_hash,
        baseline_method=args.baseline_method,
        candidate_method=args.candidate_method,
        title=args.title,
        seed=args.seed,
        bootstrap_samples=args.bootstrap_samples,
        permutation_samples=args.permutation_samples,
    )
    gate_payload = run_evidence_gate(run_dir=args.out)
    payload = attach_evidence_gate_to_audit(out_dir=args.out, gate_payload=gate_payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_source_verify(args: argparse.Namespace) -> None:
    payload = verify_source_inputs(run_dir=args.run, out_path=args.out)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    if args.strict and payload.get("status") != "pass":
        msg = (
            "Source input verification failed in strict mode: "
            f"status={payload.get('status')}, "
            f"mismatches={payload.get('mismatch_count')}, "
            f"missing={payload.get('missing_count')}, "
            f"unchecked={payload.get('unchecked_count')}"
        )
        raise PromptControlLabError(msg)


def _cmd_evidence_gate(args: argparse.Namespace) -> None:
    payload = run_evidence_gate(
        run_dir=args.run,
        out_path=args.out,
        require_source=args.require_source,
        allow_missing_bundle=args.allow_missing_bundle,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    if args.strict and payload.get("status") != "pass":
        msg = f"Evidence gate failed in strict mode: status={payload.get('status')}"
        raise PromptControlLabError(msg)


def _cmd_ecosystem_demo(args: argparse.Namespace) -> None:
    payload = run_ecosystem_demo(
        examples_dir=args.examples,
        out_dir=args.out,
        split_hash=args.split_hash,
        provider=args.provider,
        model=args.model,
        bootstrap_samples=args.bootstrap_samples,
        permutation_samples=args.permutation_samples,
    )
    if args.summary:
        print(_format_ecosystem_demo_summary(payload))
        return
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_ecosystem_scorecard(args: argparse.Namespace) -> None:
    payload = write_ecosystem_scorecard(run_dir=args.run, out_path=args.out)
    if args.summary:
        print(_format_ecosystem_scorecard_summary(payload))
        return
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _format_ecosystem_scorecard_summary(payload: JsonDict) -> str:
    lines = [
        "Ecosystem scorecard summary",
        f"HTML: {payload.get('html_path', '')}",
        f"Markdown: {payload.get('markdown_path', '')}",
        "",
    ]
    lines.extend(_market_readiness_summary_lines(payload))
    return "\n".join(lines)


def _format_ecosystem_demo_summary(payload: JsonDict) -> str:
    runs = payload.get("runs")
    run_count = len(runs) if isinstance(runs, list) else 0
    scorecard_path = Path(str(payload.get("ecosystem_scorecard_path") or ""))
    scorecard_payload = read_json(scorecard_path) if scorecard_path.exists() else {}
    lines = [
        "Ecosystem demo summary",
        f"Run: {payload.get('out_dir', '')}",
        f"Tool bundles: {run_count}",
        f"Scorecard: {payload.get('ecosystem_scorecard_html_path', '')}",
        f"Research bundle: {payload.get('research_bundle_html_path', '')}",
        "",
    ]
    if scorecard_payload:
        lines.extend(_market_readiness_summary_lines(scorecard_payload))
    else:
        lines.append("Market readiness: not available")
    lines.extend(
        [
            "",
            "Next: open ecosystem_scorecard.html first, or run the local UI Research Overview.",
        ]
    )
    return "\n".join(lines)


def _market_readiness_summary_lines(payload: JsonDict) -> list[str]:
    readiness = payload.get("market_readiness")
    readiness_dict = readiness if isinstance(readiness, dict) else {}
    next_moves = readiness_dict.get("next_moves")
    lines = [
        "Market readiness",
        f"Status: {readiness_dict.get('status', 'unknown')}",
    ]
    positioning = str(readiness_dict.get("recommended_positioning") or "")
    if positioning:
        lines.append(f"Positioning: {positioning}")
    first_users = _summary_string_items(readiness_dict.get("best_first_users"))
    if first_users:
        lines.extend(["", "Best first users:", *[f"- {item}" for item in first_users]])
    do_not_build = _summary_string_items(readiness_dict.get("do_not_build"))
    if do_not_build:
        lines.extend(["", "Do not build:", *[f"- {item}" for item in do_not_build]])
    lines.extend(["", "Next moves:"])
    if isinstance(next_moves, list) and next_moves:
        for item in next_moves:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- "
                f"{item.get('priority', '')} {item.get('tool', '')}: "
                f"{item.get('move', '')}"
            )
    else:
        lines.append("- No next moves recorded.")
    lines.extend(
        [
            "",
            "Boundary: positioning guidance only; imported rows remain the evidence.",
        ]
    )
    return lines


def _summary_string_items(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _cmd_choose(args: argparse.Namespace) -> None:
    """Print adjacent-tool guidance for a user need."""

    if args.need is None:
        payload = {
            "choices": tool_choice_lanes(),
            "market_gap_actions": market_gap_action_rows(language=args.language),
            "adoption_path": adoption_path_rows(language=args.language),
            "next": "Run pcl choose --need <your-goal>.",
        }
    else:
        payload = choose_tool_for_need(args.need)
    written: tuple[Path, Path] | None = None
    if args.out is not None:
        json_path = _choice_output_path(args.out)
        md_path = json_path.with_suffix(".md")
        write_json(json_path, payload)
        md_path.write_text(
            render_tool_choice_markdown(payload, language=args.language),
            encoding="utf-8",
        )
        written = (json_path, md_path)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return
    print(format_tool_choice(payload, language=args.language))
    if written is not None:
        print(f"\nWrote tool-choice artifacts: {written[0]} and {written[1]}")


def _choice_output_path(path: Path) -> Path:
    """Resolve ``pcl choose --out`` to a JSON artifact path."""

    if path.suffix.lower() == ".json":
        return path
    if path.suffix:
        return path.with_suffix(".json")
    return path / "tool_choice.json"


def _cmd_start(args: argparse.Namespace) -> None:
    if args.guide:
        print(_format_start_guide(args.language))
        return

    choice = _start_choice(args.choice, language=args.language)
    if choice == "demo":
        out_dir = args.out or Path("demo")
        write_example_project(out_dir)
        quick_run = out_dir / "runs" / "quick"
        run_quick_analysis(
            data_path=out_dir / "examples" / "tasks.jsonl",
            baseline_predictions_path=out_dir / "examples" / "predictions_baseline.jsonl",
            candidate_predictions_path=out_dir / "examples" / "predictions_candidate.jsonl",
            out_dir=quick_run,
            metric="exact_match",
            train_ratio=0.5,
            val_ratio=0.25,
            seed=args.seed,
            bootstrap_samples=50,
            permutation_samples=50,
            explain_level="plain",
            title="PromptControlLab Demo Analysis",
            policy_path=out_dir / "examples" / "gate.policy.yaml",
            prompt_id="demo-prompt",
            prompt_file=out_dir / "prompts" / "current.txt",
            prompt_version="v1",
        )
        history_index = out_dir / "runs" / "history_index.json"
        index_history(runs_dir=out_dir / "runs", out_path=history_index)
        if args.language == "zh":
            print("新手模式: 创建可运行 demo 项目并生成 quick report")
        else:
            print("Beginner mode: create a runnable demo project and quick report")
        print(
            _format_init_output(
                out_dir,
                language=args.language,
                quick_run=quick_run,
                history_index=history_index,
            )
        )
        if args.open_report:
            _open_html_report(quick_run / "report.html", language=args.language)
        return

    if choice == "research":
        out_dir = args.out or Path("runs") / "research-demo"
        payload = write_research_demo(out_dir=out_dir, seed=args.seed)
        if args.language == "zh":
            print("新手模式: 运行论文风格的 prompt optimization 诊断 demo")
        else:
            print("Beginner mode: run the paper-style research diagnostics demo")
        print(
            _format_research_demo_output(
                out_dir=out_dir,
                payload=payload,
                language=args.language,
            )
        )
        return

    if choice == "choose":
        if args.language == "zh":
            print("新手模式: 选择先用哪个相邻工具")
        else:
            print("Beginner mode: choose the right adjacent tool")
        _cmd_choose(
            argparse.Namespace(
                need=args.need,
                language=args.language,
                json=False,
                out=args.out,
            )
        )
        return

    if choice == "ecosystem":
        out_dir = args.out or Path("runs") / "ecosystem-demo"
        payload = _run_start_ecosystem(args, out_dir=out_dir)
        if args.language == "zh":
            print("新手模式: 对比相邻生态工具")
        else:
            print("Beginner mode: compare adjacent ecosystem tools")
        print(
            _format_start_ecosystem_result(
                out_dir=out_dir,
                payload=payload,
                language=args.language,
            )
        )
        return

    if choice == "import":
        if args.input is None:
            print(_format_start_import_guide(args.language))
            return
        out_dir = args.out or _default_start_import_out_dir(args.tool)
        payload = _run_start_import(args, out_dir=out_dir)
        payload.setdefault("source_tool", args.tool)
        print(_format_start_import_result(out_dir=out_dir, payload=payload, language=args.language))
        return

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


def _cmd_quickstart(args: argparse.Namespace) -> None:
    """Create the beginner demo through a shorter public command."""

    _cmd_start(
        argparse.Namespace(
            guide=False,
            choice="demo",
            language=args.language,
            out=args.out,
            seed=args.seed,
            open_report=args.open_report,
        )
    )


def _default_start_import_out_dir(tool: str) -> Path:
    name = "external" if tool == "auto" else tool
    return Path("runs") / f"from-{name}"


def _run_start_import(args: argparse.Namespace, *, out_dir: Path) -> JsonDict:
    if args.input is None:
        raise ValueError("--input is required when start import executes an import.")
    source_path: Path = args.input
    if args.tool == "auto":
        return ingest_auto_results(
            source_path=source_path,
            out_dir=out_dir,
            prompt_id=args.prompt_id,
            name=args.name,
            experiment=args.experiment,
            score_name=args.score_name,
            model=args.model,
            provider=args.provider,
            method=args.method,
            asset_id=args.asset_id,
        )
    if args.tool == "promptfoo":
        return ingest_promptfoo_results(
            source_path=source_path,
            out_dir=out_dir,
            prompt_id=args.prompt_id,
            provider=args.provider,
            method=args.method,
        )
    if args.tool == "langfuse":
        return ingest_langfuse_results(
            source_path=source_path,
            out_dir=out_dir,
            name=args.name,
            score_name=args.score_name,
            model=args.model,
            provider=args.provider,
            method=args.method,
        )
    if args.tool == "langsmith":
        return ingest_langsmith_results(
            source_path=source_path,
            out_dir=out_dir,
            experiment=args.experiment,
            score_name=args.score_name,
            model=args.model,
            provider=args.provider,
            method=args.method,
        )
    if args.tool == "deepeval":
        return ingest_deepeval_results(
            source_path=source_path,
            out_dir=out_dir,
            score_name=args.score_name,
            model=args.model,
            provider=args.provider,
            method=args.method,
        )
    return ingest_prompt_optimizer_assets(
        source_path=source_path,
        out_dir=out_dir,
        asset_id=args.asset_id,
    )


def _run_start_ecosystem(args: argparse.Namespace, *, out_dir: Path) -> JsonDict:
    examples_dir = Path("examples") / "external"
    if examples_dir.exists():
        return _run_ecosystem_demo_with_examples(args, examples_dir=examples_dir, out_dir=out_dir)
    bundled_examples = out_dir.parent / f"{out_dir.name}_source_examples"
    write_external_examples(bundled_examples)
    return _run_ecosystem_demo_with_examples(
        args,
        examples_dir=bundled_examples,
        out_dir=out_dir,
    )


def _run_ecosystem_demo_with_examples(
    args: argparse.Namespace,
    *,
    examples_dir: Path,
    out_dir: Path,
) -> JsonDict:
    return run_ecosystem_demo(
        examples_dir=examples_dir,
        out_dir=out_dir,
        split_hash="external-demo-split",
        provider=args.provider or "openai",
        model=args.model or "gpt-4o-mini-20260601",
        bootstrap_samples=50,
        permutation_samples=50,
    )


def _format_start_ecosystem_result(
    *,
    out_dir: Path,
    payload: JsonDict,
    language: str = "en",
) -> str:
    runs = payload.get("runs")
    run_count = len(runs) if isinstance(runs, list) else 0
    scorecard = payload.get("ecosystem_scorecard_html_path") or str(
        out_dir / "ecosystem_scorecard.html"
    )
    bundle = out_dir / "research_bundle.html"
    if language == "zh":
        return "\n".join(
            [
                f"已生成生态对比 demo: {out_dir}",
                f"- 工具证据包数量: {run_count}",
                f"- 先打开: {scorecard}",
                (
                    "- 先看 Market readiness: 它会告诉你 PCL 应该优先切入哪里, "
                    "学习什么, 暂时不要做什么。"
                ),
                f"- 研究证据包: {bundle}",
                "- 下一步: 再看扩展市场地图和每个外部工具强项, 确认 PCL 补充的证据层。",
            ]
        )
    return "\n".join(
        [
            f"Generated ecosystem comparison demo: {out_dir}",
            f"- Tool bundles: {run_count}",
            f"- Open first: {scorecard}",
            (
                "- Start with Market readiness: it shows where PCL should lead, "
                "learn, and avoid overbuilding."
            ),
            f"- Research bundle: {bundle}",
            (
                "- Next: review the extended market map and each external tool's strength "
                "against PCL-added evidence."
            ),
        ]
    )


def _format_start_import_guide(language: str = "en") -> str:
    if language == "zh":
        return "\n".join(
            [
                "新手模式: 把外部评测结果导入成证据",
                "",
                "如果你已经有 Promptfoo / Langfuse / LangSmith / DeepEval 导出文件, 运行:",
                (
                    "  pcl start --choice import --tool auto --input results.json "
                    "--out runs/from-external"
                ),
                "",
                "如果是 prompt-optimizer 收藏或模板导出, 运行:",
                (
                    "  pcl start --choice import --tool prompt-optimizer "
                    "--input favorites.json --out runs/from-prompt-optimizer"
                ),
                "",
                "得到什么: PCL run artifact、manifest、metrics 或 prompt asset gap plan。",
                (
                    "下一步: 运行 `pcl scaffold-check --run <run>`、"
                    "`pcl evidence-card --run <run>` 或 `pcl evidence-audit`。"
                ),
            ]
        )
    return "\n".join(
        [
            "Beginner mode: import external eval results as evidence",
            "",
            "If you already have Promptfoo / Langfuse / LangSmith / DeepEval exports, run:",
            "  pcl start --choice import --tool auto --input results.json --out runs/from-external",
            "",
            "For prompt-optimizer favorites or template exports, run:",
            (
                "  pcl start --choice import --tool prompt-optimizer "
                "--input favorites.json --out runs/from-prompt-optimizer"
            ),
            "",
            "Result: PCL run artifacts, manifest, metrics, or a prompt asset gap plan.",
            (
                "Next: run `pcl scaffold-check --run <run>`, "
                "`pcl evidence-card --run <run>`, or `pcl evidence-audit`."
            ),
        ]
    )


def _format_start_import_result(
    *,
    out_dir: Path,
    payload: JsonDict,
    language: str = "en",
) -> str:
    source_tool = payload.get("source_tool") or payload.get("tool") or "external"
    status = payload.get("evaluation_status") or payload.get("status") or "imported"
    count = payload.get("count")
    count_text = "unknown" if count is None else str(count)
    if language == "zh":
        return "\n".join(
            [
                "新手模式: 把外部评测结果导入成证据",
                f"- 来源工具: {source_tool}",
                f"- 输出目录: {out_dir}",
                f"- 记录数量: {count_text}",
                f"- 状态: {status}",
                "",
                "下一步:",
                f"  pcl scaffold-check --run {out_dir}",
                f"  pcl evidence-card --run {out_dir} --out {out_dir / 'evidence_card.md'}",
            ]
        )
    return "\n".join(
        [
            "Beginner mode: import external eval results as evidence",
            f"- Source tool: {source_tool}",
            f"- Output directory: {out_dir}",
            f"- Records: {count_text}",
            f"- Status: {status}",
            "",
            "Next steps:",
            f"  pcl scaffold-check --run {out_dir}",
            f"  pcl evidence-card --run {out_dir} --out {out_dir / 'evidence_card.md'}",
        ]
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
        evidence_gate_path=args.evidence_gate,
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
    print(_format_research_demo_output(out_dir=args.out, payload=payload, language=args.language))


def _cmd_research_quickstart(args: argparse.Namespace) -> None:
    write_research_demo(out_dir=args.out, seed=args.seed)
    payload = run_research_diagnostics(
        run_dir=args.out,
        mode="diagnose",
        summary_dir=args.out,
    )
    if args.language == "zh":
        print("研究 quickstart: 已生成论文诊断 demo 并刷新 diagnose 证据包")
    else:
        print("Research quickstart: generated the paper demo and refreshed diagnose evidence")
    print(_format_research_demo_output(out_dir=args.out, payload=payload, language=args.language))
    if args.open_report:
        report_name = "research_bundle.zh.html" if args.language == "zh" else "research_bundle.html"
        _open_html_report(args.out / report_name, language=args.language)


def _format_research_demo_output(
    *,
    out_dir: Path,
    payload: JsonDict,
    language: str = "en",
) -> str:
    diagnostics = payload.get("diagnostics", {})
    diagnostic_names = sorted(diagnostics) if isinstance(diagnostics, dict) else []
    readable_diagnostics = _readable_research_diagnostic_names(
        diagnostic_names,
        language=language,
    )
    if language == "zh":
        lines = [
            f"已写出研究 demo: {out_dir}",
            "做了什么: 生成一个用于论文诊断的小型 synthetic 证据包"
            f"({readable_diagnostics})。",
            f"诊断项: {', '.join(diagnostic_names)}",
            *_research_cli_summary_lines(
                summary_dir=out_dir,
                payload=payload,
                language=language,
            ),
            *_research_output_guide_lines(out_dir, language=language),
            f"UI: pcl ui --runs {out_dir} --language zh",
        ]
        return "\n".join(lines)
    lines = [
        f"Wrote research demo to {out_dir}",
        "What it did: generated a small synthetic evidence bundle for the paper "
        f"diagnostics ({readable_diagnostics}).",
        f"Diagnostics: {', '.join(diagnostic_names)}",
        *_research_cli_summary_lines(summary_dir=out_dir, payload=payload, language=language),
        *_research_output_guide_lines(out_dir, language=language),
        f"UI: pcl ui --runs {out_dir}",
    ]
    return "\n".join(lines)


def _readable_research_diagnostic_names(names: list[str], *, language: str = "en") -> str:
    labels = _research_diagnostic_labels(language=language)
    readable = [labels.get(name, name.replace("_", "-")) for name in names]
    return ", ".join(readable) if readable else "none"


def _research_diagnostic_labels(*, language: str = "en") -> dict[str, str]:
    if language == "zh":
        return {
            "soft_hard": "soft-hard gap (soft prompt 转 hard prompt 的差距)",
            "trajectory": "hidden-state trajectory (隐藏状态轨迹)",
            "riccati": "Riccati surrogate (降维控制论替代模型)",
            "tv_soft": "time-varying soft-control (时变 soft prompt 控制)",
        }
    return {
        "soft_hard": "soft-hard gap",
        "trajectory": "hidden-state trajectory",
        "riccati": "Riccati surrogate",
        "tv_soft": "time-varying soft-control",
    }


def _research_output_guide_lines(out_dir: Path, *, language: str = "en") -> list[str]:
    if language == "zh":
        return [
            "",
            "如何阅读输出:",
            f"研究诊断报告: {out_dir / 'research_diagnostics.html'}",
            "  用直白语言解释每个论文诊断。",
            f"证据卡片: {out_dir / 'evidence_card.html'}",
            "  总结当前 prompt optimization 主张有哪些证据支持。",
            f"主张检查: {out_dir / 'claim_check.html'}",
            "  说明当前证据最多能安全支持什么主张。",
            f"证据门禁: {out_dir / 'evidence_gate_result.html'}",
            "  检查论文证据 artifact 是否齐全、是否链接完整。",
        ]
    return [
        "",
        "How to read the outputs:",
        f"Research diagnostics: {out_dir / 'research_diagnostics.html'}",
        "  Explains each paper-derived diagnostic in plain language.",
        f"Evidence card: {out_dir / 'evidence_card.html'}",
        "  Summarizes what evidence exists for a prompt-optimization claim.",
        f"Claim check: {out_dir / 'claim_check.html'}",
        "  Shows the strongest claim this run can safely support.",
        f"Evidence gate: {out_dir / 'evidence_gate_result.html'}",
        "  Checks whether required research artifacts are present and linked.",
    ]


def _research_cli_summary_lines(
    *,
    summary_dir: Path,
    payload: JsonDict,
    language: str = "en",
) -> list[str]:
    at_a_glance = payload.get("at_a_glance")
    summary = at_a_glance if isinstance(at_a_glance, dict) else {}
    diagnostics_ready = summary.get("diagnostics_ready", "unknown")
    claim_status = summary.get("claim_status", "unknown")
    evidence_tier = summary.get("evidence_tier", "unknown")
    readable_tier = _readable_evidence_tier(str(evidence_tier), language=language)
    next_action = summary.get("next_action")
    open_first = summary.get("open_first")
    if language == "zh":
        lines = [
            (
                "概览: "
                f"诊断={diagnostics_ready}; 主张检查={claim_status}; "
                f"证据层级={readable_tier}"
            ),
        ]
        if isinstance(open_first, str) and open_first:
            open_path = (
                "research_bundle.zh.html"
                if open_first == "research_bundle.html"
                else open_first
            )
            lines.append(f"先打开: {summary_dir / open_path}")
        if isinstance(next_action, str) and next_action:
            lines.append(f"下一步: {_translate_research_next_action(next_action)}")
        return lines
    lines = [
        (
            "At a glance: "
            f"diagnostics={diagnostics_ready}; claim={claim_status}; "
            f"evidence tier={readable_tier}"
        ),
    ]
    if isinstance(open_first, str) and open_first:
        lines.append(f"Open first: {summary_dir / open_first}")
    if isinstance(next_action, str) and next_action:
        lines.append(f"Next action: {next_action}")
    return lines


def _readable_evidence_tier(value: str, *, language: str = "en") -> str:
    if language == "zh":
        labels = {
            "tier_1_paired": "仅成对比较",
            "tier_2_partial_research": "部分研究诊断",
            "tier_3_research_ready": "研究证据基本齐备",
            "tier_4_full_research_diagnostics": "完整研究诊断",
        }
        return labels.get(value, value.replace("_", " "))
    labels = {
        "tier_1_paired": "paired comparison only",
        "tier_2_partial_research": "partial research diagnostics",
        "tier_3_research_ready": "research-ready evidence",
        "tier_4_full_research_diagnostics": "full research diagnostics",
    }
    return labels.get(value, value.replace("_", " "))


def _translate_research_next_action(value: str) -> str:
    if value == "Share the research bundle, evidence card, and claim check together.":
        return "把 research_bundle、evidence_card 和 claim_check 一起分享给审阅者。"
    return value


def _cmd_research_bundle(args: argparse.Namespace) -> None:
    if args.strict and not args.verify:
        msg = "research-bundle --strict must be used together with --verify"
        raise PromptControlLabError(msg)
    if args.verify:
        payload = verify_research_bundle_index(args.run)
    else:
        payload = write_research_bundle_index(args.run)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    if args.strict and payload.get("status") != "pass":
        msg = (
            "Research bundle verification failed in strict mode: "
            f"status={payload.get('status')}, "
            f"mismatches={payload.get('mismatch_count')}, "
            f"missing={payload.get('missing_count')}, "
            f"unchecked={payload.get('unchecked_count')}"
        )
        raise PromptControlLabError(msg)


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
    summary_dir_path = Path(str(payload["summary_dir"]))
    if args.language == "zh":
        print(f"已写出研究诊断: {payload['diagnostics_dir']}")
        print(f"报告: {summary_dir_path / 'research_diagnostics.html'}")
    else:
        print(f"Wrote research diagnostics to {payload['diagnostics_dir']}")
        print(f"Report: {summary_dir_path / 'research_diagnostics.html'}")
    print(
        "\n".join(
            _research_cli_summary_lines(
                summary_dir=summary_dir_path,
                payload=payload,
                language=args.language,
            )
        )
    )
    print("\n".join(_research_output_guide_lines(summary_dir_path, language=args.language)))


def _cmd_gap_status(args: argparse.Namespace) -> None:
    payload = write_research_gap_status(run_dir=args.run, out_path=args.out)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_extract_hidden(args: argparse.Namespace) -> None:
    payload = extract_hidden_states(
        model_id=args.model,
        prompts_path=args.prompts,
        out_path=args.out,
        layer=args.layer,
        pool=args.pool,
        max_items=args.max_items,
        max_length=args.max_length,
        device=args.device,
        trust_remote_code=args.trust_remote_code,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


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


def _cmd_evidence_card(args: argparse.Namespace) -> None:
    payload = write_evidence_card(args.run, markdown_path=args.out, json_path=args.json_out)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_claim_check(args: argparse.Namespace) -> None:
    payload = run_claim_check(args.run, claim=args.claim, out_path=args.out)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


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


def _start_choice(value: str | None, *, language: str = "en") -> str:
    if value is not None:
        return value
    if language == "zh":
        print(
            "\n".join(
                [
                    "你想先做什么?",
                    "1) 创建一个可直接运行的 demo 项目",
                    "2) 运行论文风格的 prompt optimization 研究 demo",
                    "3) 把外部评测结果导入成证据",
                    "4) 让我的 prompt 更清楚",
                    "5) 在发送给 AI 工具前检查 prompt",
                    "6) 比较 prompts 并生成报告",
                    "7) 生成生态对比 demo",
                    "8) 选择应该先用哪个相邻工具",
                    "",
                    "提示: 如果不确定路径, 运行 `pcl start --guide --language zh`。",
                ]
            )
        )
        raw = input("请选择 1、2、3、4、5、6、7 或 8: ").strip().lower()
    else:
        print(
            "\n".join(
                [
                    "What do you want to do?",
                    "1) Create a runnable demo project",
                    "2) Run a paper-style prompt optimization research demo",
                    "3) Import external eval results as evidence",
                    "4) Make my prompt clearer",
                    "5) Check a prompt before sending it to an AI tool",
                    "6) Compare prompts and create a report",
                    "7) Generate an ecosystem comparison demo",
                    "8) Choose which adjacent tool to use first",
                    "",
                    "Tip: run `pcl start --guide` if you are unsure which path fits your goal.",
                ]
            )
        )
        raw = input("Choose 1, 2, 3, 4, 5, 6, 7, or 8: ").strip().lower()
    choices = {
        "1": "demo",
        "demo": "demo",
        "2": "research",
        "research": "research",
        "3": "import",
        "import": "import",
        "evidence": "import",
        "4": "improve",
        "improve": "improve",
        "5": "guard",
        "guard": "guard",
        "6": "analyze",
        "analyze": "analyze",
        "7": "ecosystem",
        "ecosystem": "ecosystem",
        "ecosystem-demo": "ecosystem",
        "8": "choose",
        "choose": "choose",
        "tool-choice": "choose",
    }
    if raw not in choices:
        msg = (
            "请选择 1、2、3、4、5、6、7 或 8"
            if language == "zh"
            else "Choose 1, 2, 3, 4, 5, 6, 7, or 8"
        )
        raise ValueError(msg)
    return choices[raw]


def _format_start_guide(language: str = "en") -> str:
    """Return a compact beginner guide for choosing the right first command."""

    if language == "zh":
        rows = [
            (
                "先看产品长什么样",
                "pcl quickstart --language zh --out demo --open-report "
                "(同: pcl start --choice demo --language zh --out demo)",
                "生成 demo 并打开 `runs/quick/report.html`。",
            ),
            (
                "运行论文里的 prompt optimization 诊断",
                "pcl research-quickstart --out runs/research-demo --language zh --open-report",
                "打开 research_bundle.zh.html 查看论文证据包。",
            ),
            (
                "不知道应该先用哪个工具",
                'pcl choose --need "安全评测和红队检查" --language zh',
                "Promptfoo / DeepEval / LangSmith / Langfuse / prompt-optimizer / PCL 的选择建议。",
            ),
            (
                "对比相邻工具和 PCL 补充证据",
                "pcl start --choice ecosystem --out runs/ecosystem-demo",
                "打开 `ecosystem_scorecard.html`, 先看 Market readiness。",
            ),
            (
                "把外部评测结果导入成证据",
                "pcl start --choice import --tool auto --input results.json "
                "--out runs/from-external",
                "`manifest.json` 和 `bridge_summary.html`。",
            ),
            (
                "在 coding agent 执行前守护 prompt",
                "pcl guard --prompt \"修复这个 bug\" "
                "--profile coding --policy examples/guard.policy.yaml",
                "复制改写后的 prompt。",
            ),
            (
                "审计 agent 到底改了什么",
                "pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit",
                "生成审计 artifact, 之后可做 PR summary。",
            ),
        ]
        lines = ["PromptControlLab 新手路径指南", "", "复制最符合你目标的一条命令:", ""]
        start_label = "起点"
        result_label = "得到"
        final_lines = [
            "更多选择逻辑: docs/choice_guide.zh.md",
            (
                "相邻工具地图: Promptfoo -> eval / CI / red-team; "
                "DeepEval -> Pytest-style LLM tests; prompt-optimizer -> prompt 写作。"
            ),
            "如果想用交互菜单: pcl start --language zh",
        ]
    else:
        rows = [
            (
                "See the product first",
                "pcl quickstart --out demo --open-report "
                "(same as: pcl start --choice demo --out demo)",
                "A demo run and `runs/quick/report.html`.",
            ),
            (
                "Run the paper-derived prompt optimization diagnostics",
                "pcl research-quickstart --out runs/research-demo --open-report",
                "research_bundle.html as the paper evidence bundle.",
            ),
            (
                "Choose the right adjacent tool",
                'pcl choose --need "security evals and red-team checks"',
                (
                    "A direct recommendation for Promptfoo, DeepEval, "
                    "LangSmith/Langfuse, prompt-optimizer, or PCL."
                ),
            ),
            (
                "Compare adjacent tools and PCL-added evidence",
                "pcl start --choice ecosystem --out runs/ecosystem-demo",
                "ecosystem_scorecard.html with Market readiness.",
            ),
            (
                "Import external eval results as evidence",
                "pcl start --choice import --tool auto --input results.json "
                "--out runs/from-external",
                "`manifest.json` and `bridge_summary.html`.",
            ),
            (
                "Guard a coding-agent prompt before it runs",
                "pcl guard --prompt \"Fix this bug\" "
                "--profile coding --policy examples/guard.policy.yaml",
                "An improved prompt and guard result.",
            ),
            (
                "Audit what an agent changed",
                "pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit",
                "Diff audit artifacts; optionally build a PR summary.",
            ),
        ]
        lines = [
            "PromptControlLab beginner guide",
            "",
            "Copy the one command that matches your goal:",
            "",
        ]
        start_label = "Start"
        result_label = "You get"
        final_lines = [
            "More choice logic: docs/choice_guide.en.md",
            (
                "Adjacent-tool map: Promptfoo -> eval / CI / red-team; "
                "DeepEval -> Pytest-style LLM tests; prompt-optimizer -> prompt writing."
            ),
            "Interactive menu: pcl start",
        ]
    for index, (goal, command, next_step) in enumerate(rows, start=1):
        lines.extend(
            [
                f"{index}. {goal}",
                f"   {start_label}: {command}",
                f"   {result_label}: {next_step}",
                "",
            ]
        )
    lines.extend(final_lines)
    return "\n".join(lines)


def _read_start_prompt(prompt: str | None, prompt_file: Path | None) -> str:
    if prompt is not None or prompt_file is not None:
        return _read_improve_prompt(prompt, prompt_file)
    return input("Paste your prompt: ")
