# 与 Promptfoo、DeepEval、LangSmith、Langfuse 和 Prompt Optimizer 的对比

这份文档说明 `prompt_control_lab` 应该在哪里竞争，在哪里集成。

一句话版本：PCL 不应该做另一个大而全的 LLMOps 平台。它最强的位置是
**prompt optimization 的研究证据层**。

更直白地说：其他工具产出 prompt、trace、测试或安全结果；PCL 负责把这些结果整理成更干净、更可审查的证据。

## 30 秒选择指南

| 用户想要什么 | 先用什么 | 什么时候加 PCL |
|---|---|---|
| 安全测试、红队用例、provider 评测矩阵 | Promptfoo | 结果还需要成对不确定性、prompt-only 有效性、claim 边界或论文诊断证据。 |
| Pytest 风格 LLM 单元测试，以及大量现成指标 | DeepEval | 测试结果还需要 prompt / model / split provenance、成对不确定性或 claim 边界审查。 |
| 生产 trace、agent debug、标注队列、LangChain/LangGraph 观测 | LangSmith | trace / eval 导出需要变成可复现的 prompt optimization 证据包。 |
| 开源观测、prompt registry、成本跟踪、自托管 LLM monitoring | Langfuse | observability 还需要 soft-hard gap、hidden trajectory、Riccati 或 time-varying control 诊断。 |
| 更顺手地改写 prompt、管理 prompt 资产 | prompt-optimizer | 优化后的 prompt 需要在部署或论文声称前证明“真的变好”。 |
| 回答“我最多能安全声称什么？” | PCL | 这是 PCL 的中心：evidence card、claim check、gap status、provenance 和 research bundle。 |

## 定位对比

| 工具 | 强项 | PCL 不应该硬拼 | PCL 可以补上的东西 |
|---|---|---|---|
| Promptfoo | LLM 评测、红队/安全测试、guardrails、provider 覆盖、CI 和安全报告。 | 红队插件数量、provider 矩阵深度、企业安全 dashboard。 | 导入 Promptfoo 结果后，补上成对不确定性、prompt-only 有效性、evidence card、claim check、论文诊断缺口闭环和可验证研究证据包。 |
| DeepEval | Pytest 风格 LLM 单元测试、丰富内置指标、合成数据、组件/端到端评测和本地 CI 工作流。 | 指标目录广度、LLM-as-judge 框架、合成数据流程、单元测试开发者体验。 | 给 DeepEval 风格结果加证据层：prompt identity、model identity、split hash、成对不确定性、evidence card 和论文诊断缺口状态。 |
| LangSmith | Agent trace、在线/离线评测、Prompt Hub/Playground、监控、部署、sandbox、人工标注流程。 | LangChain/LangGraph 原生 trace UI、部署基础设施、sandbox runtime、标注队列产品。 | 把 experiment export 转成 prompt optimization 证据包，区分 prompt 效果和 model、metric、split、统计显著性等混杂因素。 |
| Langfuse | 开源 observability、prompt management、evaluation、成本跟踪、SDK/OpenTelemetry/LiteLLM 集成、自托管。 | 通用 tracing、prompt registry、成本 dashboard、RBAC、托管观测平台。 | 补上 observability 工具通常不覆盖的研究诊断：soft-hard 部署 gap、hidden-state trajectory、Riccati surrogate、time-varying control evidence 和 claim 支持边界。 |
| linshenkx/prompt-optimizer | 面向普通用户的 prompt 改写产品，覆盖 Web、桌面端、Chrome 扩展、Docker、MCP、多模型、Prompt Garden、收藏、图像生成模式和交互式测试。 | 成熟 prompt 编辑器体验、prompt 资产管理、浏览器/桌面分发、prompt marketplace/garden、模型调用应用和通用一键 prompt 改写。 | 验证优化后的 prompt 是否真的可靠：tri-split 协议、prompt-only 比较有效性、成对不确定性、claim 边界、soft-hard 部署 gap、trajectory/Riccati/tv-soft 诊断，以及 reviewer-facing 证据包。 |

