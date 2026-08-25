"""Prompt reachability evidence adapter."""

from promptcontrollab.evidence_adapters.base import GenericMetricAdapter


class PromptReachabilityAdapter(GenericMetricAdapter):
    """Normalize reachable-subspace and empirical Gramian summaries."""

    def __init__(self) -> None:
        super().__init__(
            name="prompt_reachability",
            interpretation_role="mechanism",
            patterns=(
                "reachable/**/*.json",
                "gramian/**/*.json",
                "reach_length/**/*.json",
                "reach_pos/**/*.json",
                "directed/**/*.json",
                "**/prompt_reachability*.json",
                "**/prompt_reachability*.jsonl",
            ),
            metric_names=frozenset(
                {
                    "effective_rank",
                    "participation_ratio",
                    "gramian_trace",
                    "width",
                    "reachable_radius",
                    "sample_count",
                }
            ),
            explanation=(
                "These metrics characterize the measured size and effective dimensionality of "
                "prompt-induced representation changes."
            ),
            scope="The recorded models, prompt class, layers, tasks, and sampling procedure.",
            claim_boundary=(
                "Empirical effective rank is not literal controllability rank and does not prove "
                "global behavioral reachability."
            ),
            next_action="Compare matched layers, prompt lengths, tasks, and seeds.",
        )
