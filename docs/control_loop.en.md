# Local Control Loop

Chinese: [control_loop.zh.md](control_loop.zh.md)

PromptControlLab is a local control framework for prompts and AI agents. The default path is a concrete loop around execution: inspect the pending prompt, require an explicit authorization boundary, observe only approved public metadata, diagnose the recorded run, and write a decision that another person or adapter can review.

It is not an autonomous launcher. A control session is created without executing a provider or agent, and the base `pcl control` command does not launch an agent. Agent execution belongs to an explicit adapter such as the [DeepSeek Harness Cordis plugin](deepseek_harness.en.md).

## The Loop

1. **Bind:** hash the exact pending prompt and create the immutable run context.
2. **Before:** run the local prompt guard and persist a redacted preflight decision.
3. **Authorize:** require one of four execution levels; non-interactive use must pass it on the command line.
4. **Run:** call one configured provider only in `model` mode, or hand an allowed decision to an agent adapter.
5. **Observe:** append ordered, redacted events with stable ids and idempotency keys.
6. **Why and after:** derive attribution factors and observable stability states from recorded events.
7. **Decide:** write the recommendation, next action, Markdown/HTML report, and rebuild the local run index.

Attribution is association based. Stability is an observable event classification. Neither output proves causation, correctness, or safety.

## Two-Minute Inspect Run

```bash
python -m pip install -e ".[ui]"
pcl control \
  --prompt "Inspect the request and propose a bounded plan." \
  --authorization inspect \
  --out runs/first-control \
  --json
```

This writes a finalized preflight-only run. It does not call a provider and it does not launch an agent.

## Authorization Levels

| Level | What it authorizes | What it does not imply |
|---|---|---|
| `inspect` | Local guard, prompt hashes, redacted artifacts, and an `inspect_only` decision. | No model request, tool dispatch, or agent launch. |
| `model` | One call through the named provider adapter and public model id, after a passing preflight. Both `--provider` and `--model` are required. | No agent or tool execution. A blocked or review-required preflight prevents the call. |
| `agent-scoped` | A named adapter may control one bound agent/session and its observed lifecycle. The Harness bridge requires this level. | The base command still does not launch an agent; the adapter owns execution. |
| `agent-full` | An adapter or replay may record a broader, explicitly chosen agent boundary. | It is not an implicit permission escalation. Native Harness live sessions remain locked to `agent-scoped`. |

When stdin is not interactive, omitting `--authorization` is an error. In an interactive terminal, PromptControlLab shows a non-persisting suggestion preview before asking for the level. Authorization describes the allowed execution surface; it does not certify the prompt or action as safe.

## Model Mode

Configure credentials in an environment variable, inspect the local adapter, and name the public model explicitly:

```bash
pcl providers inspect deepseek --json
pcl control \
  --prompt "Return a three-item checklist." \
  --authorization model \
  --provider deepseek \
  --model deepseek-chat \
  --out runs/model-control \
  --json
```

Provider setup and public-model provenance limits are documented in [providers.en.md](providers.en.md).

## JSON Is the Source of Truth

Every durable record has a versioned schema. JSON and JSONL artifacts are the source of truth:

| Artifact | Schema or role |
|---|---|
| `control_run.json` | Immutable identity and context: `prompt_control_lab.control_run.v1`. |
| `events.jsonl` | Append-only ordered records: `prompt_control_lab.control_event.v1`. |
| `preflight.json` | Persistence-safe gate result: `prompt_control_lab.preflight_decision.v1`. The improved prompt is redacted on disk. |
| `provider_result.json` | Normalized provider output and public provenance for an executed `model` run. |
| `attribution.json` | Observable factors: `prompt_control_lab.attribution_report.v1`. |
| `stability.json` | Observable state and counts: `prompt_control_lab.stability_report.v1`. |
| `decision.json` | Recommendation and next action: `prompt_control_lab.control_decision.v1`. |
| `report.md` and `report.html` | Human-readable projections of the JSON records. |
| `.prompt_control_lab/runs.sqlite3` | Rebuildable query index, never the evidence authority. |

The live caller may receive the suggested prompt in the preflight transport response. The persisted `preflight.json` replaces that body with `[REDACTED]` and keeps hashes, findings, and the decision.

## Open Event Protocol

Each `prompt_control_lab.control_event.v1` record contains `run_id`, canonical `event_id`, positive `sequence`, `event_type`, UTC `timestamp`, redacted `payload`, and an optional `idempotency_key`. A run accepts only contiguous sequences. Replaying the same idempotent content is a no-op; reusing a key with changed content is an error.

`events.jsonl` is append-only and flushed to disk for every accepted event. Typical namespaces include `session/*`, `agent/*`, `tools/*`, `tool/*`, `test/*`, `step/*`, `task/*`, and `harness/*`. Adapters may add observable metadata, but secret fields, prompt bodies, and hidden reasoning are redacted before persistence.

The schema name carries its major protocol version. A breaking field or semantic change requires a new schema version; consumers should reject a schema they do not understand instead of guessing.

## Rebuildable SQLite Index

Finalization rebuilds `.prompt_control_lab/runs.sqlite3` under the runs root. The table stores locators and summary fields such as run id, path, authorization, provider/model/agent, risk, stability, decision, and event count.

Deleting this SQLite file does not delete control evidence. It can be rebuilt from `control_run.json`, `preflight.json`, `stability.json`, `decision.json`, and `events.jsonl`. Do not edit SQLite to change a decision; update the source artifacts through the control workflow and rebuild the index.

## Failure and Evidence Boundaries

- A preflight `block` or `required_review` stops `model` execution.
- A preflight-only run writes `insufficient_evidence` attribution and stability rather than inventing execution evidence.
- Provider and adapter errors are surfaced; PromptControlLab does not silently replace a requested model.
- Prompt hashes prove byte identity of the recorded input, not prompt quality.
- Event labels describe observed behavior, not hidden model state or causal mechanisms.

Use the [benchmark](control_benchmark.en.md) to check analyzer contract behavior and the [local UI](control_ui.en.md) to review a run. PEOC, soft-hard, trajectory, Riccati, and time-varying soft-control tooling stays in Advanced Diagnostics and is not required for this loop.
