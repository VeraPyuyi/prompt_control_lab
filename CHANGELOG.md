# Changelog

## 0.2.0a1 - Unreleased release candidate

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
