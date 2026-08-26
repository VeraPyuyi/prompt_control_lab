---
title: PromptControlLab
emoji: 🧭
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
fullWidth: true
header: mini
license: apache-2.0
short_description: Local-first prompt and AI-agent control diagnostics, in a safe public demo.
---

# prompt_control_lab public demo

This Docker Space is the public, CPU-only demonstration of
[prompt_control_lab](https://github.com/VeraPyuyi/prompt_control_lab), a local control,
attribution, and stability-diagnostics framework for prompts and AI agents. Its control-inspired
diagnostics are connected to the authors' mathematical work on prompt engineering and latent
dynamics ([arXiv:2606.17762](https://arxiv.org/abs/2606.17762)).

The demo can run the offline Prompt Guard and improved-prompt suggestion, inspect curated Quick
Analysis, checkpoint, Agent Audit, model-drift, history, terminal-sensitivity, Green-certificate,
and posterior-certificate artifacts, and download session results. The displayed certificates and
diagnostics are scoped evidence for the named surrogate or run. They are not a proof that an entire
language model or agent action is globally safe or optimal.

## Public-demo boundary

- No API key or external model call is used.
- No shell command, Git mutation, plugin installation, model training, or live agent bridge is
  available.
- Uploaded files are limited to bounded JSON/JSONL artifacts of at most 5 MB, with cumulative
  per-session and global temporary-storage quotas.
- Every browser session receives an isolated temporary directory. Raw Prompt text is not written to
  a server artifact; uploaded artifacts are temporarily stored in that isolated server-side
  session and disappear when the Space restarts.
- The full local CLI and source remain on
  [GitHub](https://github.com/VeraPyuyi/prompt_control_lab). Please report bugs or propose changes
  through [Issues](https://github.com/VeraPyuyi/prompt_control_lab/issues) and Pull Requests there.

For local installation, plugins, real repository audit, provider adapters, and post-training
workflows, use the GitHub project rather than this restricted Space.
