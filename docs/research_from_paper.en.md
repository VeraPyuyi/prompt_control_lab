# Research From The Paper

`prompt_control_lab` is organized around the Prompt-Engineering-Optimal-Control
framing. The applied agent features are useful, but the research core is the
paper-derived diagnostic stack below.

## Concept-To-Command Map

| Paper concept | Command | Main output | Interpretation boundary |
|---|---|---|---|
| one-command research workflow | `pcl research-demo`, `pcl diagnose` | `research_diagnostics.json`, `research_diagnostics.md` | Runs synthetic fixtures or user-provided artifacts; demo outputs are not benchmark results. |
| tri-split withheld protocol | `pcl split`, `pcl analyze` | `splits.json`, `manifest.json` | Checks protocol hygiene; it does not make a small task pool representative. |
| paired statistical comparison | `pcl stats` | `stats.json` | Reports mean delta, bootstrap CI, permutation p-value, and Holm-adjusted p-value. |
| prompt-only comparison validity | `pcl validity` | `comparison_validity.json`, `comparison_validity.md` | Checks whether a baseline/candidate result is confounded by model, split, metric, or missing prompt identity. |
| prompt optimization evidence card | `pcl evidence-card` | `evidence_card.json`, `evidence_card.md` | Summarizes protocol, statistics, validity, deployment, trajectory, Riccati, and time-varying evidence in one reviewer-facing artifact. |
| soft-to-hard projection gap | `pcl soft-hard` | `diagnostics/soft_hard.json` | Measures nearest-token projection risk; it is not a proof of optimal hard prompting. |
| HuggingFace hidden-state extraction | `pcl extract-hidden` | `hidden_states.npz`, `hidden_states.npz.metadata.json` | Generates trajectory-ready hidden states from an open/local HuggingFace model. |
| hidden-state trajectory | `pcl trajectory` | `diagnostics/trajectory.json` | Reports drift, log-decay slope, fit quality, and turnpike-like signal. |
| Riccati surrogate | `pcl riccati` | `diagnostics/riccati.json` | Checks a fitted finite-dimensional surrogate, not the full language model. |
| time-varying soft-control lane | `pcl tv-soft` | `diagnostics/tv_soft.json` | Compares static, time-varying, shuffled, and random control lanes. |

## 1. One-Command Research Workflow

If you want to experience the paper-derived diagnostics before preparing your
own artifacts, start here:

```bash
pcl research-demo --out runs/research-demo
pcl diagnose --run runs/research-demo
```

This writes synthetic soft prompt vectors, vocabulary embeddings, hidden-state
trajectories, Riccati matrices, and method predictions under `runs/research-demo/inputs`.
It also writes a small synthetic `tasks.jsonl`, baseline/candidate scored runs,
`splits.json`, `stats.json`, `comparison_validity.json`, `evidence_card.json`, and
`evidence_card.md`. The demo is for learning the workflow and artifact relationships, not for
claiming benchmark performance.

## 2. Tri-Split Withheld Protocol

The paper emphasizes clean separation between optimization data, selection data,
and withheld evaluation. The toolkit makes that protocol explicit:

```bash
pcl split --data examples/tasks.jsonl --out runs/candidate --seed 0
pcl analyze --config promptcontrol.example.yaml --out runs/quick
```

Use the split hash and leakage report to verify that train, validation, and
withheld ids do not overlap. This protects the evaluation story from validation
overfitting and accidental test leakage.

## 3. Paired Statistics

Prompt changes should not be judged by one average score alone:

```bash
pcl stats \
  --baseline runs/baseline/predictions.jsonl \
  --candidate runs/candidate/predictions.jsonl \
  --out runs/candidate/stats.json
```

The output records paired mean delta, bootstrap confidence interval, permutation
p-value, and Holm-adjusted p-value. If the interval crosses zero, the evidence is
weaker even when the candidate mean is higher.

## 4. Prompt-Only Comparison Validity

A higher candidate score is not enough if the model, data split, metric, or
prompt identity changed at the same time. The validity command turns that
question into a small auditable artifact:

```bash
pcl validity \
  --baseline runs/baseline \
  --candidate runs/candidate \
  --out runs/candidate/comparison_validity.json
```

It writes `comparison_validity.json` and `comparison_validity.md`. A `clean`
result means the recorded artifacts support a prompt-only comparison. An
`invalid` result means a blocking confound was found, such as model or split
mismatch. A `needs_review` result means the evidence is useful but incomplete.

