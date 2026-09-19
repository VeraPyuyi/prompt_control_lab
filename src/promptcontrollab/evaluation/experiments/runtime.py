"""Budgeted, cancellable provider execution with a durable no-replay ledger."""

from __future__ import annotations

import copy
import math
import queue
import re
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, cast

from promptcontrollab.core.files import stable_digest
from promptcontrollab.evaluation.metrics import _first_number, score_output
from promptcontrollab.integrations.providers import call_provider

from .storage import JobLock, configured_secrets, event, read_json, redact, write_json


class ExperimentStopped(RuntimeError):  # noqa: N818 - public control-flow protocol
    """A bounded execution stopped before another request could be admitted."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _digest(value: object) -> str:
    return stable_digest(value).removeprefix("sha256:")


def _usage(value: object) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    result = {}
    for key, alias in (("input_tokens", "prompt_tokens"), ("output_tokens", "completion_tokens")):
        number = source.get(key, source.get(alias))
        result[key] = (
            number
            if isinstance(number, int) and not isinstance(number, bool) and number >= 0
            else None
        )
    return result


def output_quality(output: str, metric: str) -> str:
    """Classify observable output parsing and formatting failures separately from service errors."""
    if not output.strip():
        return "empty_output"
    if metric.startswith("numeric_tolerance") and _first_number(output) is None:
        return "parse_error"
    return "scored"


def render_task_prompt(config: dict[str, Any], task: dict[str, Any]) -> str:
    """Render task input into the prompt template or append it as a separate paragraph."""
    prompt = str(config["prompt"])
    return (
        prompt.replace("{input}", task["input"])
        if "{input}" in prompt
        else f"{prompt}\n\n{task['input']}"
        if prompt
        else str(task["input"])
    )


def validate_completed_record(
    record: dict[str, Any],
    task: dict[str, Any],
    config: dict[str, Any],
    *,
    metric: str,
    phase: str,
    name: str,
    job_dir: Path,
    imported: bool = False,
) -> None:
    """Check a reusable completion against its immutable task and call receipt."""
    score = record.get("score")
    if (
        record.get("id") != task["id"]
        or record.get("name") != name
        or record.get("phase") != phase
        or record.get("expected") != task["expected"]
        or not isinstance(record.get("output"), str)
        or isinstance(score, bool)
        or not isinstance(score, (int, float))
        or not 0 <= score <= 1
        or not math.isfinite(score)
        or score != score_output(record["output"], task["expected"], metric)
    ):
        raise ValueError("Persisted completion does not match its immutable task or score")
    if imported:
        return
    call_id = record.get("call_id")
    if not isinstance(call_id, str) or not re.fullmatch(r"[a-f0-9]{64}(?:-r[0-9]{6,})?", call_id):
        raise ValueError("Persisted completion has an invalid call receipt ID")
    receipt = read_json(job_dir / "calls" / f"{call_id}.json")
    if (
        receipt.get("status") != "completed"
        or receipt.get("output") != record["output"]
        or receipt.get("config_hash") != _digest(config)
        or receipt.get("prompt_hash") != _digest(render_task_prompt(config, task))
    ):
        raise ValueError("Persisted completion disagrees with its provider call receipt")


def ledger_budget(
    records: list[dict[str, Any]],
    budget: dict[str, Any],
    *,
    elapsed_seconds: float,
    concurrency: int,
) -> dict[str, Any]:
    """Project committed ledger receipts without mutating in-flight requests."""
    return {
        "calls": len(records),
        "charged_output_tokens": sum(
            row.get("charged_output_tokens", row.get("reserved_output_tokens", 0))
            for row in records
        ),
        "known_output_tokens": sum(
            row.get("usage", {}).get("output_tokens") or 0 for row in records
        ),
        "output_usage_complete": all(
            row.get("usage", {}).get("output_tokens") is not None for row in records
        ),
        "known_cost": sum(row.get("actual_cost") or 0 for row in records),
        "unknown_cost_calls": sum(row.get("actual_cost") is None for row in records),
        "reserved_cost": sum(
            row.get("charged_cost", row.get("reserved_cost")) or 0 for row in records
        ),
        "elapsed_seconds": round(elapsed_seconds, 6),
        "limits": budget,
        "concurrency_limit": concurrency,
    }


class ExperimentRuntime:
    """Shared execution protocol used by evaluation and GEPA optimization.

    Admission reserves a complete output limit before sending a call. Unknown
    usage retains that reservation. A timed-out request is never reissued,
    including on explicit resume. A still-running transport holds the global
    lease until it exits, preventing another job from overlapping it.
    """

    def __init__(
        self,
        job_dir: Path,
        spec: dict[str, Any],
        split: dict[str, Any],
        provider_call: Callable[..., Any] | None = None,
        lease: JobLock | None = None,
    ):
        self.job_dir = job_dir
        self.spec = copy.deepcopy(spec)
        self.tasks = copy.deepcopy(spec["data"])
        self.split = copy.deepcopy(split)
        self._provider = provider_call or call_provider
        self._lease = lease
        self._mutex = threading.RLock()
        self._started = time.monotonic()
        self._elapsed_before = float(read_json(job_dir / "job.json").get("elapsed_seconds", 0.0))
        job = read_json(job_dir / "job.json")
        self._execution_attempt = int(job.get("attempt", 1))
        self.retry_failed = bool(job.get("retry_failed", False))
        self._pending = 0
        self._closed = False
        self._headroom_calls = 0
        self._headroom_tokens = 0
        self._headroom_cost = 0.0
        self._halt: str | None = None
        self._secrets = configured_secrets(spec)
        for folder in ("calls", "records", "checkpoints"):
            (job_dir / folder).mkdir(exist_ok=True)
        # An interrupted process may have admitted a request without recording
        # its response. Preserve the reservation and explicitly mark uncertainty.
        for path in (job_dir / "calls").glob("*.json"):
            call = read_json(path)
            if call.get("status") == "started":
                call.update(
                    status="uncertain",
                    error_type="interrupted_request",
                    error="Request outcome is unknown; automatic replay is disabled",
                )
                write_json(path, call)
                self.event("call_recovered_uncertain", call_id=call["call_id"])

    @property
    def elapsed_seconds(self) -> float:
        """Return cumulative active execution time across explicit resumes."""
        return self._elapsed_before + time.monotonic() - self._started

    def event(self, kind: str, **details: object) -> None:
        """Append a credential-redacted execution event to the durable job log."""
        event(self.job_dir, kind, **redact(details, self._secrets))

    def checkpoint(self, name: str, payload: dict[str, Any]) -> None:
        """Atomically persist a named JSON checkpoint after credential redaction."""
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", name):
            raise ValueError("Invalid checkpoint name")
        write_json(self.job_dir / "checkpoints" / f"{name}.json", redact(payload, self._secrets))

    def load_checkpoint(self, name: str) -> dict[str, Any] | None:
        """Read a named JSON checkpoint without changing its state."""
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", name):
            raise ValueError("Invalid checkpoint name")
        path = self.job_dir / "checkpoints" / f"{name}.json"
        return read_json(path) if path.exists() else None

    def reserve_final(self, calls: int, output_tokens: int, cost: float = 0.0) -> None:
        """Hold call, output-token, and cost capacity for the frozen final comparison."""
        with self._mutex:
            self._headroom_calls = calls
            self._headroom_tokens = output_tokens
            self._headroom_cost = cost

    def release_final(self) -> None:
        """Release final-comparison reservations after the candidate is frozen."""
        self.reserve_final(0, 0)

    def check_stop(self) -> None:
        """Raise when cancellation, uncertainty, or the active-time budget prevents progress."""
        if (self.job_dir / "cancel.request").exists():
            raise ExperimentStopped("cancelled")
        if self._halt:
            raise ExperimentStopped(self._halt)
        if self.elapsed_seconds >= self.spec["budget"]["max_seconds"]:
            raise ExperimentStopped("time_budget")

    def ledger(self) -> list[dict[str, Any]]:
        """Read all committed call-attempt receipts for this job."""
        return [read_json(path) for path in sorted((self.job_dir / "calls").glob("*.json"))]

    def budget_state(self) -> dict[str, Any]:
        """Summarize charged calls, token reservations, known costs, and active time."""
        return ledger_budget(
            self.ledger(),
            self.spec["budget"],
            elapsed_seconds=self.elapsed_seconds,
            concurrency=self.spec["max_concurrency"],
        )

    def _admit(
        self, config: dict[str, Any], prompt: str, *, phase: str, label: str
    ) -> tuple[Path, dict[str, Any], bool]:
        """Reserve a call atomically or reuse its receipt unless an explicit safe retry applies."""
        key = _digest({"config": config, "prompt": prompt, "phase": phase, "label": label})
        path = self.job_dir / "calls" / f"{key}.json"
        with self._mutex:
            if path.exists():
                prior = read_json(path)
                attempts = sorted((self.job_dir / "calls").glob(f"{key}-r*.json"))
                if attempts:
                    path = attempts[-1]
                    prior = read_json(path)
                if not self._should_retry(prior):
                    return path, prior, False
                path = self.job_dir / "calls" / f"{key}-r{self._execution_attempt:06d}.json"
            self.check_stop()
            budget = self.spec["budget"]
            usage = self.budget_state()
            tokens = config.get("max_output_tokens", 256)
            if usage["calls"] + 1 + self._headroom_calls > budget["max_calls"]:
                raise ExperimentStopped("call_budget")
            if (
                usage["charged_output_tokens"] + tokens + self._headroom_tokens
                > budget["max_output_tokens"]
            ):
                raise ExperimentStopped("output_token_budget")
            rates_known = all(
                budget.get(key) is not None
                for key in ("input_cost_per_million", "output_cost_per_million")
            )
            # Byte-bound input reservation plus protocol overhead. Any provider
            # usage exceeding this bound is recorded and stops further calls.
            input_bound = len(prompt.encode("utf-8")) + 4096
            reserved_cost = (
                (
                    input_bound * budget["input_cost_per_million"]
                    + tokens * budget["output_cost_per_million"]
                )
                / 1_000_000
                if rates_known
                else None
            )
            if budget.get("max_cost") is not None:
                if reserved_cost is None:
                    raise ExperimentStopped("cost_unknown")
                if (
                    usage["reserved_cost"] + reserved_cost + self._headroom_cost
                    > budget["max_cost"]
                ):
                    raise ExperimentStopped("cost_budget")
            record = {
                "call_id": path.stem,
                "request_key": key,
                "execution_attempt": self._execution_attempt,
                "phase": phase,
                "label": label,
                "status": "started",
                "started_at": time.time(),
                "provider": config["provider"],
                "model": config["model"],
                "prompt_hash": _digest(prompt),
                "config_hash": _digest(config),
                "reserved_output_tokens": tokens,
                "input_token_reservation": input_bound,
                "reserved_cost": reserved_cost,
                "usage": {"input_tokens": None, "output_tokens": None},
                "actual_cost": None,
                "output": None,
            }
            write_json(path, record)
            self.event("call_started", call_id=key, phase=phase, label=label)
            return path, record, True

    def _should_retry(self, record: dict[str, Any]) -> bool:
        return (
            self.retry_failed
            and record.get("status") == "service_error"
            and record.get("retry_safe") is True
            and int(record.get("execution_attempt", 1)) < self._execution_attempt
        )

    def _invoke(self, kwargs: dict[str, Any], timeout: float) -> object:
        mailbox: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)
        with self._mutex:
            self._pending += 1

        def transport() -> None:
            try:
                mailbox.put((True, self._provider(**kwargs)))
            except BaseException as exc:
                mailbox.put((False, exc))
            finally:
                with self._mutex:
                    self._pending -= 1
                    if self._closed and self._pending == 0 and self._lease:
                        self._lease.release()

        threading.Thread(target=transport, daemon=True, name="pcl-experiment-call").start()
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Request deadline reached; outcome unknown, replay disabled")
            try:
                success, result = mailbox.get(timeout=min(0.05, remaining))
            except queue.Empty:
                if (self.job_dir / "cancel.request").exists():
                    raise ExperimentStopped("cancelled_in_flight") from None
                continue
            if not success:
                raise result
            return result

    def call(
        self, config: dict[str, Any], prompt: str, *, phase: str, label: str
    ) -> dict[str, Any]:
        """Execute one guarded provider call and persist its known or uncertain outcome."""
        path, record, admitted = self._admit(config, prompt, phase=phase, label=label)
        if not admitted:
            return record
        start = time.monotonic()
        timeout = max(
            0.001,
            min(
                config.get("timeout", 30.0),
                self.spec["budget"]["max_seconds"] - self.elapsed_seconds,
            ),
        )
        kwargs: dict[str, Any] = {
            key: config[key]
            for key in (
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
            )
            if key in config
        }
        kwargs.update(prompt=prompt, timeout=timeout)
        try:
            response = self._invoke(kwargs, timeout)
            if hasattr(response, "to_json"):
                response = response.to_json()
            if isinstance(response, str):
                response = {"output_text": response}
            if not isinstance(response, dict):
                raise ValueError("Provider response is not an object")
            output = response.get("output_text", response.get("output"))
            if not isinstance(output, str):
                raise ValueError("Provider response has no text output")
            if response.get("error") or response.get("status") in {
                "error",
                "failed",
                "service_error",
            }:
                raise ValueError("Provider response reports a service error")
            usage = _usage(response.get("usage"))
            record.update(
                status="completed",
                output=output,
                usage=usage,
                observed_model=response.get("model_id", response.get("model", config["model"])),
                request_id=response.get("request_id"),
                provenance_evidence=response.get("provenance_evidence", []),
            )
            for key in ("request_sha256", "response_sha256", "warnings"):
                if key in response:
                    record[key] = response[key]
            output_count = usage["output_tokens"]
            record["charged_output_tokens"] = (
                output_count if output_count is not None else record["reserved_output_tokens"]
            )
            budget = self.spec["budget"]
            if all(usage[key] is not None for key in ("input_tokens", "output_tokens")) and all(
                budget.get(key) is not None
                for key in ("input_cost_per_million", "output_cost_per_million")
            ):
                cost = (
                    usage["input_tokens"] * budget["input_cost_per_million"]
                    + usage["output_tokens"] * budget["output_cost_per_million"]
                ) / 1_000_000
                record.update(actual_cost=cost, charged_cost=cost)
            if (output_count is not None and output_count > record["reserved_output_tokens"]) or (
                usage["input_tokens"] is not None
                and usage["input_tokens"] > record["input_token_reservation"]
            ):
                record["budget_warning"] = "Provider reported usage above the reserved upper bound"
                self._halt = "provider_budget_violation"
        except Exception as exc:
            detail = str(exc)
            lowered = detail.lower()
            uncertain = isinstance(exc, (TimeoutError, OSError, ExperimentStopped)) or any(
                text in lowered
                for text in (
                    "timed out",
                    "timeout",
                    "deadline",
                    "connection reset",
                    "could not reach",
                    "connection aborted",
                )
            )
            rejected = re.search(
                r"\bHTTP(?:\s+Error)?\s+(400|401|403|404|413|415|422|429)\b", detail
            )
            local_rejection = any(
                message in lowered
                for message in (
                    "requires api credentials",
                    "requires a base url",
                    "explicit model id is required",
                )
            )
            if rejected is not None or local_rejection:
                uncertain = False
            retry_safe = not uncertain and (rejected is not None or local_rejection)
            error_type = (
                "cancelled_in_flight"
                if isinstance(exc, ExperimentStopped)
                else "timeout"
                if uncertain
                else "rate_limited"
                if "429" in detail or "rate limit" in lowered
                else "response_error"
                if isinstance(exc, ValueError)
                else "provider_error"
            )
            record.update(
                status="uncertain" if uncertain else "service_error",
                error_type=error_type,
                error=detail[:500],
                output=None,
                retry_safe=retry_safe,
            )
            if uncertain:
                self._halt = (
                    "cancelled" if isinstance(exc, ExperimentStopped) else "uncertain_request"
                )
        record.update(
            finished_at=time.time(), latency_ms=round((time.monotonic() - start) * 1000, 3)
        )
        record = cast(dict[str, Any], redact(record, self._secrets))
        with self._mutex:
            write_json(path, record)
            self.event(
                "call_finished",
                call_id=record["call_id"],
                status=record["status"],
                phase=phase,
                label=label,
                error_type=record.get("error_type"),
            )
        return record

    def evaluate(
        self, name: str, config: dict[str, Any], tasks: list[dict[str, Any]], phase: str
    ) -> list[dict[str, Any]]:
        """Evaluate immutable tasks within their permitted phase and reuse verified completions."""
        if phase == "withheld" and not (self.job_dir / "checkpoints" / "selection.json").exists():
            raise ValueError("Withheld evaluation requires a frozen selection")
        allowed_ids = (
            set(self.split.get(phase, []))
            if self.spec["operation"] == "optimize"
            else {task["id"] for task in self.tasks}
        )
        canonical = {task["id"]: task for task in self.tasks}
        if any(
            task.get("id") not in allowed_ids or task != canonical.get(task.get("id"))
            for task in tasks
        ):
            raise ValueError(
                "Evaluation tasks must match the immutable snapshot and permitted phase"
            )

        def one(task: dict[str, Any]) -> dict[str, Any]:
            """Score a task after verifying any reusable completion against its call receipt."""
            key = _digest({"name": name, "config": config, "task": task["id"], "phase": phase})
            target = self.job_dir / "records" / f"{key}.json"
            if target.exists():
                prior_record = read_json(target)
                if prior_record.get("status") == "completed":
                    validate_completed_record(
                        prior_record,
                        task,
                        config,
                        metric=self.spec["metric"],
                        phase=phase,
                        name=name,
                        job_dir=self.job_dir,
                    )
                if not self._should_retry(prior_record):
                    return prior_record
            prompt = render_task_prompt(config, task)
            call = self.call(config, prompt, phase=phase, label=f"{name}:{task['id']}")
            score = (
                score_output(call["output"], task["expected"], self.spec["metric"])
                if call["status"] == "completed"
                else None
            )
            result = {
                "id": task["id"],
                "name": name,
                "phase": phase,
                "output": call.get("output"),
                "expected": task["expected"],
                "slice": task["slice"],
                "score": score,
                "status": call["status"],
                "output_status": output_quality(call["output"], self.spec["metric"])
                if call["status"] == "completed"
                else "unavailable",
                "error_type": call.get("error_type"),
                "error": call.get("error"),
                "call_id": call["call_id"],
                "usage": call["usage"],
                "latency_ms": call.get("latency_ms"),
                "observed_model": call.get("observed_model"),
                "actual_cost": call.get("actual_cost"),
                "retry_safe": call.get("retry_safe", False),
                "execution_attempt": call.get("execution_attempt", 1),
            }
            write_json(target, result)
            self.event(
                "record_completed", id=task["id"], name=name, phase=phase, status=result["status"]
            )
            return result

        records = []
        limit = self.spec["max_concurrency"]
        with ThreadPoolExecutor(max_workers=limit) as executor:
            for offset in range(0, len(tasks), limit):
                futures = [executor.submit(one, task) for task in tasks[offset : offset + limit]]
                failure = None
                for future in futures:
                    try:
                        records.append(future.result())
                    except ExperimentStopped as exc:
                        failure = exc
                if failure:
                    raise failure
        return records

    def close(self) -> None:
        """Release the job lease once every outstanding transport has exited."""
        with self._mutex:
            self._closed = True
            if self._pending == 0 and self._lease:
                self._lease.release()
