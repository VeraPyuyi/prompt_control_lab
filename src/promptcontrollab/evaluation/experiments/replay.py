"""Offline, bounded replay of portable experiment bundles from raw saved outputs."""

# Long bilingual report prose and HTML templates preserve intentional punctuation.
# ruff: noqa: E501, RUF001

from __future__ import annotations

import copy
import csv
import hashlib
import html
import io
import json
import math
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, cast

from promptcontrollab.core.files import stable_digest
from promptcontrollab.diagnostics.research_tools.replay import compare_values
from promptcontrollab.evaluation.metrics import score_output

from .assessment import assess
from .models import ExperimentSpec, model_config
from .runtime import _usage, output_quality
from .storage import configured_secrets, redact, snapshot_hash

JsonDict = dict[str, Any]
MAX_BUNDLE_BYTES = 100 * 1024 * 1024
MAX_BUNDLE_FILES = 10000
ATOL, RTOL = 1e-10, 1e-8
_FILES = {
    "spec.json",
    "data.json",
    "split.json",
    "job.json",
    "manifest.json",
    "events.jsonl",
    "bundle_receipts.json",
}
_DIRS = {"calls", "records", "checkpoints", "report"}


def _name(value: str) -> str:
    clean = value.rstrip("/")
    path, windows = PurePosixPath(clean), PureWindowsPath(clean)
    if (
        not clean
        or path.is_absolute()
        or windows.drive
        or ".." in path.parts
        or "\\" in clean
        or ":" in clean
        or "\x00" in clean
        or path.as_posix() != clean
        or clean == "."
    ):
        raise ValueError("Bundle contains an unsafe path")
    return clean


def _load_bundle(source: Path) -> tuple[dict[str, bytes], str]:
    """Read an allowlisted bundle in memory with bounded sizes and safe paths."""
    raw: dict[str, bytes] = {}
    total = 0
    if source.is_dir():
        root = source.resolve()
        for path in sorted(root.rglob("*")):
            if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                raise ValueError("Directory bundles must not contain symlinks or junctions")
            if not path.resolve().is_relative_to(root):
                raise ValueError("Directory bundle entry escapes its root")
            if not path.is_file():
                continue
            relative = _name(path.relative_to(root).as_posix())
            # An exported job directory may also contain its own ZIP and replay outputs.
            if relative not in _FILES and PurePosixPath(relative).parts[0] not in _DIRS:
                continue
            total += path.stat().st_size
            if total > MAX_BUNDLE_BYTES or len(raw) >= MAX_BUNDLE_FILES:
                raise ValueError("Bundle exceeds the byte or file-count limit")
            with path.open("rb") as stream:
                data = stream.read(MAX_BUNDLE_BYTES + 1)
            if len(data) > MAX_BUNDLE_BYTES or len(data) != path.stat().st_size:
                raise ValueError("Bundle entry changed or exceeds the byte limit")
            raw[relative] = data
        kind = "directory"
    else:
        if not source.is_file() or not zipfile.is_zipfile(source):
            raise ValueError("Supply an experiment ZIP or exported job directory")
        try:
            with zipfile.ZipFile(source) as archive:
                entries = archive.infolist()
                if len(entries) > MAX_BUNDLE_FILES:
                    raise ValueError("ZIP exceeds the file-count limit")
                folded: set[str] = set()
                for entry in entries:
                    relative = _name(entry.orig_filename)
                    if relative.casefold() in folded:
                        raise ValueError("ZIP contains duplicate or case-colliding paths")
                    folded.add(relative.casefold())
                    mode = (entry.external_attr >> 16) & 0xFFFF
                    filetype = stat.S_IFMT(mode)
                    if stat.S_ISLNK(mode) or filetype not in (0, stat.S_IFREG, stat.S_IFDIR):
                        raise ValueError("ZIP symlinks and special file entries are forbidden")
                    if entry.flag_bits & 1:
                        raise ValueError("Encrypted ZIP entries are unsupported")
                    if entry.is_dir():
                        continue
                    total += entry.file_size
                    if entry.file_size < 0 or total > MAX_BUNDLE_BYTES:
                        raise ValueError("ZIP exceeds the uncompressed byte limit")
                    with archive.open(entry) as stream:
                        data = stream.read(MAX_BUNDLE_BYTES + 1)
                    if len(data) != entry.file_size or len(data) > MAX_BUNDLE_BYTES:
                        raise ValueError("ZIP entry exceeds its declared size or byte limit")
                    raw[relative] = data
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as error:
            raise ValueError("ZIP could not be safely read") from error
        kind = "zip"
    if "spec.json" not in raw:
        roots = {name.rsplit("/", 1)[0] for name in raw if name.endswith("/spec.json")}
        if len(roots) != 1:
            raise ValueError("Bundle must contain exactly one experiment snapshot")
        prefix = roots.pop() + "/"
        if any(not name.startswith(prefix) for name in raw):
            raise ValueError("ZIP contains files outside its single experiment root")
        raw = {name[len(prefix) :]: data for name, data in raw.items()}
    if any(name not in _FILES and PurePosixPath(name).parts[0] not in _DIRS for name in raw):
        raise ValueError("Bundle contains files outside the experiment export allowlist")
    if not {"spec.json", "data.json", "split.json", "job.json"} <= raw.keys():
        raise ValueError("Bundle is missing spec, data, split or job snapshots")
    return raw, kind


