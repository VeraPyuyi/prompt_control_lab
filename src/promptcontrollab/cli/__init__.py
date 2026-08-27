"""Stable command-line entry points for PromptControlLab."""

from promptcontrollab.cli.legacy import (
    _reconfigure_windows_pipe,
    build_parser,
    main,
)

__all__ = ["_reconfigure_windows_pipe", "build_parser", "main"]
