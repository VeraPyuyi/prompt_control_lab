"""Persistent experiment behavior against deterministic, offline providers."""

from __future__ import annotations

import json
import threading
import time
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.request import Request

import pytest

from promptcontrollab.evaluation.experiments import (
    cancel_experiment,
    create_experiment,
    export_experiment,
    get_experiment,
    list_experiments,
    make_experiment_split,
    prepare_resume,
    run_experiment,
)
from promptcontrollab.evaluation.experiments.models import ExperimentSpec
from promptcontrollab.evaluation.experiments.storage import job_directory, write_json


def spec(count: int = 6) -> dict[str, Any]:
    return {
        "schema_version": "experiment/v1",
        "operation": "run",
        "data": [
            {"id": str(index), "input": f"item {index}", "expected": "yes"}
            for index in range(count)
        ],
        "baseline": {
            "provider": "openai",
            "model": "test",
            "prompt": "baseline",
            "max_output_tokens": 10,
        },
        "candidate": {
            "provider": "openai",
            "model": "test",
            "prompt": "candidate",
            "max_output_tokens": 10,
        },
        "metric": "exact_match",
        "budget": {"max_calls": 100, "max_output_tokens": 1000, "max_seconds": 30},
    }


def provider(**kwargs: object) -> dict[str, Any]:
    return {
        "output_text": "yes" if str(kwargs["prompt"]).startswith("candidate") else "no",
        "model_id": "test",
        "usage": {"input_tokens": 2, "output_tokens": 1},
    }


def test_complete_paired_run_and_portable_export(tmp_path: Path) -> None:
    created = create_experiment(tmp_path, spec())
    job = run_experiment(tmp_path, created["id"], provider)
    assert job["status"] == "completed"
    assert job["assessment"]["coverage"]["matched"] == 6
    assert job["assessment"]["effect"]["statistics"]["mean_delta"] == 1
    assert job["assessment"]["comparability"]["scope"] == "evaluation"
    assert job["assessment"]["cost"]["status"] == "unknown"
    assert job["budget"]["calls"] == 12
    assert len(job["artifacts"]) == 5
    assert list_experiments(tmp_path)[0]["id"] == job["id"]
    assert run_experiment(tmp_path, job["id"], lambda **_: pytest.fail("already completed")) == job
    archive = export_experiment(tmp_path, job["id"])
    with zipfile.ZipFile(archive) as zipped:
        assert any(name.endswith("report.en.html") for name in zipped.namelist())
        assert all(
            name.startswith(job["id"] + "/") and ".." not in name for name in zipped.namelist()
        )
        assert not any(name.endswith("experiment.zip") for name in zipped.namelist())


def test_import_keeps_quality_zero_separate_from_missing_and_errors(tmp_path: Path) -> None:
    value = spec(3)
    value.update(
        operation="import",
        predictions={
            "baseline": [{"id": "0", "output": "no"}, {"id": "1", "error": "service unavailable"}],
            "candidate": [
                {"id": "0", "output": "yes"},
                {"id": "1", "output": "yes"},
                {"id": "2", "output": ""},
            ],
        },
    )
    job = run_experiment(
        tmp_path,
        create_experiment(tmp_path, value)["id"],
        lambda **_: pytest.fail("import must not call a provider"),
    )
    assert job["status"] == "completed_with_errors"
    assert job["progress"]["stage"] == "evaluation"
    assessment = job["assessment"]
    assert assessment["coverage"]["matched"] == 1
    assert assessment["effect"]["statistics"]["mean_delta"] == 1
    records = json.loads(
        (job_directory(tmp_path, job["id"]) / "report" / "records.json").read_text()
    )
    assert records["baseline"][0]["score"] == 0
    assert records["baseline"][1]["score"] is None
    assert records["baseline"][2]["status"] == "missing"
    assert records["candidate"][2]["score"] == 0
    assert records["candidate"][2]["output_status"] == "empty_output"
    report = (job_directory(tmp_path, job["id"]) / "report" / "report.en.html").read_text(
        encoding="utf-8"
    )
    assert "<td>0.0</td>" in report


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value["data"].append(value["data"][0]),
        lambda value: value["baseline"].update(api_key="secret"),
        lambda value: value["baseline"].update(base_url="https://user:secret@example.com"),
        lambda value: value.update(max_concurrency=3),
        lambda value: value["budget"].update(max_seconds=float("nan")),
    ],
)
def test_invalid_specs_rejected_before_creation(
    tmp_path: Path, mutation: Callable[[dict[str, Any]], None]
) -> None:
    value = spec()
    mutation(value)
    with pytest.raises((ValueError, TypeError)):
        create_experiment(tmp_path, value)
    assert list_experiments(tmp_path) == []


