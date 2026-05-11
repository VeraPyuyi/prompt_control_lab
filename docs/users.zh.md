# 面向群体

## 非专业评审者

如果你只想快速得到一份清楚报告，可以使用 Quick Mode。`pcl analyze` 会把任务数据和两份预测文件转换成 split hygiene、metrics、stats、explanation 和 Markdown/HTML 报告。

## Prompt 研究者

你可以用 PromptControlLab 固化 train/val/withheld 协议，避免把 withheld set 用成调参集。工具会保存 split hash、每条样本输出、统计检验和报告，方便论文复现。

## LLM 工程团队

你可以把 prompt 改动当成一次本地 regression test：导入旧 prompt 和新 prompt 的输出，比较总体分数、slice 分数和统计可靠性，再决定是否保留新 prompt。

## Soft Prompt 研究者

你可以检查 soft prompt 向 hard token embedding 投影时的距离和风险。这个结果能说明 soft prompt 是否有可能直接转成 hard prompt 使用。

## 模型迁移和评测团队

你可以对同一批任务保存不同模型或不同 prompt 的 artifact，比较迁移后的退化、slice 风险和报告结果。

## Trajectory / Control 方向研究者

你可以导入 hidden-state trajectory，检查 drift、log-decay slope、turnpike-like signal 和 Riccati surrogate stability。结果用于诊断，不用于声称已经证明完整语言模型满足某个控制论假设。

## 专业用户

如果你需要精细控制每一步，可以使用 Expert Mode。单个命令可以分别控制切分参数、评测指标、统计采样次数、研究诊断和策略阈值判断。

## 专家决策指南

- 如果 bootstrap 置信区间跨过 0，就算平均分提高，也要把这次变化视为“不够确定”。
- 如果 adjusted p-value 很高，但 gate 仍然 pass，通常说明策略只要求“没有明显退化”或“达到最低分数”。这表示“符合当前策略”，不是“统计上已经证明提升”。
- 如果 `p-value = 1.0` 但 gate pass，请先检查 gate policy。它可能比较宽松，或者只关注最低分和最大退化阈值。
- 如果总体平均分提高，但某些 slice 退化，先检查这些 slice，再决定是否保留 prompt。
- Riccati、trajectory、soft-hard 诊断是拟合探针和部署风险信号，不是对完整语言模型的数学证明。
