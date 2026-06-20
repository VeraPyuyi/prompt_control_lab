# 一步一步教程

本教程采用“怎么操作 -> 得到什么结果 -> 能说明什么问题”的格式。

## 新手模式：选择场景

操作：

```bash
pcl start --guide --language zh
pcl start --language zh
```

得到：

- 一个按目标选择路径的 guide
- 一个三选一菜单：优化 prompt、守护 prompt、生成报告
- 当前场景的直白输出

说明：如果你不确定自己应该走研究 demo、证据桥接、guard、audit 还是报告路径，先运行
`pcl start --guide --language zh`。如果你还不熟悉 `profile`、`gate` 或 `stats` 这些词，就运行
`pcl start --language zh` 进入交互菜单。

## 快速模式：一个命令生成报告

操作：

```bash
pcl init --path demo
cd demo
pcl analyze --config promptcontrol.example.yaml --out runs/quick
```

得到：

- `runs/quick/splits.json`
- `runs/quick/baseline/metrics.json`
- `runs/quick/candidate/metrics.json`
- `runs/quick/stats.json`
- `runs/quick/explanation.json`
- `runs/quick/report.md`
- `runs/quick/report.html`

说明：这是给非专业人员的最短路径。报告会直接说明 candidate prompt 是否更好、证据是否可靠、哪些样本发生变化、下一步应该检查哪里。

## 最简单的 prompt 优化

操作：

```bash
pcl improve --prompt "回答下面的问题"
```

控制 token 成本的操作：

```bash
pcl improve --prompt "回答下面的问题" --token-mode aggressive --max-tokens 80
```

结合已有检测报告：

```bash
pcl improve --prompt-file prompts/current.txt --run runs/quick --out runs/improve
```

得到：

- 终端输出优化后的 prompt
- `runs/improve/improved_prompt.txt`
- `runs/improve/prompt_improvement.json`
- `runs/improve/prompt_diff.md`
- 终端、JSON 和 Markdown diff 里的 estimated token 数

说明：这个命令会给出一个更清晰的 prompt，包含任务目标、输出格式要求和稳定性要求。结合 `--run` 时，它还会根据已有诊断加入退化 slice、变差样本或部署风险提示。默认 token 模式是 `balanced`：尽量保留关键约束，同时减少不必要措辞。`aggressive` 更短、更省成本，但可能减少一部分保护性规则。`--max-tokens` 是估算预算。

## 给 IDE 和 CLI agent 用的 Prompt Guard

操作：

```bash
pcl guard --prompt "修复这个 bug" --profile coding --token-mode balanced --json
```

适合 hook 的操作：

```bash
echo "修复这个 bug" | pcl guard --stdin --profile coding --json
```

团队策略操作：

```bash
pcl guard --prompt "修复这个 bug" --profile coding --policy examples/guard.policy.yaml --json
```

得到：

- `plain_summary`
- `action`
- `risk_level`
- `improved_prompt`
- `token_report`
- `reasons`
- `risk_categories`
- `policy_violations`
- `required_review`

说明：这个命令是给 prompt 输入层插件用的。Claude Code、Cursor、Codex 或 shell wrapper 在把 prompt 发给模型前，可以先调用它。`plain_summary` 给人看，`action`、`risk_level` 和 `token_report` 给插件稳定读取。`suggest` 返回更稳的 prompt，`auto` 表示可自动使用，`gate` 可以阻断高风险或超过 token 预算的 prompt。加上 `--policy` 后，团队可以配置必填信息、危险模式、风险类别和人工复核阈值。

Policy 文件保持 dependency-free：内置示例使用扁平键，v0.1 也支持少量 `rules:` 嵌套写法，方便习惯 YAML 列表的用户。

## 专家模式：一步一步控制

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
- `examples/guard.policy.yaml`
- `examples/gate.policy.yaml`
- `promptcontrol.example.yaml`

说明：这些文件展示了工具需要的最小输入：任务 id、输入、期望答案、任务 slice，以及不同 prompt 或方法的输出。

## 2. 生成 train/val/withheld 切分

操作：

```bash
pcl split --data examples/tasks.jsonl --out runs/candidate --seed 0
```

得到：

- `runs/candidate/splits.json`

说明：`splits.json` 里的 split hash 用来复现同一次切分。leakage report 用来检查 train、validation、withheld 是否发生样本交叉。如果有交叉，评测结果不可信。

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

说明：`predictions.jsonl` 说明每条样本输出了什么、得分是多少、是否缺失输出。`metrics.json` 说明总体平均分和每个 slice 的平均分。slice 分数能发现“平均分变好但某类任务变差”的情况。

## 3.5. 记录模型身份

操作：

```bash
pcl model-detect --predictions examples/predictions_candidate.jsonl
```

得到：

- 终端里打印一段 JSON，包含 `provider`、`model_id`、`source`、`confidence` 和 warning。

说明：这能告诉你 prediction 文件里记录的公开 model id 是什么。如果 baseline 和 candidate 使用不同 model id，后面的比较就是“模型 + prompt”的共同变化，不是干净的 prompt-only 对比。

## 3.6. 审计模型漂移

操作：

