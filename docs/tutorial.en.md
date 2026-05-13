# Step-by-Step Tutorial

This tutorial uses the format "operation -> result -> what it explains".

## Beginner Mode: Choose a Scenario

Operation:

```bash
pcl start
```

Result:

- a three-option menu: improve a prompt, guard a prompt, or create a report
- plain-language output for the selected scenario

What it explains:

This is the lowest-friction entry point. Use it when terms like `profile`, `gate`, or
`stats` are not familiar yet.

## Quick Mode: One Command

Operation:

```bash
pcl init --path demo
cd demo
pcl analyze --config promptcontrol.example.yaml --out runs/quick
```

Result:

- `runs/quick/splits.json`
- `runs/quick/baseline/metrics.json`
- `runs/quick/candidate/metrics.json`
- `runs/quick/stats.json`
- `runs/quick/explanation.json`
- `runs/quick/report.md`
- `runs/quick/report.html`

What it explains:

This is the shortest path for non-specialists. The report says whether the candidate prompt
looks better, how reliable the evidence is, which examples changed, and what to inspect next.

## Simplest Prompt Improvement

Operation:

```bash
pcl improve --prompt "Answer the user question."
```

Token-conscious operation:

```bash
pcl improve --prompt "Answer the user question." --token-mode aggressive --max-tokens 80
```

Operation with an existing report:

```bash
pcl improve --prompt-file prompts/current.txt --run runs/quick --out runs/improve
```

Result:

- optimized prompt printed in the terminal
- `runs/improve/improved_prompt.txt`
- `runs/improve/prompt_improvement.json`
- `runs/improve/prompt_diff.md`
- estimated token counts in the terminal, JSON, and Markdown diff

What it explains:

The command gives a clearer prompt with a task goal, output-format rules, and stability rules.
With `--run`, it also uses previous diagnostics to add simple warnings about regressed slices,
broken examples, or deployment risk. The default token mode is `balanced`, which keeps key
constraints while reducing unnecessary wording. `aggressive` is shorter and useful when cost is
more important, but it may remove some guardrails. `--max-tokens` is an estimated budget.

## Prompt Guard for IDE and CLI Agents

Operation:

```bash
pcl guard --prompt "Fix this bug" --profile coding --token-mode balanced --json
```

Hook-friendly operation:

```bash
echo "Fix this bug" | pcl guard --stdin --profile coding --json
```

Result:

- `plain_summary`
- `action`
- `risk_level`
- `improved_prompt`
- `token_report`
- `reasons`

What it explains:

This command is for prompt-input plugins. Use it before Claude Code, Cursor, Codex, or a shell
wrapper sends a prompt to a model. `plain_summary` is written for humans; `action`, `risk_level`,
and `token_report` are stable fields for plugins. `suggest` returns a safer prompt, `auto` marks
it as ready to use, and `gate` can block high-risk or over-budget prompts.

Team policy operation:

```bash
pcl guard --prompt "Fix this bug" --profile coding --policy examples/guard.policy.yaml --json
```

This adds configurable required fields, dangerous-pattern rules, risk categories, and
`required_review` to the guard output.

## Expert Mode: Step by Step

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

## 3.5. Detect Model Identity

Operation:

```bash
pcl model-detect --predictions examples/predictions_candidate.jsonl
```

Result:

- JSON printed in the terminal with `provider`, `model_id`, `source`, `confidence`, and warnings.

What it explains:

This tells you which public model id is recorded in the prediction file. If baseline and
candidate use different model ids, the later comparison is a model+prompt comparison, not a
clean prompt-only comparison.

## 3.6. Audit Model Drift

Operation:

```bash
pcl model-drift --run runs/current --history runs/previous --out runs/current/model_drift.json
```

Result:

- `runs/current/model_drift.json`

What it explains:

This file says whether a comparison is low risk, uncertain because model identity is missing,
or confounded by a model/provider change. Alias model ids are marked as reproducibility risk.

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

Decision guide:

- CI crosses zero -> do not claim a reliable improvement yet.
- p-value is high -> the evidence is weak, even if the mean score improved.
- p-value is high but gate passes -> the policy likely checks minimum score or allowed
  regression, not proof of improvement.
- average improves but a slice regresses -> inspect that slice before keeping the prompt.

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

## 6. Generate Plain or Technical Explanations

Operation:

```bash
pcl explain --run runs/quick --level plain
pcl explain --run runs/quick --level technical
```

Result:

- `runs/quick/explanation.json`

What it explains:

Plain explanations are written for readers who want the conclusion quickly. Technical
explanations keep artifact paths and raw comparison details for audit and reproduction.

## 7. Apply a Gate Policy

Operation:

```bash
pcl gate --run runs/quick --policy examples/gate.policy.yaml
```

Result:

- `runs/quick/gate_result.json`

What it explains:

The gate returns `pass`, `needs_review`, or `fail` based on thresholds such as minimum
candidate score, maximum regression, adjusted p-value, and optional diagnostic risk.

## 8. Check Soft-to-Hard Risk

Operation:

```bash
pcl soft-hard --soft soft_prompt.npz --vocab vocab_embeddings.npz --out runs/candidate/diagnostics
```

Result:

- `runs/candidate/diagnostics/soft_hard.json`

What it explains:

Large projection distances mean the learned soft vectors are far from real token embeddings.
In that case, strong soft prompt performance does not guarantee hard prompt deployability.

## 9. Inspect Hidden-State Trajectories

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

## 10. Run Riccati Surrogate Diagnostics

Operation:

```bash
pcl riccati --trajectory hidden_states.npz --out runs/candidate/diagnostics
```

Result:

- `runs/candidate/diagnostics/riccati.json`

What it explains:

A closed-loop spectral radius below 1 means the fitted finite-dimensional surrogate is stable in
this diagnostic. It is not a proof about the full language model.

## 11. Compare a Time-Varying Soft-Control Lane

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
