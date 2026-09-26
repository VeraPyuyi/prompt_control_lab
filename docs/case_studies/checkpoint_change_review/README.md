# Checkpoint Change Review

This public-safe case reuses the recorded aggregate evidence from the real three-seed SFT pilot and feeds it through the unified Change Review workflow:

```text
aggregate initial checkpoint
  -> aggregate final checkpoint
  -> comparison validity
  -> attribution and stability
  -> candidate checkpoint gate
  -> reviewer-facing decision
```

Run it locally:

```bash
pcl review --baseline docs/case_studies/checkpoint_change_review/baseline --candidate docs/case_studies/checkpoint_change_review/candidate --out runs/checkpoint-review
pcl ui --runs runs/checkpoint-review --language en
```

## What changed

The expected checkpoint identity changed from `aggregate-initial` to `aggregate-final`. The recorded model, evaluation prompt, split, metric, and Agent identity stayed fixed in the public aggregate manifests.

## What was observed

| Observation | Initial | Final |
|---|---:|---:|
| Mean task score | 0.0885 | 0.1944 |
| Generation mismatch | 0.5729 | 0.4670 |
| Selective-risk AURC | 0.8712 | 0.6674 |
| Trajectory drift | 8.3955 | 8.8259 |

The final score was higher, and generation mismatch and selective risk moved in a favorable direction. Trajectory drift increased, the format-following slice stayed at zero, and the source checkpoint gate required `hold`.

![Checkpoint score, diagnostic, and gate evidence](comparison.en.svg)

- **What changed:** the compared stage moved from the aggregate initial checkpoint to the aggregate final checkpoint across the same three seeds.
- **What was observed:** mean score rose from `0.0885` to `0.1944`; generation mismatch and selective-risk AURC decreased, while representation trajectory drift increased.
- **What this can and cannot explain:** the recorded training stage is associated with a different performance and risk profile, but the aggregate evidence does not identify a unique causal mechanism or prove deployment safety.
- **Next action:** keep the promotion on `hold` and inspect the triggered stability, generation, and readout evidence before release.

## Why the decision is `hold`

Change Review does not replace a source gate with a single score. The candidate's recorded post-training gate is therefore preserved: promotion remains on hold until the stability and generation/readout findings are resolved or justified.

## Evidence boundary

This case supports a bounded association between the recorded SFT stage and the observed performance, efficiency, stability, and risk profile. It does not identify a unique causal mechanism, prove general model improvement, or establish deployment safety.

## Artifacts

- [`case_manifest.json`](case_manifest.json): compact case summary.
- [`baseline/manifest.json`](baseline/manifest.json) and [`candidate/manifest.json`](candidate/manifest.json): comparison identities.
- [`review/change_review.json`](review/change_review.json): top-level decision.
- [`review/comparison_validity.json`](review/comparison_validity.json): identity and confounder checks.
- [`review/human_feedback.json`](review/human_feedback.json): fixed reviewer questions.
- [`review/decision_trace.json`](review/decision_trace.json): checks that produced the decision.
- [`checkpoint_visualization.json`](checkpoint_visualization.json): the canonical data used by React and the static figures.
- [`checkpoint_metrics.csv`](checkpoint_metrics.csv): normalized public-safe checkpoint rows.
- [`comparison.en.svg`](comparison.en.svg) and [`comparison.zh.svg`](comparison.zh.svg): bilingual linked views.

Only aggregate evidence is included. No prompts, per-example generations, model weights, credentials, hidden reasoning, or private paths are stored here.
