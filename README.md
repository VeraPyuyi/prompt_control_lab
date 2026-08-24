# PromptControlLab 2.0

**The local evidence, diagnosis, and control loop for prompts, checkpoints, and AI agents.**

> Framework direction: 2.0. Current installable Python package: `promptcontrollab 0.1.0`.

PromptControlLab is an open-source, local-first framework for explaining where a result changed, whether the comparison is valid, how stable the observed behavior is, and whether a prompt, checkpoint, or agent run should continue. It combines preflight control with trajectory, soft-hard, generation-mismatch, selective-risk, and fitted-surrogate evidence. Chinese: [README.zh.md](README.zh.md).

## 2-Minute Control Demo

```bash
python -m pip install -e ".[ui]"
pcl control --prompt "Inspect the request and propose a bounded plan." --authorization inspect --out runs/first-control --json
pcl ui --runs runs --language en
```

`inspect` runs the local preflight and writes a complete control run without calling a model or launching an agent.

## Core Diagnostic Loop

```bash
pcl evidence scan --root /path/to/experiments --profile peoc-server --out server_evidence_manifest.json
pcl evidence import --manifest server_evidence_manifest.json --out runs/server-evidence
pcl posttrain-gate --baseline runs/checkpoint-000 --candidate runs/checkpoint-500 --policy examples/posttrain.policy.yaml --out runs/posttrain-gate
```

These commands connect dispersed real experiment artifacts to five explanation roles: mechanism, stability, boundary, uncertainty, and decision. See the [real 911-source server snapshot](docs/case_studies/server_evidence/README.md), [evidence import guide](docs/server_evidence.en.md), and [post-training gate](docs/posttraining.en.md).

## Flagship Integration: DeepSeek Harness

The [native Cordis integration](docs/deepseek_harness.en.md) gates model requests and tools, streams redacted lifecycle evidence through one persistent local bridge, and is contract-locked to Harness `0.1.1-rc.2` at `b150a551...`.

## Supported Surfaces

| Surface | Current adapters |
|---|---|
| Providers | OpenAI, Anthropic, Gemini, DeepSeek, Qwen / DashScope, Kimi / Moonshot, OpenAI-compatible endpoints |
| Agents | DeepSeek Harness native control; Codex, Cursor, Claude Code, and GitHub Action prompt-guard adapters |
| Open contract | Versioned `prompt_control_lab.control_event.v1` JSONL protocol and deterministic [control benchmark](docs/control_benchmark.en.md) |
| Diagnostic evidence | Trajectory/turnpike, Riccati/DARE surrogate, soft-hard/time-varying control, generation mismatch, selective risk, checkpoint gate |
| Local UI | Before / Run / Mechanism / Stability / Training Gate / Evidence Scope / Decision / History |

## Documentation

[Evidence and interpretation](docs/server_evidence.en.md) | [Post-training diagnosis](docs/posttraining.en.md) | [Control loop](docs/control_loop.en.md) | [DeepSeek Harness](docs/deepseek_harness.en.md) | [Providers](docs/providers.en.md) | [Local UI](docs/control_ui.en.md)

Install and existing workflows: [release guide](docs/release_install.en.md), `pcl start --guide`, `pcl quickstart --out demo --open-report`, `pcl start --choice demo --out demo`, and `pcl choose --need "<your goal>"`.

External evidence remains available through `pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate` (`pcl ingest` remains the backward-compatible alias); see the [choice guide](docs/choice_guide.en.md).

Engineering references: [production protocol](docs/production_pilot.en.md), [preflight pilot](docs/case_studies/agent_guard_pilot.en.md), [paired Codex pilot](docs/case_studies/agent_guard_paired_pilot.en.md), [ecosystem scorecard](docs/assets/ecosystem_scorecard.svg), and [evidence matrix](docs/assets/ecosystem_evidence_matrix.svg). These small pilots are not universal benchmarks.

## Method Origins and Boundaries

PEOC contributes the control-theoretic framing and several diagnostic methods; the product surface generalizes them to prompt, checkpoint, and agent evidence. `soft-hard`, `trajectory`, `riccati`, and `tv-soft` are observable or fitted-surrogate explanations, not mathematical safety proofs for an operational LLM. See the [method mapping](docs/research_from_paper.en.md) and [PEOC import guide](docs/research_import_peoc.en.md).

Apache-2.0. See [LICENSE](LICENSE).
