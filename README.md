# PromptControlLab 2.0

**The local control loop for prompts and AI agents.**

PromptControlLab is an open-source, local-first framework for preflight checks, explicit execution authorization, redacted event capture, run diagnosis, and reviewable decisions. It controls real prompt and agent workflows; research diagnostics are optional. Chinese: [README.zh.md](README.zh.md).

## 2-Minute Control Demo

```bash
python -m pip install -e ".[ui]"
pcl control --prompt "Inspect the request and propose a bounded plan." --authorization inspect --out runs/first-control --json
pcl ui --runs runs --language en
```

`inspect` runs the local preflight and writes a complete control run without calling a model or launching an agent.

## Flagship Integration: DeepSeek Harness

The [native Cordis integration](docs/deepseek_harness.en.md) gates model requests and tools, streams redacted lifecycle evidence through one persistent local bridge, and is contract-locked to Harness `0.1.1-rc.2` at `b150a551...`.

## Supported Surfaces

| Surface | Current adapters |
|---|---|
| Providers | OpenAI, Anthropic, Gemini, DeepSeek, Qwen / DashScope, Kimi / Moonshot, OpenAI-compatible endpoints |
| Agents | DeepSeek Harness native control; Codex, Cursor, Claude Code, and GitHub Action prompt-guard adapters |
| Open contract | Versioned `prompt_control_lab.control_event.v1` JSONL protocol and deterministic [control benchmark](docs/control_benchmark.en.md) |
| Local UI | Before / Run / Why / After / Decision / History / Advanced |

## Documentation

[Control loop and authorization](docs/control_loop.en.md) | [DeepSeek Harness](docs/deepseek_harness.en.md) | [Providers and provenance](docs/providers.en.md) | [Benchmark interpretation](docs/control_benchmark.en.md) | [Local UI](docs/control_ui.en.md)

Install and existing workflows: [release guide](docs/release_install.en.md), `pcl start --guide`, `pcl quickstart --out demo --open-report`, `pcl start --choice demo --out demo`, and `pcl choose --need "<your goal>"`.

External evidence remains available through `pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate` (`pcl ingest` remains the backward-compatible alias); see the [choice guide](docs/choice_guide.en.md).

Engineering references: [production protocol](docs/production_pilot.en.md), [preflight pilot](docs/case_studies/agent_guard_pilot.en.md), [paired Codex pilot](docs/case_studies/agent_guard_paired_pilot.en.md), [ecosystem scorecard](docs/assets/ecosystem_scorecard.svg), and [evidence matrix](docs/assets/ecosystem_evidence_matrix.svg). These small pilots are not universal benchmarks.

## Advanced Diagnostics

PEOC import plus `soft-hard`, `trajectory`, `riccati`, and `tv-soft` are bounded research diagnostics, not the default control path. Start with the [advanced mapping](docs/research_from_paper.en.md) or [PEOC import guide](docs/research_import_peoc.en.md).

Apache-2.0. See [LICENSE](LICENSE).
