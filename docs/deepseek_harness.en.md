# DeepSeek Harness Native Integration

Chinese: [deepseek_harness.zh.md](deepseek_harness.zh.md)

DeepSeek Harness is PromptControlLab 2.0's flagship agent integration. It is a native Cordis plugin, not a log scraper or a second agent loop. The plugin uses Harness interception points before model and tool execution, then sends bounded, redacted observations to one persistent local Python bridge.

This integration is a community-maintained PromptControlLab component. Its existence does not claim endorsement, support, or inclusion by DeepSeek Harness maintainers.

## Compatibility Lock

The tested contract is intentionally narrow:

- DeepSeek Harness version: `0.1.1-rc.2`
- DeepSeek Harness commit: `b150a551b8d465e31e418e1b2eaf5e79bbb7d28e`
- Node.js: `^22.19.0 || >=24.0.0`
- Bridge protocol: `prompt_control_lab.bridge.v1`
- Transport: line-delimited JSON-RPC 2.0 over one persistent stdio process

The machine-readable contract is [`plugins/deepseek-harness/compatibility.json`](../plugins/deepseek-harness/compatibility.json). Compatibility with another Harness version or commit is not claimed. If a Harness event signature changes, update the lock, TypeScript wrappers, Python methods, and contract tests together.

Pinned official Harness references:

- [Repository at the tested commit](https://github.com/deepseek-ai/deepseek-harness/tree/b150a551b8d465e31e418e1b2eaf5e79bbb7d28e)
- [Architecture and turn flow](https://github.com/deepseek-ai/deepseek-harness/blob/b150a551b8d465e31e418e1b2eaf5e79bbb7d28e/docs/architecture.md)
- [Cordis event system](https://github.com/deepseek-ai/deepseek-harness/blob/b150a551b8d465e31e418e1b2eaf5e79bbb7d28e/docs/user/develop/framework/events.md)
- [First Harness plugin guide](https://github.com/deepseek-ai/deepseek-harness/blob/b150a551b8d465e31e418e1b2eaf5e79bbb7d28e/docs/user/develop/basic/index.md)
- [Producer/consumer event map](https://github.com/deepseek-ai/deepseek-harness/blob/b150a551b8d465e31e418e1b2eaf5e79bbb7d28e/docs/event-producer-consumer.md)
- [Built-in repeat-tool reminder](https://github.com/deepseek-ai/deepseek-harness/blob/b150a551b8d465e31e418e1b2eaf5e79bbb7d28e/packages/guard/repeat-tool-reminder/README.md)

## Architecture

```text
Harness Agent
  -> Cordis waterfall: agent/pre-step
  -> Cordis waterfall: tools/pre-execute
  -> native PromptControlLab plugin
  -> one persistent `pcl bridge serve --transport stdio`
  -> versioned local JSON/JSONL artifacts
  -> attribution, stability, decision, report, and history index
```

The Cordis plugin owns lifecycle listeners and a bounded single-writer observation queue. The Python bridge owns durable control artifacts and analysis. Harness continues to own the agent loop, provider request, retry policy, tool execution, approvals, session log, built-in guards, and cancellation signals.

## Install and Initialize

Start from a Harness checkout at the pinned commit and install PromptControlLab in the environment that will launch Harness. The official Harness repository documents its own `pnpm` setup.

Initialize reviewable project files; this command does not edit the active Cordis composition:

```bash
pcl harness init --project .
```

It writes:

- `.promptcontrol/deepseek-harness.json`
- `.promptcontrol/deepseek-harness.cordis.yml`
- `.promptcontrol/deepseek-harness.compatibility.json`

Install the native plugin into the Harness checkout and build it:

```bash
pcl install-plugin deepseek-harness --target ./plugins/prompt-control-lab
cd plugins/prompt-control-lab
npm ci
npm run build
```

Review `cordis.patch.yml` and merge its row into the active Harness profile. The generated safe-default row is:

```yaml
- insert:
    - id: prompt-control-lab
      name: '@prompt-control-lab/deepseek-harness'
      config:
        mode: suggest
        policyPath: .promptcontrol/guard.policy.yaml
        capture: redacted
        feedback: summary
        autoRecover: false
        maxAutoRecoveries: 1
        bridgeFailure: warn
        runsRoot: .promptcontrol/runs
        feedbackMaxChars: 600
        observationQueueSize: 256
        exposeStatusTool: false
```

PromptControlLab must be importable and `pcl bridge serve --transport stdio` must be available to the Harness process. The plugin starts and reuses that bridge; do not start a second writer for the same live session.

## Doctor

```bash
pcl harness doctor --project . --json
```

Doctor is offline. It checks the local config schema, redacted capture, compatibility lock, Python bridge health, Node version, and packaged plugin files. A passing result does not prove that the active Harness profile loaded the row, that a provider credential works, or that a live session emitted events. Verify those separately with a bounded Harness run.

A completed live acceptance additionally requires `session_origin=live_cordis`, the persistent
stdio transport, the pinned Harness version/commit, and lifecycle events carrying bridge source
sequence and timestamp fields. Replay data and events appended directly by fixtures cannot satisfy
this acceptance. These checks establish the captured native lifecycle path; they still do not prove
a provider's hidden model weights or the semantic safety of every action.

## Exact Event Mapping

Harness distinguishes live Cordis events from durable session events. `turn/*`, `step/*`, `tool/call`, `tool/result`, and `compaction/*` arrive through the Cordis `session/event` listener; they are not same-named Cordis events.

| Harness source | PromptControlLab bridge call | Durable effect |
|---|---|---|
| `agent/session-start` | `harness_session_start` | Create or retry the active `agent-scoped`, redacted control run and verify the compatibility lock. A session resumed after finalization receives a new deterministic `-resume-N` run with lineage metadata. |
| `agent/pre-step` | `harness_pre_step` | Inspect the final downstream prompt synchronously for each `(turn, step)` before a model request; persist only hashes, findings, and the decision. |
| `agent/request` | `harness_event` with `agent/request` | Record turn, step, retry attempt, public provider/model, max tokens, and temperature. |
| `agent/request-error` | `harness_event` with `agent/request-error` | Record bounded failure kind/code/status/retryability; Harness still owns retries. |
| `tools/pre-execute` | `harness_tool_pre_execute` | Gate a hash-only tool projection before dispatch. |
| `tools/post-execute` | `harness_event` with `tools/post-execute` | Observe normalized result status after downstream policies. |
| `tools/result` | `harness_event` with `tools/result` | Observe the immutable result projection. |
| `session/event` | `harness_event` with `session/<event.type>` | Record redacted durable session metadata except `assistant/chunk`. |
| `turn/end` inside `session/event` | `harness_event`, then `harness_turn_end` | Persist the event and compute a bounded turn assessment. |
| `agent/turn-stopping` | `harness_turn_end` | Ask for a recovery recommendation only when `autoRecover` is explicitly enabled. |
| `agent/disposed` | `harness_finalize` | Flush critical lifecycle work and finalize local reports. |
| Optional `pcl_status` tool | `harness_status` | Read status without changing state; registered only with `exposeStatusTool: true`. |

The seven versioned bridge methods are `harness_session_start`, `harness_pre_step`, `harness_tool_pre_execute`, `harness_event`, `harness_turn_end`, `harness_status`, and `harness_finalize`.

## Suggest and Gate Semantics

### Prompt gate: `agent/pre-step`

The plugin first awaits downstream pre-step listeners and inspects the exact final message batch they would send.

- In `suggest`, all PromptControlLab decisions delegate. Available feedback may be appended as a bounded source-attributed user message. If the bridge is unavailable, the plugin logs a local warning and continues: suggest mode is fail open.
- In `gate`, a `deny` decision returns `{ kind: "reject" }` before the model request. Bridge failure also returns reject: gate mode is fail closed. A missing prompt is rejected unless Harness is making an explicit empty continuation after step 1.
- If a downstream listener already rejects, PromptControlLab preserves that rejection.
- Harness abort signals cancel waiting; PromptControlLab does not create a separate retry loop.
- The first non-empty pre-step binds the stable run-level prompt identity. Later coordinates are inspected into redacted `preflight.turn-N.step-N.json` artifacts; an exact coordinate retry is idempotent, while reusing that coordinate with different content is rejected.

### Tool gate: `tools/pre-execute`

- In `suggest`, `allow`, `ask`, and `deny` all delegate to the next Harness listener.
- In `gate`, `deny` prevents dispatch, `ask` delegates to Harness approval, and `allow` delegates normally.
- If the bridge is unavailable in `gate`, the tool is denied with a bounded reason. If the Harness signal is already aborted, the tool is denied as cancelled.

`bridgeFailure` is normalized to `warn` in `suggest` and `block` in `gate`; a configuration value cannot turn gate mode into fail open behavior.

## Privacy Defaults

Only `capture: redacted` is supported by the native reference integration.

| Input | Persisted representation |
|---|---|
| Raw prompt | Crosses local stdio only for synchronous `harness_pre_step`; persists as SHA-256 identity, findings, and decision, never as the raw prompt body. |
| Tool arguments | SHA-256 over a stable projection plus sorted top-level argument keys. |
| Tool results | Error flag, bounded error name/code, turn-conclusion flag, and content-block count. |
| Assistant content | Never copied into PromptControlLab events; `assistant/chunk` is skipped. |
| Hidden reasoning | Hidden reasoning, chain-of-thought, thinking fields, and reasoning content are not persisted. |
| API keys | API keys, authorization headers, tokens, and credential-shaped values are not persisted. |
| Paths | Replay sanitization hashes workspace/repository paths instead of retaining them. |

Redaction reduces retained content; it is not a guarantee that arbitrary user-supplied metadata is harmless. Review policies and artifacts before sharing them.

## Bounded Feedback and Observation

- `feedbackMaxChars` defaults to `600`; prompt suggestions, tool reasons, and recovery recommendations are truncated to that bound.
- `observationQueueSize` defaults to `256`; one worker serializes asynchronous observations.
- Queue overflow drops the new noncritical observation, increments a counter, and writes a warning. Missing observations must be treated as missing evidence.
- `autoRecover` defaults to `false` and is transmitted to the bridge. Automatic steering requires three conditions: `autoRecover: true`, `harness_auto_recover: true` (or `harness.auto_recover: true`) in the selected policy, and `maxAutoRecoveries > 0`. Otherwise the bridge returns `recover: false`.
- `maxAutoRecoveries` defaults to one. The plugin counts steering actions within each control run and will not exceed that configured bound; `0` disables recovery even when both opt-ins are true.
- Turn-end and finalization work use the critical lifecycle path and are flushed during plugin teardown.

## Collaboration With Harness Guards

The plugin does not replace or reproduce Harness's `repeat-tool-reminder`, timeout policies, approval system, retry policy, or tool guards. Those components remain authoritative in Harness.

PromptControlLab observes a `repeat_tool_reminder` signal when a source plugin identifies `repeat-tool-reminder`, and a `tool_timeout` signal when a timeout code or event is visible. These signals feed local cross-run stability views. They do not cause PromptControlLab to claim that it detected every loop or timeout, and they do not override the built-in guard decision.

## Replay and Report

Replay an existing Harness JSONL session into a new redacted control run:

```bash
pcl harness replay --session <session.jsonl> --out runs/harness-replay --json
```

Replay requires at least one user prompt so it can perform an honest preflight. It hashes content, removes hidden reasoning and raw content from persisted events, records the source-session hash, and does not rerun the agent.

If the external Harness process exits before plugin teardown runs, close the local run explicitly:

```bash
pcl harness finalize --runs .promptcontrol/runs --session <session-or-run-id> --outcome failed --exit-code 1 --json
```

This command does not invent missing activity. If no preflight was observed, it records an incomplete run with `insufficient_evidence` and states that no model request, tool execution, or code change was proven.

Resolve a local report by Harness session id or PromptControlLab run id:

```bash
pcl harness report --runs .promptcontrol/runs --session <session-or-run-id> --json
```

The result returns paths to locally available `report.md`, `report.html`, and `decision.json`. For the review request intended for upstream maintainers, see the [GitHub Discussion draft](github_discussion_deepseek_harness.md).
