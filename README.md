# prompt_control_lab

[![GitHub stars](https://img.shields.io/github/stars/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/stargazers) [![License](https://img.shields.io/github/license/VeraPyuyi/prompt_control_lab)](LICENSE) [![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

**Control-theoretic diagnostics and reproducible evidence for prompt optimization.**

`prompt_control_lab` turns prompt optimization into reviewable evidence: paper diagnostics, imported eval results, prompt-only validity checks, and local agent governance. Package name: `promptcontrollab`. Chinese: [README.zh.md](README.zh.md).

```bash
git clone https://github.com/VeraPyuyi/prompt_control_lab.git && cd prompt_control_lab
pip install -e ".[research,ui]"
pcl start --choice demo --out demo && pcl start --guide
pcl research-demo --out runs/research-demo && pcl diagnose --run runs/research-demo
```

## What It Adds

- **Paper research core:** `pcl research-demo`, `pcl diagnose`, `pcl soft-hard`, `pcl trajectory`, `pcl riccati`, `pcl tv-soft`.
- **Evidence bridge:** `pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate`; `pcl ingest` remains the backward-compatible alias for `pcl import`.
- **Applied Agent Layer:** `pcl guard`, `pcl audit-diff`, model provenance, local UI, plugins, and GitHub templates.

UI: `pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501`. Demo video: [EN](docs/assets/demo/prompt_control_lab_demo.en.mp4) / [ZH](docs/assets/demo/prompt_control_lab_demo.zh.mp4).

Boundaries: model provenance records public model IDs and evidence levels, not hidden provider weight versions. Local pilots are transparent small samples, not as universal benchmarks. `guard` and `audit-diff` are heuristic governance tools, not safety proofs.

Docs: [choice guide](docs/choice_guide.en.md), [tutorial](docs/tutorial.en.md), [install](docs/release_install.en.md), [paper mapping](docs/research_from_paper.en.md), [comparison](docs/comparison.en.md), [production pilot](docs/production_pilot.en.md), [preflight pilot](docs/case_studies/agent_guard_pilot.en.md), [paired pilot](docs/case_studies/agent_guard_paired_pilot.en.md), [plugins](plugins/), [scorecard](docs/assets/ecosystem_scorecard.svg), [matrix](docs/assets/ecosystem_evidence_matrix.svg).

Apache-2.0. See [LICENSE](LICENSE).
