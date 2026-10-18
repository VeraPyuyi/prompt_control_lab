"""Review regressions for partially labelled independent evaluation units."""

from __future__ import annotations

from typing import Any

import pytest

from promptcontrollab.evaluation.experiments.assessment import assess

GROUP_FIELDS = ("task", "task_id", "document", "document_id", "group", "group_id")


def _assessment(
    metadata: list[dict[str, Any]],
    candidate_scores: list[float] | None = None,
    *,
    baseline_scores: list[float] | None = None,
    inputs: list[str] | None = None,
) -> dict[str, Any]:
    tasks = [
        {
            "id": str(index),
            "input": inputs[index] if inputs is not None else f"independent input {index}",
            "meta": meta,
        }
        for index, meta in enumerate(metadata)
    ]
    baseline = [
        {
            "id": task["id"],
            "status": "completed",
            "score": baseline_scores[index] if baseline_scores is not None else 0.0,
        }
        for index, task in enumerate(tasks)
    ]
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


@pytest.mark.parametrize("field", (*GROUP_FIELDS, "sample_id", "source_id"))
@pytest.mark.parametrize(
    "other",
    [
        "task a",
        "\uff34\uff41\uff53\uff4b \uff21",
        " Task A",
        "Task A ",
        "Task  A",
        "Task\tA",
    ],
    ids=["case", "fullwidth", "leading-space", "trailing-space", "inner-space", "tab"],
)
def test_group_identity_preserves_case_unicode_and_whitespace(field: str, other: str) -> None:
    result = _assessment([{field: "Task A" if i % 2 else other} for i in range(30)])
    stats = result["effect"]["statistics"]
    assert stats["independent_group_count"] == stats["n"] == 2
    assert stats["mean_delta"] == 1.0
    assert stats["bootstrap_ci"] is None
    assert stats["permutation_p_value"] is None
    assert stats["holm_adjusted_p_value"] is None
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
def test_distinct_group_labels_keep_thirty_independent_units(field: str) -> None:
    result = _assessment([{field: f"  UNIT {i} "} for i in range(30)])
    stats = result["effect"]["statistics"]
    assert stats["independent_group_count"] == stats["n"] == 30
    assert stats["inference_status"] == "cluster_bootstrap"
    assert result["effect"]["status"] == "improved"


def test_case_distinct_task_ids_do_not_reverse_effect_or_claim_improvement() -> None:
    # 21 negative tasks differ only by case; 9 positive tasks have separate IDs.
    # Folding case would give the negatives one vote and the positives nine votes.
    negative_ids = [
        "".join(
            letter.upper() if mask & (1 << bit) else letter for bit, letter in enumerate("abcde")
        )
        for mask in range(21)
    ]
    metadata = [{"task_id": label} for label in negative_ids] + [
        {"task_id": f"positive-{i}"} for i in range(9)
    ]
    result = _assessment(
        metadata, [0.0] * 21 + [1.0] * 9, baseline_scores=[1.0] * 21 + [0.0] * 9
    )
    stats = result["effect"]["statistics"]
    assert stats["record_count"] == stats["independent_group_count"] == stats["n"] == 30
    assert stats["baseline_mean"] == pytest.approx(0.7)
    assert stats["candidate_mean"] == pytest.approx(0.3)
    assert stats["mean_delta"] == pytest.approx(-0.4)
    assert stats["bootstrap_ci"] == pytest.approx([-0.7333333333333333, -0.06666666666666667])
    assert stats["holm_adjusted_p_value"] == pytest.approx(0.050974512743628186)
    assert result["effect"]["status"] == "uncertain"


@pytest.mark.parametrize("field", (*GROUP_FIELDS, "sample_id", "source_id"))
def test_integer_and_string_group_ids_remain_distinct(field: str) -> None:
    result = _assessment([{field: 0 if i % 2 else "0"} for i in range(30)])
    stats = result["effect"]["statistics"]
    assert stats["independent_group_count"] == stats["n"] == 2
    assert stats["bootstrap_ci"] is None
    assert result["effect"]["status"] != "improved"


@pytest.mark.parametrize("field", GROUP_FIELDS)
def test_explicit_same_group_value_combines_different_task_ids(field: str) -> None:
    result = _assessment([{field: "same exact task"} for _ in range(30)])
    stats = result["effect"]["statistics"]
    assert stats["record_count"] == 30
    assert stats["independent_group_count"] == stats["n"] == 1
    assert stats["mean_delta"] == 1.0
    assert stats["bootstrap_ci"] is None
    assert stats["permutation_p_value"] is None
    assert stats["holm_adjusted_p_value"] is None
    assert result["effect"]["status"] != "improved"


@pytest.mark.parametrize("declared", [False, True])
def test_normalized_input_duplicates_do_not_reduce_independent_groups(declared: bool) -> None:
    metadata = [{"task_id": f"task-{i}"} if declared else {} for i in range(30)]
    result = _assessment(
        metadata,
        [0.0] * 21 + [1.0] * 9,
        baseline_scores=[1.0] * 21 + [0.0] * 9,
        inputs=[
            "  \uff33\uff21\uff2d\uff25\tinput " if i % 2 else "same input" for i in range(30)
        ],
    )
    stats = result["effect"]["statistics"]
    assert stats["record_count"] == stats["independent_group_count"] == stats["n"] == 30
    assert stats["mean_delta"] == pytest.approx(-0.4)
    assert stats["bootstrap_ci"] is None
    assert stats["permutation_p_value"] is None
    assert stats["holm_adjusted_p_value"] is None
    assert stats["inference_status"] == "descriptive_only_nonindependent_rows"
    assert result["effect"]["status"] == "uncertain"


def test_input_duplicate_and_explicit_group_members_are_reported_separately() -> None:
    result = _assessment(
        [{"task_id": "same"}, {"task_id": "same"}, {}, {}, {}, {}],
        inputs=["input 0", "input 1", " \uff21 ", "a", "input 4", "input 5"],
    )
    duplicates = result["effect"]["grouping"]
    assert duplicates["identity_policy"] == "exact_typed_values_nonblank"
    assert duplicates["normalized_input_duplicates"] == [["2", "3"]]
    assert duplicates["explicit_group_duplicates"] == [["0", "1"]]
    assert duplicates["explicit_group_fields"] == ["task_id"]
    assert result["effect"]["statistics"]["independent_group_count"] == 5
