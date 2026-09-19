# Evaluate, optimize, explain

PromptControlLab 0.3 runs locally. Its wheel contains the React app and examples; using it does not require Node. Install the wheel with `[ui,optimize,research]` extras, then run:

```bash
pcl ui --runs runs --language en
```

## A first comparison in five minutes

1. Open **Experiments** and choose **Try the offline example**. Its outputs are preset synthetic teaching data, with no model calls.
2. Read the four separate answers: comparison conditions, effect, matched items and mean change. A completed run is not proof of an improvement.
3. Inspect the individual outputs. Download the readable report, CSV or portable bundle.
4. For your own task, edit both prompts and upload CSV, JSONL or JSON. Map the ID, input and expected-answer fields. IDs must be unique; related items can share `meta.group_id`.
5. Choose **Run evaluation**, **Import results**, or **Find a better prompt**. Live calls require an explicit provider and model ID. Credentials can come from an environment variable or the current local service's memory.

The five-minute target is an onboarding design target. Measured first-user completion remains a separate [human trial](releases/usability-trial.md).

## Live evaluation and imports

The seven existing providers remain available: OpenAI, Anthropic, Gemini, DeepSeek, Qwen, Kimi and OpenAI-compatible endpoints. Remote endpoints require HTTPS; loopback endpoints can use HTTP. Anthropic-compatible relays may explicitly select Bearer authentication. Provider contract tests and actual model-call validation are recorded separately in the release acceptance record.

Deterministic scorers support exact answers, containment, classification, numeric tolerance and format checks. Format error uses lower-is-better ordering. Missing outputs and service errors are excluded from quality scores; observed wrong or unparseable output is a model-quality result. Per-item records retain latency, tokens and failure details when available.

Native PCL JSON/CSV and existing Promptfoo, DeepEval, Langfuse, LangSmith and prompt-optimizer importers are supported. Select the relevant prompt/arm when an export contains several versions. Prompt assets load into the editor for evaluation. Explicit `aggregate_metrics` objects remain descriptive; they do not acquire paired statistics. CSV is spreadsheet-safe; `records.json` preserves exact text for lossless reuse.

## Bounded GEPA search

Install `gepa==0.1.4` through the `optimize` extra. The default is at most five rounds, one proposal per round, with two validation rounds without improvement stopping the search. The reflection model uses the selected evaluation model unless explicitly changed. The UI gives reflection 512 output tokens per call.

Training records generate suggestions. Validation records select candidates. The engine locks the final candidate before it reads and evaluates the withheld partition. Shared inputs and group identifiers stay in one split component. GEPA's internal evaluation cache is disabled; PCL caches by phase, item and configuration to avoid train/validation ID collisions.

Task and reflection calls share call, output-token and time budgets. Final comparison headroom is reserved. Amount limits require input/output prices, in one currency; when different models have different rates, configure conservative shared rates. Missing usage and unknown charges remain explicit. A budget or time stop may leave the final comparison incomplete, which is reported as such.

Search stores candidate text, lineage, validation scores, costs and stop reasons. It never silently overwrites your original prompt. An optimized prompt has at most one `{input}` placeholder; otherwise the input is appended. Candidate text is bounded to 100,000 characters.

## Persistence, cancellation and retry

One experiment runs at a time per runs directory, with no more than two model requests in flight. Cancellation stops new admission and keeps finished items. A request already sent may finish before cancellation becomes visible. If the process exits before its outcome is known, the call remains uncertain and its budget reservation remains charged.

Resume reuses completed calls and continues unfinished work. **Retry safely rejected requests** is explicit: only known pre-execution rejections or known local configuration errors qualify. Timeouts, interrupted calls and malformed responses are not automatically replayed. Memory-only credentials must be supplied again after service restart; keep the recorded environment-variable reference when restoring them.

```bash
pcl experiment import --example --runs runs
pcl experiment run --config my-experiment.json --runs runs
pcl experiment optimize --config my-search.json --runs runs
pcl experiment status --runs runs
pcl experiment cancel EXPERIMENT_ID --runs runs
pcl experiment resume EXPERIMENT_ID --runs runs --retry-failed
pcl experiment replay --bundle experiment.zip --out replayed
```

Configuration and dataset paths in CLI JSON resolve relative to that configuration file. Export bundles use relative paths. Replay makes no model calls and separately checks file integrity, numerical results and the scope of evidence. Identity hashes establish matching content, not chronology or independence.

## Research and earlier workflows

**Research tools** provides five offline tools with examples and bilingual HTML, JSON, CSV and SVG. Saved internal tensors are needed only for response diagnostics. Closed-model API users can complete ordinary evaluation and cost analysis without them. See the [input examples](../examples/research-tools/README.md).

Change Review, checkpoint plots, trace import and earlier commands remain available. Quick analysis now actually scores its withheld IDs; `pcl analyze --evaluation-scope all` requests an explicit full-data comparison. Previously saved `pass` and `clean` fields retain their original meanings. New experiment judgments use `comparison-assessment/v1`.

The local API accepts typed experiment operations and rejects arbitrary commands, cross-origin writes and non-loopback access. Public demo mode remains read-only. Do not place raw API keys in configuration, prompts or datasets; the credential field and environment variables provide the intended path.
