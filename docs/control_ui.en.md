# Local Control UI

[中文](control_ui.zh.md) | [Control loop](control_loop.en.md) | [Benchmark](control_benchmark.en.md) | [Advanced diagnostics](research_from_paper.en.md)

The local React workflow cockpit reads versioned run artifacts through a bounded local FastAPI service. It does not require an account and is not the source of truth: JSON and JSONL remain authoritative, while the UI provides a review surface. The previous Streamlit interface remains available with `--legacy-streamlit`.

```bash
pcl ui --runs runs
pcl ui --runs runs --legacy-streamlit
```

## Navigation

The workflow order is fixed so an operator can review one decision from input to outcome:

**Change Review -> Before -> Run -> Why -> After -> Decision -> History -> Stability & Confidence**

| View | Purpose |
|---|---|
| **Change Review** | Read the conclusion, change type, likely causes, evidence coverage, observed outcome, and next action on one page. |
| **Before** | Inspect the prompt, authorization level, provider/agent selection, redaction state, and preflight decision before execution. |
| **Run** | Follow normalized control events and bounded status updates while a run is active or replayed. |
| **Why** | Review attribution evidence and the event references behind a diagnosis; missing evidence stays visible. |
| **After** | Compare the requested objective with recorded outputs and stability observations. |
| **Decision** | Read the final allow, suggest, gate, or insufficient-evidence decision with its reasons. |
| **History** | Compare versioned local runs and open their original artifacts. SQLite may accelerate this list, but it can be rebuilt from JSON. |
| **Stability & Confidence** | Read **Long-horizon goal influence**, local stability boundary, and local solution confidence checks in plain language; technical names and assumptions remain secondary details. |

## Flagship cases

When `pcl ui --runs docs/case_studies` is used, Change Review begins with three curated case cards: **Agent workflow optimization**, **Model change review**, and **Checkpoint promotion review**. Selecting a card updates the URL and keeps Before, Why, After, Decision, and Stability & Confidence aligned to the same nested `review/` artifacts. The Agent card remains technically labeled `prompt_change`; the product title does not imply that two Agent identities were compared.

## Local checkpoint CSV import

The Run view can create a descriptive local checkpoint Run from a CSV. Required columns are `seed`, `checkpoint_id`, `mean_score`, and either `stage` (`initial`, `mid`, `final`) or numeric `step`. Optional generation mismatch, selective-risk, trajectory, cost, and alignment fields are allowlisted. Uploads are limited to 1 MB and 1,000 finite rows, remain below the configured `runs` directory, and never imply a release decision when gate, model, prompt, or split provenance is missing. The write interface is disabled in the Hugging Face demo.

## Review boundaries

The UI explains recorded evidence; it does not create evidence that is absent from the artifacts. A visual trend is not causal proof, a green decision is not a safety proof, and a stability diagnostic is not a default control requirement. Export or share the versioned artifacts when a decision needs independent review.
