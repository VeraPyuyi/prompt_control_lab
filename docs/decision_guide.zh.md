# 统计和上线决策指南

这份文档解释如何阅读统计结果和 gate 结果，避免把工具输出说得过满。

## 如果置信区间跨过 0

发生了什么：

- candidate 平均分可能更高，但 paired uncertainty 仍然包含“没有变化”。

说明什么问题：

- 先把结果当成 `needs_review`。
- 保留 prompt 前，先检查变好/变差样本和任务 slice。
- 如果这个决策很重要，建议增加 withheld 样本。

## 如果 p-value 是 1.0，但 gate 仍然 pass

发生了什么：

- gate 检查的是你配置的阈值。
- 如果 policy 比较宽松，即使统计证据弱，也可能通过 gate。

说明什么问题：

- `gate_result.json` 回答：这次运行是否满足配置好的上线规则？
- `stats.json` 回答：这次差异在统计上是否足够可靠？
- 如果 p-value 很高，即使 gate pass，也不要声称“可靠提升”。

## 如果平均分提升，但某个 slice 退化

发生了什么：

- 总体平均分变好，但某类任务变差。

说明什么问题：

- 先检查退化 slice。
- 只有当这个 slice 不重要，或者退化幅度可以接受时，才考虑保留 prompt。

## 如果 soft-hard 风险很高

发生了什么：

- soft prompt 向量离最近的 hard token embedding 较远。

说明什么问题：

- soft prompt 的好分数不能直接说明 hard prompt 可以部署。
- 部署前应重新做 hard prompt 评测，或用 `pcl improve` 生成更可部署的 hard prompt。

## 更稳妥的表述方式

可以说：

- “candidate 通过了当前配置的 gate。”
- “candidate 在这个样本池上平均分更高，但置信区间跨过 0。”
- “当前证据支持人工复查，还不能直接上线。”

不要说：

- “这个 prompt 已经被证明更好。”
- “这个模型已经稳定。”
- “Riccati 诊断证明完整语言模型被控制住了。”

