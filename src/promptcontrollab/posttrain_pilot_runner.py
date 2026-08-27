"""Backward-compatible facade for :mod:`promptcontrollab.evidence.posttrain_pilot_runner`."""

from promptcontrollab.evidence.posttrain_pilot_runner import (
    CheckpointEvaluation,
    PosttrainPilotError,
    execute_sft_pilot,
)

__all__ = [
    "CheckpointEvaluation",
    "PosttrainPilotError",
    "execute_sft_pilot",
]
