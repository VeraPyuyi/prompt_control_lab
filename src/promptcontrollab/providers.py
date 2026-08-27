"""Backward-compatible facade for :mod:`promptcontrollab.integrations.providers`."""

from promptcontrollab.integrations.providers import (
    ProviderError,
    ProviderResponse,
    ProviderSpec,
    call_provider,
    doctor_provider,
    inspect_provider,
    list_providers,
)

__all__ = [
    "ProviderError",
    "ProviderResponse",
    "ProviderSpec",
    "call_provider",
    "doctor_provider",
    "inspect_provider",
    "list_providers",
]
