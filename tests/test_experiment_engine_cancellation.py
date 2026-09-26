"""Deterministic cancellation and completion-cache scheduling regressions."""

from __future__ import annotations

import json
import queue
import threading
from pathlib import Path
from typing import Any

import pytest

from promptcontrollab.evaluation.experiments import (
    cancel_experiment,
    create_experiment,
    prepare_resume,
    run_experiment,
)
from promptcontrollab.evaluation.experiments.runtime import ExperimentRuntime
from promptcontrollab.evaluation.experiments.storage import job_directory, read_json


def _spec() -> dict[str, Any]:
    return {
        "operation": "run",
        "data": [
            {"id": str(index), "input": f"item {index}", "expected": "yes"} for index in range(2)
        ],
        "baseline": {"provider": "openai", "model": "test", "prompt": "baseline"},
        "candidate": {"provider": "openai", "model": "test", "prompt": "candidate"},
        "metric": "exact_match",
        "budget": {"max_calls": 4, "max_output_tokens": 1024, "max_seconds": 30},
        "max_concurrency": 1,
    }


def test_cancelled_in_flight_success_is_preserved_before_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cancelled = threading.Event()
    allow_response = threading.Event()
    prompts: list[str] = []
    created = create_experiment(tmp_path, _spec())

    class CancellationBoundaryQueue(queue.Queue[Any]):
        def get(self, block: bool = True, timeout: float | None = None) -> Any:
            if not allow_response.is_set():
                assert cancelled.wait(5), "provider did not request cancellation"
                allow_response.set()
                # The polling wait expires immediately before the callback returns.
                raise queue.Empty
            return super().get(block, timeout)

    def cancelling(**kwargs: Any) -> str:
        prompts.append(kwargs["prompt"])
        cancel_experiment(tmp_path, created["id"])
        cancelled.set()
        assert allow_response.wait(5), "consumer did not reach the cancellation boundary"
        return "yes"

    with monkeypatch.context() as patch:
        patch.setattr(
            "promptcontrollab.evaluation.experiments.runtime.queue.Queue", CancellationBoundaryQueue
        )
        stopped = run_experiment(tmp_path, created["id"], cancelling)
    assert stopped["status"] == "cancelled"
    assert len(prompts) == 1
    directory = job_directory(tmp_path, created["id"])
    receipt = read_json(next((directory / "calls").glob("*.json")))
    record = read_json(next((directory / "records").glob("*.json")))
    assert receipt["status"] == record["status"] == "completed"
    assert receipt["output"] == record["output"] == "yes"
    prepare_resume(tmp_path, created["id"])

    def resumed(**kwargs: Any) -> str:
        prompts.append(kwargs["prompt"])
        return "yes"

    completed = run_experiment(tmp_path, created["id"], resumed)
    assert completed["status"] == "completed"
    assert completed["budget"]["calls"] == len(prompts) == len(set(prompts)) == 4


@pytest.mark.parametrize("concurrency", [1, 2])
def test_all_cached_completions_are_verified_before_new_batch_calls(
    tmp_path: Path, concurrency: int
) -> None:
    created = create_experiment(tmp_path, _spec())
    directory = job_directory(tmp_path, created["id"])
    spec = read_json(directory / "spec.json")
    spec["max_concurrency"] = concurrency
    requests: list[str] = []

    def provider(**kwargs: Any) -> str:
        requests.append(kwargs["prompt"])
        return "yes"

    runtime = ExperimentRuntime(directory, spec, read_json(directory / "split.json"), provider)
    try:
        runtime.evaluate("baseline", spec["baseline"], [runtime.tasks[1]], "evaluation")
        target = next((directory / "records").glob("*.json"))
        record = read_json(target)
        assert record["status"] == "completed"
        record["score"] = float("nan")
        corrupted = json.dumps(record)
        target.write_text(corrupted, encoding="utf-8")
        requests.clear()
        with pytest.raises(ValueError, match="immutable task or score"):
            runtime.evaluate("baseline", spec["baseline"], runtime.tasks, "evaluation")
        assert requests == [], "cache integrity must be checked before any fresh request"
        assert target.read_text(encoding="utf-8") == corrupted
    finally:
        runtime.close()


@pytest.mark.parametrize("returned_at", [0.5, 2.0])
@pytest.mark.parametrize("expired_poll", [False, True])
def test_transport_return_time_enforces_original_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, returned_at: float, expired_poll: bool
) -> None:
    clock = [0.0]
    release = threading.Event()
    created = create_experiment(tmp_path, _spec())
    directory = job_directory(tmp_path, created["id"])
    spec = read_json(directory / "spec.json")

    class DeadlineBoundaryQueue(queue.Queue[Any]):
        def get(self, block: bool = True, timeout: float | None = None) -> Any:
            if not block:
                return super().get(block, timeout)
            release.set()
            response = super().get(block, 5)
            # The consumer resumes after the deadline for either arrival order.
            clock[0] = 2.0
            if expired_poll:
                # The earlier wait timed out, then the response was enqueued
                # before the consumer resumed its Empty exception handler.
                self.put(response)
                raise queue.Empty
            return response

    def late_provider(**_: Any) -> str:
        assert release.wait(5)
        clock[0] = returned_at
        return "yes"

    monkeypatch.setattr(
        "promptcontrollab.evaluation.experiments.runtime.time.monotonic", lambda: clock[0]
    )
    monkeypatch.setattr(
        "promptcontrollab.evaluation.experiments.runtime.queue.Queue", DeadlineBoundaryQueue
    )
    runtime = ExperimentRuntime(directory, spec, read_json(directory / "split.json"), late_provider)
    try:
        config = {**spec["baseline"], "timeout": 1.0}
        outcome = runtime.call(config, "prompt", phase="evaluation", label="baseline:0")
        if returned_at > 1.0:
            assert outcome["status"] == "uncertain"
            assert outcome["error_type"] == "timeout"
            assert outcome["output"] is None
        else:
            assert outcome["status"] == "completed"
            assert outcome["output"] == "yes"
        assert runtime.budget_state()["calls"] == 1
    finally:
        runtime.close()
