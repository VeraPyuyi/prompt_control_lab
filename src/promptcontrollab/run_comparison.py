"""One-command comparison for two existing run directories."""

from __future__ import annotations

import shutil
from pathlib import Path

from promptcontrollab.files import JsonDict, ensure_dir, read_json, write_json
from promptcontrollab.model_identity import compare_model_identities
from promptcontrollab.reporting import generate_report
from promptcontrollab.statistics import compare_prediction_files
from promptcontrollab.validity import run_comparison_validity
from promptcontrollab.version import __version__


def compare_runs(
    *,
    baseline_dir: Path,
    candidate_dir: Path,
    out_dir: Path,
    title: str,
    seed: int,
    bootstrap_samples: int,
    permutation_samples: int,
) -> JsonDict:
    """Compare two already-scored runs and write a self-contained comparison run."""

    baseline_predictions = baseline_dir / "predictions.jsonl"
    candidate_predictions = candidate_dir / "predictions.jsonl"
    _require_file(baseline_predictions, "baseline predictions")
    _require_file(candidate_predictions, "candidate predictions")
    _require_file(baseline_dir / "metrics.json", "baseline metrics")
    _require_file(candidate_dir / "metrics.json", "candidate metrics")
    _require_file(baseline_dir / "manifest.json", "baseline manifest")
    _require_file(candidate_dir / "manifest.json", "candidate manifest")
    _validate_output_dir(
        out_dir=out_dir,
        baseline_dir=baseline_dir,
        candidate_dir=candidate_dir,
    )

    ensure_dir(out_dir)
    comparison_baseline = out_dir / "baseline"
    comparison_candidate = out_dir / "candidate"
    ensure_dir(comparison_baseline)
    ensure_dir(comparison_candidate)

    _copy_run_file(baseline_dir, comparison_baseline, "predictions.jsonl")
    _copy_run_file(candidate_dir, comparison_candidate, "predictions.jsonl")
    _copy_run_file(baseline_dir, comparison_baseline, "metrics.json")
    _copy_run_file(candidate_dir, comparison_candidate, "metrics.json")
    _copy_run_file(baseline_dir, comparison_baseline, "manifest.json")
    _copy_run_file(candidate_dir, comparison_candidate, "manifest.json")
    _copy_optional_run_file(baseline_dir, comparison_baseline, "splits.json")
    _copy_optional_run_file(candidate_dir, comparison_candidate, "splits.json")
    shutil.copy2(candidate_dir / "metrics.json", out_dir / "metrics.json")

    stats = compare_prediction_files(
        baseline_path=comparison_baseline / "predictions.jsonl",
        candidate_path=comparison_candidate / "predictions.jsonl",
        out_path=out_dir / "stats.json",
        seed=seed,
        bootstrap_samples=bootstrap_samples,
        permutation_samples=permutation_samples,
    )
    validity = run_comparison_validity(
        baseline_dir=comparison_baseline,
        candidate_dir=comparison_candidate,
        out_path=out_dir / "comparison_validity.json",
    )

    baseline_manifest = read_json(baseline_dir / "manifest.json")
    candidate_manifest = read_json(candidate_dir / "manifest.json")
    baseline_model = _object_dict(baseline_manifest.get("model"))
    candidate_model = _object_dict(candidate_manifest.get("model"))
    manifest: JsonDict = {
        "tool": "promptcontrollab",
        "tool_version": __version__,
        "mode": "run_comparison",
        "method": "baseline_vs_candidate",
        "source": "compare-runs",
        "metric": candidate_manifest.get("metric") or baseline_manifest.get("metric"),
        "baseline_run": str(baseline_dir),
        "candidate_run": str(candidate_dir),
        "baseline_snapshot": str(comparison_baseline),
        "candidate_snapshot": str(comparison_candidate),
        "baseline_source_mode": baseline_manifest.get("mode"),
        "candidate_source_mode": candidate_manifest.get("mode"),
        "baseline_model": baseline_model,
        "candidate_model": candidate_model,
        "model_warnings": compare_model_identities(baseline_model, candidate_model),
    }
    baseline_prompt = _object_dict(baseline_manifest.get("prompt"))
    candidate_prompt = _object_dict(candidate_manifest.get("prompt"))
    if baseline_prompt:
        manifest["baseline_prompt"] = baseline_prompt
    if candidate_prompt:
        manifest["candidate_prompt"] = candidate_prompt
    write_json(out_dir / "manifest.json", manifest)
    md_path, html_path = generate_report(out_dir, title=title)

    payload: JsonDict = {
        "kind": "run_comparison",
        "out_dir": str(out_dir),
        "baseline_run": str(baseline_dir),
        "candidate_run": str(candidate_dir),
        "stats_path": str(out_dir / "stats.json"),
        "comparison_validity_path": str(out_dir / "comparison_validity.json"),
        "report_md": str(md_path),
        "report_html": str(html_path),
        "stats": stats,
        "comparison_validity": validity,
    }
    write_json(out_dir / "compare_runs_result.json", payload)
    return payload


def _require_file(path: Path, label: str) -> None:
    if not path.exists():
        msg = f"Missing {label}: {path}"
        raise ValueError(msg)


def _validate_output_dir(*, out_dir: Path, baseline_dir: Path, candidate_dir: Path) -> None:
    resolved_out = out_dir.resolve(strict=False)
    for label, source_dir in [
        ("baseline", baseline_dir),
        ("candidate", candidate_dir),
    ]:
        resolved_source = source_dir.resolve(strict=False)
        if _paths_overlap(resolved_out, resolved_source):
            msg = (
                f"Comparison output directory must not overlap the {label} source run: "
                f"{out_dir}"
            )
            raise ValueError(msg)
    if out_dir.exists() and any(out_dir.iterdir()):
        msg = f"Comparison output directory must be empty: {out_dir}"
        raise ValueError(msg)


def _paths_overlap(first: Path, second: Path) -> bool:
    return first == second or first in second.parents or second in first.parents


def _copy_run_file(source_dir: Path, target_dir: Path, name: str) -> None:
    shutil.copy2(source_dir / name, target_dir / name)


def _copy_optional_run_file(source_dir: Path, target_dir: Path, name: str) -> None:
    source = source_dir / name
    if source.exists():
        shutil.copy2(source, target_dir / name)


def _object_dict(value: object) -> JsonDict:
    return value if isinstance(value, dict) else {}
