"""Saved paired-output readout sensitivity; no generated continuation is fabricated."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from .common import JsonDict, evidence, number, require_document, text
from .transfer_prediction import binary_auc


def _answer(value: str, rule: str) -> str | None:
    value = value.strip()
    if rule == "exact":
        return value or None
    if rule == "boxed":
        matches = re.findall(r"\\boxed\{([^{}]+)\}", value)
        return matches[-1].strip() if matches else None
    if rule == "last_number":
        matches = re.findall(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?(?:[eE][-+]?\d+)?", value)
        if not matches:
            return None
        try:
            return str(Decimal(matches[-1].replace(",", "")).normalize())
        except InvalidOperation:
            return None
    raise ValueError("parser.rule must be exact, boxed, or last_number")


def _output(endpoint: object, budget: int) -> tuple[str, str]:
    if not isinstance(endpoint, dict) or not isinstance(endpoint.get("text"), str):
        raise ValueError("Each endpoint requires explicit saved text")
    if "prefix_tokens" not in endpoint:
        return endpoint["text"], "saved_output"
    count = endpoint["prefix_tokens"]
    ids, pieces = endpoint.get("token_ids"), endpoint.get("token_texts")
    if type(count) is not int or count < 0 or count > budget:
        raise ValueError("prefix_tokens must be a nonnegative integer within condition budget")
    if not isinstance(ids, list) or any(type(x) is not int or x < 0 for x in ids):
        raise ValueError("Derived prefixes require original token_ids")
    if (
        not isinstance(pieces, list)
        or len(pieces) != len(ids)
        or any(not isinstance(x, str) for x in pieces)
    ):
        raise ValueError("Derived prefixes require aligned saved token_texts")
    if count > len(ids) or "".join(pieces) != endpoint["text"]:
        raise ValueError("Original token/prefix evidence must reconstruct saved text exactly")
    text(endpoint.get("tokenizer_id"), "tokenizer_id")
    return "".join(
        pieces[:count]
    ), "derived_saved_token_prefix; not a rerun at shorter generation budget"


def analyze_document(document: JsonDict) -> JsonDict:
    """Compare saved paired outputs across explicit parser and generation conditions."""
    require_document(document, "readout-sensitivity/v1")
    conditions = document.get("conditions")
    if not isinstance(conditions, list) or not conditions:
        raise ValueError("conditions must contain saved paired outputs")
    rows, seen, reference, panel = [], set(), None, None
    reference_gold = None
    for condition in conditions:
        if not isinstance(condition, dict):
            raise ValueError("Each condition must be an object")
        cid = text(condition.get("condition_id"), "condition_id")
        if cid in seen:
            raise ValueError("condition_id must be unique")
        seen.add(cid)
        parser = condition.get("parser")
        if not isinstance(parser, dict) or type(parser.get("posthoc")) is not bool:
            raise ValueError("Each parser requires rule, version, and explicit posthoc Boolean")
        rule = text(parser.get("rule"), "parser.rule")
        text(parser.get("version"), "parser.version")
        _answer("", rule)
        budget = condition.get("budget_tokens")
        if type(budget) is not int or budget <= 0:
            raise ValueError("budget_tokens must be a positive integer")
        if not isinstance(condition.get("decoding"), dict) or not condition["decoding"]:
            raise ValueError("Explicit decoding metadata is required")
        samples = condition.get("samples")
        if not isinstance(samples, list) or not samples:
            raise ValueError("Every condition requires a nonempty paired sample panel")
        clean: list[JsonDict] = []
        ids, gold_values = [], []
        for sample in samples:
            if not isinstance(sample, dict):
                raise ValueError("Each sample must be an object")
            item = text(sample.get("item_id"), "item_id")
            ids.append(item)
            gold = text(sample.get("gold_answer"), "gold_answer")
            gold_values.append(gold)
            outputs = {key: _output(sample.get(key), budget) for key in ("source", "target")}
            parsed = {key: _answer(value[0], rule) for key, value in outputs.items()}
            canonical_gold = _answer(gold, "last_number") if rule == "last_number" else gold.strip()
            if canonical_gold is None:
                raise ValueError("gold_answer is incompatible with parser")
            correct = {
                key: int(value is not None and value == canonical_gold)
                for key, value in parsed.items()
            }
            scores = sample.get("scores")
            if not isinstance(scores, dict) or "loss" not in scores or len(scores) < 2:
                raise ValueError("Each sample needs loss plus at least one fixed diagnostic score")
            for key, value in scores.items():
                number(value, f"scores.{key}")
            clean.append(
                {
                    "item_id": item,
                    "parsed": parsed,
                    "correct": correct,
                    "parse_switch": int((parsed["source"] is None) != (parsed["target"] is None)),
                    "correctness_change": abs(correct["target"] - correct["source"]),
                    "answer_changed": parsed["source"] != parsed["target"],
                    "output_evidence": {key: value[1] for key, value in outputs.items()},
                    "scores": scores,
                }
            )
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate item_id within condition")
        if panel is None:
            panel = ids
            reference_gold = gold_values
        elif ids != panel:
            raise ValueError("Conditions must share the same ordered item panel")
        elif gold_values != reference_gold:
            raise ValueError("Conditions must retain the same gold answers for the paired panel")
        score_names = sorted(clean[0]["scores"])
        if any(sorted(row["scores"]) != score_names for row in clean):
            raise ValueError("Fixed diagnostic score names must align within each condition")
        auc: JsonDict = {
            target: {
                name: binary_auc(
                    [row["scores"][name] for row in clean], [row[target] for row in clean]
                )
                for name in score_names
            }
            for target in ("correctness_change", "parse_switch")
        }
        gaps = {
            target: {
                name: value - auc[target]["loss"]
                if value is not None and auc[target]["loss"] is not None
                else None
                for name, value in values.items()
                if name != "loss"
            }
            for target, values in auc.items()
        }
        if reference is None:
            reference = clean
        switches = {
            key: sum(
                row["parsed"][key] != base["parsed"][key]
                for row, base in zip(clean, reference, strict=True)
            )
            for key in ("source", "target")
        }
        rows.append(
            {
                "condition_id": cid,
                "parser": parser,
                "budget_tokens": budget,
                "decoding": condition["decoding"],
                "item_count": len(clean),
                "auc": auc,
                "auc_gaps": gaps,
                "parsed_answer_switches_from_reference": switches,
                "samples": clean,
            }
        )
    return {
        "schema_version": "readout-sensitivity-result/v1",
        "synthetic": document["synthetic"],
        "kind": "readout",
        "evidence": evidence(document),
        "reference_condition": rows[0]["condition_id"],
        "conditions": rows,
        "claim_scope": (
            "Sensitivity of supplied outputs and parser rules; posthoc analyses remain posthoc."
        ),
    }
