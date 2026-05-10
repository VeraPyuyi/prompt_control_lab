"""High-level quick-mode workflows."""

from __future__ import annotations

from pathlib import Path

from promptcontrollab.config import get_config_path, get_config_str, read_simple_yaml
from promptcontrollab.evaluation import run_import_eval
from promptcontrollab.explain import generate_explanation
from promptcontrollab.files import JsonDict, ensure_dir, write_json
from promptcontrollab.gate import run_gate
from promptcontrollab.reporting import generate_report
from promptcontrollab.splitting import load_tasks, make_split, write_split
from promptcontrollab.statistics import compare_prediction_files
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
    )
    run_import_eval(
        data_path=data_path,
        predictions_path=candidate_predictions_path,
        out_dir=out_dir / "candidate",
        metric=metric,
        method="candidate",
    )
    compare_prediction_files(
        baseline_path=out_dir / "baseline" / "predictions.jsonl",
        candidate_path=out_dir / "candidate" / "predictions.jsonl",
        out_path=out_dir / "stats.json",
        seed=seed,
        bootstrap_samples=bootstrap_samples,
        permutation_samples=permutation_samples,
    )
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
    }
    write_json(out_dir / "manifest.json", manifest)
    generate_explanation(out_dir, level=explain_level)
    if policy_path is not None:
        run_gate(out_dir, policy_path=policy_path)
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
    }


def config_metric(config: JsonDict, default: str) -> str:
    """Return metric from config."""

    return get_config_str(config, "metric", default)
