# Real PEOC Import: Bounded Case Study

This public-safe snapshot was generated on 2026-08-22 by running
`pcl research-import peoc --portable` against the local PEOC NMI replication
bundle. It contains derived summaries and relative source paths only. No local
absolute path or NPZ array was copied into this directory.

## Provenance

- Evidence origin: `real`
- Source files discovered: `14`
- Original bundle manifest: `sha256:8254ca7c122405739369d64e9629493c2fd6c66d9a367466fde1ef1d0375d72f`
- Generated source-manifest hash: `sha256:cbedb26eb5722da4cdd1fb11644162167cb4a5c46f0db21cae45dba9bc7a8769`
- Public source inventory: `14/14` records contain a relative path and SHA-256 hash.
- Full-research support: `false`
- Claim check: `fail`
- Evidence recommendation: `not_supported`

## Evidence Status

| Section | Status | Recorded result | Interpretation |
|---|---|---|---|
| hard evaluation | `available` | 72 valid rows; 3 models, 4 tasks, 6 methods | Useful task/model/method measurements, not a universal ranking. |
| trajectory | `available` | selected stationary/heterogeneous pair | Supports a bounded comparison of fitted decay signatures. |
| stage heterogeneity | `failed_validation` | verdict `FAIL`; held rho `-0.5429`, CI `[-1.0, 0.6364]` | Negative evidence; cannot support a stage-control selector. |
| segmented soft evaluation | `unusable` | no row with positive sample count | Cannot support a positive soft-evaluation claim. |
| Riccati/DARE | `missing` | no qualifying source discovered | No Riccati claim is supported by this bundle. |
| soft-to-hard | `missing` | no projection diagnostic discovered | No deployment projection claim is supported. |

Status totals: `available=2`, `partial=0`, `failed_validation=1`,
`unusable=1`, `missing=2`.

## What The Hard Results Actually Show

Across the 12 model-task cells, `tv_pmp` exceeded `static_autograd` in 6 and
trailed it in 6. Its unweighted descriptive mean cell delta was `+0.0063`, with
a range from `-0.0566` to `+0.0449`; it was the highest-mean method in 2 of 12
cells. These are descriptive aggregates, not a significance test. The result is
task-dependent and does not support universal optimizer superiority.

## Selected Trajectory Pair

| Lane | Model | Seed | Empirical decay | Mean R2 | Traces |
|---|---|---:|---:|---:|---:|
| stationary arithmetic | Qwen/Qwen2.5-7B-Instruct | 0 | `0.02471` | `0.6020` | 16 |
| heterogeneous GSM8K | Qwen/Qwen2.5-7B-Instruct | 0 | `0.001741` | `0.0880` | 32 |

The selected stationary summary has a stronger fitted decay signature than the
heterogeneous GSM8K summary. This is a trajectory diagnostic, not proof of
global language-model stability.

## Strongest Safe Claim

This bounded case study reports imported PEOC measurements and their recorded
limitations. The hard-test summary contains task-, model-, and method-specific
results; the selected stationary trajectory summary has a stronger fitted
decay signal than the heterogeneous summary; stage heterogeneity failed its
recorded validation; and the segmented soft summary is unusable for a positive
claim. It is not a universal benchmark or a complete PEOC validation.

Machine-readable evidence: [research_case_study.json](research_case_study.json).
Import tutorial: [research_import_peoc.en.md](../../research_import_peoc.en.md).
