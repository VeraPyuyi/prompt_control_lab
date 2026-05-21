"""Build unified agent run manifests."""

from __future__ import annotations

from pathlib import Path

from promptcontrollab.files import JsonDict, read_json, write_json


def build_agent_run_manifest(
    *,
    run_dir: Path,
    audit_dir: Path | None,
    agent: str,
    out_path: Path,
    policy: str | None = None,
) -> JsonDict:
    """Build and write an ``agent_run.json`` manifest."""

    manifest = _read_optional(run_dir / "manifest.json")
    audit_path = (
        audit_dir / "audit_result.json" if audit_dir is not None else run_dir / "audit_result.json"
    )
    audit = _read_optional(audit_path)
    gate_path = run_dir / "gate_result.json"
    gate = _read_optional(gate_path)
    prompt = _prompt_identity(manifest)
    model = _candidate_model(manifest)
    payload: JsonDict = {
        "schema": "prompt_control_lab.agent_run.v1",
        "prompt_hash": prompt.get("prompt_hash"),
        "prompt_id": prompt.get("prompt_id"),
        "prompt_version": prompt.get("prompt_version"),
        "prompt_file": prompt.get("prompt_file"),
        "agent": agent,
        "provider": model.get("provider"),
        "model": model.get("model_id"),
        "policy": policy,
        "decision": gate.get("status"),
        "risk_level": _risk_level(gate, audit),
        "changed_files": audit.get("changed_files", []),
        "tests_run": audit.get("tests_run", []),
        "tests_passed": audit.get("tests_passed"),
        "human_review_required": bool(
            audit.get("human_review_required") or gate.get("status") == "fail"
        ),
        "audit_path": str(audit_path) if audit else None,
        "gate_path": str(gate_path) if gate else None,
    }
    write_json(out_path, payload)
    return payload


def _read_optional(path: Path) -> JsonDict:
    if not path.exists():
        return {}
    return read_json(path)


def _prompt_identity(manifest: JsonDict) -> JsonDict:
    prompt = manifest.get("prompt")
    if isinstance(prompt, dict):
        return prompt
    identity: JsonDict = {}
    for key in ["prompt_hash", "prompt_id", "prompt_version", "prompt_file"]:
        value = manifest.get(key)
        if isinstance(value, str) and value:
            identity[key] = value
    return identity


def _candidate_model(manifest: JsonDict) -> JsonDict:
    candidate = manifest.get("candidate_model")
    if isinstance(candidate, dict):
        return candidate
    model = manifest.get("model")
    if isinstance(model, dict):
        return model
    return {}


def _risk_level(gate: JsonDict, audit: JsonDict) -> str | None:
    if gate.get("status") == "fail":
        return "high"
    if gate.get("status") == "needs_review" or audit.get("human_review_required"):
        return "medium"
    if gate.get("status") == "pass":
        return "low"
    return None
