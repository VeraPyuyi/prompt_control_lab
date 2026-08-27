"""Provider, agent, plugin, UI, and public-demo integrations."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "call_provider": ("promptcontrollab.providers", "call_provider"),
    "doctor_harness": ("promptcontrollab.harness_integration", "doctor_harness"),
    "doctor_provider": ("promptcontrollab.providers", "doctor_provider"),
    "initialize_harness_project": (
        "promptcontrollab.harness_integration",
        "initialize_harness_project",
    ),
    "install_plugin": ("promptcontrollab.plugin_installer", "install_plugin"),
    "list_providers": ("promptcontrollab.providers", "list_providers"),
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
