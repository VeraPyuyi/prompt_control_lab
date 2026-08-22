# Users

## Prompt and Agent Operators

Inspect a prompt before it leaves the machine, choose how much execution authority to grant, and review the decision with its event evidence. Start with `inspect`; move to `model`, `agent-scoped`, or `agent-full` only when the task requires that boundary.

## Agent Integrators

Connect a native lifecycle plugin or a guard adapter to the versioned event protocol. DeepSeek Harness is the flagship native Cordis integration; Codex, Cursor, Claude Code, and GitHub Action use guard-oriented surfaces. Integration does not silently grant agent authority.

## Model and Provider Operators

Select an explicit provider and model, inspect the adapter configuration, and keep public-model provenance claims limited to what the endpoint and artifacts actually record. Credential presence is configuration, not authorization.

## Reviewers and Maintainers

Use `control_run.json`, `events.jsonl`, and the decision artifacts to reconstruct what happened. Reports, the local UI, and the rebuildable SQLite index make review easier without replacing the source JSON.

## Evaluation Teams

Replay recorded events and run the synthetic control benchmark to detect protocol or analyzer regressions. Benchmark accuracy covers the bundled labels only; it does not measure real-agent performance, causal impact, or safety.

## Advanced Diagnostic Users

Use the optional evaluation and research commands for paired statistics, soft/hard projection, trajectories, Riccati surrogates, time-varying controls, or PEOC imports. Treat these as bounded diagnostics, not proof about a full language model and not a requirement for ordinary control runs.
