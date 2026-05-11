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

记录这次运行的直白或技术解释，包括总体结论、证据强度、数据隔离、slice 变化、样本变化、部署风险、下一步建议、`plain_summary` 和 `deployment_recommendation`。

说明什么问题：不用逐个阅读所有 JSON 文件，也能知道这次 prompt 改动说明了什么。

## `gate_result.json`

记录策略阈值判断结果。

说明什么问题：这次运行是 `pass`、`needs_review` 还是 `fail`，以及触发原因是什么。它也会包含 `plain_summary`，方便插件和报告直接展示直白结论。

## `pcl guard --json` 输出

记录 hook、rules 或 shell wrapper 使用的输入层 prompt 守护结果。

重要字段：

- `plain_summary`：给普通用户看的直白建议，例如“补充目标文件和验收标准”
- `action`：`suggest`、`auto` 或 `block`
- `risk_level`：`low`、`medium` 或 `high`
- `improved_prompt`：建议继续发送给 AI 工具的守护版 prompt

说明什么问题：这条 prompt 是否已经足够清楚，发送前还应该补什么。

## `improved_prompt.txt`

记录 `pcl improve` 生成的优化 prompt。

说明什么问题：工具推荐用户使用哪一个更直白、更稳定的 prompt。

## `prompt_improvement.json`

记录原始 prompt、优化 prompt、识别语言、优化目标、风格、改写原因和报告上下文提示。它还包含 `token_report`，用不依赖外部 tokenizer 的方式估算原始 prompt 和优化 prompt 的 token 数、token 模式、可选预算以及是否满足预算。

说明什么问题：工具为什么这样改 prompt，是否使用了已有诊断报告，以及这次改写对估算 prompt token 成本有什么影响。`plain_summary` 会用一句直白的话解释结果，方便插件或简单 wrapper 直接展示给普通用户。

## `prompt_diff.md`

记录原始 prompt、优化 prompt、可读的改动列表和 estimated token 成本。

说明什么问题：不用看 JSON，也能知道 prompt 具体改了什么。

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
