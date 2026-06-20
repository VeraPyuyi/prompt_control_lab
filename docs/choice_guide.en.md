# Which Tool Should I Use First?

`prompt_control_lab` is not trying to replace Promptfoo, LangSmith, Langfuse, DeepEval, or
prompt-optimizer. Use those tools for their strongest workflow, then use PCL when you need a
reviewer-facing evidence layer for prompt optimization.

## 30-Second Map

| Your starting point | Use first | Add PCL when you need |
|---|---|---|
| You need eval matrices, CI checks, or red-team/security tests. | Promptfoo | Paired uncertainty, prompt-only validity, claim boundaries, and paper diagnostics. |
| You need traces, agent debugging, datasets, or LangChain/LangGraph observability. | LangSmith | A reproducible evidence bundle that separates prompt effects from model, metric, and split changes. |
| You need open-source tracing, prompt management, evals, cost, or self-hosting. | Langfuse | Soft-hard gap, trajectory/Riccati/tv-soft diagnostics, and bounded research claims. |
| You want a polished prompt writing app. | prompt-optimizer | Proof that the optimized prompt is reproducibly better before deployment or publication. |
| You already have baseline/candidate outputs. | PCL | Evidence card, claim check, gap status, provenance, and research bundle verification. |

## Copy-Paste Paths

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

Sources for positioning: [Promptfoo intro](https://www.promptfoo.dev/docs/intro/),
[Promptfoo CI/CD](https://www.promptfoo.dev/docs/integrations/ci-cd/),
[LangSmith observability](https://www.langchain.com/langsmith/observability),
[Langfuse docs](https://langfuse.com/docs),
[Langfuse prompt management](https://langfuse.com/docs/prompt-management/overview), and
[linshenkx/prompt-optimizer README](https://github.com/linshenkx/prompt-optimizer).
