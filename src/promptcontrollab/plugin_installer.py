"""Backward-compatible facade for :mod:`promptcontrollab.integrations.plugin_installer`."""

from promptcontrollab.integrations.plugin_installer import PLUGIN_CHOICES, install_plugin

__all__ = ["PLUGIN_CHOICES", "install_plugin"]
