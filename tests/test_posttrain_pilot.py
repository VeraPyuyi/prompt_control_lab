from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from promptcontrollab import posttrain_pilot_runner
from promptcontrollab.cli import main
from promptcontrollab.posttrain_pilot import (
    PilotInputs,
    aggregate_pilot_decisions,
    build_sft_pilot_plan,
    canonical_answer_exact_match,
    paired_checkpoint_statistics,
    score_pilot_output,
    sequence_exact_match,
    token_trajectory_drift,
    training_strategy_argument,
    validate_gpu_idle_snapshots,
    validate_model_provenance,
    validate_resource_approval,
    write_model_provenance,
)
from promptcontrollab.posttrain_pilot_runner import (
    _assert_gpu_idle_twice,
    _aurc,
    _representation_shift,
)


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
                "queue_pending_jobs": 0,
                "queue_running_jobs": 0,
                "queue_source": "/root/prompt_control_lab_runtime/queue_snapshot.json",
                "queue_snapshot_sha256": "sha256:" + "a" * 64,
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
    assert _representation_shift([0.0, 0.0], [1.0, 1.0]) == pytest.approx(1.0)
    assert _representation_shift([], []) is None


def test_pilot_scoring_extracts_gsm8k_final_number_but_keeps_format_strict() -> None:
    reasoning = "We add 19 and 23. The answer is 42."

    assert score_pilot_output(reasoning, "#### 42", "gsm8k") == 1.0
    assert score_pilot_output("19 + 23 = 41. Final answer: 41", "#### 42", "gsm8k") == 0.0
    assert score_pilot_output("LABEL: YES\nExplanation", "LABEL: YES", "format") == 0.0
    assert score_pilot_output("LABEL: YES", "LABEL: YES", "format_following") == 1.0


def test_gpu_idle_validation_requires_two_matching_idle_snapshots() -> None:
    first = {
        "gpu": 3,
        "uuid": "GPU-123",
        "memory_used_mib": 0,
        "active_compute_pids": [],
    }
    second = dict(first)

    result = validate_gpu_idle_snapshots(first, second, gpu=3)

    assert result["consecutive_idle_checks"] == 2
    assert result["gpu_uuid"] == "GPU-123"
    with pytest.raises(ValueError, match="active compute"):
        validate_gpu_idle_snapshots(first, {**second, "active_compute_pids": [123]}, gpu=3)
    with pytest.raises(ValueError, match="identity changed"):
        validate_gpu_idle_snapshots(first, {**second, "uuid": "GPU-456"}, gpu=3)


def test_gpu_idle_execution_check_observes_the_gpu_twice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshots = [
        {"gpu": 3, "uuid": "GPU-123", "memory_used_mib": 0, "active_compute_pids": []},
        {"gpu": 3, "uuid": "GPU-123", "memory_used_mib": 0, "active_compute_pids": []},
    ]
    sleeps: list[float] = []
    monkeypatch.setattr(
        posttrain_pilot_runner,
        "_gpu_idle_snapshot",
        lambda index: snapshots.pop(0),
    )

    result = _assert_gpu_idle_twice(3, interval_seconds=15.0, sleep=sleeps.append)

    assert result["consecutive_idle_checks"] == 2
    assert sleeps == [15.0]
    assert snapshots == []


@pytest.mark.parametrize(
    ("decisions", "expected"),
    [
        (["pass", "pass"], "pass"),
        (["pass", "needs_review"], "needs_review"),
        (["pass", "insufficient_evidence"], "insufficient_evidence"),
        (["insufficient_evidence", "hold"], "hold"),
    ],
)
def test_pilot_decision_aggregation_is_conservative(
    decisions: list[str], expected: str
) -> None:
    assert aggregate_pilot_decisions(decisions) == expected


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
        "queue_pending_jobs": 0,
        "queue_running_jobs": 0,
        "queue_source": "/root/prompt_control_lab_runtime/queue_snapshot.json",
        "queue_snapshot_sha256": "sha256:" + "a" * 64,
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


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"queue_pending_jobs": 1}, "pending"),
        ({"queue_running_jobs": 1}, "running"),
        ({"queue_source": ""}, "queue_source"),
        ({"queue_snapshot_sha256": "sha256:bad"}, "queue_snapshot_sha256"),
    ],
)
def test_resource_approval_requires_auditable_queue_snapshot(
    tmp_path: Path,
    overrides: dict[str, object],
    message: str,
) -> None:
    now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    payload: dict[str, object] = {
        "approved": True,
        "queue_clear": True,
        "queue_pending_jobs": 0,
        "queue_running_jobs": 0,
        "queue_source": "/root/prompt_control_lab_runtime/queue_snapshot.json",
        "queue_snapshot_sha256": "sha256:" + "a" * 64,
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


def test_model_provenance_locks_revision_and_detects_cache_tampering(tmp_path: Path) -> None:
    model = tmp_path / "model"
    model.mkdir()
    (model / "config.json").write_text('{"model_type":"qwen2"}', encoding="utf-8")
    (model / "weights.safetensors").write_bytes(b"safe-model-weights")

    written = write_model_provenance(
        model,
        model_id="Qwen/Qwen2.5-0.5B-Instruct",
        revision="a" * 40,
    )
    validated = validate_model_provenance(model)

    assert written == validated
    assert validated["combined_sha256"].startswith("sha256:")
    assert len(validated["files"]) == 2
    (model / "weights.safetensors").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        validate_model_provenance(model)


@pytest.mark.parametrize("revision", ["main", "latest", "not-a-hash", "abc123"])
def test_model_provenance_requires_pinned_commit_revision(
    tmp_path: Path, revision: str
) -> None:
    model = tmp_path / revision.replace("/", "_")
    model.mkdir()
    (model / "config.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="revision"):
        write_model_provenance(
            model,
            model_id="Qwen/Qwen2.5-0.5B-Instruct",
            revision=revision,
        )
