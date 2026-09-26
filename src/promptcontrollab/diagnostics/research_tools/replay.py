"""Self-contained, allowlisted research replay with separate integrity and numeric checks."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import cast

from .common import JsonDict, canonical, digest, number, require_document, text


def compare_values(
    expected: object, actual: object, *, atol: float, rtol: float, path: str = "$"
) -> list[JsonDict]:
    """Compare structure and values without confusing numeric tolerance with byte identity."""
    if type(expected) in (int, float) and type(actual) in (int, float):
        a, b = number(expected, path), number(actual, path)
        if math.isclose(a, b, abs_tol=atol, rel_tol=rtol):
            return []
        return [
            {
                "path": path,
                "expected": expected,
                "actual": actual,
                "reason": "numeric_tolerance_exceeded",
            }
        ]
    if isinstance(expected, dict) and isinstance(actual, dict):
        differences = [
            {"path": f"{path}.{key}", "reason": "missing_or_extra_field"}
            for key in sorted(set(expected) ^ set(actual))
        ]
        return differences + [
            diff
            for key in sorted(set(expected) & set(actual))
            for diff in compare_values(
                expected[key], actual[key], atol=atol, rtol=rtol, path=f"{path}.{key}"
            )
        ]
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return [{"path": path, "reason": "length_mismatch"}]
        return [
            diff
            for index, (left, right) in enumerate(zip(expected, actual, strict=True))
            for diff in compare_values(left, right, atol=atol, rtol=rtol, path=f"{path}[{index}]")
        ]
    if type(expected) is type(actual) and expected == actual:
        return []
    return [
        {"path": path, "expected": expected, "actual": actual, "reason": "type_or_value_mismatch"}
    ]


def _safe_name(value: object) -> str:
    name = text(value, "bundle file name")
    windows, posix = PureWindowsPath(name), PurePosixPath(name)
    if (
        windows.is_absolute()
        or windows.drive
        or posix.is_absolute()
        or ".." in posix.parts
        or "\\" in name
        or ":" in name
        or "\x00" in name
    ):
        raise ValueError("Bundle names must be safe relative POSIX paths")
    return name


def _without_hashes(value: object) -> object:
    """Hash receipts belong to the integrity channel, never numeric tolerances."""
    if isinstance(value, dict):
        return {
            key: _without_hashes(item) for key, item in value.items() if not key.endswith("sha256")
        }
    if isinstance(value, list):
        return [_without_hashes(item) for item in value]
    return value


def _certificate(kind: str, document: JsonDict, directory: Path) -> JsonDict:
    """Recompute an allowlisted local certificate from self-contained saved inputs."""
    directory.mkdir(parents=True, exist_ok=True)
    if kind == "posterior-certificate":
        from promptcontrollab.diagnostics.posterior_certificate import analyze_posterior_certificate

        source = directory / "posterior_input.json"
        source.write_bytes(canonical(document))
        result = analyze_posterior_certificate(input_path=source, out_dir=directory / "result")
    elif kind == "terminal-sensitivity":
        from promptcontrollab.diagnostics.terminal_sensitivity import analyze_terminal_sensitivity

        records = document.get("records")
        if not isinstance(records, list):
            raise ValueError("terminal-sensitivity requires inline records")
        source = directory / "terminal_records.jsonl"
        source.write_bytes(b"".join(canonical(record) + b"\n" for record in records))
        result = analyze_terminal_sensitivity(records_path=source, out_dir=directory / "result")
    elif kind == "green-certificate":
        import numpy as np

        from promptcontrollab.diagnostics.green_certificate import analyze_green_certificate

        arrays = document.get("arrays")
        if (
            not isinstance(arrays, dict)
            or not {"M", "B0", "BN"} <= set(arrays)
            or set(arrays) - {"M", "B0", "BN", "graph_S"}
        ):
            raise ValueError("green-certificate requires numeric inline M, B0, BN arrays")
        converted = {}
        for key, value in arrays.items():
            if not isinstance(value, list) or any(not isinstance(row, list) for row in value):
                raise ValueError("Certificate arrays must be matrices")
            converted[key] = np.array([[number(x, key) for x in row] for row in value], dtype=float)
        source = directory / "surrogate.npz"
        np.savez(source, **converted)
        premises_path = directory / "premises.json"
        premises_path.write_bytes(canonical(document.get("premises", {})))
        result = analyze_green_certificate(
            surrogate_path=source,
            horizons=document.get("horizons", [8, 16, 32]),
            premises_path=premises_path,
            out_dir=directory / "result",
        )
    else:
        raise ValueError("Unsupported certificate kind")

    # These modules put local generated paths in their reports; published replay is portable.
    def sanitize(value: object) -> object:
        if isinstance(value, dict):
            return {key: sanitize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        if isinstance(value, str):
            return value.replace(str(directory), "bundle://certificate").replace(
                directory.as_posix(), "bundle://certificate"
            )
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return value

    return cast(JsonDict, sanitize(result))


def analyze_document(document: JsonDict, out_dir: Path) -> JsonDict:
    """Replay embedded research evidence with separate integrity and numerical checks."""
    from . import _compute

    require_document(document, "research-replay/v1")
    allowed = {
        "schema_version",
        "synthetic",
        "files",
        "checks",
        "tolerances",
        "provenance",
        "evidence_status",
    }
    if set(document) - allowed:
        raise ValueError("Replay manifest rejects commands, external paths, and unknown fields")
    files, checks = document.get("files"), document.get("checks")
    if not isinstance(files, dict) or not files or not isinstance(checks, list) or not checks:
        raise ValueError("Self-contained files and checks are required")
    tolerances = document.get("tolerances", {})
    if not isinstance(tolerances, dict) or set(tolerances) - {"atol", "rtol"}:
        raise ValueError("tolerances accepts only atol and rtol")
    atol = number(tolerances.get("atol", 1e-9), "atol", nonnegative=True)
    rtol = number(tolerances.get("rtol", 1e-7), "rtol", nonnegative=True)
    contents, integrity = {}, []
    for name, entry in files.items():
        _safe_name(name)
        if (
            not isinstance(entry, dict)
            or set(entry) - {"json", "text", "sha256"}
            or ("json" in entry) == ("text" in entry)
        ):
            raise ValueError("Each inline file requires exactly json or text plus optional sha256")
        raw = (
            canonical(entry["json"])
            if "json" in entry
            else text(entry["text"], "inline text").encode("utf-8")
        )
        actual_hash = hashlib.sha256(raw).hexdigest()
        expected_hash = entry.get("sha256")
        if expected_hash is not None and (
            not isinstance(expected_hash, str)
            or len(expected_hash) != 64
            or any(c not in "0123456789abcdef" for c in expected_hash)
        ):
            raise ValueError("sha256 must be 64 lowercase hex characters")
        integrity.append(
            {
                "file": name,
                "actual_sha256": actual_hash,
                "expected_sha256": expected_hash,
                "status": "not_supplied"
                if expected_hash is None
                else "passed"
                if actual_hash == expected_hash
                else "failed",
                "encoding": "canonical_json_utf8" if "json" in entry else "exact_text_utf8",
            }
        )
        contents[name] = entry["json"] if "json" in entry else json.loads(raw)
    numerical, theoretical, result_hashes = [], [], []
    for index, check in enumerate(checks):
        if not isinstance(check, dict) or set(check) - {"kind", "input_file", "expected_file"}:
            raise ValueError("Checks accept only allowlisted kind, input_file, expected_file")
        kind, source_name = check.get("kind"), _safe_name(check.get("input_file"))
        if source_name not in contents:
            raise ValueError("Replay input_file must reference an embedded file")
        if kind in {"posterior-certificate", "terminal-sensitivity", "green-certificate"}:
            actual = _certificate(
                kind, contents[source_name], Path(out_dir) / f"certificate-{index}"
            )
            theoretical.append(
                {
                    "kind": kind,
                    "status": actual.get("check_state", "unknown"),
                    "certificate_level": actual.get("certificate_level"),
                    "claim_scope": "Supplied local surrogate only; no entire-LLM proof",
                    "result": actual,
                }
            )
        elif kind in {"readout", "response", "measurement-value", "transfer"}:
            actual = _compute(kind, contents[source_name], Path(out_dir) / f"recomputed-{index}")
        else:
            raise ValueError("Unknown or recursive replay kind; arbitrary commands are not allowed")
        expected_name = check.get("expected_file")
        differences = None
        if expected_name is not None:
            expected_name = _safe_name(expected_name)
            if expected_name not in contents:
                raise ValueError("expected_file must reference an embedded file")
            expected = contents[expected_name]
            differences = compare_values(
                _without_hashes(expected), _without_hashes(actual), atol=atol, rtol=rtol
            )
            result_hashes.append(
                {
                    "kind": kind,
                    "input_file": source_name,
                    "expected_sha256": digest(expected),
                    "actual_sha256": digest(actual),
                    "status": "passed" if digest(expected) == digest(actual) else "failed",
                    "encoding": "canonical_json_utf8; exact bytes independently of tolerance",
                }
            )
        numerical.append(
            {
                "kind": kind,
                "input_file": source_name,
                "expected_file": expected_name,
                "status": "not_supplied"
                if differences is None
                else "passed"
                if not differences
                else "failed",
                "differences": differences,
                "result": actual,
            }
        )
    statuses = [row["status"] for row in integrity + result_hashes]
    return {
        "schema_version": "research-replay-result/v1",
        "kind": "replay",
        "synthetic": document["synthetic"],
        "integrity": {
            "status": "failed"
            if "failed" in statuses
            else "passed"
            if all(x == "passed" for x in statuses)
            else "partial",
            "files": integrity,
            "recomputed_result_hashes": result_hashes,
        },
        "numerical_replay": {"tolerances": {"atol": atol, "rtol": rtol}, "checks": numerical},
        "theoretical_checks": {
            "status": "not_requested" if not theoretical else "evaluated_local_premises",
            "checks": theoretical,
        },
        "claim_scope": (
            "Integrity, numerical agreement, and local theoretical conditions are independent "
            "checks. No commands or pickle files are executed."
        ),
    }
