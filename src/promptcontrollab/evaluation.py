"""Evaluation and import helpers."""

from __future__ import annotations

from pathlib import Path

from promptcontrollab.files import JsonDict, read_jsonl, write_json, write_jsonl
from promptcontrollab.metrics import score_output, summarize_predictions
from promptcontrollab.schemas import PredictionRecord, TaskRecord
from promptcontrollab.splitting import load_tasks
from promptcontrollab.version import __version__


def load_prediction_outputs(path: Path) -> dict[str, str]:
    """Load raw output records keyed by id."""

    outputs: dict[str, str] = {}
    for record in read_jsonl(path):
        raw_id = record.get("id")
        raw_output = record.get("output")
        if not isinstance(raw_id, str) or not isinstance(raw_output, str):
            msg = f"Prediction imports must contain string `id` and `output`: {path}"
            raise ValueError(msg)
        outputs[raw_id] = raw_output
    return outputs


def build_predictions(
    tasks: list[TaskRecord],
    outputs: dict[str, str],
    *,
    metric: str,
    method: str,
) -> list[PredictionRecord]:
    """Join task records with raw model outputs and deterministic scores."""

    predictions: list[PredictionRecord] = []
    for task in tasks:
        if task.id not in outputs:
            predictions.append(
                PredictionRecord(
                    id=task.id,
                    output="",
                    expected=task.expected,
                    score=0.0,
                    slice=task.slice,
                    method=method,
                    error="missing_output",
                )
            )
            continue
        output = outputs[task.id]
        predictions.append(
            PredictionRecord(
                id=task.id,
                output=output,
                expected=task.expected,
                score=score_output(output, task.expected, metric),
                slice=task.slice,
                method=method,
            )
        )
    return predictions


def run_import_eval(
    *,
    data_path: Path,
    predictions_path: Path,
    out_dir: Path,
    metric: str,
    method: str,
) -> JsonDict:
    """Import raw predictions, score them, and write run artifacts."""

    tasks = load_tasks(data_path)
    outputs = load_prediction_outputs(predictions_path)
    predictions = build_predictions(tasks, outputs, metric=metric, method=method)
    summary = summarize_predictions(predictions)
    write_jsonl(out_dir / "predictions.jsonl", [prediction.to_json() for prediction in predictions])
    metrics_payload = summary.to_json()
    write_json(out_dir / "metrics.json", metrics_payload)
    manifest: JsonDict = {
        "tool": "promptcontrollab",
        "tool_version": __version__,
        "mode": "import",
        "method": method,
        "metric": metric,
        "data_path": str(data_path),
        "predictions_path": str(predictions_path),
    }
    write_json(out_dir / "manifest.json", manifest)
    return metrics_payload


def load_scored_predictions(path: Path) -> list[PredictionRecord]:
    """Load already-scored prediction records."""

    return [PredictionRecord.from_json(record) for record in read_jsonl(path)]

