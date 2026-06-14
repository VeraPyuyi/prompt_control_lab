# prompt_control_lab

[![GitHub stars](https://img.shields.io/github/stars/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/forks)
[![License](https://img.shields.io/github/license/VeraPyuyi/prompt_control_lab)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

**Control-theoretic diagnostics and reproducible evidence for prompt optimization.**

`prompt_control_lab` turns prompt optimization experiments into auditable artifacts: clean splits, paired statistics, soft-to-hard gap checks, hidden-state trajectory diagnostics, Riccati probes, and time-varying soft-control comparisons. Agent guardrails, model provenance, diff audit, UI, and IDE/GitHub templates are optional workflow layers.

Package name: `promptcontrollab`. Repository name: `prompt_control_lab`. Chinese docs: [README.zh.md](README.zh.md).

## Quick Start

```bash
git clone https://github.com/VeraPyuyi/prompt_control_lab.git
cd prompt_control_lab
pip install -e ".[research,ui]"
pcl research-demo --out runs/research-demo
pcl diagnose --run runs/research-demo
pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501
```

## What It Adds

```bash
# Research core
pcl research-demo --out runs/research-demo
pcl diagnose --run runs/research-demo

# Evidence bridge
pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate
pcl scaffold-check --run runs/from-promptfoo

# Applied Agent Layer
pcl guard --prompt "Fix this bug" --profile coding --policy examples/guard.policy.yaml
pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit
```

`pcl ingest` remains the backward-compatible alias for `pcl import`.

## UI And Demo

Run `pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501` for the local dashboard. It reads local artifacts only.

4K walkthroughs: [English MP4](docs/assets/demo/prompt_control_lab_demo.en.mp4) | [Chinese MP4](docs/assets/demo/prompt_control_lab_demo.zh.mp4).

## Boundaries

Model provenance records public model IDs and evidence levels, not hidden provider weight versions. Local pilots are transparent small samples, not universal benchmarks. `pcl guard` and `pcl audit-diff` are heuristic governance tools, not safety proofs.

## Docs

[Paper mapping](docs/research_from_paper.en.md) | [Tutorial](docs/tutorial.en.md) | [Artifacts](docs/artifacts.en.md) | [Ecosystem bridge](docs/ecosystem_bridge.en.md) | [Decision guide](docs/decision_guide.en.md) | [Comparison](docs/comparison.en.md) | [Install/release](docs/release_install.en.md) | [Plugins](plugins/)

Apache-2.0. See [LICENSE](LICENSE).
