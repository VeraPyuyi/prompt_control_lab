# Innovation and Contribution

PromptControlLab makes authorization, observation, and evidence explicit in a local prompt and agent control loop.

## 1. Graduated authorization

The `inspect`, `model`, `agent-scoped`, and `agent-full` levels separate review from model access and agent execution. A workflow can add only the authority it needs, and credentials do not silently select a higher level.

## 2. Versioned open event protocol

Normalized `prompt_control_lab.control_event.v1` events let native plugins, guard adapters, replays, reports, and benchmarks share one inspectable contract. Schema versions are stored with the artifacts instead of being inferred from UI state.

## 3. Local evidence authority

JSON and JSONL are the source of truth. Reports and the local UI are derived views, and SQLite is a rebuildable index. This keeps a run reviewable even when a display layer or index is unavailable.

## 4. Bounded agent feedback

Agent integrations declare suggest or gate behavior, redact persistent data by default, bound feedback and queues, and preserve existing agent guards instead of claiming ownership of them.

## 5. Deterministic replay and benchmark

Recorded events can be replayed through the same analyzer. The open synthetic benchmark checks the classification contract across known trace types without presenting fixture accuracy as real-agent performance.

## 6. Evidence-linked explanation

Attribution, stability, and decision records point back to normalized events. Unsupported conclusions can remain `insufficient_evidence` rather than being filled in by a report or UI.

## Advanced diagnostics

The existing statistical evaluation, soft/hard, hidden-state trajectory, Riccati surrogate, time-varying control, and PEOC evidence tools remain available as optional Advanced Diagnostics. Their contribution is bounded analysis under stated assumptions, not a universal theory claim.
