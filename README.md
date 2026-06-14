# prompt_control_lab

[![GitHub stars](https://img.shields.io/github/stars/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/forks)
[![GitHub watchers](https://img.shields.io/github/watchers/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/watchers)
[![License](https://img.shields.io/github/license/VeraPyuyi/prompt_control_lab)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

**Control-theoretic diagnostics and reproducible evidence for prompt optimization.**

`prompt_control_lab` turns prompt experiments into auditable evidence for the paper workflow: clean splits, paired statistics, soft-to-hard gaps, hidden-state trajectories, Riccati probes, and time-varying soft-control comparisons. Agent guardrails, model provenance, diff audit, UI, and IDE/GitHub templates are support layers.

Package name: `promptcontrollab`. Repository name: `prompt_control_lab`. Chinese docs: [README.zh.md](README.zh.md).

## 60-Second Start

```bash
git clone https://github.com/VeraPyuyi/prompt_control_lab.git
cd prompt_control_lab
pip install -e ".[research,ui]"
pcl research-demo --out runs/research-demo
pcl diagnose --run runs/research-demo
pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501
```

This creates a local research bundle, diagnostics report, and dashboard. The UI reads local files only.

![prompt_control_lab workflow](docs/assets/workflow.svg)

## What It Adds

- **Research:** `pcl research-demo`, `pcl diagnose`.
- **Evidence bridge:** `pcl import`, `pcl scaffold-check`, `pcl evidence-audit`.
- **Applied Agent Layer:** `pcl guard`, `pcl model-detect`, `pcl audit-diff`, `pcl history`.

Paper mapping: [Research From The Paper](docs/research_from_paper.en.md). Ecosystem comparison: [Ecosystem Bridge](docs/ecosystem_bridge.en.md).

## Command Cheatsheet

```bash
pcl guard --prompt "Fix this bug" --profile coding --policy examples/guard.policy.yaml
pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate
pcl import prompt-optimizer --input favorites.json --out runs/from-prompt-optimizer
pcl scaffold-check --run runs/from-prompt-optimizer
pcl evidence-audit --tool promptfoo --baseline-input results.json --candidate-input results.json --out runs/audit
pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit
```

`pcl ingest` remains the backward-compatible alias for `pcl import`.

## UI And Demo

Run `pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501` for the local dashboard: Research Overview, Tutorial, Workflows, Guard, Report, Drift, Audit, and History.

4K walkthroughs: [English MP4](docs/assets/demo/prompt_control_lab_demo.en.mp4) | [Chinese MP4](docs/assets/demo/prompt_control_lab_demo.zh.mp4).

## Boundaries

- Model provenance records public model IDs and evidence levels; it does not prove hidden provider weight versions.
- Local pilots are small transparent samples, not as universal benchmarks.
- `pcl guard` and `pcl audit-diff` are heuristic governance tools, not safety proofs.

Details: [Decision Guide](docs/decision_guide.en.md), [pilot reports](docs/case_studies/agent_guard_pilot.en.md), [paired pilot](docs/case_studies/agent_guard_paired_pilot.en.md), [production pilot protocol](docs/production_pilot.en.md).

## Docs

[Tutorial](docs/tutorial.en.md) | [Artifacts](docs/artifacts.en.md) | [Innovation](docs/innovation.en.md) | [Comparison](docs/comparison.en.md) | [Ecosystem scorecard](docs/assets/ecosystem_scorecard.svg) | [Evidence matrix](docs/assets/ecosystem_evidence_matrix.svg) | [Release/install](docs/release_install.en.md) | [Plugins](plugins/)

Apache-2.0. See [LICENSE](LICENSE).
