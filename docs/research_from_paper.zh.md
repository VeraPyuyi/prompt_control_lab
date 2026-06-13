# 论文功能映射

`prompt_control_lab` 的主线来自 Prompt-Engineering-Optimal-Control 的研究框架。
Agent guard 和 audit 很有用，但它们是应用层；项目的研究内核是下面这套诊断栈。

## 概念到命令的对应关系

| 论文概念 | 命令 | 主要输出 | 解释边界 |
|---|---|---|---|
| 一键研究流程 | `pcl research-demo`、`pcl diagnose` | `research_diagnostics.json`、`research_diagnostics.md` | 运行 synthetic fixtures 或用户自己的 artifacts；demo 结果不是 benchmark。 |
| 三段切分 withheld protocol | `pcl split`、`pcl analyze` | `splits.json`、`manifest.json` | 检查协议是否干净；不保证小任务池天然具有代表性。 |
| 成对统计比较 | `pcl stats` | `stats.json` | 报告 mean delta、bootstrap CI、permutation p-value 和 Holm-adjusted p-value。 |
| prompt-only 比较有效性 | `pcl validity` | `comparison_validity.json`、`comparison_validity.md` | 检查 baseline / candidate 结果是否被模型、切分、指标或缺失 prompt identity 混淆。 |
| prompt 优化证据卡 | `pcl evidence-card` | `evidence_card.json`、`evidence_card.md` | 把协议、统计、有效性、部署风险、trajectory、Riccati 和 time-varying 证据汇总成一份可审查 artifact。 |
| prompt 优化主张检查 | `pcl claim-check` | `claim_check.json`、`claim_check.md` | 检查当前 artifact bundle 是否足以支持 paired、partial-research 或 full-research 层级的主张。 |
| 软转硬 soft-to-hard projection gap | `pcl soft-hard` | `diagnostics/soft_hard.json` | 衡量 nearest-token projection 风险；不是 hard prompt 最优性证明。 |
| HuggingFace hidden-state 提取 | `pcl extract-hidden` | `hidden_states.npz`、`hidden_states.npz.metadata.json` | 从开源或本地 HuggingFace 模型生成 trajectory 可直接读取的 hidden states。 |
| hidden-state trajectory | `pcl trajectory` | `diagnostics/trajectory.json` | 报告 drift、log-decay slope、fit quality 和 turnpike-like signal。 |
| Riccati surrogate | `pcl riccati` | `diagnostics/riccati.json` | 检查拟合出的有限维 surrogate，不证明完整语言模型稳定。 |
| time-varying soft-control lane | `pcl tv-soft` | `diagnostics/tv_soft.json` | 比较 static、time-varying、shuffled 和 random control lane。 |

## 1. 一键体验论文诊断流程

如果你想先体验论文诊断流程，而不是立刻准备自己的模型 artifact，可以运行：

```bash
pcl research-demo --out runs/research-demo
pcl diagnose --run runs/research-demo
```

这个命令会在 `runs/research-demo/inputs` 下写出 synthetic soft prompt vectors、
vocabulary embeddings、hidden-state trajectories、Riccati matrices 和 method predictions。
它还会生成小型 synthetic `tasks.jsonl`、baseline / candidate scored runs、`splits.json`、
`stats.json`、`comparison_validity.json`、`evidence_card.json` 和 `evidence_card.md`。
它用于学习流程和 artifact 关系，不是 benchmark 结果。

## 2. 三段切分 withheld protocol

论文强调 optimization data、selection data 和 withheld evaluation 的干净隔离。
工具把这个协议变成显式 artifact：

```bash
pcl split --data examples/tasks.jsonl --out runs/candidate --seed 0
pcl analyze --config promptcontrol.example.yaml --out runs/quick
```

用户可以用 split hash 和 leakage report 检查 train、validation、withheld id 是否重叠。
这能减少 validation overfitting 和 test leakage。

## 3. 成对统计

prompt 改动不应该只看一次平均分：

```bash
pcl stats \
  --baseline runs/baseline/predictions.jsonl \
  --candidate runs/candidate/predictions.jsonl \
  --out runs/candidate/stats.json
```

输出会记录 paired mean delta、bootstrap confidence interval、permutation p-value 和
Holm-adjusted p-value。如果置信区间跨过 0，即使 candidate 平均分更高，证据也仍然偏弱。

## 4. prompt-only 比较有效性

candidate 分数更高还不够。如果模型、数据切分、指标或 prompt identity 同时变了，
这次结果就不能被干净地解释成 prompt 改动带来的提升。`validity` 命令会把这个问题
变成一份可审计 artifact：

```bash
pcl validity \
  --baseline runs/baseline \
  --candidate runs/candidate \
  --out runs/candidate/comparison_validity.json
```

它会写出 `comparison_validity.json` 和 `comparison_validity.md`。`clean` 表示当前 artifacts
支持 prompt-only 比较；`invalid` 表示发现了模型、切分或指标不一致等阻断问题；
`needs_review` 表示证据有用但还不完整，需要补充 prompt identity、split hash 或统计结果。

如果使用 Quick Mode 做 baseline / candidate 两个 prompt 的 A/B 对比，可以直接记录两侧
prompt identity：

```bash
pcl analyze \
  --data examples/tasks.jsonl \
  --baseline-predictions examples/baseline.jsonl \
  --candidate-predictions examples/candidate.jsonl \
  --baseline-prompt-file prompts/baseline.txt \
  --candidate-prompt-file prompts/candidate.txt \
  --baseline-model claude-sonnet-4-20250514 \
  --candidate-model claude-sonnet-4-20250514 \
  --out runs/quick
```

