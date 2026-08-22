# 创新点和贡献

PromptControlLab 在本地 Prompt 与 Agent 控制闭环中，把授权、观测和证据变成显式契约。

## 1. 分级授权

`inspect`、`model`、`agent-scoped` 和 `agent-full` 把检查、模型访问与 Agent 执行分开。工作流只增加任务所需权限，凭据也不会静默选择更高授权级别。

## 2. 版本化开放事件协议

归一化的 `prompt_control_lab.control_event.v1` 让原生插件、guard adapter、重放、报告和基准共享同一个可检查契约。Schema 版本随产物保存，而不是从 UI 状态推断。

## 3. 本地证据权威

JSON 与 JSONL 是事实源。报告和本地 UI 是派生视图，SQLite 是可重建索引。因此，即使显示层或索引不可用，运行仍然可复核。

## 4. 有界 Agent 反馈

Agent 集成显式声明 suggest 或 gate 行为，默认对持久化数据脱敏，限制反馈与队列，并保留已有 Agent guard 的职责边界。

## 5. 确定性重放与基准

已记录事件可以通过同一分析器重放。开放合成基准检查已知轨迹类型的分类契约，不把夹具 accuracy 表述为真实 Agent 性能。

## 6. 证据关联解释

归因、稳定性与决策记录都指向归一化事件。缺乏支持的结论可以保持 `insufficient_evidence`，而不会被报告或 UI 自动补齐。

## 高级诊断

已有统计评测、soft/hard、hidden-state trajectory、Riccati surrogate、time-varying control 和 PEOC 证据工具继续作为可选高级诊断。它们是在明确假设下进行的有边界分析，不构成通用理论主张。
