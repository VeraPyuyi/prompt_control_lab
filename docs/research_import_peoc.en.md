# Import Real PEOC Evidence

Use this workflow when you have a Prompt-Engineering-Optimal-Control (PEOC)
replication bundle and want a reviewable `prompt_control_lab` run. The importer
does not rerun the language models. It verifies, normalizes, and explains the
recorded evidence without promoting failed, unusable, partial, or missing
sections to positive evidence.

## Before You Start

Install the research and UI extras, then confirm that the bundle directory
contains its manifest and recorded result files:

```bash
pip install -e ".[research,ui]"
pcl doctor
```

The examples below use `<peoc-bundle>` for the local
`nmi_replication_bundle` directory and `runs/peoc-real` for the imported run.

## Step 1: Import The Bundle

**Operation**

```bash
pcl research-import peoc \
  --bundle <peoc-bundle> \
  --out runs/peoc-real \
  --portable
```

**What you get**

- `source_manifest.json`: discovered sources, sizes, roles, and SHA-256 hashes.
- `peoc_evidence.json`: normalized evidence sections and explicit statuses.
- `research_case_study.json`, `.md`, and `.html`: a bounded review narrative.
- `evidence_card.*`, `claim_check.*`, `research_gap_plan.*`,
  `research_gap_status.*`, and `research_bundle.*`: the downstream evidence chain.

**What it means**

The import succeeded only if required structured sources could be parsed and
their identities stayed stable while the import ran. `--portable` copies
eligible small JSON/CSV sources into the run, but intentionally leaves large
NPZ trajectory arrays as hashed references.

**Next**

Open `runs/peoc-real/research_case_study.html` before reading any headline as a
claim.

## Step 2: Read Statuses Before Scores

Each research section has one of these states:

| Status | Meaning | Can support a positive claim? |
|---|---|---|
| `available` | Real, parseable evidence passed the section checks. | Only within the stated limitation. |
| `partial` | Some required evidence is absent. | No. |
| `failed_validation` | A recorded validation gate failed. | No; retain it as negative evidence. |
| `unusable` | A real source exists but cannot support the analysis. | No. |
| `missing` | No qualifying source was discovered. | No. |

**Operation**

```bash
pcl claim-check --run runs/peoc-real --claim full-research
pcl gap-status --run runs/peoc-real
```

**What you get**

`claim_check.json/html` states whether the requested claim is supported, while
`research_gap_status.json/html` names incomplete diagnostics.

**What it means**

A failed full-research check is a useful result. It prevents hard-test scores
or one trajectory pair from being described as complete PEOC validation.

**Next**

Use `research_gap_plan.html` to decide whether the missing evidence should be
generated, imported, or explicitly left outside the claim.

## Step 3: Verify The Evidence Chain

**Operation**

```bash
pcl research-bundle --run runs/peoc-real --verify --strict
```

**What you get**

`research_bundle_verification.json/html` records the expected and observed hash
for every indexed artifact.

**What it means**

`pass` proves that the indexed local bytes match the generated bundle index. It
does not prove an API provider's hidden model weights or make the underlying
experiment representative of every task.

**Next**

Archive the run directory or share the portable small artifacts together with
the referenced source manifest.

## Step 4: Inspect The Research UI

**Operation**

```bash
pcl ui --runs runs --language en
```

Choose `peoc-real`, then open **Research Overview**.

**What you get**

The first section shows the real-bundle badge and manifest hash, status counts,
hard-method rows, the selected stationary/heterogeneous trajectory pair, failed
validation evidence, limitations, and a link to the local case-study report.

**What it means**

Imported summaries are labeled separately from fresh current-run diagnostics.
The UI never counts `partial`, `failed_validation`, `unusable`, or `missing` as
available.

**Next**

Use the current-run diagnostic commands only for evidence you actually have:

```bash
pcl soft-hard --soft soft_prompt.npz --vocab vocab_embeddings.npz --out runs/peoc-real/diagnostics
pcl trajectory --states hidden_states.npz --out runs/peoc-real/diagnostics
pcl riccati --trajectory hidden_states.npz --out runs/peoc-real/diagnostics
pcl tv-soft --predictions method_predictions.jsonl --out runs/peoc-real/diagnostics
```

Then refresh `gap-status`, `evidence-card`, `claim-check`, and
`research-bundle --verify --strict`.

## Overrides, Re-imports, And Safety

Use `--hard-summary`, repeated `--trajectory-file`, or
`--heterogeneity-summary` only when automatic discovery selects the wrong
source. Re-importing into an existing run requires `--overwrite`; the importer
replaces only its registered generated artifacts. On an ambiguous filesystem
failure it preserves the transaction backup for manual recovery instead of
guessing.

## Scientific Boundaries

- Hard-test aggregates are task- and model-dependent, not universal optimizer rankings.
- Turnpike-like decay is a trajectory diagnostic, not a proof of global LM stability.
- Riccati/DARE results apply to a fitted finite-dimensional surrogate only.
- A failed stage-heterogeneity validation remains negative evidence.
- A source hash establishes byte identity, not hidden model-weight identity.
- Imported results are recorded evidence, not a fresh execution by this tool.

See the public bounded example in
[`docs/case_studies/peoc_real/`](case_studies/peoc_real/README.md).
