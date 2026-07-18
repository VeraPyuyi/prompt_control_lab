# Real PEOC Evidence Bridge

Status: Design approved in conversation; written specification awaiting review.

Date: 2026-07-18

## Context

`prompt_control_lab` already exposes the paper-derived research commands
`research-demo`, `research-quickstart`, `diagnose`, `soft-hard`, `trajectory`,
`riccati`, and `tv-soft`. It can also generate evidence cards, claim checks,
gap status, and a verifiable research bundle.

The current one-command research experience is synthetic. The original
Prompt-Engineering-Optimal-Control (PEOC) workspace contains real experiment
summaries and hidden-state trajectory results, including negative and
incomplete findings. Those artifacts are not yet consumable as a first-class
`prompt_control_lab` run.

This design adds a native evidence bridge from the PEOC NMI replication bundle
to the existing research workflow. It does not replace the synthetic demo.
Instead, it makes the evidence source explicit and prevents synthetic,
missing, unusable, or failed-validation results from being presented as real
positive evidence.

## Problem

The paper-first positioning currently has three practical gaps:

1. A new user can run a synthetic research demo but cannot import the real PEOC
   replication evidence with one command.
2. Existing research reports do not expose a uniform origin and validity status
   for every diagnostic.
3. The Research Overview metric cards can clip at narrower desktop widths,
   which makes the evidence summary harder to inspect.

The bridge must close these gaps without strengthening the scientific claims.
In particular, it must preserve the following observations:

- stationary arithmetic trajectories have a stronger decay signature than the
  heterogeneous GSM8K trajectories in the available summaries;
- the stage-heterogeneity validation summary reports `FAIL`;
- the segmented soft summary contains rows but no usable observations
  (`n = 0`);
- no Riccati result artifact has been identified in the replication bundle;
- aggregate method means do not by themselves prove universal optimizer
  superiority.

## Goals

1. Import a PEOC NMI replication bundle into a normal
   `prompt_control_lab` run directory.
2. Hash and describe every source artifact used by the import.
3. Normalize hard-test method summaries, trajectory summaries, and
   stage-heterogeneity results into a stable JSON schema.
4. Represent real, synthetic, missing, unusable, and failed-validation evidence
   without conflating them.
5. Generate a reviewer-readable case study and connect it to the existing
   evidence-card, claim-check, gap-status, and research-bundle workflow.
6. Show the real evidence and its limitations in the local Research Overview.
7. Fix research metric-card clipping at 1280-pixel desktop widths and smaller
   viewports.
8. Keep the import local, dependency-free, deterministic, and testable with
   compact fixtures.

## Non-goals

- Re-running the original PEOC experiments.
- Copying the complete NMI bundle into a `prompt_control_lab` run.
- Recomputing hidden states, soft prompts, or Riccati matrices.
- Inferring missing per-seed values from aggregate means.
- Treating behavior on one task, model, or seed as universal.
- Proving operational language-model stability from fitted diagnostics.
- Replacing the existing generic third-party export importers.
- Adding commercial plans, pricing, hosted services, or private dashboards.

## User Experience

### Primary command

```bash
pcl research-import peoc \
  --bundle "D:\path\to\nmi_replication_bundle" \
  --out runs/peoc-real
```

The `peoc` subcommand leaves room for future native research-bundle adapters
without mixing them with third-party evaluation exports.

### Optional controls

```bash
pcl research-import peoc \
  --bundle "D:\path\to\nmi_replication_bundle" \
  --out runs/peoc-real \
  --hard-summary path/to/summary_acc_hard_test.json \
  --trajectory-file path/to/stationary.json \
  --trajectory-file path/to/heterogeneous.json \
  --heterogeneity-summary path/to/shi_r27_summary.json \
  --portable \
  --language zh
```

Arguments:

- `--bundle`: required PEOC NMI replication-bundle root.
- `--out`: required output run directory.
- `--hard-summary`: optional explicit hard-test summary override.
- `--trajectory-file`: repeatable explicit trajectory-summary override.
- `--heterogeneity-summary`: optional stage-heterogeneity summary override.
- `--portable`: copy compact JSON/CSV source artifacts into the run.
- `--language`: `en` or `zh`; controls the primary rendered case study while
  the normalized JSON schema remains language-neutral.
- `--overwrite`: required when a generated artifact already exists.

The command prints:

- the output directory;
- the number of source artifacts hashed;
- the number of available, missing, unusable, and failed-validation evidence
  sections;
- the main case-study HTML path;
- the strongest claim currently supported;
- warnings that require review.

### Expected output tree

