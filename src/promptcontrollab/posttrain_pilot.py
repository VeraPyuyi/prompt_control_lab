"""Backward-compatible facade for :mod:`promptcontrollab.evidence.posttrain_pilot`."""

from promptcontrollab.evidence.posttrain_pilot import (
    PilotInputs,
    aggregate_pilot_decisions,
    build_sft_pilot_plan,
    canonical_answer_exact_match,
    model_provenance_path,
    paired_checkpoint_statistics,
    score_pilot_output,
    sequence_exact_match,
    token_trajectory_drift,
    training_strategy_argument,
    validate_gpu_idle_snapshots,
    validate_model_provenance,
    validate_resource_approval,
    write_model_provenance,
    write_sft_pilot_plan,
)

__all__ = [
    "PilotInputs",
    "write_model_provenance",
    "model_provenance_path",
    "validate_model_provenance",
    "build_sft_pilot_plan",
    "write_sft_pilot_plan",
    "validate_resource_approval",
    "paired_checkpoint_statistics",
    "training_strategy_argument",
    "sequence_exact_match",
    "canonical_answer_exact_match",
    "score_pilot_output",
    "validate_gpu_idle_snapshots",
    "aggregate_pilot_decisions",
    "token_trajectory_drift",
]
