# prompt_control_lab

**Control-theoretic diagnostics and reproducible evidence for prompt optimization.** Package: `promptcontrollab`. Chinese: [README.zh.md](README.zh.md).

```bash
pip install -e ".[research,ui]"
pcl start --guide
pcl research-quickstart --out runs/research-demo --open-report
```

## What It Adds

- **Paper research core:** `pcl research-quickstart`; lower-level `pcl research-demo` + `pcl diagnose`; advanced `soft-hard`, `trajectory`, `riccati`, `tv-soft`.
- **Evidence bridge:** `pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate`; `pcl ingest` remains the backward-compatible alias.
- **Applied Agent Layer:** `pcl choose --need "security evals"` points to `guard`, `audit-diff`, local UI, plugins, and GitHub templates.

Start: [tutorial](docs/tutorial.en.md), [choice guide](docs/choice_guide.en.md), [install](docs/release_install.en.md). Quick demo: `pcl quickstart --out demo --open-report`; alias: `pcl start --choice demo --out demo`.

<details><summary>Evidence, paper map, and boundaries</summary>

Paper: [mapping](docs/research_from_paper.en.md), [comparison](docs/comparison.en.md). Evidence: [production](docs/production_pilot.en.md), [preflight](docs/case_studies/agent_guard_pilot.en.md), [paired](docs/case_studies/agent_guard_paired_pilot.en.md), [scorecard](docs/assets/ecosystem_scorecard.svg), [matrix](docs/assets/ecosystem_evidence_matrix.svg), [video](docs/assets/demo/prompt_control_lab_demo.en.mp4).

Boundaries: public model IDs, not hidden weights; pilots are small samples, not as universal benchmarks; guard/audit are heuristics, not safety proofs.

</details>

Apache-2.0. See [LICENSE](LICENSE).
