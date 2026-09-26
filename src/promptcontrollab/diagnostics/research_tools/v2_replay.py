"""Four-channel replay: content, numbers, protocol premises, and local theory."""

from __future__ import annotations

from pathlib import Path

from .common import JsonDict
from .replay import analyze_document as replay_v1
from .v2_common import aggregate_status, header, saved_summary


def analyze_document(document: JsonDict, out_dir: Path) -> JsonDict:
    """Separate integrity, numerical replay, protocol checks and local property assumptions."""
    result = header(document, "replay")
    summary = saved_summary(document, result)
    if summary is not None:
        return summary
    allowed = {
        "schema_version",
        "synthetic",
        "representation",
        "provenance",
        "evidence_status",
        "evidence_receipts",
        "files",
        "checks",
        "tolerances",
    }
    if set(document) - allowed:
        raise ValueError("Replay rejects commands, external paths, and unknown manifest fields")
    legacy = {
        key: value
        for key, value in document.items()
        if key not in {"representation", "evidence_receipts"}
    }
    legacy["schema_version"] = "research-replay/v1"
    replayed = replay_v1(legacy, out_dir)
    numerical = replayed["numerical_replay"]
    numerical["status"] = aggregate_status([row["status"] for row in numerical["checks"]])
    premises = []
    for check in numerical["checks"]:
        actual = check["result"]
        # Local validation succeeds when a raw record module accepts all of its required
        # premises. It is independent of numerical agreement with an expected file.
        validated = actual.get("representation") == "raw_records"
        status = "passed" if validated else "not_supplied"
        if actual.get("fixed_score_initial_answer_preserving_claim") == "failed":
            status = "failed"
        premises.append(
            {
                "kind": check["kind"],
                "input_file": check["input_file"],
                "status": status,
                "scope": "Versioned input prerequisites checked locally"
                if validated
                else "Legacy or saved-summary input does not verify v2 protocol premises",
            }
        )
    protocol = {
        "status": aggregate_status([row["status"] for row in premises]),
        "checks": premises,
        "chronological_prediction_lock": "not_verified",
        "temporal_independence_verified": False,
        "scope": (
            "Hash matches and self-reported dates cannot certify "
            "prediction-before-evaluation chronology."
        ),
    }
    theory = replayed["theoretical_checks"]
    theory["model_global_claim"] = False
    theory["scope"] = "Only supplied finite-dimensional local surrogates and declared assumptions."
    result.update(
        integrity=replayed["integrity"],
        numerical_replay=numerical,
        protocol=protocol,
        theoretical_checks=theory,
        statuses={
            "integrity": replayed["integrity"]["status"],
            "numerical": numerical["status"],
            "protocol": protocol["status"],
            "theory": theory["status"],
        },
        claim_scope=(
            "Integrity, numerical agreement, protocol premises and local theory are "
            "independent channels. Chronology and model-global properties are not certified."
        ),
    )
    return result
