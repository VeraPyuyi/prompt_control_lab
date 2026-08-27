"""Backward-compatible facade for :mod:`promptcontrollab.provenance.model_identity`."""

from promptcontrollab.provenance.model_identity import (
    ModelIdentity,
    compare_model_identities,
    detect_model_identity,
    from_declared_model,
    from_predictions_file,
    from_response_file,
    infer_provider,
    is_alias_model,
    model_payload_from_prediction,
    unknown_identity,
    verify_identity,
)

__all__ = [
    "ModelIdentity",
    "compare_model_identities",
    "detect_model_identity",
    "from_declared_model",
    "from_predictions_file",
    "from_response_file",
    "infer_provider",
    "is_alias_model",
    "model_payload_from_prediction",
    "unknown_identity",
    "verify_identity",
]
