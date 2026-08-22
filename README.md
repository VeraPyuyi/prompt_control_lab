# prompt_control_lab

**Control-theoretic diagnostics and reproducible evidence for prompt optimization.** Package: `promptcontrollab`. Chinese: [README.zh.md](README.zh.md).

Import a real PEOC replication bundle, see exactly which evidence is available, failed, unusable, or missing, and prevent a small result from becoming an oversized claim.

```bash
pip install -e ".[research,ui]"
pcl research-import peoc --bundle <path-to-nmi_replication_bundle> --out runs/peoc-real --portable
pcl ui --runs runs --language en
```

## What It Adds

- **Real evidence first:** source hashes, normalized PEOC evidence, bounded case study, claim check, gap plan, and verified research bundle.
- **Fresh research diagnostics:** `pcl research-quickstart`, `pcl research-demo`, `pcl diagnose`, plus `soft-hard`, `trajectory`, `riccati`, and `tv-soft`.
- **Reproducible evaluation:** tri-split withheld protocol, paired statistics, prompt-only validity, evidence cards, and fail-closed claim tiers.
- **Applied Agent Layer:** `guard`, model provenance, `audit-diff`, local UI, IDE/CLI adapters, and GitHub review artifacts reuse the same evidence discipline.

## Start Here

- Real PEOC import, step by step: [tutorial](docs/research_import_peoc.en.md)
- Paper concept -> command -> interpretation: [research mapping](docs/research_from_paper.en.md)
- No real bundle yet: `pcl research-quickstart --out runs/research-demo --open-report`
- External eval results: `pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate` (`pcl ingest` remains the backward-compatible alias)
- Choose the shortest path: `pcl choose --need "<your goal>"` and [choice guide](docs/choice_guide.en.md)

Real bounded evidence: [PEOC case study](docs/case_studies/peoc_real/README.md). Demo: [4K walkthrough](docs/assets/demo/prompt_control_lab_demo.en.mp4). Install: [release guide](docs/release_install.en.md).

Boundaries: imported results are not fresh reruns; task-specific hard scores are not universal rankings; trajectory/Riccati results are diagnostics or fitted-surrogate checks; public model IDs and hashes do not prove hidden weights; guard/audit are heuristics, not safety proofs.

Apache-2.0. See [LICENSE](LICENSE).
