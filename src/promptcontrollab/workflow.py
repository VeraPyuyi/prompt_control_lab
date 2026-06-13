"""High-level quick-mode workflows."""

from __future__ import annotations

from pathlib import Path

from promptcontrollab.config import get_config_path, get_config_str, read_simple_yaml
from promptcontrollab.evaluation import run_import_eval
from promptcontrollab.evidence_card import write_evidence_card
from promptcontrollab.explain import generate_explanation
from promptcontrollab.files import JsonDict, ensure_dir, read_json, write_json
from promptcontrollab.gate import run_gate
from promptcontrollab.model_identity import compare_model_identities
from promptcontrollab.prompt_identity import build_prompt_identity
from promptcontrollab.reporting import generate_report
from promptcontrollab.splitting import load_tasks, make_split, write_split
from promptcontrollab.statistics import compare_prediction_files
from promptcontrollab.validity import run_comparison_validity
from promptcontrollab.version import __version__


def run_quick_analysis(
    *,
    data_path: Path,
    baseline_predictions_path: Path,
    candidate_predictions_path: Path,
    out_dir: Path,
    metric: str,
    train_ratio: float,
    val_ratio: float,
    seed: int,
    bootstrap_samples: int,
    permutation_samples: int,
    explain_level: str,
    title: str,
    policy_path: Path | None = None,
    baseline_provider: str | None = None,
    baseline_model: str | None = None,
    candidate_provider: str | None = None,
    candidate_model: str | None = None,
    api_version: str | None = None,
    verify_model: bool = False,
    prompt_id: str | None = None,
    prompt_file: Path | None = None,
    prompt_version: str | None = None,
    baseline_prompt_id: str | None = None,
    baseline_prompt_file: Path | None = None,
    baseline_prompt_version: str | None = None,
    candidate_prompt_id: str | None = None,
    candidate_prompt_file: Path | None = None,
    candidate_prompt_version: str | None = None,
) -> None:
    """Run split, import-eval, stats, explanation, optional gate, and report."""

    ensure_dir(out_dir)
    tasks = load_tasks(data_path)
    split = make_split(tasks, train_ratio=train_ratio, val_ratio=val_ratio, seed=seed)
    write_split(out_dir / "splits.json", split)
    run_import_eval(
        data_path=data_path,
        predictions_path=baseline_predictions_path,
        out_dir=out_dir / "baseline",
        metric=metric,
        method="baseline",
        provider=baseline_provider,
        model_id=baseline_model,
        api_version=api_version,
        verify_model=verify_model,
    )
    run_import_eval(
        data_path=data_path,
        predictions_path=candidate_predictions_path,
        out_dir=out_dir / "candidate",
        metric=metric,
        method="candidate",
        provider=candidate_provider,
        model_id=candidate_model,
        api_version=api_version,
        verify_model=verify_model,
    )
    compare_prediction_files(
        baseline_path=out_dir / "baseline" / "predictions.jsonl",
        candidate_path=out_dir / "candidate" / "predictions.jsonl",
        out_path=out_dir / "stats.json",
        seed=seed,
        bootstrap_samples=bootstrap_samples,
        permutation_samples=permutation_samples,
    )
    baseline_manifest = read_json(out_dir / "baseline" / "manifest.json")
    candidate_manifest = read_json(out_dir / "candidate" / "manifest.json")
    baseline_manifest["split_hash"] = split.split_hash
    candidate_manifest["split_hash"] = split.split_hash
    baseline_prompt_identity = build_prompt_identity(
        prompt_id=baseline_prompt_id,
        prompt_file=baseline_prompt_file,
        prompt_version=baseline_prompt_version,
    )
    candidate_prompt_identity = build_prompt_identity(
        prompt_id=candidate_prompt_id,
        prompt_file=candidate_prompt_file,
        prompt_version=candidate_prompt_version,
    )
    if baseline_prompt_identity:
        baseline_manifest["prompt"] = baseline_prompt_identity
    if candidate_prompt_identity:
        candidate_manifest["prompt"] = candidate_prompt_identity
    write_json(out_dir / "baseline" / "manifest.json", baseline_manifest)
    write_json(out_dir / "candidate" / "manifest.json", candidate_manifest)
    baseline_identity = baseline_manifest.get("model", {})
    candidate_identity = candidate_manifest.get("model", {})
    if not isinstance(baseline_identity, dict):
        baseline_identity = {}
    if not isinstance(candidate_identity, dict):
        candidate_identity = {}
    manifest: JsonDict = {
        "tool": "promptcontrollab",
        "tool_version": __version__,
        "mode": "quick",
        "method": "baseline_vs_candidate",
        "metric": metric,
        "data_path": str(data_path),
        "baseline_predictions_path": str(baseline_predictions_path),
        "candidate_predictions_path": str(candidate_predictions_path),
        "baseline_run": str(out_dir / "baseline"),
        "candidate_run": str(out_dir / "candidate"),
        "baseline_model": baseline_identity,
        "candidate_model": candidate_identity,
        "model_warnings": compare_model_identities(baseline_identity, candidate_identity),
    }
    prompt_identity = build_prompt_identity(
        prompt_id=prompt_id,
        prompt_file=prompt_file,
        prompt_version=prompt_version,
    )
    if prompt_identity:
        manifest["prompt"] = prompt_identity
    if baseline_prompt_identity:
        manifest["baseline_prompt"] = baseline_prompt_identity
    if candidate_prompt_identity:
        manifest["candidate_prompt"] = candidate_prompt_identity
    write_json(out_dir / "manifest.json", manifest)
    generate_explanation(out_dir, level=explain_level)
    run_comparison_validity(
        baseline_dir=out_dir / "baseline",
        candidate_dir=out_dir / "candidate",
        out_path=out_dir / "comparison_validity.json",
    )
    if policy_path is not None:
        run_gate(out_dir, policy_path=policy_path)
    write_evidence_card(out_dir)
    generate_report(out_dir, title=title)


def load_analyze_config(path: Path) -> JsonDict:
    """Load a quick-mode config file."""

    return read_simple_yaml(path)


def resolve_analyze_paths(config: JsonDict, *, config_path: Path) -> dict[str, Path | None]:
    """Resolve path fields used by ``pcl analyze --config``."""

    base_dir = config_path.parent
    return {
        "data": get_config_path(config, "data", base_dir=base_dir),
        "baseline_predictions": get_config_path(config, "baseline_predictions", base_dir=base_dir),
        "candidate_predictions": get_config_path(
            config,
            "candidate_predictions",
            base_dir=base_dir,
        ),
        "gate_policy": get_config_path(config, "gate_policy", base_dir=base_dir),
        "prompt_file": get_config_path(config, "prompt_file", base_dir=base_dir),
        "baseline_prompt_file": get_config_path(
            config,
            "baseline_prompt_file",
            base_dir=base_dir,
        ),
        "candidate_prompt_file": get_config_path(
            config,
            "candidate_prompt_file",
            base_dir=base_dir,
        ),
    }


def config_metric(config: JsonDict, default: str) -> str:
    """Return metric from config."""

    return get_config_str(config, "metric", default)
