# prompt_control_lab

[![GitHub stars](https://img.shields.io/github/stars/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/forks)
[![GitHub watchers](https://img.shields.io/github/watchers/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/watchers)
[![License](https://img.shields.io/github/license/VeraPyuyi/prompt_control_lab)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

**Control-theoretic diagnostics and reproducible evidence for prompt optimization.**

`prompt_control_lab` is the open-source toolkit for the Prompt-Engineering-Optimal-Control project.
It turns prompt experiments into auditable artifacts: clean splits, paired statistics,
prompt-only validity checks, soft-to-hard gap analysis, hidden-state trajectory diagnostics,
Riccati surrogate probes, and time-varying soft-control comparisons.

It also includes applied AI-coding-agent tooling: prompt policy guardrails, public model
provenance, diff audit, IDE/GitHub templates, and a local dashboard. These are workflows around
the research evidence layer, not replacements for the paper-derived diagnostics.

Package name: `promptcontrollab`. Repository name: `prompt_control_lab`.
Chinese documentation: [README.zh.md](README.zh.md).

## Quick Start

```bash
git clone https://github.com/VeraPyuyi/prompt_control_lab.git
cd prompt_control_lab
pip install -e ".[research,ui]"

pcl research-demo --out runs/research-demo
pcl diagnose --run runs/research-demo

pcl init --path demo
cd demo
pcl analyze --config promptcontrol.example.yaml --out runs/quick
pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501
```

You get split hashes, metrics, paired uncertainty, prompt-only validity, evidence gates,
research diagnostics, reports, and a local dashboard. The UI reads local files only.

![prompt_control_lab workflow](docs/assets/workflow.svg)

## What It Adds

| Layer | Commands | Main question |
|---|---|---|
| Reproducible protocol | `pcl split`, `pcl analyze`, `pcl stats`, `pcl validity` | Is the comparison clean and statistically interpretable? |
| Paper diagnostics | `pcl soft-hard`, `pcl trajectory`, `pcl riccati`, `pcl tv-soft`, `pcl diagnose` | What happened beyond the output score? |
| Evidence package | `pcl evidence-card`, `pcl evidence-gate`, `pcl claim-check` | What claim does the evidence support? |
| Ecosystem bridge | `pcl import`, `pcl evidence-from`, `pcl evidence-audit` | What evidence does PCL add to existing tools? |
| Applied Agent Layer | `pcl guard`, `pcl model-detect`, `pcl audit-diff`, `pcl history` | Can an agent run be checked before and after execution? |

## Research Workflow

```bash
pcl research-demo --out runs/research-demo
pcl diagnose --run runs/research-demo
```

This covers tri-split evaluation, paired statistics, prompt-only validity, evidence cards,
claim checks, soft-hard gap, trajectory diagnostics, Riccati surrogate diagnostics, and
time-varying soft-control. Full mapping: [Research From The Paper](docs/research_from_paper.en.md).

## Local UI

```bash
pip install -e ".[ui]"
pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501
```

Views: Research Overview, Tutorial, Workflows, Guard Prompt, Run Report, Model Drift,
Agent Diff Audit, and History.

![prompt_control_lab UI workflows tutorial screenshot](docs/assets/tutorial_workflows.en.png)

4K demos: [English MP4](docs/assets/demo/prompt_control_lab_demo.en.mp4) |
[Chinese MP4](docs/assets/demo/prompt_control_lab_demo.zh.mp4)

## Ecosystem Bridge

PCL complements Promptfoo, DeepEval, Langfuse, LangSmith, and prompt optimizers with prompt-only
validity, paired uncertainty, claim checks, hash verification, and diagnostic gap tracking.

```bash
pcl ecosystem-demo --examples examples/external --out runs/ecosystem-demo
pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate
pcl import prompt-optimizer --input favorites.json --out runs/from-prompt-optimizer
pcl import auto --input results.json --out runs/from-external --score-name exact_match
pcl evidence-audit --tool promptfoo --baseline-input results.json --candidate-input results.json --out runs/from-promptfoo-audit
```

`pcl ingest` remains the backward-compatible alias for `pcl import`.

Docs and visuals: [Ecosystem Bridge](docs/ecosystem_bridge.en.md),
[Comparison](docs/comparison.en.md),
[ecosystem scorecard](docs/assets/ecosystem_scorecard.svg),
[PCL-added evidence matrix](docs/assets/ecosystem_evidence_matrix.svg).

## Applied Agent Layer

```bash
pcl guard --prompt "Fix this bug" --profile coding --policy examples/guard.policy.yaml
pcl model-detect --response response.json --provider openai
pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit
pcl history index --runs runs/ --out runs/history_index.json
pcl export-report --run runs/quick --out runs/quick/report.zip
pcl install-plugin all
```

Boundary: `pcl guard` and `pcl audit-diff` are heuristic preflight/governance tools. They reduce
obvious risk and produce audit artifacts, but they do not prove an agent action is safe.

## Evidence Boundaries

- Model provenance records public model IDs and evidence levels; it does not prove hidden provider
  weight versions. See [Decision Guide](docs/decision_guide.en.md).
- Local paired pilots are transparent small samples, not as universal benchmarks:
  [preflight pilot](docs/case_studies/agent_guard_pilot.en.md),
  [paired agent pilot](docs/case_studies/agent_guard_paired_pilot.en.md).
- Guarded prompts may use more tokens because they add missing scope, constraints, and tests.

## Install And Docs

```bash
pip install -e .
pip install -e ".[research]"  # paper diagnostics
pip install -e ".[hf]"        # optional hidden-state extraction
pip install -e ".[ui]"        # local dashboard
pcl doctor
```

`pcl init` writes `.promptcontrol.yaml`; CLI flags still take precedence. Wheel/pipx details:
[Release and install readiness](docs/release_install.en.md).

Main docs: [Background](docs/background.en.md), [Users](docs/users.en.md),
[Tutorial](docs/tutorial.en.md), [Artifacts](docs/artifacts.en.md),
[Innovation and Contribution](docs/innovation.en.md),
[Production pilot protocol](docs/production_pilot.en.md), [Plugin adapters](plugins/).

## License

Apache-2.0. See [LICENSE](LICENSE).
