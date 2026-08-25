# Controlled SFT checkpoint pilot

- Conservative decision: `hold`
- Seeds: `[0, 1, 2]`
- Checkpoint runs: `9`
- Gates: `6`

| Seed | Stage | Score | GSM8K | Format | Mean tokens | Saturation |
|---:|---|---:|---:|---:|---:|---:|
| 0 | initial | 0.0885417 | 0.132812 | 0 | 147.339 | 0.927083 |
| 0 | mid | 0.177083 | 0.265625 | 0 | 106.521 | 0.4375 |
| 0 | final | 0.1875 | 0.28125 | 0 | 106.547 | 0.411458 |
| 1 | initial | 0.0885417 | 0.132812 | 0 | 147.339 | 0.927083 |
| 1 | mid | 0.15625 | 0.234375 | 0 | 105.536 | 0.411458 |
| 1 | final | 0.1875 | 0.28125 | 0 | 108.911 | 0.463542 |
| 2 | initial | 0.0885417 | 0.132812 | 0 | 147.339 | 0.927083 |
| 2 | mid | 0.203125 | 0.304688 | 0 | 106.953 | 0.416667 |
| 2 | final | 0.208333 | 0.3125 | 0 | 106.547 | 0.421875 |

## Gate decisions

| Seed | Stage | Decision | Score delta | Triggered checks |
|---:|---|---|---:|---|
| 0 | mid | hold | 0.0885417 | evidence_validity, trajectory_stability, generation_mismatch, selective_risk, prompt_reachability, readout_alignment, prompt_routing, prompt_stability |
| 0 | final | hold | 0.0989583 | evidence_validity, trajectory_stability, generation_mismatch, selective_risk, prompt_reachability, readout_alignment, prompt_routing, prompt_stability |
| 1 | mid | hold | 0.0677083 | evidence_validity, trajectory_stability, generation_mismatch, selective_risk, prompt_reachability, readout_alignment, prompt_routing, prompt_stability |
| 1 | final | hold | 0.0989583 | evidence_validity, trajectory_stability, generation_mismatch, selective_risk, prompt_reachability, readout_alignment, prompt_routing, prompt_stability |
| 2 | mid | hold | 0.114583 | evidence_validity, trajectory_stability, generation_mismatch, selective_risk, prompt_reachability, readout_alignment, prompt_routing, prompt_stability |
| 2 | final | hold | 0.119792 | evidence_validity, trajectory_stability, generation_mismatch, selective_risk, prompt_reachability, readout_alignment, prompt_routing, prompt_stability |

## Claim boundary

This summary conservatively aggregates observed checkpoint evidence across seeds. It does not establish a causal training mechanism.

This export contains aggregate evidence only. It excludes raw prompts, per-example predictions, dataset records, weights, adapters, trainer state, and absolute paths.