```text
runs/peoc-real/
  manifest.json
  source_manifest.json
  peoc_evidence.json
  research_case_study.json
  research_case_study.md
  research_case_study.html
  evidence_card.json
  evidence_card.md
  evidence_card.html
  claim_check.json
  claim_check.md
  claim_check.html
  research_gap_plan.json
  research_gap_plan.md
  research_gap_plan.html
  research_gap_status.json
  research_gap_status.md
  research_gap_status.html
  research_bundle.json
  research_bundle.html
  research_bundle.zh.html
  source/                    # only when --portable is used
```

## Source Discovery

The importer requires the bundle root to exist and contain
`README_MANIFEST.md`. A directory that merely contains similarly named JSON
files is not accepted as a PEOC replication bundle.

### Default candidates

Paths are resolved relative to the bundle root:

1. Hard-test method summary:
   `experiments/redesign_v2/results_server_pull_20260524/strong_main_grid/summary_acc_hard_test.json`
2. Segmented soft summary:
   `experiments/redesign_v2/results_server_pull_20260524/strong_main_grid/summary_soft_segmented.json`
3. Stage heterogeneity:
   `experiments/redesign_v2/stage_heterogeneity/shi_r27_summary.json`
4. Stationary trajectories:
   `experiments/turnpike_trace/results_a800/stationary_arith_*.json`
5. Heterogeneous trajectories:
   `experiments/turnpike_trace/results_a800/turnpike_gsm8k_*.json`
6. Supporting trajectory arrays:
   the `.npz` sibling of each selected stationary or heterogeneous trajectory
   JSON, when present.

### Precedence and ambiguity

1. An explicit CLI override has highest priority.
2. Otherwise, the exact default path is used when one is defined.
3. Globbed trajectory files are sorted by normalized relative path.
4. Trajectories are paired by normalized model identifier and seed. When a
   summary omits its seed field, the importer parses `_s<integer>` from the
   source filename and records that provenance.
5. The case-study headline pair prefers Qwen2.5-7B seed 0 when present.
6. If that pair is absent, the first complete shared model/seed pair in sorted
   order is used.
7. Every additional valid trajectory summary remains in
   `peoc_evidence.json`; it is not silently discarded.
8. Supporting NPZ siblings are hashed as `trajectory_binary` sources but are
   never parsed or copied by default.
9. Multiple exact candidates or malformed explicit overrides are errors, not
   arbitrary selections.

The selected path and the selection reason are recorded for every evidence
section.

## Source Manifest

`source_manifest.json` records:

```json
{
  "schema": "prompt_control_lab.peoc_source_manifest.v1",
  "bundle": {
    "resolved_path": "D:\\path\\to\\nmi_replication_bundle",
    "manifest_relative_path": "README_MANIFEST.md",
    "manifest_sha256": "sha256:..."
  },
  "sources": [
    {
      "role": "hard_test_summary",
      "relative_path": "experiments/.../summary_acc_hard_test.json",
      "resolved_path": "D:\\path\\to\\...\\summary_acc_hard_test.json",
      "bytes": 1234,
      "sha256": "sha256:...",
      "media_type": "application/json",
      "selection": "default_exact_path",
      "copied_path": null
    }
  ],
  "warnings": []
}
```

Resolved local paths support auditability but are shown only in the JSON
manifest, not in the rendered case-study pages. The report uses bundle-relative
paths to avoid exposing local usernames in screenshots or shared HTML.

By default, source files are referenced and hashed but not copied.
`--portable` copies only JSON and CSV files that are at most 10 MiB each and
50 MiB in total. NPZ files are never copied by `--portable`; they remain hashed
references. Skipped files produce warnings.

## Evidence Model

`peoc_evidence.json` uses:

```json
{
  "schema": "prompt_control_lab.peoc_evidence.v1",
  "evidence_source": "peoc_nmi_replication_bundle",
  "sections": {
    "hard_method_evaluation": {},
    "soft_segmented_evaluation": {},
    "trajectory_decay": {},
    "stage_heterogeneity": {},
    "riccati_surrogate": {},
    "soft_to_hard": {},
    "time_varying_control": {}
  },
  "claim_boundary": {},
  "warnings": []
}
```

Every section contains separate origin and status fields:

- `origin`: `real`, `synthetic`, or `none`.
- `status`: `available`, `missing`, `unusable`, or `failed_validation`.
- `display_status`: `REAL`, `SYNTHETIC`, `MISSING`, `UNUSABLE`, or
  `FAILED_VALIDATION`.
- `source_roles`: source-manifest roles supporting the section.
- `observations`: normalized measurements.
- `limitations`: section-specific interpretation boundaries.

This separation is required because a real source file can exist while its
contents are unusable. The segmented soft summary is the canonical example:
its origin is `real`, its status is `unusable`, and its display status is
`UNUSABLE` because every row has `n = 0`.

