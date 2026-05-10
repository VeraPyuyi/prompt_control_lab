# 面向群体

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

