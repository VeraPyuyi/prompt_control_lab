# prompt_control_lab

[![GitHub stars](https://img.shields.io/github/stars/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/stargazers)
[![License](https://img.shields.io/github/license/VeraPyuyi/prompt_control_lab)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

**Control-theoretic diagnostics and reproducible evidence for prompt optimization.**

`prompt_control_lab` turns prompt optimization experiments into auditable evidence: clean splits, paired statistics, soft-to-hard gap checks, hidden-state trajectory diagnostics, Riccati probes, and time-varying soft-control comparisons. Agent guardrails, model provenance, diff audit, UI, and IDE/GitHub templates are optional workflow layers.

Package: `promptcontrollab`. Chinese docs: [README.zh.md](README.zh.md).

## Quick Start

```bash
git clone https://github.com/VeraPyuyi/prompt_control_lab.git
cd prompt_control_lab
pip install -e ".[research,ui]"
pcl start --guide
pcl research-demo --out runs/research-demo && pcl diagnose --run runs/research-demo
pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501
```

## What It Adds

- **Paper research core:** `pcl research-demo`, `pcl diagnose`, `pcl soft-hard`, `pcl trajectory`, `pcl riccati`, `pcl tv-soft`.
- **Evidence bridge:** `pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate`, then `pcl scaffold-check --run runs/from-promptfoo`. `pcl ingest` remains the backward-compatible alias for `pcl import`.
- **Applied Agent Layer:** `pcl guard`, `pcl audit-diff`, model provenance, local UI, plugins, and GitHub templates.

Open the local dashboard with `pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501`. Watch the 4K walkthrough: [English MP4](docs/assets/demo/prompt_control_lab_demo.en.mp4) | [Chinese MP4](docs/assets/demo/prompt_control_lab_demo.zh.mp4).

## Boundaries

Model provenance records public model IDs and evidence levels, not hidden provider weight versions. Local pilots are transparent small samples, not as universal benchmarks. `pcl guard` and `pcl audit-diff` are heuristic governance tools, not safety proofs.

## Docs

[Paper mapping](docs/research_from_paper.en.md) | [Tutorial](docs/tutorial.en.md) | [Decision guide](docs/decision_guide.en.md) | [Install](docs/release_install.en.md) | [Comparison](docs/comparison.en.md) | [Plugins](plugins/)

Evidence: [Artifacts](docs/artifacts.en.md) | [Ecosystem bridge](docs/ecosystem_bridge.en.md) | [production pilot](docs/production_pilot.en.md) | [preflight pilot](docs/case_studies/agent_guard_pilot.en.md) | [paired pilot](docs/case_studies/agent_guard_paired_pilot.en.md) | [scorecard](docs/assets/ecosystem_scorecard.svg) | [matrix](docs/assets/ecosystem_evidence_matrix.svg)

Apache-2.0. See [LICENSE](LICENSE).
