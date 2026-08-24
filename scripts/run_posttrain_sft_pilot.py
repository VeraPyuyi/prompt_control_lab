#!/usr/bin/env python3
"""Compatibility wrapper for ``pcl posttrain-pilot`` from a source checkout."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

if __name__ == "__main__":
    cli = importlib.import_module("promptcontrollab.cli")
    raise SystemExit(cli.main(["posttrain-pilot", *sys.argv[1:]]))
