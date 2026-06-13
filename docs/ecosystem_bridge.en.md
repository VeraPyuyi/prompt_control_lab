# Ecosystem Bridge

Promptfoo, LangSmith, and Langfuse are strong at different parts of the LLM
engineering workflow:

- Promptfoo: evals, red-team tests, provider matrices, CI, and security reports.
- LangSmith: tracing, monitoring, online evals, agent trajectory debugging, and
  production dashboards.
- Langfuse: open-source observability, prompt management, evaluations, cost
  tracking, and self-hosted deployments.

`prompt_control_lab` should not replace those systems. Its job is to add a
paper-style prompt optimization evidence layer on top of their exported results.

## What PCL Adds

After importing an external baseline/candidate export, PCL writes:

- `imports/baseline/` and `imports/candidate/`: reproducible snapshots of the
  external data as PCL scored runs.
- `comparison/stats.json`: paired bootstrap CI, paired permutation p-value, and
  Holm-adjusted p-value.
- `comparison/comparison_validity.json`: prompt-only comparison checks for
  prompt identity, model identity, split hash, metric identity, statistical
  evidence, and slice regressions.
- `evidence_card.md/json`: a compact reviewer-facing evidence card.
- `claim_check.md/json`: a direct answer to which claim scope the current
  evidence tier supports.
- `bridge_summary.md/json`: a concise explanation of what the external tool
  supplied, what PCL added, and what evidence is still missing.
- `report.html`: a local report that can be archived with the run.

This makes the bridge useful when you already trust another tool for eval or
observability, but still need to answer:

- Is the baseline/candidate comparison paired by the same examples?
- Did the model, provider, metric, or split change?
- Is the observed improvement statistically reliable?
- Which evidence is missing before claiming a prompt optimization result?

## One-Command Examples

The repository includes these files under `examples/external/`. A fresh demo
project created with `pcl init --path demo` also writes the same files under
`demo/examples/external/`, so wheel or `pipx` users can try the bridge without
cloning the source tree.

Run all bundled bridge examples at once:

```bash
pcl ecosystem-demo --examples examples/external --out runs/ecosystem-demo
```

This writes `runs/ecosystem-demo/README.md`, `ecosystem_demo.json`,
`research_diagnostics.md`, `research_diagnostics.json`, and one evidence bundle
per external tool:

- `runs/ecosystem-demo/promptfoo/`
- `runs/ecosystem-demo/langfuse/`
- `runs/ecosystem-demo/langsmith/`

Open each `bridge_summary.md` first. It explains what the external tool supplied,
what PCL added, and what evidence remains missing.
You can also open the root directory in the local UI with
`pcl ui --runs runs/ecosystem-demo`; the Research Overview will show one row per
external-tool evidence bundle.

The demo automatically audits the bundle against the paper-derived evidence map.
To regenerate that diagnosis after editing the bundle, run:

```bash
pcl diagnose --run runs/ecosystem-demo
```

This writes `research_diagnostics.json` and `research_diagnostics.md` at the
root. For external-tool exports, `diagnose` reports evidence coverage and missing
research diagnostics; it does not fabricate hidden-state, soft-hard, Riccati, or
time-varying-control measurements.
After this step, `pcl ui --runs runs/ecosystem-demo` also shows a paper-evidence
gap table in Research Overview. The same report includes a remediation table with
the required inputs, copy-paste `pcl` command, expected artifact, and what that
artifact would explain. For handoff, open `research_gap_plan.md`; the paired
`research_gap_commands.ps1` and `.sh` files are review-first command scripts.
The UI shows the same plan and script list as first-class Research Overview
sections.

Promptfoo:

```bash
pcl evidence-from \
  --tool promptfoo \
  --baseline-input examples/external/promptfoo_results.json \
  --candidate-input examples/external/promptfoo_results.json \
  --baseline-prompt-id baseline \
  --candidate-prompt-id candidate \
  --provider openai:gpt-4o-mini-20260601 \
  --split-hash external-demo-split \
  --out runs/from-promptfoo-evidence
```

Langfuse:

```bash
pcl evidence-from \
  --tool langfuse \
  --baseline-input examples/external/langfuse_export.json \
  --candidate-input examples/external/langfuse_export.json \
  --baseline-name baseline \
  --candidate-name candidate \
  --score-name exact_match \
  --model gpt-4o-mini-20260601 \
  --provider openai \
  --split-hash external-demo-split \
  --out runs/from-langfuse-evidence
```

LangSmith:

```bash
pcl evidence-from \
  --tool langsmith \
  --baseline-input examples/external/langsmith_runs.csv \
  --candidate-input examples/external/langsmith_runs.csv \
  --baseline-experiment baseline \
  --candidate-experiment candidate \
  --score-name exact_match \
  --model gpt-4o-mini-20260601 \
  --provider openai \
  --split-hash external-demo-split \
  --out runs/from-langsmith-evidence
```

## Pairing Rule

Paired statistics require shared example ids. Promptfoo exports usually expose
this through `testIdx`. Langfuse and LangSmith runs often have different
observation/run ids across experiments, so PCL now prefers stable sample ids
such as `example_id`, `dataset_item_id`, `reference_example_id`, `case_id`, or
`sample_id` when present.

If no shared ids exist, PCL refuses to compute paired statistics instead of
silently reporting an invalid comparison.

## Interpretation Boundary

The example files are intentionally tiny. A generated evidence card may say
`needs_review` because four samples are not enough to support strong statistical
claims. That is a feature, not a bug: PCL should make missing evidence visible
instead of turning a small smoke test into a benchmark claim.

Start with `bridge_summary.md` when explaining the ecosystem relationship to a
teammate, open `claim_check.md` when deciding what you can safely say, then open
`evidence_card.md` when reviewing the actual prompt optimization evidence.
