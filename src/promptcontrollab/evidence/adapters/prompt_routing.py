"""Prompt routing evidence adapter."""

from promptcontrollab.evidence.adapters.base import GenericMetricAdapter

__all__ = ["PromptRoutingAdapter"]


class PromptRoutingAdapter(GenericMetricAdapter):
    """Normalize direct and indirect prompt-routing summaries."""

    def __init__(self) -> None:
        super().__init__(
            name="prompt_routing",
            interpretation_role="mechanism",
            patterns=(
                "routing/**/*.json",
                "indirect/**/*.json",
                "gaps/**/*.json",
                "**/prompt_routing*.json",
                "**/prompt_routing*.jsonl",
            ),
            metric_names=frozenset(
                {
                    "top_head_share",
                    "direct_share",
                    "indirect_share",
                    "participation",
                    "norm_ratio",
                    "causal_mask_error",
                }
            ),
            explanation=(
                "These metrics separate measured direct and indirect pathways by which prompt "
                "information reaches downstream positions."
            ),
            scope="The studied prompt class, attention blocks, positions, and intervention design.",
            claim_boundary=(
                "Observed routing shares do not establish a universal pathway for all prompts."
            ),
            next_action=(
                "Repeat matched interventions across positions, layers, and prompt classes."
            ),
        )
