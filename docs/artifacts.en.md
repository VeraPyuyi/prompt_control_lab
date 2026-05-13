# Artifacts

PromptControlLab keeps inspectable files for each run instead of only reporting a final score.

## `manifest.json`

Records tool version, run mode, method name, metric, data path, prediction path, and optional
model identity.

What it explains: how the score was produced and which public model id was recorded.

## `splits.json`

Records train, validation, and withheld ids, split hash, seed, counts, and leakage report.

What it explains: whether the data was separated cleanly and whether the split can be reproduced.

## `predictions.jsonl`

Stores output, expected answer, score, slice, method, error, and optional model provenance for
each item.

What it explains: which exact examples passed or failed.

## `pcl model-detect` output

Stores `provider`, `model_id`, `source`, `confidence`, optional public metadata such as
`created` and `owned_by`, and warnings.

What it explains: whether the artifacts record the public model id used for a run. It does not
prove a provider's hidden internal weight build.

## `model_drift.json`

Stores previous/current provider and model id, a drift risk level, and a short reason.

What it explains: whether a comparison is still prompt-only, or whether model changes make the
result harder to interpret. Alias model ids are treated as reproducibility risks.

## `metrics.json`

Stores count, overall mean score, and slice-level mean scores.

What it explains: whether a prompt improved overall while regressing on a task slice.

## `stats.json`

Stores paired comparison results: mean delta, bootstrap confidence interval, permutation p-value,
and Holm-adjusted p-value.

What it explains: whether an observed change is reliable or still uncertain.

## `explanation.json`

Stores a plain or technical explanation of the run: verdict, evidence strength, data hygiene,
slice changes, example changes, deployment risk, next action, `plain_summary`, and a
`deployment_recommendation`.

What it explains: what the artifacts mean for a reader who does not want to inspect every file.

## `gate_result.json`

Stores the result of applying a policy file to a run.

What it explains: whether the run passes, needs review, or fails configured thresholds. It also
includes `plain_summary`, so plugins and reports can show the result without exposing raw JSON.
When model policy keys are configured, it also records model provenance checks such as unknown
model, model mismatch, alias model, provider allow-list, and verification requirements.

## `pcl guard --json` output

Stores an input-layer prompt guard result when used by hooks, rules, or shell wrappers.

Important fields:

- `plain_summary`: human-readable advice, such as "add target files and acceptance criteria"
- `action`: `suggest`, `auto`, or `block`
- `risk_level`: `low`, `medium`, or `high`
- `improved_prompt`: the guarded prompt to send onward
- `risk_categories`: examples include `destructive_change`, `security`, `production_path`,
  `broad_refactor`, `token_budget`, or team policy categories
- `policy_violations`: built-in or policy-triggered rule violations
- `required_review`: whether a human should review the prompt before execution

What it explains: whether a prompt is clear enough to send to an AI tool and what to add first.

## `improved_prompt.txt`

Stores the prompt produced by `pcl improve`.

What it explains: the recommended plain-language rewrite of the original prompt.

## `prompt_improvement.json`

Stores the original prompt, improved prompt, detected language, goal, style, changes, and report
context notes. It also includes `token_report`, a dependency-free estimate of original and
improved prompt tokens, token mode, optional budget, and whether the rewrite fits that budget.

What it explains: why the tool changed the prompt, which diagnostic hints were used, and how the
rewrite affects estimated prompt-token cost. The `plain_summary` field gives a one-sentence,
non-technical explanation that plugins and simple wrappers can show directly.

## `prompt_diff.md`

Stores the original prompt, improved prompt, a readable list of changes, and estimated token cost.

What it explains: what changed in the prompt without reading JSON.

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