当前定位和相关定价来源：
[Promptfoo intro](https://www.promptfoo.dev/docs/intro/)、
[Promptfoo CI/CD docs](https://www.promptfoo.dev/docs/integrations/ci-cd/)、
[Promptfoo pricing](https://www.promptfoo.dev/pricing)、
[DeepEval introduction](https://deepeval.com/docs/introduction)、
[DeepEval quickstart](https://deepeval.com/docs/getting-started)、
[LangSmith observability](https://www.langchain.com/langsmith/observability)、
[LangSmith pricing](https://www.langchain.com/pricing)、
[Langfuse docs](https://langfuse.com/docs)、
[Langfuse pricing](https://langfuse.com/pricing)、
[linshenkx/prompt-optimizer README](https://github.com/linshenkx/prompt-optimizer)。

## 与 linshenkx/prompt-optimizer 的具体区别

`linshenkx/prompt-optimizer` 更像一个成熟的通用 prompt 写作和优化产品。它有更完整的用户界面和分发路径：Web app、桌面端、Chrome 扩展、Docker、MCP server、多模型设置、Prompt Garden 导入、智能收藏、图像生成模式、变量测试和多轮 prompt 测试。

PCL 不应该靠“我也能一键改 prompt”去和它正面竞争。那会让 PCL 变成一个更小、更不成熟的 prompt editor。

PCL 更应该赢在更窄但更有壁垒的位置：

| 用户真正想问的问题 | prompt-optimizer 更适合 | PCL 更适合 |
|---|---|---|
| “帮我把这句 prompt 改得更好用。” | 是。它就是为交互式 prompt 改写和 prompt 资产管理设计的。 | PCL 有 `pcl improve`，但这是轻量入口，不是项目中心。 |
| “新 prompt 是否在干净协议下真的变好？” | 它有 analysis 和 compare evaluation，但产品中心仍然是 prompt optimization。 | PCL 把这件事放在中心：tri-split、成对统计、prompt-only 有效性、split/model/prompt provenance。 |
| “我最多能从这个结果声称什么？” | 不是它的主线。 | `pcl claim-check` 和 `pcl evidence-card` 会收束可支持的主张。 |
| “soft prompt 转 hard prompt 后风险多大？” | 不是它的主线。 | `pcl soft-hard` 报告 projection gap 和部署风险。 |
| “hidden-state trajectory 是否漂移？” | 不是它的主线。 | `pcl extract-hidden` 和 `pcl trajectory` 生成内部轨迹诊断。 |
| “拟合出的控制 surrogate 是否稳定？” | 不是它的主线。 | `pcl riccati` 报告 Riccati / DARE surrogate 诊断。 |
| “time-varying prompt 的收益来自时序结构吗？” | 不是它的主线。 | `pcl tv-soft` 比较 static、time-varying、shuffled 和 random lanes。 |

实际传播时可以这样说：

> 想写出更好的 prompt，用 prompt-optimizer。想证明 prompt optimization 结果是否可复现、可部署、不过度声称，用 PCL。

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

如果只想导入一个外部 run，可以用更直白的 import 入口：

```bash
pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate
pcl import langfuse --input langfuse-export.json --out runs/from-langfuse --name candidate
pcl import langsmith --input langsmith-runs.csv --out runs/from-langsmith --experiment candidate
pcl import prompt-optimizer --input favorites.json --out runs/from-prompt-optimizer
```

`pcl ingest ...` 仍然作为兼容旧脚本的别名保留。

对 prompt-optimizer 来说，这个导入是 **prompt 资产桥接**，不是已经打分的 evidence
bridge。它会写出 `prompt_assets.json/html` 和 `prompt_optimizer_gap_plan.json/html`，
记录 prompt 内容哈希，并说明在声称“优化有效”之前还缺哪些 eval 证据。只有后续用户用成对
评测协议给这些 prompt 打分后，才会产生 `predictions.jsonl` 或 `metrics.json`。

## 不重造竞品，也能超过它们的方式

1. **把证据来源做得更严谨。** 外部工具可以给出分数和 trace；PCL 应该保存原始 source
   文件、source hash、resolved path、导入筛选条件和生成后的 bundle hash。
2. **把 prompt-only 有效性显式化。** 每次比较都应该说明 model、provider、metric、split、
   prompt identity 或 source 文件有没有变化；如果变了，就标记为 confounded，而不是只展示
   “candidate 分数更高”。
3. **把论文诊断变成 checklist。** `gap-status` 和 `evidence-audit` 应该告诉用户还缺哪些诊断：
   soft-hard gap、hidden-state trajectory、Riccati surrogate、time-varying control evidence。
4. **自动收窄可声明的结论。** `claim-check` 应该防止用户在只有成对比较或外部导入不完整证据时，
   直接声称完整研究结果。
5. **保持本地、可组合。** 最容易被采用的路线不是托管大平台，而是一个可以接在
   Promptfoo、Langfuse、LangSmith、DeepEval、notebook 或自定义 eval 脚本后面的本地 Python 工具。

## 用户应该从 PCL 得到什么答案

PCL 应该回答大多数 eval / observability 工具不会直接回答的问题：

- baseline / candidate 是否按同一批样本成对比较？
- model、provider、metric、split 或 prompt identity 有没有变化？
- 这份证据到底来自哪两个外部导出文件、哪些哈希和哪些导入筛选条件？
- candidate 的提升在成对不确定性下是否可靠？
- 当前证据最多能支持哪一层 prompt optimization claim？
- 在声称完整研究结果之前，还缺哪些论文诊断？
- 分享出去的 research evidence bundle 之后有没有被改过？

## 产品含义

1. 把 `research-demo`、`diagnose`、`evidence-audit`、`claim-check`、`gap-status` 和
   `research-bundle --verify` 保持为一等入口。
2. 把 `guard`、`audit-diff` 和 PR 工具视为工程应用层，而不是项目主身份。
3. 优先增强真实 Promptfoo、LangSmith、Langfuse 导出的导入能力，而不是重造它们的平台。
4. 不要重造 prompt-optimizer 的 prompt 编辑器。`pcl improve` 保持轻量入口，真正让用户留下来的应该是
   `research-demo`、`diagnose` 和证据 artifact。
5. 把 reviewer-facing HTML artifact 做成主要体验：`evidence_audit_result.html`、
   `bridge_summary.html`、`research_bundle.html`、`evidence_card.html`、
   `claim_check.html`、`research_gap_status.html` 和
   `research_bundle_verification.html`。
6. 用浅显语言解释研究术语：部署 gap、内部轨迹稳定性、surrogate 稳定性、
   time-varying evidence 和 claim 边界。

## 边界

这份对比不是说 PCL 比这些工具更大或更成熟。恰恰相反，PCL 应该有意保持更窄：
成为 prompt optimization 研究和复现里最有用的开源证据层。
