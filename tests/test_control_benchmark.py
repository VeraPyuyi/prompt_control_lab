from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = ROOT / "examples" / "control-benchmark"
MANIFEST_PATH = BENCHMARK_DIR / "manifest.json"
MANIFEST_SCHEMA = "prompt_control_lab.control_benchmark_manifest.v1"
RESULT_SCHEMA = "prompt_control_lab.control_benchmark_result.v1"
EXPECTED_LABELS = {
    "converging",
    "stalled",
    "oscillating",
    "diverging",
    "insufficient_evidence",
}
SENSITIVE_KEYS = {
    "access_key",
    "access_token",
    "api_key",
    "apikey",
    "auth_token",
    "authorization",
    "chain_of_thought",
    "client_secret",
    "cot",
    "password",
    "private_key",
    "prompt",
    "raw_prompt",
    "reasoning",
    "reasoning_content",
    "secret",
    "secret_key",
    "system_prompt",
    "token",
}


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def _walk_keys(value: object) -> Iterator[str]:
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key).strip().lower().replace("-", "_")
            yield from _walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_keys(item)


def test_open_benchmark_covers_every_stability_label() -> None:
    from promptcontrollab.control_benchmark import run_benchmark

    result = run_benchmark(MANIFEST_PATH)
    cases = cast(list[dict[str, Any]], result["cases"])

    assert {case["expected"] for case in cases} == EXPECTED_LABELS
    assert {case["observed"] for case in cases} == EXPECTED_LABELS
    assert all(case["pass"] is True for case in cases)
    assert result["passed_cases"] == 5
    assert result["total_cases"] == 5
    assert result["accuracy"] == 1.0

    for case in cases:
        stability = cast(dict[str, Any], case["stability"])
        attribution = cast(dict[str, Any], case["attribution"])
        assert stability["state"] == case["observed"]
        assert stability["schema"] == "prompt_control_lab.stability_report.v1"
        assert "no hidden-state claim" in str(stability["summary"])
        assert attribution["schema"] == "prompt_control_lab.attribution_report.v1"
        assert attribution["status"] == "insufficient_evidence"
        assert "causation" in str(attribution["summary"])


def test_benchmark_result_is_deterministic_and_has_a_stable_schema() -> None:
    from promptcontrollab.control_benchmark import run_benchmark

    first = run_benchmark(MANIFEST_PATH)
    second = run_benchmark(MANIFEST_PATH)

    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["schema"] == RESULT_SCHEMA
    assert first["benchmark_id"] == "open-control-events-v1"
    assert set(first) == {
        "schema",
        "benchmark_id",
        "description",
        "claim_boundary",
        "cases",
        "passed_cases",
        "total_cases",
        "accuracy",
    }
    assert "synthetic observable events" in str(first["claim_boundary"])
    assert "does not measure agent quality" in str(first["claim_boundary"])
    assert "universal safety" in str(first["claim_boundary"])


def test_manifest_and_event_fixture_schema_are_explicit() -> None:
    manifest = _read_object(MANIFEST_PATH)

    assert manifest["schema"] == MANIFEST_SCHEMA
    assert isinstance(manifest["benchmark_id"], str)
    assert isinstance(manifest["description"], str)
    assert isinstance(manifest["claim_boundary"], str)
    cases = cast(list[dict[str, Any]], manifest["cases"])
    assert len(cases) == 5
    assert len({case["case_id"] for case in cases}) == len(cases)

    for case in cases:
        assert set(case) == {
            "case_id",
            "fixture",
            "expected_label",
            "evidence_boundary",
            "baseline_run",
        }
        assert case["expected_label"] in EXPECTED_LABELS
        assert isinstance(case["evidence_boundary"], str)
        assert 20 <= len(case["evidence_boundary"]) <= 180
        fixture = (BENCHMARK_DIR / str(case["fixture"])).resolve()
        assert fixture.is_relative_to(BENCHMARK_DIR.resolve())
        assert fixture.suffix == ".jsonl"
        assert fixture.is_file()

        records = [json.loads(line) for line in fixture.read_text(encoding="utf-8").splitlines()]
        assert records
        for record in records:
            assert isinstance(record, dict)
            assert set(record) == {"sequence", "event_type", "payload"}
            assert isinstance(record["sequence"], int)
            assert record["sequence"] > 0
            assert isinstance(record["event_type"], str)
            assert record["event_type"]
            assert isinstance(record["payload"], dict)


def test_malformed_fixture_reports_its_file_and_line(tmp_path: Path) -> None:
    from promptcontrollab.control_benchmark import ControlBenchmarkError, run_benchmark

    fixture = tmp_path / "malformed.jsonl"
    fixture.write_text(
        '{"sequence": 1, "event_type": "agent/request", "payload": {}}\nnot-json\n',
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": MANIFEST_SCHEMA,
                "benchmark_id": "malformed-fixture-test",
                "description": "Synthetic malformed fixture test.",
                "claim_boundary": "Synthetic observable events only.",
                "cases": [
                    {
                        "case_id": "malformed",
                        "fixture": fixture.name,
                        "expected_label": "insufficient_evidence",
                        "evidence_boundary": "Malformed input must fail before classification.",
                        "baseline_run": {"run_id": "synthetic-baseline"},
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ControlBenchmarkError, match=r"malformed\.jsonl:2"):
        run_benchmark(manifest)


def test_fixtures_contain_no_sensitive_or_private_reasoning_keys() -> None:
    manifest = _read_object(MANIFEST_PATH)
    cases = cast(list[dict[str, Any]], manifest["cases"])

    for case in cases:
        fixture = BENCHMARK_DIR / str(case["fixture"])
        text = fixture.read_text(encoding="utf-8")
        records = [json.loads(line) for line in text.splitlines()]
        assert SENSITIVE_KEYS.isdisjoint(_walk_keys(records))
        assert "sk-" not in text.lower()
        assert "bearer " not in text.lower()
        assert "begin private key" not in text.lower()


def test_python_module_entrypoint_prints_the_api_result(capsys: pytest.CaptureFixture[str]) -> None:
    from promptcontrollab.control_benchmark import main, run_benchmark

    assert main([str(MANIFEST_PATH)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == run_benchmark(MANIFEST_PATH)


@pytest.mark.parametrize("readme_name", ["README.md", "README.zh.md"])
def test_module_run_docs_include_editable_install_prerequisite(readme_name: str) -> None:
    text = (BENCHMARK_DIR / readme_name).read_text(encoding="utf-8")

    assert "python -m pip install -e ." in text
    assert (
        "python -m promptcontrollab.control_benchmark "
        "examples/control-benchmark/manifest.json"
    ) in text
