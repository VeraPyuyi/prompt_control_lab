from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from promptcontrollab.hf_demo import (
    HF_DEMO_MAX_UPLOAD_BYTES,
    cleanup_expired_sessions,
    prepare_demo_session,
    store_uploaded_artifact,
    validate_uploaded_artifact,
)
from promptcontrollab.ui.workflows import run_analyze_workflow, run_guard_workflow


def test_hf_demo_upload_accepts_bounded_json_and_jsonl() -> None:
    document = validate_uploaded_artifact(
        "stats.json",
        b'{"comparisons":[{"mean_delta":0.2,"bootstrap_ci":[0.1,0.3]}]}',
    )
    records = validate_uploaded_artifact(
        "events.jsonl",
        b'{"event":"start","sequence":1}\n{"event":"end","sequence":2}\n',
    )

    assert document["format"] == "json"
    assert document["record_count"] == 1
    assert document["value"]["comparisons"][0]["mean_delta"] == 0.2
    assert records["format"] == "jsonl"
    assert records["record_count"] == 2


@pytest.mark.parametrize("filename", ["archive.zip", "weights.pt", "matrix.npz", "data.pkl"])
def test_hf_demo_upload_rejects_binary_and_archive_formats(filename: str) -> None:
    with pytest.raises(ValueError, match="JSON or JSONL"):
        validate_uploaded_artifact(filename, b"not-json")