def test_duplicate_import_ids_rejected(tmp_path: Path) -> None:
    value = spec(1)
    value.update(
        operation="import",
        predictions={"baseline": [{"id": "0", "output": "yes"}] * 2, "candidate": []},
    )
    with pytest.raises(ValueError, match="duplicate"):
        create_experiment(tmp_path, value)


def test_safe_job_ids_and_immutable_snapshot(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Invalid experiment ID"):
        get_experiment(tmp_path, "../../outside")
    job = create_experiment(tmp_path, spec())
    directory = job_directory(tmp_path, job["id"])
    value = json.loads((directory / "spec.json").read_text())
    value["baseline"]["prompt"] = "tampered"
    (directory / "spec.json").write_text(json.dumps(value))
    with pytest.raises(ValueError, match="snapshot"):
        run_experiment(tmp_path, job["id"], provider)


def test_call_and_unknown_output_budgets_are_upper_bounded(tmp_path: Path) -> None:
    value = spec(4)
    value["budget"].update(max_calls=3, max_output_tokens=20)
    seen = []

    def without_usage(**kwargs: Any) -> str:
        seen.append(kwargs)
        return "yes"

    job = run_experiment(tmp_path, create_experiment(tmp_path, value)["id"], without_usage)
    assert job["status"] == "stopped"
    assert job["stop_reason"] == "output_token_budget"
    assert len(seen) == 2
    assert job["budget"]["charged_output_tokens"] == 20
    assert not job["budget"]["output_usage_complete"]


def test_cost_limit_without_prices_fails_closed(tmp_path: Path) -> None:
    value = spec()
    value["budget"]["max_cost"] = 1
    job = run_experiment(
        tmp_path, create_experiment(tmp_path, value)["id"], lambda **_: pytest.fail("unknown cost")
    )
    assert job["stop_reason"] == "cost_unknown"
    assert job["budget"]["calls"] == 0


def test_explicit_resume_reuses_completed_records(tmp_path: Path) -> None:
    value = spec(3)
    value["max_concurrency"] = 1
    created = create_experiment(tmp_path, value)
    calls = []

    def cancelling(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs["prompt"])
        if len(calls) == 2:
            cancel_experiment(tmp_path, created["id"])
        return provider(**kwargs)

    stopped = run_experiment(tmp_path, created["id"], cancelling)
    assert stopped["status"] == "cancelled"
    with pytest.raises(ValueError, match="prepare_resume"):
        run_experiment(tmp_path, created["id"], provider)
    prepare_resume(tmp_path, created["id"])

    def resumed_provider(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs["prompt"])
        return provider(**kwargs)

    resumed = run_experiment(tmp_path, created["id"], resumed_provider)
    assert resumed["status"] == "completed"
    assert len(calls) == 6
    assert len(set(calls)) == 6
    assert resumed["attempt"] == 2


def test_timeout_is_uncertain_and_never_replayed(tmp_path: Path) -> None:
    value = spec(1)
    value["max_concurrency"] = 1
    value["baseline"]["timeout"] = 0.03
    count = 0
    exited = threading.Event()

    def slow(**kwargs: Any) -> str:
        nonlocal count
        count += 1
        time.sleep(1)
        exited.set()
        return "yes"

    created = create_experiment(tmp_path, value)
    started = time.monotonic()
    stopped = run_experiment(tmp_path, created["id"], slow)
    assert time.monotonic() - started < 0.8
    assert stopped["stop_reason"] == "uncertain_request"
    with pytest.raises(RuntimeError, match="active request"):
        prepare_resume(tmp_path, created["id"])
    assert exited.wait(2)
    # The transport's finally block releases the lease just after the event.
    time.sleep(0.02)
    prepare_resume(tmp_path, created["id"], retry_failed=True)
    resumed = run_experiment(tmp_path, created["id"], provider)
    assert count == 1
    assert resumed["assessment"]["coverage"]["baseline_completed"] == 0
    calls = [
        json.loads(path.read_text())
        for path in (job_directory(tmp_path, created["id"]) / "calls").glob("*.json")
    ]
    assert sum(row["status"] == "uncertain" for row in calls) == 1


def test_concurrency_and_single_active_job(tmp_path: Path) -> None:
    mutex = threading.Lock()
    release = threading.Event()
    entered = threading.Event()
    current = peak = 0

    def blocking(**kwargs: Any) -> dict[str, Any]:
        nonlocal current, peak
        with mutex:
            current += 1
            peak = max(peak, current)
            if current == 2:
                entered.set()
        assert release.wait(5)
        with mutex:
            current -= 1
        return provider(**kwargs)

    first = create_experiment(tmp_path, spec(2))
    second = create_experiment(tmp_path, spec(1))
    thread = threading.Thread(target=run_experiment, args=(tmp_path, first["id"], blocking))
    thread.start()
    assert entered.wait(5)
    live = get_experiment(tmp_path, first["id"])
    assert live["budget"]["calls"] == 2
    assert live["budget"]["charged_output_tokens"] == 20
    assert live["progress"]["stage"] == "evaluation"
    assert live["progress"]["expected_total"] == 4
    assert live["progress"]["completed"] == 0
    assert live["progress"]["in_flight"] == 2
    assert live["progress"]["by_phase"]["evaluation"]["calls"] == 2
    live_receipts = (job_directory(tmp_path, first["id"]) / "calls").glob("*.json")
    assert all(json.loads(path.read_text())["status"] == "started" for path in live_receipts)
    with pytest.raises(RuntimeError, match="already active"):
        run_experiment(tmp_path, second["id"], provider)
    release.set()
    thread.join(5)
    assert not thread.is_alive()
    assert peak == 2
    assert get_experiment(tmp_path, first["id"])["status"] == "completed"


def test_group_text_and_sample_split_are_disjoint() -> None:
    value = spec(10)
    value["operation"] = "optimize"
    value["data"][0]["input"] = " SAME  text "
    value["data"][1]["input"] = "same text"
    value["data"][1]["meta"] = {"group": "g"}
    value["data"][2]["meta"] = {"group_id": "g"}
    value["data"][3]["meta"] = {"sample_id": "s"}
    value["data"][4]["meta"] = {"sample_id": "s"}
    validated = ExperimentSpec.from_json(value).to_json()
    split = make_experiment_split(validated)
    location = {item: phase for phase in ("train", "val", "withheld") for item in split[phase]}
    assert location["0"] == location["1"] == location["2"]
    assert location["3"] == location["4"]
    assert split == make_experiment_split(validated)
    assert all(split[phase] for phase in ("train", "val", "withheld"))


def test_provider_failures_do_not_become_zero_scores(tmp_path: Path) -> None:
    def limited(**kwargs: Any) -> dict[str, Any]:
        if str(kwargs["prompt"]).endswith("item 1"):
            raise RuntimeError("HTTP 429 rate limit")
        return provider(**kwargs)

    job = run_experiment(tmp_path, create_experiment(tmp_path, spec(3))["id"], limited)
    assert job["assessment"]["coverage"]["matched"] == 2
    assert job["assessment"]["effect"]["statistics"]["mean_delta"] == 1
    assert job["assessment"]["coverage"]["baseline_statuses"]["service_error"] == 1


def test_credentials_redacted_from_records_and_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "test-private-token-not-for-persistence"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    job = run_experiment(
        tmp_path,
        create_experiment(tmp_path, spec(1))["id"],
        lambda **_: {"output_text": secret, "request_id": secret},
    )
    archive = export_experiment(tmp_path, job["id"])
    with zipfile.ZipFile(archive) as zipped:
        for name in zipped.namelist():
            assert secret.encode() not in zipped.read(name)


def test_explicit_failed_retry_keeps_success_and_attempt_ledger(tmp_path: Path) -> None:
    value = spec(1)
    value["max_concurrency"] = 1
    created = create_experiment(tmp_path, value)
    attempts: list[str] = []

    def first_provider(**kwargs: Any) -> dict[str, Any]:
        attempts.append(kwargs["prompt"])
        if kwargs["prompt"].startswith("baseline"):
            raise RuntimeError("HTTP 429 rate limit")
        return provider(**kwargs)

    first = run_experiment(tmp_path, created["id"], first_provider)
    assert first["status"] == "completed_with_errors"
    prepare_resume(tmp_path, created["id"])
    unchanged = run_experiment(
        tmp_path, created["id"], lambda **_: pytest.fail("default resume must not retry failures")
    )
    assert unchanged["status"] == "completed_with_errors"
    prepare_resume(tmp_path, created["id"], retry_failed=True)

    def retry_provider(**kwargs: Any) -> dict[str, Any]:
        attempts.append(kwargs["prompt"])
        return provider(**kwargs)

    final = run_experiment(tmp_path, created["id"], retry_provider)
    assert final["status"] == "completed"
    assert len(attempts) == 3
    assert final["budget"]["calls"] == 3
    ledger = [
        json.loads(path.read_text())
        for path in (job_directory(tmp_path, created["id"]) / "calls").glob("*.json")
    ]
    assert len(ledger) == 3
    assert sum(row["status"] == "service_error" for row in ledger) == 1
    assert any(row["call_id"].endswith("-r000003") for row in ledger)


def test_malformed_response_is_never_retried(tmp_path: Path) -> None:
    value = spec(1)
    created = create_experiment(tmp_path, value)
    first = run_experiment(tmp_path, created["id"], lambda **_: {"usage": {}})
    assert first["status"] == "completed_with_errors"
    prepare_resume(tmp_path, created["id"], retry_failed=True)
    final = run_experiment(
        tmp_path,
        created["id"],
        lambda **_: pytest.fail("unknown completed response must not replay"),
    )
    assert final["budget"]["calls"] == 2


def test_grouped_rows_do_not_claim_iid_significance(tmp_path: Path) -> None:
    value = spec(10)
    for task in value["data"]:
        task["meta"] = {"group_id": "same-document"}
    job = run_experiment(tmp_path, create_experiment(tmp_path, value)["id"], provider)
    effect = job["assessment"]["effect"]
    assert effect["status"] == "uncertain"
    assert effect["statistics"]["mean_delta"] == 1
    assert effect["statistics"]["bootstrap_ci"] is None
    assert effect["statistics"]["permutation_p_value"] is None
    assert effect["statistics"]["inference_status"] == "descriptive_only_nonindependent_rows"


def test_known_prices_and_zero_call_unknown_price_status(tmp_path: Path) -> None:
    value = spec(1)
    value["budget"].update(input_cost_per_million=2, output_cost_per_million=3)
    job = run_experiment(tmp_path, create_experiment(tmp_path, value)["id"], provider)
    assert job["assessment"]["cost"]["status"] == "known"
    assert job["assessment"]["cost"]["known_cost"] == pytest.approx(0.000014)
    cancelled = cancel_experiment(tmp_path, create_experiment(tmp_path, spec(1))["id"])
    assert cancelled["assessment"]["cost"]["status"] == "unknown"
    assert len(cancelled["artifacts"]) == 5


def test_numeric_parse_error_is_an_observed_quality_zero(tmp_path: Path) -> None:
    value = spec(1)
    value["metric"] = "numeric_tolerance:0.1"
    value["data"][0]["expected"] = "42"
    job = run_experiment(
        tmp_path, create_experiment(tmp_path, value)["id"], lambda **_: "no number"
    )
    rows = json.loads((job_directory(tmp_path, job["id"]) / "report" / "records.json").read_text())
    assert rows["baseline"][0]["status"] == "completed"
    assert rows["baseline"][0]["score"] == 0
    assert rows["baseline"][0]["output_status"] == "parse_error"


def test_interrupted_admission_is_recovered_without_replay(tmp_path: Path) -> None:
    value = spec(1)
    value["max_concurrency"] = 1
    created = create_experiment(tmp_path, value)

    def interrupted(**kwargs: Any) -> str:
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        run_experiment(tmp_path, created["id"], interrupted)
    prepare_resume(tmp_path, created["id"], retry_failed=True)
    attempted: list[str] = []

    def remaining(**kwargs: Any) -> dict[str, Any]:
        attempted.append(kwargs["prompt"])
        return provider(**kwargs)

    final = run_experiment(tmp_path, created["id"], remaining)
    assert final["status"] == "completed_with_errors"
    assert len(attempted) == 1
    assert attempted[0].startswith("candidate")
    assert final["budget"]["calls"] == 2


def test_atomic_json_write_keeps_windows_temporary_path_short(tmp_path: Path) -> None:
    parent = tmp_path / ("nested-" + "x" * max(1, 165 - len(str(tmp_path))))
    target = parent / ("a" * 64 + "-r000002.json")
    # The final path fits legacy Windows limits; a filename containing both
    # this hash and a second full UUID would exceed them.
    assert len(str(target)) < 260
    write_json(target, {"status": "completed"})
    assert json.loads(target.read_text()) == {"status": "completed"}
    assert list(parent.glob("*.tmp")) == []


def test_explicit_rejected_reflection_retry_with_real_gepa(tmp_path: Path) -> None:
    pytest.importorskip("gepa")
    value = spec(10)
    value.update(operation="optimize", synthetic=True, max_concurrency=1)
    value["optimization"] = {"max_rounds": 1, "patience": 1}
    created = create_experiment(tmp_path, value)
    reflection_calls = 0
    completed_prompts: list[str] = []

    def reflective(**kwargs: Any) -> dict[str, Any]:
        nonlocal reflection_calls
        prompt = kwargs["prompt"]
        if "Training examples and feedback:" in prompt:
            reflection_calls += 1
            if reflection_calls == 1:
                raise RuntimeError("HTTP 429 rate limit")
            return {
                "output_text": "```\ncandidate\n```",
                "usage": {"input_tokens": 2, "output_tokens": 2},
            }
        completed_prompts.append(prompt)
        return provider(**kwargs)

    first = run_experiment(tmp_path, created["id"], reflective)
    assert first["status"] == "failed"
    assert first["assessment"]["coverage"]["matched"] == 0
    assert reflection_calls == 1
    prepare_resume(tmp_path, created["id"], retry_failed=True)
    final = run_experiment(tmp_path, created["id"], reflective)
    assert final["status"] == "completed", final.get("error", final.get("stop_reason"))
    assert reflection_calls == 2
    assert final["optimization"]["validation_improved"] is True
    assert final["assessment"]["coverage"]["matched"] == 2


@pytest.mark.parametrize("scheme", [None, "api_key", "bearer"])
def test_anthropic_explicit_auth_scheme_and_secret_free_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scheme: str | None
) -> None:
    from promptcontrollab.integrations import providers

    secret = "private-anthropic-auth-token-for-test"
    monkeypatch.setenv("EXPERIMENT_ANTHROPIC_TOKEN", secret)
    requests: list[Request] = []

    def transport(request: Request, timeout: float) -> tuple[bytes, dict[str, str]]:
        requests.append(request)
        if scheme == "bearer":
            assert request.get_header("Authorization") == f"Bearer {secret}"
            assert request.get_header("X-api-key") is None
        else:
            assert request.get_header("X-api-key") == secret
            assert request.get_header("Authorization") is None
        return json.dumps(
            {
                "model": "test",
                "content": [{"type": "text", "text": secret}],
                "usage": {"input_tokens": 2, "output_tokens": 1},
            }
        ).encode(), {}

    monkeypatch.setattr(providers, "_perform_request", transport)
    value = spec(1)
    for arm in ("baseline", "candidate"):
        value[arm].update(
            provider="anthropic",
            base_url="https://relay.example.test",
            api_key_env="EXPERIMENT_ANTHROPIC_TOKEN",
            temperature=0.2,
            top_p=0.8,
        )
        if scheme is not None:
            value[arm]["auth_scheme"] = scheme
    job = run_experiment(tmp_path, create_experiment(tmp_path, value)["id"])
    assert job["status"] == "completed"
    assert len(requests) == 2
    request_data = requests[0].data
    assert isinstance(request_data, bytes)
    payload = json.loads(request_data)
    assert payload["temperature"] == 0.2 and payload["top_p"] == 0.8
    with zipfile.ZipFile(export_experiment(tmp_path, job["id"])) as zipped:
        for name in zipped.namelist():
            assert secret.encode() not in zipped.read(name)


