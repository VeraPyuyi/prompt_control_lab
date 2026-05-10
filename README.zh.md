# PromptControlLab

PromptControlLab 是一个开源工具包，用于 prompt 评测、诊断、复现和控制论分析。

它帮助研究者和工程团队回答这些问题：

- prompt 改动后，效果是否真的变好？
- 结果是否只是验证集过拟合？
- train / val / withheld 是否被干净隔离？
- soft prompt 转成 hard prompt 后风险有多大？
- hidden-state trajectory 是否出现漂移、不稳定或 turnpike-like 信号？
- time-varying prompt 的收益来自时序结构，还是只是参数更多？

它不是只输出一个分数的表格，而是生成一套可复现的实验产物：数据怎么切、输出怎么评、差异是否可靠、哪些风险需要检查。

## 图示概览

![PromptControlLab 工作流](docs/assets/workflow.svg)

工具的主流程很直接：准备任务池，生成干净的 train/val/withheld 切分，评测 baseline 和 candidate 输出，做 paired statistics，最后生成报告。如果有 soft prompt 或 hidden states，再追加研究诊断。

![PromptControlLab 产物结构](docs/assets/artifacts.svg)

每次运行都会留下一个小型 audit trail。这些文件既方便人阅读，也方便脚本、论文复现和后续工具继续消费。

## 面向谁

- prompt optimization 研究者：需要干净的 train/val/withheld 协议。
- LLM 工程团队：需要本地 prompt regression report。
- soft prompt 研究者：需要 soft-to-hard 部署风险分析。
- 模型迁移和评测团队：需要可复现的 artifact trail。
- 研究 hidden-state trajectory、turnpike-like 行为和 Riccati surrogate 的研究者。

## 安装

```bash
pip install -e ".[dev,research]"
```

使用 uv：

```bash
uv pip install -e ".[dev,research]"
```

核心命令只依赖 Python 标准库。`soft-hard`、`trajectory`、`riccati` 等研究诊断命令使用可选科学计算依赖。

## 快速开始

生成示例项目：

```bash
pcl init --path demo
cd demo
```

你会得到示例任务、baseline 输出、candidate 输出和一个配置说明。它说明这个工具需要什么输入格式。

生成可复现的 train/val/withheld 切分：

```bash
pcl split --data examples/tasks.jsonl --out runs/candidate --seed 0
```

你会得到 `runs/candidate/splits.json`。里面的 split hash 和 leakage report 说明数据切分是否可复现，以及 train/val/withheld 是否有交叉泄漏。

评测 baseline 和 candidate：

```bash
pcl eval --data examples/tasks.jsonl `
  --predictions examples/predictions_baseline.jsonl `
  --out runs/baseline `
  --metric exact_match `
  --method baseline

pcl eval --data examples/tasks.jsonl `
  --predictions examples/predictions_candidate.jsonl `
  --out runs/candidate `
  --metric exact_match `
  --method candidate
```

你会得到每个 run 的 `predictions.jsonl` 和 `metrics.json`。它们说明每条样本答得如何、每个任务 slice 表现如何、总体分数是多少。

比较 candidate 是否真的比 baseline 好：

```bash
pcl stats --baseline runs/baseline/predictions.jsonl `
  --candidate runs/candidate/predictions.jsonl `
  --out runs/candidate/stats.json
```

你会得到置信区间、paired permutation p-value 和 Holm-adjusted p-value。它们说明新 prompt 的提升是否可靠，还是样本波动导致的不确定结果。

生成报告：

```bash
pcl report --run runs/candidate --title "Candidate Prompt Report"
```

你会得到 `report.md` 和 `report.html`。报告会说明这次 prompt 改动表现如何、统计结果意味着什么、下一步应该检查哪里。

## 研究诊断命令

![PromptControlLab 研究诊断](docs/assets/diagnostics.svg)

soft prompt 到 hard prompt 的风险：

```bash
pcl soft-hard --soft soft_prompt.npz --vocab vocab_embeddings.npz --out runs/candidate/diagnostics
```

它会输出 nearest-token projection distance。距离越大，说明 soft prompt 学到的向量越不像真实 token embedding，转成 hard prompt 后越可能丢失行为。

hidden-state trajectory 诊断：

```bash
pcl trajectory --states hidden_states.npz --out runs/candidate/diagnostics
```

它会输出 step drift、log-decay slope 和拟合质量。如果 slope 为负且拟合质量较好，说明轨迹可能向某个稳定区域靠近；如果拟合弱或 drift 高，说明行为可能更异质或不稳定。

Riccati surrogate 诊断：

```bash
pcl riccati --trajectory hidden_states.npz --out runs/candidate/diagnostics
```

它会构造有限维 surrogate 并检查 closed-loop spectral radius。这个结果只说明 surrogate 是否自洽稳定，不是对完整语言模型的数学证明。

time-varying soft-control lane：

```bash
pcl tv-soft --predictions scored_methods.jsonl --out runs/candidate/diagnostics
```

它会比较 `static`、`time_varying`、`shuffled_tv`、`random_tv` 等方法，帮助判断收益来自时序结构，还是只是参数容量或选择效应。

## 文档

- [使用背景](docs/background.zh.md)
- [面向群体](docs/users.zh.md)
- [一步一步教程](docs/tutorial.zh.md)
- [产物说明](docs/artifacts.zh.md)
- [创新点和贡献](docs/innovation.zh.md)

## License

Apache-2.0。
