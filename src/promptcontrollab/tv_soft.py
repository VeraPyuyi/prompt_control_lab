"""Time-varying soft-control lane summaries."""

from __future__ import annotations

from pathlib import Path

from promptcontrollab.evaluation import load_scored_predictions
from promptcontrollab.files import JsonDict, ensure_dir, write_json


def summarize_tv_soft(
    *,
    predictions_path: Path,
    out_dir: Path,
    baseline_method: str = "static",
) -> JsonDict:
    """Summarize static/time-varying/shuffled/random method groups from scored predictions."""

    predictions = load_scored_predictions(predictions_path)
    grouped: dict[str, list[float]] = {}
    for prediction in predictions:
        grouped.setdefault(prediction.method, []).append(prediction.score)
    means = {
        method: sum(scores) / len(scores)
        for method, scores in sorted(grouped.items(), key=lambda item: item[0])
        if scores
    }
    baseline = means.get(baseline_method)
    deltas = {
        method: (score - baseline if baseline is not None else None)
        for method, score in means.items()
        if method != baseline_method
    }
    payload: JsonDict = {
        "kind": "tv_soft",
        "predictions_path": str(predictions_path),
        "baseline_method": baseline_method,
        "method_means": means,
        "delta_vs_baseline": deltas,
        "interpretation": (
            "If time_varying beats static and shuffled_tv/random_tv do not, the gain is more "
            "consistent with temporal structure than raw parameter count. If shuffled or random "
            "matches it, inspect capacity and selection effects."
        ),
    }
    ensure_dir(out_dir)
    write_json(out_dir / "tv_soft.json", payload)
    return payload
