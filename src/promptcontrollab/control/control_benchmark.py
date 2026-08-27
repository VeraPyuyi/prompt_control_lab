"""Run the open synthetic-event benchmark for the control analyzers.

The benchmark checks deterministic classification contracts over recorded
events. It does not measure agent quality, establish causation, or prove safety.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from promptcontrollab.control.control_analysis import analyze_attribution, analyze_stability
from promptcontrollab.core.files import JsonDict

MANIFEST_SCHEMA = "prompt_control_lab.control_benchmark_manifest.v1"
RESULT_SCHEMA = "prompt_control_lab.control_benchmark_result.v1"
STABILITY_LABELS = frozenset(
    {
        "converging",
        "stalled",
        "oscillating",
        "diverging",
        "insufficient_evidence",
    }
)
_EVENT_FIELDS = {"sequence", "event_type", "payload"}


class ControlBenchmarkError(ValueError):
    """Raised when a benchmark manifest or fixture violates the open schema."""


def run_benchmark(manifest_path: str | Path) -> JsonDict:
    """Run every case in ``manifest_path`` and return a stable JSON-compatible result."""

    path = Path(manifest_path)
    manifest = _read_json_object(path, "benchmark manifest")
    _require_schema(manifest, path)
    benchmark_id = _require_string(manifest.get("benchmark_id"), "benchmark_id", path)
    description = _require_string(manifest.get("description"), "description", path)
    claim_boundary = _require_string(manifest.get("claim_boundary"), "claim_boundary", path)
    raw_cases = manifest.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ControlBenchmarkError(f"Expected non-empty `cases` list in {path}")

    case_results: list[JsonDict] = []
    seen_case_ids: set[str] = set()
    for position, raw_case in enumerate(raw_cases, start=1):
        case = _require_object(raw_case, f"cases[{position}]", path)
        case_id = _require_string(case.get("case_id"), "case_id", path)
        if case_id in seen_case_ids:
            raise ControlBenchmarkError(f"Duplicate case_id `{case_id}` in {path}")
        seen_case_ids.add(case_id)
        case_results.append(_run_case(case, case_id=case_id, manifest_path=path))

    passed_cases = sum(case["pass"] is True for case in case_results)
    total_cases = len(case_results)
    return {
        "schema": RESULT_SCHEMA,
        "benchmark_id": benchmark_id,
        "description": description,
        "claim_boundary": claim_boundary,
        "cases": case_results,
        "passed_cases": passed_cases,
        "total_cases": total_cases,
        "accuracy": round(passed_cases / total_cases, 6),
    }


def _run_case(case: JsonDict, *, case_id: str, manifest_path: Path) -> JsonDict:
    fixture_name = _require_string(case.get("fixture"), "fixture", manifest_path)
    expected = _require_string(case.get("expected_label"), "expected_label", manifest_path)
    if expected not in STABILITY_LABELS:
        supported = ", ".join(sorted(STABILITY_LABELS))
        raise ControlBenchmarkError(
            f"Unsupported expected_label `{expected}` for `{case_id}`; expected one of {supported}"
        )
    evidence_boundary = _require_string(
        case.get("evidence_boundary"), "evidence_boundary", manifest_path
    )
    baseline_run = _require_object(case.get("baseline_run"), "baseline_run", manifest_path)
    fixture_path = _resolve_fixture(manifest_path, fixture_name)
    events = _read_events(fixture_path)
    run: JsonDict = {"run_id": f"control-benchmark:{case_id}"}

    stability = analyze_stability(run, events).to_json()
    attribution = analyze_attribution(
        run,
        events,
        baseline_run=baseline_run,
    ).to_json()
    observed = cast(str, stability["state"])
    return {
        "case_id": case_id,
        "fixture": fixture_name,
        "expected": expected,
        "observed": observed,
        "pass": observed == expected,
        "evidence_boundary": evidence_boundary,
        "stability": stability,
        "attribution": attribution,
    }


def _read_json_object(path: Path, description: str) -> JsonDict:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise ControlBenchmarkError(f"Could not read {description} {path}: {exc}") from exc
    try:
        value = cast(object, json.loads(text))
    except json.JSONDecodeError as exc:
        raise ControlBenchmarkError(
            f"Invalid JSON in {description} {path}:{exc.lineno}: {exc.msg}"
        ) from exc
    return _require_object(value, description, path)


def _read_events(path: Path) -> list[JsonDict]:
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ControlBenchmarkError(f"Could not read benchmark fixture {path}: {exc}") from exc

    events: list[JsonDict] = []
    sequences: set[int] = set()
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        location = f"{path.name}:{line_number}"
        try:
            value = cast(object, json.loads(stripped))
        except json.JSONDecodeError as exc:
            raise ControlBenchmarkError(
                f"Malformed benchmark fixture {location}: {exc.msg}"
            ) from exc
        event = _require_object(value, "event record", Path(location))
        if set(event) != _EVENT_FIELDS:
            raise ControlBenchmarkError(
                f"Malformed benchmark fixture {location}: expected fields {sorted(_EVENT_FIELDS)}"
            )
        sequence = event.get("sequence")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence <= 0:
            raise ControlBenchmarkError(
                f"Malformed benchmark fixture {location}: `sequence` must be a positive integer"
            )
        if sequence in sequences:
            raise ControlBenchmarkError(
                f"Malformed benchmark fixture {location}: duplicate sequence {sequence}"
            )
        sequences.add(sequence)
        event_type = event.get("event_type")
        if not isinstance(event_type, str) or not event_type.strip():
            raise ControlBenchmarkError(
                f"Malformed benchmark fixture {location}: `event_type` must be a non-empty string"
            )
        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            raise ControlBenchmarkError(
                f"Malformed benchmark fixture {location}: `payload` must be an object"
            )
        events.append(
            {
                "sequence": sequence,
                "event_type": event_type,
                "payload": {str(key): item for key, item in payload.items()},
            }
        )
    if not events:
        raise ControlBenchmarkError(f"Benchmark fixture {path} contains no event records")
    return events


def _resolve_fixture(manifest_path: Path, fixture_name: str) -> Path:
    root = manifest_path.resolve().parent
    fixture_path = (root / fixture_name).resolve()
    try:
        fixture_path.relative_to(root)
    except ValueError as exc:
        raise ControlBenchmarkError(
            f"Fixture `{fixture_name}` must stay within benchmark directory {root}"
        ) from exc
    if fixture_path.suffix.lower() != ".jsonl":
        raise ControlBenchmarkError(f"Fixture `{fixture_name}` must be a .jsonl file")
    return fixture_path


def _require_schema(manifest: JsonDict, path: Path) -> None:
    observed = manifest.get("schema")
    if observed != MANIFEST_SCHEMA:
        raise ControlBenchmarkError(
            f"Unsupported benchmark schema in {path}: "
            f"expected `{MANIFEST_SCHEMA}`, got {observed!r}"
        )


def _require_string(value: object, field: str, path: Path) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ControlBenchmarkError(f"Expected non-empty string `{field}` in {path}")
    return value


def _require_object(value: object, field: str, path: Path) -> JsonDict:
    if not isinstance(value, Mapping):
        raise ControlBenchmarkError(f"Expected object `{field}` in {path}")
    return {str(key): item for key, item in value.items()}


def main(argv: Sequence[str] | None = None) -> int:
    """Run the benchmark as ``python -m promptcontrollab.control.control_benchmark``."""

    parser = argparse.ArgumentParser(
        description="Run PromptControlLab's open synthetic control-event benchmark."
    )
    parser.add_argument("manifest", type=Path, help="Path to the benchmark manifest JSON file.")
    args = parser.parse_args(argv)
    result = run_benchmark(cast(Path, args.manifest))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
