"""Independent task groups must not inflate paired inference."""

from promptcontrollab.evaluation.experiments.assessment import assess


def _records(task_id: str, score: float, arm: str) -> dict:
    return {"id": task_id, "status": "completed", "score": score, "slice": "default"}


def test_cluster_bootstrap_uses_independent_groups_not_repeated_rows() -> None:
    tasks = []
    baseline, candidate = [], []
    for group in range(10):
        for repeat in range(3):
            task_id = f"{group}-{repeat}"
            tasks.append(
                {
                    "id": task_id,
                    "input": f"task {group}",
                    "expected": "yes",
                    "slice": "default",
                    "meta": {"group_id": str(group)},
                }
            )
            baseline.append(_records(task_id, 0.0, "baseline"))
            candidate.append(_records(task_id, 1.0, "candidate"))
    spec = {
        "metric": "exact_match",
        "seed": 0,
        "operation": "run",
        "data": tasks,
        "budget": {},
        "baseline": {},
        "candidate": {},
    }
    result = assess(
        spec,
        baseline,
        candidate,
        expected_ids=[task["id"] for task in tasks],
        scope="evaluation",
        budget={},
    )
    stats = result["effect"]["statistics"]
    assert stats["record_count"] == 30
    assert stats["independent_group_count"] == 10
    assert stats["estimation_target"] == "mean_task_effect"
    assert stats["bootstrap_ci"] is not None
    assert stats["inference_status"] == "cluster_bootstrap"
