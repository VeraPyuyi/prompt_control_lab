# Comparison With Promptfoo, LangSmith, and Langfuse

This page explains where `prompt_control_lab` should compete and where it should integrate.
The short version: PCL should not try to become another broad LLMOps platform. Its strongest lane is
the research evidence layer for prompt optimization.

## Positioning

| Tool | Strong lane | PCL should not copy | PCL can add |
|---|---|---|---|
| Promptfoo | LLM evals, red-team/security testing, guardrails, provider coverage, CI, and security reports. | Red-team plugin breadth, provider matrix depth, enterprise security dashboard. | Paired uncertainty, prompt-only validity, evidence cards, claim checks, paper-diagnostic gap closure, and tamper-evident research bundles after importing Promptfoo results. |
| LangSmith | Agent tracing, offline/online evals, Prompt Hub/Playground, monitoring, deployment, sandboxes, annotation workflows. | LangChain/LangGraph-native trace UI, deployment infrastructure, sandbox runtime, annotation queue product. | Convert experiment exports into prompt-optimization evidence bundles that separate prompt effects from model, metric, split, and statistical confounds. |
| Langfuse | Open-source observability, prompt management, evaluation, cost tracking, SDK/OpenTelemetry/LiteLLM integrations, self-hosting. | General tracing, prompt registry, cost dashboards, RBAC, hosted observability. | Add diagnostics observability tools usually do not provide: soft-hard deployment gap, hidden-state trajectory probes, Riccati surrogates, time-varying control evidence, and claim support boundaries. |

Sources for current product positioning and pricing:
[Promptfoo intro](https://www.promptfoo.dev/docs/intro/),
[Promptfoo CI/CD docs](https://www.promptfoo.dev/docs/integrations/ci-cd/),
[Promptfoo pricing](https://www.promptfoo.dev/pricing),
[LangSmith observability](https://www.langchain.com/langsmith/observability),
[LangSmith pricing](https://www.langchain.com/pricing),
[Langfuse docs](https://langfuse.com/docs), and
[Langfuse pricing](https://langfuse.com/pricing).

## The Winning Wedge

PCL should be the tool you run after an eval or observability system produces evidence:

```bash
pcl evidence-audit \
  --tool promptfoo \
  --baseline-input results.json \
  --candidate-input results.json \
  --baseline-prompt-id baseline \
  --candidate-prompt-id candidate \
  --provider openai:gpt-4o-mini-20260601 \
  --split-hash eval-split-2026-06 \
  --out runs/from-promptfoo-audit
```

That one command imports the external exports, creates paired statistics, checks whether the
comparison is prompt-only, writes an evidence card, checks the supported claim scope, reports
which paper-derived diagnostics are missing, and verifies the browser-first research bundle hashes.

For a single external run, use the readable import facade:

```bash
pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate
pcl import langfuse --input langfuse-export.json --out runs/from-langfuse --name candidate
pcl import langsmith --input langsmith-runs.csv --out runs/from-langsmith --experiment candidate
```

`pcl ingest ...` remains a backward-compatible alias for existing scripts.

## How PCL Can Beat Adjacent Tools Without Rebuilding Them

1. **Be stricter about evidence provenance.** External tools can produce useful scores and traces;
   PCL should preserve the exact source files, source hashes, resolved paths, import filters, and
   generated bundle hashes.
2. **Make prompt-only validity visible.** A comparison should say whether model, provider, metric,
   split, prompt identity, or source files changed. If they changed, PCL should label the result as
   confounded rather than merely showing a better score.
3. **Turn paper diagnostics into a checklist.** `gap-status` and `evidence-audit` should show which
   diagnostics are present or missing: soft-hard gap, hidden-state trajectory, Riccati surrogate,
   and time-varying control evidence.
4. **Bound claims automatically.** `claim-check` should keep users from claiming a full research
   result when the artifact only supports a paired comparison or an incomplete external import.
5. **Stay local and composable.** The best adoption path is not a hosted platform; it is a local
   Python tool that can sit after Promptfoo, Langfuse, LangSmith, DeepEval, notebooks, or custom
   eval scripts.

## What Users Should Learn

PCL should answer questions that broad eval/observability tools usually leave implicit:

- Is the baseline/candidate comparison paired by the same examples?
- Did the model, provider, metric, split, or prompt identity change?
- Which exact external export files, hashes, and import filters produced the evidence?
- Is the candidate improvement reliable under paired uncertainty?
- What is the strongest prompt-optimization claim this evidence can support?
- Which paper-derived diagnostics are missing before claiming a full research result?
- Did the shared research evidence bundle change after it was created?

## Product Implications

1. Keep `research-demo`, `diagnose`, `evidence-audit`, `claim-check`, `gap-status`, and
   `research-bundle --verify` as first-class entry points.
2. Treat `guard`, `audit-diff`, and PR tooling as an applied engineering layer, not the main
   identity of the project.
3. Improve importers for real Promptfoo, LangSmith, and Langfuse exports instead of rebuilding
   their platforms.
4. Make reviewer-facing HTML artifacts the primary user experience:
   `evidence_audit_result.html`, `bridge_summary.html`, `research_bundle.html`,
   `evidence_card.html`, `claim_check.html`, `research_gap_status.html`, and
   `research_bundle_verification.html`.
5. Use plain explanations for hard research terms: deployment gap, internal trajectory stability,
   surrogate stability, time-varying evidence, and claim boundary.

## Boundary

This comparison is not a claim that PCL is broader or more mature than these tools. It is narrower
by design. The goal is to become the most useful open-source evidence layer for prompt optimization
research and reproducibility.
