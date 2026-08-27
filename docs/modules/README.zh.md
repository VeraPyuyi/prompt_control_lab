# Canonical 功能模块

本索引定义 PromptControlLab 的 canonical 模块边界。真实实现位于下列领域 package 中，旧的平铺模块仅作为显式兼容 facade；本次代码组织调整不改变公共 CLI 行为和 artifact schema。

| 模块 | 职责 | 指南 |
|---|---|---|
| Core | 配置、文件、schema、错误、版本和可选依赖 | [English](../../src/promptcontrollab/core/README.md) · [中文](../../src/promptcontrollab/core/README.zh.md) |
| Preflight | Prompt Guard、Policy、改写、Token 预算和工具选择 | [English](../../src/promptcontrollab/preflight/README.md) · [中文](../../src/promptcontrollab/preflight/README.zh.md) |
| Evaluation | 数据切分、评测、统计、报告、Gate 和 History | [English](../../src/promptcontrollab/evaluation/README.md) · [中文](../../src/promptcontrollab/evaluation/README.zh.md) |
| Control | ControlRun、生命周期事件、归因、稳定性和决策 | [English](../../src/promptcontrollab/control/README.md) · [中文](../../src/promptcontrollab/control/README.zh.md) |
| Provenance | Prompt/模型身份、验证证据和模型漂移 | [English](../../src/promptcontrollab/provenance/README.md) · [中文](../../src/promptcontrollab/provenance/README.zh.md) |
| Audit | Git Diff、Agent Run、PR Summary、SARIF 和结论审查 | [English](../../src/promptcontrollab/audit/README.md) · [中文](../../src/promptcontrollab/audit/README.zh.md) |
| Evidence | 外部证据、Adapter、PEOC 导入和后训练 Gate | [English](../../src/promptcontrollab/evidence/README.md) · [中文](../../src/promptcontrollab/evidence/README.zh.md) |
| Diagnostics | Trajectory、Soft-Hard、Riccati、TV-Soft 和控制证书 | [English](../../src/promptcontrollab/diagnostics/README.md) · [中文](../../src/promptcontrollab/diagnostics/README.zh.md) |
| Integrations | Provider、Agent、插件、UI、GitHub 和 Hugging Face | [English](../../src/promptcontrollab/integrations/README.md) · [中文](../../src/promptcontrollab/integrations/README.zh.md) |
| CLI | 稳定的命令注册、调度、输出和兼容层 | [English](../../src/promptcontrollab/cli/README.md) · [中文](../../src/promptcontrollab/cli/README.zh.md) |

## 依赖方向

`core` 保持独立。产品领域构建在 `core` 之上；`control`、`evaluation`、`audit`、`evidence` 和 `diagnostics` 通过结构化 artifact 交换数据，而不是依赖 UI 文本。`integrations` 与 `cli` 位于最外层，负责组合领域 API。Canonical 模块不得反向依赖旧兼容 facade。

## 兼容性

实现迁移到这些 package 的过程中，现有 `pcl` 命令、JSON/JSONL artifact、插件协议和已文档化的公共导入继续受支持。以下划线开头的私有 Helper 和 Pickle 完整限定路径不在兼容承诺中。
