# prompt_control_lab Demo Storyboard (English)

Working title: prompt_control_lab: Preflight, Provenance, and Reproducible Evaluation for AI Coding Agents

Target length: 10-12 minutes. Voice: calm technical walkthrough. Visual style: hands-on 4K UI operation replay with enlarged screenshots, cursor movement, click highlights, command cards, and result callouts. Audience: developers who use Claude Code, Cursor, Codex, shell wrappers, or CI to run AI coding agents.

Positioning guardrails:

- Lead with agent prompt preflight, model provenance, and reproducible prompt regression.
- Treat guard, gate, and audit results as local evidence and review signals, not guarantees.
- Keep all artifacts local and stay focused on engineering evidence.

## Scene 01 - Why Preflight Exists

Duration: 45 seconds

Visual: `docs/assets/tutorial_workflows.en.png`

Narration:

prompt_control_lab sits before and after an AI coding agent. Before the agent runs, it checks whether the prompt is clear, scoped, policy-compliant, and cost-aware. After the run, it records model identity, reproducible evaluation evidence, gate status, diff audit signals, and local run history. The goal is not to claim that an agent is safe. The goal is to replace one-off impressions with inspectable evidence.

Commands:

```bash
pcl start
```

On-screen decision: "Use prompt_control_lab when a prompt is expensive, broad, risky, or should leave a reproducible trail."

## Scene 02 - Guard A Coding-Agent Prompt

Duration: 60 seconds

Visual: `docs/assets/tutorial_guard.en.png`

Narration:

Start with the prompt that a developer might send directly to an agent: "Fix this bug." The guard command turns that vague instruction into a structured preflight result. It reports the action, risk level, reasons, policy violations, required review, token estimate, and an improved prompt. The useful decision is whether to send the prompt onward, revise it first, or block it under a local policy.

Commands:

```bash
pcl guard --prompt "Fix this bug" --profile coding --policy examples/guard.policy.yaml --token-mode balanced --json
```

On-screen decision: "`suggest` means the prompt can be improved before the agent sees it; `block` means the local policy says to stop and revise."

## Scene 03 - Improve Before You Spend Tokens

Duration: 55 seconds

Visual: `docs/assets/tutorial_guard.en.png`

Narration:

The improve path is the lightweight version of preflight. It rewrites a prompt in plain language, adds the task goal, output format, assumptions, and stability rules, and estimates token cost. When connected to a previous run, it can include diagnostic hints such as regressed slices or broken examples. This is useful when the original request is not dangerous, but is too ambiguous for an expensive agent task.

Commands:

```bash
pcl improve --prompt "Answer the user question."
pcl improve --prompt-file prompts/current.txt --run runs/quick --out runs/improve
```

On-screen decision: "Use `guard` for policy decisions; use `improve` for a direct rewrite."

## Scene 04 - Local UI Walkthrough

Duration: 60 seconds

Visual: `docs/assets/tutorial_workflows.en.png`

Narration:

The local UI exposes the same workflow without requiring the viewer to remember every command. The workflow cards start with guard, continue into a quick report, then show gate, model drift, audit diff, and history. The UI is deliberately local: it reads artifacts from the working tree and run folders. It is a control surface for inspection, not a hosted dashboard.

Commands:

```bash
pcl ui --run runs/quick
```

On-screen decision: "Use the UI when reviewers need to inspect the same local evidence without reading raw JSON first."

## Scene 05 - Analyze: Build A Reproducible Run

Duration: 65 seconds

Visual: `docs/assets/tutorial_report.en.png`

Narration:

The analyze command is the shortest path from example data to a report. It creates a reproducible split, evaluates baseline and candidate predictions, computes metrics, runs paired statistics, writes explanations, and produces Markdown and HTML reports. The important idea is that the prompt change is tied to input files, prediction files, split hash, metric, and output artifacts. A result is no longer just "it felt better."

Commands:

```bash
pcl init --path demo
cd demo
pcl analyze --config promptcontrol.example.yaml --out runs/quick
```

On-screen decision: "A reproducible prompt report needs the data path, prediction path, split, metric, model identity, and artifact paths."

## Scene 06 - Gate And Report: Make The Decision Explicit

Duration: 60 seconds

Visual: `docs/assets/tutorial_report.en.png`

Narration:

After analysis, the report gives humans the evidence and the gate gives automation a compact decision. A gate policy can check minimum score, maximum regression, adjusted p-value, diagnostic risk, and model provenance rules. Passing a gate means the configured thresholds passed. It does not prove the prompt is correct, safe, or production-ready. If confidence intervals cross zero or a slice regresses, the decision should say that clearly.

Commands:

```bash
pcl report --run runs/quick --title "Candidate Prompt Report"
pcl gate --run runs/quick --policy examples/gate.policy.yaml
```

On-screen decision: "Gate results are policy outcomes: `pass`, `needs_review`, or `fail`."

