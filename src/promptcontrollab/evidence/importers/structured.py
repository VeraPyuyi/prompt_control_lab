"""Provider export normalization shared by evidence ingestion entrypoints."""

from __future__ import annotations

import csv
import hashlib
import html
import json
from pathlib import Path
from typing import Any, cast

from promptcontrollab.core.files import JsonDict, read_json
from promptcontrollab.core.schemas import PredictionRecord


def _deepeval_rows(payload: JsonDict, *, score_name: str | None) -> list[JsonDict]:
    test_cases, context = _deepeval_test_cases(payload)
    rows: list[JsonDict] = []
    for index, item in enumerate(test_cases):
        row = _row_from_deepeval_case(item, index=index, score_name=score_name, context=context)
        if row is not None:
            rows.append(row)
    return rows


def _deepeval_test_cases(payload: JsonDict) -> tuple[list[JsonDict], JsonDict]:
    context = _deepeval_context(payload)
    rows: list[JsonDict] = []
    nested_sources = [_dict_or_empty(payload.get(key)) for key in ["test_run", "testRun", "run"]]
    for source in [payload, *nested_sources]:
        for key in ["test_cases", "testCases", "test_results", "testResults", "results", "data"]:
            value = source.get(key)
            if isinstance(value, list):
                rows.extend(item for item in value if isinstance(item, dict))
    return rows, context


def _deepeval_context(payload: JsonDict) -> JsonDict:
    for key in ["hyperparameters", "metadata", "config"]:
        value = payload.get(key)
        if isinstance(value, dict):
            return cast(JsonDict, value)
    nested = payload.get("test_run") or payload.get("testRun") or payload.get("run")
    if isinstance(nested, dict):
        return _deepeval_context(cast(JsonDict, nested))
    return {}


def _row_from_deepeval_case(
    item: JsonDict,
    *,
    index: int,
    score_name: str | None,
    context: JsonDict,
) -> JsonDict | None:
    score = _deepeval_score(item, score_name=score_name)
    if score is None:
        return None
    test_case = _dict_or_empty(item.get("test_case")) or _dict_or_empty(item.get("testCase"))
    metadata = _dict_or_empty(item.get("metadata")) or _dict_or_empty(test_case.get("metadata"))
    model_id = (
        _optional_str(metadata.get("model"))
        or _optional_str(item.get("model"))
        or _optional_str(context.get("model"))
    )
    provider = (
        _optional_str(metadata.get("provider"))
        or _optional_str(item.get("provider"))
        or _optional_str(context.get("provider"))
    )
    if provider is None and model_id is not None:
        provider, model_id = _split_provider_model(model_id)
    stable_id = _stable_example_id(metadata, item, test_case)
    metric_reason = _deepeval_metric_reason(item, score_name=score_name)
    return {
        "id": stable_id
        or _optional_str(item.get("id"))
        or _optional_str(item.get("test_case_id"))
        or _optional_str(item.get("testCaseId"))
        or f"deepeval-{index}",
        "provider": provider,
        "model_id": model_id,
        "output": _deepeval_output(item, test_case),
        "expected": _deepeval_expected(item, test_case),
        "score": score,
        "slice": _deepeval_slice(metadata, item, test_case),
        "error": _optional_str(item.get("error")) or metric_reason,
    }


def _deepeval_score(item: JsonDict, *, score_name: str | None) -> float | None:
    for key in ["metrics", "metric_results", "metricResults", "metrics_data", "metricsData"]:
        value = item.get(key)
        if isinstance(value, list):
            matches = [metric for metric in value if isinstance(metric, dict)]
            if score_name is not None:
                matches = [
                    metric
                    for metric in matches
                    if metric.get("name") == score_name or metric.get("metric") == score_name
                ]
            elif len({metric.get("name") or metric.get("metric") for metric in matches}) > 1:
                msg = "Multiple DeepEval metric names found; pass --score-name to choose one"
                raise ValueError(msg)
            for metric in matches:
                parsed = _numeric_score(metric.get("score"))
                if parsed is not None:
                    return parsed
                for key in ["success", "passed"]:
                    parsed = _numeric_score(metric.get(key))
                    if parsed is not None:
                        return parsed
    for key in ["score", "value", "success", "passed"]:
        parsed = _numeric_score(item.get(key))
        if parsed is not None:
            return parsed
    return None