### Hard-test method evaluation

The importer preserves each summary row:

- model;
- task;
- horizon `T`;
- prompt length `L0`;
- budget;
- method;
- mean;
- standard deviation;
- observation count.

Rows with missing or zero observation counts are excluded from evidence-backed
comparisons and retained in an `excluded_rows` list with reasons.

Source-provided test results are preserved when their schema is valid. The
importer does not manufacture paired tests from aggregate means. Descriptive
method rankings are labeled descriptive, task-specific, and model-specific.

### Trajectory decay

The importer records all valid trajectory summaries and builds explicit
stationary/heterogeneous pairs. For each summary it preserves:

- model and seed;
- trace/task type;
- stream or prompt count;
- sequence limit;
- hidden dimension;
- empirical decay mean;
- fit-quality mean;
- any source-provided dispersion fields.

The main case study compares the selected paired summaries. It may state that
the available stationary arithmetic traces exhibit a stronger fitted decay
signature than the available GSM8K traces. It may not claim a universal
turnpike law or causal mechanism.

### Stage heterogeneity

The source verdict, held-out correlations, confidence intervals, and cell
summaries are preserved. A source verdict of `FAIL` maps to:

- `origin: real`;
- `status: failed_validation`;
- `display_status: FAILED_VALIDATION`.

Reports must show this as a negative result, not merely a warning hidden below
positive findings.

### Missing and unusable diagnostics

- No Riccati result source: `origin: none`, `status: missing`.
- Segmented soft rows with `n = 0`: `origin: real`, `status: unusable`.
- A malformed source: import fails for a required section or marks an optional
  section unusable with a precise warning.
- A source containing non-finite numeric values: values are serialized as
  `null`, with their JSON path recorded in warnings.

All JSON is written with strict serialization (`allow_nan = false`).

## Claim Boundaries

The bridge introduces no new scientific claim. It packages existing evidence
and makes its limits machine-readable.

Allowed report language:

- "In the imported PEOC summaries, the stationary arithmetic traces show a
  stronger fitted decay signature than the heterogeneous GSM8K traces."
- "Method performance is task-dependent in the imported hard-test summaries."
- "The stage-heterogeneity validation reported FAIL."
- "The available segmented soft summary contains no usable observations."
- "No Riccati artifact was found in the imported bundle."

Disallowed report language:

- "Turnpike behavior is universal in LLM prompting."
- "Time-varying control is always superior."
- "The operational language model is Riccati-stable."
- "Soft prompts can be safely rounded for deployment" when soft-hard evidence
  is absent.
- "The imported evidence proves the paper's full hypothesis."

`claim_check.json` must fail closed. Missing, unusable, or failed-validation
sections can lower the supported claim tier but can never be counted as
positive coverage.

## Integration With Existing Research Workflow

The importer is a native paper-evidence adapter, not a generic third-party
export adapter. Its implementation belongs in a new module:

```text
src/promptcontrollab/peoc_import.py
```

Responsibilities:

- validate and discover bundle sources;
- hash and optionally copy source artifacts;
- normalize finite JSON values;
- classify evidence status;
- build the case-study model;
- write source and evidence artifacts.

`cli.py` adds the `research-import peoc` parser and delegates to this module.

Existing modules are extended, rather than duplicated:

- `evidence_card.py` reads `peoc_evidence.json` when present.
- `claim_check.py` applies the explicit evidence statuses and claim boundary.
- `research_workflow.py` writes a gap plan from the missing/unusable PEOC
  sections, derives gap status from that plan, and includes all PEOC artifacts
  in the research bundle.
- `ui/data.py` normalizes PEOC evidence for the Research Overview.
- `ui/app.py` renders the real-evidence case study and limitations.
- `ui/components.py` renders responsive metric cards.

The existing synthetic research demo continues to work unchanged and records
`origin: synthetic` for its generated diagnostics.

## Case-study Rendering

`research_case_study.json` is the single rendering model for Markdown and HTML.
The renderers do not re-parse prose.

The first screen contains:

1. evidence-source badge: `REAL PEOC BUNDLE`;
2. source-manifest hash;
3. available/failed/unusable/missing counts;
4. selected model/task context;
5. strongest supported claim;
6. one visible limitations statement.

The body contains:

1. hard-test method table by model and task;
2. stationary versus heterogeneous trajectory comparison;
3. stage-heterogeneity negative result;
4. missing/unusable diagnostic table;
5. source provenance table using relative paths and hashes;
6. next commands for filling evidence gaps;
7. exact claim boundary.

English and Chinese renderings use the same JSON values. Labels and explanatory
text are localized; numbers, hashes, statuses, and schema fields are not.

## UI Design

The Research Overview adds:

