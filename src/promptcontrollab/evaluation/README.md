# Evaluation

## Purpose

`promptcontrollab.evaluation` provides reproducible prompt and checkpoint comparison: deterministic splits, imported predictions, metrics, paired statistics, validity checks, explanations, policy gates, reports, and run history.

Its primary reviewer-facing entry point is Change Review: compare two recorded prompt, model, Agent, or checkpoint runs and explain the decision without modifying either source run.

## Use cases

- Compare baseline and candidate prompts on the same examples.
- Detect leakage, slice regressions, and statistically uncertain gains.
- Produce reviewer-facing Markdown, HTML, and structured gate artifacts.
- Index and compare a directory of historical runs.

## CLI commands

```bash
pcl analyze --config promptcontrol.example.yaml --out runs/quick
pcl split --data examples/tasks.jsonl --out runs/split
pcl eval --data examples/tasks.jsonl --predictions examples/candidate.jsonl --out runs/candidate
pcl stats --baseline runs/baseline/predictions.jsonl --candidate runs/candidate/predictions.jsonl --out runs/stats.json
pcl explain --run runs/quick --level technical
pcl gate --run runs/quick --policy examples/gate.policy.yaml
pcl report --run runs/quick
pcl history index --runs runs --out runs/history_index.json
pcl review --baseline runs/baseline --candidate runs/candidate --kind auto --out runs/change-review
```

## Python API

The approved canonical package exposes orchestration and focused analysis APIs:

```python
from promptcontrollab.evaluation import (
    compare_prediction_files,
    generate_report,
    run_gate,
    run_import_eval,
    review_changes,
    run_quick_analysis,
)
```

`ReportModel`, `SplitResult`, `ComparisonResult`, metric helpers, history functions, and comparison-validity checks support custom workflows.

## Inputs/Artifacts

- Inputs: task JSONL, prediction JSONL, baseline/candidate runs, metrics, policies, and optional prompt/model identity.
- Outputs: `splits.json`, `predictions.jsonl`, `metrics.json`, `stats.json`, `explanation.json`, `gate_result.json`, `change_review.json`, `comparison_validity.json`, `attribution.json`, `stability.json`, `decision_trace.json`, `human_feedback.json`, `report.md`, `report.html`, and history artifacts.
- `export-report` packages known run artifacts without including undeclared source files.

## Dependencies

Core evaluation is dependency-free and uses `core` schemas/files plus `provenance` identity records. Statistical routines use deterministic Python implementations rather than requiring a scientific stack.

## Extension points

- Add metrics through explicit scoring and summary functions.
- Add report sections through `ReportModel` rather than parsing rendered Markdown.
- Add gate checks as structured evidence with status, impact, reason, and next action.

## Limitations

- Statistical significance does not establish causality or deployment safety.
- A prompt-only comparison is valid only when model, data, and relevant execution settings are controlled.
- Imported predictions are trusted only to the extent recorded provenance and validation permit.

## Tests/Examples

Use `promptcontrol.example.yaml`, the quickstart guide, and evaluation tests. Run:

```bash
python -m pytest tests -k "analyze or split or eval or stats or report or gate or history"
```