## Scene 07 - Model Detect And Drift

Duration: 60 seconds

Visual: `docs/assets/tutorial_model_drift.en.png`

Narration:

Model provenance matters because prompt experiments are only clean when the model is stable enough to interpret the comparison. `model-detect` records provider, public model id, source, confidence, and warnings. `model-drift` compares a current run with history and marks whether the result is prompt-only, uncertain, or confounded by a model or provider change. It records public identity evidence; it does not prove a provider's hidden internal weight build.

Commands:

```bash
pcl model-detect --predictions examples/predictions_candidate.jsonl
pcl model-drift --run runs/current --history runs/previous --out runs/current/model_drift.json
```

On-screen decision: "If the model changed, call the result a model-plus-prompt comparison."

## Scene 08 - Audit Diff After The Agent Runs

Duration: 55 seconds

Visual: `docs/assets/tutorial_audit.en.png`

Narration:

Once an agent has changed files, `audit-diff` summarizes what changed. It counts source, test, docs, config, workflow, dependency, and generated files. It flags deleted tests, dangerous paths, redacted secret findings, possible public API changes, expected-path mismatches, and test command status. This is review triage. It helps a human inspect the right evidence first.

Commands:

```bash
pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit
pcl audit-diff --before main --after HEAD --expected-path src/promptcontrollab --out runs/audit
```

On-screen decision: "Audit diff explains what the agent changed; it does not infer task intent unless expected paths are supplied."

## Scene 09 - History: Compare Runs Over Time

Duration: 55 seconds

Visual: `docs/assets/tutorial_history.en.png`

Narration:

History turns scattered run folders into a local index. It records manifest data, model identity, prompt identity, metrics, gate status, risk categories, and artifact paths. Compare mode shows whether a newer run changed the prompt, model, score, gate result, slice behavior, or risk profile. This is how prompt work becomes a sequence of reviewable changes instead of disconnected experiments.

Commands:

```bash
pcl history index --runs runs/ --out runs/history_index.json
pcl history compare --a runs/old --b runs/new --out runs/history_compare.json
```

On-screen decision: "History is the local ledger for prompt identity, model provenance, gate status, and run artifacts."

## Scene 10 - Plugins, Skills, And CI

Duration: 60 seconds

Visual: `docs/assets/tutorial_workflows.en.png`

Narration:

prompt_control_lab can be placed where prompts enter the workflow. Claude Code hooks, Cursor rules and MCP-style tools, Codex skills, shell wrappers, and a GitHub Action template can all call the same local commands. The stable fields are designed for adapters: action, risk level, token report, plain summary, gate status, and audit summary. CI can run analysis, gate the result, and attach audit evidence to a pull request.

Commands:

```bash
pcl install-plugin codex
pcl install-plugin cursor
pcl install-plugin claude-code
pcl install-plugin github-action
```

On-screen decision: "Adapters should read structured fields and keep the human-readable summary visible."

## Scene 11 - Research Diagnostics: Soft-Hard, Trajectory, Riccati, TV-Soft

Duration: 70 seconds

Visual: `docs/assets/tutorial_report.en.png`

Narration:

The advanced commands are for prompt optimization research. `soft-hard` checks whether learned soft vectors project cleanly to real token embeddings. `trajectory` summarizes hidden-state drift and stability-like signals. `riccati` fits a finite-dimensional surrogate and reports closed-loop stability for that surrogate, not for the full language model. `tv-soft` compares static, time-varying, shuffled, and random control lanes to see whether gains are consistent with temporal structure.

Commands:

```bash
pcl soft-hard --soft soft_prompt.npz --vocab vocab_embeddings.npz --out runs/candidate/diagnostics
pcl trajectory --states hidden_states.npz --out runs/candidate/diagnostics
pcl riccati --trajectory hidden_states.npz --out runs/candidate/diagnostics
pcl tv-soft --predictions scored_methods.jsonl --out runs/candidate/diagnostics
```

On-screen decision: "Research diagnostics are evidence for interpretation and follow-up experiments, not deployment guarantees."

## Scene 12 - End-To-End Review Loop

Duration: 55 seconds

Visual: `docs/assets/tutorial_workflows.en.png`

Narration:

The full loop is simple: preflight the prompt, improve it when needed, run the agent, analyze the prompt change, record model provenance, gate the result, audit the diff, and compare history. Each step produces files that another person can inspect. The final message is the positioning of the project: local agent preflight, model provenance, and reproducible prompt evaluation.

Commands:

```bash
pcl guard --prompt "Fix this bug" --profile coding --policy examples/guard.policy.yaml --json
pcl analyze --config promptcontrol.example.yaml --out runs/quick
pcl gate --run runs/quick --policy examples/gate.policy.yaml
pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit
```

On-screen decision: "Ship the artifact package, not just a conclusion."
