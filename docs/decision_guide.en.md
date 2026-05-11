# Decision Guide

This guide explains how to read the statistical and gate artifacts without overclaiming.

## If the Confidence Interval Crosses Zero

What happened:

- The candidate may be better on average, but the paired uncertainty still includes no change.

What it means:

- Treat the result as `needs_review`.
- Inspect changed examples and task slices before keeping the prompt.
- Add more withheld examples if the decision matters.

## If the p-value Is 1.0 but the Gate Passes

What happened:

- The gate policy checks configured thresholds.
- A permissive policy can pass even when statistical evidence is weak.

What it means:

- `gate_result.json` answers: did this run satisfy the configured release rule?
- `stats.json` answers: is the observed difference statistically convincing?
- If p-value is high, do not claim a reliable improvement even if the gate passes.

## If Mean Score Improves but a Slice Regresses

What happened:

- The average improved, but one task group got worse.

What it means:

- Review the regressed slice first.
- Keep the prompt only if that slice is not important or the regression is acceptable.

## If Soft-hard Risk Is High

What happened:

- The soft prompt vectors are far from nearby hard-token embeddings.

What it means:

- A soft prompt score does not guarantee hard prompt deployability.
- Use `pcl improve` or a separate hard-prompt evaluation before deployment.

## Safe Claim Language

Use:

- "The candidate passed the configured gate."
- "The candidate improved on this sample, but the confidence interval crosses zero."
- "The current evidence supports review, not deployment."

Avoid:

- "The prompt is proven better."
- "The model is stable."
- "The Riccati diagnostic proves the full language model is controlled."

