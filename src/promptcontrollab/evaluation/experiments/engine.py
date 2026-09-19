"""Persistent experiment creation, evaluation, import, cancellation and resume."""

from __future__ import annotations

import copy
import random
import time
import unicodedata
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from promptcontrollab.evaluation.metrics import score_output

from .assessment import assess
from .models import ExperimentSpec, model_config
from .reporting import write_reports
from .runtime import (
    ExperimentRuntime,
    ExperimentStopped,
    ledger_budget,
    output_quality,
    validate_completed_record,
)
from .storage import (
    JobLock,
    active_job,
    configured_secrets,
    event,
    experiments_dir,
    job_directory,
    read_json,
    redact,
    snapshot_hash,
    write_json,
)


def _text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def make_experiment_split(spec: dict[str, Any]) -> dict[str, Any]:
    """Assign connected sample/text/group components to disjoint partitions."""
    tasks = spec["data"]
    if spec["operation"] != "optimize":
        return {
            "scope": "evaluation_only",
            "evaluation": [task["id"] for task in tasks],
            "seed": spec["seed"],
            "leakage": {"status": "not_applicable"},
        }
    parents = list(range(len(tasks)))

    def find(index: int) -> int:
        while index != parents[index]:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    seen: dict[tuple[str, str], int] = {}
    for index, task in enumerate(tasks):
        tokens = [("text", _text(task["input"]))]
        meta = task.get("meta", {})
        for key in ("group", "group_id", "sample_id", "source_id", "document_id"):
            if meta.get(key) is not None:
                tokens.append(("group" if key in {"group", "group_id"} else key, str(meta[key])))
        for token in tokens:
            if token in seen:
                parents[find(index)] = find(seen[token])
            seen[token] = index
    components: dict[int, list[str]] = {}
    for index, task in enumerate(tasks):
        components.setdefault(find(index), []).append(task["id"])
    groups = sorted((sorted(ids) for ids in components.values()), key=lambda ids: ids[0])
    if len(groups) < 3:
        raise ValueError(
            "Optimization needs at least three independent input/group components "
            "for train, validation and withheld"
        )
    random.Random(spec["seed"]).shuffle(groups)
    train_count = max(1, min(len(groups) - 2, round(len(groups) * spec["split"]["train_ratio"])))
    val_count = max(
        1, min(len(groups) - train_count - 1, round(len(groups) * spec["split"]["val_ratio"]))
    )
    split = {
        name: sorted(item for group in batch for item in group)
        for name, batch in (
            ("train", groups[:train_count]),
            ("val", groups[train_count : train_count + val_count]),
            ("withheld", groups[train_count + val_count :]),
        )
    }
    return {
        **split,
        "scope": "optimization_trisplit",
        "seed": spec["seed"],
        "component_count": len(groups),
        "counts": {name: len(ids) for name, ids in split.items()},
        "split_hash": snapshot_hash(split),
        "leakage": {
            "status": "checked",
            "id_overlap": [],
            "normalized_input_overlap": [],
            "group_overlap": [],
            "group_fields": ["group", "group_id", "sample_id", "source_id", "document_id"],
        },
    }


