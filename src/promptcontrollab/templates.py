"""Example project templates for ``pcl init``."""

from __future__ import annotations

from pathlib import Path

from promptcontrollab.files import ensure_dir

TASKS_JSONL = """\
{"id":"arith-1","input":"What is 2 + 2?","expected":"4","slice":"arithmetic"}
{"id":"arith-2","input":"What is 10 - 3?","expected":"7","slice":"arithmetic"}
{"id":"format-1","input":"Return the label POSITIVE.","expected":"POSITIVE","slice":"format"}
{"id":"format-2","input":"Return the label NEGATIVE.","expected":"NEGATIVE","slice":"format"}
"""

BASELINE_JSONL = """\
{"id":"arith-1","output":"4"}
{"id":"arith-2","output":"6"}
{"id":"format-1","output":"POSITIVE"}
{"id":"format-2","output":"negative"}
"""

CANDIDATE_JSONL = """\
{"id":"arith-1","output":"4"}
{"id":"arith-2","output":"7"}
{"id":"format-1","output":"POSITIVE"}
{"id":"format-2","output":"NEGATIVE"}
"""

CONFIG_YAML = """\
# PromptControlLab Quick Mode example.
mode: quick
data: examples/tasks.jsonl
metric: exact_match
baseline_predictions: examples/predictions_baseline.jsonl
candidate_predictions: examples/predictions_candidate.jsonl
out: runs/quick
explain_level: plain
gate_policy: examples/gate.policy.yaml
"""

GATE_POLICY_YAML = """\
# Example gate policy for `pcl gate`.
min_candidate_score: 0.75
max_regression: 0.0
require_adjusted_p_below: 1.0
"""


def write_example_project(path: Path) -> None:
    """Write a small example project."""

    ensure_dir(path / "examples")
    ensure_dir(path / "runs")
    (path / "examples" / "tasks.jsonl").write_text(TASKS_JSONL, encoding="utf-8")
    (path / "examples" / "predictions_baseline.jsonl").write_text(BASELINE_JSONL, encoding="utf-8")
    (path / "examples" / "predictions_candidate.jsonl").write_text(
        CANDIDATE_JSONL,
        encoding="utf-8",
    )
    (path / "examples" / "gate.policy.yaml").write_text(GATE_POLICY_YAML, encoding="utf-8")
    (path / "promptcontrol.example.yaml").write_text(CONFIG_YAML, encoding="utf-8")