```bash
pcl model-drift --run runs/current --history runs/previous --out runs/current/model_drift.json
```

得到：

- `runs/current/model_drift.json`

说明：这个文件会说明一次比较是低风险、因为缺少模型身份而不确定，还是已经被模型或 provider 变化污染。alias model id 会被标为复现风险。这里的“模型身份”指 API 请求或响应里记录的公开 model id，不是服务商隐藏权重版本的证明。

## 4. 做统计比较

操作：

```bash
pcl stats --baseline runs/baseline/predictions.jsonl `
  --candidate runs/candidate/predictions.jsonl `
  --out runs/candidate/stats.json
```

得到：

- `runs/candidate/stats.json`

说明：这个文件包含 mean delta、bootstrap confidence interval、paired permutation p-value 和 Holm-adjusted p-value。如果置信区间跨过 0，说明提升仍然不稳定。如果 adjusted p-value 很小且区间不跨 0，说明 candidate 的提升更可靠。

决策指南：

- CI 跨过 0 -> 暂时不要声称 prompt 已经可靠提升。
- p-value 很高 -> 证据偏弱，就算平均分提高也要谨慎。
- p-value 很高但 gate pass -> 当前 policy 可能只检查最低分或最大退化，不代表已经证明提升。
- 平均分提高但某个 slice 退化 -> 先检查这个 slice，再决定是否保留 prompt。

## 5. 生成报告

操作：

```bash
pcl report --run runs/candidate --title "Candidate Prompt Report"
```

得到：

- `runs/candidate/report.md`
- `runs/candidate/report.html`

说明：报告把 split、metrics、stats 和 diagnostics 汇总到一起，适合放进实验记录、评审材料或 prompt 变更记录。HTML 首页会展示上线建议、prompt-only 对比是否有效、模型来源、指标摘要和下一步行动；完整 Markdown 会保留在页面下方用于审计。

## 6. 生成直白或技术解释

操作：

```bash
pcl explain --run runs/quick --level plain
pcl explain --run runs/quick --level technical
```

得到：

- `runs/quick/explanation.json`

说明：`plain` 面向只想看结论的人。`technical` 保留 artifact path 和原始统计比较，方便专业用户审计和复现。

## 7. 使用策略阈值判断

操作：

```bash
pcl gate --run runs/quick --policy examples/gate.policy.yaml
```

得到：

- `runs/quick/gate_result.json`

说明：gate 会输出 `pass`、`needs_review` 或 `fail`，依据包括最低 candidate 分数、最大允许退化、adjusted p-value、可选诊断风险和模型来源策略。模型策略可以检查模型是否未知、baseline/candidate 是否不同、是否使用 alias model、provider 是否在白名单里，以及是否要求 verified。

## 8. 检查 soft-to-hard 风险

操作：

```bash
pcl soft-hard --soft soft_prompt.npz --vocab vocab_embeddings.npz --out runs/candidate/diagnostics
```

得到：

- `runs/candidate/diagnostics/soft_hard.json`

说明：projection distance 越大，说明 soft prompt 向量越不像真实 token embedding。风险高时，soft prompt 训练分数不能直接说明 hard prompt 部署会成功。

## 9. 检查 hidden-state trajectory

操作：

```bash
pcl extract-hidden \
  --model Qwen/Qwen2.5-0.5B \
  --prompts examples/tasks.jsonl \
  --out runs/candidate/inputs/hidden_states.npz \
  --pool last-token \
  --max-items 32

pcl trajectory \
  --states runs/candidate/inputs/hidden_states.npz \
  --out runs/candidate/diagnostics
```

得到：

- `runs/candidate/inputs/hidden_states.npz`
- `runs/candidate/inputs/hidden_states.npz.metadata.json`
- `runs/candidate/diagnostics/trajectory.json`

说明：`extract-hidden` 会把开源或本地 HuggingFace 模型的 hidden activations 转成研究诊断需要的
`states` artifact。建议先用小模型试跑，并安装可选依赖 `pip install -e ".[hf]"`。

mean step drift 说明轨迹每步变化强度。log-decay slope 为负且 R2 较高时，说明轨迹可能向稳定区域靠近。
drift 高或拟合弱时，说明任务或 prompt 可能导致更异质的内部行为。

## 10. 做 Riccati surrogate 诊断

操作：

```bash
pcl riccati \
  --trajectory runs/candidate/inputs/hidden_states.npz \
  --out runs/candidate/diagnostics
```

得到：

- `runs/candidate/diagnostics/riccati.json`

说明：closed-loop spectral radius 小于 1 时，说明拟合出来的有限维 surrogate 在这个诊断中是稳定的。它只是对 surrogate 的检查，不是对完整语言模型的证明。

## 11. 比较 time-varying soft-control lane

操作：

```bash
pcl tv-soft --predictions scored_methods.jsonl --out runs/candidate/diagnostics
```

得到：

- `runs/candidate/diagnostics/tv_soft.json`

说明：如果 `time_varying` 明显优于 `static`，但 `shuffled_tv` 和 `random_tv` 没有同样提升，收益更可能来自时序结构。如果 shuffled/random 也提升，应该检查参数容量和选择效应。