- an evidence-origin badge;
- a source status summary;
- real hard-test method comparison;
- stationary/heterogeneous trajectory cards;
- a prominent failed-validation panel;
- a missing/unusable evidence panel;
- a link to `research_case_study.html`.

Metric cards must not use one fixed Streamlit column per card. They are rendered
with an escaped HTML grid:

```css
grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
```

The grid wraps at 1280-pixel desktop, tablet, and mobile widths. Card labels and
values use wrapping and overflow-safe rules. No evidence card may be clipped
outside the main content area.

The UI shows real and synthetic runs distinctly:

- `REAL`: green/teal neutral evidence badge;
- `SYNTHETIC`: blue demo badge;
- `FAILED_VALIDATION`: red status;
- `UNUSABLE` and `MISSING`: amber/gray status.

Color is never the only signal; every state includes text.

## Error Handling

The command returns a concise `pcl: error:` message for:

- missing bundle directory;
- missing `README_MANIFEST.md`;
- an explicit source path that does not exist;
- invalid JSON;
- an unrecognized required source schema;
- an output path that already contains generated artifacts without
  `--overwrite`;
- a source path that resolves to the output directory;
- a portable-copy size-limit violation when no referenced fallback is
  possible.

Optional missing diagnostics do not abort the import. They are recorded as
missing evidence. Required provenance or hard-test files do abort because a
"real PEOC import" without bundle identity or primary evaluation evidence would
be misleading.

Warnings are stable objects with:

```json
{
  "code": "non_finite_value",
  "source_role": "stage_heterogeneity",
  "json_path": "$.cells[2].score",
  "message": "Non-finite value was normalized to null."
}
```

## Security and Privacy

- The importer reads source artifacts and writes only under `--out`.
- It does not execute scripts from the bundle.
- It does not unpickle arbitrary files.
- It does not upload data or make network requests.
- It parses JSON and CSV with standard-library readers.
- It hashes binary sources as bytes without loading them as executable objects.
- Rendered reports omit absolute local paths.
- Source hashes provide tamper evidence for the imported snapshot, not a
  cryptographic signature or proof of scientific correctness.

## Testing

Tests use compact repository fixtures, never the external PEOC workspace.

### Unit tests

- valid PEOC layout discovery;
- missing bundle and missing manifest;
- explicit source override precedence;
- deterministic trajectory pairing;
- hard-summary row normalization;
- zero-count segmented soft rows classified as unusable;
- stage-heterogeneity `FAIL` preserved;
- missing Riccati evidence preserved;
- non-finite numbers converted to `null` with warnings;
- source hashes and byte counts;
- portable copy includes compact JSON/CSV and excludes NPZ;
- strict JSON serialization;
- case-study claim wording does not exceed the evidence boundary.

### CLI tests

- minimal `pcl research-import peoc` succeeds;
- existing output requires `--overwrite`;
- explicit malformed source gives a concise error;
- English and Chinese reports are generated;
- generated artifacts can be consumed by `evidence-card`, `claim-check`,
  `gap-status`, and `research-bundle`.

### UI tests

- real evidence badge and status rows are normalized correctly;
- failed validation remains visible;
- missing/unusable sections are not counted as positive evidence;
- metric cards render through the responsive grid;
- escaped labels cannot inject HTML;
- the 1280-pixel Research Overview does not clip the rightmost card.

### Full regression

```bash
python -m pytest
python -m ruff check .
python -m mypy src tests
git diff --check
python -m promptcontrollab doctor --json
```

## Rollout and Compatibility

1. Add the importer and compact fixtures.
2. Connect the normalized evidence to existing evidence and claim modules.
3. Add the case-study renderers.
4. Add the Research Overview panels and responsive metric grid.
5. Update English and Chinese research documentation.
6. Run a local import against the real PEOC bundle as an integration smoke
   test without committing private absolute paths or large source files.
7. Commit only normalized, explicitly reviewed public artifacts if publication
   is desired later.

No existing CLI command is renamed. Existing run directories without
`peoc_evidence.json` continue to load. The synthetic demo remains the default
zero-input research experience, while the real bridge becomes the recommended
path when a PEOC replication bundle is available.

## Acceptance Criteria

The design is complete when:

1. one command imports the real PEOC bundle into a self-describing run;
2. every evidence section exposes origin, status, provenance, and limitations;
3. the real negative and unavailable results remain visible;
4. the generated claim check cannot promote missing or failed evidence;
5. the case-study report opens without access to the original workspace;
6. large NPZ artifacts are not copied by default;
7. the Research Overview distinguishes real and synthetic evidence;
8. metric cards wrap without clipping at 1280 pixels;
9. existing research commands and tests remain compatible;
10. all full-regression checks pass.
