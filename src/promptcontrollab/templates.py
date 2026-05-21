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
{"id":"arith-1","output":"4","provider":"openai","model":"gpt-4o"}
{"id":"arith-2","output":"6","provider":"openai","model":"gpt-4o"}
{"id":"format-1","output":"POSITIVE","provider":"openai","model":"gpt-4o"}
{"id":"format-2","output":"negative","provider":"openai","model":"gpt-4o"}
"""

CANDIDATE_JSONL = """\
{"id":"arith-1","output":"4","provider":"openai","model":"gpt-4o"}
{"id":"arith-2","output":"7","provider":"openai","model":"gpt-4o"}
{"id":"format-1","output":"POSITIVE","provider":"openai","model":"gpt-4o"}
{"id":"format-2","output":"NEGATIVE","provider":"openai","model":"gpt-4o"}
"""

CONFIG_YAML = """\
# PromptControlLab Quick Mode example.
mode: quick
data: examples/tasks.jsonl
metric: exact_match
baseline_predictions: examples/predictions_baseline.jsonl
candidate_predictions: examples/predictions_candidate.jsonl
baseline_model: gpt-4o
candidate_model: gpt-4o
baseline_provider: openai
candidate_provider: openai
out: runs/quick
explain_level: plain
gate_policy: examples/gate.policy.yaml
"""

GUARD_POLICY_YAML = """\
# Example guard policy for `pcl guard --policy`.
# The parser is dependency-free. It supports this flat style and a small nested `rules:` style.
profile: coding
block_at: high
review_at: medium
required_fields: target_files,failing_behavior,test_plan,acceptance_criteria
rule.destructive_action.severity: high
rule.destructive_action.patterns: delete database|drop table|remove auth
rule.destructive_action.message: Coding prompt asks for a destructive change.
rule.destructive_action.category: destructive_change
rule.broad_refactor.severity: medium
rule.broad_refactor.patterns: refactor whole repo|rewrite all
rule.broad_refactor.message: Broad refactors need human review before an agent runs.
rule.broad_refactor.category: broad_refactor
"""

GATE_POLICY_YAML = """\
# Example gate policy for `pcl gate`.
min_candidate_score: 0.75
max_regression: 0.0
require_adjusted_p_below: 1.0
allowed_models: gpt-4o,gpt-5.2
allowed_providers: openai
block_if_model_unknown: true
block_if_model_mismatch: true
block_if_alias_model: false
require_model_verified: false
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
    (path / "examples" / "guard.policy.yaml").write_text(GUARD_POLICY_YAML, encoding="utf-8")
    (path / "examples" / "gate.policy.yaml").write_text(GATE_POLICY_YAML, encoding="utf-8")
    (path / "promptcontrol.example.yaml").write_text(CONFIG_YAML, encoding="utf-8")
