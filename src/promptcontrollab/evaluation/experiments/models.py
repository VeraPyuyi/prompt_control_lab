"""Validated, versioned contracts for local experiment jobs."""

from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from promptcontrollab.core.schemas import TaskRecord
from promptcontrollab.evaluation.metrics import score_output


def _number(value: object, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    if not math.isfinite(value) or value < 0 or (positive and value <= 0):
        raise ValueError(f"{label} must be {'positive' if positive else 'nonnegative'} and finite")
    return float(value)


def _integer(value: object, label: str, *, positive: bool = False) -> int:
    _number(value, label, positive=positive)
    if not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def model_config(value: object, label: str, *, imported: bool = False) -> dict[str, Any]:
    """Validate model settings, environment credential names, and DeepSeek thinking mode."""
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    allowed = {
        "prompt",
        "provider",
        "model",
        "base_url",
        "api_key_env",
        "auth_scheme",
        "thinking",
        "max_output_tokens",
        "temperature",
        "top_p",
        "seed",
        "timeout",
    }
    if set(value) - allowed:
        raise ValueError(f"Unsupported {label} fields: {', '.join(sorted(set(value) - allowed))}")
    result = copy.deepcopy(value)
    for key in ("prompt", "provider", "model"):
        if imported:
            result.setdefault(key, "" if key == "prompt" else "imported")
        if not isinstance(result.get(key), str) or (key != "prompt" and not result[key].strip()):
            raise ValueError(
                f"{label}.{key} must be a string{' with a value' if key != 'prompt' else ''}"
            )
    result["max_output_tokens"] = _integer(
        result.get("max_output_tokens", 256), f"{label}.max_output_tokens", positive=True
    )
    if "api_key_env" in result and (
        not isinstance(result["api_key_env"], str)
        or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", result["api_key_env"])
    ):
        raise ValueError("api_key_env must name an environment variable")
    if "auth_scheme" in result and (
        result["provider"] != "anthropic" or result["auth_scheme"] not in {"api_key", "bearer"}
    ):
        raise ValueError("auth_scheme supports api_key or bearer only for Anthropic endpoints")
    if "thinking" in result and (
        result["provider"] != "deepseek"
        or not isinstance(result["thinking"], str)
        or result["thinking"] not in {"enabled", "disabled"}
    ):
        raise ValueError("thinking supports enabled or disabled only for DeepSeek endpoints")
    if "base_url" in result:
        if not isinstance(result["base_url"], str):
            raise ValueError("base_url must be a string")
        parsed = urlsplit(result["base_url"])
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            raise ValueError("base_url must be an absolute HTTP(S) URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("base_url must not contain credentials, query parameters or fragments")
        if parsed.scheme == "http" and parsed.hostname.lower() not in {
            "localhost",
            "127.0.0.1",
            "::1",
        }:
            raise ValueError("Remote provider endpoints require HTTPS")
    for key in ("temperature", "top_p", "timeout"):
        if key in result:
            _number(result[key], f"{label}.{key}", positive=key == "timeout")
    if result.get("top_p", 1) > 1 or result.get("temperature", 0) > 2:
        raise ValueError("top_p must be <= 1 and temperature must be <= 2")
    if "seed" in result:
        _integer(result["seed"], f"{label}.seed")
    return result


@dataclass(frozen=True)
class ExperimentSpec:
    """A validated experiment/v1 JSON snapshot, independent of mutable files."""

    payload: dict[str, Any]

    @classmethod
    def from_json(cls, value: dict[str, Any]) -> ExperimentSpec:
        """Validate experiment settings and return an independent JSON snapshot."""
        if not isinstance(value, dict):
            raise ValueError("Experiment spec must be an object")
        json.dumps(value, allow_nan=False)
        spec = copy.deepcopy(value)
        allowed = {
            "schema_version",
            "name",
            "operation",
            "data",
            "baseline",
            "candidate",
            "metric",
            "budget",
            "seed",
            "split",
            "optimization",
            "predictions",
            "max_concurrency",
            "title",
            "synthetic",
            "provenance",
        }
        if set(spec) - allowed:
            raise ValueError(
                f"Unsupported experiment fields: {', '.join(sorted(set(spec) - allowed))}"
            )
        if spec.get("schema_version", "experiment/v1") != "experiment/v1":
            raise ValueError("schema_version must be experiment/v1")
        spec["schema_version"] = "experiment/v1"
        if "title" in spec:
            if not isinstance(spec["title"], str):
                raise ValueError("title must be a string")
            spec.setdefault("name", spec["title"])
        if "synthetic" in spec and not isinstance(spec["synthetic"], bool):
            raise ValueError("synthetic must be a boolean")
        if "provenance" in spec and not isinstance(spec["provenance"], dict):
            raise ValueError("provenance must be an object")
        operation = spec.setdefault("operation", "run")
        if operation not in {"run", "import", "optimize"}:
            raise ValueError("operation must be run, import or optimize")
        if "name" in spec and not isinstance(spec["name"], str):
            raise ValueError("name must be a string")
        data = spec.get("data")
        if not isinstance(data, list) or not data:
            raise ValueError("data must be a nonempty list of task records")
        if not all(isinstance(item, dict) for item in data):
            raise ValueError("Each task must be an object")
        tasks = [TaskRecord.from_json(item).to_json() for item in data]
        ids = [item["id"] for item in tasks]
        if any(not item.strip() for item in ids) or len(ids) != len(set(ids)):
            raise ValueError("Task IDs must be nonempty and unique")
        spec["data"] = tasks
        if operation == "optimize" and "candidate" not in spec:
            spec["candidate"] = copy.deepcopy(spec.get("baseline", {}))
        for arm in ("baseline", "candidate"):
            spec[arm] = model_config(spec.get(arm, {}), arm, imported=operation == "import")
        if operation == "optimize":
            for arm in ("baseline", "candidate"):
                prompt = spec[arm]["prompt"]
                if len(prompt) > 100_000 or prompt.count("{input}") > 1:
                    raise ValueError(
                        "Optimization prompts must be at most 100000 characters "
                        "and contain at most one {input} placeholder"
                    )
            baseline_settings = {
                key: item for key, item in spec["baseline"].items() if key != "prompt"
            }
            candidate_settings = {
                key: item for key, item in spec["candidate"].items() if key != "prompt"
            }
            if baseline_settings != candidate_settings:
                raise ValueError(
                    "optimize requires baseline and candidate to use identical "
                    "model and decoding settings"
                )
        metric = spec.setdefault("metric", "exact_match")
        if not isinstance(metric, str):
            raise ValueError("metric must be a string")
        if metric.startswith("numeric_tolerance:"):
            _number(float(metric.split(":", 1)[1]), "numeric tolerance")
        for task in tasks:
            try:
                score_output("", task["expected"], metric)
            except re.error as exc:
                raise ValueError(f"Invalid expected regex for task {task['id']}: {exc}") from exc
        spec["seed"] = _integer(spec.get("seed", 0), "seed")
        concurrency = _integer(spec.get("max_concurrency", 2), "max_concurrency", positive=True)
        if concurrency > 2:
            raise ValueError("max_concurrency cannot exceed 2")
        spec["max_concurrency"] = concurrency
        budget = spec.setdefault("budget", {})
        if not isinstance(budget, dict):
            raise ValueError("budget must be an object")
        if set(budget) - {
            "max_calls",
            "max_output_tokens",
            "max_seconds",
            "max_cost",
            "input_cost_per_million",
            "output_cost_per_million",
        }:
            raise ValueError("Unsupported budget fields")
        defaults = {"max_calls": 100, "max_output_tokens": 25600, "max_seconds": 300}
        for key, default in defaults.items():
            budget[key] = (_number if key == "max_seconds" else _integer)(
                budget.get(key, default), f"budget.{key}", positive=key == "max_seconds"
            )
        for key in ("max_cost", "input_cost_per_million", "output_cost_per_million"):
            if key in budget and budget[key] is not None:
                _number(budget[key], f"budget.{key}")
        split = spec.setdefault("split", {"train_ratio": 0.6, "val_ratio": 0.2})
        if not isinstance(split, dict) or set(split) - {"train_ratio", "val_ratio"}:
            raise ValueError("split must contain train_ratio and val_ratio")
        train = _number(split.setdefault("train_ratio", 0.6), "split.train_ratio", positive=True)
        val = _number(split.setdefault("val_ratio", 0.2), "split.val_ratio", positive=True)
        if train + val >= 1:
            raise ValueError("train_ratio + val_ratio must be less than 1")
        opt = spec.setdefault("optimization", {})
        if not isinstance(opt, dict) or set(opt) - {"max_rounds", "patience", "reflection"}:
            raise ValueError("Unsupported optimization settings")
        for key, default in (("max_rounds", 5), ("patience", 2)):
            opt[key] = _integer(opt.get(key, default), f"optimization.{key}", positive=True)
        if "reflection" in opt:
            opt["reflection"] = model_config(opt["reflection"], "optimization.reflection")
        if operation == "import":
            predictions = spec.get("predictions")
            if not isinstance(predictions, dict) or set(predictions) != {"baseline", "candidate"}:
                raise ValueError(
                    "import requires predictions.baseline and predictions.candidate lists"
                )
            for arm, records in predictions.items():
                if not isinstance(records, list) or any(
                    not isinstance(row, dict) for row in records
                ):
                    raise ValueError(f"predictions.{arm} must be a list of objects")
                seen = set()
                for row in records:
                    item_id = row.get("id")
                    if not isinstance(item_id, str) or item_id not in ids or item_id in seen:
                        raise ValueError(f"predictions.{arm} contains a duplicate or unknown ID")
                    seen.add(item_id)
        elif "predictions" in spec:
            raise ValueError("predictions is supported only by operation=import")
        return cls(spec)

    def to_json(self) -> dict[str, Any]:
        """Return a deep copy of the validated experiment configuration."""
        return copy.deepcopy(self.payload)


@dataclass(frozen=True)
class ExperimentJob:
    """Persisted projection of a job's execution and artifact state."""

    payload: dict[str, Any]

    def to_json(self) -> dict[str, Any]:
        """Return a deep copy of the persisted job projection."""
        return copy.deepcopy(self.payload)


@dataclass(frozen=True)
class ComparisonAssessment:
    """Independent comparability, effect, coverage and cost conclusions."""

    payload: dict[str, Any]

    def to_json(self) -> dict[str, Any]:
        """Return independent comparison conclusions as a JSON-compatible dictionary."""
        return copy.deepcopy(self.payload)