def _reject_constant(value: str) -> None:
    raise ValueError(f"Nonfinite JSON constant is forbidden: {value}")


def _json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("Nonfinite JSON number is forbidden")
    return parsed


def _json(data: bytes, label: str) -> JsonDict:
    try:
        value = json.loads(
            data.decode("utf-8-sig"), parse_constant=_reject_constant, parse_float=_json_float
        )
    except (ValueError, UnicodeError) as error:
        raise ValueError(f"Invalid JSON in bundle member {label}") from error
    if not isinstance(value, dict):
        raise ValueError(f"Bundle member {label} must contain a JSON object")
    return value


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _digest_check(name: str, expected: object, actual: str) -> JsonDict:
    return {
        "name": name,
        "expected": expected,
        "actual": actual,
        "status": "unavailable"
        if expected is None
        else "passed"
        if expected == actual
        else "failed",
    }


def _integrity(
    files: dict[str, bytes], spec: JsonDict, data: JsonDict, split: JsonDict, job: JsonDict
) -> JsonDict:
    """Check saved snapshot and exact-byte receipts without asserting authenticity."""
    manifest = _json(files["manifest.json"], "manifest.json") if "manifest.json" in files else {}
    checks = [
        _digest_check("job.snapshot_hash", job.get("snapshot_hash"), snapshot_hash(spec)),
        _digest_check("manifest.snapshot_hash", manifest.get("snapshot_hash"), snapshot_hash(spec)),
        _digest_check("manifest.data_hash", manifest.get("data_hash"), snapshot_hash(data)),
        _digest_check("manifest.split_hash", manifest.get("split_hash"), snapshot_hash(split)),
    ]
    covered: set[str] = set()
    artifacts = job.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValueError("job.artifacts must be a list")
    for artifact in artifacts:
        if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str):
            raise ValueError("Invalid report artifact receipt")
        path = _name(artifact["path"])
        check = _digest_check(
            f"artifact:{path}",
            artifact.get("sha256"),
            _hash(files[path]) if path in files else "missing",
        )
        if path not in files:
            check["status"] = "failed"
        elif artifact.get("sha256") is not None:
            covered.add(path)
        if artifact.get("bytes") is not None and path in files:
            check["size_matches"] = artifact["bytes"] == len(files[path])
            if not check["size_matches"]:
                check["status"] = "failed"
        checks.append(check)
    receipt = files.get("bundle_receipts.json")
    if receipt is not None:
        document = _json(receipt, "bundle_receipts.json")
        hashes = document.get("files")
        if document.get("schema_version") != "experiment-bundle-receipts/v1" or not isinstance(
            hashes, dict
        ):
            raise ValueError("Unsupported bundle receipt schema")
        for name, expected in sorted(hashes.items()):
            path = _name(name)
            if path == "bundle_receipts.json":
                raise ValueError("Bundle receipt must exclude its own bytes")
            if not isinstance(expected, str) or not re.fullmatch("[0-9a-f]{64}", expected):
                raise ValueError("Bundle receipt hashes must be lowercase SHA256 values")
            check = _digest_check(
                f"file:{path}", expected, _hash(files[path]) if path in files else "missing"
            )
            checks.append(check)
            if path in files:
                covered.add(path)
    names = set(files) - {"bundle_receipts.json"}
    statuses = [row["status"] for row in checks]
    return {
        "status": "failed"
        if "failed" in statuses
        else "passed"
        if names <= covered and "unavailable" not in statuses
        else "partial",
        "checks": checks,
        "covered_files": sorted(covered),
        "uncovered_files": sorted(names - covered),
        "receipt_self_hash": _hash(receipt) if receipt is not None else None,
        "external_authenticity_verified": False,
        "scope": "Internal exact-byte and snapshot consistency only; self-contained hashes do not authenticate a source or a freeze date.",
    }


