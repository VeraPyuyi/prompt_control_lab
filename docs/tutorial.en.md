# Step-by-Step Tutorial

This tutorial uses the format "operation -> result -> what it explains".

## 1. Initialize an Example

Operation:

```bash
pcl init --path demo
cd demo
```

Result:

- `examples/tasks.jsonl`
- `examples/predictions_baseline.jsonl`
- `examples/predictions_candidate.jsonl`
- `promptcontrol.example.yaml`

What it explains:

These files show the minimal input format: task id, input, expected answer, task slice, and
outputs from different prompts or methods.

## 2. Create a Train/Validation/Withheld Split

Operation:

```bash
pcl split --data examples/tasks.jsonl --out runs/candidate --seed 0
```

Result:

- `runs/candidate/splits.json`

What it explains:

The split hash makes the split reproducible. The leakage report checks whether train,
validation, and withheld ids overlap. If they overlap, the evaluation is not clean.

## 3. Score Baseline and Candidate Outputs

Operation:

```bash
pcl eval --data examples/tasks.jsonl \
  --predictions examples/predictions_baseline.jsonl \
  --out runs/baseline \
  --metric exact_match \
  --method baseline

pcl eval --data examples/tasks.jsonl \
  --predictions examples/predictions_candidate.jsonl \
  --out runs/candidate \
  --metric exact_match \
  --method candidate
```

Result:

- `runs/baseline/predictions.jsonl`
- `runs/baseline/metrics.json`
- `runs/candidate/predictions.jsonl`
- `runs/candidate/metrics.json`

What it explains:

`predictions.jsonl` shows output and score for every item. `metrics.json` shows overall score
and slice-level scores. Slice scores reveal cases where the average improves while a task group
regresses.

## 4. Run the Statistical Comparison

Operation:

```bash
pcl stats --baseline runs/baseline/predictions.jsonl \
  --candidate runs/candidate/predictions.jsonl \
  --out runs/candidate/stats.json
```

Result:

- `runs/candidate/stats.json`

What it explains:

The file contains mean delta, bootstrap confidence interval, paired permutation p-value, and
Holm-adjusted p-value. If the interval crosses zero, the change is still uncertain. If the
adjusted p-value is small and the interval stays above zero, the improvement is more reliable.

## 5. Generate a Report

Operation:

```bash
pcl report --run runs/candidate --title "Candidate Prompt Report"
```

Result:

- `runs/candidate/report.md`
- `runs/candidate/report.html`

What it explains:

The report gathers split hygiene, metrics, statistics, and diagnostics into one readable file.

## 6. Check Soft-to-Hard Risk

Operation:

```bash
pcl soft-hard --soft soft_prompt.npz --vocab vocab_embeddings.npz --out runs/candidate/diagnostics
```

Result:

- `runs/candidate/diagnostics/soft_hard.json`

What it explains:

Large projection distances mean the learned soft vectors are far from real token embeddings.
In that case, strong soft prompt performance does not guarantee hard prompt deployability.

## 7. Inspect Hidden-State Trajectories

Operation:

```bash
pcl trajectory --states hidden_states.npz --out runs/candidate/diagnostics
```

Result:

- `runs/candidate/diagnostics/trajectory.json`

What it explains:

Mean step drift describes how strongly the trajectory moves step to step. A negative log-decay
slope with good fit quality suggests motion toward a stable region. High drift or weak fit
suggests more heterogeneous internal behavior.

## 8. Run Riccati Surrogate Diagnostics

Operation:

```bash
pcl riccati --trajectory hidden_states.npz --out runs/candidate/diagnostics
```

Result:

- `runs/candidate/diagnostics/riccati.json`

What it explains:

A closed-loop spectral radius below 1 means the fitted finite-dimensional surrogate is stable in
this diagnostic. It is not a proof about the full language model.

## 9. Compare a Time-Varying Soft-Control Lane

Operation:

```bash
pcl tv-soft --predictions scored_methods.jsonl --out runs/candidate/diagnostics
```

Result:

- `runs/candidate/diagnostics/tv_soft.json`

What it explains:

If `time_varying` beats `static` while `shuffled_tv` and `random_tv` do not, the gain is more
consistent with temporal structure. If shuffled or random variants also improve, inspect capacity
and selection effects.

