# 与 Promptfoo、LangSmith、Langfuse 的对比

这份文档说明 `prompt_control_lab` 应该在哪里竞争，在哪里集成。

一句话版本：PCL 不应该做另一个大而全的 LLMOps 平台。它最强的位置是
**prompt optimization 的研究证据层**。

## 定位对比

| 工具 | 强项 | PCL 不应该硬拼 | PCL 可以补上的东西 |
|---|---|---|---|
| Promptfoo | LLM 评测、红队/安全测试、guardrails、provider 覆盖、CI 和安全报告。 | 红队插件数量、provider 矩阵深度、企业安全 dashboard。 | 导入 Promptfoo 结果后，补上成对不确定性、prompt-only 有效性、evidence card、claim check、论文诊断缺口闭环和可验证研究证据包。 |
| LangSmith | Agent trace、在线/离线评测、Prompt Hub/Playground、监控、部署、sandbox、人工标注流程。 | LangChain/LangGraph 原生 trace UI、部署基础设施、sandbox runtime、标注队列产品。 | 把 experiment export 转成 prompt optimization 证据包，区分 prompt 效果和 model、metric、split、统计显著性等混杂因素。 |
| Langfuse | 开源 observability、prompt management、evaluation、成本跟踪、SDK/OpenTelemetry/LiteLLM 集成、自托管。 | 通用 tracing、prompt registry、成本 dashboard、RBAC、托管观测平台。 | 补上 observability 工具通常不覆盖的研究诊断：soft-hard 部署 gap、hidden-state trajectory、Riccati surrogate、time-varying control evidence 和 claim 支持边界。 |

当前产品定位和定价来源：
[Promptfoo pricing](https://www.promptfoo.dev/pricing)、
[LangSmith pricing](https://www.langchain.com/pricing)、
[Langfuse pricing](https://langfuse.com/pricing)。

## 最值得押注的切口

PCL 应该成为评测或观测工具产出 evidence 之后运行的工具：

```bash
pcl evidence-audit \
  --tool promptfoo \
  --baseline-input results.json \
  --candidate-input results.json \
  --baseline-prompt-id baseline \
  --candidate-prompt-id candidate \
  --provider openai:gpt-4o-mini-20260601 \
  --split-hash eval-split-2026-06 \
  --out runs/from-promptfoo-audit
```

这条命令会导入外部导出结果，生成成对统计，检查比较是否真的是 prompt-only，
写出 evidence card，检查当前证据能支持的 claim，报告还缺哪些论文诊断，并验证
浏览器优先的 research bundle 哈希。

## 用户应该从 PCL 得到什么答案

PCL 应该回答大多数 eval / observability 工具不会直接回答的问题：

- baseline / candidate 是否按同一批样本成对比较？
- model、provider、metric、split 或 prompt identity 有没有变化？
- candidate 的提升在成对不确定性下是否可靠？
- 当前证据最多能支持哪一层 prompt optimization claim？
- 在声称完整研究结果之前，还缺哪些论文诊断？
- 分享出去的 research evidence bundle 之后有没有被改过？

## 产品含义

1. 把 `research-demo`、`diagnose`、`evidence-audit`、`claim-check`、`gap-status` 和
   `research-bundle --verify` 保持为一等入口。
2. 把 `guard`、`audit-diff` 和 PR 工具视为工程应用层，而不是项目主身份。
3. 优先增强真实 Promptfoo、LangSmith、Langfuse 导出的导入能力，而不是重造它们的平台。
4. 把 reviewer-facing HTML artifact 做成主要体验：`evidence_audit_result.html`、
   `bridge_summary.html`、`research_bundle.html`、`evidence_card.html`、
   `claim_check.html`、`research_gap_status.html` 和
   `research_bundle_verification.html`。
5. 用浅显语言解释研究术语：部署 gap、内部轨迹稳定性、surrogate 稳定性、
   time-varying evidence 和 claim 边界。

## 边界

这份对比不是说 PCL 比这些工具更大或更成熟。恰恰相反，PCL 应该有意保持更窄：
成为 prompt optimization 研究和复现里最有用的开源证据层。
