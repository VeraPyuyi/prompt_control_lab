# Import dispersed server evidence

`pcl evidence` turns an existing experiment tree into a hashed evidence inventory and an explanation-first local report. It is useful when trajectory, Riccati, soft-hard, deployment, generation-aware, selective-risk, and agent-episode artifacts live in different directories.

## Step 1: scan without changing the server tree

**Operation**

```bash
pcl evidence scan \
  --root /path/to/experiments \
  --profile peoc-server \
  --out server_evidence_manifest.json
```

**What you get:** `server_evidence_manifest.json` with a deterministic order, byte size, SHA-256, adapter, role, media type, and load policy for every matched source.

**What it means:** the manifest records exactly which files are available for analysis. `.pt` files are metadata/hash only and `.npz` files are hash-only by default. Scanning does not run a model or edit the source tree.

**Next:** review `adapter_counts` and warnings. Missing adapters remain missing evidence; they are not silently imputed.

## Step 2: verify and normalize

**Operation**

```bash
pcl evidence import \
  --manifest server_evidence_manifest.json \
  --out runs/server-evidence
```

Add `--portable` to create a path-free `portable/` bundle containing only the public source manifest, evidence matrix, interpretability report, and claim check. Raw JSON/CSV, weights, and arrays are never copied by this server-evidence option.

**What you get**

| Artifact | What it records | What it explains |
|---|---|---|
| `source_manifest.json` | Verified source identity and hashes | Whether the evidence changed after scanning |
| `evidence_matrix.json` | Inputs, status, confidence, role, missing adapters | Which diagnostic questions can currently be answered |
| `interpretability_report.json/html` | Observation, explanation, scope, boundary, next action | How to read the result without hiding uncertainty |
| `claim_check.json` | Allowed and disallowed statements | Whether a universal or causal claim is supported |

**What it means:** each finding is classified as `mechanism`, `boundary`, `stability`, `uncertainty`, or `decision`. Original p-values, intervals, and statuses such as `CONFIRMATORY_FAIL_CLOSED` remain unchanged.

**Next:** open `interpretability_report.html` or select the run in `pcl ui --runs runs`.

## Seven built-in adapters

- `turnpike_a800`: trajectory decay, drift, and task heterogeneity.
- `riccati_ass_hyp`: local consistency of a fitted finite-dimensional DARE surrogate.
- `soft_hard_tv`: temporal structure, capacity, QAT, and projection-gap attribution.
- `deployment_gate`: why evidence passes, needs review, or remains fail-closed.
- `generation_aware`: teacher-forced/free-generation mismatch and pilot boundaries.
- `selective_risk`: AURC, fixed-coverage accuracy, and confidence-based selection.
- `agent_episode`: links prompts, tools, tests, verifiers, and per-round behavior.

## Claim boundary

This workflow supports bounded, observable interpretation. It does not prove universal prompt or checkpoint improvement, hidden-weight identity, global LLM stability, or strict causality without a controlled intervention. The public [server case study](case_studies/server_evidence/README.md) shows the exact aggregate evidence retained from one real snapshot.