def _records(files: dict[str, bytes], phase: str) -> tuple[dict[str, list[JsonDict]], str]:
    records: dict[str, list[JsonDict]] = {"baseline": [], "candidate": []}
    originals = [
        (name, _json(data, name))
        for name, data in sorted(files.items())
        if name.startswith("records/") and name.endswith(".json")
    ]
    if originals:
        for _, row in originals:
            if row.get("phase") == phase and row.get("name") in records:
                records[row["name"]].append(row)
        return records, "original_per_item_records"
    if "report/records.json" in files:
        report = _json(files["report/records.json"], "report/records.json")
        for arm in records:
            if not isinstance(report.get(arm), list) or any(
                not isinstance(row, dict) for row in report[arm]
            ):
                raise ValueError("Invalid report record arrays")
            records[arm] = report[arm]
        return records, "report_record_fallback"
    return records, "no_saved_records"


def _finite(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        converted = float(value)
    except OverflowError:
        return None
    return converted if math.isfinite(converted) and converted >= 0 else None


def _ledger_budget(
    spec: JsonDict, job: JsonDict, calls: list[JsonDict], record_count: int
) -> tuple[JsonDict, str]:
    """Reconstruct known call usage and retain uncertainty in missing cost receipts."""
    saved = job.get("budget")
    budget = copy.deepcopy(saved) if isinstance(saved, dict) else {"limits": spec["budget"]}
    if not calls and record_count and spec["operation"] != "import":
        budget.update(
            calls=None,
            known_cost=None,
            unknown_cost_calls=None,
            charged_output_tokens=None,
            reserved_cost=None,
            output_usage_complete=False,
        )
        return budget, "unavailable_missing_call_ledger"
    known_output, charged_output, known_cost, charged_cost = [], [], [], []
    unknown_cost = 0
    output_complete = True
    rates = [
        _finite(spec["budget"].get(key))
        for key in ("input_cost_per_million", "output_cost_per_million")
    ]
    for call in calls:
        usage = _usage(call.get("usage"))
        if usage["output_tokens"] is not None:
            known_output.append(usage["output_tokens"])
        else:
            output_complete = False
        charge = (
            usage["output_tokens"]
            if usage["output_tokens"] is not None
            else _finite(call.get("reserved_output_tokens"))
        )
        charged_output.append(charge)
        if all(value is not None for value in rates) and all(
            value is not None for value in usage.values()
        ):
            actual = (
                usage["input_tokens"] * rates[0] + usage["output_tokens"] * rates[1]
            ) / 1_000_000
            known_cost.append(actual)
            charged_cost.append(actual)
        else:
            unknown_cost += 1
            charged_cost.append(_finite(call.get("reserved_cost")))
    complete = (
        not unknown_cost
        and output_complete
        and all(value is not None for value in charged_output + charged_cost)
    )
    budget.update(
        calls=len(calls),
        charged_output_tokens=sum(value for value in charged_output if value is not None)
        if all(value is not None for value in charged_output)
        else None,
        known_output_tokens=sum(known_output),
        output_usage_complete=output_complete,
        known_cost=math.fsum(known_cost),
        unknown_cost_calls=unknown_cost,
        reserved_cost=math.fsum(value for value in charged_cost if value is not None),
        limits=spec["budget"],
        concurrency_limit=spec["max_concurrency"],
    )
    return budget, "recomputed_known_fields" if complete else "partial_unknown_usage_or_prices"


def _premises(
    spec: JsonDict, split: JsonDict, files: dict[str, bytes], calls: list[JsonDict]
) -> tuple[JsonDict, JsonDict]:
    """Check the saved partition and candidate lock against local recorded evidence."""
    from .engine import make_experiment_split

    expected = make_experiment_split(spec)
    checks = [
        {
            "name": "immutable_split_matches_seeded_group_partition",
            "status": "passed" if split == expected else "failed",
        }
    ]
    selected = spec["candidate"]
    if spec["operation"] == "optimize":
        selection = (
            _json(files["checkpoints/selection.json"], "checkpoints/selection.json")
            if "checkpoints/selection.json" in files
            else None
        )
        if selection is None:
            checks.append({"name": "selection_frozen_before_withheld", "status": "unavailable"})
        else:
            selected = model_config(selection.get("candidate"), "frozen_candidate")
            same_settings = {key: value for key, value in selected.items() if key != "prompt"} == {
                key: value for key, value in spec["baseline"].items() if key != "prompt"
            }
            checks.append(
                {
                    "name": "frozen_candidate_hash_and_model_settings",
                    "status": "passed"
                    if same_settings and snapshot_hash(selected) == selection.get("candidate_hash")
                    else "failed",
                }
            )
            frozen = _finite(selection.get("frozen_at"))
            times = [
                _finite(call.get("started_at")) for call in calls if call.get("phase") == "withheld"
            ]
            checks.append(
                {
                    "name": "declared_freeze_precedes_saved_withheld_calls",
                    "status": "unavailable"
                    if frozen is None or not times or any(value is None for value in times)
                    else "passed"
                    if all(frozen <= value for value in times if value is not None)
                    else "failed",
                }
            )
            optimization = selection.get("optimization", {})
            checks.append(
                {
                    "name": "complete_validation_evidence_declared",
                    "status": "passed"
                    if isinstance(optimization, dict)
                    and optimization.get("selection_complete") is True
                    else "unavailable",
                }
            )
    else:
        checks.append({"name": "untouched_generalization_claim", "status": "not_applicable"})
    states = [check["status"] for check in checks]
    return selected, {
        "status": "failed"
        if "failed" in states
        else "partial"
        if "unavailable" in states
        else "passed",
        "checks": checks,
        "temporal_independence_verified": False,
        "scope": "Local partition, locked candidate and declared chronology checks; no external independence or model-wide theorem is certified.",
    }


def _rescore(
    spec: JsonDict,
    rows: dict[str, list[JsonDict]],
    phase: str,
    ids: list[str],
    calls: list[JsonDict],
    selected: JsonDict,
) -> tuple[dict[str, list[JsonDict]], list[JsonDict], list[JsonDict]]:
    """Rescore saved text and verify its linkage to requests or imported predictions."""
    tasks = {task["id"]: task for task in spec["data"]}
    by_call = {call.get("call_id"): call for call in calls}
    if len(by_call) != len(calls) or None in by_call:
        raise ValueError("Call receipts require unique nonmissing call IDs")
    updated: dict[str, list[JsonDict]] = {"baseline": [], "candidate": []}
    score_checks, links = [], []
    for arm in updated:
        seen = set()
        config = spec["baseline"] if arm == "baseline" else selected
        for source in sorted(rows[arm], key=lambda value: str(value.get("id"))):
            item = source.get("id")
            if item not in tasks or item not in ids or item in seen:
                raise ValueError("Saved records contain duplicate or out-of-scope task IDs")
            seen.add(item)
            task = tasks[item]
            row = copy.deepcopy(source)
            output, status = row.get("output"), row.get("status", "missing")
            if status == "completed" and not isinstance(output, str):
                status = "missing"
            row.update(
                id=item,
                name=arm,
                phase=phase,
                status=status,
                expected=task["expected"],
                slice=task["slice"],
                score=score_output(output, task["expected"], spec["metric"])
                if status == "completed" and isinstance(output, str)
                else None,
                output_status=output_quality(output, spec["metric"])
                if status == "completed" and isinstance(output, str)
                else "unavailable",
            )
            differences = compare_values(source.get("score"), row["score"], atol=ATOL, rtol=RTOL)
            score_checks.append(
                {
                    "arm": arm,
                    "id": item,
                    "status": "unavailable"
                    if "score" not in source
                    else "passed"
                    if not differences
                    else "failed",
                    "original_score": source.get("score"),
                    "recomputed_score": row["score"],
                }
            )
            call = by_call.get(source.get("call_id"))
            if call is not None:
                prompt = (
                    config["prompt"].replace("{input}", task["input"])
                    if "{input}" in config["prompt"]
                    else f"{config['prompt']}\n\n{task['input']}"
                    if config["prompt"]
                    else task["input"]
                )
                agrees = call.get("output") == source.get("output") and call.get(
                    "status"
                ) == source.get("status")
                metadata_checks = [
                    call.get("config_hash") == snapshot_hash(config).removeprefix("sha256:"),
                    call.get("prompt_hash") == stable_digest(prompt).removeprefix("sha256:"),
                ]
                links.append(
                    {
                        "arm": arm,
                        "id": item,
                        "status": "passed" if agrees and all(metadata_checks) else "failed",
                        "scope": "saved output/status and request hash linkage",
                    }
                )
            elif spec["operation"] == "import":
                prediction = next(
                    (value for value in spec["predictions"][arm] if value["id"] == item), None
                )
                imported_output = (
                    prediction.get("output", prediction.get("output_text")) if prediction else None
                )
                imported_status = "completed" if prediction else "missing"
                if prediction and (
                    prediction.get("error")
                    or prediction.get("status")
                    in {
                        "failed",
                        "error",
                        "service_error",
                        "uncertain",
                        "timeout",
                        "rate_limited",
                        "missing",
                    }
                ):
                    imported_status = (
                        "missing" if prediction.get("status") == "missing" else "service_error"
                    )
                if imported_status == "completed" and not isinstance(imported_output, str):
                    imported_status = "missing"
                links.append(
                    {
                        "arm": arm,
                        "id": item,
                        "status": "passed"
                        if imported_output == source.get("output")
                        and imported_status == source.get("status")
                        else "failed",
                        "scope": "immutable imported prediction output and transport status",
                    }
                )
            else:
                links.append(
                    {
                        "arm": arm,
                        "id": item,
                        "status": "unavailable",
                        "scope": "missing call receipt",
                    }
                )
            updated[arm].append(row)
    return updated, score_checks, links


def _assessment_differences(
    expected: JsonDict, actual: JsonDict
) -> tuple[list[JsonDict], list[JsonDict]]:
    """Compare persisted fields while separating numerical changes from new metadata."""
    numerical: list[JsonDict] = []
    metadata: list[JsonDict] = []
    missing = object()

    def numeric(value: object) -> bool:
        if type(value) in (int, float):
            return True
        if isinstance(value, dict):
            return any(numeric(item) for item in value.values())
        return isinstance(value, list) and any(numeric(item) for item in value)

    def visit(left: Any, right: Any, path: str) -> None:
        if isinstance(left, dict) and isinstance(right, dict):
            for key, value in left.items():
                visit(value, right.get(key, missing), f"{path}.{key}")
            return
        if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
            for index, (first, second) in enumerate(zip(left, right, strict=True)):
                visit(first, second, f"{path}[{index}]")
            return
        differences = (
            [{"path": path, "expected": left, "reason": "missing_original_field"}]
            if right is missing
            else compare_values(left, right, atol=ATOL, rtol=RTOL, path=path)
        )
        (numerical if numeric(left) or numeric(right) else metadata).extend(differences)

    visit(expected, actual, "$")
    return numerical, metadata


def _public(value: object, secrets: list[str]) -> Any:
    redacted = redact(value, secrets)
    if isinstance(redacted, dict):
        return {key: _public(item, secrets) for key, item in redacted.items()}
    if isinstance(redacted, list):
        return [_public(item, secrets) for item in redacted]
    if isinstance(redacted, str):
        return re.sub(
            r"(?<![\w:/])(?:[A-Za-z]:[\\/][^\s\"<>]+|/(?:home|root|Users|tmp|workspace|mnt)/[^\s\"<>]+)",
            "[local-path]",
            redacted,
        )
    return redacted


def _write(result: JsonDict, out_dir: Path) -> None:
    """Write sanitized numerical evidence and portable bilingual HTML reports."""
    out_dir.mkdir(parents=True, exist_ok=True)
    documents = {
        "report.json": result,
        "assessment.original.json": result["assessment_original"],
        "assessment.recomputed.json": result["assessment_recomputed"],
        "comparison.json": result["numerical_replay"],
        "records.recomputed.json": result["records_recomputed"],
    }
    for name, payload in documents.items():
        (out_dir / name).write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            + "\n",
            encoding="utf-8",
        )
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["arm", "id", "transport_status", "parse_status", "recomputed_score"])
    for arm, rows in result["records_recomputed"].items():
        for row in rows:
            values = [arm, row["id"], row["status"], row["output_status"], row["score"]]
            writer.writerow(
                [
                    "null"
                    if value is None
                    else "'" + str(value)
                    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r"))
                    else value
                    for value in values
                ]
            )
    (out_dir / "records.recomputed.csv").write_text(stream.getvalue(), encoding="utf-8")
    for language in ("en", "zh"):
        zh = language == "zh"
        title = "实验包离线复算" if zh else "Offline experiment bundle replay"
        labels = [
            ("来源字节完整性" if zh else "Source byte integrity", result["integrity"]["status"]),
            (
                "数值与旧报告比较" if zh else "Numerical comparison",
                result["numerical_replay"]["status"],
            ),
            (
                "局部设计与前提" if zh else "Local design and premises",
                result["premise_checks"]["status"],
            ),
        ]
        cards = "".join(
            f"<article><small>{html.escape(label)}</small><h2>{html.escape(status)}</h2></article>"
            for label, status in labels
        )
        assessment = result["assessment_recomputed"]
        coverage = assessment["coverage"]
        note = (
            f"已从原始保存输出重新评分，成功配对 {coverage['matched']}/{coverage['total']}。服务错误、超时和缺失保留原状态，不按质量零分计入。解析失败是实际观察到的质量结果。"
            if zh
            else f"Scores were recalculated from raw saved outputs; {coverage['matched']}/{coverage['total']} pairs matched. Service errors, timeouts and missing outputs keep their transport status and are excluded from quality scores. Parse failures remain observed quality outcomes."
        )
        boundary = (
            "哈希仅核对包内一致性，不能认证来源或冻结日期。未提供的记录仍标记为不可用。复算没有模型调用、网络请求、命令执行或 pickle 加载。"
            if zh
            else "Hashes check internal consistency; they do not authenticate the source or freeze date. Missing receipts remain unavailable. Replay makes no model calls, network requests, command executions or pickle loads."
        )
        marker = (
            ("合成演示数据" if zh else "Synthetic demonstration")
            if result["synthetic"]
            else ("输入的研究记录" if zh else "Supplied research records")
        )
        rows_html = "".join(
            "<tr>"
            + "".join(
                f"<td>{html.escape(str(value))}</td>"
                for value in [
                    arm,
                    row["id"],
                    row["status"],
                    row["output_status"],
                    "null" if row["score"] is None else row["score"],
                ]
            )
            + "</tr>"
            for arm, rows in result["records_recomputed"].items()
            for row in rows
        )
        headers = (
            ["组别", "样本", "传输状态", "解析状态", "复算分数"]
            if zh
            else ["Arm", "Item", "Transport status", "Parse status", "Recomputed score"]
        )
        details = html.escape(
            json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        )
        page = f'''<!doctype html><html lang="{language}"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>{title}</title><style>body{{font:15px/1.6 system-ui;max-width:1100px;margin:36px auto;padding:0 20px;color:#17263c;background:#f8fafc}}.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}article,details{{border:1px solid #dbe5f0;border-radius:12px;background:white;padding:18px}}h2{{font-size:20px}}table{{width:100%;border-collapse:collapse;background:white;margin:24px 0}}th,td{{text-align:left;padding:10px;border-bottom:1px solid #e2e8f0}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}}@media(max-width:600px){{.cards{{grid-template-columns:1fr}}}}</style><h1>{title}</h1><strong>{marker}</strong><div class="cards">{cards}</div><p>{note}</p><p>{boundary}</p><table><thead><tr>{"".join(f"<th>{value}</th>" for value in headers)}</tr></thead><tbody>{rows_html}</tbody></table><details><summary>{"完整证据与差异" if zh else "Complete evidence and differences"}</summary><pre>{details}</pre></details></html>'''
        (out_dir / f"report.{language}.html").write_text(page, encoding="utf-8")


