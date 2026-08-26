# Control Certificate Diagnostics

[中文](control_certificates.zh.md)

PromptControlLab exposes three bounded checks derived from control-theoretic sensitivity and local-existence arguments. They diagnose a named artifact or finite-dimensional surrogate. They do not certify an operational language model, global optimality, hidden reasoning, or safe deployment.

Install the research dependencies for the matrix-based commands:

```bash
python -m pip install -e ".[research]"
```

## 1. Terminal Sensitivity

Use recorded terminal-objective or readout interventions:

```bash
pcl terminal-sensitivity \
  --records examples/terminal_interventions.jsonl \
  --out runs/certificates/terminal
```

For each record, the command computes

```text
sensitivity = control_delta_norm / perturbation_norm
log(sensitivity) = intercept - decay_rate * (horizon - early_step)
```

The result reports the fitted decay rate, R-squared, bootstrap interval, per-intervention fits, and values clipped at the numerical floor. A positive fitted trend is `empirical_only`; it is not a horizon-uniform Green estimate.

For a reproducible low-dimensional boundary-value example, run `pcl research-demo --out runs/research-demo`. The generated `inputs/terminal_surrogate.npz` contains `M`, `B0`, `BN`, `terminal_perturbations`, and `control_readout` and can be passed with repeated `--horizon` and `--early-step` options.

## 2. Green Certificate

```bash
pcl green-certificate \
  --surrogate runs/research-demo/inputs/green_surrogate.npz \
  --horizon 16 --horizon 32 --horizon 64 \
  --premises examples/green_premises.json \
  --out runs/certificates/green
```

The command checks the stable/unstable Schur splitting, distance from the unit circle, scaled boundary minimum singular value, inverse norm, condition number, and deterministic coefficient-recovery residual. A `graph_S` array enables a separate terminal-only graph-boundary check. Ordinary mixed boundaries never produce a one-sided terminal-decay claim.

Floating-point checks with estimated premises are at most `surrogate_consistent`. `certificate_verified` is reserved for the fixed-dimensional surrogate and horizon family named by a complete conservative premise record. It is not a certificate for the full Transformer.

## 3. Posterior Certificate

```bash
pcl posterior-certificate \
  --input examples/posterior_bounds.json \
  --out runs/certificates/posterior
```

Given residual bound `epsilon`, inverse-Jacobian bound `beta`, local Jacobian Lipschitz bound `L`, and justified radius `R`, the command evaluates

```text
eta = beta * epsilon
K = beta * L
h = eta * K
```

It checks `h <= 1/2` and whether the resulting local existence radius fits inside `R`. With `L = 0`, it uses the linear radius `eta`. Estimated constants are at most `surrogate_consistent`; complete conservative bound provenance is required for `certificate_verified`.

## Levels And States

| Field | Values | Meaning |
|---|---|---|
| `certificate_level` | `certificate_verified`, `surrogate_consistent`, `empirical_only`, `not_applicable`, `insufficient_evidence` | Strength and applicability of the recorded evidence. |
| `check_state` | `passed`, `conditions_not_met`, `missing`, `invalid` | Outcome of the named check. |

`conditions_not_met` means only that the supplied certificate conditions were not all satisfied. It does not prove that a solution does not exist.

## Diagnose, UI, And Checkpoint Gate

Place the artifacts under `<run>/diagnostics/` and run:

```bash
pcl diagnose --run runs/research-demo
pcl ui --runs runs
```

The UI presents each result as: observation, explanation, claim boundary, and next action. `pcl posttrain-gate` discovers the same three files in candidate checkpoint diagnostics. Existing workflows remain compatible when they are absent. To require them, add policy keys such as:

```yaml
require_terminal_sensitivity: true
require_green_certificate: true
require_posterior_certificate: true
minimum_control_certificate_level: surrogate_consistent
```

The global minimum is interpreted against each diagnostic's natural ceiling. Terminal sensitivity
remains `empirical_only`, so the example above requires its valid empirical artifact while requiring
at least `surrogate_consistent` Green and posterior artifacts. The gate records these effective
per-diagnostic minima in `certificate_summary.effective_minimum_levels`.

An explicitly provided result with `conditions_not_met` can hold a checkpoint. Missing required evidence yields `insufficient_evidence`. A passing certificate never overrides a score, slice, provenance, or other gate failure.
