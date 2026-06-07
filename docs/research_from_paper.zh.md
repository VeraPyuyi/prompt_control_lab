# 论文功能映射

`prompt_control_lab` 的主线来自 Prompt-Engineering-Optimal-Control 的研究框架。
Agent guard 和 audit 很有用，但它们是应用层；项目的研究内核是下面这套诊断栈。

## 概念到命令的对应关系

| 论文概念 | 命令 | 主要输出 | 解释边界 |
|---|---|---|---|
| 一键研究流程 | `pcl research-demo`、`pcl diagnose` | `research_diagnostics.json`、`research_diagnostics.md` | 运行 synthetic fixtures 或用户自己的 artifacts；demo 结果不是 benchmark。 |
| 三段切分 withheld protocol | `pcl split`、`pcl analyze` | `splits.json`、`manifest.json` | 检查协议是否干净；不保证小任务池天然具有代表性。 |
| 成对统计比较 | `pcl stats` | `stats.json` | 报告 mean delta、bootstrap CI、permutation p-value 和 Holm-adjusted p-value。 |
| 软转硬 soft-to-hard projection gap | `pcl soft-hard` | `diagnostics/soft_hard.json` | 衡量 nearest-token projection 风险；不是 hard prompt 最优性证明。 |
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
vocabulary embeddings、hidden-state trajectories、Riccati matrices 和 method predictions，
然后生成 `research_diagnostics.json` 和 `research_diagnostics.md`。它用于学习流程，
不是 benchmark 结果。

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

## 4. soft-to-hard 部署 gap

soft prompt 在优化时可能表现很好，但投影成 hard token 后损失明显。`soft-hard` 诊断用于量化这个风险：

```bash
pcl soft-hard \
  --soft soft_prompt.npz \
  --vocab vocab_embeddings.npz \
  --out runs/candidate/diagnostics
```

它会输出 projection distance 和风险信号。这个结果应该被理解为部署风险诊断，而不是 hard prompt optimizer。

## 5. hidden-state trajectory 诊断

trajectory 命令导入 hidden states，并估计漂移和衰减：

```bash
pcl trajectory --states hidden_states.npz --out runs/candidate/diagnostics
```

输出包含 mean step drift、log-decay slope、fit quality 和 turnpike-like signal。
如果 log-decay slope 为负且拟合质量尚可，可以说明这条 trace 上存在稳定性风格的信号；
异质任务 trace 可能削弱这种信号。

## 6. Riccati surrogate 诊断

Riccati 命令检查用户提供或从 trajectory 拟合出来的有限维 surrogate：

```bash
pcl riccati --matrices surrogate_mats.npz --out runs/candidate/diagnostics
```

也可以使用：

```bash
pcl riccati --trajectory hidden_states.npz --out runs/candidate/diagnostics
```

输出会报告 closed-loop spectral radius，以及这个 surrogate 在诊断里是否稳定。
这个边界必须说清楚：它不证明真实运行的完整语言模型满足这些控制论假设。

## 7. time-varying soft-control lane

time-varying lane 用来比较不同方法组：

```bash
pcl tv-soft --predictions method_predictions.jsonl --out runs/candidate/diagnostics
```

它比较 static、time-varying、shuffled time-varying 和 random controls。
关键问题是：收益更像来自时序结构，还是只是来自更多参数容量。

## 8. 统一 diagnose 命令

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
