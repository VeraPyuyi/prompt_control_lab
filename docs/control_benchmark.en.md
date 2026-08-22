# Control Benchmark

[中文](control_benchmark.zh.md) | [Control loop](control_loop.en.md) | [Providers](providers.en.md) | [Local UI](control_ui.en.md)

PromptControlLab ships an open, versioned benchmark fixture for checking the deterministic control-analysis contract. It is a synthetic regression suite, not a leaderboard for public models or agents.

## Run it

```bash
python -m promptcontrollab.control_benchmark examples/control-benchmark/manifest.json
```

The manifest uses `prompt_control_lab.control_benchmark_manifest.v1`; the command prints one `prompt_control_lab.control_benchmark_result.v1` object. Its fixtures use the observable event shape exercised by `prompt_control_lab.control_event.v1`, but this command does not write `ControlRun` or `ControlEvent` artifacts. Results can still be inspected without a hosted service or private evaluator.

## What is measured

The fixture contains five labeled trajectories:

| Label | Contract exercised |
|---|---|
| `converging` | Error decreases within the observation window. |
| `stalled` | Progress remains below the configured threshold. |
| `oscillating` | Direction changes repeatedly without stable convergence. |
| `diverging` | Error grows across the observed steps. |
| `insufficient_evidence` | The trace is too short or incomplete for a supported decision. |

`accuracy` is the fraction of fixture labels reproduced by the deterministic analyzer. It is useful for detecting analyzer or event-protocol regressions. Read it together with the fixture manifest, protocol version, configuration, and per-case output rather than as a standalone quality score.

## Interpretation boundary

This benchmark does **not** measure model intelligence, agent task performance, causal impact, production reliability, or safety. Passing it does not prove that a prompt, provider, or agent is better, and it does not establish a causal effect of enabling control. Public-model comparisons need independently recorded model identifiers, endpoints, parameters, dates, raw artifacts, and an evaluation design appropriate to the claim.

Use the benchmark to answer one narrow question: given these versioned synthetic events, does this PromptControlLab version produce the expected control classifications? Use real run artifacts and an explicit study protocol for anything broader.
