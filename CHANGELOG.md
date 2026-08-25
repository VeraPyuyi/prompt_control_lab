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

Both required acceptance runs are complete. Publication remains blocked until the repository owner
reviews the candidate, rotates the live-session credential, merges PR #3, and approves the Public
visibility change and GitHub Pre-release.