def _deepeval_metric_reason(item: JsonDict, *, score_name: str | None) -> str | None:
    metrics = item.get("metrics") or item.get("metric_results") or item.get("metricResults")
    if not isinstance(metrics, list):
        return None
    for metric in metrics:
        if not isinstance(metric, dict):
            continue
        if (
            score_name is not None
            and metric.get("name") != score_name
            and metric.get("metric") != score_name
        ):
            continue
        return _optional_str(metric.get("reason")) or _optional_str(metric.get("error"))
    return None


def _deepeval_output(item: JsonDict, test_case: JsonDict) -> str:
    for payload in [item, test_case]:
        for key in ["actual_output", "actualOutput", "output", "actual", "prediction"]:
            if key in payload:
                return _jsonish_text(payload.get(key))
    return ""


def _deepeval_expected(item: JsonDict, test_case: JsonDict) -> str:
    for payload in [item, test_case]:
        for key in ["expected_output", "expectedOutput", "expected", "target", "reference"]:
            if key in payload:
                return _jsonish_text(payload.get(key))
    return ""


def _deepeval_slice(*payloads: JsonDict) -> str:
    for payload in payloads:
        for key in ["slice", "dataset", "dataset_name", "task", "metric_name", "name"]:
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
    return "default"


def _langfuse_rows(payload: JsonDict, *, score_name: str | None) -> list[JsonDict]:
    observations = _langfuse_observations(payload)
    rows: list[JsonDict] = []
    for index, item in enumerate(observations):
        row = _row_from_langfuse_observation(item, index=index, score_name=score_name)
        if row is not None:
            rows.append(row)
    return rows


def _langsmith_rows(source_path: Path, *, score_name: str | None) -> list[JsonDict]:
    if source_path.suffix.lower() == ".csv":
        return _langsmith_csv_rows(source_path, score_name=score_name)
    payload = read_json(source_path)
    runs = _langsmith_run_items(payload)
    rows: list[JsonDict] = []
    for index, item in enumerate(runs):
        row = _row_from_langsmith_run(item, index=index, score_name=score_name)
        if row is not None:
            rows.append(row)
    return rows


def _langsmith_run_items(payload: JsonDict) -> list[JsonDict]:
    rows: list[JsonDict] = []
    for key in ["runs", "results", "data", "examples"]:
        value = payload.get(key)
        if isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, dict))
    return rows


def _langsmith_csv_rows(source_path: Path, *, score_name: str | None) -> list[JsonDict]:
    rows: list[JsonDict] = []
    with source_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, raw in enumerate(reader):
            row = _row_from_langsmith_csv(raw, index=index, score_name=score_name)
            if row is not None:
                rows.append(row)
    return rows


def _row_from_langsmith_run(
    item: JsonDict,
    *,
    index: int,
    score_name: str | None,
) -> JsonDict | None:
    score = _langsmith_score(item, score_name=score_name)
    if score is None:
        return None
    metadata = _langsmith_metadata(item)
    outputs = _dict_or_empty(item.get("outputs"))
    references = _dict_or_empty(item.get("reference_outputs")) or _dict_or_empty(
        item.get("referenceOutputs")
    )
    model_id = _optional_str(metadata.get("model")) or _optional_str(item.get("model"))
    provider = _optional_str(metadata.get("provider")) or _optional_str(item.get("provider"))
    if provider is None and model_id is not None:
        provider, model_id = _split_provider_model(model_id)
    stable_id = _stable_example_id(metadata, item)
    return {
        "id": stable_id
        or _optional_str(item.get("id"))
        or _optional_str(item.get("run_id"))
        or _optional_str(item.get("runId"))
        or f"run-{index}",
        "experiment": _langsmith_experiment(item, metadata),
        "provider": provider,
        "model_id": model_id,
        "output": _langsmith_output(item, outputs),
        "expected": _langsmith_expected(item, references),
        "score": score,
        "slice": _langsmith_slice(metadata, item),
        "error": _optional_str(item.get("error")) or _optional_str(item.get("status")),
    }


