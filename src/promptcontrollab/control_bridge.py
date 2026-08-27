"""Backward-compatible facade for :mod:`promptcontrollab.control.control_bridge`."""

from promptcontrollab.control.control_bridge import (
    BRIDGE_PROTOCOL,
    ControlBridge,
    InvalidParamsError,
    InvalidRequestError,
    MethodNotFoundError,
    serve_stdio,
)

__all__ = [
    "BRIDGE_PROTOCOL",
    "ControlBridge",
    "InvalidParamsError",
    "InvalidRequestError",
    "MethodNotFoundError",
    "serve_stdio",
]
