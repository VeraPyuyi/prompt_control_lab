# 面向群体

## Prompt 与 Agent 操作者

在 Prompt 离开本机前检查内容，选择执行授权范围，并依据事件证据复核决策。默认从 `inspect` 开始；只有任务确实需要时，才进入 `model`、`agent-scoped` 或 `agent-full`。

## Agent 集成开发者

通过原生生命周期插件或 guard adapter 接入版本化事件协议。DeepSeek Harness 是旗舰原生 Cordis 集成；Codex、Cursor、Claude Code 和 GitHub Action 使用 guard 类接口。完成集成本身不会静默授予 Agent 权限。

## 模型与提供商操作者

显式选择模型提供商和模型，检查 adapter 配置，并把公开模型来源主张限制在端点与产物实际记录的范围内。存在凭据只表示配置可用，不等于执行授权。

## 评审者与维护者

使用 `control_run.json`、`events.jsonl` 和决策产物重建过程。报告、本地 UI 与可重建 SQLite 索引便于查看，但不会取代源 JSON。

## 评测团队

重放已记录事件，并运行合成控制基准以发现协议或分析器回归。基准 accuracy 只覆盖内置标签，不测量真实 Agent 性能、因果影响或安全。

## 高级诊断用户

可选评测与研究命令可用于成对统计、soft/hard 投影、trajectory、Riccati surrogate、time-varying control 或 PEOC 导入。这些能力是有边界的诊断，不是完整语言模型的证明，也不是普通控制运行的前置要求。
