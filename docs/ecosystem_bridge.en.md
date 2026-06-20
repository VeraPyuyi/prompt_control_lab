# Ecosystem Bridge

Promptfoo, DeepEval, LangSmith, Langfuse, and prompt-optimizer are strong at different parts of
the LLM engineering workflow:

- Promptfoo: evals, red-team tests, provider matrices, CI, and security reports.
- DeepEval: local LLM test runs, metrics, reasons, and CI-style evaluation artifacts.
- LangSmith: tracing, monitoring, online evals, agent trajectory debugging, and
  production dashboards.
- Langfuse: open-source observability, prompt management, evaluations, cost
  tracking, and self-hosted deployments.
- prompt-optimizer: user-facing prompt rewriting, prompt asset management, web/desktop/browser
  distribution, Prompt Garden, and interactive prompt testing.

`prompt_control_lab` should not replace those systems. Its job is to add a
paper-style prompt optimization evidence layer on top of their exported results.

## Where PCL Can Win

The strongest lane is not a broader dashboard. It is a narrower evidence layer
that the larger tools do not focus on:

| Tool | Strongest lane | PCL's complementary lane |
|---|---|---|
| Promptfoo | LLM evals, red-team/security tests, provider matrices, CI, and security reports. | Import Promptfoo eval results, then add paired uncertainty, prompt-only validity, evidence cards, claim checks, and paper-derived diagnostic gap closure. |
| DeepEval | Local LLM test runs, metric scores, reasons, and CI-style evaluation artifacts. | Import DeepEval TestRun JSON, then add paired prompt evidence, protocol hygiene, claim scope checks, and paper-diagnostic gap planning. |
| LangSmith | Agent tracing, observability, online/offline evals, deployment, and sandboxed agent infrastructure. | Turn LangSmith experiment exports into prompt-optimization evidence bundles that separate prompt effects from model, metric, and split confounds. |
| Langfuse | Open-source observability, prompt management, evaluation, cost tracking, and self-hosted traces. | Add research diagnostics that are usually outside observability platforms: soft-hard gap, hidden-state trajectories, Riccati surrogates, and time-varying control evidence. |
| prompt-optimizer | Prompt rewriting UX, prompt favorites/templates, model-calling app surface, and interactive testing. | Import prompt assets as auditable candidates, record content hashes, and produce the evidence gap plan required before making an improvement claim. |

The practical integration story is:

1. Use the external tool for what it already does well: collect traces, run evals,
   red-team, or manage prompt versions.
2. Export baseline/candidate results.
3. Run `pcl evidence-from` to create a local evidence bundle.
4. Run `pcl diagnose` and `pcl gap-status` to see which paper-derived evidence is
   present, missing, or newly closed.
5. Use `claim_check.md` to decide what strength of prompt-optimization claim is
   actually supported.

That keeps PCL focused on a defensible wedge: **research-grade prompt
optimization evidence**, not generic LLMOps.

## What PCL Adds

After importing an external baseline/candidate export, PCL writes:

- `imports/baseline/` and `imports/candidate/`: reproducible snapshots of the
  external data as PCL scored runs.
- `comparison/stats.json`: paired bootstrap CI, paired permutation p-value, and
  Holm-adjusted p-value.
- `comparison/comparison_validity.json`: prompt-only comparison checks for
  prompt identity, model identity, split hash, metric identity, statistical
  evidence, and slice regressions.
- `research_bundle.html/json`: the browser-first index for the linked research evidence.
- `evidence_card.html/md/json`: a compact reviewer-facing evidence card.
- `claim_check.html/md/json`: a direct answer to which claim scope the current
  evidence tier supports.
- `bridge_summary.html/md/json`: a concise explanation of what the external tool
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
`ecosystem_scorecard.html`, `ecosystem_scorecard.md`, `ecosystem_scorecard.json`,
`research_bundle.html`, `research_diagnostics.html`, `research_diagnostics.md`,
`research_diagnostics.json`, and one evidence bundle per
external tool:

- `runs/ecosystem-demo/promptfoo/`
- `runs/ecosystem-demo/langfuse/`
- `runs/ecosystem-demo/langsmith/`
- `runs/ecosystem-demo/deepeval/`
- `runs/ecosystem-demo/prompt-optimizer/`

The first four directories are scored evidence bundles. The `prompt-optimizer/`
directory is intentionally an asset bridge: it contains `prompt_assets.html`,
`prompt_optimizer_gap_plan.html`, and a bridge summary explaining which paired eval
evidence is still required before claiming that an optimized prompt improved.

Open `ecosystem_scorecard.html` first when you need a reviewer-facing cross-tool
positioning table. Start with the **Market readiness** block: it states where PCL should lead,
what it should learn from adjacent tools, what not to rebuild, and the next P1/P2 product moves.
Then read the full matrix: what each external tool is good at, what PCL adds, and which paper
diagnostics are still missing. The scorecard also links to each bridge summary, evidence card,
claim check, HTML report, and gap artifact when available. Use `ecosystem_scorecard.md` for
plain-text review. Then open each `bridge_summary.html` for tool-specific provenance.
You can also open the root directory in the local UI with
`pcl ui --runs runs/ecosystem-demo`; the Research Overview will show one row per
external-tool evidence bundle.

If you later edit a bridge bundle or rerun diagnostics, refresh the cross-tool
scorecard without rebuilding the whole demo:

```bash
pcl ecosystem-scorecard --run runs/ecosystem-demo
pcl ecosystem-scorecard --run runs/ecosystem-demo --summary
```

Use `--out <file-or-directory>` when you want to write a separate scorecard copy
for review. Use `--summary` when you want the terminal output to show only the
Market readiness status, first users, do-not-build list, and next moves instead
of the full JSON payload.

