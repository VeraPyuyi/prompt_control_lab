"""Build unified agent run manifests."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
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
    repo = audit.get("repo")
    policy_payload, warnings = _policy_detail(policy)
    risk_level = _risk_level(gate, audit)
    review_required = bool(
        audit.get("human_review_required")
        or gate.get("status") in {"fail", "needs_review"}
        or risk_level in {"high", "medium"}
    )
    payload: JsonDict = {
        "schema": "prompt_control_lab.agent_run.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "prompt_hash": prompt.get("prompt_hash"),
        "prompt_id": prompt.get("prompt_id"),
        "prompt_version": prompt.get("prompt_version"),
        "prompt_file": prompt.get("prompt_file"),
        "prompt": prompt,
        "agent": agent,
        "provider": model.get("provider"),
        "model": model.get("model_id"),
        "policy": policy,
        "policy_detail": policy_payload,
        "guard": _read_optional(run_dir / "guard_result.json"),
        "gate": gate,
        "audit": audit,
        "decision": gate.get("status"),
        "risk_level": risk_level,
        "changed_files": audit.get("changed_files", []),
        "tests_run": audit.get("tests_run", []),
        "tests_passed": audit.get("tests_passed"),
        "human_review_required": review_required,
        "review_required": review_required,
        "repo": repo if isinstance(repo, str) else None,
        "commit_before": audit.get("before"),
        "commit_after": audit.get("after"),
        "audit_path": str(audit_path) if audit else None,
        "gate_path": str(gate_path) if gate else None,
        "warnings": warnings,
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
    if (
        audit.get("secret_findings")
        or audit.get("dangerous_paths")
        or audit.get("workflow_files_changed")
        or audit.get("deleted_test_files")
    ):
        return "high"
    if gate.get("status") == "fail":
        return "high"
    if gate.get("status") == "needs_review" or audit.get("human_review_required"):
        return "medium"
    if gate.get("status") == "pass":
        return "low"
    return None


def _policy_detail(policy: str | None) -> tuple[JsonDict, list[str]]:
    if not policy:
        return {}, []
    payload: JsonDict = {
        "id": policy,
        "policy_file": policy,
        "path": policy,
        "exists": False,
    }
    warnings: list[str] = []
    path = Path(policy)
    if path.exists():
        sha256 = _sha256_file(path)
        payload["policy_hash"] = sha256
        payload["sha256"] = sha256
        payload["exists"] = True
    else:
        warnings.append(f"Policy file was not found: {policy}")
    return payload, warnings


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"
