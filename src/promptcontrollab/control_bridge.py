"""Backward-compatible facade for :mod:`promptcontrollab.control.control_bridge`."""

from promptcontrollab.control.control_bridge import (
    ControlBridge,
    InvalidParamsError,
    InvalidRequestError,
    MethodNotFoundError,
    serve_stdio,
)

__all__ = [
    "ControlBridge",
    "InvalidParamsError",
    "InvalidRequestError",
    "MethodNotFoundError",
    "serve_stdio",
]
