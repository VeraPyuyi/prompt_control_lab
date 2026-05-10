# 使用背景

Prompt 工程常见的问题是：我们看到一个 prompt 的分数更高，但不知道这个提升是否可靠。

常见风险包括：

- 在 validation 上反复调 prompt，最后得到的结果可能只是 validation artifact。
- train、validation、withheld 数据混在一起，导致评测看起来过好。
- 只看平均分，忽略某些任务 slice 已经退化。
- soft prompt 训练有效，但部署时只能使用 hard prompt，效果可能丢失。
- prompt 改动后，输出分数变化不大，但 hidden-state trajectory 可能更漂移、更不稳定。

PromptControlLab 的目标是把这些问题变成可检查的工程步骤。它不只回答“分数是多少”，还回答：

- 数据是否切干净？
- prompt 改动是否统计上可靠？
- 哪些 slice 变好或变差？
- soft-to-hard 转换风险是否高？
- trajectory 是否更稳定或更漂移？
- time-varying prompt 的收益是否真的来自时序结构？

因此，它适合用在 prompt 优化研究、论文复现、本地 prompt regression testing、soft prompt 部署分析和 open-model hidden-state 诊断中。

工具支持两种模式。Quick Mode 给非专业人员一个命令生成可读报告。Expert Mode 保留每个独立命令，方便专业用户深入控制和审计。
