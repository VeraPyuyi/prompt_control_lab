# PromptControlLab

**Prompt、Checkpoint 与 AI Agent 的本地证据、诊断和控制闭环。**

> Alpha 包候选版本：`promptcontrollab 0.2.0a1`。真实三 seed checkpoint pilot 已完成；公共预览版目前仍等待真实 DeepSeek Harness session 验收。

PromptControlLab 是一个开源、本地优先的框架，用来解释结果为什么变化、比较是否有效、观察到的行为是否稳定，以及 Prompt、checkpoint 或 Agent run 是否值得继续。它把执行前控制与 trajectory、soft-hard、generation mismatch、selective-risk 和拟合 surrogate 证据连接起来。英文：[README.md](README.md)。

## 2 分钟 Control Demo

```bash
python -m pip install -e ".[ui]"
pcl control --prompt "检查这个请求，并提出边界清楚的计划。" --authorization inspect --out runs/first-control --json
pcl ui --runs runs --language zh
```

`inspect` 只运行本地 preflight 并写出完整 control run，不调用模型，也不启动 Agent。

## 核心诊断闭环

```bash
pcl evidence scan --root /path/to/evidence --profile prompt-reach-v2 --out manifest.json
pcl evidence import --manifest manifest.json --out runs/prompt-reach-v2 --portable
pcl posttrain-gate --baseline runs/checkpoint-000 --candidate runs/checkpoint-500 --policy examples/posttrain.policy.yaml --out runs/posttrain-gate
```

这三步把分散的实验 artifact 归入 Prompt 可达性、读出对齐、路由、投影和稳定性五类证据。公开安全的 [371 项 prompt-reach-v2 案例](docs/case_studies/prompt_reach_v2/README.zh.md)中有四类已观测、一类需要重新分析。

真实的[三 seed SFT checkpoint 案例](docs/case_studies/sft_checkpoint_pilot/README.zh.md)包含 9 个 checkpoint 和 6 个配对 gate。平均分数从 0.0885 提高到 0.1944，平均生成 token 减少 27.2%。格式 slice 独立地保持为 0；真正触发 `hold` 的是 trajectory/prompt stability 与 generation mismatch/readout 检查，routing 证据则仍然不足。这是有边界的真实工作流结果，不是普遍提升声明。参见[证据导入说明](docs/server_evidence.zh.md)和[后训练门禁](docs/posttraining.zh.md)。

## 旗舰集成：DeepSeek Harness

[原生 Cordis 集成](docs/deepseek_harness.zh.md)可以在模型请求和工具执行前 gate，并通过一个持久本地 bridge 写入脱敏生命周期证据；兼容性锁定到 Harness `0.1.1-rc.2`、commit `b150a551...`。[可公开集成状态](docs/case_studies/deepseek_harness/README.zh.md)记录已验证的 bridge 与脱敏链路，同时明确标记：在本地提供 provider credential 前，真实模型、工具、修改与测试会话仍处于阻塞状态。

## 支持范围

| 范围 | 当前 adapter |
|---|---|
| Provider | OpenAI、Anthropic、Gemini、DeepSeek、Qwen / DashScope、Kimi / Moonshot、OpenAI-compatible endpoint |
| Agent | DeepSeek Harness 原生控制；Codex、Cursor、Claude Code、GitHub Action prompt-guard adapter |
| 开放协议 | 版本化 `prompt_control_lab.control_event.v1` JSONL 协议与确定性 [control benchmark](docs/control_benchmark.zh.md) |
| 诊断证据 | Trajectory/turnpike、Riccati/DARE surrogate、soft-hard/time-varying control、generation mismatch、selective risk、checkpoint gate |
| 本地 UI | 执行前 / 运行中 / 机制解释 / 稳定性 / 训练门禁 / 证据边界 / 决策 / 历史 |

## Documentation

[五分钟快速上手](docs/quickstart.zh.md) | [证据与可解释性](docs/server_evidence.zh.md) | [后训练诊断](docs/posttraining.zh.md) | [控制闭环](docs/control_loop.zh.md) | [DeepSeek Harness](docs/deepseek_harness.zh.md) | [Provider](docs/providers.zh.md) | [本地 UI](docs/control_ui.zh.md)

安装与已有流程：[发布安装说明](docs/release_install.zh.md)、`pcl start --guide --language zh`、`pcl quickstart --language zh --out demo --open-report`、`pcl start --choice demo --language zh --out demo`、`pcl choose --need "<你的目标>" --language zh`。

外部证据仍可通过 `pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate` 导入（`pcl ingest` 是向后兼容别名）；详见[工具选择](docs/choice_guide.zh.md)。

工程参考：[production protocol](docs/production_pilot.zh.md)、[preflight pilot](docs/case_studies/agent_guard_pilot.zh.md)、[Codex 成对试点](docs/case_studies/agent_guard_paired_pilot.zh.md)、[生态 scorecard](docs/assets/ecosystem_scorecard.zh.svg)和[证据矩阵](docs/assets/ecosystem_evidence_matrix.zh.svg)。这些小样本试点不是通用 benchmark。

## 方法来源与结论边界

PEOC 提供控制论框架和若干诊断方法；产品层将其推广到 Prompt、checkpoint 与 Agent 证据。`soft-hard`、`trajectory`、`riccati`、`tv-soft` 属于基于观测或拟合 surrogate 的解释，不能当作线上 LLM 的数学安全证明。参见[方法映射](docs/research_from_paper.zh.md)和 [PEOC 导入说明](docs/research_import_peoc.zh.md)。

Apache-2.0。见 [LICENSE](LICENSE)。
