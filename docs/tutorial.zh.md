# 一步一步教程

本教程采用“怎么操作 -> 得到什么结果 -> 能说明什么问题”的格式。

## 1. 初始化示例

操作：

```bash
pcl init --path demo
cd demo
```

得到：

- `examples/tasks.jsonl`
- `examples/predictions_baseline.jsonl`
- `examples/predictions_candidate.jsonl`
- `promptcontrol.example.yaml`

说明：

这些文件展示了工具需要的最小输入：任务 id、输入、期望答案、任务 slice，以及不同 prompt 或方法的输出。

## 2. 生成 train/val/withheld 切分

操作：

```bash
pcl split --data examples/tasks.jsonl --out runs/candidate --seed 0
```

得到：

- `runs/candidate/splits.json`

说明：

`splits.json` 里的 split hash 用来复现同一次切分。leakage report 用来检查 train、validation、withheld 是否发生样本交叉。如果有交叉，评测结果不可信。

## 3. 评测 baseline 和 candidate

操作：

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

得到：

- `runs/baseline/predictions.jsonl`
- `runs/baseline/metrics.json`
- `runs/candidate/predictions.jsonl`
- `runs/candidate/metrics.json`

说明：

`predictions.jsonl` 说明每条样本输出了什么、得分是多少、是否缺失输出。`metrics.json` 说明总体平均分和每个 slice 的平均分。slice 分数能发现“平均分变好但某类任务变差”的情况。

## 4. 做统计比较

操作：

```bash
pcl stats --baseline runs/baseline/predictions.jsonl `
  --candidate runs/candidate/predictions.jsonl `
  --out runs/candidate/stats.json
```

得到：

- `runs/candidate/stats.json`

说明：

这个文件包含 mean delta、bootstrap confidence interval、paired permutation p-value 和 Holm-adjusted p-value。如果置信区间跨过 0，说明提升仍然不稳定。如果 adjusted p-value 很小且区间不跨 0，说明 candidate 的提升更可靠。

## 5. 生成报告

操作：

```bash
pcl report --run runs/candidate --title "Candidate Prompt Report"
```

得到：

- `runs/candidate/report.md`
- `runs/candidate/report.html`

说明：

报告把 split、metrics、stats 和 diagnostics 汇总到一起，适合放进实验记录、评审材料或 prompt 变更记录。

## 6. 检查 soft-to-hard 风险

操作：

```bash
pcl soft-hard --soft soft_prompt.npz --vocab vocab_embeddings.npz --out runs/candidate/diagnostics
```

得到：

- `runs/candidate/diagnostics/soft_hard.json`

说明：

projection distance 越大，说明 soft prompt 向量越不像真实 token embedding。风险高时，soft prompt 训练分数不能直接说明 hard prompt 部署会成功。

## 7. 检查 hidden-state trajectory

操作：

```bash
pcl trajectory --states hidden_states.npz --out runs/candidate/diagnostics
```

得到：

- `runs/candidate/diagnostics/trajectory.json`

说明：

mean step drift 说明轨迹每步变化强度。log-decay slope 为负且 R2 较高时，说明轨迹可能向稳定区域靠近。drift 高或拟合弱时，说明任务或 prompt 可能导致更异质的内部行为。

## 8. 做 Riccati surrogate 诊断

操作：

```bash
pcl riccati --trajectory hidden_states.npz --out runs/candidate/diagnostics
```

得到：

- `runs/candidate/diagnostics/riccati.json`

说明：

closed-loop spectral radius 小于 1 时，说明拟合出来的有限维 surrogate 在这个诊断中是稳定的。它只是对 surrogate 的检查，不是对完整语言模型的证明。

## 9. 比较 time-varying soft-control lane

操作：

```bash
pcl tv-soft --predictions scored_methods.jsonl --out runs/candidate/diagnostics
```

得到：

- `runs/candidate/diagnostics/tv_soft.json`

说明：

如果 `time_varying` 明显优于 `static`，但 `shuffled_tv` 和 `random_tv` 没有同样提升，收益更可能来自时序结构。如果 shuffled/random 也提升，应该检查参数容量和选择效应。

