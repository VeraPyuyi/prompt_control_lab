from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from promptcontrollab.integrations.web_api import create_app


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_web_api_exposes_normalized_change_review_and_diagnostics(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    run = runs / "change-review"
    _write_json(
        run / "change_review.json",
        {
            "change_kind": "prompt_change",
            "decision": "needs_review",
            "reasons": ["The candidate changed a second recorded factor."],
            "next_action": "Resolve the confounder.",
            "claim_boundary": "Association, not unique causation.",
            "coverage": {"baseline_metrics": True, "candidate_metrics": True},
            "observations": {
                "baseline_score": 1.0,
                "candidate_score": 1.0,
                "metric_deltas": {
                    "mean_total_tokens": {
                        "baseline": 1200.0,
                        "candidate": 900.0,
                        "delta": -300.0,
                        "direction": "decrease",
                    }
                },
            },
        },
    )
    _write_json(run / "comparison_validity.json", {"validity": "needs_review"})
    _write_json(run / "stability.json", {"state": "stalled"})
    _write_json(
        run / "diagnostics" / "green_certificate.json",
        {
            "certificate_level": "insufficient_evidence",
            "check_state": "conditions_not_met",
            "explanation": "Recorded boundary conditions were not met.",
            "claim_boundary": "This does not establish non-existence.",
            "next_action": "Inspect the boundary matrices.",
        },
    )

    client = TestClient(create_app(runs_dir=runs, language="zh"), base_url="http://127.0.0.1")
    overview = client.get("/api/overview", params={"run": "change-review"})
    catalog = client.get(
        "/api/diagnostics/catalog",
        params={"run": "change-review", "language": "zh"},
    )

    assert overview.status_code == 200
    assert overview.json()["change_review"]["decision"] == "needs_review"
    assert overview.json()["conclusion"] == "needs_review"
    assert overview.json()["change_kind"] == "prompt_change"
    assert overview.json()["risk"] == "medium"
    assert overview.json()["likely_causes"] == ["The candidate changed a second recorded factor."]
    assert overview.json()["ui_language"] == "zh"
    assert overview.json()["next_action"].startswith("先解决")
    assert any("完整运行 Token" in item for item in overview.json()["observations"])
    assert overview.json()["comparison_validity"]["validity"] == "needs_review"
    assert catalog.status_code == 200
    assert catalog.json()["terminal_sensitivity"]["label"] == "最终目标影响"
    assert catalog.json()["green_certificate"]["label"] == "局部稳定边界"
    assert catalog.json()["green_certificate"]["meaning"] == (
        "Recorded boundary conditions were not met."
    )
    assert catalog.json()["green_certificate"]["next_action"] == ("Inspect the boundary matrices.")
    assert catalog.json()["posterior_certificate"]["label"] == "局部解可信范围"


def test_diagnostic_catalog_tracks_the_selected_run(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    for name, decay_rate in (("agent-case", 0.12), ("model-case", 0.73)):
        _write_json(
            runs / name / "change_review.json",
            {"change_kind": "prompt_change", "decision": "needs_review"},
        )
        _write_json(
            runs / name / "diagnostics" / "terminal_sensitivity.json",
            {
                "certificate_level": "empirical_only",
                "check_state": "passed",
                "decay_rate": decay_rate,
                "r_squared": 0.9,
            },
        )

    client = TestClient(create_app(runs_dir=runs, language="en"), base_url="http://127.0.0.1")
    response = client.get(
        "/api/diagnostics/catalog",
        params={"run": "model-case", "language": "en"},
    )

    assert response.status_code == 200
    assert response.json()["terminal_sensitivity"]["metrics"]["decay_rate"] == 0.73


def test_web_api_lists_child_runs_and_rejects_path_escape(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _write_json(runs / "safe-run" / "manifest.json", {"mode": "quick"})
    _write_json(tmp_path / "outside" / "manifest.json", {"secret": True})
    client = TestClient(create_app(runs_dir=runs), base_url="http://127.0.0.1")

    response = client.get("/api/runs")
    history = client.get("/api/history")
    health = client.get("/api/health")
    overview = client.get("/api/overview", params={"run": "safe-run"})
    escaped = client.get("/api/runs/%2E%2E%5Coutside")

    assert response.status_code == 200
    assert [row["name"] for row in response.json()["runs"]] == ["safe-run"]
    assert [row["run_name"] for row in history.json()["runs"]] == ["safe-run"]
    assert "path" not in response.json()["runs"][0]
    assert "path" not in history.json()["runs"][0]
    assert "runs_dir" not in health.json()
    assert "runs_dir" not in overview.json()
    assert "path" not in overview.json()["run"]
    assert escaped.status_code in {400, 404}


def test_web_api_discovers_featured_cases_with_nested_reviews(tmp_path: Path) -> None:
    runs = tmp_path / "cases"
    case = runs / "model_change_review"
    _write_json(
        case / "case_manifest.json",
        {
            "schema": "prompt_control_lab.model_change_review_case.v1",
            "decision": "needs_review",
            "display": {
                "featured": True,
                "order": 2,
                "category": "model",
                "evidence_level": "historical_aggregate",
                "review_path": "review",
                "title": {"en": "Model change review", "zh": "模型切换审查"},
                "summary": {
                    "en": "Compare two recorded model aggregates.",
                    "zh": "比较两个已记录的模型汇总。",
                },
                "boundary": {
                    "en": "No paired per-example evidence.",
                    "zh": "没有逐样本配对证据。",
                },
            },
        },
    )
    _write_json(
        case / "review" / "change_review.json",
        {
            "change_kind": "model_change",
            "decision": "needs_review",
            "next_action": "Collect paired per-example evidence.",
            "claim_boundary": "Aggregate association, not unique causation.",
        },
    )
    client = TestClient(create_app(runs_dir=runs, language="zh"), base_url="http://127.0.0.1")

    listed = client.get("/api/runs")
    overview = client.get(
        "/api/overview",
        params={"run": "model_change_review", "language": "zh"},
    )

    assert listed.status_code == 200
    assert listed.json()["runs"] == [
        {
            "name": "model_change_review",
            "title": {"en": "Model change review", "zh": "模型切换审查"},
            "category": "model",
            "decision": "needs_review",
            "evidence_level": "historical_aggregate",
            "featured": True,
            "order": 2,
            "summary": {
                "en": "Compare two recorded model aggregates.",
                "zh": "比较两个已记录的模型汇总。",
            },
            "boundary": {
                "en": "No paired per-example evidence.",
                "zh": "没有逐样本配对证据。",
            },
        }
    ]
    assert overview.status_code == 200
    assert overview.json()["run"] == {"name": "model_change_review"}
    assert overview.json()["change_kind"] == "model_change"
    assert overview.json()["conclusion"] == "needs_review"
    assert "path" not in json.dumps(overview.json())


def test_web_api_localizes_the_featured_model_review_reason() -> None:
    client = TestClient(
        create_app(runs_dir=Path("docs/case_studies"), language="zh"), base_url="http://127.0.0.1"
    )

    response = client.get(
        "/api/overview",
        params={"run": "model_change_review", "language": "zh"},
    )

    assert response.status_code == 200
    assert response.json()["likely_causes"] == ["Candidate 门禁要求人工复核。"]


def test_web_api_empty_state_is_explicit(tmp_path: Path) -> None:
    client = TestClient(
        create_app(runs_dir=tmp_path / "missing", language="en"), base_url="http://127.0.0.1"
    )

    response = client.get("/api/overview")

    assert response.status_code == 200
    assert response.json()["has_run"] is False
    assert "pcl review" in response.json()["next_action"]


def test_web_api_rejects_unknown_or_unbounded_selected_runs(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _write_json(runs / "known" / "change_review.json", {"decision": "needs_review"})
    client = TestClient(create_app(runs_dir=runs, language="en"), base_url="http://127.0.0.1")

    for endpoint in ("/api/overview", "/api/diagnostics/catalog"):
        assert client.get(endpoint, params={"run": "missing"}).status_code == 404
        assert client.get(endpoint, params={"run": "../outside"}).status_code == 404


def test_web_api_reads_checkpoint_series_from_featured_case(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    case = runs / "checkpoint-case"
    _write_json(
        case / "case_manifest.json",
        {
            "decision": "hold",
            "display": {"review_path": "review", "featured": True},
        },
    )
    _write_json(case / "review" / "change_review.json", {"decision": "hold"})
    _write_json(
        case / "checkpoint_visualization.json",
        {
            "schema": "prompt_control_lab.checkpoint_visualization.v1",
            "decision": "hold",
            "points": [{"seed": "0", "stage": "initial", "mean_score": 0.1}],
        },
    )
    client = TestClient(create_app(runs_dir=runs), base_url="http://127.0.0.1")

    response = client.get("/api/checkpoint-series", params={"run": "checkpoint-case"})

    assert response.status_code == 200
    assert response.json()["decision"] == "hold"
    assert "path" not in json.dumps(response.json())


def test_web_api_imports_checkpoint_csv_as_bounded_local_run(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    client = TestClient(create_app(runs_dir=runs), base_url="http://127.0.0.1")
    csv_text = (
        "seed,stage,checkpoint_id,mean_score\n"
        "0,initial,seed-0-initial,0.1\n"
        "0,final,seed-0-final,0.2\n"
    )

    response = client.post(
        "/api/checkpoint-runs",
        headers={"x-pcl-session": client.get("/api/session").json()["token"]},
        json={"name": "Uploaded Checkpoints", "csv_text": csv_text},
    )

    assert response.status_code == 201
    assert response.json()["run"]["name"] == "uploaded-checkpoints"
    assert response.json()["decision"] == "insufficient_evidence"
    assert (runs / "uploaded-checkpoints" / "checkpoint_visualization.json").is_file()
    listed = client.get("/api/runs").json()["runs"]
    assert listed == [
        {
            "name": "uploaded-checkpoints",
            "title": {"en": "Uploaded Checkpoints", "zh": "Uploaded Checkpoints"},
            "category": "checkpoint",
            "decision": "insufficient_evidence",
            "evidence_level": "user_imported_descriptive_metrics",
            "featured": False,
            "technical_change_kind": "checkpoint_change",
        }
    ]
    assert (
        client.get("/api/checkpoint-series", params={"run": "uploaded-checkpoints"}).status_code
        == 200
    )
    assert (
        client.post(
            "/api/checkpoint-runs",
            headers={"x-pcl-session": client.get("/api/session").json()["token"]},
            json={"name": "Uploaded Checkpoints", "csv_text": csv_text},
        ).status_code
        == 409
    )


def test_web_api_rejects_checkpoint_upload_in_public_demo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PCL_DEPLOYMENT_MODE", "hf_demo")
    client = TestClient(create_app(runs_dir=tmp_path / "runs"), base_url="http://127.0.0.1")

    response = client.post(
        "/api/checkpoint-runs",
        json={"name": "blocked", "csv_text": "seed,stage,checkpoint_id,mean_score"},
    )

    assert response.status_code == 403
    assert client.get("/api/overview").json()["checkpoint_import_enabled"] is False
