# Local Control UI

[中文](control_ui.zh.md) | [Control loop](control_loop.en.md) | [Benchmark](control_benchmark.en.md) | [Advanced diagnostics](research_from_paper.en.md)

The local UI reads versioned run artifacts from disk. It does not require an account and is not the source of truth: JSON and JSONL remain authoritative, while the UI provides a review surface.

```bash
pcl ui --runs runs
```

## Navigation

The workflow order is fixed so an operator can review one decision from input to outcome:

**Before -> Run -> Why -> After -> Decision -> History -> Advanced**

| View | Purpose |
|---|---|
| **Before** | Inspect the prompt, authorization level, provider/agent selection, redaction state, and preflight decision before execution. |
| **Run** | Follow normalized control events and bounded status updates while a run is active or replayed. |
| **Why** | Review attribution evidence and the event references behind a diagnosis; missing evidence stays visible. |
| **After** | Compare the requested objective with recorded outputs and stability observations. |
| **Decision** | Read the final allow, suggest, gate, or insufficient-evidence decision with its reasons. |
| **History** | Compare versioned local runs and open their original artifacts. SQLite may accelerate this list, but it can be rebuilt from JSON. |
| **Advanced** | Open optional PEOC, soft/hard, trajectory, Riccati, and `tv-soft` diagnostics when their assumptions and evidence are available. |

## Review boundaries

The UI explains recorded evidence; it does not create evidence that is absent from the artifacts. A visual trend is not causal proof, a green decision is not a safety proof, and an Advanced diagnostic is not a default control requirement. Export or share the versioned artifacts when a decision needs independent review.