@pytest.mark.parametrize(
    ("filename", "payload", "message"),
    [
        ("../stats.json", b"{}", "plain filename"),
        ("stats.json", b'{"score":NaN}', "finite"),
        ("events.jsonl", b'{"event":"ok"}\nnot-json\n', "line 2"),
        ("stats.json", b"\xff", "UTF-8"),
    ],
)
def test_hf_demo_upload_rejects_unsafe_or_invalid_payloads(
    filename: str,
    payload: bytes,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_uploaded_artifact(filename, payload)


def test_hf_demo_upload_enforces_size_depth_and_record_limits() -> None:
    with pytest.raises(ValueError, match="5 MB"):
        validate_uploaded_artifact("stats.json", b" " * (HF_DEMO_MAX_UPLOAD_BYTES + 1))

    nested: object = {"value": 1}
    for _ in range(25):
        nested = {"nested": nested}
    with pytest.raises(ValueError, match="nesting depth"):
        validate_uploaded_artifact("stats.json", json.dumps(nested).encode("utf-8"))

    rows = b"".join(b'{"event":"tick"}\n' for _ in range(5001))
    with pytest.raises(ValueError, match="record limit"):
        validate_uploaded_artifact("events.jsonl", rows)


def test_hf_demo_upload_requires_a_recognized_artifact_schema() -> None:
    with pytest.raises(ValueError, match="recognized PromptControlLab artifact"):
        validate_uploaded_artifact("arbitrary.json", b'{"value":1}')
    with pytest.raises(ValueError, match="comparisons"):
        validate_uploaded_artifact("stats.json", b'{"comparisons":"invalid"}')
    with pytest.raises(ValueError, match="runs"):
        validate_uploaded_artifact("history_index.json", b'{"runs":{}}')


def test_hf_demo_session_isolated_copy_upload_and_cleanup(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    (seed / "quick").mkdir(parents=True)
    (seed / "quick" / "manifest.json").write_text(
        '{"tool":"prompt_control_lab"}\n', encoding="utf-8"
    )
    base = tmp_path / "runtime"

    session = prepare_demo_session(base, seed_runs=seed, session_id="session-1")

    assert session.root == base.resolve() / "sessions" / "session-1"
    assert (session.runs_dir / "quick" / "manifest.json").exists()
    assert session.uploads_dir.is_dir()
    assert session.outputs_dir.is_dir()
    assert (session.root / ".pcl-hf-session.json").exists()

    uploaded = store_uploaded_artifact(
        session,
        run_name="uploaded-run",
        filename="stats.json",
        content=b'{"comparisons":[]}',
    )
    assert uploaded == session.runs_dir / "uploaded-run" / "stats.json"
    assert json.loads(uploaded.read_text(encoding="utf-8")) == {"comparisons": []}

    marker = session.root / ".pcl-hf-session.json"
    old = time.time() - 10_000
    os.utime(marker, (old, old))
    removed = cleanup_expired_sessions(base, max_age_seconds=60, now=time.time())

    assert removed == [session.root]
    assert not session.root.exists()


def test_hf_demo_upload_enforces_cumulative_session_quota(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from promptcontrollab import hf_demo

    session = prepare_demo_session(tmp_path / "runtime", session_id="quota-session")
    payload = json.dumps({"summary": "x" * 120}).encode("utf-8")
    monkeypatch.setattr(hf_demo, "HF_DEMO_MAX_SESSION_FILES", 2)
    monkeypatch.setattr(hf_demo, "HF_DEMO_MAX_SESSION_BYTES", 10_000)
    monkeypatch.setattr(hf_demo, "HF_DEMO_MAX_GLOBAL_BYTES", 100_000)

    store_uploaded_artifact(
        session,
        run_name="upload-one",
        filename="explanation.json",
        content=payload,
    )
    with pytest.raises(ValueError, match="file quota"):
        store_uploaded_artifact(
            session,
            run_name="upload-two",
            filename="explanation.json",
            content=payload,
        )


def test_hf_demo_upload_enforces_cumulative_byte_and_global_quotas(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from promptcontrollab import hf_demo

    base = tmp_path / "runtime"
    first = prepare_demo_session(base, session_id="quota-first")
    second = prepare_demo_session(base, session_id="quota-second")
    payload = json.dumps({"summary": "x" * 200}).encode("utf-8")
    monkeypatch.setattr(hf_demo, "HF_DEMO_MAX_SESSION_FILES", 100)
    monkeypatch.setattr(hf_demo, "HF_DEMO_MAX_SESSION_BYTES", 180)
    monkeypatch.setattr(hf_demo, "HF_DEMO_MAX_GLOBAL_BYTES", 100_000)

    with pytest.raises(ValueError, match="byte quota"):
        store_uploaded_artifact(
            first,
            run_name="too-large",
            filename="explanation.json",
            content=payload,
        )

    monkeypatch.setattr(hf_demo, "HF_DEMO_MAX_SESSION_BYTES", 10_000)
    monkeypatch.setattr(hf_demo, "HF_DEMO_MAX_GLOBAL_BYTES", 300)
    store_uploaded_artifact(
        first,
        run_name="fits-once",
        filename="explanation.json",
        content=b'{"summary":"small"}',
    )
    with pytest.raises(ValueError, match="global storage quota"):
        store_uploaded_artifact(
            second,
            run_name="global-limit",
            filename="explanation.json",
            content=payload,
        )


def test_hf_demo_quota_check_and_write_share_one_process_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from promptcontrollab import hf_demo

    session = prepare_demo_session(tmp_path / "runtime", session_id="locked-session")
    original_quota_check = hf_demo._enforce_storage_quotas
    original_write_bytes = Path.write_bytes
    observations: list[str] = []

    def checked_quota(
        session_arg: hf_demo.DemoSession,
        *,
        output: Path,
        incoming_bytes: int,
    ) -> None:
        assert hf_demo._STORAGE_LOCK.locked()
        observations.append("quota")
        original_quota_check(session_arg, output=output, incoming_bytes=incoming_bytes)

    def checked_write(path: Path, data: bytes) -> int:
        assert hf_demo._STORAGE_LOCK.locked()
        observations.append("write")
        return original_write_bytes(path, data)

    monkeypatch.setattr(hf_demo, "_enforce_storage_quotas", checked_quota)
    monkeypatch.setattr(Path, "write_bytes", checked_write)
    store_uploaded_artifact(
        session,
        run_name="locked-run",
        filename="explanation.json",
        content=b'{"summary":"bounded"}',
    )

    assert observations == ["quota", "write"]


@pytest.mark.parametrize("session_id", ["../escape", "a/b", ".", "", "x" * 65])
def test_hf_demo_session_rejects_unsafe_identifiers(tmp_path: Path, session_id: str) -> None:
    with pytest.raises(ValueError, match="session id"):
        prepare_demo_session(tmp_path / "runtime", session_id=session_id)


def test_hf_demo_backend_allows_guard_but_blocks_other_workflows_and_external_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PCL_DEPLOYMENT_MODE", "hf_demo")
    runs = tmp_path / "runtime" / "sessions" / "safe" / "runs"

    guarded = run_guard_workflow(
        prompt="Fix the parser in src/parser.py and run focused tests.",
        out_dir=runs / "guard",
        execution_mode="auto",
        confirmed=False,
        overwrite=False,
        safe_root=runs,
    )
    assert guarded["status"] == "completed"

    with pytest.raises(ValueError, match="disabled in the Hugging Face demo"):
        run_analyze_workflow(
            data_path=tmp_path / "missing-tasks.jsonl",
            baseline_predictions_path=tmp_path / "missing-baseline.jsonl",
            candidate_predictions_path=tmp_path / "missing-candidate.jsonl",
            out_dir=runs / "quick",
            execution_mode="auto",
            confirmed=False,
            overwrite=False,
            safe_root=runs,
        )

    with pytest.raises(ValueError, match="outside the session runs directory"):
        run_guard_workflow(
            prompt="Fix the parser in src/parser.py and run focused tests.",
            out_dir=tmp_path / "outside",
            execution_mode="confirm",
            confirmed=True,
            overwrite=False,
            safe_root=runs,
            allow_external_outputs=True,
        )


def test_hf_demo_run_view_does_not_render_local_workflow_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from promptcontrollab.ui import app

    class FakeStreamlit:
        def subheader(self, _value: object) -> None:
            pass

        def caption(self, _value: object) -> None:
            pass

        def info(self, _value: object) -> None:
            pass

    def fail_if_rendered(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Local workflows must not be rendered in hf_demo mode.")

    monkeypatch.setattr(app, "_render_workflows_tab", fail_if_rendered)
    app._render_run_view(
        FakeStreamlit(),
        app.TEXT["en"],
        "en",
        None,
        {},
        Path("runs"),
        "confirm",
        False,
        False,
        deployment_mode="hf_demo",
    )


def test_before_view_uses_tabs_instead_of_nesting_tutorial_expanders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from promptcontrollab.ui import app

    rendered: list[str] = []

    class Context:
        def __enter__(self) -> None:
            return None

        def __exit__(self, *_args: object) -> None:
            return None

    class FakeStreamlit:
        def subheader(self, _value: object) -> None:
            pass

        def caption(self, _value: object) -> None:
            pass

        def info(self, _value: object) -> None:
            pass

        def tabs(self, labels: list[str]) -> list[Context]:
            assert len(labels) == 2
            return [Context(), Context()]

        def expander(self, *_args: object, **_kwargs: object) -> None:
            raise AssertionError("Before view must not wrap nested tutorial expanders.")

    monkeypatch.setattr(
        app,
        "_render_guard_tab",
        lambda *_args, **_kwargs: rendered.append("guard"),
    )
    monkeypatch.setattr(
        app,
        "_render_tutorial_tab",
        lambda *_args, **_kwargs: rendered.append("tutorial"),
    )
    app._render_before_view(
        FakeStreamlit(),
        app.TEXT["en"],
        "en",
        None,
        {},
        {},
        Path("runs"),
        False,
        "hf_demo",
    )

    assert rendered == ["guard", "tutorial"]
