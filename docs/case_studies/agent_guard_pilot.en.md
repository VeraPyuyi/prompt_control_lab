# Agent Guard Local Pilot Case Study

This file records the first local paired pilot for `pcl guard`.

## Current status

The repository now contains 20 paired **preflight** records in
`docs/case_studies/agent_guard_pilot.csv`. Each row uses a raw coding prompt and the guarded
prompt produced by:

```bash
pcl guard --profile coding --policy examples/guard.policy.yaml --token-mode balanced
```

This is not yet a raw-agent vs guarded-agent success-rate benchmark. The `*_success`,
`*_tests_passed`, `*_touched_files`, and correction fields are marked `not_run` because the paired
agent executions were not performed. The pilot measures prompt preflight behavior, token estimates,
and the shape of the guarded prompt.

## Data file

```text
docs/case_studies/agent_guard_pilot.csv
```

The public CSV stores summaries and metrics, not private full prompts.

## Metrics

| Metric | Definition |
|---|---|
| `raw_success` / `guarded_success` | `not_run` in this preflight pilot; reserved for future paired agent execution |
| `raw_tests_passed` / `guarded_tests_passed` | `not_run` in this preflight pilot |
| `*_touched_files` | `not_run` until an actual agent modifies the repository |
| `*_unnecessary_file_edits` | `not_run` until paired agent executions are available |
| `*_human_corrections` | `not_run` until paired agent executions are available |
| `*_prompt_tokens` | dependency-free prompt-token estimate, not model billing tokens |
| `notes` | guard action, risk level, risk categories, and policy-violation count |

## Publication rule

The README may publish the preflight pilot table because it can be recomputed from 20 CSV rows.
It must not publish task-success improvement numbers until the same tasks are executed once with
raw prompts and once with guarded prompts.

> This is a small local preflight pilot, not a universal benchmark. It shows how `pcl guard`
> rewrote and classified this task set; it does not prove agent task-success improvement.
