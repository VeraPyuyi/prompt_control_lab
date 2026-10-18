"""Review regressions for partially labelled independent evaluation units."""

from __future__ import annotations

from typing import Any

import pytest

from promptcontrollab.evaluation.experiments.assessment import assess

GROUP_FIELDS = ("task", "task_id", "document", "document_id", "group", "group_id")


def _assessment(
    metadata: list[dict[str, Any]], candidate_scores: list[float] | None = None
) -> dict[str, Any]:
    tasks = [
        {"id": str(index), "input": f"independent input {index}", "meta": meta}
        for index, meta in enumerate(metadata)
    ]
    baseline = [{"id": task["id"], "status": "completed", "score": 0.0} for task in tasks]
    candidate = [
        {**row, "score": candidate_scores[index] if candidate_scores is not None else 1.0}
        for index, row in enumerate(baseline)
    ]
    return assess(
        {
            "operation": "run",
            "metric": "exact_match",
            "seed": 0,
            "baseline": {},
            "candidate": {},
            "budget": {},
            "data": tasks,
        },
        baseline,
        candidate,
        expected_ids=[str(task["id"]) for task in tasks],
        scope="evaluation",
        budget={},
    )


@pytest.mark.parametrize("field", GROUP_FIELDS)
def test_partial_group_labels_count_29_plus_one_as_two_units(field: str) -> None:
    # The label deliberately equals the unlabelled row's ID; it cannot absorb that row.
    result = _assessment([{field: "29"} for _ in range(29)] + [{}], [1.0] * 29 + [0.0])
    stats = result["effect"]["statistics"]
    assert stats["record_count"] == 30
    assert stats["independent_group_count"] == stats["n"] == 2
    assert stats["mean_delta"] == 0.5
    assert stats["estimation_target"] == "mean_task_effect"
    assert stats["bootstrap_ci"] is None
    assert stats["permutation_p_value"] is None
    assert stats["holm_adjusted_p_value"] is None
    assert stats.get("iid_diagnostics", {}).get("bootstrap_ci") is None
    assert result["effect"]["status"] == "uncertain"
    assert result["next_action"]["code"] == "evaluate_independent_groups"


@pytest.mark.parametrize("field", GROUP_FIELDS)
def test_all_declared_group_fields_join_even_when_primary_labels_differ(field: str) -> None:
    metadata = [{"group_id": f"unique-{i}", field: "shared"} for i in range(30)]
    result = _assessment(metadata)
    stats = result["effect"]["statistics"]
    assert stats["independent_group_count"] == stats["n"] == 1
    assert stats["bootstrap_ci"] is None
    assert stats["permutation_p_value"] is None
    assert stats.get("iid_diagnostics", {}).get("bootstrap_ci") is None
    assert result["effect"]["status"] != "improved"


@pytest.mark.parametrize("field", (*GROUP_FIELDS, "sample_id", "source_id"))
@pytest.mark.parametrize("empty", ["", None, " \t\n "])
def test_empty_group_labels_leave_distinct_inputs_independent(field: str, empty: object) -> None:
    result = _assessment([{field: empty} for _ in range(30)])
    stats = result["effect"]["statistics"]
    assert stats["independent_group_count"] == stats["n"] == 30
    assert stats["bootstrap_ci"] == [1.0, 1.0]
    assert stats["inference_status"] == "iid_assumed"
    assert result["effect"]["status"] == "improved"


@pytest.mark.parametrize("field", GROUP_FIELDS)
def test_group_labels_normalize_case_and_whitespace(field: str) -> None:
    result = _assessment([{field: "Roof  A" if i % 2 else "  roof\t a  "} for i in range(30)])
    stats = result["effect"]["statistics"]
    assert stats["independent_group_count"] == stats["n"] == 1
    assert stats["bootstrap_ci"] is None
    assert result["effect"]["status"] != "improved"


@pytest.mark.parametrize("field,alias", [("task", "task_id"), ("document", "document_id")])
def test_group_aliases_join_transitively_across_missing_rows(field: str, alias: str) -> None:
    metadata = [{field: f"unit-{i}"} for i in range(30)]
    # Each bridge is in the immutable snapshot but has no completed outputs.
    tasks = [
        {"id": str(i), "input": f"input {i}", "meta": meta}
        for i, meta in enumerate(metadata)
    ] + [
        {
            "id": f"bridge-{i}",
            "input": f"bridge {i}",
            "meta": {field: f"unit-{i}", alias: f"unit-{i + 1}"},
        }
        for i in range(29)
    ]
    rows = [{"id": str(i), "score": 0.0, "status": "completed"} for i in range(30)]
    result = assess(
        {
            "operation": "run",
            "metric": "exact_match",
            "seed": 0,
            "baseline": {},
            "candidate": {},
            "budget": {},
            "data": tasks,
        },
        rows,
        [{**row, "score": 1.0} for row in rows],
        expected_ids=[str(task["id"]) for task in tasks],
        scope="evaluation",
        budget={},
    )
    assert result["effect"]["statistics"]["independent_group_count"] == 1
    assert result["effect"]["statistics"]["bootstrap_ci"] is None
    assert result["effect"]["status"] != "improved"


def test_empty_primary_label_does_not_hide_a_shared_task() -> None:
    result = _assessment([{"group_id": " ", "task": "shared"} for _ in range(30)])
    assert result["effect"]["statistics"]["independent_group_count"] == 1
    assert result["effect"]["statistics"]["bootstrap_ci"] is None


def test_partial_group_labels_keep_inference_with_enough_independent_units() -> None:
    result = _assessment([{"task": f"task-{i // 3}"} for i in range(18)] + [{} for _ in range(12)])
    stats = result["effect"]["statistics"]
    assert stats["record_count"] == 30
    assert stats["independent_group_count"] == stats["n"] == 18
    assert stats["inference_status"] == "cluster_bootstrap"
    assert stats["estimation_target"] == "mean_task_effect"
    assert result["effect"]["status"] == "improved"


@pytest.mark.parametrize("field", GROUP_FIELDS)
def test_distinct_group_labels_remain_distinct_after_normalization(field: str) -> None:
    result = _assessment([{field: f"  UNIT {i} "} for i in range(30)])
    stats = result["effect"]["statistics"]
    assert stats["independent_group_count"] == stats["n"] == 30
    assert stats["inference_status"] == "cluster_bootstrap"
    assert result["effect"]["status"] == "improved"
