# Changelog

## 0.2.0a1 - Unreleased release candidate

- Added shadow-mode OpenTelemetry GenAI and OpenInference trace import with deterministic event normalization, deduplication, ordering, and default redaction.
- Added unified Change Review for prompt, model, Agent, and checkpoint changes, including comparison validity, attribution, stability, human feedback, and decision trace artifacts.
- Added a React/FastAPI workflow cockpit while preserving the Streamlit dashboard through `pcl ui --legacy-streamlit`.
- Reframed the three control-certificate diagnostics in bilingual, function-first language under Stability & Confidence while preserving stable artifact IDs and technical details.
- Added a 10-task, 3-trial paired Agent Change Review case from 60 real Codex executions; both sides completed 30/30 while the guarded side used fewer full-run tokens and tool calls on the controlled fixture set.
- Added three bilingual flagship Change Review cards for Agent workflow, historical model, and checkpoint changes, including nested review discovery and URL-persistent selection.
- Added a public-safe Qwen2.5-7B versus Mistral-7B historical aggregate review with task-slice heterogeneity, a conservative `needs_review` decision, and an explicitly unexecuted paired-model pilot protocol.
- Reorganized the Python package into documented `core`, `preflight`, `evaluation`, `control`,
  `provenance`, `audit`, `evidence`, `diagnostics`, `integrations`, and `cli` domains while
  preserving established imports, commands, protocols, and artifact schemas.
- Added the versioned local ControlRun and ControlEvent loop with provider-neutral adapters.
- Added the native DeepSeek Harness Cordis integration and persistent local bridge contracts.
- Added `prompt-reach-v2`, portable evidence reconciliation, and five prompt diagnostic adapters.
- Added capability-aware post-training checkpoint gates and conservative cross-seed aggregation.
- Added deterministic preparation and guarded execution for a three-seed Qwen2.5-0.5B-Instruct SFT pilot.
- Added the local UI views for mechanism, stability, training gate, evidence scope, decision, and history.
- Recorded the completed three-seed SFT pilot as a public-safe checkpoint case with 9 checkpoint
  runs, 6 paired gates, and a conservative `hold` decision.
- Recorded one bounded, real DeepSeek Harness lifecycle with model requests, tool activity, one
  bounded file edit, and a test process with exit code `0`.
- Added public contribution, private vulnerability reporting, issue, pull request, and release
  inspection guidance.
- Added a Docker Hugging Face Space bundle with session isolation, bounded JSON/JSONL imports,
  curated public-safe artifacts, bilingual documentation, and manual/release deployment automation.

Both required acceptance runs are complete and the GitHub source is public. GitHub Pre-release,
PyPI, and Hugging Face Space publication remain separate maintainer-controlled release steps.
