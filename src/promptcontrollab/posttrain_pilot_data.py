"""Backward-compatible facade for :mod:`promptcontrollab.evidence.posttrain_pilot_data`."""

from promptcontrollab.evidence.posttrain_pilot_data import (
    GSM8K_CONFIGURATION,
    GSM8K_DATASET_ID,
    GSM8K_DATASET_REVISION,
    PILOT_SELECTION_SEED,
    load_gsm8k_jsonl,
    prepare_sft_pilot_data,
    prepare_sft_pilot_data_from_huggingface,
)

__all__ = [
    "GSM8K_DATASET_ID",
    "GSM8K_DATASET_REVISION",
    "GSM8K_CONFIGURATION",
    "PILOT_SELECTION_SEED",
    "prepare_sft_pilot_data",
    "prepare_sft_pilot_data_from_huggingface",
    "load_gsm8k_jsonl",
]