def test_auth_scheme_rejected_for_unsupported_provider(tmp_path: Path) -> None:
    value = spec(1)
    value["baseline"]["auth_scheme"] = "bearer"
    with pytest.raises(ValueError, match="only for Anthropic"):
        create_experiment(tmp_path, value)
    from promptcontrollab.integrations.providers import (
        ProviderError,
        _build_request,
        _provider_spec,
    )

    with pytest.raises(ProviderError, match="only for Anthropic"):
        _build_request(
            _provider_spec("openai"),
            model="test",
            prompt="hi",
            base_url="https://example.test",
            api_key="local-test-only",
            max_output_tokens=10,
            auth_scheme="api_key",
        )


def test_numeric_overflow_never_matches_or_counts_as_parse_success(tmp_path: Path) -> None:
    from promptcontrollab.evaluation.metrics import score_output

    assert score_output("9" * 500, "8" * 500, "numeric_tolerance:0") == 0
    value = spec(1)
    value["metric"] = "numeric_tolerance:0"
    value["data"][0]["expected"] = "42"
    job = run_experiment(tmp_path, create_experiment(tmp_path, value)["id"], lambda **_: "9" * 500)
    rows = json.loads((job_directory(tmp_path, job["id"]) / "report" / "records.json").read_text())
    assert rows["baseline"][0]["score"] == 0
    assert rows["baseline"][0]["output_status"] == "parse_error"


