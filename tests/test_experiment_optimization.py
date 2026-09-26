"""Offline engine tests: synthetic scores are never evidence of live model gains."""

from __future__ import annotations

import copy
import importlib
import json
import re
from pathlib import Path
from typing import Any

import pytest


class StoppedError(RuntimeError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class SyntheticRuntime:
    """Deterministic provider boundary; the optimization algorithm is real GEPA."""

    def __init__(self, path: Path):
        self.job_dir = path
        config = {
            "prompt": "Be conversational.",
            "provider": "synthetic",
            "model": "test-only",
            "max_output_tokens": 64,
        }
        self.spec: dict[str, Any] = {
            "baseline": config,
            "candidate": copy.deepcopy(config),
            "metric": "exact_match",
            "seed": 17,
            "optimization": {"max_rounds": 5, "patience": 2},
            "budget": {"max_calls": 100, "max_output_tokens": 10000},
        }
        self.tasks = [
            {"id": part, "input": f"{part.upper()}_INPUT", "expected": f"{part.upper()}_EXPECTED"}
            for part in ("train", "val", "withheld")
        ]
        self.split = {part: [part] for part in ("train", "val", "withheld")}
        self.calls: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.saved: dict[str, dict[str, Any]] = {}
        self.cached: dict[str, dict[str, Any]] = {}
        self.proposals = ["ANSWER_ONLY", "ANSWER_ONLY", "ANSWER_ONLY"]
        self.failure_phase: str | None = None
        self.stop_reason: str | None = None
        self.limit = 100

    def check_stop(self) -> None:
        if self.stop_reason:
            raise StoppedError(self.stop_reason)

    def call(
        self, config: dict[str, Any], prompt: str, *, phase: str, label: str
    ) -> dict[str, Any]:
        self.check_stop()
        key = json.dumps([config, prompt, phase, label], sort_keys=True)
        if key in self.cached:
            return copy.deepcopy(self.cached[key])
        if len(self.calls) >= self.limit:
            raise StoppedError("budget_calls")
        self.calls.append(
            {"config": copy.deepcopy(config), "prompt": prompt, "phase": phase, "label": label}
        )
        if self.failure_phase and self.failure_phase in phase:
            return {"status": "provider_error", "output": "SECRET_SERVICE_ERROR", "score": None}
        if "reflection" in phase:
            result = {
                "status": "completed",
                "output": f"```\n{self.proposals.pop(0)}\n```",
                "usage": {"output_tokens": 8, "input_tokens": 30},
            }
        else:
            result = {
                "status": "completed",
                "output": prompt,
                "usage": {"output_tokens": 4, "input_tokens": 10},
            }
        self.cached[key] = copy.deepcopy(result)
        return result

    def evaluate(
        self, name: str, config: dict[str, Any], tasks: list[dict[str, Any]], phase: str
    ) -> list[dict[str, Any]]:
        rows = []
        for task in tasks:
            row = self.call(config, task["input"], phase=phase, label=f"{name}:{task['id']}")
            quality = float("ANSWER_ONLY" in config["prompt"])
            raw = 1.0 - quality if self.spec["metric"] == "format_error" else quality
            rows.append(
                {**row, "id": task["id"], "score": raw if row["status"] == "completed" else None}
            )
        return rows

    def event(self, kind: str, **details: Any) -> None:
        self.events.append({"kind": kind, **details})

    def checkpoint(self, name: str, payload: dict[str, Any]) -> None:
        self.saved[name] = json.loads(json.dumps(payload, allow_nan=False))

    def load_checkpoint(self, name: str) -> dict[str, Any] | None:
        return copy.deepcopy(self.saved.get(name))


def optimizer() -> Any:
    return importlib.import_module("promptcontrollab.evaluation.experiments.optimization")


def test_optional_dependency_failure_is_actionable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = optimizer()
    real_import = module.importlib.import_module

    def unavailable(name: str) -> Any:
        if name == "gepa":
            raise ImportError("synthetic missing dependency")
        return real_import(name)

    monkeypatch.setattr(module.importlib, "import_module", unavailable)
    with pytest.raises(RuntimeError, match=r"promptcontrollab\[optimize\]"):
        module.optimize(SyntheticRuntime(tmp_path))


def test_real_gepa_uses_shared_calls_and_only_training_reflection(tmp_path: Path) -> None:
    pytest.importorskip("gepa")
    runtime = SyntheticRuntime(tmp_path)
    result = optimizer().optimize(runtime)
    assert result["candidate"]["prompt"] == "ANSWER_ONLY"
    assert result["search_status"] == "completed"
    assert result["stop_reason"] == "no_improvement"
    assert result["best_round"] == 1
    assert result["rounds_completed"] == 3
    assert result["validation_improved"] is True
    reflections = [row for row in runtime.calls if "reflection" in row["phase"]]
    assert len(reflections) == 3
    assert all("TRAIN_INPUT" in row["prompt"] for row in reflections)
    assert all("VAL_INPUT" not in row["prompt"] for row in reflections)
    assert all("WITHHELD" not in json.dumps(row) for row in runtime.calls)
    assert result["history"][1]["parent_id"] == result["history"][0]["id"]
    assert result["history"][1]["validation_complete"] is True
    assert not list(tmp_path.rglob("*.pkl"))
    json.dumps(result, allow_nan=False)


def test_real_gepa_no_gain_retains_baseline_and_completes(tmp_path: Path) -> None:
    pytest.importorskip("gepa")
    runtime = SyntheticRuntime(tmp_path)
    runtime.proposals = ["still conversational", "also conversational"]
    result = optimizer().optimize(runtime)
    assert result["candidate"] == runtime.spec["baseline"]
    assert result["validation_improved"] is False
    assert result["search_status"] == "completed"
    assert result["stop_reason"] == "no_improvement"
    assert result["rounds_completed"] == 2


@pytest.mark.parametrize("phase", ["train", "reflection", "val"])
def test_provider_errors_stop_without_becoming_quality_feedback(tmp_path: Path, phase: str) -> None:
    pytest.importorskip("gepa")
    runtime = SyntheticRuntime(tmp_path)
    runtime.failure_phase = phase
    result = optimizer().optimize(runtime)
    assert result["search_status"] == "failed"
    assert result["stop_reason"] == "provider_error"
    assert result["candidate"] == runtime.spec["baseline"]
    assert result["validation_improved"] is False
    assert "SECRET_SERVICE_ERROR" not in json.dumps(runtime.events)
    assert sum("reflection" in row["phase"] for row in runtime.calls) <= 1
    for row in runtime.calls:
        if "reflection" in row["phase"]:
            assert "SECRET_SERVICE_ERROR" not in row["prompt"]


def test_budget_stop_keeps_only_completed_validation_and_resumes_json(tmp_path: Path) -> None:
    pytest.importorskip("gepa")
    runtime = SyntheticRuntime(tmp_path)
    runtime.limit = 4  # Seed val + train + reflection + candidate train, no candidate val.
    first = optimizer().optimize(runtime)
    assert first["search_status"] == "stopped"
    assert first["candidate"] == runtime.spec["baseline"]
    assert first["stop_reason"] == "budget_calls"
    assert first["history"][-1]["validation_complete"] is False
    before = len(runtime.calls)
    again = optimizer().optimize(runtime)
    assert len(runtime.calls) == before
    assert again["resumed"] is True
    assert again["candidate"] == runtime.spec["baseline"]


def test_cancelled_before_search_makes_no_calls(tmp_path: Path) -> None:
    pytest.importorskip("gepa")
    runtime = SyntheticRuntime(tmp_path)
    runtime.stop_reason = "cancelled"
    result = optimizer().optimize(runtime)
    assert result["search_status"] == "cancelled"
    assert result["stop_reason"] == "cancelled"
    assert runtime.calls == []


def test_format_error_metric_is_minimized(tmp_path: Path) -> None:
    pytest.importorskip("gepa")
    runtime = SyntheticRuntime(tmp_path)
    runtime.spec["metric"] = "format_error"
    runtime.spec["optimization"]["max_rounds"] = 1
    result = optimizer().optimize(runtime)
    assert result["validation_improved"] is True
    assert result["history"][0]["validation_score"] == 1
    assert result["history"][1]["validation_score"] == 0
    assert result["candidate"]["prompt"] == "ANSWER_ONLY"


def test_training_gain_cannot_substitute_for_validation(tmp_path: Path) -> None:
    pytest.importorskip("gepa")
    runtime = SyntheticRuntime(tmp_path)
    original = runtime.evaluate

    def only_train_improves(
        name: str, config: dict[str, Any], tasks: list[dict[str, Any]], phase: str
    ) -> list[dict[str, Any]]:
        records = original(name, config, tasks, phase)
        if phase == "val":
            for record in records:
                record["score"] = 0.0
        return records

    runtime.evaluate = only_train_improves  # type: ignore[method-assign]
    result = optimizer().optimize(runtime)
    assert result["search_status"] == "completed"
    assert result["validation_improved"] is False
    assert result["candidate"] == runtime.spec["baseline"]
    assert result["history"][1]["validation_complete"] is True
    assert result["history"][1]["validation_score"] == 0


def test_empty_proposal_stops_without_running_candidate(tmp_path: Path) -> None:
    pytest.importorskip("gepa")
    runtime = SyntheticRuntime(tmp_path)
    runtime.proposals = [""]
    result = optimizer().optimize(runtime)
    assert result["search_status"] == "failed"
    assert result["stop_reason"] == "invalid_proposal"
    assert result["candidate"] == runtime.spec["baseline"]
    assert len(runtime.calls) == 3  # seed validation, training, one guarded reflection


def test_repeated_input_placeholder_cannot_exceed_reserved_final_budget(tmp_path: Path) -> None:
    pytest.importorskip("gepa")
    runtime = SyntheticRuntime(tmp_path)
    runtime.proposals = ["ANSWER_ONLY {input} {input}"]
    result = optimizer().optimize(runtime)
    assert result["search_status"] == "failed"
    assert result["stop_reason"] == "invalid_proposal"
    assert "at most one {input}" in result["proposal_error"]
    assert result["candidate"] == runtime.spec["baseline"]
    assert len(runtime.calls) == 3


def test_corrupt_json_checkpoint_cannot_change_provider(tmp_path: Path) -> None:
    pytest.importorskip("gepa")
    runtime = SyntheticRuntime(tmp_path)
    runtime.spec["optimization"]["max_rounds"] = 1
    module = optimizer()
    module.optimize(runtime)
    payload = runtime.saved["optimizer"]
    payload["candidate"]["provider"] = "unexpected-network-destination"
    with pytest.raises(ValueError, match="checkpoint"):
        module.optimize(runtime)


def test_real_gepa_persistent_runtime_freezes_before_withheld(tmp_path: Path) -> None:
    pytest.importorskip("gepa")
    from promptcontrollab.evaluation.experiments.engine import create_experiment, run_experiment
    from promptcontrollab.evaluation.experiments.storage import job_directory

    path = Path(__file__).parents[1] / "examples" / "experiments" / "live-optimize.json"
    spec = json.loads(path.read_text(encoding="utf-8"))
    spec["synthetic"] = True
    spec["optimization"]["max_rounds"] = 1
    calls = []

    def provider(**kwargs: Any) -> dict[str, Any]:
        prompt = kwargs["prompt"]
        calls.append(prompt)
        if "Training examples and feedback:" in prompt:
            output = "```\nANSWER_ONLY. Compute and return only the integer answer.\n```"
        else:
            match = re.search(r"sum of (\d+) and (\d+)", prompt)
            assert match
            answer = str(int(match[1]) + int(match[2]))
            output = answer if prompt.startswith("ANSWER_ONLY") else f"The sum is {answer}."
        return {
            "output_text": output,
            "model_id": spec["baseline"]["model"],
            "usage": {"input_tokens": 5, "output_tokens": 8},
        }

    created = create_experiment(tmp_path, spec)
    job = run_experiment(tmp_path, created["id"], provider)
    assert job["status"] == "completed", job.get("error", job.get("stop_reason"))
    assert job["optimization"]["validation_improved"] is True
    assert job["assessment"]["coverage"]["matched"] == 3
    assert job["assessment"]["effect"]["statistics"]["mean_delta"] == 1
    assert job["budget"]["calls"] == len(calls)
    directory = job_directory(tmp_path, created["id"])
    split = json.loads((directory / "split.json").read_text())
    by_id = {row["id"]: row["input"] for row in spec["data"]}
    reflections = [prompt for prompt in calls if "Training examples and feedback:" in prompt]
    assert len(reflections) == 1
    assert all(by_id[item] not in reflections[0] for item in split["val"] + split["withheld"])
    selection = json.loads((directory / "checkpoints" / "selection.json").read_text())
    withheld_records = [
        json.loads(path.read_text()) for path in (directory / "calls").glob("*.json")
    ]
    assert all(
        row["started_at"] >= selection["frozen_at"]
        for row in withheld_records
        if row["phase"] == "withheld"
    )
    assert not list(directory.rglob("*.pkl"))
