"""Shared CLI formatting, path, and artifact helpers."""

from __future__ import annotations

import json
import webbrowser
from pathlib import Path

from promptcontrollab.core.config import (
    get_config_path,
)
from promptcontrollab.core.files import JsonDict, read_json
from promptcontrollab.evaluation.explain import generate_explanation


def _open_html_report(path: Path, *, language: str = "en") -> None:
    """Open a generated HTML report in the user's default browser."""

    report_path = path.resolve()
    if not report_path.exists():
        raise ValueError(f"Report does not exist: {report_path}")
    opened = webbrowser.open(report_path.as_uri())
    if language == "zh":
        if opened:
            print(f"已在浏览器中打开报告: {report_path}")
        else:
            print(f"无法自动打开浏览器, 请手动打开: {report_path}")
    elif opened:
        print(f"Opened report in your browser: {report_path}")
    else:
        print(f"Could not open a browser automatically. Open manually: {report_path}")


def _read_json_if_exists(path: Path) -> JsonDict:
    if not path.exists():
        return {}
    return read_json(path)


def _first_stats_comparison(stats: JsonDict) -> JsonDict:
    comparisons = stats.get("comparisons")
    if isinstance(comparisons, list) and comparisons and isinstance(comparisons[0], dict):
        return comparisons[0]
    return stats if isinstance(stats, dict) else {}


def _format_optional_number(value: object, *, signed: bool = False) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, int | float):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return value
    else:
        return str(value)
    if signed:
        return f"{number:+.3f}"
    return f"{number:.3f}"


def _print_command_payload(payload: object, *, compact: bool) -> None:
    indent = None if compact else 2
    print(json.dumps(payload, indent=indent, ensure_ascii=False, sort_keys=True))


def _path_arg(value: Path | None, config_value: Path | None, name: str) -> Path:
    path = value if value is not None else config_value
    if path is None:
        msg = f"Missing required --{name} argument or config key"
        raise ValueError(msg)
    return path


def _config_path(config: JsonDict, config_path: Path | None, key: str) -> Path | None:
    if config_path is None:
        return None
    return get_config_path(config, key, base_dir=config_path.parent)


def _maybe_refresh_explanation(out_dir: Path, level: str | None) -> None:
    if level is None:
        return
    run_dir = out_dir.parent if out_dir.name == "diagnostics" else out_dir
    generate_explanation(run_dir, level=level)


def _optional_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    return value == "true"
