# Production Pilot Protocol

This document describes how to collect a small but credible production-style
`raw-agent vs guarded-agent` study for `prompt_control_lab`.

The goal is not to prove a universal improvement. The goal is to show, on a
defined task set, whether `pcl guard` changes agent behavior in ways that are
useful for a team: fewer unexpected edits, clearer test evidence, fewer review
corrections, better audit coverage, or lower run time.

## Privacy Boundary

Do not publish private prompts or source code. Public artifacts should use task
summaries, aggregate metrics, redacted file paths when needed, and reproducible
protocol notes. Keep full prompts, patches, logs, and repository snapshots in a
private workspace unless they are explicitly safe to release.

## Recommended Sample

- Start with 20 to 50 real coding tasks from one repository or one product area.
- Include bug fixes, tests, docs, dependency changes, UI changes, CI fixes, and
  security-sensitive requests.
- Avoid cherry-picking only easy or successful tasks.
- Record excluded tasks and the reason for exclusion.

## Paired Execution Protocol

For each task, run both sides from identical clean repository states.

1. Create a clean worktree or temporary clone.
2. Run the raw prompt with the chosen agent.
3. Record success, tests, touched files, unexpected edits, duration, and human
   correction turns.
4. Reset to the same clean starting commit.
5. Run:

   ```bash
   pcl guard --prompt "<task prompt>" \
     --profile coding \
     --policy examples/guard.policy.yaml \
     --token-mode balanced \
     --json
   ```

6. Run the guarded prompt with the same agent, provider, model, and timeout.
7. Record the same metrics.
8. Run:

   ```bash
   pcl audit-diff --before <start-ref> --after <end-ref> --out runs/audit-<task-id>
   pcl agent-run build --run runs/quick --audit runs/audit-<task-id> --agent codex --out runs/agent_run-<task-id>.json
   ```

9. Store only redacted summaries in the public CSV.

## Fields To Record

Use the existing case-study schema as the minimum:

- `task_id`
- `agent`
- `task_type`
- `raw_prompt_summary`
- `guarded_prompt_summary`
- `raw_success`
- `guarded_success`
- `raw_touched_files`
- `guarded_touched_files`
- `raw_unnecessary_file_edits`
- `guarded_unnecessary_file_edits`
- `raw_tests_passed`
- `guarded_tests_passed`
- `raw_human_corrections`
- `guarded_human_corrections`
- `raw_prompt_tokens`
- `guarded_prompt_tokens`
- `raw_duration_seconds`
- `guarded_duration_seconds`
- `notes`

## What The Result Can Claim

Safe claims:

- "On this task set, guarded prompts had fewer unexpected edits."
- "On this task set, guarded runs recorded clearer tests or audit evidence."
- "The guard increased prompt tokens but reduced average run duration."
- "No success-rate gain was observed in this pilot."

Unsafe claims:

- "Guarded prompts always improve coding success."
- "The guard proves the agent action is safe."
- "This sample is a universal benchmark."

## Publish A Summary

After collecting the CSV, update a case-study page with:

```bash
pcl history index --runs runs --out runs/history_index.json
pcl export-report --run runs/quick --out runs/quick/report.zip
```

Publish the aggregate table, visualization, method, and limitations. Keep raw
private logs out of the open repository unless they are explicitly reviewed for
release.
