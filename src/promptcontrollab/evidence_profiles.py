"""Registry for evidence discovery profiles."""

from __future__ import annotations

from dataclasses import dataclass

from promptcontrollab.evidence_adapters import (
    GenericMetricAdapter,
    PromptProjectionAdapter,
    PromptReachabilityAdapter,
    PromptRoutingAdapter,
    PromptStabilityAdapter,
    ReadoutAlignmentAdapter,
)

LEGACY_ADAPTER_NAMES = (
    "agent_episode",
    "deployment_gate",
    "generation_aware",
    "riccati_ass_hyp",
    "selective_risk",
    "soft_hard_tv",
    "turnpike_a800",
)


@dataclass(frozen=True)
class EvidenceProfile:
    """A named evidence discovery and normalization contract."""

    name: str
    manifest_schema: str
    adapter_names: tuple[str, ...]
    adapters: tuple[GenericMetricAdapter, ...] = ()


def evidence_profile_registry() -> dict[str, EvidenceProfile]:
    """Return a fresh registry so callers cannot mutate shared state."""

    prompt_reach_adapters: tuple[GenericMetricAdapter, ...] = (
        PromptReachabilityAdapter(),
        ReadoutAlignmentAdapter(),
        PromptRoutingAdapter(),
        PromptProjectionAdapter(),
        PromptStabilityAdapter(),
    )
    return {
        "peoc-server": EvidenceProfile(
            name="peoc-server",
            manifest_schema="prompt_control_lab.server_evidence_manifest.v1",
            adapter_names=LEGACY_ADAPTER_NAMES,
        ),
        "prompt-reach-v2": EvidenceProfile(
            name="prompt-reach-v2",
            manifest_schema="prompt_control_lab.evidence_manifest.v2",
            adapter_names=tuple(adapter.name for adapter in prompt_reach_adapters),
            adapters=prompt_reach_adapters,
        ),
    }


def get_evidence_profile(name: str) -> EvidenceProfile:
    """Resolve a profile or raise a user-facing error."""

    registry = evidence_profile_registry()
    try:
        return registry[name]
    except KeyError as exc:
        supported = ", ".join(sorted(registry))
        msg = f"Unsupported evidence profile: {name}. Supported profiles: {supported}"
        raise ValueError(msg) from exc
