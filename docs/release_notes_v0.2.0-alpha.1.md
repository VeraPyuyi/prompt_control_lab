# v0.2.0-alpha.1 release candidate notes

PromptControlLab `0.2.0a1` connects prompt and agent preflight with model provenance, reproducible evaluation, checkpoint diagnosis, diff audit, and local lifecycle evidence.

The alpha candidate adds:

- a provider-neutral local control protocol;
- a native, version-locked DeepSeek Harness integration;
- portable `prompt-reach-v2` evidence scanning and reconciliation;
- prompt reachability, readout alignment, routing, projection, and stability adapters;
- capability-aware SFT/DPO/GRPO checkpoint gates;
- a completed, guarded three-seed SFT checkpoint case;
- one bounded, real DeepSeek Harness lifecycle case; and
- a local dashboard organized around observation, explanation, claim boundary, and next action.

The checkpoint case contains 9 checkpoint runs and 6 paired gates. Its aggregate score improved on
the fixed protocol, but the configured stability and generation-mismatch checks produced the
conservative decision `hold`. The Harness case contains four matched model request/response pairs,
two file reads, one bounded edit, and one test process with exit code `0`; the final control decision
remains `suggest`.

These two acceptance runs establish that the bounded workflows executed and produced auditable,
public-safe artifacts. Diagnostic associations remain evidence for review, not strict causal,
universal-performance, hidden-weight-identity, or safety proofs. This candidate remains unpublished
until the repository owner completes the final inspection in
[`release_checklist_v0.2.0-alpha.1.md`](release_checklist_v0.2.0-alpha.1.md).
