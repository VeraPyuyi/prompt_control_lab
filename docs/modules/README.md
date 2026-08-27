# Canonical Feature Modules

This index defines the canonical module boundaries for PromptControlLab. Real implementations live in the domain packages below; the legacy flat modules are explicit compatibility facades. Public CLI behavior and artifact schemas remain unchanged by this code-organization migration.

| Module | Responsibility | Guide |
|---|---|---|
| Core | Configuration, files, schemas, errors, versioning, optional dependencies | [English](../../src/promptcontrollab/core/README.md) · [中文](../../src/promptcontrollab/core/README.zh.md) |
| Preflight | Prompt guard, policy, improvement, token budgeting, tool selection | [English](../../src/promptcontrollab/preflight/README.md) · [中文](../../src/promptcontrollab/preflight/README.zh.md) |
| Evaluation | Split, evaluation, statistics, reports, gates, history | [English](../../src/promptcontrollab/evaluation/README.md) · [中文](../../src/promptcontrollab/evaluation/README.zh.md) |
| Control | ControlRun, lifecycle events, attribution, stability, decisions | [English](../../src/promptcontrollab/control/README.md) · [中文](../../src/promptcontrollab/control/README.zh.md) |
| Provenance | Prompt/model identity, verification evidence, model drift | [English](../../src/promptcontrollab/provenance/README.md) · [中文](../../src/promptcontrollab/provenance/README.zh.md) |
| Audit | Git diff, agent run, PR summary, SARIF, claim review | [English](../../src/promptcontrollab/audit/README.md) · [中文](../../src/promptcontrollab/audit/README.zh.md) |
| Evidence | External evidence, adapters, PEOC import, post-training gates | [English](../../src/promptcontrollab/evidence/README.md) · [中文](../../src/promptcontrollab/evidence/README.zh.md) |
| Diagnostics | Trajectory, soft-hard, Riccati, TV-soft, control certificates | [English](../../src/promptcontrollab/diagnostics/README.md) · [中文](../../src/promptcontrollab/diagnostics/README.zh.md) |
| Integrations | Providers, agents, plugins, UI, GitHub, Hugging Face | [English](../../src/promptcontrollab/integrations/README.md) · [中文](../../src/promptcontrollab/integrations/README.zh.md) |
| CLI | Stable command registration, dispatch, output, and compatibility | [English](../../src/promptcontrollab/cli/README.md) · [中文](../../src/promptcontrollab/cli/README.zh.md) |

## Dependency direction

`core` is independent. Product domains build on `core`; `control`, `evaluation`, `audit`, `evidence`, and `diagnostics` exchange structured artifacts rather than UI text. `integrations` and `cli` compose the domain APIs at the outer boundary. Canonical modules must not depend on legacy compatibility facades.

## Compatibility

Existing `pcl` commands, JSON/JSONL artifacts, plugin protocols, and documented public imports remain supported while implementations move into these packages. Private underscore-prefixed helpers and pickle-qualified paths are outside that compatibility promise.
