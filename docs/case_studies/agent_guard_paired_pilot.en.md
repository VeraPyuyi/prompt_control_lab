# Real Paired Pilot: Codex Local Guard Study

This is a small **real raw-agent vs guarded-agent paired pilot**. It uses local Codex
non-interactive execution on isolated temporary Python repositories.

It is not a universal benchmark. It is a first reproducible smoke study that checks whether the
guarded prompt can be sent to an actual coding agent and compared against the raw prompt under the
same starting conditions.

## Protocol

- Agent: `codex-local-exec`
- Sample size: 12 paired tasks
- Task type: isolated Python `pytest` fixes, including single-file and multi-file tasks
- Each task runs twice:
  - raw prompt
  - prompt rewritten by `pcl guard --profile coding --policy examples/guard.policy.yaml`
- Each side starts from the same fresh git repository.
- Success means the post-agent `python -m pytest -q` command passed.
- No human correction turns were given after a failed or partial run.

## Result

| Metric | Raw agent | Guarded agent |
|---|---:|---:|
| Completed tasks | 12/12 | 12/12 |
| Tests passed | 12/12 | 12/12 |
| Average touched files | 1.25 | 1.0 |
| Total unexpected file edits | 3 | 0 |
| Human correction turns | 0 | 0 |
| Average estimated prompt tokens | 8.08 | 51.08 |
| Average duration seconds | 173.74 | 119.97 |

![Real paired Codex guard pilot visualization](../assets/agent_guard_paired_pilot.svg)

## Interpretation

The guarded prompts did **not** improve success rate in this fixture set because raw Codex also
solved all 12 tasks. The useful signal is elsewhere: after compacting the guard output, guarded
prompts still used more prompt tokens than raw prompts, but far fewer than the previous long guard
template. In this run they touched fewer files, produced zero unexpected file edits, and completed
faster on average.

The right conclusion is modest:

- guard output can be executed by a real coding agent;
- the paired harness can compare raw and guarded runs from identical starting states;
- this sample does not prove general task-success improvement;
- the next stronger study should use larger real repository tasks and PR-level review outcomes.

Data:

- [`agent_guard_paired_pilot.csv`](agent_guard_paired_pilot.csv)
- [`agent_guard_paired_pilot.summary.json`](agent_guard_paired_pilot.summary.json)
