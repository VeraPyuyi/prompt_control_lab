# prompt_control_lab

[![GitHub stars](https://img.shields.io/github/stars/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/forks)
[![GitHub watchers](https://img.shields.io/github/watchers/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/watchers)
[![License](https://img.shields.io/github/license/VeraPyuyi/prompt_control_lab)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

**Control-theoretic diagnostics and reproducible evidence for prompt optimization.**

`prompt_control_lab` turns prompt optimization experiments into auditable artifacts: clean splits, paired statistics, prompt-only validity checks, soft-to-hard gap analysis, hidden-state trajectory diagnostics, Riccati surrogate probes, and time-varying soft-control comparisons. It also includes a practical layer for agent prompt guardrails, model provenance, diff audit, local UI, and IDE/GitHub templates.

Package name: `promptcontrollab`. Repository name: `prompt_control_lab`. Chinese docs: [README.zh.md](README.zh.md).

## Start Here

```bash
git clone https://github.com/VeraPyuyi/prompt_control_lab.git
cd prompt_control_lab
pip install -e ".[research,ui]"
pcl research-demo --out runs/research-demo
pcl diagnose --run runs/research-demo
pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501
```

This creates a local research bundle, diagnostics report, and dashboard. Nothing is uploaded by the UI.

![prompt_control_lab workflow](docs/assets/workflow.svg)

## What It Adds

| Path | What you get | First command |
|---|---|---|
| Paper workflow | tri-split protocol, soft-hard, trajectory, Riccati, tv-soft diagnostics | `pcl research-demo` |
| Evidence bridge | reviewer-facing cards and audits for external eval exports | `pcl import`, `pcl evidence-audit` |
| Applied Agent Layer | prompt preflight, model provenance, diff audit, run history | `pcl guard`, `pcl audit-diff` |

Paper mapping: [Research From The Paper](docs/research_from_paper.en.md). Ecosystem comparison: [Ecosystem Bridge](docs/ecosystem_bridge.en.md).

## Useful Commands

```bash
pcl guard --prompt "Fix this bug" --profile coding --policy examples/guard.policy.yaml
pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate
pcl import prompt-optimizer --input favorites.json --out runs/from-prompt-optimizer
pcl scaffold-check --run runs/from-prompt-optimizer
pcl evidence-audit --tool promptfoo --baseline-input results.json --candidate-input results.json --out runs/audit
pcl model-detect --response response.json --provider openai
pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit
pcl export-report --run runs/quick --out runs/quick/report.zip
```

`pcl ingest` remains the backward-compatible alias for `pcl import`.

## UI And Demo

The local UI includes Research Overview, Tutorial, Workflows, Guard Prompt, Run Report, Model Drift, Agent Diff Audit, and History.

![prompt_control_lab UI workflows tutorial screenshot](docs/assets/tutorial_workflows.en.png)

4K demos: [English MP4](docs/assets/demo/prompt_control_lab_demo.en.mp4) | [Chinese MP4](docs/assets/demo/prompt_control_lab_demo.zh.mp4).

## Boundaries

- Model provenance records public model IDs and evidence levels; it does not prove hidden provider weight versions. See [Decision Guide](docs/decision_guide.en.md).
- Local pilots are transparent small samples, not as universal benchmarks: [preflight pilot](docs/case_studies/agent_guard_pilot.en.md), [paired agent pilot](docs/case_studies/agent_guard_paired_pilot.en.md), [production pilot protocol](docs/production_pilot.en.md).
- `pcl guard` and `pcl audit-diff` are heuristic preflight/governance tools. They reduce obvious risk and produce audit artifacts; they do not prove an agent action is safe.

## Docs

[Background](docs/background.en.md) | [Tutorial](docs/tutorial.en.md) | [Artifacts](docs/artifacts.en.md) | [Innovation](docs/innovation.en.md) | [Comparison](docs/comparison.en.md) | [Ecosystem scorecard](docs/assets/ecosystem_scorecard.svg) | [Evidence matrix](docs/assets/ecosystem_evidence_matrix.svg) | [Release/install](docs/release_install.en.md) | [Plugins](plugins/)

Apache-2.0. See [LICENSE](LICENSE).
