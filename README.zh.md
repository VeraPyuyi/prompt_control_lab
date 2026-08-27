# PromptControlLab
**面向 Prompt、模型、Checkpoint 与 AI Agent 的本地 Change Review 决策层。**
> 当前为公开 Alpha 源码预览：`promptcontrollab 0.2.0a1`。仓库包含三条有边界的真实验收工作流；GitHub Release 构建产物和 PyPI 包尚未发布。

PromptControlLab 是一个开源、本地优先的变更审查框架，用来回答一次已记录的变更到底改了什么、观察到了什么、最可能由哪些已记录因素造成、证据有多可靠，以及 candidate 是否值得继续或发布。它把 Prompt 执行前检查、模型与运行溯源、可复现评测、Agent 改动审计和有边界的稳定性诊断收敛成一个面向 reviewer 的决策。英文：[README.md](README.md)。相关论文：[*Horizon-Uniform Sensitivity and Decay of Terminal Reward Perturbations in Discrete-Time Pontryagin Systems*](https://arxiv.org/abs/2606.17762)。

## 2 分钟 Change Review

```bash
python -m pip install -e ".[ui]"
pcl review --baseline docs/case_studies/checkpoint_change_review/baseline --candidate docs/case_studies/checkpoint_change_review/candidate --out runs/checkpoint-review
pcl ui --runs runs/checkpoint-review --language zh
```

Change Review 默认使用 `shadow` 模式：只读取已有 artifact，写出有边界的解释和决策轨迹，不改变 baseline 或 candidate。需要在执行前检查 Prompt 时，再使用 `pcl control --authorization inspect`。

如果已有 Agent telemetry，可以先统一导入：

```bash
pcl trace import --input traces.jsonl --format auto --out runs/imported
pcl review --baseline runs/old --candidate runs/imported --kind auto --out runs/change-review
```

Trace 导入支持 OpenTelemetry GenAI 与 OpenInference JSONL，默认执行排序、去重和敏感字段脱敏。

## 在 Hugging Face 体验
<p><a href="https://huggingface.co/spaces/VeraPyuyi/prompt-control-lab"><img src="https://img.shields.io/badge/🤗%20在线体验-Hugging%20Face-yellow" alt="在 Hugging Face 体验"></a> <a href="https://huggingface.co/spaces/VeraPyuyi/prompt-control-lab"><img src="docs/assets/hf_space.zh.png" alt="Hugging Face 中文演示预览" width="760"></a></p>
公开 Space 使用免费 CPU，不需要 API key，可体验离线 Guard/Prompt 改进、预置报告、审计、History、控制证书和受限 JSON/JSONL 上传，每个浏览器会话使用独立临时目录。[本地完整版](docs/huggingface_space.zh.md)另有可持久化 run、真实仓库审计、Provider、插件、DeepSeek Harness 和后训练工作流；边界详见 [`deploy/huggingface/README.md`](deploy/huggingface/README.md)。GitHub 仍是源码、Issue、PR 和 Release 的唯一主仓库。

## 先看示例结果
<p><strong>统一 Change Review。</strong> 三个旗舰案例用同一流程审查 Agent、模型与 Checkpoint 变更：60 次真实 Codex 执行案例在完成率相同的情况下记录到更低的完整运行 Token 和工具调用；Qwen/Mistral 历史聚合案例因任务切片方向不同且缺少逐样本配对而保持 <code>needs_review</code>；三 Seed Checkpoint 案例则在分数提高后仍保留 <code>hold</code>。</p>
<p><a href="docs/case_studies/agent_change_review/README.zh.md">Agent 运行案例</a> | <a href="docs/case_studies/model_change_review/README.zh.md">模型切换案例</a> | <a href="docs/case_studies/checkpoint_change_review/README.zh.md">Checkpoint 案例</a>。</p>
<p><strong>Quickstart 报告。</strong> 固定合成样例给出 <code>needs_review</code>：分数更高，但置信区间跨 0、Prompt 身份不完整、模型 alias 未锁定。运行 <code>pcl quickstart --out demo --language zh --open-report</code> 即可生成；它验证报告链路，不是普遍提升证明。</p>
<p><a href="docs/quickstart.zh.md"><img src="docs/assets/quickstart_result.zh.svg" alt="Quickstart 报告快照"></a></p>
<p><strong>研究诊断。</strong> 真实三 seed SFT 试点中，平均分数提高、生成 Token 减少，但稳定性与生成错配/读出检查没有通过，因此 checkpoint gate 给出 <code>hold</code>。查看<a href="docs/case_studies/sft_checkpoint_pilot/README.zh.md">完整案例</a>，或运行 <code>pcl research-quickstart --out demo-research --language zh</code>。</p>
<p><a href="docs/case_studies/sft_checkpoint_pilot/README.zh.md"><img src="docs/case_studies/sft_checkpoint_pilot/checkpoint_decision.zh.svg" alt="三 seed SFT checkpoint 决策"></a></p>

## 核心诊断闭环

```bash
pcl evidence scan --root /path/to/evidence --profile prompt-reach-v2 --out manifest.json
pcl evidence import --manifest manifest.json --out runs/prompt-reach-v2 --portable
pcl posttrain-gate --baseline runs/checkpoint-000 --candidate runs/checkpoint-500 --policy examples/posttrain.policy.yaml --out runs/posttrain-gate
```

这三步把分散的实验 artifact 归入 Prompt 可达性、读出对齐、路由、投影和稳定性五类证据。公开安全的 [371 项 prompt-reach-v2 案例](docs/case_studies/prompt_reach_v2/README.zh.md)中有四类已观测、一类需要重新分析。如需有边界的控制检查，可使用 `pcl terminal-sensitivity`、`pcl green-certificate` 和 `pcl posterior-certificate`，区分经验趋势、有限维 surrogate 一致性与有 premise 支持的局部证书。详见[控制证书指南](docs/control_certificates.zh.md)；任何等级都不等于对完整线上语言模型的证明。

真实的[三 seed SFT checkpoint 案例](docs/case_studies/sft_checkpoint_pilot/README.zh.md)包含 9 个 checkpoint 和 6 个配对 gate。平均分数从 0.0885 提高到 0.1944，平均生成 token 减少 27.2%。格式 slice 独立地保持为 0；真正触发 `hold` 的是 trajectory/prompt stability 与 generation mismatch/readout 检查，routing 证据则仍然不足。这是有边界的真实工作流结果，不是普遍提升声明。参见[证据导入说明](docs/server_evidence.zh.md)和[后训练门禁](docs/posttraining.zh.md)。
## 旗舰集成：DeepSeek Harness

[原生 Cordis 集成](docs/deepseek_harness.zh.md)可以在模型请求和工具执行前 gate，并通过一个持久本地 bridge 写入脱敏生命周期证据；兼容性锁定到 Harness `0.1.1-rc.2`、commit `b150a551...`。[可公开真实会话案例](docs/case_studies/deepseek_harness/README.zh.md)记录了 4 组模型请求/响应、2 次终态读取、1 次有界修改、1 次退出码为 `0` 的测试调用和 3/3 测试通过。经过严格协议验收的真实运行是 `low` risk、`converging`，最终仍保守给出 `suggest`；生命周期验收不被包装成安全证明。
## 支持范围
Provider 包括 OpenAI、Anthropic、Gemini、DeepSeek、Qwen/DashScope、Kimi/Moonshot 和 OpenAI-compatible endpoint；Agent 包括 DeepSeek Harness 原生控制以及 Codex、Cursor、Claude Code、GitHub Action adapter。版本化 `prompt_control_lab.control_event.v1` 协议连接 Change Review、最终目标影响、局部稳定边界、局部解可信范围与本地 UI：变更审查 / 执行前 / 运行 / 原因 / 执行后 / 决策 / 历史 / 稳定性与可信度。参见 [control benchmark](docs/control_benchmark.zh.md)。
## Documentation

[架构与模块](docs/modules/README.zh.md) | [五分钟快速上手](docs/quickstart.zh.md) | [控制证书](docs/control_certificates.zh.md) | [证据与可解释性](docs/server_evidence.zh.md) | [后训练诊断](docs/posttraining.zh.md) | [控制闭环](docs/control_loop.zh.md) | [DeepSeek Harness](docs/deepseek_harness.zh.md) | [Provider](docs/providers.zh.md) | [本地 UI](docs/control_ui.zh.md)

安装与已有流程：[发布安装说明](docs/release_install.zh.md)、`pcl start --guide --language zh`、`pcl quickstart --language zh --out demo --open-report`、`pcl start --choice demo --language zh --out demo`、`pcl choose --need "<你的目标>" --language zh`。

外部证据仍可通过 `pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate` 导入（`pcl ingest` 是向后兼容别名）；详见[工具选择](docs/choice_guide.zh.md)。

工程参考：[production protocol](docs/production_pilot.zh.md)、[preflight pilot](docs/case_studies/agent_guard_pilot.zh.md)、[Codex 成对试点](docs/case_studies/agent_guard_paired_pilot.zh.md)、[生态 scorecard](docs/assets/ecosystem_scorecard.zh.svg)和[证据矩阵](docs/assets/ecosystem_evidence_matrix.zh.svg)。这些小样本试点不是通用 benchmark。
## 方法来源与结论边界

PEOC 提供控制论框架和若干诊断方法；产品层将其推广到 Prompt、checkpoint 与 Agent 证据。`soft-hard`、`trajectory`、`riccati`、`tv-soft` 属于基于观测或拟合 surrogate 的解释，不能当作线上 LLM 的数学安全证明。参见[方法映射](docs/research_from_paper.zh.md)和 [PEOC 导入说明](docs/research_import_peoc.zh.md)。

终端目标敏感性、长时域稳定性和 Riccati surrogate 诊断的一项数学基础是 Pyuyi Chufeng Huang 与 Zikang Song（2026）的论文 [*Horizon-Uniform Sensitivity and Decay of Terminal Reward Perturbations in Discrete-Time Pontryagin Systems*](https://arxiv.org/abs/2606.17762)。该论文在明确的正则性、双曲性和边界横截条件下，给出了时域一致的 Green estimate、终端奖励敏感性的指数衰减、后验存在性检查和 Riccati 收敛结果。PromptControlLab 将这些思想转化为面向 Prompt、checkpoint 和 Agent run 证据的有边界诊断；除非相关假设得到独立验证，否则这些输出仍属于观测证据或有限维 surrogate 证据，而不是关于线上语言模型的定理。
欢迎参与贡献：[中文贡献指南](CONTRIBUTING.zh.md)、[安全策略](SECURITY.md)和 [v0.2.0-alpha.1 发布检查表](docs/release_checklist_v0.2.0-alpha.1.md)。

Apache-2.0。见 [LICENSE](LICENSE)。
