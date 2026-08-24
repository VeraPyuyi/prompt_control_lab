from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from promptcontrollab.cli import main
from promptcontrollab.posttrain_pilot import (
    PilotInputs,
    build_sft_pilot_plan,
    canonical_answer_exact_match,
    paired_checkpoint_statistics,
    sequence_exact_match,
    token_trajectory_drift,
    training_strategy_argument,
    validate_resource_approval,
)
from promptcontrollab.posttrain_pilot_runner import _aurc


def _write_jsonl(
    path: Path,
    *,
    row_id: str | None = None,
    prompt: str | None = None,
) -> None:
    path.write_text(
        json.dumps(
            {
                "id": row_id or path.stem,
                "prompt": prompt or f"Question for {path.stem}?",
                "answer": "4",
                "slice": "math",
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_sft_pilot_plan_is_three_seed_fixed_split_and_plan_only(tmp_path: Path) -> None:
    train = tmp_path / "train.jsonl"
    validation = tmp_path / "validation.jsonl"
    withheld = tmp_path / "withheld.jsonl"
    format_fixture = tmp_path / "format.jsonl"
    for path in [train, validation, withheld, format_fixture]:
        _write_jsonl(path)

    plan = build_sft_pilot_plan(
        PilotInputs(
            model_path=tmp_path / "Qwen2.5-0.5B",
            train_path=train,
            validation_path=validation,
            withheld_path=withheld,
            format_fixture_path=format_fixture,
            out_dir=tmp_path / "pilot",
        )
    )

    assert plan["schema"] == "prompt_control_lab.posttrain_sft_pilot.v1"
    assert plan["execution_status"] == "plan_only"
    assert plan["seeds"] == [0, 1, 2]
    assert plan["checkpoint_stages"] == ["initial", "mid", "final"]
    assert plan["task_families"] == ["gsm8k", "format_following"]
    assert plan["split_provenance"]["combined_sha256"].startswith("sha256:")
    assert len(plan["planned_evaluations"]) == 9
    assert all(
        row["soft_hard_applicability"] == "not_applicable"
        for row in plan["planned_evaluations"]
    )


def test_posttrain_pilot_cli_is_available_without_gpu_dependencies(tmp_path: Path) -> None:
    paths = [
        tmp_path / name
        for name in ["train.jsonl", "validation.jsonl", "withheld.jsonl", "format.jsonl"]
    ]
    for path in paths:
        _write_jsonl(path)
    out_dir = tmp_path / "pilot"

    assert main(
        [
            "posttrain-pilot",
            "--model",
            str(tmp_path / "Qwen2.5-0.5B"),
            "--train",
            str(paths[0]),
            "--validation",
            str(paths[1]),
            "--withheld",
            str(paths[2]),
            "--format-fixture",
            str(paths[3]),
            "--out",
            str(out_dir),
        ]
    ) == 0
    protocol = json.loads((out_dir / "pilot_protocol.json").read_text(encoding="utf-8"))
    assert protocol["execution_status"] == "plan_only"


def test_resource_approval_requires_queue_clear_matching_gpu_and_fresh_expiry(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    approval = tmp_path / "approval.json"
    approval.write_text(
        json.dumps(
            {
                "approved": True,
                "queue_clear": True,
                "gpu": 3,
                "checked_at": (now - timedelta(minutes=5)).isoformat(),
                "expires_at": (now + timedelta(minutes=25)).isoformat(),
                "approved_by": "server-operator",
            }
        ),
        encoding="utf-8",
    )

    result = validate_resource_approval(approval, gpu=3, now=now)

    assert result["approved"] is True
    assert result["queue_clear"] is True
    assert result["gpu"] == 3


def test_paired_checkpoint_statistics_are_deterministic_and_matched() -> None:
    first = paired_checkpoint_statistics(
        [0.0, 0.0, 1.0, 1.0],
        [1.0, 0.0, 1.0, 1.0],
        seed=7,
        samples=500,
        baseline_checkpoint="seed-7-initial",
        candidate_checkpoint="seed-7-final",
        baseline_split_hash="sha256:split",
        candidate_split_hash="sha256:split",
        baseline_sample_hash="sha256:samples",
        candidate_sample_hash="sha256:samples",
    )
    second = paired_checkpoint_statistics(
        [0.0, 0.0, 1.0, 1.0],
        [1.0, 0.0, 1.0, 1.0],
        seed=7,
        samples=500,
        baseline_checkpoint="seed-7-initial",
        candidate_checkpoint="seed-7-final",
        baseline_split_hash="sha256:split",
        candidate_split_hash="sha256:split",
        baseline_sample_hash="sha256:samples",
        candidate_sample_hash="sha256:samples",
    )

    assert first == second
    comparison = first["comparisons"][0]
    assert comparison["mean_delta"] == 0.25
    assert comparison["n_pairs"] == 4
    assert len(comparison["bootstrap_ci"]) == 2
    assert 0.0 <= comparison["permutation_p_value"] <= 1.0
    assert comparison["baseline_checkpoint"] == "seed-7-initial"
    assert comparison["candidate_checkpoint"] == "seed-7-final"
    assert comparison["baseline_split_hash"] == "sha256:split"


def test_training_strategy_argument_supports_current_and_legacy_transformers() -> None:
    assert training_strategy_argument({"eval_strategy", "output_dir"}) == {
        "eval_strategy": "steps"
    }
    assert training_strategy_argument({"evaluation_strategy", "output_dir"}) == {
        "evaluation_strategy": "steps"
    }
    with pytest.raises(ValueError, match="evaluation strategy"):
        training_strategy_argument({"output_dir"})


def test_pilot_diagnostics_use_comparable_sequence_and_token_trajectory_units() -> None:
    assert sequence_exact_match([1, 2], [1, 2]) == 1.0
    assert sequence_exact_match([1, 3], [1, 2]) == 0.0
    assert sequence_exact_match([], []) == 0.0

    drift = token_trajectory_drift([[0.0, 0.0], [1.0, 0.0], [1.0, 2.0]])
    assert drift == pytest.approx((1.0 / (2**0.5) + 2.0 / (2**0.5)) / 2.0)
    assert canonical_answer_exact_match("  FINAL   Answer ", "final answer") == 1.0
    assert canonical_answer_exact_match("#### 4", "4") == 1.0


@pytest.mark.parametrize("overlap_kind", ["id", "content", "format_content"])
def test_sft_pilot_rejects_train_validation_withheld_overlap(
    tmp_path: Path,
    overlap_kind: str,
) -> None:
    train = tmp_path / "train.jsonl"
    validation = tmp_path / "validation.jsonl"
    withheld = tmp_path / "withheld.jsonl"
    format_fixture = tmp_path / "format.jsonl"
    _write_jsonl(train, row_id="train", prompt="train question")
    _write_jsonl(validation, row_id="validation", prompt="validation question")
    _write_jsonl(withheld, row_id="withheld", prompt="withheld question")
    _write_jsonl(format_fixture, row_id="format", prompt="format question")
    if overlap_kind == "id":
        _write_jsonl(withheld, row_id="train", prompt="different content")
    elif overlap_kind == "content":
        _write_jsonl(withheld, row_id="different", prompt="train question")
    else:
        _write_jsonl(format_fixture, row_id="format", prompt="train question")

    with pytest.raises(ValueError, match="overlap"):
        build_sft_pilot_plan(
            PilotInputs(
                model_path=tmp_path / "model",
                train_path=train,
                validation_path=validation,
                withheld_path=withheld,
                format_fixture_path=format_fixture,
                out_dir=tmp_path / "pilot",
            )
        )


def test_selective_risk_uses_label_independent_confidence_ties() -> None:
    assert _aurc([1.0, 0.0], [0.5, 0.5]) == pytest.approx(0.5)
    assert _aurc([0.0, 1.0], [0.5, 0.5]) == pytest.approx(0.5)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"queue_clear": False}, "queue"),
        ({"gpu": 2}, "GPU"),
        ({"approved": False}, "approved"),
        ({"expires_at": "2026-08-23T11:59:00+00:00"}, "expired"),
    ],
)
def test_resource_approval_fails_closed(
    tmp_path: Path,
    overrides: dict[str, object],
    message: str,
) -> None:
    now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    payload: dict[str, object] = {
        "approved": True,
        "queue_clear": True,
        "gpu": 3,
        "checked_at": "2026-08-23T11:55:00+00:00",
        "expires_at": "2026-08-23T12:25:00+00:00",
        "approved_by": "server-operator",
    }
    payload.update(overrides)
    approval = tmp_path / "approval.json"
    approval.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        validate_resource_approval(approval, gpu=3, now=now)
