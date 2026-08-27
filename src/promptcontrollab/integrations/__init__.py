"""Provider, agent, plugin, UI, and public-demo integrations."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "ProviderError": ("promptcontrollab.integrations.providers", "ProviderError"),
    "ProviderResponse": ("promptcontrollab.integrations.providers", "ProviderResponse"),
    "ProviderSpec": ("promptcontrollab.integrations.providers", "ProviderSpec"),
    "assess_harness_run_acceptance": (
        "promptcontrollab.integrations.harness_integration",
        "assess_harness_run_acceptance",
    ),
    "build_space_bundle": ("promptcontrollab.integrations.hf_space", "build_space_bundle"),
    "call_provider": ("promptcontrollab.integrations.providers", "call_provider"),
    "doctor_harness": ("promptcontrollab.integrations.harness_integration", "doctor_harness"),
    "format_doctor": ("promptcontrollab.integrations.doctor", "format_doctor"),
    "doctor_provider": ("promptcontrollab.integrations.providers", "doctor_provider"),
    "initialize_harness_project": (
        "promptcontrollab.integrations.harness_integration",
        "initialize_harness_project",
    ),
    "install_plugin": ("promptcontrollab.integrations.plugin_installer", "install_plugin"),
    "inspect_provider": ("promptcontrollab.integrations.providers", "inspect_provider"),
    "list_providers": ("promptcontrollab.integrations.providers", "list_providers"),
    "run_doctor": ("promptcontrollab.integrations.doctor", "run_doctor"),
    "run_ecosystem_demo": (
        "promptcontrollab.integrations.ecosystem_demo",
        "run_ecosystem_demo",
    ),
    "write_example_project": (
        "promptcontrollab.integrations.templates",
        "write_example_project",
    ),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Load a public integration symbol without importing optional services."""

    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, symbol_name = target
    value = getattr(import_module(module_name), symbol_name)
    globals()[name] = value
    return value
