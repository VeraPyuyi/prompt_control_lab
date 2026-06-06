# Real Paired Pilot: Codex Local Guard Study

This is a small **real raw-agent vs guarded-agent paired pilot**. It uses local Codex
non-interactive execution on isolated temporary Python repositories.

It is not a universal benchmark. It is a first reproducible smoke study that checks whether the
guarded prompt can be sent to an actual coding agent and compared against the raw prompt under the
same starting conditions.

## Protocol

- Agent: `codex-local-exec`
- Sample size: 6 paired tasks
- Task type: isolated Python `pytest` bug fixes
- Each task runs twice:
  - raw prompt
  - prompt rewritten by `pcl guard --profile coding --policy examples/guard.policy.yaml`
- Each side starts from the same fresh git repository.
- Success means the post-agent `python -m pytest -q` command passed.
- No human correction turns were given after a failed or partial run.

## Result

| Metric | Raw agent | Guarded agent |
|---|---:|---:|
| Completed tasks | 6/6 | 6/6 |
| Tests passed | 6/6 | 6/6 |
| Average touched files | 1.17 | 1.17 |
| Total unexpected file edits | 1 | 1 |
| Human correction turns | 0 | 0 |
| Average estimated prompt tokens | 5.17 | 83.17 |
| Average duration seconds | 149.02 | 114.36 |

## Interpretation

The guarded prompts did **not** improve success rate in this small fixture set because raw Codex
already solved all six tasks. The guarded prompts did, in this run, complete faster on average,
but they also used many more prompt tokens.

The right conclusion is modest:

- guard output can be executed by a real coding agent;
- the paired harness can compare raw and guarded runs from identical starting states;
- this sample does not prove general task-success improvement;
- larger and more realistic tasks are needed before making stronger claims.

Data:

- [`agent_guard_paired_pilot.csv`](agent_guard_paired_pilot.csv)
- [`agent_guard_paired_pilot.summary.json`](agent_guard_paired_pilot.summary.json)

