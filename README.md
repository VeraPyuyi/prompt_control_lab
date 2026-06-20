# prompt_control_lab

**Control-theoretic diagnostics and reproducible evidence for prompt optimization.**

Paper-derived prompt diagnostics plus local eval, provenance, and agent-audit artifacts. Package: `promptcontrollab`. Chinese: [README.zh.md](README.zh.md).

```bash
pip install -e ".[research,ui]"
pcl start --guide
pcl start --choice demo --out demo
pcl research-demo --out runs/research-demo && pcl diagnose --run runs/research-demo
```

## What It Adds

**Paper research core:** `pcl research-demo` -> `pcl diagnose`; advanced `soft-hard`, `trajectory`, `riccati`, `tv-soft`.

**Evidence bridge:** `pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate`; `pcl ingest` remains the backward-compatible alias for `pcl import`.

**Applied Agent Layer:** `pcl guard`, `audit-diff`, model provenance, UI (`pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501`), plugins, and GitHub templates.

Docs: [tutorial](docs/tutorial.en.md) | [paper mapping](docs/research_from_paper.en.md) | [tool choice](docs/choice_guide.en.md) | [comparison](docs/comparison.en.md) | [install](docs/release_install.en.md).

Evidence: [production pilot](docs/production_pilot.en.md) | [preflight pilot](docs/case_studies/agent_guard_pilot.en.md) | [paired pilot](docs/case_studies/agent_guard_paired_pilot.en.md) | [scorecard](docs/assets/ecosystem_scorecard.svg) / [matrix](docs/assets/ecosystem_evidence_matrix.svg) | [demo video](docs/assets/demo/prompt_control_lab_demo.en.mp4).

Boundaries: public model IDs, not hidden weights; pilots are small samples, not as universal benchmarks; guard/audit are heuristics, not safety proofs.

Apache-2.0. See [LICENSE](LICENSE).