def _row_from_langsmith_csv(
    item: dict[str, str],
    *,
    index: int,
    score_name: str | None,
) -> JsonDict | None:
    score = _langsmith_csv_score(item, score_name=score_name)
    if score is None:
        return None
    model_id = _csv_first(item, ["model", "model_id", "model_id.name"])
    provider = _csv_first(item, ["provider", "model_provider"])
    if provider is None and model_id is not None:
        provider, model_id = _split_provider_model(model_id)
    return {
        "id": _csv_first(
            item,
            [
                "example_id",
                "exampleId",
                "dataset_example_id",
                "dataset_item_id",
                "metadata.example_id",
                "metadata.dataset_item_id",
                "reference_example_id",
                "run_id",
                "id",
                "runId",
            ],
        )
        or f"run-{index}",
        "experiment": _csv_first(item, ["experiment_name", "experiment", "session_name"]),
        "provider": provider,
        "model_id": model_id,
        "output": _csv_first(item, ["output", "outputs", "prediction", "answer"]) or "",
        "expected": _csv_first(
            item,
            ["reference_output", "reference_outputs", "expected", "target"],
        )
        or "",
        "score": score,
        "slice": _csv_first(item, ["slice", "metadata.slice", "dataset", "task"]) or "default",
        "error": _csv_first(item, ["error", "status"]),
    }


def _filter_langsmith_rows(
    rows: list[JsonDict],
    *,
    experiment: str | None,
    model: str | None,
    provider: str | None,
) -> list[JsonDict]:
    return [
        row
        for row in rows
        if (experiment is None or row.get("experiment") == experiment)
        and (model is None or row.get("model_id") == model)
        and (provider is None or row.get("provider") == provider)
    ]


def _langfuse_observations(payload: JsonDict) -> list[JsonDict]:
    rows: list[JsonDict] = []
    for key in ["observations", "generations"]:
        value = payload.get(key)
        if isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, dict))
    for key in ["data", "traces"]:
        value = payload.get(key)
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            nested = item.get("observations")
            if isinstance(nested, list):
                rows.extend(
                    _with_trace_context(observation, item)
                    for observation in nested
                    if isinstance(observation, dict)
                )
            else:
                rows.append(item)
    return rows


def _with_trace_context(observation: JsonDict, trace: JsonDict) -> JsonDict:
    context: JsonDict = {}
    trace_id = trace.get("id") or trace.get("traceId")
    if isinstance(trace_id, str):
        context["trace_id"] = trace_id
    trace_name = trace.get("name")
    if isinstance(trace_name, str):
        context["trace_name"] = trace_name
    return {**observation, "_trace": context}


def _row_from_langfuse_observation(
    item: JsonDict,
    *,
    index: int,
    score_name: str | None,
) -> JsonDict | None:
    score = _langfuse_score(item, score_name=score_name)
    if score is None:
        return None
    metadata = _dict_or_empty(item.get("metadata"))
    input_payload = _dict_or_empty(item.get("input"))
    model_id = _optional_str(item.get("model")) or _optional_str(item.get("modelId"))
    provider = _optional_str(metadata.get("provider")) or _optional_str(item.get("provider"))
    if provider is None and model_id is not None:
        provider, model_id = _split_provider_model(model_id)
    stable_id = _stable_example_id(metadata, input_payload, item)
    return {
        "id": stable_id
        or _optional_str(item.get("id"))
        or _optional_str(item.get("observationId"))
        or f"observation-{index}",
        "name": _optional_str(item.get("name")),
        "provider": provider,
        "model_id": model_id,
        "output": _jsonish_text(item.get("output")),
        "expected": _langfuse_expected(metadata, input_payload),
        "score": score,
        "slice": _langfuse_slice(metadata, input_payload),
        "error": _optional_str(item.get("error")) or _optional_str(item.get("statusMessage")),
    }


def _filter_langfuse_rows(
    rows: list[JsonDict],
    *,
    name: str | None,
    model: str | None,
    provider: str | None,
) -> list[JsonDict]:
    return [
        row
        for row in rows
        if (name is None or row.get("name") == name)
        and (model is None or row.get("model_id") == model)
        and (provider is None or row.get("provider") == provider)
    ]


def _filter_deepeval_rows(
    rows: list[JsonDict],
    *,
    model: str | None,
    provider: str | None,
) -> list[JsonDict]:
    return [
        row
        for row in rows
        if (model is None or row.get("model_id") == model)
        and (provider is None or row.get("provider") == provider)
    ]


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


