"""API security, input boundaries, and native/external import fidelity."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from promptcontrollab.evaluation.experiments import create_experiment, run_experiment
from promptcontrollab.evaluation.experiments.storage import JobLock, active_job, job_directory
from promptcontrollab.integrations.experiment_imports import normalize_import_document
from promptcontrollab.integrations.experiment_inputs import parse_dataset
from promptcontrollab.integrations.web_api import create_app


def _spec() -> dict[str, Any]:
    source = Path(__file__).parents[1] / "examples/experiments/synthetic-import.json"
    return cast(dict[str, Any], json.loads(source.read_text(encoding="utf-8")))


def _headers(client: TestClient) -> dict[str, str]:
    return {"x-pcl-session": client.get("/api/session").json()["token"]}


def test_host_guard_covers_legacy_reads_and_writes(tmp_path: Path) -> None:
    with TestClient(create_app(runs_dir=tmp_path), base_url="http://attacker.example") as client:
        assert client.get("/api/session").status_code == 403
        assert client.get("/api/runs").status_code == 403
        assert client.post("/api/checkpoint-runs", json={}).status_code == 403


def test_session_and_origin_guard_covers_legacy_mutation(tmp_path: Path) -> None:
    with TestClient(create_app(runs_dir=tmp_path), base_url="http://127.0.0.1") as client:
        payload = {
            "name": "secure",
            "csv_text": "seed,stage,checkpoint_id,mean_score\n0,initial,a,0.1\n0,final,b,0.2\n",
        }
        assert client.post("/api/checkpoint-runs", json=payload).status_code == 403
        headers = _headers(client)
        assert (
            client.post(
                "/api/checkpoint-runs",
                json=payload,
                headers={**headers, "origin": "http://attacker.example"},
            ).status_code
            == 403
        )
        assert not (tmp_path / "secure").exists()
        assert client.post("/api/checkpoint-runs", json=payload, headers=headers).status_code == 201


def test_public_demo_stays_read_only_without_loopback_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PCL_DEPLOYMENT_MODE", "hf_demo")
    with TestClient(create_app(runs_dir=tmp_path), base_url="https://example.hf.space") as client:
        assert client.get("/api/runs").status_code == 200
        assert client.get("/api/session").json()["enabled"] is False
        assert client.post("/api/checkpoint-runs", json={}).status_code == 403
        assert client.post("/api/credentials", json={"key": "example"}).status_code == 403


@pytest.mark.parametrize("path", ["/api/experiments/parse-data", "/api/checkpoint-runs"])
def test_chunked_body_is_rejected_before_consuming_the_whole_stream(
    tmp_path: Path, path: str
) -> None:
    import asyncio

    app = create_app(runs_dir=tmp_path)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        token = _headers(client)["x-pcl-session"]
    received = 0
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        nonlocal received
        received += 1
        return {"type": "http.request", "body": b"x" * 1_000_000, "more_body": received < 20}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "server": ("127.0.0.1", 80),
        "client": ("127.0.0.1", 1234),
        "headers": [(b"host", b"127.0.0.1"), (b"x-pcl-session", token.encode())],
    }
    asyncio.run(app(scope, receive, send))
    assert (
        next(message["status"] for message in sent if message["type"] == "http.response.start")
        == 413
    )
    assert received <= 7


def test_native_json_and_csv_exports_reimport_an_explicit_arm(tmp_path: Path) -> None:
    spec = _spec()
    job = run_experiment(tmp_path, create_experiment(tmp_path, spec)["id"])
    directory = job_directory(tmp_path, job["id"]) / "report"
    for format in ("json", "csv"):
        payload = {
            "format": format,
            "text": (directory / f"records.{format}").read_text(encoding="utf-8-sig"),
        }
        with pytest.raises(ValueError, match="arm"):
            normalize_import_document(payload, tmp_path / "imports")
        normalized = normalize_import_document(
            {**payload, "arm": "candidate"}, tmp_path / "imports"
        )
        assert normalized["kind"] == "predictions"
        assert [row["output"] for row in normalized["predictions"]] == [
            row["output"] for row in spec["predictions"]["candidate"]
        ]
        assert len({row["id"] for row in normalized["predictions"]}) == 4


def test_deepeval_quality_feedback_is_not_a_service_failure(tmp_path: Path) -> None:
    examples = Path(__file__).parents[1] / "examples/external"
    arms = {
        arm: normalize_import_document(
            {"format": "json", "text": (examples / f"deepeval_{arm}.json").read_text()},
            tmp_path / "imports",
        )
        for arm in ("baseline", "candidate")
    }
    assert all(not row.get("error") for arm in arms.values() for row in arm["predictions"])
    assert arms["baseline"]["predictions"][0]["feedback"] == "wrong answer"
    spec = _spec()
    spec["data"] = [
        {"id": row["id"], "input": row["id"], "expected": row["expected"]}
        for row in arms["baseline"]["predictions"]
    ]
    spec["predictions"] = {arm: data["predictions"] for arm, data in arms.items()}
    job = run_experiment(tmp_path, create_experiment(tmp_path, spec)["id"])
    assert job["assessment"]["coverage"]["matched"] == 4
    assert job["status"] == "completed"


def test_deepeval_explicit_transport_failure_is_preserved(tmp_path: Path) -> None:
    source = Path(__file__).parents[1] / "examples/external/deepeval_baseline.json"
    payload = json.loads(source.read_text())
    payload["test_cases"][0]["error"] = "provider request failed"
    result = normalize_import_document({"format": "json", "text": json.dumps(payload)}, tmp_path)
    assert result["predictions"][0]["error"] == "provider request failed"


def test_large_valid_csv_field_is_within_the_file_limit() -> None:
    text = "id,input,expected\nx," + "a" * 150_000 + ",yes\n"
    assert len(parse_dataset(text, "csv")[0]["input"]) == 150_000


def test_csv_and_format_failures_are_actionable_422(tmp_path: Path) -> None:
    with TestClient(create_app(runs_dir=tmp_path), base_url="http://127.0.0.1") as client:
        for path in ("parse-data", "normalize-import"):
            for payload in (
                {"format": "csv", "text": 'id,input,expected\nx,"unterminated,yes'},
                {"format": "unknown", "text": "[]"},
            ):
                response = client.post(
                    "/api/experiments/" + path, json=payload, headers=_headers(client)
                )
                assert response.status_code == 422


def test_external_lease_failure_never_leaves_a_finished_worker_queued(tmp_path: Path) -> None:
    lease = JobLock(tmp_path, "external-owner")
    app = create_app(runs_dir=tmp_path)
    try:
        with TestClient(app, base_url="http://127.0.0.1") as client:
            created = client.post("/api/experiments", json=_spec(), headers=_headers(client)).json()
            app.state.experiment_pool.submit(lambda: None).result(timeout=5)
            job = client.get("/api/experiments/" + created["id"]).json()
            assert job["status"] in {"stopped", "failed"}
            assert job["stop_reason"]
            active = active_job(tmp_path)
            assert active is not None
            assert active["id"] == "external-owner"
    finally:
        lease.release()


def test_resume_requires_explicit_boolean_retry_option(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from promptcontrollab.evaluation import experiments

    job = create_experiment(tmp_path, _spec())
    retries: list[bool] = []

    def prepare(root: Path, job_id: str, *, retry_failed: bool = False) -> dict[str, Any]:
        retries.append(retry_failed)
        return job

    monkeypatch.setattr(experiments, "prepare_resume", prepare)
    monkeypatch.setattr(experiments, "run_experiment", lambda *args: job)
    with TestClient(create_app(runs_dir=tmp_path), base_url="http://127.0.0.1") as client:
        path = f"/api/experiments/{job['id']}/resume"
        headers = _headers(client)
        assert client.post(path, json={}, headers=headers).status_code == 200
        assert client.post(path, json={"retry_failed": True}, headers=headers).status_code == 200
        for invalid in ("false", 1, None):
            assert (
                client.post(path, json={"retry_failed": invalid}, headers=headers).status_code
                == 422
            )
        assert retries == [False, True]


def test_error_responses_redact_session_keys_and_exports_use_allowlist(tmp_path: Path) -> None:
    job = run_experiment(tmp_path, create_experiment(tmp_path, _spec())["id"])
    with TestClient(create_app(runs_dir=tmp_path), base_url="http://127.0.0.1") as client:
        headers = _headers(client)
        secret = "synthetic-private-key-for-redaction"
        credential = client.post("/api/credentials", json={"key": secret}, headers=headers)
        assert credential.status_code == 200
        assert secret not in credential.text
        rows = [{"id": secret, "input": "a", "expected": "b"}] * 2
        response = client.post(
            "/api/experiments/parse-data",
            json={"format": "json", "text": json.dumps(rows)},
            headers=headers,
        )
        assert response.status_code == 422
        assert secret not in response.text
        assert "[redacted]" in response.text
        prefix = f"/api/experiments/{job['id']}/artifacts/"
        artifact = client.get(prefix + "records.json")
        assert artifact.status_code == 200
        assert "attachment" in artifact.headers["content-disposition"]
        assert client.get(prefix + "job.json").status_code == 404
