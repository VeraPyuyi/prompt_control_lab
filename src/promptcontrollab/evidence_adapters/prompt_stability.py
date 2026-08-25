"""Prompt training stability evidence adapter."""

from promptcontrollab.evidence_adapters.base import GenericMetricAdapter


class PromptStabilityAdapter(GenericMetricAdapter):
    """Normalize repeated-training and cross-seed prompt stability metrics."""

    def __init__(self) -> None:
        super().__init__(
            name="prompt_stability",
            interpretation_role="stability",
            patterns=(
                "analysis/reproducibility*.json",
                "analysis/training_determinism*.json",
                "analysis/prompt_stability*.json",
                "analysis/prompt_stability*.jsonl",
                "results_replication/**/*.json",
                "results_replication/**/*.jsonl",
                "results_replication_1024/**/*.json",
                "results_replication_1024/**/*.jsonl",
                "**/prompt_stability*.json",
                "**/prompt_stability*.jsonl",
            ),
            metric_names=frozenset(
                {
                    "score_gap",
                    "repeat_score_gap",
                    "cosine",
                    "parameter_cosine",
                    "effective_rank_delta",
                    "seed_count",
                    "reproducibility",
                }
            ),
            explanation=(
                "These metrics characterize whether repeated prompt training reaches similar "
                "scores and parameter or representation directions."
            ),
            scope="The recorded optimizer, initialization, budget, model, task, and seeds.",
            claim_boundary=(
                "Repeatability is algorithm- and budget-specific and is not proof of global "
                "optimization stability."
            ),
            next_action="Repeat matched runs and inspect score and direction agreement together.",
        )
