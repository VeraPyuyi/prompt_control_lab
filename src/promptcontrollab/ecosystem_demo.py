"""Backward-compatible facade for :mod:`promptcontrollab.integrations.ecosystem_demo`."""

from promptcontrollab.integrations.ecosystem_demo import (
    ASSET_SPECS,
    DEMO_SPECS,
    EcosystemDemoSpec,
    PromptOptimizerAssetSpec,
    run_ecosystem_demo,
    write_ecosystem_scorecard,
)

__all__ = [
    "ASSET_SPECS",
    "DEMO_SPECS",
    "EcosystemDemoSpec",
    "PromptOptimizerAssetSpec",
    "run_ecosystem_demo",
    "write_ecosystem_scorecard",
]
