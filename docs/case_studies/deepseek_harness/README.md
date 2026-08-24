# DeepSeek Harness Integration Status

This public-safe snapshot separates integration readiness from a real model-backed agent session.

## Observed

- The native Cordis plugin builds against Harness `0.1.1-rc.2` at commit `b150a551...`.
- Twenty-seven TypeScript contract tests pass.
- The active profile resolves the plugin, starts the persistent local bridge, and creates a redacted `ControlRun`.
- An external startup failure can be closed explicitly as `insufficient_evidence` without inventing preflight, model, tool, file, or test activity.
- A run cannot be finalized as completed unless matched model request/response evidence, a file read, a bounded file write, and a successful test execution were recorded.

## Not Yet Observed

The local environment did not contain `DEEPSEEK_API_KEY` at the recorded check. Therefore no real model request, tool read, controlled edit, or test execution is claimed. Replay and fixtures do not satisfy the live acceptance gate.

The machine-readable status is in [live_session_status.json](live_session_status.json). The next accepted run must use a disposable repository and capture the full chain: policy preflight, public model identity, PromptControlLab request identity, provider response identity where available, file read, bounded edit, test result, stability state, and final decision. A local request identifier is not represented as a provider-issued request identifier.
