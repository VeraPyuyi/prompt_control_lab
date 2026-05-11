# Agent Guard Pilot Case Study

This file tracks the planned paired Codex local pilot for `pcl guard`.

## Current status

The repository does not yet contain 20 paired `raw prompt` vs `pcl guard` task records. The
available historical transcripts under `D:\Vibe Research Projects` are real agent logs, but they
do not contain the same coding tasks run once with a raw prompt and once with a guarded prompt.

Because of that, the README must not publish success-rate improvement numbers yet.

## Data file

The pilot dataset will live in:

```text
docs/case_studies/agent_guard_pilot.csv
```

Each row is one local Codex coding task run twice:

- raw prompt sent directly to the agent
- guarded prompt produced by `pcl guard --profile coding --token-mode balanced`

The public CSV stores summaries and metrics, not private full prompts.

## Metrics

| Metric | Definition |
|---|---|
| `raw_success` / `guarded_success` | `true` when the task was completed and the relevant verification passed |
| `raw_tests_passed` / `guarded_tests_passed` | `true` when the expected test or acceptance check passed |
| `*_touched_files` | number of files changed during the run |
| `*_unnecessary_file_edits` | changed files outside the task, test, doc, or formatting scope |
| `*_human_corrections` | human turns needed to narrow scope, request missing tests, or undo off-target work |
| `*_prompt_tokens` | dependency-free prompt-token estimate, not model billing tokens |

## Publication rule

Publish a README result table only after at least 20 paired rows exist and the summary can be
recomputed from the CSV. Until then, the README should say that the pilot is in progress.

When the table is published, include this limitation:

> This is a small local Codex pilot, not a universal benchmark. It shows how the guard behaved on this task set.