def _prediction_from_langfuse_row(
    row: JsonDict,
    *,
    index: int,
    method: str,
) -> PredictionRecord:
    model_payload: JsonDict = {}
    if isinstance(row.get("provider"), str):
        model_payload["provider"] = row["provider"]
    if isinstance(row.get("model_id"), str):
        model_payload["model_id"] = row["model_id"]
    return PredictionRecord(
        id=_unique_id(row, index),
        output=str(row.get("output", "")),
        expected=str(row.get("expected", "")),
        score=float(row.get("score", 0.0)),
        slice=str(row.get("slice") or "default"),
        method=method,
        error=cast(str | None, row.get("error")),
        model=model_payload,
    )


def _prediction_from_langsmith_row(
    row: JsonDict,
    *,
    index: int,
    method: str,
) -> PredictionRecord:
    model_payload: JsonDict = {}
    if isinstance(row.get("provider"), str):
        model_payload["provider"] = row["provider"]
    if isinstance(row.get("model_id"), str):
        model_payload["model_id"] = row["model_id"]
    return PredictionRecord(
        id=_unique_id(row, index),
        output=str(row.get("output", "")),
        expected=str(row.get("expected", "")),
        score=float(row.get("score", 0.0)),
        slice=str(row.get("slice") or "default"),
        method=method,
        error=cast(str | None, row.get("error")),
        model=model_payload,
    )


