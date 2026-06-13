# Artifacts

PromptControlLab keeps inspectable files for each run instead of only reporting a final score.

## `manifest.json`

Records tool version, run mode, method name, metric, data path, prediction path, optional
model identity, and optional prompt identity (`prompt_hash`, `prompt_id`, `prompt_file`,
`prompt_version`).

What it explains: how the score was produced and which public model id was recorded.
For Quick Mode paired prompt experiments, the top-level manifest may also include
`baseline_prompt` and `candidate_prompt`, while each child run manifest stores its own `prompt`
identity for `pcl validity`.

## `splits.json`

Records train, validation, and withheld ids, split hash, seed, counts, and leakage report.

What it explains: whether the data was separated cleanly and whether the split can be reproduced.

## `predictions.jsonl`

Stores output, expected answer, score, slice, method, error, and optional model provenance for
each item.

What it explains: which exact examples passed or failed.

When written by `pcl ingest promptfoo`, `score` comes from Promptfoo's exported result score or
pass/fail value. That run can then be used with `pcl stats`, `pcl validity`, and `pcl report`.

## `pcl model-detect` output

Stores `provider`, `model_id`, `source`, `confidence`, optional public metadata such as
`created` and `owned_by`, request evidence such as `request_id`, `request_sha256`,
`response_sha256`, optional `provider_log_reference`, optional `signed_receipt`,
`provenance_level`, `provenance_evidence`, and warnings.

What it explains: whether the artifacts record the public model id used for a run. It does not
prove a provider's hidden internal weight build.

Provenance levels are explicit: user-declared model id, observed response/prediction model id,
provider metadata verification, provider-log reference recorded, and signed-receipt reference
recorded. The signed-receipt field records a reference only; this tool does not verify provider
signatures. Most public APIs do not expose a signed model receipt, so this is audit evidence
rather than hidden-weight proof.

## `model_drift.json`

Stores previous/current provider and model id, a drift risk level, and a short reason.

What it explains: whether a comparison is still prompt-only, or whether model changes make the
result harder to interpret. Alias model ids are treated as reproducibility risks.

## `audit_result.json`

Stores the result of `pcl audit-diff`: changed files, per-file added/deleted line counts,
source/test/docs/config counts, dependency/lockfile/workflow changes, deleted tests, generated
files, redacted secret findings, dangerous paths, possible public API changes, test commands,
test status, per-command `test_results` with stdout/stderr snippets and timeout state,
expected-path checks, and whether human review is required.

The built-in secret scanner records `secret_scanner_scope: added_diff_lines`. Optional external
scanners such as `gitleaks` and `trufflehog` record `secret_scanner_scope: workspace`, because
they scan the current workspace and may report pre-existing findings outside the requested
`before`/`after` diff.

What it explains: what an AI coding agent changed after it ran. If `--expected-path` is not
provided, `unnecessary_file_edits` is `null` because the tool does not pretend to know the
original task intent.

## `audit_summary.md`

Stores a readable summary of `audit_result.json`.

What it explains: which files changed, which risk signals were found, and what a reviewer should
look at first.

## `pcl.sarif`

Optionally written by `pcl audit-diff --sarif runs/audit/pcl.sarif`.

What it explains: the same high-signal audit findings in a GitHub Code Scanning compatible shape:
secret-like added lines, dangerous paths, workflow changes, dependency changes, deleted tests, and
public API-like changes.

## `history_index.json`

Stores a local index of run directories, including manifest data, model identity, prompt identity,
metrics, gate status, risk categories, and artifact paths.

What it explains: what runs exist in a local `runs/` folder and what each run recorded.

## `history_compare.json`

Stores a comparison between two run directories: prompt identity match, model match, metric delta,
gate status change, slice regressions, and new or resolved risk categories.

What it explains: whether a newer run changed the prompt, model, score, gate result, or risk
profile compared with an older run.

## `comparison_validity.json` / `comparison_validity.md`

Written by `pcl validity --baseline runs/baseline --candidate runs/candidate --out
runs/candidate/comparison_validity.json`.

What it explains: whether the recorded artifacts support a clean prompt-only comparison. It checks
prompt identity, model identity, split hash, metric identity, paired statistical evidence, and
slice regressions. `clean` means the comparison is well supported by artifacts; `needs_review`
means evidence is incomplete or uncertain; `invalid` means a blocking confound such as model,
metric, or split mismatch was found.

## `agent_run.json`

Stores a compact agent execution manifest: prompt identity, agent name, provider/model, policy,
gate decision, risk level, changed files, tests, audit path, gate path, and whether human review is
required.

What it explains: how the preflight, model provenance, gate result, and diff audit connect to one
AI coding agent run.

## `pr_summary.md` / `pr_summary.json`

Stores a reviewer-facing PR summary built from `audit_result.json`, `gate_result.json`, and
optional `agent_run.json`.

What it explains: whether a PR should pass, fail, or receive human review, plus labels such as
`prompt-control-lab:needs-review`, dangerous paths, missing tests, workflow/dependency changes, or
secret findings.

## `pcl doctor` output

Stores or prints local setup checks: Python version, package import, CLI parser, optional
`OPENAI_API_KEY`, guard policy parsing, Claude Code hook, Cursor MCP server, demo report
generation, and optional research dependencies.

What it explains: whether the local installation is ready for normal CLI and plugin workflows,
and where a user should look if setup failed.

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
If `comparison_validity.json` exists, the gate also consumes it: `invalid` becomes a hard failure,
`needs_review` becomes a review item, and `clean` passes the comparison-validity check.

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