For a single external tool export, the recommended reviewer-first entry point is
`pcl evidence-audit`. It imports the external baseline/candidate export, writes the PCL comparison
evidence, checks paper-diagnostic gaps, verifies the original source export hashes, and verifies
the local research bundle hashes in one pass:

```bash
pcl evidence-audit \
  --tool promptfoo \
  --baseline-input examples/external/promptfoo_results.json \
  --candidate-input examples/external/promptfoo_results.json \
  --baseline-prompt-id baseline \
  --candidate-prompt-id candidate \
  --provider openai:gpt-4o-mini-20260601 \
  --split-hash external-demo-split \
  --out runs/from-promptfoo-audit
```

Open `evidence_audit_result.html` first when a human reviewer needs the one-command audit
summary. Use `evidence_audit_result.json` when automation needs the same status. The audit also
writes `evidence_gate_result.html` / `.json` so CI and reviewers can see the combined source and
bundle gate. Then open `bridge_summary.html`, `research_gap_status.html`,
`source_input_verification.html`, and `research_bundle_verification.html` for the full evidence
trail.

The audit also records source input provenance for the external baseline and candidate exports:
original path, path kind, resolved absolute path, byte size, SHA-256 hash, detected tool, and
imported row count. This lets reviewers verify which external export files the PCL evidence bundle
was built from, even if they later run verification from a different working directory.
To re-check those original exports later, run:

```bash
pcl source-verify --run runs/from-promptfoo-audit
```

`pcl evidence-audit` already writes `source_input_verification.json`, `.md`, and `.html`.
The standalone command refreshes the check later. It checks the external source exports
themselves; `pcl research-bundle --verify` checks the PCL evidence artifacts created from those
exports.
Use strict mode when this check should act as a CI gate:

```bash
pcl source-verify --run runs/from-promptfoo-audit --strict
```

Strict mode still writes the same JSON, Markdown, and HTML evidence, but returns a non-zero exit
code if any source export is changed, missing, or unchecked.

For a single reviewer or CI gate that checks both original source exports and the local research
bundle, run:

```bash
pcl evidence-gate --run runs/from-promptfoo-audit --strict
```

This writes `evidence_gate_result.json`, `.md`, and `.html`. Source-input verification and
research-bundle verification are required checks. Gap status and claim-check status are included
as advisory checks so reviewers can see missing paper diagnostics without treating a small external
smoke export as a complete hidden-state or control-theoretic study.

The demo automatically audits the bundle against the paper-derived evidence map.
To regenerate that diagnosis after editing the bundle, run:

```bash
pcl diagnose --run runs/ecosystem-demo
```

This writes `research_bundle.html`, `research_diagnostics.json`, `research_diagnostics.md`,
and `research_diagnostics.html` at the
root. For external-tool exports, `diagnose` reports evidence coverage and missing
research diagnostics; it does not fabricate hidden-state, soft-hard, Riccati, or
time-varying-control measurements.
After this step, `pcl ui --runs runs/ecosystem-demo` also shows a paper-evidence
gap table in Research Overview. The same report includes a remediation table with
the required inputs, copy-paste `pcl` command, expected artifact, and what that
artifact would explain. For browser review, open `research_gap_plan.html`; the paired
`research_gap_commands.ps1` and `.sh` files are review-first command scripts.
The UI shows the same plan and script list as first-class Research Overview
sections.

If you add diagnostics manually or import fresh external-tool evidence, refresh the browser-first
bundle index with:

```bash
pcl research-bundle --run runs/ecosystem-demo
```

This rewrites `research_bundle.html` and `research_bundle.json`. The JSON inventory includes
`bytes` and `sha256` for linked evidence files, while the self-generated bundle index files are
marked as generated index artifacts to avoid unstable self-referential hashes.
To use the recorded bundle hashes as a CI or reviewer gate, verify without refreshing and enable
strict mode:

```bash
pcl research-bundle --run runs/ecosystem-demo --verify --strict
```

Strict mode still writes `research_bundle_verification.json`, `.md`, and `.html`, then returns a
non-zero exit code if linked evidence files changed, disappeared, or cannot be checked.

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

DeepEval:

```bash
pcl evidence-from \
  --tool deepeval \
  --baseline-input examples/external/deepeval_baseline.json \
  --candidate-input examples/external/deepeval_candidate.json \
  --score-name exact_match \
  --model gpt-4o-mini-20260601 \
  --provider openai \
  --split-hash external-demo-split \
  --out runs/from-deepeval-evidence
```

prompt-optimizer asset import:

```bash
pcl import prompt-optimizer \
  --input examples/external/prompt_optimizer_favorites.json \
  --out runs/from-prompt-optimizer
```

This is deliberately not an `evidence-from` example: prompt-optimizer exports are prompt
assets/favorites/templates, not paired scored eval results. PCL records asset hashes, writes
a gap plan, and creates `eval_scaffold/` templates so the next scoring step is concrete:
fill `tasks.template.jsonl`, `baseline_predictions.template.jsonl`, and
`candidate_predictions.template.jsonl`, then run the generated analyze config.
Before scoring, run `pcl scaffold-check --run runs/from-prompt-optimizer` to catch placeholders,
missing model/provider fields, and non-paired ids.

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

Start with `bridge_summary.html` when explaining the ecosystem relationship to a
teammate, open `research_bundle.html` for reviewer navigation, open
`claim_check.html` when deciding what you can safely say, then open
`evidence_card.html` when reviewing the actual prompt optimization evidence. The
Markdown files remain available for plain-text review.
