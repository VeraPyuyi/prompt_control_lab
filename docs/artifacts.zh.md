# 产物说明

PromptControlLab 的核心思想是：每次运行都应该留下可复查的文件，而不是只留一个最终分数。

## `manifest.json`

记录这次运行的工具版本、评测模式、方法名、metric、数据路径和 prediction 路径。

说明什么问题：以后看到一个分数时，可以知道它是怎么来的。

## `splits.json`

记录 train、validation、withheld 的样本 id、split hash、seed、数量和 leakage report。

说明什么问题：数据是否被干净隔离，切分是否可以复现。

## `predictions.jsonl`

每一行是一条样本的输出、期望答案、score、slice、method 和错误信息。

说明什么问题：不是只看平均分，而是能回到每条样本检查失败原因。

## `metrics.json`

记录总体样本数、平均分和每个 slice 的平均分。

说明什么问题：新 prompt 是否只在某些 slice 上变好，是否在另一些 slice 上退化。

## `stats.json`

记录 baseline 和 candidate 的 paired comparison，包括 mean delta、bootstrap CI、permutation p-value 和 Holm-adjusted p-value。

说明什么问题：观察到的提升是否可靠，还是样本波动导致的不确定结果。

## `explanation.json`

记录这次运行的直白或技术解释，包括总体结论、证据强度、数据隔离、slice 变化、样本变化、部署风险和下一步建议。

说明什么问题：不用逐个阅读所有 JSON 文件，也能知道这次 prompt 改动说明了什么。

## `gate_result.json`

记录策略阈值判断结果。

说明什么问题：这次运行是 `pass`、`needs_review` 还是 `fail`，以及触发原因是什么。

## `diagnostics/soft_hard.json`

记录 soft prompt 向 nearest token embedding 投影的 token index 和距离。

说明什么问题：soft prompt 转成 hard prompt 的部署风险。

## `diagnostics/trajectory.json`

记录 hidden-state trajectory 的 drift、log-decay slope、fit quality 和 turnpike-like signal。

说明什么问题：prompt 或任务是否让内部轨迹更稳定，还是更漂移。

## `diagnostics/riccati.json`

记录 surrogate 的 closed-loop spectral radius、theory decay rate 和稳定性标签。

说明什么问题：拟合出的有限维控制论 surrogate 是否自洽稳定。

## `diagnostics/tv_soft.json`

记录 static、time-varying、shuffled、random 等方法的均值和相对 baseline 的差异。

说明什么问题：time-varying prompt 的收益是否更像来自时序结构。

## `report.md` / `report.html`

把 split、metrics、stats 和 diagnostics 汇总成可读报告。

说明什么问题：这次 prompt 改动是否值得保留，以及下一步应该检查哪里。