def replay_experiment(bundle_or_directory: Path, out_dir: Path) -> JsonDict:
    """Recompute a bounded portable experiment bundle without model or network access."""
    source, destination = Path(bundle_or_directory), Path(out_dir)
    if source.is_dir() and destination.resolve().is_relative_to(source.resolve()):
        raise ValueError("Replay output must be outside the input bundle directory")
    output_names = {
        "report.json",
        "assessment.original.json",
        "assessment.recomputed.json",
        "comparison.json",
        "records.recomputed.json",
        "records.recomputed.csv",
        "report.en.html",
        "report.zh.html",
    }
    if source.resolve() in {(destination / name).resolve() for name in output_names}:
        raise ValueError("Replay output would overwrite the input bundle")
    files, kind = _load_bundle(source)
    raw_spec, data, split, job = (
        _json(files[name], name) for name in ("spec.json", "data.json", "split.json", "job.json")
    )
    spec = ExperimentSpec.from_json(raw_spec).to_json()
    if data.get("records") != spec["data"]:
        raise ValueError("Data snapshot disagrees with the immutable experiment spec")
    integrity = _integrity(files, raw_spec, data, split, job)
    calls = [
        _json(raw, name)
        for name, raw in sorted(files.items())
        if name.startswith("calls/") and name.endswith(".json")
    ]
    selected, premises = _premises(spec, split, files, calls)
    phase = "withheld" if spec["operation"] == "optimize" else "evaluation"
    ids = split.get(phase)
    if not isinstance(ids, list) or any(not isinstance(item, str) for item in ids):
        raise ValueError("Bundle has no valid evaluation partition")
    rows, record_source = _records(files, phase)
    rescored, score_checks, links = _rescore(spec, rows, phase, ids, calls, selected)
    budget, ledger_status = _ledger_budget(
        spec, job, calls, sum(len(values) for values in rows.values())
    )
    assessment = assess(
        spec,
        rescored["baseline"],
        rescored["candidate"],
        expected_ids=ids,
        scope=phase,
        budget=budget,
        selected_config=selected,
    )
    if ledger_status.startswith("unavailable"):
        assessment["cost"]["status"] = "unknown"
    original = job.get("assessment")
    if not isinstance(original, dict) and "report/summary.json" in files:
        original = _json(files["report/summary.json"], "report/summary.json").get("assessment")
    differences, metadata_differences = (
        _assessment_differences(original, assessment)
        if isinstance(original, dict)
        else (None, None)
    )
    statuses = [row["status"] for row in score_checks]
    numerical_status = (
        "failed"
        if "failed" in statuses or differences
        else "unavailable"
        if differences is None
        else "partial"
        if "unavailable" in statuses or not score_checks or ledger_status.startswith("unavailable")
        else "passed"
    )
    link_statuses = [row["status"] for row in links]
    integrity["record_linkage"] = {
        "status": "failed"
        if "failed" in link_statuses
        else "passed"
        if link_statuses and all(value == "passed" for value in link_statuses)
        else "partial",
        "checks": links,
    }
    if "failed" in link_statuses:
        integrity["status"] = "failed"
    elif "unavailable" in link_statuses and integrity["status"] == "passed":
        integrity["status"] = "partial"
    result = {
        "schema_version": "experiment-replay-result/v1",
        "synthetic": spec.get("synthetic", False),
        "source": {
            "kind": kind,
            "bundle_id": job.get("id"),
            "file_count": len(files),
            "bytes": sum(map(len, files.values())),
        },
        "integrity": integrity,
        "numerical_replay": {
            "status": numerical_status,
            "tolerances": {"atol": ATOL, "rtol": RTOL},
            "record_source": record_source,
            "score_checks": score_checks,
            "record_call_links": links,
            "call_ledger": ledger_status,
            "assessment_differences": differences,
            "metadata_differences": metadata_differences,
            "comparison_scope": "Numerical fields present in the original assessment; newly added fields are displayed but do not fail replay. Changed nonnumeric metadata is reported separately.",
            "original_assessment_available": isinstance(original, dict),
        },
        "premise_checks": premises,
        "assessment_original": original,
        "assessment_recomputed": assessment,
        "records_recomputed": rescored,
        "redaction": "Report text is sanitized; integrity checks use the original supplied bytes.",
        "claim_scope": "Offline recomputation from supplied evidence only. Numerical agreement, byte integrity and local design checks are separate; external independence is not verified.",
    }
    result = cast(JsonDict, _public(result, configured_secrets(spec)))
    _write(result, destination)
    return result


__all__ = ["replay_experiment"]
