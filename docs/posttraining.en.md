# Post-training checkpoint diagnosis

`pcl posttrain-gate` compares a baseline and candidate checkpoint through performance, provenance, stability, deployment boundary, generation mismatch, and selective-risk evidence.

```bash
pcl posttrain-gate \
  --baseline runs/checkpoint-000 \
  --candidate runs/checkpoint-500 \
  --policy examples/posttrain.policy.yaml \
  --out runs/posttrain-gate
```

## What each checkpoint directory needs

```text
manifest.json
metrics.json
stats.json
diagnostics/trajectory.json
diagnostics/soft_hard.json
diagnostics/generation_mismatch.json
diagnostics/selective_risk.json
```

The candidate `stats.json` stores the paired bootstrap interval and permutation p-value for the
matched baseline/candidate examples. Both `metrics.json` files record `n`, `sample_hash`, mean
generated tokens, and latency. The paired record binds both checkpoint IDs, both split hashes,
both sample hashes, `n_pairs`, and `mean_delta`; the gate rejects inconsistent or reversed
statistics instead of treating them as evidence.

For SFT, DPO, PPO, or GRPO checkpoints that do not deploy a learned soft prompt, record that boundary explicitly:

```json
{
  "applicability": "not_applicable",
  "reason": "This checkpoint does not deploy a learned soft prompt."
}
```

This is more accurate than inventing a low projection risk.

## Decisions

- `pass`: all required evidence is present and satisfies the policy.
- `needs_review`: evidence is complete, but a review-level slice or uncertainty check needs attention.
- `hold`: a fail-level score, provenance, stability, projection, or generation check is outside policy.
- `insufficient_evidence`: a required artifact is missing, so the gate refuses to guess.

The output includes `posttrain_gate.json`, `checkpoint_comparison.json`, `mechanism_attribution.json`, and `report.md/html`.

## What it can and cannot do

The gate can help select checkpoints and explain whether a score change co-occurs with trajectory drift, generation mismatch, selective-risk behavior, or a deployment gap. It can support SFT, DPO, PPO, and GRPO workflows without replacing those algorithms. A matched checkpoint comparison is stronger than an unrelated Base/Instruct comparison, but it still does not prove a hidden causal mechanism without a controlled intervention.

The repository also includes a guarded SFT pilot protocol. It defaults to plan-only execution and requires an explicit resource approval record plus an exclusive lock before GPU work can begin; this prevents an apparently idle GPU from overriding an active server queue.

```bash
pcl posttrain-pilot \
  --model /local/cache/Qwen2.5-0.5B \
  --train pilot/train.jsonl --validation pilot/validation.jsonl \
  --withheld pilot/withheld.jsonl --format-fixture pilot/format.jsonl \
  --out runs/sft-pilot
```

This command only writes `pilot_protocol.json`. Before writing the plan, it rejects overlap among
train, validation, withheld, and format-fixture data by both row ID and normalized prompt/answer content. Starting
training additionally requires `--execute --approval <expiring-resource-approval.json> --gpu
<index>`; the script then rechecks GPU processes and takes an exclusive `flock`.

The pilot's `trajectory` value is adjacent prompt-token drift in the final hidden layer. Its
generation-mismatch value compares teacher-forced and free-generation answers with the same
canonical text exact-match rule, so the gap is not caused by different scoring conventions.
