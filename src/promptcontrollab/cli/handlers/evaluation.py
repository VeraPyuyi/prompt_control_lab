"""Evaluation command handlers and terminal formatters."""

from __future__ import annotations

import argparse
import json

from promptcontrollab.cli.common import (
    _config_path,
    _path_arg,
)
from promptcontrollab.core.config import (
    get_config_bool,
    get_config_float,
    get_config_int,
    get_config_path,
    get_config_str,
    load_project_config,
)
from promptcontrollab.evaluation.artifact_export import export_report_zip
from promptcontrollab.evaluation.change_review import review_changes
from promptcontrollab.evaluation.evaluation import run_import_eval
from promptcontrollab.evaluation.explain import generate_explanation
from promptcontrollab.evaluation.gate import run_gate
from promptcontrollab.evaluation.history import compare_history, index_history
from promptcontrollab.evaluation.reporting import generate_report
from promptcontrollab.evaluation.run_comparison import compare_runs
from promptcontrollab.evaluation.splitting import load_tasks, make_split, write_split
from promptcontrollab.evaluation.statistics import compare_prediction_files
from promptcontrollab.evaluation.validity import run_comparison_validity
from promptcontrollab.evaluation.workflow import (
    config_metric,
    load_analyze_config,
    resolve_analyze_paths,
    run_quick_analysis,
)


def _cmd_validity(args: argparse.Namespace) -> None:
    """Execute the validity command handler."""
    payload = run_comparison_validity(
        baseline_dir=args.baseline,
        candidate_dir=args.candidate,
        out_path=args.out,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_compare_runs(args: argparse.Namespace) -> None:
    """Execute the compare runs command handler."""
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


def _cmd_review(args: argparse.Namespace) -> None:
    """Execute the unified change review command handler."""

    payload = review_changes(
        baseline_dir=args.baseline,
        candidate_dir=args.candidate,
        out_dir=args.out,
        kind=args.kind,
        mode=args.mode,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_history_index(args: argparse.Namespace) -> None:
    """Execute the history index command handler."""
    payload = index_history(runs_dir=args.runs, out_path=args.out)
    print(f"Wrote history index to {args.out} ({len(payload['runs'])} runs)")


def _cmd_history_compare(args: argparse.Namespace) -> None:
    """Execute the history compare command handler."""
    compare_history(a_dir=args.a, b_dir=args.b, out_path=args.out)
    print(f"Wrote history comparison to {args.out}")


def _cmd_export_report(args: argparse.Namespace) -> None:
    """Execute the export report command handler."""
    payload = export_report_zip(run_dir=args.run, zip_path=args.out)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _cmd_analyze(args: argparse.Namespace) -> None:
    """Execute the analyze command handler."""
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
    """Execute the split command handler."""
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
    """Execute the eval command handler."""
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
    """Execute the stats command handler."""
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
    """Execute the report command handler."""
    md_path, html_path = generate_report(args.run, title=args.title)
    print(f"Wrote reports to {md_path} and {html_path}")


def _cmd_explain(args: argparse.Namespace) -> None:
    """Execute the explain command handler."""
    generate_explanation(args.run, level=args.level)
    print(f"Wrote explanation to {args.run / 'explanation.json'}")


def _cmd_gate(args: argparse.Namespace) -> None:
    """Execute the gate command handler."""
    project_config, project_config_path = load_project_config()
    policy_path = args.policy or _config_path(project_config, project_config_path, "gate_policy")
    if policy_path is None:
        msg = "Missing required --policy argument or .promptcontrol.yaml gate_policy"
        raise ValueError(msg)
    run_gate(args.run, policy_path=policy_path)
    print(f"Wrote gate result to {args.run / 'gate_result.json'}")
