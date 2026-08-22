# PromptControlLab for DeepSeek Harness

Native Cordis integration that places PromptControlLab before model requests and tool execution, then
streams redacted lifecycle evidence to one persistent local Python bridge.

## What it does

1. `agent/pre-step` inspects the pending prompt. In `gate` mode, a deny decision returns
   `{ kind: "reject" }`, so Harness does not send a model request.
2. `tools/pre-execute` checks a hash-only tool projection. In `gate` mode, `deny` prevents dispatch and
   `ask` delegates to Harness approval.
3. Model, tool, session, and turn observations enter a bounded single-writer queue.
4. PromptControlLab attributes changes and builds local stability/history reports.

This is a heuristic governance and diagnostics layer. It is not a proof that an agent action is safe.

## Install into a Harness checkout

```bash
pcl install-plugin deepseek-harness --target ./plugins/prompt-control-lab
cd plugins/prompt-control-lab
npm ci
npm run build
```

Add the row from `cordis.patch.yml` to the active Harness profile. PromptControlLab must be installed so
`pcl bridge serve --transport stdio` is available to the Harness process.

## Safe default config

```yaml
- id: prompt-control-lab
  name: '@prompt-control-lab/deepseek-harness'
  config:
    mode: suggest
    policyPath: .promptcontrol/guard.policy.yaml
    capture: redacted
    feedback: summary
    autoRecover: false
    bridgeFailure: warn
    runsRoot: .promptcontrol/runs
    feedbackMaxChars: 600
    observationQueueSize: 256
    exposeStatusTool: false
```

`suggest` fails open when the bridge is unavailable. `gate` is forced to fail closed. Automatic steering
is disabled by default and is bounded by `maxAutoRecoveries` when explicitly enabled.

## Privacy boundary

- Raw prompts cross stdio only for synchronous inspection and must not be persisted by the Python bridge.
- Tool arguments are represented by a SHA-256 digest and top-level key names.
- Assistant text, hidden reasoning, chain-of-thought, API keys, and raw tool output are not copied into
  PromptControlLab events.
- The optional `pcl_status` tool is read-only and is registered only when `exposeStatusTool: true`.

See [COMPATIBILITY.md](COMPATIBILITY.md) for the pinned Harness contract and exact bridge schemas.
