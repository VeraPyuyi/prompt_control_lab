# Artifacts

PromptControlLab keeps inspectable files for each run instead of only reporting a final score.

## `manifest.json`

Records tool version, run mode, method name, metric, data path, and prediction path.

What it explains: how the score was produced.

## `splits.json`

Records train, validation, and withheld ids, split hash, seed, counts, and leakage report.

What it explains: whether the data was separated cleanly and whether the split can be reproduced.

## `predictions.jsonl`

Stores output, expected answer, score, slice, method, and error for each item.

What it explains: which exact examples passed or failed.

## `metrics.json`

Stores count, overall mean score, and slice-level mean scores.

What it explains: whether a prompt improved overall while regressing on a task slice.

## `stats.json`

Stores paired comparison results: mean delta, bootstrap confidence interval, permutation p-value,
and Holm-adjusted p-value.

What it explains: whether an observed change is reliable or still uncertain.

## `diagnostics/soft_hard.json`

Stores nearest-token projection indices and distances for a soft prompt.

What it explains: whether soft-to-hard projection may lose behavior.

## `diagnostics/trajectory.json`

Stores hidden-state drift, log-decay slope, fit quality, and turnpike-like signal.

What it explains: whether the internal trajectory looks more stable or more drifting.

## `diagnostics/riccati.json`

Stores surrogate closed-loop spectral radius, theory decay rate, and stability label.

What it explains: whether the fitted finite-dimensional surrogate is internally stable.

## `diagnostics/tv_soft.json`

Stores means for static, time-varying, shuffled, and random method groups.

What it explains: whether time-varying gains are more consistent with temporal structure.

## `report.md` / `report.html`

Collects split hygiene, metrics, statistics, and diagnostics into a readable report.

What it explains: whether the prompt change should be kept and what should be inspected next.

