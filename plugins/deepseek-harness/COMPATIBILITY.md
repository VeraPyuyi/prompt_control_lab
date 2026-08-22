# Compatibility contract

This plugin is contract-tested against DeepSeek Harness `0.1.1-rc.2` at commit
`b150a551b8d465e31e418e1b2eaf5e79bbb7d28e`. The machine-readable source of truth is
[`compatibility.json`](compatibility.json).

The integration is a native Cordis plugin. It uses the public waterfalls documented by Harness:

- `agent/pre-step`: `{ kind: "reject" }` prevents the model request.
- `tools/pre-execute`: `{ kind: "deny", reason }` prevents tool dispatch.
- `agent/request` and `agent/request-error`: observe provider/model and failures without owning retries.
- `tools/post-execute` and `tools/result`: observe normalized and immutable outcomes.
- `session/event`: records redacted durable event metadata; `turn/end` is a session event, not a Cordis event.
- `agent/turn-stopping`: registered only when `autoRecover` is explicitly enabled.

The plugin does not reproduce Harness repeat-tool or timeout policies. It records signals produced by
`repeat-tool-reminder` and timeout failures so PromptControlLab can compare them across runs.

## Bridge alignment

The TypeScript bridge method wrappers are isolated in `src/bridge.ts`. Python must implement the seven
`harness_*` methods exactly as declared in `compatibility.json`. The raw prompt in
`harness_pre_step.params.prompt` is ephemeral inspection input. Python must persist only
`prompt_hash`, findings, decisions, and explicitly authorized metadata.

If Harness changes an event signature, update the pinned commit, this contract, and the native contract
tests together. Compatibility with unlisted Harness revisions is not claimed.