这样会把两份 prompt 的 hash 分别写入 `runs/quick/baseline/manifest.json` 和
`runs/quick/candidate/manifest.json`。之后 `comparison_validity.json` 就可以判断这次结果
是否真的支持 prompt-only 比较。

## 5. prompt 优化证据卡

当一个 comparison run 已经包含统计、比较有效性和可用的研究诊断后，可以把证据链压缩成一张卡片：

```bash
pcl evidence-card --run runs/candidate --out runs/candidate/evidence_card.md
```

证据卡会给出有边界的推荐：`supported`、`needs_review`、`not_supported` 或
`insufficient_evidence`。它的用途是让证据更容易审查，而不是声称找到了全局最优 prompt。

证据卡还会给出 evidence tier。`tier_2_paired_comparison` 表示分数比较已经成对且可审计，但还不是完整论文诊断结论。`tier_4_full_research_diagnostics` 表示 artifact bundle 同时包含 soft-hard、trajectory、Riccati 和 time-varying 等论文诊断。

## 6. 主张检查

当你想知道当前 run 最多能安全声称什么时，运行：

```bash
pcl claim-check --run runs/candidate --claim paired
pcl claim-check --run runs/candidate --claim full-research --out runs/candidate/claim_check.json
```

这个命令会读取 evidence tier，并回答一个很直接的问题：当前 artifact 是否支持你要求的 claim scope？例如，从 Promptfoo、Langfuse 或 LangSmith 导入的结果可能足以支持 `paired` 层级的成对比较主张，但如果缺少 soft-hard、trajectory、Riccati 和 time-varying 诊断，就不应该被说成 `full-research` 层级的完整 prompt-control 分析。这个失败结果是有价值的：它能阻止把一个小型 eval 导出过度包装成论文级结论。

## 7. soft-to-hard 部署 gap

soft prompt 在优化时可能表现很好，但投影成 hard token 后损失明显。`soft-hard` 诊断用于量化这个风险：

```bash
pcl soft-hard \
  --soft soft_prompt.npz \
  --vocab vocab_embeddings.npz \
  --out runs/candidate/diagnostics
```

它会输出 projection distance 和风险信号。这个结果应该被理解为部署风险诊断，而不是 hard prompt optimizer。

## 8. hidden-state trajectory 诊断

如果你还没有 `hidden_states.npz`，可以先从开源或本地 HuggingFace 模型提取：

```bash
pcl extract-hidden \
  --model Qwen/Qwen2.5-0.5B \
  --prompts examples/tasks.jsonl \
  --out runs/candidate/inputs/hidden_states.npz \
  --pool last-token \
  --max-items 32
```

这个命令会写出包含 `states` 数组的 `hidden_states.npz`，并同时写出
`hidden_states.npz.metadata.json`，记录 model id、prompt 来源、层号、pooling
方式、设备和数组形状。它需要安装可选 HF 依赖：

```bash
pip install -e ".[hf]"
```

之后 trajectory 命令导入 hidden states，并估计漂移和衰减：

```bash
pcl trajectory \
  --states runs/candidate/inputs/hidden_states.npz \
  --out runs/candidate/diagnostics
```

输出包含 mean step drift、log-decay slope、fit quality 和 turnpike-like signal。
如果 log-decay slope 为负且拟合质量尚可，可以说明这条 trace 上存在稳定性风格的信号；
异质任务 trace 可能削弱这种信号。

## 9. Riccati surrogate 诊断

Riccati 命令检查用户提供或从 trajectory 拟合出来的有限维 surrogate：

```bash
pcl riccati --matrices surrogate_mats.npz --out runs/candidate/diagnostics
```

也可以使用：

```bash
pcl riccati \
  --trajectory runs/candidate/inputs/hidden_states.npz \
  --out runs/candidate/diagnostics
```

输出会报告 closed-loop spectral radius，以及这个 surrogate 在诊断里是否稳定。
这个边界必须说清楚：它不证明真实运行的完整语言模型满足这些控制论假设。

## 10. time-varying soft-control lane

time-varying lane 用来比较不同方法组：

```bash
pcl tv-soft --predictions method_predictions.jsonl --out runs/candidate/diagnostics
```

它比较 static、time-varying、shuffled time-varying 和 random controls。
关键问题是：收益更像来自时序结构，还是只是来自更多参数容量。

## 11. 统一 diagnose 命令

如果你已经有自己的 artifacts，可以直接运行统一诊断：

```bash
pcl diagnose \
  --soft soft_prompt.npz \
  --vocab vocab_embeddings.npz \
  --states hidden_states.npz \
  --matrices surrogate_mats.npz \
  --tv-predictions method_predictions.jsonl \
  --out runs/candidate/diagnostics
```

你可以只提供已有的 artifacts。`--soft` 需要配合 `--vocab`；Riccati 会优先使用
`--matrices`，没有 matrices 时也可以从 `--states` 拟合 surrogate。

## 工程应用层

`pcl guard`、`pcl audit-diff`、`pcl model-detect`、GitHub Action 模板和本地 UI
是围绕研究内核做出的应用层。它们帮助 coding-agent 用户保留同样的证据链，
但项目应该首先被理解为面向 prompt optimization 的研究诊断工具。
