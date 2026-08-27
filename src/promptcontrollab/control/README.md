# Control

## Purpose

`promptcontrollab.control` defines the local closed-loop protocol for prompts and AI agents. It records a versioned `ControlRun`, accepts ordered lifecycle events, performs preflight decisions, analyzes attribution and stability, and produces a bounded final decision.

## Use cases

- Start an inspect-only or provider/agent-scoped control run.
- Gate a model request or tool execution before downstream work occurs.
- Replay ordered events from an agent integration without duplicating them.
- Explain which inputs changed and whether an observed run is converging, stalled, oscillating, or diverging.

## CLI commands

```bash
pcl control --prompt "Inspect the request" --authorization inspect --out runs/control
pcl trace import --input traces.jsonl --format auto --out runs/imported
pcl trace serve --host 127.0.0.1 --port 4318 --out runs/observed
pcl bridge serve --transport stdio
pcl harness replay --session session.jsonl --out runs/harness-replay
pcl harness finalize --runs runs --session session-id
```

## Python API

The approved canonical package exposes protocol records and workflow entry points:

```python
from promptcontrollab.control import (
    ControlEvent,
    ControlRun,
    analyze_attribution,
    analyze_stability,
    run_control,
)
```

Additional public contracts include `PreflightDecision`, `AttributionReport`, `StabilityReport`, `ControlDecision`, `ControlBridge`, and `EventLog`.

## Inputs/Artifacts

- Inputs: prompt or prompt digest, authorization scope, policy, provider/model metadata, and ordered lifecycle events.
- Outputs: `control_run.json`, `events.jsonl`, `preflight.json`, `attribution.json`, `stability.json`, `decision.json`, `report.md`, and `report.html`.
- Event IDs and sequence numbers support deterministic replay and deduplication.

## Dependencies

The protocol, event log, analysis, and stdio bridge use the default dependency-free runtime plus `core` and `preflight`. Provider and agent implementations enter through `integrations` rather than the control domain importing them directly.

## Extension points

- Add versioned event kinds without changing existing event meanings.
- Add attribution dimensions and stability signals with explicit evidence and confidence.
- Add adapters that translate external agent events into the stable control protocol.
- Import OpenTelemetry GenAI and OpenInference observations through a redacted,
  deterministic trace adapter.

## Limitations

- Attribution is evidence-based association, not strict causal identification.
- Stability labels are heuristic summaries of observable events and may be `insufficient_evidence`.
- Automatic steering and recovery must remain opt-in and bounded by policy.
- The local trace receiver accepts OTLP JSON over HTTP, not OTLP protobuf. It is
  observation-only: it never blocks, retries, or modifies downstream execution.
- Trace ingestion stores prompt/content hashes, lengths, and approved metadata rather
  than raw prompt, response, authorization, credential, or reasoning content.

## Tests/Examples

See the control-loop guide, benchmark fixtures, and DeepSeek Harness integration tests. Run:

```bash
python -m pytest tests -k "control or bridge or attribution or stability"
```
