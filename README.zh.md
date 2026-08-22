# PromptControlLab 2.0

**Prompt 与 AI Agent 的本地控制闭环。**

PromptControlLab 是一个开源、本地优先的控制框架，负责执行前检查、显式执行授权、脱敏事件记录、运行诊断和可复核决策。它面向真实 Prompt 与 Agent 工作流；研究诊断是可选能力。英文：[README.md](README.md)。

## 2 分钟 Control Demo

```bash
python -m pip install -e ".[ui]"
pcl control --prompt "检查这个请求，并提出边界清楚的计划。" --authorization inspect --out runs/first-control --json
pcl ui --runs runs --language zh
```

`inspect` 只运行本地 preflight 并写出完整 control run，不调用模型，也不启动 Agent。

## 旗舰集成：DeepSeek Harness

[原生 Cordis 集成](docs/deepseek_harness.zh.md)可以在模型请求和工具执行前 gate，并通过一个持久本地 bridge 写入脱敏生命周期证据；兼容性锁定到 Harness `0.1.1-rc.2`、commit `b150a551...`。

## 支持范围

| 范围 | 当前 adapter |
|---|---|
| Provider | OpenAI、Anthropic、Gemini、DeepSeek、Qwen / DashScope、Kimi / Moonshot、OpenAI-compatible endpoint |
| Agent | DeepSeek Harness 原生控制；Codex、Cursor、Claude Code、GitHub Action prompt-guard adapter |
| 开放协议 | 版本化 `prompt_control_lab.control_event.v1` JSONL 协议与确定性 [control benchmark](docs/control_benchmark.zh.md) |
| 本地 UI | Before / Run / Why / After / Decision / History / Advanced |

## Documentation

[控制闭环与授权](docs/control_loop.zh.md) | [DeepSeek Harness](docs/deepseek_harness.zh.md) | [Provider 与溯源](docs/providers.zh.md) | [Benchmark 解读](docs/control_benchmark.zh.md) | [本地 UI](docs/control_ui.zh.md)

安装与已有流程：[发布安装说明](docs/release_install.zh.md)、`pcl start --guide --language zh`、`pcl quickstart --language zh --out demo --open-report`、`pcl start --choice demo --language zh --out demo`、`pcl choose --need "<你的目标>" --language zh`。

外部证据仍可通过 `pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate` 导入（`pcl ingest` 是向后兼容别名）；详见[工具选择](docs/choice_guide.zh.md)。

工程参考：[production protocol](docs/production_pilot.zh.md)、[preflight pilot](docs/case_studies/agent_guard_pilot.zh.md)、[Codex 成对试点](docs/case_studies/agent_guard_paired_pilot.zh.md)、[生态 scorecard](docs/assets/ecosystem_scorecard.zh.svg)和[证据矩阵](docs/assets/ecosystem_evidence_matrix.zh.svg)。这些小样本试点不是通用 benchmark。

## 高级诊断 / Advanced Diagnostics

PEOC import 与 `soft-hard`、`trajectory`、`riccati`、`tv-soft` 只属于有边界的研究诊断，不是默认控制主线。入口见[高级功能映射](docs/research_from_paper.zh.md)和 [PEOC 导入说明](docs/research_import_peoc.zh.md)。

Apache-2.0。见 [LICENSE](LICENSE)。
