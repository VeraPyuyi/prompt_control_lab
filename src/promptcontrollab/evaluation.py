"""Evaluation and import helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from promptcontrollab.files import JsonDict, read_jsonl, write_json, write_jsonl
from promptcontrollab.metrics import score_output, summarize_predictions
from promptcontrollab.model_identity import (
    detect_model_identity,
    model_payload_from_prediction,
)
from promptcontrollab.schemas import PredictionRecord, TaskRecord
from promptcontrollab.splitting import load_tasks
from promptcontrollab.version import __version__


@dataclass(frozen=True)
class RawPredictionOutput:
    """Raw prediction output plus optional model provenance."""

    output: str
    model: JsonDict = field(default_factory=dict)


def load_prediction_outputs(path: Path) -> dict[str, RawPredictionOutput]:
    """Load raw output records keyed by id."""

    outputs: dict[str, RawPredictionOutput] = {}
    for record in read_jsonl(path):
        raw_id = record.get("id")
        raw_output = record.get("output")
        if not isinstance(raw_id, str) or not isinstance(raw_output, str):
            msg = f"Prediction imports must contain string `id` and `output`: {path}"
            raise ValueError(msg)
        outputs[raw_id] = RawPredictionOutput(
            output=raw_output,
            model=model_payload_from_prediction(record),
        )
    return outputs


def build_predictions(
    tasks: list[TaskRecord],
    outputs: dict[str, RawPredictionOutput],
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
        prediction = outputs[task.id]
        predictions.append(
            PredictionRecord(
                id=task.id,
                output=prediction.output,
                expected=task.expected,
                score=score_output(prediction.output, task.expected, metric),
                slice=task.slice,
                method=method,
                model=prediction.model,
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
    provider: str | None = None,
    model_id: str | None = None,
    api_version: str | None = None,
    verify_model: bool = False,
) -> JsonDict:
    """Import raw predictions, score them, and write run artifacts."""

    tasks = load_tasks(data_path)
    outputs = load_prediction_outputs(predictions_path)
    predictions = build_predictions(tasks, outputs, metric=metric, method=method)
    summary = summarize_predictions(predictions)
    write_jsonl(out_dir / "predictions.jsonl", [prediction.to_json() for prediction in predictions])
    metrics_payload = summary.to_json()
    write_json(out_dir / "metrics.json", metrics_payload)
    model_identity = detect_model_identity(
        provider=provider,
        model_id=model_id,
        predictions_path=predictions_path if model_id is None else None,
        api_version=api_version,
        verify=verify_model,
    )
    manifest: JsonDict = {
        "tool": "promptcontrollab",
        "tool_version": __version__,
        "mode": "import",
        "method": method,
        "metric": metric,
        "data_path": str(data_path),
        "predictions_path": str(predictions_path),
        "model": model_identity.to_json(),
    }
    write_json(out_dir / "manifest.json", manifest)
    return metrics_payload


def load_scored_predictions(path: Path) -> list[PredictionRecord]:
    """Load already-scored prediction records."""

    return [PredictionRecord.from_json(record) for record in read_jsonl(path)]
