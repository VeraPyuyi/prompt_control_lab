"""Finite JSON validation, deterministic reports, and bounded evidence receipts."""

from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]


def number(value: Any, name: str, *, nonnegative: bool = False) -> float:
    """Validate and return a finite real number, excluding Boolean values."""
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be a finite number (not Boolean)")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError(f"{name} exceeds finite range") from error
    if not math.isfinite(result) or (nonnegative and result < 0):
        raise ValueError(f"{name} must be finite" + (" and nonnegative" if nonnegative else ""))
    return result


def text(value: Any, name: str) -> str:
    """Validate and return a nonempty text value."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")
    return value


def canonical(value: Any) -> bytes:
    """Encode a finite JSON value deterministically for portable hashing."""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(value: Any) -> str:
    """Return the SHA256 digest of a canonical JSON value."""
    return hashlib.sha256(canonical(value)).hexdigest()


def require_document(document: JsonDict, schema: str) -> None:
    """Validate the top-level research document and its schema version."""
    if not isinstance(document, dict) or document.get("schema_version") != schema:
        raise ValueError(f"schema_version must be {schema}")
    if type(document.get("synthetic")) is not bool:
        raise ValueError("synthetic must be an explicit Boolean")
    canonical(document)


def transfer_v2_receipt_projection(document: JsonDict) -> tuple[Any, Any, Any]:
    """Project ordered forecasts and actual crossed cohorts without evaluation outcomes."""
    calibration = {
        "question_ids": document.get("calibration_question_ids"),
        "prompt_ids": document.get("calibration_prompt_ids"),
    }
    if any(not isinstance(value, list) or not value for value in calibration.values()):
        raise ValueError("Transfer receipts require actual calibration question and prompt IDs")
    panels = document.get("panels")
    if not isinstance(panels, list) or not panels:
        raise ValueError("Transfer receipts require complete crossed panels")
    forecasts, cohorts = [], []
    for panel in panels:
        if (
            not isinstance(panel, dict)
            or not {"panel_id", "model", "axes", "pairs"} <= panel.keys()
        ):
            raise ValueError("Transfer receipts require complete crossed panels")
        pairs = panel["pairs"]
        keys = ("pair_id", "prompt_ids", "question_ids", "predictions")
        if (
            not isinstance(pairs, list)
            or not pairs
            or any(not isinstance(pair, dict) or not set(keys) <= pair.keys() for pair in pairs)
        ):
            raise ValueError("Transfer receipts require complete nested forecast pairs")
        identity = {key: panel[key] for key in ("panel_id", "model", "axes")}
        forecasts.append(
            {**identity, "pairs": [{key: pair[key] for key in keys} for pair in pairs]}
        )
        cohorts.append(
            {
                **identity,
                "pairs": [
                    {key: pair[key] for key in keys if key != "predictions"} for pair in pairs
                ],
            }
        )
    return forecasts, calibration, cohorts


def evidence(document: JsonDict) -> JsonDict:
    """Verify links inside supplied receipts; never authenticate their real-world dates."""
    status = document.get("evidence_status", "historical_observation")
    allowed = {"historical_observation", "locked_prediction", "independent_confirmation"}
    if status not in allowed:
        raise ValueError("Unknown evidence_status")
    receipts = document.get("evidence_receipts")
    result = {
        "declared": status,
        "linked_receipts_verified": False,
        "temporal_independence_verified": False,
        "scope": "Local content and receipt consistency only; hashes do not prove chronology.",
    }
    if receipts is None:
        if status == "independent_confirmation":
            raise ValueError(
                "independent_confirmation requires actual linked lock and provenance receipts"
            )
        return result
    if not isinstance(receipts, dict):
        raise ValueError("evidence_receipts must be an object")
    lock, evaluation = receipts.get("lock"), receipts.get("evaluation")
    if not isinstance(lock, dict) or not isinstance(evaluation, dict):
        raise ValueError("Actual lock and evaluation receipt objects are required")
    payload = lock.get("payload")
    if not isinstance(payload, dict) or not payload:
        raise ValueError("Lock receipt requires its actual nonempty payload")
    if lock.get("payload_sha256") != digest(payload):
        raise ValueError("Lock payload hash mismatch")
    if evaluation.get("lock_sha256") != digest(lock):
        raise ValueError("Evaluation receipt does not link to the supplied lock")
    observed = {k: v for k, v in document.items() if k != "evidence_receipts"}
    if evaluation.get("document_sha256") != digest(observed):
        raise ValueError("Evaluation receipt does not link to the analyzed document")
    try:
        frozen = datetime.fromisoformat(
            text(lock.get("frozen_at"), "frozen_at").replace("Z", "+00:00")
        )
        started = datetime.fromisoformat(
            text(evaluation.get("started_at"), "started_at").replace("Z", "+00:00")
        )
        if frozen.tzinfo is None or started.tzinfo is None or frozen >= started:
            raise ValueError("Freeze must precede evaluation with explicit time zones")
    except (TypeError, ValueError) as error:
        raise ValueError(
            "Receipt chronology requires valid zoned dates and freeze before evaluation"
        ) from error
    if document.get("prediction_lock_sha256") not in (None, digest(lock)):
        raise ValueError("prediction_lock_sha256 does not match the supplied lock receipt")
    measurement_v2 = document.get("schema_version") in (
        "measurement-value/v2",
        "pcl.measurement-value/v2",
    )
    transfer_v2 = document.get("schema_version") in (
        "control-transfer/v2",
        "pcl.control-transfer/v2",
    )
    if transfer_v2:
        forecasts, calibration, panel_cohorts = transfer_v2_receipt_projection(document)
        if payload.get("forecasts_sha256") != digest(forecasts):
            raise ValueError("Lock receipt does not freeze the supplied crossed-panel forecasts")
        cohorts = receipts.get("cohorts")
        if not isinstance(cohorts, dict) or (
            cohorts.get("calibration") != calibration
            or cohorts.get("evaluation_panels") != panel_cohorts
        ):
            raise ValueError("Transfer cohort provenance must match the actual crossed panels")
        if payload.get("calibration_cohorts_sha256") != digest(calibration) or evaluation.get(
            "evaluation_panels_sha256"
        ) != digest(panel_cohorts):
            raise ValueError("Transfer cohorts are not linked to lock and evaluation receipts")
    if "pairs" in document:
        if not isinstance(document["pairs"], list) or any(
            not isinstance(pair, dict)
            or not {"model", "pair_id", "left_seed", "right_seed", "pairing_type", "predictions"}
            <= pair.keys()
            for pair in document["pairs"]
        ):
            raise ValueError("Receipt verification requires complete forecast pair records")
        forecasts = [
            {
                k: pair[k]
                for k in (
                    "model",
                    "pair_id",
                    "left_seed",
                    "right_seed",
                    "pairing_type",
                    "predictions",
                )
            }
            for pair in document["pairs"]
        ]
        if payload.get("forecasts_sha256") != digest(forecasts):
            raise ValueError("Lock receipt does not freeze the supplied forecasts")
    if "cases" in document:
        policy_keys = (
            ("case_id", "model", "pair_id", "item_ids", "budget_seconds", "policies")
            if measurement_v2
            else ("model", "pair", "item_ids", "scores", "costs")
        )
        if not isinstance(document["cases"], list) or any(
            not isinstance(case, dict) or not set(policy_keys) <= case.keys()
            for case in document["cases"]
        ):
            raise ValueError("Receipt verification requires complete measurement case records")
        policies = [{key: case[key] for key in policy_keys} for case in document["cases"]]
        if payload.get("policies_sha256") != digest(policies):
            raise ValueError("Lock receipt does not freeze the supplied score and cost policies")
    if status == "independent_confirmation" and not transfer_v2:
        cohorts = receipts.get("cohorts")
        if not isinstance(cohorts, dict):
            raise ValueError("independent_confirmation requires linked cohort provenance")
        train, test = cohorts.get("calibration_ids"), cohorts.get("evaluation_ids")
        if not isinstance(train, list) or not train or not isinstance(test, list) or not test:
            raise ValueError("Actual calibration and evaluation identity lists are required")
        if any(not isinstance(x, str) or not x for x in train + test) or set(train) & set(test):
            raise ValueError("Calibration and evaluation identities must be nonempty and disjoint")
        if len(set(train)) != len(train) or len(set(test)) != len(test):
            raise ValueError("Cohort identity lists must be unique")
        actual_ids = None
        if "pairs" in document:
            actual_ids = {
                f"{pair['model']}:{pair[name]}"
                for pair in document["pairs"]
                for name in ("left_seed", "right_seed")
            }
        elif "cases" in document:
            pair_key = "pair_id" if measurement_v2 else "pair"
            actual_ids = {f"{case['model']}:{case[pair_key]}" for case in document["cases"]}
        if actual_ids is not None and set(test) != actual_ids:
            raise ValueError("Evaluation cohort identities must match the actual analyzed cases")
        if payload.get("calibration_ids_sha256") != digest(train) or evaluation.get(
            "evaluation_ids_sha256"
        ) != digest(test):
            raise ValueError("Cohort provenance is not linked to lock and evaluation receipts")
    result.update(linked_receipts_verified=True, receipt_chronology_consistent=True)
    return result


def flatten(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    """Flatten a nested JSON value into stable path and scalar pairs."""
    if isinstance(value, dict):
        return [
            row
            for key in sorted(value)
            for row in flatten(value[key], f"{prefix}.{key}" if prefix else key)
        ]
    if isinstance(value, list):
        return [
            row for index, item in enumerate(value) for row in flatten(item, f"{prefix}[{index}]")
        ]
    return [(prefix, value)]


def write_reports(result: JsonDict, out_dir: Path) -> JsonDict:
    """Write deterministic JSON, CSV, and bilingual research reports."""
    from .reporting import render_sections

    payload = (
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(payload, encoding="utf-8")
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["metric", "value", "value_type"])
    for key, value in flatten(result):
        # Guard spreadsheet formula interpretation while keeping JSON exact.
        cell = "null" if value is None else str(value)
        if isinstance(value, str) and cell[:1] in ("=", "+", "-", "@"):
            cell = "'" + cell
        writer.writerow([key, cell, type(value).__name__])
    (out_dir / "metrics.csv").write_text(stream.getvalue(), encoding="utf-8")
    for language in ("en", "zh"):
        title = "Research diagnostic replay" if language == "en" else "研究诊断复算"
        marker = (
            ("SYNTHETIC DEMONSTRATION DATA" if language == "en" else "合成演示数据")
            if result.get("synthetic")
            else ("Supplied research records" if language == "en" else "已提供的研究记录")
        )
        boundary = (
            "Results apply to supplied records and stated local assumptions. "
            "Undefined values remain null. No whole-model theorem or temporal "
            "independence is certified."
            if language == "en"
            else "结果仅适用于已提供的记录和明确的局部假设。"
            "无定义数值保留为空。本报告不认证整个模型的理论性质或时间独立性。"
        )
        sections_html, sections_md = render_sections(result, language, out_dir)
        details_title = "Complete numerical record" if language == "en" else "完整数值记录"
        md = (
            f"# {title}\n\n**{marker}**\n\n{sections_md}\n\n{boundary}\n\n"
            f"<details><summary>{details_title}</summary>\n\n```json\n{payload}```\n\n</details>\n"
        )
        (out_dir / f"report.{language}.md").write_text(md, encoding="utf-8")
        page = (
            f'<!doctype html><html lang="{language}"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width">'
            f"<title>{title}</title><style>"
            "*{box-sizing:border-box}body{font:15px/1.6 system-ui,sans-serif;color:#17263c;"
            "max-width:1180px;margin:36px auto;padding:0 24px;background:#f8fafc}"
            "h1{font-size:32px;letter-spacing:-.03em;margin-bottom:8px}p{max-width:105ch}"
            ".cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;"
            "margin:24px 0}.cards article{padding:18px;border:1px solid #dbe5f0;"
            "border-radius:12px;background:white}.cards small{font-size:12px;"
            "text-transform:uppercase;color:#526581}.cards p{margin:8px 0 0;font-weight:600}"
            ".table-scroll{overflow-x:auto;margin:20px 0;border:1px solid #dbe5f0;"
            "border-radius:10px}table{width:100%;border-collapse:collapse;background:white;"
            "font-variant-numeric:tabular-nums}th,td{padding:10px 12px;text-align:left;"
            "border-bottom:1px solid #e7edf4;white-space:nowrap}th{background:#eaf1f9;"
            "font-size:12px}tr:last-child td{border-bottom:0}figure{margin:24px 0}"
            "svg{width:100%;height:auto;border:1px solid #dbe5f0;border-radius:12px}"
            "details{margin:24px 0;background:white;border:1px solid #dbe5f0;"
            "border-radius:10px;padding:16px}summary{cursor:pointer;font-weight:600}"
            "pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef3f7;padding:20px;"
            "font-size:12px}strong{color:#8a4b00}@media(max-width:650px){"
            ".cards{grid-template-columns:1fr}body{padding:0 14px}h1{font-size:26px}}</style>"
            f"<h1>{title}</h1><p><strong>{marker}</strong></p>{sections_html}<p>{boundary}</p>"
            f"<details><summary>{details_title}</summary><pre>{html.escape(payload)}</pre>"
            "</details></html>"
        )
        (out_dir / f"report.{language}.html").write_text(page, encoding="utf-8")
    return result
