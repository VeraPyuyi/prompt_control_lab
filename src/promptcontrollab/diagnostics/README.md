# Diagnostics

## Purpose

`promptcontrollab.diagnostics` analyzes mechanisms and stability signals behind prompt, checkpoint, and agent behavior. It includes trajectory, soft-to-hard, Riccati, time-varying control, terminal sensitivity, Green-boundary, and posterior-certificate diagnostics.

## Use cases

- Measure hidden-state drift, tail behavior, and turnpike-like decay.
- Quantify soft-to-hard projection gaps and time-varying control effects.
- Fit a low-dimensional Riccati/DARE surrogate and inspect local stability.
- Separate empirical terminal sensitivity, surrogate consistency, and premise-backed local certificates.

## CLI commands

```bash
pcl diagnose --run runs/research
pcl research-demo --out runs/research-demo
pcl soft-hard --soft soft.npz --vocab vocab.npz --out runs/soft-hard
pcl trajectory --states states.npz --out runs/trajectory
pcl riccati --matrices matrices.npz --trajectory states.npz --out runs/riccati
pcl tv-soft --predictions scored_predictions.jsonl --out runs/tv-soft
pcl terminal-sensitivity --records terminal_interventions.jsonl --out runs/certificates
pcl green-certificate --surrogate green_surrogate.npz --horizon 16 --horizon 32 --horizon 64 --premises green_premises.json --out runs/certificates
pcl posterior-certificate --input posterior_bounds.json --out runs/certificates
```

## Python API

The approved canonical package exposes focused analyzers:

```python
from promptcontrollab.diagnostics import (
    analyze_green_certificate,
    analyze_posterior_certificate,
    analyze_terminal_sensitivity,
    analyze_trajectory,
)
```

Additional APIs include `analyze_soft_hard`, `analyze_riccati`, `summarize_tv_soft`, `run_research_diagnostics`, and research-bundle renderers.

## Inputs/Artifacts

- Inputs: hidden states, transition samples, soft controls, vocabulary embeddings, intervention JSONL, bounded NPZ surrogates, and premise/bound JSON.
- Outputs: diagnostic JSON, CSV, SVG/HTML summaries, research bundle indexes, and certificate artifacts.
- Certificate results carry both `certificate_level` and `check_state` so evidence strength and condition status remain distinct.

## Dependencies

Most numerical diagnostics require the `research` extra (`numpy` and `scipy`). Scalar posterior checks remain available without the scientific stack. The module consumes evidence but does not execute model training.

## Extension points

- Add analyzers that return observation, explanation, confidence, scope, claim boundary, and next action.
- Add safe artifact readers for bounded numeric formats.
- Add renderers without changing the diagnostic JSON source of truth.

## Limitations

- Observed trajectories and fitted surrogates do not prove a mechanism in a full language model.
- `surrogate_consistent` is weaker than `certificate_verified` and is scoped to the named finite-dimensional system.
- A condition not being met does not prove that a solution or useful behavior does not exist.

## Tests/Examples

Use `pcl research-demo`, the control-certificate guide, and synthetic numeric fixtures. Run:

```bash
python -m pytest tests -k "trajectory or soft_hard or riccati or tv_soft or certificate or research"
```
