# PromptControlLab

PromptControlLab is an open-source toolkit for prompt evaluation, prompt diagnostics,
reproducibility, and control-oriented analysis.

It helps researchers and engineering teams answer practical questions:

- Did a prompt change really improve the result?
- Was the improvement caused by validation overfitting?
- Were train, validation, and withheld examples kept separate?
- How much behavior may be lost when a soft prompt is projected to hard tokens?
- Do hidden-state trajectories show drift, decay, or turnpike-like behavior?
- Does a time-varying prompt help because of temporal structure, or just because it has
  more parameters?

PromptControlLab is not just a score table. It creates reproducible artifacts that explain
what was tested, how it was split, how outputs were scored, whether the change is reliable,
and which diagnostics need inspection.

Chinese documentation is available in [README.zh.md](README.zh.md).

## Who It Is For

- Prompt optimization researchers who need clean train/val/withheld protocols.
- LLM engineering teams that want local prompt regression reports.
- Soft prompt researchers who need soft-to-hard deployment diagnostics.
- Model migration and evaluation teams that need repeatable artifact trails.
- Researchers studying hidden-state trajectories, turnpike-like behavior, and Riccati
  surrogate diagnostics.

## Install

```bash
pip install -e ".[dev,research]"
```

With uv:

```bash
uv pip install -e ".[dev,research]"
```

Core commands use only the standard library. Research diagnostics such as `soft-hard`,
`trajectory`, and `riccati` use optional scientific dependencies.

## Quick Start

Create an example project:

```bash
pcl init --path demo
cd demo
```

This creates example tasks, example baseline predictions, example candidate predictions,
and a short config note. It shows the input format expected by the toolkit.

Create a reproducible tri-split manifest:

```bash
pcl split --data examples/tasks.jsonl --out runs/candidate --seed 0
```

This writes `runs/candidate/splits.json`. The split hash and leakage report explain whether
train, validation, and withheld examples were kept apart.

Score the baseline and candidate outputs:

```bash
pcl eval --data examples/tasks.jsonl \
  --predictions examples/predictions_baseline.jsonl \
  --out runs/baseline \
  --metric exact_match \
  --method baseline

pcl eval --data examples/tasks.jsonl \
  --predictions examples/predictions_candidate.jsonl \
  --out runs/candidate \
  --metric exact_match \
  --method candidate
```

This writes `predictions.jsonl` and `metrics.json` for each run. These files explain how
the prompt performed on every item and on each task slice.

Compare the candidate against the baseline:

```bash
pcl stats --baseline runs/baseline/predictions.jsonl \
  --candidate runs/candidate/predictions.jsonl \
  --out runs/candidate/stats.json
```

This writes confidence intervals, a paired permutation p-value, and a Holm-adjusted p-value.
The result explains whether the observed improvement is reliable or still uncertain.

Generate a report:

```bash
pcl report --run runs/candidate --title "Candidate Prompt Report"
```

This writes `report.md` and `report.html`. The report explains what changed, what the
numbers mean, and what should be inspected next.

## Research Diagnostics

Soft-to-hard projection risk:

```bash
pcl soft-hard --soft soft_prompt.npz --vocab vocab_embeddings.npz --out runs/candidate/diagnostics
```

This reports nearest-token projection distances. Large distances indicate that hard-token
deployment may lose behavior learned by the soft prompt.

Hidden-state trajectory diagnostics:

```bash
pcl trajectory --states hidden_states.npz --out runs/candidate/diagnostics
```

This reports step drift, log-decay slope, and fit quality. A negative slope with reasonable
fit quality suggests motion toward a stable region; weak fit or high drift suggests unstable
or heterogeneous behavior.

Riccati surrogate diagnostics:

```bash
pcl riccati --trajectory hidden_states.npz --out runs/candidate/diagnostics
```

This fits a finite-dimensional surrogate and checks closed-loop spectral radius. It is a
diagnostic for the surrogate, not a proof about the full language model.

Time-varying soft-control lane:

```bash
pcl tv-soft --predictions scored_methods.jsonl --out runs/candidate/diagnostics
```

This compares methods such as `static`, `time_varying`, `shuffled_tv`, and `random_tv`.
It helps distinguish temporal-structure gains from capacity or selection effects.

## Documentation

- [Background](docs/background.en.md)
- [Users](docs/users.en.md)
- [Tutorial](docs/tutorial.en.md)
- [Artifacts](docs/artifacts.en.md)
- [Innovation and contribution](docs/innovation.en.md)

## License

Apache-2.0.

