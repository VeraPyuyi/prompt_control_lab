# Users

## Non-Specialist Reviewers

Use Quick Mode when you want a clear report without tuning every command. `pcl analyze` turns
task data and two prediction files into split hygiene, metrics, statistics, explanation, and
Markdown/HTML reports.

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

## Expert Users

Use Expert Mode when you need fine control over each step. The individual commands let you choose
split settings, metrics, sampling counts, diagnostics, and policy gates separately.

## Expert Decision Guide

- If the bootstrap confidence interval crosses zero, treat the observed change as uncertain even
  when the average score improved.
- If the adjusted p-value is high, the run may still pass a gate when the policy only requires
  "no large regression". That means "acceptable under this policy", not "statistically proven".
- If `p-value = 1.0` and the gate passes, inspect the gate policy. It usually means the policy is
  permissive or focused on minimum score/regression thresholds.
- If slice-level scores regress while the average improves, inspect those slices before keeping
  the prompt.
- Riccati, trajectory, and soft-hard diagnostics are fitted probes and deployment-risk signals;
  they are not proofs about the full language model.
