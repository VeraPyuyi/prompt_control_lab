# PromptControlLab

**The local evidence, diagnosis, and control loop for prompts, checkpoints, and AI agents.**

> Alpha package candidate: `promptcontrollab 0.2.0a1`. The two real acceptance runs are complete; publication still requires credential rotation, candidate-commit CI, final maintainer inspection, and the fail-closed visibility/security transition.

PromptControlLab is an open-source, local-first framework for explaining where a result changed, whether the comparison is valid, how stable the observed behavior is, and whether a prompt, checkpoint, or agent run should continue. It combines preflight control with trajectory, soft-hard, generation-mismatch, selective-risk, and fitted-surrogate evidence. 中文: [README.zh.md](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/README.zh.md). Related paper: [*Horizon-Uniform Sensitivity and Decay of Terminal Reward Perturbations in Discrete-Time Pontryagin Systems*](https://arxiv.org/abs/2606.17762).

## 2-Minute Control Demo

```bash
python -m pip install -e ".[ui]"
pcl control --prompt "Inspect the request and propose a bounded plan." --authorization inspect --out runs/first-control --json
pcl ui --runs runs --language en
```

`inspect` runs the local preflight and writes a complete control run without calling a model or launching an agent.

## Preview The Outputs
<p><strong>Quickstart report.</strong> The fixed synthetic fixture returns <code>needs_review</code>: the score is higher, but the CI crosses zero, prompt identity is incomplete, and the model alias is not pinned. Run <code>pcl quickstart --out demo --open-report</code>; this verifies the reporting path, not universal improvement.</p>
<p><a href="https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/quickstart.en.md"><img src="https://raw.githubusercontent.com/VeraPyuyi/prompt_control_lab/main/docs/assets/quickstart_result.en.svg" alt="Quickstart report snapshot"></a></p>
<p><strong>Research diagnosis.</strong> The real three-seed SFT pilot improved mean score and reduced generated tokens, yet returned <code>hold</code> because stability and generation/readout checks did not pass. Open the <a href="https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/case_studies/sft_checkpoint_pilot/report.md">full report</a>, or run <code>pcl research-quickstart --out demo-research</code>.</p>
<p><a href="https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/case_studies/sft_checkpoint_pilot/README.md"><img src="https://raw.githubusercontent.com/VeraPyuyi/prompt_control_lab/main/docs/case_studies/sft_checkpoint_pilot/checkpoint_decision.svg" alt="Three-seed SFT checkpoint decision"></a></p>

## Core Diagnostic Loop

```bash
pcl evidence scan --root /path/to/evidence --profile prompt-reach-v2 --out manifest.json
pcl evidence import --manifest manifest.json --out runs/prompt-reach-v2 --portable
pcl posttrain-gate --baseline runs/checkpoint-000 --candidate runs/checkpoint-500 --policy examples/posttrain.policy.yaml --out runs/posttrain-gate
```

These commands connect dispersed experiment artifacts to prompt reachability, readout alignment, routing, projection, and stability evidence. The public-safe [371-source prompt-reach-v2 case](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/case_studies/prompt_reach_v2/README.md) reports four observed dimensions and one dimension that requires reanalysis.

The real [three-seed SFT checkpoint case](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/case_studies/sft_checkpoint_pilot/README.md) records 9 checkpoints and 6 paired gates. Mean score rose from 0.0885 to 0.1944 and mean generated tokens fell 27.2%. The format slice independently remained at 0; the `hold` was triggered by trajectory/prompt-stability and generation-mismatch/readout checks, while routing evidence remained insufficient. This is an observed, bounded workflow result, not a universal improvement claim. See the [evidence import guide](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/server_evidence.en.md) and [post-training gate](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/posttraining.en.md).

## Flagship Integration: DeepSeek Harness

The [native Cordis integration](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/deepseek_harness.en.md) gates model requests and tools, streams redacted lifecycle evidence through one persistent local bridge, and is contract-locked to Harness `0.1.1-rc.2` at `b150a551...`. The [public-safe real-session case](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/case_studies/deepseek_harness/README.md) records four model request/response pairs, two terminal reads, one bounded edit, one test invocation with exit code `0`, and 3/3 passing tests. The verified live run is `low` risk, `converging`, and conservatively `suggest`; lifecycle acceptance is still not presented as a safety proof.

## Supported Surfaces

| Surface | Current adapters |
|---|---|
| Providers | OpenAI, Anthropic, Gemini, DeepSeek, Qwen / DashScope, Kimi / Moonshot, OpenAI-compatible endpoints |
| Agents | DeepSeek Harness native control; Codex, Cursor, Claude Code, and GitHub Action prompt-guard adapters |
| Open contract | Versioned `prompt_control_lab.control_event.v1` JSONL protocol and deterministic [control benchmark](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/control_benchmark.en.md) |
| Diagnostic evidence | Trajectory/turnpike, Riccati/DARE surrogate, soft-hard/time-varying control, generation mismatch, selective risk, checkpoint gate |
| Local UI | Before / Run / Mechanism / Stability / Training Gate / Evidence Scope / Decision / History |

## Documentation

[5-minute quickstart](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/quickstart.en.md) | [Evidence and interpretation](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/server_evidence.en.md) | [Post-training diagnosis](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/posttraining.en.md) | [Control loop](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/control_loop.en.md) | [DeepSeek Harness](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/deepseek_harness.en.md) | [Providers](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/providers.en.md) | [Local UI](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/control_ui.en.md)

Install and existing workflows: [release guide](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/release_install.en.md), `pcl start --guide`, `pcl quickstart --out demo --open-report`, `pcl start --choice demo --out demo`, and `pcl choose --need "<your goal>"`.

External evidence remains available through `pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate` (`pcl ingest` remains the backward-compatible alias); see the [choice guide](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/choice_guide.en.md).

Engineering references: [production protocol](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/production_pilot.en.md), [preflight pilot](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/case_studies/agent_guard_pilot.en.md), [paired Codex pilot](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/case_studies/agent_guard_paired_pilot.en.md), [ecosystem scorecard](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/assets/ecosystem_scorecard.svg), and [evidence matrix](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/assets/ecosystem_evidence_matrix.svg). These small pilots are not universal benchmarks.

## Method Origins and Boundaries

PEOC contributes the control-theoretic framing and several diagnostic methods; the product surface generalizes them to prompt, checkpoint, and agent evidence. `soft-hard`, `trajectory`, `riccati`, and `tv-soft` are observable or fitted-surrogate explanations, not mathematical safety proofs for an operational LLM. See the [method mapping](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/research_from_paper.en.md) and [PEOC import guide](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/research_import_peoc.en.md).

One mathematical foundation for the terminal-objective sensitivity, long-horizon stability, and Riccati-surrogate diagnostics is [*Horizon-Uniform Sensitivity and Decay of Terminal Reward Perturbations in Discrete-Time Pontryagin Systems*](https://arxiv.org/abs/2606.17762) by Pyuyi Chufeng Huang and Zikang Song (2026). The paper establishes horizon-uniform Green estimates, exponential decay of terminal-reward sensitivity, a posteriori existence checks, and Riccati convergence under explicit regularity, hyperbolicity, and boundary-transversality assumptions. PromptControlLab translates these ideas into bounded diagnostics for prompt, checkpoint, and agent-run evidence; unless those assumptions are independently verified, the outputs remain observational or finite-dimensional surrogate evidence rather than a theorem about an operational language model.

Contributions are welcome: [contributing guide](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/CONTRIBUTING.md), [security policy](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/SECURITY.md),
and [v0.2.0-alpha.1 release checklist](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/docs/release_checklist_v0.2.0-alpha.1.md).

Apache-2.0. See [LICENSE](https://github.com/VeraPyuyi/prompt_control_lab/blob/main/LICENSE).
