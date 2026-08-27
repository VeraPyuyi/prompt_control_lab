"""Backward-compatible facade for :mod:`promptcontrollab.evidence.adapters`."""

from promptcontrollab.evidence.adapters import (
    GenericMetricAdapter,
    PromptProjectionAdapter,
    PromptReachabilityAdapter,
    PromptRoutingAdapter,
    PromptStabilityAdapter,
    ReadoutAlignmentAdapter,
)

__all__ = [
    "GenericMetricAdapter",
    "PromptProjectionAdapter",
    "PromptReachabilityAdapter",
    "PromptRoutingAdapter",
    "PromptStabilityAdapter",
    "ReadoutAlignmentAdapter",
]