@pytest.mark.parametrize("bad_score", [True, float("nan"), float("inf"), float("-inf"), 2])
def test_invalid_completed_scores_excluded_before_statistics(bad_score: object) -> None:
    from promptcontrollab.evaluation.experiments.assessment import assess

    value = ExperimentSpec.from_json(spec(1)).to_json()
    result = assess(
        value,
        [{"id": "0", "score": bad_score, "status": "completed"}],
        [{"id": "0", "score": 1.0, "status": "completed"}],
        expected_ids=["0"],
        scope="evaluation",
        budget={},
    )
    assert result["coverage"]["matched"] == 0
    assert result["effect"]["statistics"] is None
    assert result["comparability"]["status"] == "invalid_records"
    json.dumps(result, allow_nan=False)


def test_out_of_scope_and_duplicate_scores_do_not_complete_coverage() -> None:
    from promptcontrollab.evaluation.experiments.assessment import assess

    value = ExperimentSpec.from_json(spec(1)).to_json()
    wrong = {"id": "wrong", "score": 1.0, "status": "completed"}
    result = assess(value, [wrong], [wrong], expected_ids=["0"], scope="evaluation", budget={})
    assert result["coverage"]["status"] == "none"
    right = {"id": "0", "score": 1.0, "status": "completed"}
    result = assess(
        value, [right, right], [right], expected_ids=["0"], scope="evaluation", budget={}
    )
    assert result["coverage"]["matched"] == 0
    assert result["coverage"]["invalid_records"][0]["reason"] == "duplicate_id"


