"""Readout sensitivity with fixed diagnostic scores and explicit generation evidence."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from .common import JsonDict, digest, text
from .readout import _output
from .transfer_prediction import binary_auc
from .v2_common import boolean, header, integer, mapping, records, saved_summary, score_number
from .v2_response import _ranks, rank_correlation

_NUMBER = r"[-+]?(?:\d+(?:,\d{3})*(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


def parse_answer(value: str, rule: str, version: str) -> str | None:
    """Frozen, explicit numeric or A-E choice domain; no implicit coercion."""
    if version not in ("numeric/v2", "choice/v2") or rule not in ("strict", "leading", "terminal"):
        raise ValueError(
            "Parser requires numeric/v2 or choice/v2 with strict, leading, or terminal"
        )
    patterns = {
        "strict": rf"\s*({_NUMBER})\s*",
        "leading": rf"\s*({_NUMBER})(?=$|\s|[,;.!?])",
        "terminal": rf"(?<![\w.])({_NUMBER})\s*[.!]?\s*$",
    }
    if version == "choice/v2":
        patterns = {
            "strict": r"\s*([A-E])\s*",
            "leading": r"\s*([A-E])(?=$|\s|[.)\]:;!?])",
            "terminal": r"(?<![\w])([A-E])\s*[)\]]?\s*[.!]?\s*$",
        }
    match = (
        re.fullmatch(patterns[rule], value)
        if rule == "strict"
        else re.search(patterns[rule], value)
        if rule == "terminal"
        else re.match(patterns[rule], value)
    )
    if match is None:
        return None
    if version == "choice/v2":
        return match.group(1)
    try:
        decimal = Decimal(match.group(1).replace(",", ""))
        if decimal == 0:
            return "0"
        parts = decimal.as_tuple()
        exponent = parts.exponent
        if not isinstance(exponent, int):
            return None
        digits = list(parts.digits)
        while len(digits) > 1 and digits[-1] == 0:
            digits.pop()
            exponent += 1
        # Decimal.normalize() obeys ambient precision and can collapse distinct answers.
        return str(Decimal((parts.sign, tuple(digits), exponent)))
    except InvalidOperation:
        return None


def _saved_output(endpoint: object, budget: int, mode: str) -> tuple[str, str]:
    item = mapping(endpoint, "endpoint")
    if mode == "stored_prefix":
        if "prefix_tokens" not in item:
            raise ValueError("stored_prefix requires prefix_tokens and token consistency evidence")
        receipt = mapping(item.get("token_consistency"), "token_consistency")
        if (
            receipt.get("verified") is not True
            or receipt.get("token_ids_sha256") != digest(item.get("token_ids"))
            or receipt.get("decoded_text_sha256") != digest(item.get("text"))
        ):
            raise ValueError("token consistency evidence must link original ids and decoded text")
        text(receipt.get("decoder"), "token_consistency.decoder")
        return _output(item, budget)
    if "prefix_tokens" in item:
        raise ValueError("A saved prefix cannot be represented as a full or real short generation")
    if mode == "real_short_generation":
        text(item.get("generation_run_id"), "real short generation_run_id")
        integer(item.get("generated_tokens"), "generated_tokens")
        if item["generated_tokens"] > budget:
            raise ValueError("Real short generation exceeds its declared token budget")
        text(item.get("finish_reason"), "finish_reason")
    output, _ = _output(item, budget)
    return output, mode


def analyze_document(document: JsonDict) -> JsonDict:
    """Compare versioned parsing, answers and diagnostic ranks under recorded conditions."""
    result = header(document, "readout")
    summary = saved_summary(document, result)
    if summary is not None:
        return summary
    conditions = records(document.get("conditions"), "conditions")
    seen: set[str] = set()
    reference: dict[str, JsonDict] = {}
    panel: list[str] | None = None
    output_rows: list[JsonDict] = []
    reference_execution: JsonDict | None = None
    for condition in conditions:
        cid = text(condition.get("condition_id"), "condition_id")
        if cid in seen:
            raise ValueError("condition_id must be unique")
        seen.add(cid)
        parser = mapping(condition.get("parser"), "parser")
        rule, version = (
            text(parser.get("rule"), "parser.rule"),
            text(parser.get("version"), "parser.version"),
        )
        boolean(parser.get("posthoc"), "parser.posthoc")
        parse_answer("", rule, version)
        budget = integer(condition.get("budget_tokens"), "budget_tokens", minimum=1)
        mode = condition.get("generation_mode")
        if mode not in ("saved_full", "stored_prefix", "real_short_generation"):
            raise ValueError(
                "generation_mode must distinguish saved_full, stored_prefix, real_short_generation"
            )
        decoding = mapping(condition.get("decoding"), "decoding")
        if not decoding:
            raise ValueError("decoding must explicitly describe generation")
        axes = {
            "batch_size": integer(condition.get("batch_size"), "batch_size", minimum=1),
            "stopping": text(condition.get("stopping"), "stopping"),
            "precision": text(condition.get("precision"), "precision"),
            "template_id": text(condition.get("template_id"), "template_id"),
            "budget_tokens": budget,
        }
        execution = {**axes, "decoding": decoding, "generation_mode": mode}
        if reference_execution is None:
            reference_execution = execution
        clean: list[JsonDict] = []
        ids: list[str] = []
        score_names: set[str] | None = None
        for sample in records(condition.get("samples"), "samples"):
            item_id = text(sample.get("item_id"), "item_id")
            ids.append(item_id)
            gold = parse_answer(text(sample.get("gold_answer"), "gold_answer"), "strict", version)
            if gold is None:
                raise ValueError("gold_answer must be compatible with the declared strict parser")
            initial = mapping(sample.get("initial_answers"), "initial_answers")
            if set(initial) != {"source", "target"} or any(
                not isinstance(value, str) for value in initial.values()
            ):
                raise ValueError("initial_answers requires preserved source and target strings")
            scores = mapping(sample.get("scores"), "scores")
            if "loss" not in scores or len(scores) < 2:
                raise ValueError("Fixed scores require loss and at least one diagnostic")
            checked_scores = {
                name: score_number(value, f"scores.{name}") for name, value in scores.items()
            }
            if score_names is None:
                score_names = set(scores)
            elif set(scores) != score_names:
                raise ValueError("All fixed score names must align")
            if panel is not None:
                if item_id not in reference:
                    raise ValueError("Conditions require the same ordered item panel")
                prior = reference[item_id]
                if set(checked_scores) != set(prior["scores"]):
                    raise ValueError("Diagnostic score names must align across conditions")
                if gold != prior["gold_answer"]:
                    raise ValueError("Conditions must preserve gold answers")
            outputs = {
                key: _saved_output(sample.get(key), budget, mode) for key in ("source", "target")
            }
            parsed = {key: parse_answer(value[0], rule, version) for key, value in outputs.items()}
            correct = {
                key: int(value is not None and value == gold) for key, value in parsed.items()
            }
            clean.append(
                {
                    "item_id": item_id,
                    "gold_answer": gold,
                    "initial_answers": initial,
                    "scores": checked_scores,
                    "parsed": parsed,
                    "correct": correct,
                    "parse_switch": int((parsed["source"] is None) != (parsed["target"] is None)),
                    "answer_changed": parsed["source"] != parsed["target"],
                    "correctness_change": abs(correct["source"] - correct["target"]),
                    "output_evidence": {key: value[1] for key, value in outputs.items()},
                    "source_record_identity": {
                        key: digest(
                            {
                                field: mapping(sample[key], key).get(field)
                                for field in ("text", "token_ids", "generation_run_id")
                            }
                        )
                        for key in ("source", "target")
                    },
                }
            )
        if len(set(ids)) != len(ids) or (panel is not None and ids != panel):
            raise ValueError("Conditions require a unique and identical ordered item panel")
        if panel is None:
            panel, reference = ids, {row["item_id"]: row for row in clean}
        rank_sensitivity = {}
        for name in sorted(score_names or []):
            baseline = [reference[row["item_id"]]["scores"][name] for row in clean]
            current = [row["scores"][name] for row in clean]
            rank_sensitivity[name] = {
                "values_preserved": current == baseline,
                "ranks_preserved": _ranks(current) == _ranks(baseline),
                "spearman": rank_correlation(current, baseline),
                "changed_items": sum(a != b for a, b in zip(current, baseline, strict=True)),
            }
        fixed_scores = all(row["values_preserved"] for row in rank_sensitivity.values())
        initial_preserved = all(
            row["initial_answers"] == reference[row["item_id"]]["initial_answers"] for row in clean
        )
        premise = "passed" if fixed_scores and initial_preserved else "failed"
        sources_preserved = all(
            row["source_record_identity"] == reference[row["item_id"]]["source_record_identity"]
            for row in clean
        )
        changed_axes = [key for key in execution if execution[key] != reference_execution[key]]
        saved_views = mode in {"saved_full", "stored_prefix"} and reference_execution[
            "generation_mode"
        ] in {"saved_full", "stored_prefix"}
        # A proven prefix view changes the reading budget, not the underlying generation.
        execution_preserved = not changed_axes or (
            saved_views
            and "stored_prefix" in {mode, reference_execution["generation_mode"]}
            and set(changed_axes) <= {"budget_tokens", "generation_mode"}
            and sources_preserved
        )
        auc = {
            target: {
                name: binary_auc(
                    [row["scores"][name] for row in clean], [int(row[target]) for row in clean]
                )
                for name in sorted(score_names or [])
            }
            for target in ("parse_switch", "answer_changed", "correctness_change")
        }
        changes = {
            "parsed_answer_changes": sum(
                row["parsed"][key] != reference[row["item_id"]]["parsed"][key]
                for row in clean
                for key in ("source", "target")
            ),
            "parse_status_changes": sum(
                (row["parsed"][key] is None) != (reference[row["item_id"]]["parsed"][key] is None)
                for row in clean
                for key in ("source", "target")
            ),
            "correctness_changes": sum(
                row["correct"][key] != reference[row["item_id"]]["correct"][key]
                for row in clean
                for key in ("source", "target")
            ),
        }
        output_rows.append(
            {
                "condition_id": cid,
                "parser": parser,
                "comparison_axes": axes,
                "generation_mode": mode,
                "decoding": decoding,
                "item_count": len(clean),
                "fixed_scores_preserved": fixed_scores,
                "initial_answers_preserved": initial_preserved,
                "fixed_score_initial_answer_preserving_claim": premise,
                "execution_conditions_preserved": execution_preserved,
                "execution_axes_changed": changed_axes,
                "source_records_preserved": sources_preserved,
                "comparison_class": "readout_only"
                if premise == "passed" and execution_preserved and sources_preserved
                else "inference_perturbation",
                "rank_sensitivity": rank_sensitivity,
                "auc": auc,
                "auc_gaps": {
                    target: {
                        name: value - values["loss"]
                        if value is not None and values["loss"] is not None
                        else None
                        for name, value in values.items()
                        if name != "loss"
                    }
                    for target, values in auc.items()
                },
                "changes_from_reference": changes,
                "samples": clean,
            }
        )
    result.update(
        conditions=output_rows,
        reference_condition=output_rows[0]["condition_id"],
        fixed_scores_preserved=all(row["fixed_scores_preserved"] for row in output_rows),
        fixed_score_ranks_preserved=all(
            rank["ranks_preserved"]
            for row in output_rows
            for rank in row["rank_sensitivity"].values()
        ),
        initial_answers_preserved=all(row["initial_answers_preserved"] for row in output_rows),
        fixed_score_initial_answer_preserving_claim="passed"
        if all(
            row["fixed_score_initial_answer_preserving_claim"] == "passed" for row in output_rows
        )
        else "failed",
        prefix_scope=(
            "Stored token prefixes are not real short-generation reruns; "
            "token receipts are locally checked declarations."
        ),
    )
    return result
