"""Local project helpers for the DeepSeek Harness reference integration."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import replace
from importlib import resources
from pathlib import Path
from typing import cast

from promptcontrollab.control_protocol import redact_sensitive
from promptcontrollab.control_workflow import (
    ControlSession,
    append_control_event,
    finalize_control_session,
    perform_preflight,
    start_control_session,
)
from promptcontrollab.files import JsonDict, read_json, read_jsonl, stable_digest, write_json

HARNESS_VERSION = "0.1.1-rc.2"
HARNESS_COMMIT = "b150a551b8d465e31e418e1b2eaf5e79bbb7d28e"
HARNESS_CONFIG_SCHEMA = "prompt_control_lab.deepseek_harness.config.v1"
HARNESS_COMPATIBILITY_SCHEMA = "prompt_control_lab.deepseek_harness.compatibility.v1"

_HIDDEN_KEYS = {
    "analysis",
    "reasoning",
    "reasoning_content",
    "reasoning_text",
    "thinking",
    "thinking_content",
    "chain_of_thought",
    "chainofthought",
    "cot",
    "hidden_reasoning",
    "scratchpad",
    "thought",
    "thoughts",
}
_HIDDEN_KEY_SUFFIXES = (
    "_chain_of_thought",
    "_hidden_reasoning",
    "_reasoning",
    "_reasoning_content",
    "_reasoning_text",
    "_scratchpad",
    "_thinking",
    "_thinking_content",
)
_HIDDEN_KEY_PARTS = {
    "analysis",
    "chainofthought",
    "cot",
    "reasoning",
    "scratchpad",
    "thinking",
    "thought",
    "thoughts",
}
_CONTENT_KEYS = {
    "answer",
    "arguments",
    "body",
    "command",
    "completion",
    "content",
    "delta",
    "input",
    "input_text",
    "instruction",
    "message",
    "messages",
    "output",
    "output_text",
    "prompt",
    "prompt_text",
    "query",
    "raw_input",
    "raw_output",
    "raw_prompt",
    "response",
    "response_text",
    "result",
    "stderr",
    "stdout",
    "text",
    "tool_arguments",
    "tool_output",
    "tool_result",
}
_CONTENT_KEY_SUFFIXES = (
    "_answer",
    "_arguments",
    "_body",
    "_command",
    "_completion",
    "_content",
    "_delta",
    "_input",
    "_instruction",
    "_message",
    "_messages",
    "_output",
    "_prompt",
    "_query",
    "_response",
    "_result",
    "_stderr",
    "_stdout",
    "_text",
)
_PATH_KEYS = {"cwd", "project", "repo", "repository", "workspace"}
_MAX_METADATA_STRING_CHARS = 256
_SECRET_VALUE_RE = re.compile(
    r"(?i)(?:bearer\s+)?(?:sk|key|token|secret)[-_][A-Za-z0-9._-]{6,}"
)


def doctor_harness(project: Path) -> JsonDict:
    """Check the local Harness integration without network access."""

    root = project.resolve()
    integration_root = root / ".promptcontrol"
    checks: JsonDict = {
        "config": _doctor_config(integration_root / "deepseek-harness.json"),
        "compatibility_lock": _doctor_compatibility_lock(
            integration_root / "deepseek-harness.compatibility.json"
        ),
        "python_bridge": _doctor_python_bridge(integration_root / "runs"),
        "node": _doctor_node(),
        "packaged_plugin": _doctor_packaged_plugin(),
    }
    ok = all(
        isinstance(check, dict) and check.get("status") == "ok"
        for check in checks.values()
    )
    return {
        "schema": "prompt_control_lab.deepseek_harness.doctor.v1",
        "project": str(root),
        "offline": True,
        "status": "ok" if ok else "error",
        "checks": checks,
    }


def _doctor_config(path: Path) -> JsonDict:
    try:
        payload = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"status": "error", "path": str(path), "detail": str(exc)}
    valid = (
        payload.get("schema") == HARNESS_CONFIG_SCHEMA
        and payload.get("capture") == "redacted"
        and payload.get("mode") in {"suggest", "gate"}
    )
    return {
        "status": "ok" if valid else "error",
        "path": str(path),
        "schema": payload.get("schema"),
        "capture": payload.get("capture"),
    }


def _doctor_compatibility_lock(path: Path) -> JsonDict:
    try:
        payload = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"status": "error", "path": str(path), "detail": str(exc)}
    harness = payload.get("deepseek_harness")
    bridge = payload.get("bridge")
    valid = (
        payload.get("schema") == HARNESS_COMPATIBILITY_SCHEMA
        and isinstance(harness, dict)
        and harness.get("version") == HARNESS_VERSION
        and harness.get("commit") == HARNESS_COMMIT
        and isinstance(bridge, dict)
        and bridge.get("protocol") == "prompt_control_lab.bridge.v1"
    )
    return {
        "status": "ok" if valid else "error",
        "path": str(path),
        "harness_version": harness.get("version") if isinstance(harness, dict) else None,
        "harness_commit": harness.get("commit") if isinstance(harness, dict) else None,
    }


def _doctor_python_bridge(runs_root: Path) -> JsonDict:
    try:
        from promptcontrollab.control_bridge import ControlBridge

        health = ControlBridge(runs_root).dispatch("health", {})
    except (OSError, TypeError, ValueError) as exc:
        return {"status": "error", "detail": str(exc)}
    valid = (
        health.get("status") == "ok"
        and health.get("protocol") == "prompt_control_lab.bridge.v1"
    )
    return {
        "status": "ok" if valid else "error",
        "protocol": health.get("protocol"),
    }


def _doctor_node() -> JsonDict:
    node = shutil.which("node")
    if node is None:
        return {
            "status": "error",
            "version": None,
            "required": "^22.19.0 || >=24.0.0",
            "detail": "Node.js was not found on PATH.",
        }
    try:
        completed = subprocess.run(
            [node, "--version"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"status": "error", "version": None, "detail": str(exc)}
    version = completed.stdout.strip()
    compatible = completed.returncode == 0 and _node_version_compatible(version)
    return {
        "status": "ok" if compatible else "error",
        "version": version or None,
        "required": "^22.19.0 || >=24.0.0",
    }


def _node_version_compatible(value: str) -> bool:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value.strip())
    if match is None:
        return False
    version = tuple(int(item) for item in match.groups())
    return version >= (24, 0, 0) or (22, 19, 0) <= version < (23, 0, 0)


def _doctor_packaged_plugin() -> JsonDict:
    root = resources.files("promptcontrollab.template_data").joinpath("deepseek_harness")
    required = ["package.json", "compatibility.json", "src/index.ts", "src/bridge.ts"]
    missing = [
        relative
        for relative in required
        if not root.joinpath(*relative.split("/")).is_file()
    ]
    return {
        "status": "ok" if not missing else "error",
        "required_files": required,
        "missing": missing,
    }


def initialize_harness_project(project: Path, *, force: bool = False) -> JsonDict:
    """Write reviewable Harness integration config without changing Cordis automatically."""

    root = project.resolve()
    target = root / ".promptcontrol"
    config_path = target / "deepseek-harness.json"
    snippet_path = target / "deepseek-harness.cordis.yml"
    compatibility_path = target / "deepseek-harness.compatibility.json"
    paths = [config_path, snippet_path, compatibility_path]
    existing = [path for path in paths if path.exists()]
    if existing and not force:
        msg = f"Harness integration file already exists: {existing[0]}"
        raise ValueError(msg)
    target.mkdir(parents=True, exist_ok=True)
    config: JsonDict = {
        "schema": HARNESS_CONFIG_SCHEMA,
        "mode": "suggest",
        "policyPath": ".promptcontrol/guard.policy.yaml",
        "capture": "redacted",
        "feedback": "summary",
        "feedbackMaxChars": 600,
        "autoRecover": False,
        "bridgeFailure": "warn",
        "runsRoot": ".promptcontrol/runs",
        "exposeStatusTool": False,
    }
    compatibility: JsonDict = {
        "schema": HARNESS_COMPATIBILITY_SCHEMA,
        "deepseek_harness": {
            "version": HARNESS_VERSION,
            "commit": HARNESS_COMMIT,
        },
        "bridge": {"protocol": "prompt_control_lab.bridge.v1"},
        "verified": False,
        "note": "Run `pcl harness doctor` after installing the native Cordis plugin.",
    }
    snippet = "\n".join(
        [
            "# Review and merge this plugin entry into the project's Cordis configuration.",
            "prompt-control-lab:",
            "  $plugin: '@prompt-control-lab/deepseek-harness'",
            "  mode: suggest",
            "  policyPath: .promptcontrol/guard.policy.yaml",
            "  capture: redacted",
            "  feedback: summary",
            "  autoRecover: false",
            "  bridgeFailure: warn",
            "",
        ]
    )
    write_json(config_path, config)
    snippet_path.write_text(snippet, encoding="utf-8")
    write_json(compatibility_path, compatibility)
    return {
        "project": str(root),
        "written": [str(path) for path in paths],
        "next_steps": [
            "Install the plugin with `pcl install-plugin deepseek-harness`.",
            "Review deepseek-harness.cordis.yml before merging it into Cordis config.",
            "Run `pcl harness doctor` to verify the local bridge and compatibility lock.",
        ],
    }


def sanitize_harness_event(record: JsonDict, *, capture: str = "redacted") -> JsonDict:
    """Normalize a Harness event while excluding raw content and hidden reasoning by default."""

    if capture != "redacted":
        msg = "Only redacted Harness capture is supported in the local reference integration."
        raise ValueError(msg)
    raw_type = record.get("type", record.get("event_type", "unknown"))
    event_type = _sanitize_string(raw_type) if isinstance(raw_type, str) and raw_type else "unknown"
    raw_sequence = record.get("seq", record.get("sequence", 0))
    sequence = (
        raw_sequence
        if isinstance(raw_sequence, int) and not isinstance(raw_sequence, bool)
        else 0
    )
    raw_payload = record.get("data", record.get("payload", {}))
    payload = cast(JsonDict, raw_payload) if isinstance(raw_payload, dict) else {}
    content = _collect_content(payload)
    safe_payload = _sanitize_mapping(payload)
    if content:
        safe_payload["content_chars"] = len(content)
        safe_payload["content_sha256"] = "sha256:" + stable_digest(content)
    safe = cast(JsonDict, redact_sensitive(safe_payload))
    return {
        "sequence": sequence,
        "event_type": event_type,
        "payload": safe,
    }


def inspect_harness_session(session_path: Path) -> JsonDict:
    """Summarize observable Harness events without returning raw conversation content."""

    records = read_jsonl(session_path)
    safe = [sanitize_harness_event(record) for record in records]
    prompt_hashes: list[str] = []
    guards: list[str] = []
    turns: set[int] = set()
    tool_calls = 0
    request_errors = 0
    for raw, event in zip(records, safe, strict=True):
        event_type = str(event["event_type"])
        prompt = _prompt_from_event(raw)
        if prompt:
            digest = "sha256:" + stable_digest(prompt)
            if digest not in prompt_hashes:
                prompt_hashes.append(digest)
        payload = cast(JsonDict, event["payload"])
        if event_type in {"guard/signal", "guard/timeout"}:
            guard = payload.get("guard")
            if isinstance(guard, str) and guard not in guards:
                guards.append(guard)
        if event_type == "turn/start":
            turn = payload.get("turn")
            if isinstance(turn, int):
                turns.add(turn)
        if event_type in {"tool/call", "tools/pre-execute"}:
            tool_calls += 1
        if event_type == "agent/request-error":
            request_errors += 1
    return {
        "schema": "prompt_control_lab.deepseek_harness.session_summary.v1",
        "source_sha256": "sha256:" + stable_digest(records),
        "event_count": len(records),
        "turns": len(turns),
        "tool_calls": tool_calls,
        "request_errors": request_errors,
        "guard_signals": guards,
        "prompt_hashes": prompt_hashes,
    }


def replay_harness_session(
    session_path: Path,
    *,
    run_dir: Path,
    policy_path: Path | None = None,
    authorization: str = "agent-scoped",
) -> JsonDict:
    """Replay a durable Harness JSONL session into a redacted local control run."""

    records = read_jsonl(session_path)
    prompt = next((value for record in records if (value := _prompt_from_event(record))), None)
    if prompt is None:
        msg = "Harness replay requires at least one user prompt for an honest preflight."
        raise ValueError(msg)
    session_id = _session_id(records) or session_path.stem
    provider, model = _provider_model(records)
    session = start_control_session(
        run_dir=run_dir,
        prompt=prompt,
        authorization=authorization,
        provider=provider,
        model=model,
        agent="deepseek-harness",
        profile="coding",
        policy_path=policy_path,
    )
    metadata = dict(session.run.metadata)
    metadata.update(
        {
            "harness_session_id": session_id,
            "harness_version": HARNESS_VERSION,
            "harness_commit": HARNESS_COMMIT,
            "capture": "redacted",
            "source_session_sha256": "sha256:" + stable_digest(records),
        }
    )
    run = replace(session.run, metadata=metadata)
    write_json(run_dir / "control_run.json", run.to_json())
    session = ControlSession(run_dir=run_dir, run=run)
    perform_preflight(
        session,
        prompt=prompt,
        profile="coding",
        policy_path=policy_path,
    )
    for index, record in enumerate(records, start=1):
        safe = sanitize_harness_event(record)
        source_sequence = safe["sequence"] or index
        append_control_event(
            session,
            event_type=f"harness/{safe['event_type']}",
            payload={
                "source_sequence": source_sequence,
                **cast(JsonDict, safe["payload"]),
            },
            idempotency_key=f"harness:{session_id}:{source_sequence}:{safe['event_type']}",
        )
    status = finalize_control_session(session)
    return {
        **status,
        "harness_session_id": session_id,
        "source": str(session_path.resolve()),
    }


def resolve_harness_report(runs_root: Path, session_or_run_id: str) -> JsonDict:
    """Find a control report by Harness session id or local run id."""

    if not runs_root.exists():
        msg = f"Runs directory does not exist: {runs_root}"
        raise ValueError(msg)
    for path in sorted(runs_root.rglob("control_run.json")):
        payload = read_json(path)
        metadata = payload.get("metadata")
        harness_session = metadata.get("harness_session_id") if isinstance(metadata, dict) else None
        if payload.get("run_id") != session_or_run_id and harness_session != session_or_run_id:
            continue
        run_dir = path.parent.resolve()
        return {
            "run_id": payload.get("run_id"),
            "harness_session_id": harness_session,
            "run_dir": str(run_dir),
            "report_md": _existing_path(run_dir / "report.md"),
            "report_html": _existing_path(run_dir / "report.html"),
            "decision": _existing_path(run_dir / "decision.json"),
        }
    msg = f"No Harness control run matched `{session_or_run_id}` under {runs_root}"
    raise ValueError(msg)


def _sanitize_mapping(value: JsonDict) -> JsonDict:
    result: JsonDict = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key)
        normalized = _normalize_key(key)
        if _is_hidden_key(normalized) or _is_content_key(normalized):
            continue
        if normalized in _PATH_KEYS and isinstance(raw_value, str):
            result[f"{key}_sha256"] = "sha256:" + stable_digest(raw_value)
            continue
        if isinstance(raw_value, dict):
            result[key] = _sanitize_mapping(cast(JsonDict, raw_value))
        elif isinstance(raw_value, list):
            result[key] = [_sanitize_list_item(item) for item in raw_value]
        elif isinstance(raw_value, str):
            result[key] = _sanitize_string(raw_value)
        else:
            result[key] = raw_value
    return result


def _sanitize_list_item(value: object) -> object:
    if isinstance(value, dict):
        return _sanitize_mapping(cast(JsonDict, value))
    if isinstance(value, list):
        return [_sanitize_list_item(item) for item in value]
    if isinstance(value, str):
        return _sanitize_string(value)
    return value


def _collect_content(value: object, *, key: str = "") -> str:
    normalized = _normalize_key(key)
    if _is_hidden_key(normalized):
        return ""
    if isinstance(value, str):
        return value if _is_content_key(normalized) else ""
    if isinstance(value, list):
        return "".join(_collect_content(item, key=key) for item in value)
    if isinstance(value, dict):
        return "".join(
            _collect_content(item, key=str(item_key))
            for item_key, item in value.items()
        )
    return ""


def _normalize_key(value: str) -> str:
    separated = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", value)
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", separated)
    return re.sub(r"[^a-z0-9]+", "_", separated.lower()).strip("_")


def _is_hidden_key(normalized: str) -> bool:
    parts = normalized.split("_")
    return (
        normalized in _HIDDEN_KEYS
        or normalized.endswith(_HIDDEN_KEY_SUFFIXES)
        or any(part in _HIDDEN_KEY_PARTS for part in parts)
    )


def _is_content_key(normalized: str) -> bool:
    return normalized in _CONTENT_KEYS or normalized.endswith(_CONTENT_KEY_SUFFIXES)


def _sanitize_string(value: str) -> str:
    redacted = _SECRET_VALUE_RE.sub("[REDACTED]", value)
    safe = cast(str, redact_sensitive(redacted))
    if len(safe) <= _MAX_METADATA_STRING_CHARS:
        return safe
    return f"[REDACTED length={len(safe)} sha256:{stable_digest(safe)}]"


def _prompt_from_event(record: JsonDict) -> str | None:
    raw_type = record.get("type", record.get("event_type"))
    if raw_type not in {"user/message", "agent/pre-step", "prompt"}:
        return None
    raw_payload = record.get("data", record.get("payload", {}))
    if not isinstance(raw_payload, dict):
        return None
    content = _collect_content(raw_payload)
    return content or None


def _session_id(records: list[JsonDict]) -> str | None:
    for record in records:
        payload = record.get("data", record.get("payload", {}))
        if not isinstance(payload, dict):
            continue
        for key in ("sessionId", "session_id"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _provider_model(records: list[JsonDict]) -> tuple[str | None, str | None]:
    provider: str | None = None
    model: str | None = None
    for record in records:
        payload = record.get("data", record.get("payload", {}))
        if not isinstance(payload, dict):
            continue
        raw_provider = payload.get("provider")
        raw_model = payload.get("model")
        if provider is None and isinstance(raw_provider, str) and raw_provider:
            provider = raw_provider
        if model is None and isinstance(raw_model, str) and raw_model:
            model = raw_model
        if provider is not None and model is not None:
            break
    return provider, model


def _existing_path(path: Path) -> str | None:
    return str(path.resolve()) if path.exists() else None


__all__ = [
    "HARNESS_COMMIT",
    "HARNESS_VERSION",
    "doctor_harness",
    "initialize_harness_project",
    "inspect_harness_session",
    "replay_harness_session",
    "resolve_harness_report",
    "sanitize_harness_event",
]