def _prediction_from_deepeval_row(
    row: JsonDict,
    *,
    index: int,
    method: str,
) -> PredictionRecord:
    model_payload: JsonDict = {}
    if isinstance(row.get("provider"), str):
        model_payload["provider"] = row["provider"]
    if isinstance(row.get("model_id"), str):
        model_payload["model_id"] = row["model_id"]
    return PredictionRecord(
        id=_unique_id(row, index),
        output=str(row.get("output", "")),
        expected=str(row.get("expected", "")),
        score=float(row.get("score", 0.0)),
        slice=str(row.get("slice") or "default"),
        method=method,
        error=cast(str | None, row.get("error")),
        model=model_payload,
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


def _stable_example_id(*payloads: JsonDict) -> str | None:
    keys = [
        "example_id",
        "exampleId",
        "dataset_example_id",
        "datasetExampleId",
        "dataset_item_id",
        "datasetItemId",
        "reference_example_id",
        "referenceExampleId",
        "pcl_id",
        "input_id",
        "case_id",
        "sample_id",
    ]
    for payload in payloads:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
    return None


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


def _langfuse_score(item: JsonDict, *, score_name: str | None) -> float | None:
    scores = item.get("scores")
    if isinstance(scores, list):
        matches = [score for score in scores if isinstance(score, dict)]
        if score_name is not None:
            matches = [score for score in matches if score.get("name") == score_name]
        else:
            score_names = {
                score.get("name") for score in matches if isinstance(score.get("name"), str)
            }
            if len(score_names) > 1:
                msg = "Multiple Langfuse score names found; pass --score-name to choose one"
                raise ValueError(msg)
        for score in matches:
            value = score.get("value")
            if isinstance(value, bool):
                return 1.0 if value else 0.0
            if isinstance(value, int | float):
                return float(value)
    for key in ["score", "value"]:
        value = item.get(key)
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        if isinstance(value, int | float):
            return float(value)
    if item.get("success") is True or item.get("pass") is True:
        return 1.0
    if item.get("success") is False or item.get("pass") is False:
        return 0.0
    return None


def _langsmith_score(item: JsonDict, *, score_name: str | None) -> float | None:
    feedback = item.get("feedback_stats") or item.get("feedbackStats") or item.get("scores")
    if isinstance(feedback, dict):
        if score_name is not None:
            return _numeric_score(feedback.get(score_name))
        numeric = [
            float(value) for value in feedback.values() if isinstance(value, int | float | bool)
        ]
        if len(numeric) == 1:
            return numeric[0]
        if len(numeric) > 1:
            msg = "Multiple LangSmith score names found; pass --score-name to choose one"
            raise ValueError(msg)
    if isinstance(feedback, list):
        matches = [score for score in feedback if isinstance(score, dict)]
        if score_name is not None:
            matches = [
                score
                for score in matches
                if score.get("key") == score_name or score.get("name") == score_name
            ]
        elif len({score.get("key") or score.get("name") for score in matches}) > 1:
            msg = "Multiple LangSmith score names found; pass --score-name to choose one"
            raise ValueError(msg)
        for score in matches:
            value = score.get("score")
            if value is None:
                value = score.get("value")
            parsed = _numeric_score(value)
            if parsed is not None:
                return parsed
    for key in ["score", "value"]:
        parsed = _numeric_score(item.get(key))
        if parsed is not None:
            return parsed
    return None


def _langsmith_csv_score(item: dict[str, str], *, score_name: str | None) -> float | None:
    if score_name is not None:
        return _parse_float(item.get(score_name) or item.get(f"feedback.{score_name}"))
    candidates = [
        value
        for key, value in item.items()
        if key
        not in {
            "run_id",
            "id",
            "runId",
            "experiment_name",
            "experiment",
            "session_name",
            "output",
            "outputs",
            "prediction",
            "answer",
            "reference_output",
            "reference_outputs",
            "expected",
            "target",
            "model",
            "model_id",
            "provider",
            "model_provider",
            "slice",
            "metadata.slice",
            "dataset",
            "task",
            "error",
            "status",
        }
        and _parse_float(value) is not None
    ]
    if len(candidates) == 1:
        return _parse_float(candidates[0])
    if len(candidates) > 1:
        msg = "Multiple LangSmith score columns found; pass --score-name to choose one"
        raise ValueError(msg)
    return None


def _numeric_score(value: object) -> float | None:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        return _parse_float(value)
    return None


def _parse_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _dict_or_empty(value: object) -> JsonDict:
    return cast(JsonDict, value) if isinstance(value, dict) else {}


def _json_list(value: object) -> list[JsonDict]:
    if not isinstance(value, list):
        return []
    return [cast(JsonDict, item) for item in value if isinstance(item, dict)]


def _string_list(value: object) -> list[str]:
    if isinstance(value, str) and value:
        return [value]
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _markdown_cell(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def _html_text(value: object) -> str:
    return html.escape(str(value or ""))


def _jsonish_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _langfuse_expected(metadata: JsonDict, input_payload: JsonDict) -> str:
    for payload in [metadata, input_payload]:
        for key in ["expected", "reference", "target", "ground_truth", "groundTruth"]:
            value = payload.get(key)
            if value is not None:
                return _jsonish_text(value)
    return ""


def _langfuse_slice(metadata: JsonDict, input_payload: JsonDict) -> str:
    for payload in [metadata, input_payload]:
        for key in ["slice", "dataset", "dataset_name", "datasetName", "task"]:
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
    return "default"


def _langsmith_metadata(item: JsonDict) -> JsonDict:
    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        return cast(JsonDict, metadata)
    extra = item.get("extra")
    if isinstance(extra, dict):
        nested = extra.get("metadata")
        if isinstance(nested, dict):
            return cast(JsonDict, nested)
    return {}


def _langsmith_experiment(item: JsonDict, metadata: JsonDict) -> str | None:
    for payload in [item, metadata]:
        for key in ["experiment_name", "experiment", "session_name", "project_name", "name"]:
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _langsmith_output(item: JsonDict, outputs: JsonDict) -> str:
    for key in ["output", "prediction", "answer", "response"]:
        if key in item:
            return _jsonish_text(item.get(key))
        if key in outputs:
            return _jsonish_text(outputs.get(key))
    if outputs:
        if len(outputs) == 1:
            return _jsonish_text(next(iter(outputs.values())))
        return _jsonish_text(outputs)
    return ""


def _langsmith_expected(item: JsonDict, references: JsonDict) -> str:
    for key in ["reference_output", "reference", "expected", "target"]:
        if key in item:
            return _jsonish_text(item.get(key))
        if key in references:
            return _jsonish_text(references.get(key))
    if references:
        if len(references) == 1:
            return _jsonish_text(next(iter(references.values())))
        return _jsonish_text(references)
    return ""


def _langsmith_slice(metadata: JsonDict, item: JsonDict) -> str:
    for payload in [metadata, item]:
        for key in ["slice", "dataset", "dataset_name", "task"]:
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
    return "default"


def _csv_first(item: dict[str, str], keys: list[str]) -> str | None:
    for key in keys:
        value = item.get(key)
        if value:
            return value
    return None


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
