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
diagnostics/prompt_reachability.json
diagnostics/readout_alignment.json
diagnostics/prompt_routing.json
diagnostics/prompt_projection.json
diagnostics/prompt_stability.json
```

The five prompt diagnostic files answer different questions:

| Diagnostic | What it observes | Decision boundary |
|---|---|---|
| Prompt reachability | Representation shift relative to the initial checkpoint | A large shift can request review; it does not prove that the prompt caused the score change. |
| Readout alignment | Gap between the hidden representation and answer/readout evidence | A large gap can hold a checkpoint when the capability is available. |
| Prompt routing | Evidence that different prompt/control routes were actually compared | Without an intervention it is `insufficient_evidence`, not a failed model. |
| Prompt projection | Soft-to-hard deployment gap | Ordinary LoRA checkpoints mark this `not_applicable`. |
| Prompt stability | Drift or repeated-run variation | Increased drift can hold a candidate under the configured policy. |

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

The repository also includes a guarded SFT pilot protocol. First prepare deterministic inputs from a pinned GSM8K revision plus the generated format fixture:

```bash
pcl posttrain-pilot-prepare \
  --out /root/prompt_control_lab_runtime/pilot-data
```

The preparation command writes 320 train, 80 validation, 128 withheld GSM8K rows, and 64 withheld format rows. Selection is deterministic and recorded in `dataset_provenance.json`. Offline users can pass `--gsm8k-train-jsonl` and `--gsm8k-test-jsonl` instead of downloading the pinned dataset.

The pilot defaults to plan-only execution and requires an explicit resource approval record plus an exclusive lock before GPU work can begin; this prevents an apparently idle GPU from overriding an active server queue.

Hash the pinned model snapshot into the isolated runtime without writing into a shared model cache:

```bash
pcl posttrain-model-provenance \
  --model /root/prompt_control_lab_runtime/models/Qwen2.5-0.5B-Instruct \
  --model-id Qwen/Qwen2.5-0.5B-Instruct --revision PINNED_40_OR_64_HEX_COMMIT \
  --out /root/prompt_control_lab_runtime/provenance/qwen-0.5b.json
```

```bash
pcl posttrain-pilot \
  --runtime-root /root/prompt_control_lab_runtime \
  --model /root/prompt_control_lab_runtime/models/Qwen2.5-0.5B-Instruct \
  --model-provenance /root/prompt_control_lab_runtime/provenance/qwen-0.5b.json \
  --train /root/prompt_control_lab_runtime/pilot-data/train.jsonl \
  --validation /root/prompt_control_lab_runtime/pilot-data/validation.jsonl \
  --withheld /root/prompt_control_lab_runtime/pilot-data/withheld.jsonl \
  --format-fixture /root/prompt_control_lab_runtime/pilot-data/format_fixture.jsonl \
  --out /root/prompt_control_lab_runtime/runs/sft-pilot
```

This command only writes `pilot_protocol.json`. Before writing the plan, it rejects overlap among
train, validation, withheld, and format-fixture data by both row ID and normalized prompt/answer content. Starting
training additionally requires `--execute --approval <expiring-resource-approval.json> --gpu
<index>`; the script then rechecks GPU processes and takes an exclusive `flock`.
For `--execute`, the model, provenance, split files, approval record, lock, and output must all
resolve inside `--runtime-root`; validation happens before any lock or output file is created.
The approval must point to a real, non-symlink JSON `queue_source` inside the same runtime. Inside
the execution lock, PromptControlLab rereads that file, verifies its exact SHA-256, requires its
`checked_at` to match the approval and be at most 90 seconds old, and confirms zero pending and
running jobs. An approval cannot substitute for a fresh queue snapshot.

The pilot's `trajectory` value is adjacent prompt-token drift in the final hidden layer. Its
generation-mismatch value applies the same task-specific scorer to teacher-forced and
free-generation answers: final-number extraction for GSM8K and strict, case-sensitive string
equality for format fixtures. Outputs that consume the full generation budget without EOS are
counted as saturated; the default policy treats any saturation as insufficient scoring evidence
rather than silently converting a decode-budget limit into checkpoint failure.

The controlled protocol fixes seeds `0,1,2` and checkpoints `initial/mid/final`. A completed run creates nine checkpoint directories, six initial-to-mid/final gates, a conservative cross-seed `pilot_summary.json/html`, and `decision_trace.json`. Until those artifacts exist, a resource-preflight record is readiness evidence only and must not be presented as checkpoint performance.
