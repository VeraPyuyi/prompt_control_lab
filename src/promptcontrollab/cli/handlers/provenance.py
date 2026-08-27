"""Provenance command handlers and terminal formatters."""

from __future__ import annotations

import argparse
import json

from promptcontrollab.core.files import write_json
from promptcontrollab.provenance.model_drift import run_model_drift
from promptcontrollab.provenance.model_identity import detect_model_identity


def _cmd_model_detect(args: argparse.Namespace) -> None:
    """Execute the model detect command handler."""
    sources = sum(value is not None for value in [args.response, args.predictions, args.model])
    if sources != 1:
        msg = "Provide exactly one of --response, --predictions, or --model"
        raise ValueError(msg)
    identity = detect_model_identity(
        provider=args.provider,
        model_id=args.model,
        response_path=args.response,
        predictions_path=args.predictions,
        api_version=args.api_version,
        verify=args.verify,
        request_id=args.request_id,
        request_path=args.request_json,
        request_sha256=args.request_sha256,
        response_sha256=args.response_sha256,
        provider_log_reference=args.provider_log_reference,
        signed_receipt=args.signed_receipt,
    )
    payload = identity.to_json()
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    if args.out is not None:
        write_json(args.out, payload)


def _cmd_model_drift(args: argparse.Namespace) -> None:
    """Execute the model drift command handler."""
    payload = run_model_drift(run_dir=args.run, history_dir=args.history, out_path=args.out)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
