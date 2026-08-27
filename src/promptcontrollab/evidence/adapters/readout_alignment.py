"""Answer readout alignment evidence adapter."""

from promptcontrollab.evidence.adapters.base import GenericMetricAdapter

__all__ = ["ReadoutAlignmentAdapter"]


class ReadoutAlignmentAdapter(GenericMetricAdapter):
    """Normalize local alignment between prompt effects and answer readouts."""

    def __init__(self) -> None:
        super().__init__(
            name="readout_alignment",
            interpretation_role="mechanism",
            patterns=(
                "controllability/**/*.json",
                "centring/**/*.json",
                "common/**/*.json",
                "**/readout_alignment*.json",
                "**/readout_alignment*.jsonl",
            ),
            metric_names=frozenset(
                {
                    "readout_share",
                    "readout_alignment",
                    "readout_norm",
                    "cosine",
                    "first_order_shift",
                    "exact_shift",
                }
            ),
            explanation=(
                "These metrics describe whether measured prompt-induced directions align with "
                "the recorded answer readout."
            ),
            scope="Local readout geometry for the recorded model, layer, task, and answer set.",
            claim_boundary=(
                "Local readout alignment is not a guarantee of correct generated behavior."
            ),
            next_action=(
                "Validate alignment against held-out generated answers and matched controls."
            ),
        )
