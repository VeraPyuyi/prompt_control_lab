# v0.2.0-alpha.1 release candidate notes

PromptControlLab `0.2.0a1` connects prompt and agent preflight with model provenance, reproducible evaluation, checkpoint diagnosis, diff audit, and local lifecycle evidence.

The alpha candidate adds:

- a provider-neutral local control protocol;
- a native, version-locked DeepSeek Harness integration;
- portable `prompt-reach-v2` evidence scanning and reconciliation;
- prompt reachability, readout alignment, routing, projection, and stability adapters;
- capability-aware SFT/DPO/GRPO checkpoint gates;
- a guarded three-seed SFT pilot protocol; and
- a local dashboard organized around observation, explanation, claim boundary, and next action.

The public pre-release must not be created until two real acceptance runs are complete: the controlled three-seed checkpoint pilot and a DeepSeek Harness session that captures a real model request, tool use, a bounded file edit, and a test result. Diagnostic associations remain evidence for review, not strict causal or safety proofs.
