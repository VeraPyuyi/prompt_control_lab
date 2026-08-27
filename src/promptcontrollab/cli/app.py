"""Application entry point and error boundary for the CLI."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence

from promptcontrollab.cli.handlers.preflight import _format_start_guide
from promptcontrollab.cli.parser import build_parser
from promptcontrollab.cli.runtime import ensure_utf8_for_windows_pipes
from promptcontrollab.core.errors import PromptControlLabError


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and preserve its established error contract."""

    ensure_utf8_for_windows_pipes()
    cli_args = list(argv) if argv is not None else sys.argv[1:]
    if not cli_args:
        print(_format_start_guide("en"))
        return 0
    parser = build_parser()
    args = parser.parse_args(cli_args)
    try:
        args.func(args)
    except (PromptControlLabError, ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"pcl: error: {exc}", file=sys.stderr)
        return 2
    return 0
