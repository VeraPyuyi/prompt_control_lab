# prompt_control_lab

[![GitHub stars](https://img.shields.io/github/stars/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/forks)
[![GitHub watchers](https://img.shields.io/github/watchers/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/watchers)
[![License](https://img.shields.io/github/license/VeraPyuyi/prompt_control_lab)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

**Control-theoretic diagnostics and reproducible evidence for prompt optimization.**

`prompt_control_lab` is the open-source toolkit for the Prompt-Engineering-Optimal-Control project.
It turns prompt optimization experiments into auditable artifacts: clean train/validation/withheld
splits, paired statistics, prompt-only validity checks, soft-to-hard gap analysis, hidden-state
trajectory diagnostics, Riccati surrogate probes, and time-varying soft-control comparisons.

It also includes practical agent tooling, including prompt policy guardrails, public model
provenance, diff audit, GitHub/IDE templates, and a local dashboard. Those are applied workflows
built around the research evidence layer, not a replacement for the paper-derived diagnostics.

Python package name: `promptcontrollab`. Repository and project name: `prompt_control_lab`.

Chinese documentation is available in [README.zh.md](README.zh.md).

## Quick Start

```bash
git clone https://github.com/VeraPyuyi/prompt_control_lab.git
cd prompt_control_lab
pip install -e ".[research,ui]"

# One-command paper-style demo.
pcl research-demo --out runs/research-demo

# Re-run the unified research diagnostics on the demo artifacts.
pcl diagnose --run runs/research-demo

# Create a reproducible prompt-evaluation demo and open the local UI.
pcl init --path demo
cd demo
pcl analyze --config promptcontrol.example.yaml --out runs/quick
pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501
```

What you get: split hashes, scored predictions, metrics, paired bootstrap/permutation statistics,
prompt-only comparison validity, explanation, gate result, research diagnostics, report artifacts,
and a local dashboard. The UI reads local files and does not upload prompts, code, or reports.

![prompt_control_lab workflow](docs/assets/workflow.svg)

## What It Adds

| Layer | Main commands | What it helps answer |
|---|---|---|
| Reproducible protocol | `pcl split`, `pcl analyze`, `pcl stats`, `pcl validity` | Is this prompt comparison clean, paired, and statistically interpretable? |
| Paper diagnostics | `pcl soft-hard`, `pcl trajectory`, `pcl riccati`, `pcl tv-soft`, `pcl diagnose` | What happened beyond the final output score? |
| Evidence package | `pcl evidence-card`, `pcl evidence-gate`, `pcl claim-check` | What claim does the current evidence actually support? |
| Ecosystem bridge | `pcl import`, `pcl evidence-from`, `pcl evidence-audit` | What does PCL add on top of Promptfoo, DeepEval, Langfuse, LangSmith, or prompt optimizers? |
| Agent workflow | `pcl guard`, `pcl model-detect`, `pcl audit-diff`, `pcl history` | Can an AI coding-agent run be checked before and after execution? |

## Research Workflow

The fastest path through the paper-derived features is:

```bash
pcl research-demo --out runs/research-demo
pcl diagnose --run runs/research-demo
```

`research-demo` creates synthetic but inspectable artifacts for tri-split evaluation, paired
statistics, prompt-only validity, evidence cards, evidence gates, claim checks, soft-hard gap,
trajectory diagnostics, Riccati surrogate diagnostics, and time-varying soft-control comparison.

Use `pcl diagnose` on your own run directory when you already have soft prompts, hidden states,
surrogate matrices, or method predictions.

Full mapping from paper concepts to commands: [Research From The Paper](docs/research_from_paper.en.md).

![prompt_control_lab diagnostics](docs/assets/diagnostics.svg)

## Local UI

```bash
pip install -e ".[ui]"
pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501
```

The dashboard includes Research Overview, Tutorial, Workflows, Guard Prompt, Run Report, Model
Drift, Agent Diff Audit, and History. It can display artifacts and trigger allowlisted local
workflows such as guard, analyze, gate, audit-diff, agent-run build, PR summary, external evidence
import, and report zip export.

![prompt_control_lab UI workflows tutorial screenshot](docs/assets/tutorial_workflows.en.png)

Watch the 4K hands-on demos:
[English MP4](docs/assets/demo/prompt_control_lab_demo.en.mp4),
[Chinese MP4](docs/assets/demo/prompt_control_lab_demo.zh.mp4).

## Ecosystem Bridge

If you already use Promptfoo, DeepEval, Langfuse, LangSmith, or a prompt optimizer, keep them.
PCL is meant to add a research-evidence layer: prompt-only comparison validity, paired uncertainty,
evidence cards, claim checks, source/bundle hash verification, and paper-derived diagnostic gap
tracking.

```bash
pcl ecosystem-demo --examples examples/external --out runs/ecosystem-demo
pcl evidence-audit --tool promptfoo --baseline-input results.json --candidate-input results.json --out runs/from-promptfoo-audit
pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate
pcl import auto --input results.json --out runs/from-external --score-name exact_match
```

`pcl ingest` remains the backward-compatible alias for `pcl import`.

See [Ecosystem Bridge](docs/ecosystem_bridge.en.md) and
[Comparison With Promptfoo, LangSmith, Langfuse, and Prompt Optimizer](docs/comparison.en.md).
More visuals: [ecosystem scorecard](docs/assets/ecosystem_scorecard.svg) and
[PCL-added evidence matrix](docs/assets/ecosystem_evidence_matrix.svg).

![prompt_control_lab ecosystem position](docs/assets/ecosystem.svg)

## Applied Agent Layer

The engineering layer applies the same evidence habits to Claude Code, Cursor, Codex, and shell
agents:

```bash
pcl guard --prompt "Fix this bug" --profile coding --policy examples/guard.policy.yaml
pcl model-detect --response response.json --provider openai
pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit
pcl history index --runs runs/ --out runs/history_index.json
pcl export-report --run runs/quick --out runs/quick/report.zip
```

Install local templates:

```bash
pcl install-plugin codex
pcl install-plugin cursor
pcl install-plugin claude-code
pcl install-plugin github-action
```

Boundary: `pcl guard` and `pcl audit-diff` are heuristic preflight/governance tools. They reduce
obvious risk and produce audit artifacts, but they do not prove an agent action is safe.

## Evidence Boundaries

- Model provenance records public model IDs and evidence levels; it does not prove a provider's
  hidden weight version. See [Decision Guide](docs/decision_guide.en.md).
- Local paired pilots are included for transparency, not as universal benchmarks. See
  [preflight pilot](docs/case_studies/agent_guard_pilot.en.md) and
  [paired agent pilot](docs/case_studies/agent_guard_paired_pilot.en.md).
- Prompt guard can increase prompt tokens because it adds missing scope, constraints, and tests.
  The right metric is not always "shorter"; it is whether the run is clearer, safer, and more
  auditable.

## Install Notes

```bash
pip install -e .
pip install -e ".[research]"
pip install -e ".[hf]"      # optional HuggingFace hidden-state extraction
pip install -e ".[ui]"      # optional local dashboard
pcl doctor
```

For wheel/pipx readiness:

```bash
python -m build
pipx install dist/promptcontrollab-0.1.0-py3-none-any.whl
pcl doctor
```

`pcl init` writes `.promptcontrol.yaml` for local defaults such as guard policy, gate policy,
runs directory, expected paths, and UI default view. CLI flags still take precedence.

## Documentation

- [Background](docs/background.en.md)
- [Users](docs/users.en.md)
- [Tutorial](docs/tutorial.en.md)
- [Artifacts](docs/artifacts.en.md)
- [Research From The Paper](docs/research_from_paper.en.md)
- [Ecosystem Bridge](docs/ecosystem_bridge.en.md)
- [Comparison With Promptfoo, LangSmith, Langfuse, and Prompt Optimizer](docs/comparison.en.md)
- [Innovation and Contribution](docs/innovation.en.md)
- [Production pilot protocol](docs/production_pilot.en.md)
- [Release and install readiness](docs/release_install.en.md)
- [Plugin adapters](plugins/)

## License

Apache-2.0. See [LICENSE](LICENSE).
