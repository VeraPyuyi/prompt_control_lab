# Which Tool Should I Use First?

`prompt_control_lab` is not trying to replace Promptfoo, LangSmith, Langfuse, DeepEval, or
prompt-optimizer. Use those tools for creation, tracing, testing, or security. Add PCL when the
result needs to become reviewer-facing evidence for prompt optimization.

One-sentence rule: **create and test elsewhere; use PCL when you need to prove what the result
actually supports.**

## Five-Minute Adoption Path

| Minute | Do this | You should get |
|---:|---|---|
| 1 | Pick the adjacent tool path with `pcl choose --need "<your goal>"`. | A plain recommendation and the next PCL command. |
| 2 | Import existing Promptfoo/Langfuse/LangSmith/DeepEval output with `pcl start --choice import --tool auto --input results.json --out runs/from-external`. | `manifest.json` and `bridge_summary.html`. |
| 3 | Add paper-derived checks with `pcl evidence-audit ...` or `pcl research-quickstart --out runs/research-demo --open-report`. | `evidence_card.html`, `claim_check.html`, and `research_bundle.html`. |
| 4 | Open the first HTML artifact named by the command output. | A reviewer-readable answer to what changed and what is still missing. |
| 5 | If `claim_check` or `gap_status` says review, do not claim "better prompt" yet. | A bounded next action instead of an overclaim. |

## Shortest Path

| If this is your problem | Copy this first |
|---|---|
| "I want to see the product quickly." | `pcl quickstart --out demo --open-report` |
| "I do not know which adjacent tool fits." | `pcl choose --need "<your goal>"` |
| "I need security or red-team evals." | `pcl choose --need "security evals and red-team checks"` |
| "I already have Promptfoo/Langfuse/LangSmith/DeepEval output." | `pcl start --choice import --tool auto --input results.json --out runs/from-external` |
| "I need a local UI demo for model drift, audit, history, or prompt comparison." | `pcl quickstart --out demo --open-report`, then `pcl ui --runs demo/runs --policy demo/examples/guard.policy.yaml` |
| "I need the paper-derived diagnostics." | `pcl research-quickstart --out runs/research-demo --open-report` |
| "I need a reviewer-facing market/evidence scorecard." | `pcl start --choice ecosystem --out runs/ecosystem-demo` |

## 30-Second Map

| Your starting point | Use first | Add PCL when you need |
|---|---|---|
| You need eval matrices, CI checks, or red-team/security tests. | Promptfoo | Paired uncertainty, prompt-only validity, claim boundaries, and paper diagnostics. |
| You want Pytest-style LLM unit tests and many ready-made metrics. | DeepEval | Prompt/model/split provenance, paired uncertainty, and claim checks around those test results. |
| You need traces, agent debugging, datasets, or LangChain/LangGraph observability. | LangSmith | A reproducible evidence bundle that separates prompt effects from model, metric, and split changes. |
| You need open-source tracing, prompt management, evals, cost, or self-hosting. | Langfuse | Soft-hard gap, trajectory/Riccati/tv-soft diagnostics, and bounded research claims. |
| You want a polished prompt writing app. | prompt-optimizer | Proof that the optimized prompt is reproducibly better before deployment or publication. |
| You want a local reviewer cockpit for model drift, diff audit, history, and reports. | PCL local UI | One browser view over PCL's guard, report, model drift, audit, history, and workflow artifacts. |
| You already have baseline/candidate outputs. | PCL | Evidence card, claim check, gap status, provenance, and research bundle verification. |

## Copy-Paste Paths

Ask for a direct recommendation:

```bash
pcl choose --need prompt-writing
pcl choose --need "security evals and red-team checks" --json
```

Save the recommendation for review:

```bash
pcl choose --need "security evals and red-team checks" --out runs/tool-choice.json
pcl start --choice choose --need "security evals and red-team checks" --out runs/tool-choice.json
```

This writes `runs/tool-choice.json` and `runs/tool-choice.md`.
Use the `pcl start --choice choose` form when you want the same advisor inside beginner mode.

The same advisor is available in the local UI under **Research Overview**.

## From Market Gap to PCL Command

| What another tool leaves you with | Gap before you can make a strong claim | Run next | Open first |
|---|---|---|---|
| Promptfoo eval or red-team export | Scores exist, but paired uncertainty and prompt-only validity may still be unclear. | `pcl evidence-audit --tool promptfoo ... --out runs/from-promptfoo-audit` | `evidence_audit_result.html` |
| DeepEval TestRun output | Metrics exist, but prompt/model/split provenance and claim boundary need review. | `pcl import deepeval --input test-run.json --out runs/from-deepeval` | `manifest.json`, then `pcl evidence-card` |
| LangSmith/Langfuse trace or eval export | Traces exist, but prompt effects may be confounded with model, metric, or split changes. | `pcl start --choice import --tool auto --input results.json --out runs/from-external` | `bridge_summary.html` |
| prompt-optimizer favorites/templates | Better prompt candidates exist, but they are not yet paired scored evidence. | `pcl import prompt-optimizer --input favorites.json --out runs/from-prompt-optimizer` | `prompt_optimizer_gap_plan.html` |
| PCL run artifacts | Reviewer needs one navigable local cockpit for guard, report, model drift, audit, and history. | `pcl ui --runs runs --policy examples/guard.policy.yaml` | Local dashboard tabs |
| Any paper-diagnostic run | The research evidence bundle has not been opened first. | `pcl research-quickstart --out runs/research-demo --open-report` | `research_bundle.html` |

Generate the ecosystem scorecard and market-readiness summary:

```bash
pcl start --choice ecosystem --out runs/ecosystem-demo
```

Import one external run:

```bash
pcl start --choice import --tool auto --input results.json --out runs/from-external
```

Audit paired external evidence:

```bash
pcl evidence-audit \
  --tool promptfoo \
  --baseline-input baseline.json \
  --candidate-input candidate.json \
  --baseline-prompt-id baseline \
  --candidate-prompt-id candidate \
  --out runs/from-promptfoo-audit
```

Bridge prompt-optimizer assets into a scored protocol:

```bash
pcl import prompt-optimizer --input favorites.json --out runs/from-prompt-optimizer
pcl scaffold-check --run runs/from-prompt-optimizer
```

## The Practical Rule

Use the adjacent tool for creation, tracing, or broad evaluation. Use PCL when someone asks:

- Is this a clean prompt-only comparison?
- Did the model, split, metric, or prompt identity change?
- Is the improvement reliable under paired uncertainty?
- What is the strongest claim this evidence can safely support?
- Which paper-derived diagnostics are still missing?

Do **not** start with PCL if you only need a nicer prompt editor, a hosted tracing dashboard, or a
large red-team attack catalog. That is the adjacent tool's job. PCL's job is to make the evidence
clean enough to trust.

Sources for positioning: [Promptfoo intro](https://www.promptfoo.dev/docs/intro/),
[Promptfoo CI/CD](https://www.promptfoo.dev/docs/integrations/ci-cd/),
[DeepEval introduction](https://deepeval.com/docs/introduction),
[LangSmith observability](https://www.langchain.com/langsmith/observability),
[Langfuse docs](https://langfuse.com/docs),
[Langfuse prompt management](https://langfuse.com/docs/prompt-management/overview), and
[linshenkx/prompt-optimizer README](https://github.com/linshenkx/prompt-optimizer).
