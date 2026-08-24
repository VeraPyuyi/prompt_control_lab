"""Prompt projection evidence adapter."""

from promptcontrollab.evidence_adapters.base import GenericMetricAdapter


class PromptProjectionAdapter(GenericMetricAdapter):
    """Normalize soft-to-hard projection geometry and deployment gap metrics."""

    def __init__(self) -> None:
        super().__init__(
            name="prompt_projection",
            interpretation_role="boundary",
            patterns=(
                "projection/**/*.json",
                "projection/**/*.jsonl",
                "projection/**/*.pt",
                "projection/**/*.npz",
                "**/prompt_projection*.json",
                "**/prompt_projection*.jsonl",
            ),
            metric_names=frozenset(
                {
                    "block_norm",
                    "latent_norm",
                    "embedding_norm",
                    "magnitude_ratio",
                    "relative_gap",
                    "cosine_to_projection",
                    "at_radius",
                }
            ),
            explanation=(
                "These metrics quantify how a learned continuous prompt changes under hard-token "
                "projection."
            ),
            scope="The recorded soft prompt, tokenizer, embedding table, and projection rule.",
            claim_boundary=(
                "Nearest-token projection is an open-loop deployment approximation, not an "
                "optimal feedback equivalence."
            ),
            next_action="Measure paired soft and deployed hard behavior before release.",
        )
