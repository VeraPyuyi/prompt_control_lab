"""Optional dependency loaders."""

from __future__ import annotations

import importlib
from types import ModuleType

from promptcontrollab.errors import OptionalDependencyError, optional_dependency_message


def require_module(module_name: str, *, feature: str, extra: str) -> ModuleType:
    """Import an optional module or raise a user-facing error."""

    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        raise OptionalDependencyError(optional_dependency_message(feature, extra)) from exc

