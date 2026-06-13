"""Import artifacts from external eval tools into PromptControlLab runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from promptcontrollab.files import JsonDict, ensure_dir, read_json, write_json, write_jsonl
from promptcontrollab.metrics import summarize_predictions
from promptcontrollab.model_identity import detect_model_identity
from promptcontrollab.schemas import PredictionRecord
from promptcontrollab.version import __version__


def ingest_promptfoo_results(
    *,
    source_path: Path,
    out_dir: Path,
    prompt_id: str | None = None,
    provider: str | None = None,
    method: str | None = None,
) -> JsonDict:
    """Convert Promptfoo JSON eval output into one PromptControlLab scored run."""

    payload = read_json(source_path)
    rows = _promptfoo_rows(payload)
    if not rows:
        msg = f"No Promptfoo result rows found in {source_path}"
        raise ValueError(msg)
    selected = _filter_rows(rows, prompt_id=prompt_id, provider=provider)
    if not selected:
        msg = "No Promptfoo rows matched the requested prompt/provider filter"
        raise ValueError(msg)
    selected_prompt_id = prompt_id or _single_value(selected, "prompt_id", "Promptfoo prompt ids")
    selected_provider = provider or _single_value(selected, "provider", "Promptfoo providers")
    method_name = method or selected_prompt_id or "promptfoo"
    predictions = [
        _prediction_from_promptfoo_row(row, index=index, method=method_name)
        for index, row in enumerate(selected)
    ]
    summary = summarize_predictions(predictions)
    ensure_dir(out_dir)
    write_jsonl(out_dir / "predictions.jsonl", [prediction.to_json() for prediction in predictions])
    write_json(out_dir / "metrics.json", summary.to_json())
    provider_name, model_id = _split_provider_model(selected_provider)
    model_identity = detect_model_identity(provider=provider_name, model_id=model_id)
    prompt_identity = _prompt_identity(payload, selected_prompt_id)
    manifest: JsonDict = {
        "tool": "promptcontrollab",
        "tool_version": __version__,
        "mode": "promptfoo_ingest",
        "method": method_name,
        "metric": "promptfoo_score",
        "source_tool": "promptfoo",
        "source_path": str(source_path),
        "promptfoo_filter": {
            "prompt_id": selected_prompt_id,
            "provider": selected_provider,
        },
        "model": model_identity.to_json(),
    }
    if prompt_identity:
        manifest["prompt"] = prompt_identity
    write_json(out_dir / "manifest.json", manifest)
    return {
        "out_dir": str(out_dir),
        "count": len(predictions),
        "mean_score": summary.mean_score,
        "prompt_id": selected_prompt_id,
        "provider": selected_provider,
    }


def _promptfoo_rows(payload: JsonDict) -> list[JsonDict]:
    results = payload.get("results")
    if isinstance(results, list):
        return [_row_from_v3_result(item) for item in results if isinstance(item, dict)]
    table = payload.get("table")
    if isinstance(table, dict):
        body = table.get("body")
        if isinstance(body, list):
            rows: list[JsonDict] = []
            for row in body:
                if isinstance(row, dict):
                    rows.extend(_rows_from_table_row(row))
            return rows
    return []


def _row_from_v3_result(item: JsonDict) -> JsonDict:
    provider = _provider_id(item.get("provider"))
    prompt_id = _optional_str(item.get("promptId"))
    test_case = item.get("testCase")
    if not isinstance(test_case, dict):
        test_case = {}
    response = item.get("response")
    if not isinstance(response, dict):
        response = {}
    return {
        "id": _optional_str(item.get("id")) or _test_id(item.get("testIdx")),
        "prompt_id": prompt_id,
        "provider": provider,
        "output": _response_output(response, fallback=item.get("text")),
        "expected": _expected_from_test_case(test_case),
        "score": _score(item),
        "slice": _slice_from_test_case(test_case),
        "error": _optional_str(item.get("error")),
    }


def _rows_from_table_row(row: JsonDict) -> list[JsonDict]:
    outputs = row.get("outputs")
    if not isinstance(outputs, list):
        return []
    test_case = row.get("test")
    if not isinstance(test_case, dict):
        test_case = {}
    if "vars" not in test_case and isinstance(row.get("vars"), dict):
        test_case = {**test_case, "vars": row["vars"]}
    rows: list[JsonDict] = []
    for output in outputs:
        if not isinstance(output, dict):
            continue
        response = output.get("response")
        if not isinstance(response, dict):
            response = {}
        rows.append(
            {
                "id": _optional_str(output.get("id")) or _test_id(row.get("testIdx")),
                "prompt_id": _optional_str(output.get("prompt"))
                or _optional_str(output.get("promptId")),
                "provider": _provider_id(output.get("provider")),
                "output": _response_output(response, fallback=output.get("text")),
                "expected": _expected_from_test_case(test_case),
                "score": _score(output),
                "slice": _slice_from_test_case(test_case),
                "error": _optional_str(output.get("error")),
            }
        )
    return rows


def _filter_rows(
    rows: list[JsonDict],
    *,
    prompt_id: str | None,
    provider: str | None,
) -> list[JsonDict]:
    return [
        row
        for row in rows
        if (prompt_id is None or row.get("prompt_id") == prompt_id)
        and (provider is None or row.get("provider") == provider)
    ]


def _single_value(rows: list[JsonDict], key: str, label: str) -> str | None:
    values = sorted({value for row in rows if isinstance((value := row.get(key)), str) and value})
    if len(values) > 1:
        msg = f"Multiple {label} found; pass --{key.replace('_', '-')} to choose one: {values}"
        raise ValueError(msg)
    return values[0] if values else None


def _prediction_from_promptfoo_row(
    row: JsonDict,
    *,
    index: int,
    method: str,
) -> PredictionRecord:
    return PredictionRecord(
        id=_unique_id(row, index),
        output=str(row.get("output", "")),
        expected=str(row.get("expected", "")),
        score=float(row.get("score", 0.0)),
        slice=str(row.get("slice") or "default"),
        method=method,
        error=cast(str | None, row.get("error")),
    )


def _unique_id(row: JsonDict, index: int) -> str:
    raw_id = row.get("id")
    if isinstance(raw_id, str) and raw_id:
        return raw_id
    return f"test-{index}"


def _test_id(value: object) -> str:
    if isinstance(value, int):
        return f"test-{value}"
    if isinstance(value, str) and value:
        return value
    return ""


def _provider_id(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        raw = value.get("id") or value.get("label")
        if isinstance(raw, str):
            return raw
    return None


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _response_output(response: JsonDict, *, fallback: object) -> str:
    value = response.get("output")
    if value is None:
        value = fallback
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _expected_from_test_case(test_case: JsonDict) -> str:
    expected = test_case.get("expected")
    if isinstance(expected, str):
        return expected
    assertions = test_case.get("assert")
    if isinstance(assertions, list):
        for assertion in assertions:
            if isinstance(assertion, dict):
                value = assertion.get("value")
                if isinstance(value, str):
                    return value
                if value is not None:
                    return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return ""


def _slice_from_test_case(test_case: JsonDict) -> str:
    metadata = test_case.get("metadata")
    if isinstance(metadata, dict) and isinstance(metadata.get("slice"), str):
        return str(metadata["slice"])
    variables = test_case.get("vars")
    if isinstance(variables, dict) and isinstance(variables.get("slice"), str):
        return str(variables["slice"])
    description = test_case.get("description")
    if isinstance(description, str) and description:
        return description
    return "default"


def _score(item: JsonDict) -> float:
    raw_score = item.get("score")
    if isinstance(raw_score, int | float):
        return float(raw_score)
    grading = item.get("gradingResult")
    if isinstance(grading, dict) and isinstance(grading.get("score"), int | float):
        return float(grading["score"])
    if item.get("success") is True or item.get("pass") is True:
        return 1.0
    return 0.0


def _split_provider_model(provider: str | None) -> tuple[str | None, str | None]:
    if not provider:
        return None, None
    parts = provider.split(":", maxsplit=1)
    if len(parts) == 2 and parts[0] and parts[1]:
        return parts[0], parts[1]
    return None, provider


def _prompt_identity(payload: JsonDict, prompt_id: str | None) -> JsonDict:
    if prompt_id is None:
        return {}
    identity: JsonDict = {"prompt_id": prompt_id}
    prompt = _find_prompt(payload.get("prompts"), prompt_id)
    if prompt is None:
        return identity
    raw = prompt.get("raw") or prompt.get("template")
    if isinstance(raw, str):
        identity["prompt_hash"] = f"sha256:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"
    label = prompt.get("label")
    if isinstance(label, str):
        identity["prompt_label"] = label
    return identity


def _find_prompt(value: Any, prompt_id: str) -> JsonDict | None:
    if not isinstance(value, list):
        return None
    for item in value:
        if not isinstance(item, dict):
            continue
        for key in ["id", "label", "display"]:
            if item.get(key) == prompt_id:
                return item
    return None
