"""Local-session streaming imports and persistent research API integration."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from promptcontrollab.integrations.web_api import create_app


def test_import_run_events_report_export_and_local_guard(tmp_path: Path) -> None:
    source = Path(__file__).parents[1] / "examples/research-tools/readout.json"
    with TestClient(create_app(runs_dir=tmp_path), base_url="http://127.0.0.1") as client:
        assert (
            client.post(
                "/api/research-bundles?filename=evidence.json", content=source.read_bytes()
            ).status_code
            == 403
        )
        token = client.get("/api/session").json()["token"]
        headers = {"x-pcl-session": token}
        imported = client.post(
            "/api/research-bundles?filename=evidence.json",
            headers=headers,
            content=source.read_bytes(),
        )
        assert imported.status_code == 201, imported.text
        bundle = imported.json()
        created = client.post(
            "/api/research-jobs", headers=headers, json={"bundle_id": bundle["id"]}
        )
        assert created.status_code == 201, created.text
        identifier = created.json()["id"]
        for _ in range(150):
            job = client.get(f"/api/research-jobs/{identifier}").json()
            if job["status"] in {"completed", "failed"}:
                break
            time.sleep(0.1)
        assert job["status"] == "completed", job
        events = client.get(f"/api/research-jobs/{identifier}/events")
        assert "unit_completed" in events.text
        report = client.get(f"/api/research-jobs/{identifier}/artifacts/report.zh.html")
        assert "研究证据报告" in report.text
        assert "sandbox" in report.headers["content-security-policy"]
        assert (
            client.get(f"/api/research-jobs/{identifier}/artifacts/research.zip").content[:2]
            == b"PK"
        )
        assert client.get(f"/api/research-jobs/{identifier}/artifacts/job.json").status_code == 404
        assert len(client.get("/api/research-jobs").json()["jobs"]) == 1


def test_upload_bounds_and_path_validation(tmp_path: Path) -> None:
    with TestClient(create_app(runs_dir=tmp_path), base_url="http://127.0.0.1") as client:
        headers = {"x-pcl-session": client.get("/api/session").json()["token"]}
        assert (
            client.post(
                "/api/research-bundles?filename=../bad.json", headers=headers, content=b"{}"
            ).status_code
            == 422
        )
        assert client.post("/api/research-jobs", headers=headers, json=[]).status_code == 422
        assert (
            client.post(
                "/api/research-bundles?filename=script.py", headers=headers, content=b"print(1)"
            ).status_code
            == 422
        )
        assert client.get("/api/research-bundles/missing").status_code == 422
        assert (
            client.post(
                "/api/research-bundles?filename=broken.zip", headers=headers, content=b"invalid"
            ).status_code
            == 422
        )