def test_missing_group_bridges_preserve_dependency() -> None:
    from promptcontrollab.evaluation.experiments.assessment import assess

    value = spec(11)
    for index in range(6):
        value["data"][index]["meta"] = {"group": f"g{index}"}
    for index in range(5):
        value["data"][index + 6]["meta"] = {"group": f"g{index}", "group_id": f"g{index + 1}"}
    value = ExperimentSpec.from_json(value).to_json()
    baseline = [{"id": str(index), "score": 0.0, "status": "completed"} for index in range(6)]
    candidate = [{"id": str(index), "score": 1.0, "status": "completed"} for index in range(6)]
    result = assess(
        value,
        baseline,
        candidate,
        expected_ids=[str(index) for index in range(11)],
        scope="evaluation",
        budget={},
    )
    assert result["effect"]["status"] == "uncertain"
    assert result["effect"]["statistics"]["permutation_p_value"] is None
    assert (
        result["effect"]["statistics"]["inference_status"] == "descriptive_only_nonindependent_rows"
    )


def test_optimization_template_bound_and_native_model_metadata_import(tmp_path: Path) -> None:
    value = spec(6)
    value["operation"] = "optimize"
    value["baseline"]["prompt"] = "{input} {input}"
    with pytest.raises(ValueError, match="at most one"):
        create_experiment(tmp_path, value)
    value = spec(1)
    row = {"id": "0", "output": "yes", "model": {"provider": "openai", "model_id": "test"}}
    value.update(operation="import", predictions={"baseline": [row], "candidate": [row]})
    job = run_experiment(tmp_path, create_experiment(tmp_path, value)["id"])
    assert job["status"] == "completed"
    assert job["assessment"]["coverage"]["matched"] == 1


def test_corrupted_cached_completion_is_not_reused_or_scored(tmp_path: Path) -> None:
    value = spec(2)
    value["max_concurrency"] = 1
    created = create_experiment(tmp_path, value)

    def stop_after_one(**kwargs: Any) -> dict[str, Any]:
        cancel_experiment(tmp_path, created["id"])
        return provider(**kwargs)

    assert run_experiment(tmp_path, created["id"], stop_after_one)["status"] == "cancelled"
    record_path = next((job_directory(tmp_path, created["id"]) / "records").glob("*.json"))
    record = json.loads(record_path.read_text())
    assert record["status"] == "completed"
    record["score"] = float("nan")
    record_path.write_text(json.dumps(record))
    prepare_resume(tmp_path, created["id"])
    job = run_experiment(
        tmp_path, created["id"], lambda **_: pytest.fail("corruption must stop reuse")
    )
    assert job["status"] == "failed"
    assert job["assessment"]["coverage"]["matched"] == 0
    assert job["assessment"]["comparability"]["status"] == "invalid_records"
    assert "immutable task or score" in job["error"]
