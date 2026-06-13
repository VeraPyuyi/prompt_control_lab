from __future__ import annotations

import json
from pathlib import Path

from promptcontrollab.cli import main
from promptcontrollab.files import read_json, write_json


def test_validity_reports_clean_prompt_only_comparison(tmp_path: Path) -> None:
    baseline = _make_run(
        tmp_path / "baseline",
        prompt_hash="sha256:baseline",
        model_id="claude-sonnet-4-20250514",
        split_hash="split-1",
        mean_score=0.7,
        by_slice={"arith": 0.7, "format": 0.75},
    )
    candidate = _make_run(
        tmp_path / "candidate",
        prompt_hash="sha256:candidate",
        model_id="claude-sonnet-4-20250514",
        split_hash="split-1",
        mean_score=0.82,
        by_slice={"arith": 0.82, "format": 0.8},
        stats={
            "comparisons": [
                {
                    "mean_delta": 0.12,
                    "bootstrap_ci": [0.04, 0.18],
                    "permutation_p_value": 0.01,
                    "holm_adjusted_p_value": 0.01,
                }
            ]
        },
    )
    out = tmp_path / "validity" / "comparison_validity.json"

    assert _run_validity(baseline, candidate, out) == 0

    payload = read_json(out)
    assert payload["validity"] == "clean"
    assert payload["prompt_only_comparison"] is True
    assert payload["checks"]["model_identity"]["status"] == "pass"
    assert payload["checks"]["prompt_identity"]["status"] == "pass"
    assert payload["checks"]["statistical_evidence"]["mean_delta"] == 0.12
    assert (tmp_path / "validity" / "comparison_validity.md").exists()


def test_validity_blocks_model_mismatch(tmp_path: Path) -> None:
    baseline = _make_run(
        tmp_path / "baseline",
        prompt_hash="sha256:baseline",
        model_id="gpt-4o",
        split_hash="split-1",
        mean_score=0.7,
    )
    candidate = _make_run(
        tmp_path / "candidate",
        prompt_hash="sha256:candidate",
        model_id="gpt-5.2",
        split_hash="split-1",
        mean_score=0.82,
    )
    out = tmp_path / "comparison_validity.json"

    assert _run_validity(baseline, candidate, out) == 0

    payload = read_json(out)
    assert payload["validity"] == "invalid"
    assert payload["prompt_only_comparison"] is False
    assert payload["checks"]["model_identity"]["status"] == "fail"
    assert any("model" in issue.lower() for issue in payload["blocking_issues"])


def test_validity_reviews_missing_prompt_and_split_identity(tmp_path: Path) -> None:
    baseline = _make_run(
        tmp_path / "baseline",
        prompt_hash=None,
        model_id="claude-sonnet-4-20250514",
        split_hash=None,
        mean_score=0.7,
    )
    candidate = _make_run(
        tmp_path / "candidate",
        prompt_hash="sha256:candidate",
        model_id="claude-sonnet-4-20250514",
        split_hash=None,
        mean_score=0.82,
    )
    out = tmp_path / "comparison_validity.json"

    assert _run_validity(baseline, candidate, out) == 0

    payload = read_json(out)
    assert payload["validity"] == "needs_review"
    assert payload["prompt_only_comparison"] == "unknown"
    assert payload["checks"]["prompt_identity"]["status"] == "review"
    assert payload["checks"]["split_identity"]["status"] == "review"
    assert payload["review_items"]


def _make_run(
    path: Path,
    *,
    prompt_hash: str | None,
    model_id: str,
    split_hash: str | None,
    mean_score: float,
    by_slice: dict[str, float] | None = None,
    stats: dict[str, object] | None = None,
) -> Path:
    prompt = {"prompt_hash": prompt_hash} if prompt_hash is not None else {}
    manifest = {
        "tool": "prompt_control_lab",
        "metric": "exact_match",
        "prompt": prompt,
        "candidate_model": {
            "provider": "anthropic" if model_id.startswith("claude-") else "openai",
            "model_id": model_id,
            "provenance_level": "level_1_observed_in_response",
        },
    }
    write_json(path / "manifest.json", manifest)
    write_json(path / "metrics.json", {"mean_score": mean_score, "by_slice": by_slice or {}})
    if split_hash is not None:
        write_json(path / "splits.json", {"split_hash": split_hash})
    if stats is not None:
        write_json(path / "stats.json", json.loads(json.dumps(stats)))
    return path


def _run_validity(baseline: Path, candidate: Path, out: Path) -> int:
    return main(
        [
            "validity",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--out",
            str(out),
        ]
    )
