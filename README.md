# prompt_control_lab

[![GitHub stars](https://img.shields.io/github/stars/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/stargazers) [![License](https://img.shields.io/github/license/VeraPyuyi/prompt_control_lab)](LICENSE) [![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

**Control-theoretic diagnostics and reproducible evidence for prompt optimization.**

Local CLI/UI for paper-derived prompt diagnostics, eval evidence, model provenance, and AI-agent audits. Package: `promptcontrollab`. Chinese: [README.zh.md](README.zh.md).

```bash
pip install -e ".[research,ui]"
pcl start --guide
pcl start --choice demo --out demo
pcl research-demo --out runs/research-demo && pcl diagnose --run runs/research-demo
pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501
```

## What It Adds

- **Paper research core:** `pcl research-demo`, `pcl diagnose`, `soft-hard`, `trajectory`, `riccati`, `tv-soft`.
- **Evidence bridge:** `pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate`; `pcl ingest` remains the backward-compatible alias for `pcl import`.
- **Applied Agent Layer:** `pcl guard`, `audit-diff`, model provenance, UI, plugins, GitHub templates.

Start here: [tutorial](docs/tutorial.en.md), [paper mapping](docs/research_from_paper.en.md), [tool choice](docs/choice_guide.en.md), [comparison](docs/comparison.en.md), [install](docs/release_install.en.md).

Docs, evidence, and assets: [production pilot](docs/production_pilot.en.md), [preflight pilot](docs/case_studies/agent_guard_pilot.en.md), [paired pilot](docs/case_studies/agent_guard_paired_pilot.en.md), [scorecard](docs/assets/ecosystem_scorecard.svg), [matrix](docs/assets/ecosystem_evidence_matrix.svg), [demo video](docs/assets/demo/prompt_control_lab_demo.en.mp4).

Boundaries: public model IDs, not hidden weights; pilots are small samples, not as universal benchmarks; guard/audit are heuristics, not safety proofs.

Apache-2.0. See [LICENSE](LICENSE).
