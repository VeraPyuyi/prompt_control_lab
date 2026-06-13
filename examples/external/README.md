# External Tool Export Examples

These files are tiny Promptfoo, Langfuse, LangSmith, and DeepEval-style exports
for trying `pcl evidence-from` without setting up those tools first.

`pcl init --path demo` writes the same files under `demo/examples/external/`, so
installed users can try the bridge without cloning the repository.

They are intentionally small. The resulting `comparison_validity.json` may say
`needs_review` because four examples are not enough for strong statistical
evidence. That is expected: the demo proves the bridge and artifact shape, not a
universal prompt improvement claim.

## Promptfoo

```bash
pcl evidence-from \
  --tool promptfoo \
  --baseline-input examples/external/promptfoo_results.json \
  --candidate-input examples/external/promptfoo_results.json \
  --baseline-prompt-id baseline \
  --candidate-prompt-id candidate \
  --provider openai:gpt-4o-mini-20260601 \
  --split-hash external-demo-split \
  --out runs/from-promptfoo-evidence
```

## Langfuse

The sample uses different observation ids for baseline and candidate, but a
shared `metadata.example_id` for paired statistics.

```bash
pcl evidence-from \
  --tool langfuse \
  --baseline-input examples/external/langfuse_export.json \
  --candidate-input examples/external/langfuse_export.json \
  --baseline-name baseline \
  --candidate-name candidate \
  --score-name exact_match \
  --model gpt-4o-mini-20260601 \
  --provider openai \
  --split-hash external-demo-split \
  --out runs/from-langfuse-evidence
```

## LangSmith

The sample CSV uses different run ids for baseline and candidate, but a shared
`example_id` column for paired statistics.

```bash
pcl evidence-from \
  --tool langsmith \
  --baseline-input examples/external/langsmith_runs.csv \
  --candidate-input examples/external/langsmith_runs.csv \
  --baseline-experiment baseline \
  --candidate-experiment candidate \
  --score-name exact_match \
  --model gpt-4o-mini-20260601 \
  --provider openai \
  --split-hash external-demo-split \
  --out runs/from-langsmith-evidence
```

## DeepEval

DeepEval commonly saves local TestRun JSON artifacts. The sample keeps baseline
and candidate as two separate TestRun files, with shared `metadata.example_id`
values for paired statistics.

```bash
pcl evidence-from \
  --tool deepeval \
  --baseline-input examples/external/deepeval_baseline.json \
  --candidate-input examples/external/deepeval_candidate.json \
  --score-name exact_match \
  --model gpt-4o-mini-20260601 \
  --provider openai \
  --split-hash external-demo-split \
  --out runs/from-deepeval-evidence
```
