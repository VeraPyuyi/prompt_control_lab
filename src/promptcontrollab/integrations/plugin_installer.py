"""Install local integration templates from packaged resources."""

from __future__ import annotations

import shutil
from importlib import resources
from pathlib import Path
from typing import Any

from promptcontrollab.core.files import JsonDict

PLUGIN_CHOICES = {
    "codex",
    "cursor",
    "claude-code",
    "github-action",
    "deepseek-harness",
    "all",
}


def install_plugin(
    plugin: str,
    *,
    target: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> JsonDict:
    """Install one integration template."""

    if plugin not in PLUGIN_CHOICES:
        msg = f"Unknown plugin `{plugin}`"
        raise ValueError(msg)
    if plugin == "all":
        targets = _all_targets(target)
        installed = [
            install_plugin(name, target=targets[name], force=force, dry_run=dry_run)
            for name in [
                "codex",
                "cursor",
                "claude-code",
                "github-action",
                "deepseek-harness",
            ]
        ]
        return {"plugin": "all", "dry_run": dry_run, "installed": installed}
    destination = target or _default_target(plugin)
    if dry_run:
        return _preview_install(plugin, destination)
    if plugin == "codex":
        _copy_resource_dir("codex_skill", destination, force=force)
    elif plugin == "cursor":
        _copy_resource_file("cursor_rule/prompt_control_lab.mdc", destination, force=force)
    elif plugin == "claude-code":
        _copy_resource_dir("claude_code", destination, force=force)
    elif plugin == "github-action":
        _copy_resource_file("github_action/prompt-control-lab-gate.yml", destination, force=force)
    elif plugin == "deepseek-harness":
        _copy_resource_dir("deepseek_harness", destination, force=force)
    return {"plugin": plugin, "target": str(destination)}


def _preview_install(plugin: str, destination: Path) -> JsonDict:
    if plugin == "codex":
        would_write = _preview_resource_dir("codex_skill", destination)
    elif plugin == "cursor":
        would_write = [str(destination)]
    elif plugin == "claude-code":
        would_write = _preview_resource_dir("claude_code", destination)
    elif plugin == "github-action":
        would_write = [str(destination)]
    elif plugin == "deepseek-harness":
        would_write = _preview_resource_dir("deepseek_harness", destination)
    else:
        msg = f"Unknown plugin `{plugin}`"
        raise ValueError(msg)
    return {
        "plugin": plugin,
        "target": str(destination),
        "dry_run": True,
        "would_write": would_write,
        "would_overwrite": destination.exists(),
    }


def _default_target(plugin: str) -> Path:
    home = Path.home()
    if plugin == "codex":
        return home / ".codex" / "skills" / "prompt_control_lab"
    if plugin == "cursor":
        return home / ".cursor" / "rules" / "prompt_control_lab.mdc"
    if plugin == "claude-code":
        return home / ".prompt_control_lab" / "claude-code"
    if plugin == "github-action":
        return Path.cwd() / ".github" / "workflows" / "prompt-control-lab-gate.yml"
    if plugin == "deepseek-harness":
        return home / ".prompt_control_lab" / "deepseek-harness"
    msg = f"Unknown plugin `{plugin}`"
    raise ValueError(msg)


def _all_targets(target: Path | None) -> dict[str, Path | None]:
    if target is None:
        return {
            "codex": None,
            "cursor": None,
            "claude-code": None,
            "github-action": None,
            "deepseek-harness": None,
        }
    return {
        "codex": target / "codex",
        "cursor": target / "cursor" / "prompt_control_lab.mdc",
        "claude-code": target / "claude-code",
        "github-action": target / "github-action" / "prompt-control-lab-gate.yml",
        "deepseek-harness": target / "deepseek-harness",
    }


def _resource_root() -> Any:
    return resources.files("promptcontrollab.template_data")


def _copy_resource_file(relative: str, destination: Path, *, force: bool) -> None:
    source = _resource_root().joinpath(*relative.split("/"))
    if destination.exists() and not force:
        msg = f"{destination} already exists; pass --force to overwrite."
        raise ValueError(msg)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with resources.as_file(source) as source_path:
        shutil.copyfile(source_path, destination)


def _copy_resource_dir(relative: str, destination: Path, *, force: bool) -> None:
    source = _resource_root().joinpath(relative)
    if destination.exists():
        if not force:
            msg = f"{destination} already exists; pass --force to overwrite."
            raise ValueError(msg)
        if destination.is_file():
            destination.unlink()
        else:
            shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with resources.as_file(source) as source_path:
        for item in source_path.rglob("*"):
            if item.is_dir() or _is_generated_python_cache(item):
                continue
            relative_path = item.relative_to(source_path)
            out = destination / relative_path
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item, out)


def _preview_resource_dir(relative: str, destination: Path) -> list[str]:
    source = _resource_root().joinpath(relative)
    would_write: list[str] = []
    with resources.as_file(source) as source_path:
        for item in source_path.rglob("*"):
            if item.is_dir() or _is_generated_python_cache(item):
                continue
            relative_path = item.relative_to(source_path)
            would_write.append(str(destination / relative_path))
    return sorted(would_write)


def _is_generated_python_cache(path: Path) -> bool:
    """Skip interpreter cache files when installing human-facing templates."""

    return (
        "__pycache__" in path.parts
        or path.suffix in {".pyc", ".pyo"}
        or path.name.endswith("$py.class")
    )
