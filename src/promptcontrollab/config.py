"""Backward-compatible facade for :mod:`promptcontrollab.core.config`."""

from promptcontrollab.core.config import (
    find_project_config,
    get_config_bool,
    get_config_float,
    get_config_int,
    get_config_list,
    get_config_path,
    get_config_str,
    load_project_config,
    read_simple_yaml,
)

__all__ = [
    "find_project_config",
    "get_config_bool",
    "get_config_float",
    "get_config_int",
    "get_config_list",
    "get_config_path",
    "get_config_str",
    "load_project_config",
    "read_simple_yaml",
]
