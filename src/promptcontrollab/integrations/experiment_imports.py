"""Normalize existing exports while preserving their actual evidence scope."""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any

from promptcontrollab.integrations.experiment_inputs import MAX_RECORDS, parse_document


def normalize_import_document(payload: dict[str, Any], imports_root: Path) -> dict[str, Any]:
    """Normalize bounded native or external exports without promoting their evidence scope."""
    text = payload.get("text")
    if not isinstance(text, str):
        raise ValueError("Import must contain UTF-8 text")
    format = payload.get("format", "json")
    value = parse_document(text, format)
    arm = payload.get("arm")
    if arm is not None and arm not in {"baseline", "candidate"}:
        raise ValueError("Choose baseline or candidate as the import arm")
    native = isinstance(value, dict) and any(key in value for key in ("baseline", "candidate"))
    if native:
        if arm is None:
            raise ValueError("Native paired records require an explicit baseline or candidate arm")
        rows = value.get(arm)
    else:
        rows = (
            value
            if isinstance(value, list)
            else value.get("predictions")
            if isinstance(value, dict)
            else None
        )
    if isinstance(rows, list) and any(isinstance(row, dict) and "arm" in row for row in rows):
        native = True
        if arm is None:
            raise ValueError("Native paired records require an explicit baseline or candidate arm")
        if any(
            not isinstance(row, dict) or row.get("arm") not in {"baseline", "candidate"}
            for row in rows
        ):
            raise ValueError("Native paired records contain an invalid arm")
        rows = [row for row in rows if row["arm"] == arm]
    if native or (
        isinstance(rows, list)
        and rows
        and all(
            isinstance(row, dict)
            and "id" in row
            and ("output" in row or "output_text" in row or "status" in row or "error" in row)
            for row in rows
        )
    ):
        normalized = _prediction_rows(rows)
        result = {
            "kind": "predictions",
            "predictions": normalized,
            "source": "promptcontrollab" if native else "user_import",
            "assessment": "declared_provenance",
        }
        if native and format == "csv":
            result["warnings"] = [
                "Spreadsheet-safe CSV may escape text; use records.json for exact text replay."
            ]
        return result
    if isinstance(value, dict) and value.get("artifact_type") == "aggregate_metrics":
        metrics = value.get("metrics")
        if not isinstance(metrics, dict):
            raise ValueError("Aggregate import requires metrics")
        json.dumps(metrics, allow_nan=False)
        return {
            "kind": "aggregate",
            "metrics": metrics,
            "assessment": "descriptive_only",
            "paired_statistics": None,
        }
    from promptcontrollab.evidence.ingest import ingest_auto_results

    directory = imports_root / secrets.token_hex(12)
    directory.mkdir(parents=True)
    source = directory / ("source.csv" if format == "csv" else "source.json")
    # JSONL was already parsed. The legacy detector accepts JSON documents, not
    # newline-delimited text with a .json suffix.
    source.write_text(
        text if format == "csv" else json.dumps(value, ensure_ascii=False), encoding="utf-8"
    )
    result = ingest_auto_results(
        source_path=source,
        out_dir=directory / "normalized",
        method=payload.get("method"),
        prompt_id=payload.get("prompt_id"),
        score_name=payload.get("score_name"),
    )
    normalized_dir = directory / "normalized"
    if (normalized_dir / "prompt_assets.json").is_file():
        assets = json.loads((normalized_dir / "prompt_assets.json").read_text(encoding="utf-8"))[
            "assets"
        ]
        return {
            "kind": "assets",
            "assets": [
                {"id": row.get("id"), "title": row.get("title"), "content": row.get("content")}
                for row in assets
            ],
            "assessment": "needs_evaluation",
            "source": result.get("source_tool"),
        }
    path = normalized_dir / "predictions.jsonl"
    if not path.is_file():
        raise ValueError(
            "No per-item predictions found; import aggregate metrics for descriptive review"
        )
    predictions = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if result.get("source_tool") == "deepeval":
        _separate_deepeval_feedback(value, predictions, payload.get("score_name"))
    predictions = _prediction_rows(predictions)
    return {
        "kind": "predictions",
        "predictions": predictions,
        "source": result.get("source_tool"),
        "assessment": "declared_provenance",
    }


def _prediction_rows(rows: Any) -> list[dict[str, Any]]:
    if (
        not isinstance(rows, list)
        or not rows
        or len(rows) > MAX_RECORDS
        or any(not isinstance(row, dict) for row in rows)
    ):
        raise ValueError("Provide between 1 and 10,000 prediction records")
    ids = [row.get("id") for row in rows]
    if not all(isinstance(item, str) and item.strip() for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("Prediction IDs must be unique nonempty strings")
    for row in rows:
        output = row.get("output", row.get("output_text"))
        if output is not None and not isinstance(output, str):
            raise ValueError("Prediction output must be text or null for unavailable output")
        model = row.get("model")
        if isinstance(model, dict):
            row["model_metadata"] = dict(model)
            row["model"] = model.get("model_id") if isinstance(model.get("model_id"), str) else None
            if isinstance(model.get("provider"), str):
                row.setdefault("provider", model["provider"])
    json.dumps(rows, allow_nan=False)
    return rows


def _separate_deepeval_feedback(
    value: dict[str, Any], predictions: list[dict[str, Any]], score_name: str | None
) -> None:
    """Legacy exports stored metric reasons in error; keep actual errors distinct."""
    from promptcontrollab.evidence.importers.structured import (
        _deepeval_test_cases,
        _row_from_deepeval_case,
    )

    cases, context = _deepeval_test_cases(value)
    original = {}
    for index, case in enumerate(cases):
        row = _row_from_deepeval_case(case, index=index, score_name=score_name, context=context)
        if row:
            original[row["id"]] = case
    for prediction in predictions:
        source_case = original.get(prediction["id"])
        if source_case is None:
            raise ValueError("DeepEval prediction could not be matched to its source case")
        explanation = prediction.get("error")
        explicit_error = source_case.get("error")
        prediction["error"] = (
            explicit_error if isinstance(explicit_error, str) and explicit_error else None
        )
        if explanation and explanation != explicit_error:
            prediction["feedback"] = explanation
