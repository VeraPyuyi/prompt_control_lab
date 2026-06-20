# 我应该先用哪个工具？

`prompt_control_lab` 不应该替代 Promptfoo、LangSmith、Langfuse、DeepEval 或
prompt-optimizer。它更适合接在这些工具之后，把已有结果整理成 prompt 优化的可审查证据。

一句话判断：**创建、trace、测试和安全扫描交给相邻工具；需要证明“这个结果到底支持什么”时，用 PCL。**

## 30 秒选择地图

| 你的起点 | 先用 | 什么时候加入 PCL |
|---|---|---|
| 你需要评测矩阵、CI 检查、红队或安全测试。 | Promptfoo | 需要成对不确定性、prompt-only 有效性、claim 边界和论文诊断时。 |
| 你想用 Pytest 风格写 LLM 单元测试，或者直接使用大量现成指标。 | DeepEval | 需要围绕这些测试结果补 prompt / model / split provenance、成对不确定性和 claim check 时。 |
| 你需要 trace、agent debug、dataset 或 LangChain/LangGraph 观测。 | LangSmith | 需要把导出结果变成可复现证据包，并区分 prompt、模型、指标和切分变化时。 |
| 你需要开源 tracing、prompt 管理、eval、成本追踪或自托管。 | Langfuse | 需要补 soft-hard gap、trajectory、Riccati、tv-soft 诊断和有边界的研究结论时。 |
| 你想要好用的 prompt 写作和改写界面。 | prompt-optimizer | 需要证明优化后的 prompt 在干净协议下真的更好时。 |
| 你已经有 baseline / candidate 输出。 | PCL | 需要 evidence card、claim check、gap status、模型溯源和 research bundle 验证时。 |

## 复制即用路径

先让工具直接给出建议：

```bash
pcl choose --need prompt-writing --language zh
pcl choose --need "安全评测和红队检查" --language zh --json
```

把选择理由保存成审查材料：

```bash
pcl choose --need "安全评测和红队检查" --language zh --out runs/tool-choice.json
pcl start --choice choose --need "安全评测和红队检查" --language zh --out runs/tool-choice.json
```

这会写出 `runs/tool-choice.json` 和 `runs/tool-choice.md`。

本地 UI 的 **Research Overview / 研究总览** 里也有同一个选择器。

## 从市场缺口到 PCL 命令

| 你已经从其他工具得到什么 | 还缺什么证据 | 下一步运行 | 先打开 |
|---|---|---|---|
| Promptfoo eval 或红队导出 | 有分数，但成对不确定性和 prompt-only 有效性还不清楚。 | `pcl evidence-audit --tool promptfoo ... --out runs/from-promptfoo-audit` | `evidence_audit_result.html` |
| DeepEval TestRun 输出 | 有指标，但 prompt/model/split provenance 和 claim 边界还需要审查。 | `pcl import deepeval --input test-run.json --out runs/from-deepeval` | `manifest.json`，再运行 `pcl evidence-card` |
| LangSmith / Langfuse trace 或 eval 导出 | 有 trace，但 prompt 效果可能和模型、指标、切分变化混在一起。 | `pcl start --choice import --tool auto --input results.json --out runs/from-external` | `bridge_summary.html` |
| prompt-optimizer 收藏或模板 | 有更好的 prompt 候选，但还不是成对打分证据。 | `pcl import prompt-optimizer --input favorites.json --out runs/from-prompt-optimizer` | `prompt_optimizer_gap_plan.html` |
| 任意 baseline / candidate run | 还不清楚当前证据最多能支持什么主张。 | `pcl claim-check --run runs/<run>` | `claim_check.html` |

生成生态对比 scorecard 和 market readiness 摘要：

```bash
pcl start --choice ecosystem --out runs/ecosystem-demo
```

导入一个外部 run：

```bash
pcl start --choice import --tool auto --input results.json --out runs/from-external
```

审计成对外部证据：

```bash
pcl evidence-audit \
  --tool promptfoo \
  --baseline-input baseline.json \
  --candidate-input candidate.json \
  --baseline-prompt-id baseline \
  --candidate-prompt-id candidate \
  --out runs/from-promptfoo-audit
```

把 prompt-optimizer 资产推进到可评分协议：

```bash
pcl import prompt-optimizer --input favorites.json --out runs/from-prompt-optimizer
pcl scaffold-check --run runs/from-prompt-optimizer
```

## 最实用的判断规则

用相邻工具做创建、trace 或大规模评测。有人问下面这些问题时，用 PCL：

- 这是干净的 prompt-only 对比吗？
- 模型、切分、指标或 prompt identity 变了吗？
- candidate 的提升在成对不确定性下可靠吗？
- 当前证据最多能安全支持什么 claim？
- 还缺哪些论文里的诊断证据？

如果你只是想要更好看的 prompt 编辑器、托管 trace dashboard，或者大型红队攻击库，不要先用 PCL。
那些是相邻工具的强项。PCL 的职责是把证据整理到足够可信。

定位来源：[Promptfoo intro](https://www.promptfoo.dev/docs/intro/)、
[Promptfoo CI/CD](https://www.promptfoo.dev/docs/integrations/ci-cd/)、
[DeepEval introduction](https://deepeval.com/docs/introduction)、
[LangSmith observability](https://www.langchain.com/langsmith/observability)、
[Langfuse docs](https://langfuse.com/docs)、
[Langfuse prompt management](https://langfuse.com/docs/prompt-management/overview)、
[linshenkx/prompt-optimizer README](https://github.com/linshenkx/prompt-optimizer)。
