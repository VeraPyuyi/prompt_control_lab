"""Stable command-line entry points for PromptControlLab."""

from promptcontrollab.cli.app import main
from promptcontrollab.cli.parser import build_parser
from promptcontrollab.cli.runtime import _reconfigure_windows_pipe

__all__ = ["_reconfigure_windows_pipe", "build_parser", "main"]
