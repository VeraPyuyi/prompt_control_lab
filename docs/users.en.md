# Users

## Prompt Researchers

Use PromptControlLab to enforce train/validation/withheld separation, save split hashes, keep
per-example outputs, and produce reproducible statistical reports.

## LLM Engineering Teams

Treat a prompt change as a local regression test. Import outputs from the old and new prompts,
compare aggregate and slice-level scores, and inspect whether the change is reliable.

## Soft Prompt Researchers

Check how far learned soft vectors are from real token embeddings. This helps explain whether a
soft prompt can be safely projected into a hard prompt.

## Model Migration and Evaluation Teams

Save artifacts for different models or prompt versions, then compare migration regressions,
slice-level changes, and reports.

## Trajectory and Control Researchers

Import hidden-state trajectories and inspect drift, log-decay slope, turnpike-like signals, and
Riccati surrogate stability. These are diagnostics, not proofs about a full language model.

