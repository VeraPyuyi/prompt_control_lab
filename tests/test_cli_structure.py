"""Architecture contracts for the modular PromptControlLab CLI."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from pathlib import Path
from typing import Any

CLI_ROOT = Path(__file__).parents[1] / "src" / "promptcontrollab" / "cli"
CLI_DOMAINS = (
    "preflight",
    "evaluation",
    "control",
    "provenance",
    "audit",
    "evidence",
    "diagnostics",
    "integrations",
)
CLI_PARSER_SNAPSHOT_SHA256 = "62a1156f63f0fd05767e1e3de37d5cb01d4499281084bb7f6e0f8517583552c5"


def _normalize_parser_value(value: Any) -> Any:
    """Convert argparse values into stable JSON-compatible data."""

    if callable(value):
        return {"callable": getattr(value, "__name__", type(value).__name__)}
    if isinstance(value, Path):
        if value.is_absolute() and value.resolve(strict=False) == Path.cwd().resolve(
            strict=False
        ):
            return {"path": "<cwd>"}
        return {"path": value.as_posix()}
    if isinstance(value, type):
        return {"type": f"{value.__module__}.{value.__qualname__}"}
    if isinstance(value, dict):
        return {
            str(key): _normalize_parser_value(item)
            for key, item in sorted(value.items(), key=lambda entry: str(entry[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_parser_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return repr(value)


def _parser_snapshot(parser: argparse.ArgumentParser) -> dict[str, Any]:
    """Capture ordered parser metadata without implementation module names."""

    result: dict[str, Any] = {
        "prog": parser.prog,
        "description": parser.description,
        "epilog": parser.epilog,
        "defaults": _normalize_parser_value(parser._defaults),
        "actions": [],
    }
    actions: list[dict[str, Any]] = result["actions"]
    for action in parser._actions:
        item: dict[str, Any] = {
            "class": type(action).__name__,
            "option_strings": list(action.option_strings),
            "dest": action.dest,
            "nargs": _normalize_parser_value(action.nargs),
            "const": _normalize_parser_value(action.const),
            "default": _normalize_parser_value(action.default),
            "type": _normalize_parser_value(action.type),
            "choices": _normalize_parser_value(action.choices),
            "required": action.required,
            "help": action.help,
            "metavar": _normalize_parser_value(action.metavar),
        }
        if isinstance(action, argparse._SubParsersAction):
            item["choices"] = list(action.choices)
            item["commands"] = [
                {name: _parser_snapshot(subparser)} for name, subparser in action.choices.items()
            ]
        actions.append(item)
    return result


def test_cli_uses_domain_command_registrars() -> None:
    """Require one command registrar for every canonical product domain."""

    for domain in CLI_DOMAINS:
        module = importlib.import_module(f"promptcontrollab.cli.commands.{domain}")
        assert callable(module.register_commands), domain
        importlib.import_module(f"promptcontrollab.cli.handlers.{domain}")


def test_cli_has_no_monolithic_legacy_implementation() -> None:
    """Prevent the removed monolithic CLI from returning."""

    assert not (CLI_ROOT / "legacy.py").exists()


def test_cli_implementation_files_stay_below_size_limit() -> None:
    """Keep every CLI implementation file below the agreed hard limit."""

    oversized = {
        path.relative_to(CLI_ROOT).as_posix(): len(path.read_text(encoding="utf-8").splitlines())
        for path in CLI_ROOT.rglob("*.py")
        if len(path.read_text(encoding="utf-8").splitlines()) > 1500
    }
    assert oversized == {}


def test_cli_doctor_uses_integration_domain() -> None:
    """Keep the cross-domain doctor service outside the core package."""

    source = "\n".join(path.read_text(encoding="utf-8") for path in CLI_ROOT.rglob("*.py"))
    assert "promptcontrollab.core.doctor" not in source
    assert "promptcontrollab.integrations.doctor" in source


def test_cli_public_api_remains_narrow() -> None:
    """Expose only the three supported Python entry points."""

    cli = importlib.import_module("promptcontrollab.cli")
    assert cli.__all__ == ["_reconfigure_windows_pipe", "build_parser", "main"]


def test_cli_parser_contract_matches_pre_split_snapshot() -> None:
    """Preserve command order, arguments, defaults, help, and handlers."""

    cli = importlib.import_module("promptcontrollab.cli")
    payload = json.dumps(_parser_snapshot(cli.build_parser()), ensure_ascii=False, indent=2) + "\n"
    assert hashlib.sha256(payload.encode("utf-8")).hexdigest() == CLI_PARSER_SNAPSHOT_SHA256


def test_cli_parser_snapshot_normalizes_paths_across_platforms() -> None:
    """Keep native path separators out of the portable parser contract."""

    assert _normalize_parser_value(Path("runs") / "quick") == {"path": "runs/quick"}