def create_experiment(root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    """Validate and freeze a self-contained experiment snapshot in a new queued job."""
    validated = ExperimentSpec.from_json(spec).to_json()
    validated = redact(validated, configured_secrets(validated))
    split = make_experiment_split(validated)
    job_id = "exp-" + time.strftime("%Y%m%d-%H%M%S", time.gmtime()) + "-" + uuid.uuid4().hex[:12]
    directory = job_directory(root, job_id)
    directory.mkdir(parents=True, exist_ok=False)
    now = time.time()
    job = {
        "schema_version": "experiment-job/v1",
        "id": job_id,
        "name": validated.get("name", job_id),
        "operation": validated["operation"],
        "status": "queued",
        "created_at": now,
        "updated_at": now,
        "snapshot_hash": snapshot_hash(validated),
        "elapsed_seconds": 0.0,
        "attempt": 0,
        "scope": split["scope"],
        "artifacts": [],
        "assessment": None,
        "budget": None,
        "synthetic": validated.get("synthetic", False),
    }
    write_json(directory / "spec.json", validated)
    write_json(directory / "data.json", {"records": validated["data"]})
    write_json(directory / "split.json", split)
    write_json(directory / "job.json", job)
    write_json(
        directory / "manifest.json",
        {
            "schema_version": "experiment-manifest/v1",
            "id": job_id,
            "snapshot_hash": job["snapshot_hash"],
            "data_hash": snapshot_hash({"records": validated["data"]}),
            "split_hash": snapshot_hash(split),
            "credentials": "environment-variable names only",
            "replay_policy": (
                "reuse durable completed records; never automatically replay admitted requests"
            ),
        },
    )
    event(
        directory,
        "experiment_created",
        operation=validated["operation"],
        snapshot_hash=job["snapshot_hash"],
    )
    return job


def get_experiment(root: Path, job_id: str) -> dict[str, Any]:
    """Read job state and project live progress without modifying provider receipts."""
    directory = job_directory(root, job_id)
    job = read_json(directory / "job.json")
    if job["id"] != job_id:
        raise ValueError("Experiment identity mismatch")
    if job["status"] in {"running", "cancelling"}:
        spec = read_json(directory / "spec.json")
        split = read_json(directory / "split.json")
        calls = [read_json(path) for path in (directory / "calls").glob("*.json")]
        records = [read_json(path) for path in (directory / "records").glob("*.json")]
        elapsed = float(job["elapsed_seconds"]) + max(
            0, time.time() - job.get("active_started_at", time.time())
        )
        job["budget"] = ledger_budget(
            calls, spec["budget"], elapsed_seconds=elapsed, concurrency=spec["max_concurrency"]
        )
        job["progress"] = _progress(spec, split, calls, records)
    return job


def _progress(
    spec: dict[str, Any],
    split: dict[str, Any],
    calls: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    final_phase = "withheld" if spec["operation"] == "optimize" else "evaluation"
    final_records = [row for row in records if row.get("phase") == final_phase]
    stage = (
        max(calls, key=lambda row: row.get("started_at", 0)).get("phase")
        if calls
        else "evaluation"
        if records
        else "preparing"
    )
    phases = set(row.get("phase", "unknown") for row in calls + records) | {final_phase}
    by_phase = {}
    for phase in phases:
        rows = [row for row in records if row.get("phase") == phase]
        phase_calls = [row for row in calls if row.get("phase") == phase]
        by_phase[phase] = {
            "expected_total": 2 * len(split[final_phase]) if phase == final_phase else None,
            "completed": sum(row.get("status") == "completed" for row in rows),
            "errors": sum(row.get("status") != "completed" for row in rows),
            "calls": len(phase_calls),
            "in_flight": sum(row.get("status") == "started" for row in phase_calls),
        }
    return {
        "stage": stage,
        "expected_total": 2 * len(split[final_phase]),
        "completed": sum(row.get("status") == "completed" for row in final_records),
        "errors": sum(row.get("status") != "completed" for row in final_records),
        "in_flight": sum(row.get("status") == "started" for row in calls),
        "completed_calls": sum(row.get("status") == "completed" for row in calls),
        "by_phase": by_phase,
    }


def list_experiments(root: Path) -> list[dict[str, Any]]:
    """List persisted experiment jobs in reverse creation order."""
    parent = experiments_dir(root)
    if not parent.exists():
        return []
    jobs = []
    for path in parent.iterdir():
        if path.is_dir() and not path.is_symlink() and (path / "job.json").is_file():
            jobs.append(get_experiment(root, path.name))
    return sorted(jobs, key=lambda row: row["created_at"], reverse=True)


def cancel_experiment(root: Path, job_id: str) -> dict[str, Any]:
    """Request cancellation and finalize reports immediately for an unstarted job."""
    directory = job_directory(root, job_id)
    job = get_experiment(root, job_id)
    if job["status"] not in {"queued", "running", "cancelling"}:
        return job
    (directory / "cancel.request").touch(exist_ok=True)
    job.update(
        status="cancelling" if job["status"] in {"running", "cancelling"} else "cancelled",
        updated_at=time.time(),
        stop_reason="cancelled",
    )
    write_json(directory / "job.json", job)
    event(directory, "cancel_requested")
    if job["status"] == "cancelled":
        spec = read_json(directory / "spec.json")
        split = read_json(directory / "split.json")
        phase = "withheld" if spec["operation"] == "optimize" else "evaluation"
        budget = {
            "calls": 0,
            "charged_output_tokens": 0,
            "known_output_tokens": 0,
            "output_usage_complete": True,
            "known_cost": 0.0,
            "unknown_cost_calls": 0,
            "reserved_cost": 0.0,
            "elapsed_seconds": job["elapsed_seconds"],
            "limits": spec["budget"],
            "concurrency_limit": spec["max_concurrency"],
        }
        job["budget"] = budget
        job["assessment"] = assess(
            spec, [], [], expected_ids=split[phase], scope=phase, budget=budget
        )
        job["artifacts"] = write_reports(directory, job, [], [])
        job["finished_at"] = time.time()
        write_json(directory / "job.json", job)
    return job


def prepare_resume(root: Path, job_id: str, *, retry_failed: bool = False) -> dict[str, Any]:
    """Queue an explicit resume while preserving successes and uncertain request outcomes."""
    if not isinstance(retry_failed, bool):
        raise ValueError("retry_failed must be a boolean")
    directory = job_directory(root, job_id)
    job = get_experiment(root, job_id)
    active = active_job(root)
    if active and active.get("id") == job_id:
        raise RuntimeError("Experiment still has an active request; wait for its transport to exit")
    if job["status"] == "completed":
        raise ValueError("A completed experiment does not need resume")
    spec = read_json(directory / "spec.json")
    if snapshot_hash(spec) != job["snapshot_hash"]:
        raise ValueError("Immutable experiment snapshot was modified")
    if job["status"] in {"running", "cancelling"} and job.get("active_started_at"):
        job["elapsed_seconds"] = min(
            spec["budget"]["max_seconds"],
            job["elapsed_seconds"] + max(0, time.time() - job["active_started_at"]),
        )
    (directory / "cancel.request").unlink(missing_ok=True)
    job.update(
        status="queued",
        updated_at=time.time(),
        stop_reason=None,
        resume_prepared=True,
        retry_failed=retry_failed,
    )
    write_json(directory / "job.json", job)
    event(
        directory,
        "resume_prepared",
        retry_failed=retry_failed,
        replay_policy="retry_known_rejected_only" if retry_failed else "reuse_only",
    )
    return job


class _OptimizationView:
    """Provide search code train/validation data and no withheld task content."""

    def __init__(self, runtime: ExperimentRuntime):
        self._runtime = runtime
        allowed = set(runtime.split["train"]) | set(runtime.split["val"])
        self.tasks = [copy.deepcopy(task) for task in runtime.tasks if task["id"] in allowed]
        self.spec = copy.deepcopy(runtime.spec)
        self.spec["data"] = copy.deepcopy(self.tasks)
        self.split = {key: copy.deepcopy(runtime.split[key]) for key in ("train", "val")}
        self.job_dir = runtime.job_dir
        self.retry_failed = runtime.retry_failed

    def evaluate(
        self, name: str, config: dict[str, Any], tasks: list[dict[str, Any]], phase: str
    ) -> list[dict[str, Any]]:
        if phase not in {"train", "val"}:
            raise ValueError("Optimizer evaluation is restricted to train and validation")
        return self._runtime.evaluate(name, config, tasks, phase)

    def call(
        self, config: dict[str, Any], prompt: str, *, phase: str, label: str
    ) -> dict[str, Any]:
        if phase != "reflection":
            raise ValueError("Optimizer direct calls must be reflection calls")
        return self._runtime.call(config, prompt, phase=phase, label=label)

    def checkpoint(self, name: str, payload: dict[str, Any]) -> None:
        if name == "selection":
            raise ValueError("Only the experiment engine may freeze the withheld selection")
        self._runtime.checkpoint(name, payload)

    def __getattr__(self, name: str) -> Any:
        if name in {"event", "load_checkpoint", "check_stop", "budget_state"}:
            return getattr(self._runtime, name)
        raise AttributeError(name)


def _imported_conditions(source: dict[str, Any]) -> dict[str, Any]:
    """Preserve declared import metadata and project known comparison conditions."""
    model_metadata = copy.deepcopy(source.get("model_metadata", {}))
    if not isinstance(model_metadata, dict):
        model_metadata = {}
    supplied_model = source.get("model_id", source.get("model"))
    if isinstance(supplied_model, dict):
        model_metadata.update(copy.deepcopy(supplied_model))
        supplied_model = supplied_model.get("model_id", supplied_model.get("model"))
    if not isinstance(supplied_model, str):
        supplied_model = model_metadata.get("model_id", model_metadata.get("model"))
    observed_model = supplied_model if isinstance(supplied_model, str) else None
    decoding: dict[str, Any] = {}
    settings: dict[str, Any] = {}
    decode_fields = {"temperature", "top_p", "seed", "max_output_tokens", "stop", "thinking"}
    for container in (model_metadata, source):
        for field in ("decoding", "decoding_metadata", "generation_config"):
            if isinstance(container.get(field), dict):
                decoding.update(copy.deepcopy(container[field]))
        for key in decode_fields | {"max_tokens", "max_completion_tokens"}:
            if key in container:
                decoding[key] = copy.deepcopy(container[key])
        for key in ("provider", "base_url"):
            if isinstance(container.get(key), str) and container[key]:
                settings[key] = container[key]
    for alias in ("max_tokens", "max_completion_tokens"):
        if decoding.get(alias) is not None:
            settings["max_output_tokens"] = decoding[alias]
    for key in decode_fields:
        if decoding.get(key) is not None:
            settings[key] = decoding[key]
    if observed_model:
        settings["model"] = observed_model
    return {
        "observed_model": observed_model,
        "observed_provider": settings.get("provider"),
        "model_metadata": model_metadata,
        "decoding_metadata": decoding,
        "observed_settings": settings,
    }


def _import_records(directory: Path, spec: dict[str, Any], arm: str) -> list[dict[str, Any]]:
    """Normalize imported outputs and keep missing records distinct from observed quality errors."""
    imported = {row["id"]: row for row in spec["predictions"][arm]}
    records = []
    for task in spec["data"]:
        source = imported.get(task["id"])
        status = "missing" if source is None else "completed"
        output = source.get("output", source.get("output_text")) if source else None
        if source and (
            source.get("error")
            or source.get("status")
            in {
                "failed",
                "error",
                "service_error",
                "uncertain",
                "timeout",
                "rate_limited",
                "missing",
            }
        ):
            status = "missing" if source.get("status") == "missing" else "service_error"
        if status == "completed" and not isinstance(output, str):
            status = "missing"
        output_text = output if isinstance(output, str) else ""
        score = (
            score_output(output_text, task["expected"], spec["metric"])
            if status == "completed"
            else None
        )
        row = {
            "id": task["id"],
            "name": arm,
            "phase": "evaluation",
            "output": output,
            "expected": task["expected"],
            "slice": task["slice"],
            "score": score,
            "status": status,
            "output_status": output_quality(output_text, spec["metric"])
            if status == "completed"
            else "unavailable",
            "error_type": source.get("error_type", "imported_error")
            if source and status == "service_error"
            else None,
            "error": source.get("error") if source else None,
            "usage": source.get("usage", {}) if source else {},
            "latency_ms": source.get("latency_ms") if source else None,
            "actual_cost": source.get("actual_cost") if source else None,
            "provenance": "imported",
            **_imported_conditions(source or {}),
        }
        write_json(
            directory
            / "records"
            / f"{snapshot_hash({'arm': arm, 'id': task['id']}).removeprefix('sha256:')}.json",
            row,
        )
        records.append(row)
    return records


def _phase_records(
    directory: Path, phase: str, arm: str, config: dict[str, Any]
) -> list[dict[str, Any]]:
    rows = [read_json(path) for path in (directory / "records").glob("*.json")]
    spec = read_json(directory / "spec.json")
    tasks = {task["id"]: task for task in spec["data"]}
    for row in rows:
        if row.get("phase") != phase or row.get("name") != arm or row.get("status") != "completed":
            continue
        try:
            validate_completed_record(
                row,
                tasks[row["id"]],
                config,
                metric=spec["metric"],
                phase=phase,
                name=arm,
                job_dir=directory,
                imported=spec["operation"] == "import",
            )
        except (ValueError, KeyError, FileNotFoundError) as exc:
            row.update(
                status="invalid_record",
                score=None,
                error_type="record_integrity_error",
                error=str(exc),
            )
    return sorted(
        (row for row in rows if row.get("phase") == phase and row.get("name") == arm),
        key=lambda row: row["id"],
    )


def run_experiment(
    root: Path, job_id: str, provider_call: Callable[..., Any] | None = None
) -> dict[str, Any]:
    """Execute a queued job under shared budgets and persist its assessment and reports."""
    directory = job_directory(root, job_id)
    job = get_experiment(root, job_id)
    if job["status"] == "completed":
        return job
    if job["status"] != "queued":
        raise ValueError(
            "Explicit prepare_resume is required before continuing a stopped experiment"
        )
    spec = read_json(directory / "spec.json")
    if snapshot_hash(spec) != job["snapshot_hash"]:
        raise ValueError("Immutable experiment snapshot was modified")
    manifest = read_json(directory / "manifest.json")
    split = read_json(directory / "split.json")
    if (
        snapshot_hash(split) != manifest["split_hash"]
        or snapshot_hash(read_json(directory / "data.json")) != manifest["data_hash"]
    ):
        raise ValueError("Immutable data or split snapshot was modified")
    lease = JobLock(root, job_id)
    runtime = None
    try:
        # Recheck after acquiring the global lease to close queued/cancel races.
        job = get_experiment(root, job_id)
        if job["status"] != "queued":
            raise ValueError("Experiment is no longer queued")
        job.update(
            status="running",
            attempt=job.get("attempt", 0) + 1,
            updated_at=time.time(),
            active_started_at=time.time(),
        )
        write_json(directory / "job.json", job)
        runtime = ExperimentRuntime(directory, spec, split, provider_call, lease)
        runtime.event("experiment_started", attempt=job["attempt"])
        phase = "withheld" if spec["operation"] == "optimize" else "evaluation"
        expected_ids = split["withheld"] if spec["operation"] == "optimize" else split["evaluation"]
        selected = spec["candidate"]
        try:
            runtime.check_stop()
            if spec["operation"] == "import":
                _import_records(directory, spec, "baseline")
                _import_records(directory, spec, "candidate")
            elif spec["operation"] == "run":
                runtime.evaluate("baseline", spec["baseline"], runtime.tasks, "evaluation")
                runtime.evaluate("candidate", selected, runtime.tasks, "evaluation")
            else:
                selection = runtime.load_checkpoint("selection")
                if selection:
                    selected = selection["candidate"]
                    if snapshot_hash(selected) != selection["candidate_hash"]:
                        raise ValueError("Frozen candidate snapshot was modified")
                    job["optimization"] = selection["optimization"]
                else:
                    count = len(split["withheld"])
                    final_tokens = count * (
                        spec["baseline"]["max_output_tokens"] + selected["max_output_tokens"]
                    )
                    final_cost = 0.0
                    budget = spec["budget"]
                    if all(
                        budget.get(key) is not None
                        for key in ("input_cost_per_million", "output_cost_per_million")
                    ):
                        withheld_input_bytes = sum(
                            len(task["input"].encode("utf-8"))
                            for task in runtime.tasks
                            if task["id"] in split["withheld"]
                        )
                        # Optimizer prompts are capped at 100,000 Unicode characters.
                        input_bound = 2 * withheld_input_bytes + count * (
                            len(spec["baseline"]["prompt"].encode("utf-8")) + 400_000 + 2 * 4100
                        )
                        final_cost = (
                            input_bound * budget["input_cost_per_million"]
                            + final_tokens * budget["output_cost_per_million"]
                        ) / 1_000_000
                    runtime.reserve_final(2 * count, final_tokens, final_cost)
                    from .optimization import optimize

                    result = optimize(cast(ExperimentRuntime, _OptimizationView(runtime)))
                    job["optimization"] = result
                    if result.get("search_status") in {"failed", "cancelled"}:
                        raise ExperimentStopped(
                            "cancelled"
                            if result["search_status"] == "cancelled"
                            else "optimization_failed"
                        )
                    selected = model_config(result["candidate"], "selected_candidate")
                    if {key: value for key, value in selected.items() if key != "prompt"} != {
                        key: value for key, value in spec["baseline"].items() if key != "prompt"
                    }:
                        raise ValueError(
                            "Optimization changed model settings; only prompt updates are permitted"
                        )
                    selection = {
                        "candidate": selected,
                        "candidate_hash": snapshot_hash(selected),
                        "optimization": result,
                        "frozen_at": time.time(),
                        "withheld_opened": False,
                    }
                    runtime.checkpoint("selection", selection)
                    runtime.event("candidate_frozen", candidate_hash=selection["candidate_hash"])
                runtime.release_final()
                runtime.check_stop()
                withheld = [task for task in runtime.tasks if task["id"] in set(split["withheld"])]
                runtime.event("withheld_opened", candidate_hash=snapshot_hash(selected))
                runtime.evaluate("baseline", spec["baseline"], withheld, "withheld")
                runtime.evaluate("candidate", selected, withheld, "withheld")
            runtime.check_stop()
            job.update(status="completed", stop_reason=None)
        except ExperimentStopped as exc:
            status = "cancelled" if "cancel" in exc.reason else "stopped"
            if exc.reason == "optimization_failed":
                status = "failed"
            job.update(status=status, stop_reason=exc.reason)
        except Exception as exc:
            job.update(
                status="failed",
                stop_reason="execution_error",
                error=str(redact(str(exc), configured_secrets(spec)))[:500],
            )
            runtime.event("execution_error", error=str(exc), error_type=type(exc).__name__)
        baseline = _phase_records(directory, phase, "baseline", spec["baseline"])
        candidate = _phase_records(directory, phase, "candidate", selected)
        job["budget"] = runtime.budget_state()
        all_records = [read_json(path) for path in (directory / "records").glob("*.json")]
        job["progress"] = _progress(
            spec,
            split,
            runtime.ledger(),
            [row for row in all_records if row.get("phase") != phase] + baseline + candidate,
        )
        job["assessment"] = assess(
            spec,
            baseline,
            candidate,
            expected_ids=expected_ids,
            scope=phase,
            budget=job["budget"],
            selected_config=selected,
        )
        if job["status"] == "completed" and job["assessment"]["coverage"]["status"] != "complete":
            job.update(status="completed_with_errors", stop_reason="incomplete_coverage")
        job.update(
            updated_at=time.time(), finished_at=time.time(), elapsed_seconds=runtime.elapsed_seconds
        )
        runtime.event(
            "experiment_finished", status=job["status"], stop_reason=job.get("stop_reason")
        )
        job["artifacts"] = write_reports(directory, job, baseline, candidate)
        write_json(directory / "job.json", job)
        return job
    finally:
        if runtime:
            runtime.close()
        else:
            lease.release()