For Quick Mode A/B prompt experiments, record the two prompt identities directly:

```bash
pcl analyze \
  --data examples/tasks.jsonl \
  --baseline-predictions examples/baseline.jsonl \
  --candidate-predictions examples/candidate.jsonl \
  --baseline-prompt-file prompts/baseline.txt \
  --candidate-prompt-file prompts/candidate.txt \
  --baseline-model claude-sonnet-4-20250514 \
  --candidate-model claude-sonnet-4-20250514 \
  --out runs/quick
```

This writes prompt hashes into `runs/quick/baseline/manifest.json` and
`runs/quick/candidate/manifest.json`, so `comparison_validity.json` can tell
whether the result is really a prompt-only comparison.

## 5. Prompt Optimization Evidence Card

After a comparison run has statistics, validity checks, and any available
research diagnostics, compress the evidence into one reviewer-facing card:

```bash
pcl evidence-card --run runs/candidate --out runs/candidate/evidence_card.md
```

The card gives a bounded recommendation: `supported`, `needs_review`,
`not_supported`, or `insufficient_evidence`. It is meant to make the evidence
trail easy to inspect, not to claim global prompt optimality.

## 6. Soft-To-Hard Deployment Gap

Soft prompts can look good during optimization but fail when projected to hard
tokens. The soft-to-hard diagnostic quantifies that gap:

```bash
pcl soft-hard \
  --soft soft_prompt.npz \
  --vocab vocab_embeddings.npz \
  --out runs/candidate/diagnostics
```

This reports projection distances and risk signals. It should be interpreted as
a deployment-risk diagnostic, not as a hard-prompt optimizer.

## 7. Hidden-State Trajectory Diagnostics

If you do not already have hidden states, extract them from a local or open
HuggingFace model first:

```bash
pcl extract-hidden \
  --model Qwen/Qwen2.5-0.5B \
  --prompts examples/tasks.jsonl \
  --out runs/candidate/inputs/hidden_states.npz \
  --pool last-token \
  --max-items 32
```

This writes `hidden_states.npz` with a `states` array and a companion
`hidden_states.npz.metadata.json` file that records model id, prompt source,
layer, pooling mode, device, and shape. The extraction command requires the
optional HF extra:

```bash
pip install -e ".[hf]"
```

The trajectory command then imports those hidden states and estimates drift and
decay:

```bash
pcl trajectory \
  --states runs/candidate/inputs/hidden_states.npz \
  --out runs/candidate/diagnostics
```

The output includes mean step drift, log-decay slope, fit quality, and a
turnpike-like signal. A negative decay slope with reasonable fit can suggest
stability-like behavior on that trace; heterogeneous traces may weaken the
signature.

## 8. Riccati Surrogate Diagnostics

The Riccati command checks a fitted or supplied finite-dimensional surrogate:

```bash
pcl riccati --matrices surrogate_mats.npz --out runs/candidate/diagnostics
```

or:

```bash
pcl riccati \
  --trajectory runs/candidate/inputs/hidden_states.npz \
  --out runs/candidate/diagnostics
```

The result reports closed-loop spectral radius and whether the surrogate looks
stable under the fitted diagnostic. This is intentionally limited: it does not
prove that the operational language model satisfies the surrogate assumptions.

## 9. Time-Varying Soft-Control Lane

The time-varying lane compares method groups:

```bash
pcl tv-soft --predictions method_predictions.jsonl --out runs/candidate/diagnostics
```

Use this to compare static, time-varying, shuffled time-varying, and random
controls. The key question is whether gains are consistent with temporal
structure or merely with extra parameter capacity.

## 10. Unified Diagnose Command

For user-provided artifacts, run the same diagnostic stack directly:

```bash
pcl diagnose \
  --soft soft_prompt.npz \
  --vocab vocab_embeddings.npz \
  --states hidden_states.npz \
  --matrices surrogate_mats.npz \
  --tv-predictions method_predictions.jsonl \
  --out runs/candidate/diagnostics
```

You can provide only the artifacts you have. `--soft` requires `--vocab`; Riccati
uses `--matrices` when available and otherwise can fit a surrogate from
`--states`.

## Applied Engineering Layer

`pcl guard`, `pcl audit-diff`, `pcl model-detect`, GitHub Action templates, and
the local UI are downstream applications. They help coding-agent users keep the
same evidence trail, but the project should be understood first as a research
diagnostic toolkit for prompt optimization.
