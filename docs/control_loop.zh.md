# 本地控制闭环

English: [control_loop.en.md](control_loop.en.md)

PromptControlLab 是面向 Prompt 与 AI Agent 的本地控制框架。默认主线围绕一次真实执行形成闭环：检查待执行 Prompt，要求显式授权，只记录允许的公开元数据，根据本地事件诊断运行状态，最后写出可由人或 adapter 复核的决策。

它不是自动启动器。创建 control session 时不会执行 provider 或 Agent，基础 `pcl control` 命令也不会启动 Agent。真正的 Agent 执行必须交给显式 adapter，例如 [DeepSeek Harness Cordis 插件](deepseek_harness.zh.md)。

## 闭环步骤

1. **Bind：** 对准确的待执行 Prompt 做哈希，并创建不可变 run context。
2. **Before：** 运行本地 Prompt guard，持久化脱敏 preflight 决策。
3. **Authorize：** 要求从四个授权级别中显式选择一个；非交互执行必须在命令行传入。
4. **Run：** 只有 `model` 模式会调用一个已配置 provider；Agent 执行则由 adapter 接收允许决策后完成。
5. **Observe：** 追加带稳定 id、连续序号和幂等键的脱敏事件。
6. **Why / After：** 只根据已记录事件生成 attribution factor 与可观察 stability state。
7. **Decide：** 写出建议、下一步、Markdown/HTML 报告，并重建本地 run index。

Attribution 只表示关联，stability 只表示可观察事件分类。它们都不能证明因果、正确性或安全性。

## 两分钟 Inspect Run

```bash
python -m pip install -e ".[ui]"
pcl control \
  --prompt "检查这个请求，并提出边界清楚的计划。" \
  --authorization inspect \
  --out runs/first-control \
  --json
```

这条命令会写出一个已 finalized 的 preflight-only run；不调用 provider，也不会启动 Agent。

## 授权级别

| 级别 | 明确允许什么 | 不代表什么 |
|---|---|---|
| `inspect` | 本地 guard、Prompt 哈希、脱敏 artifact 和 `inspect_only` 决策。 | 不发模型请求，不派发工具，不启动 Agent。 |
| `model` | preflight 通过后，通过指定 provider adapter 对公开 model id 发起一次调用；必须同时给出 `--provider` 与 `--model`。 | 不执行 Agent 或工具；`block` 或 `required_review` 会阻止调用。 |
| `agent-scoped` | 指定 adapter 可以控制一个已绑定 Agent/session 及其可观察生命周期；Harness bridge 强制使用该级别。 | 基础命令仍不会启动 Agent；执行由 adapter 所有。 |
| `agent-full` | adapter 或 replay 可以记录用户显式选择的更宽 Agent 边界。 | 不是隐式提权；Harness 原生 live session 仍锁定为 `agent-scoped`。 |

stdin 不是交互终端时，省略 `--authorization` 会直接报错。交互终端会先显示一份不落盘的 suggest preview，再询问授权级别。授权只描述允许的执行范围，不是对 Prompt 或动作安全性的认证。

## Model 模式

把凭证放在环境变量中，先离线检查 adapter，再明确指定公开 model id：

```bash
pcl providers inspect deepseek --json
pcl control \
  --prompt "返回一个三项检查表。" \
  --authorization model \
  --provider deepseek \
  --model deepseek-chat \
  --out runs/model-control \
  --json
```

Provider 配置与公开模型溯源边界见 [providers.zh.md](providers.zh.md)。

## JSON 是事实源

每种持久记录都有版本化 schema。JSON 与 JSONL artifact 是事实源：

| Artifact | Schema 或作用 |
|---|---|
| `control_run.json` | 不可变身份与上下文：`prompt_control_lab.control_run.v1`。 |
| `events.jsonl` | 只追加的有序记录：`prompt_control_lab.control_event.v1`。 |
| `preflight.json` | 可安全持久化的 gate 结果：`prompt_control_lab.preflight_decision.v1`；改写后 Prompt 在磁盘中被脱敏。 |
| `provider_result.json` | `model` run 实际执行后的归一化输出与公开溯源。 |
| `attribution.json` | 可观察因素：`prompt_control_lab.attribution_report.v1`。 |
| `stability.json` | 可观察状态与计数：`prompt_control_lab.stability_report.v1`。 |
| `decision.json` | 建议与下一步：`prompt_control_lab.control_decision.v1`。 |
| `report.md` 与 `report.html` | JSON 记录的人类可读投影。 |
| `.prompt_control_lab/runs.sqlite3` | 可重建查询索引，不是证据权威来源。 |

受信任的 live caller 可以在 preflight transport response 中收到改写后的 Prompt。持久化 `preflight.json` 会把正文替换成 `[REDACTED]`，只保留哈希、发现和决策。

## 开放事件协议

每条 `prompt_control_lab.control_event.v1` 记录都包含 `run_id`、规范化 `event_id`、正整数 `sequence`、`event_type`、UTC `timestamp`、脱敏 `payload` 与可选 `idempotency_key`。同一个 run 只接受连续序号。相同幂等内容重放时不会重复写入；用同一键提交不同内容会报错。

`events.jsonl` 只追加，并在每次接受事件后 flush 到磁盘。常见 namespace 包括 `session/*`、`agent/*`、`tools/*`、`tool/*`、`test/*`、`step/*`、`task/*`、`harness/*`。Adapter 可以补充可观察元数据，但 secret 字段、Prompt 正文和隐藏推理会在持久化前脱敏。

Schema 名携带协议主版本。字段或语义发生破坏性变化时必须启用新 schema 版本；consumer 遇到未知版本应该拒绝，而不是猜测。

## 可重建 SQLite 索引

Finalization 会在 runs root 下重建 `.prompt_control_lab/runs.sqlite3`。表中只存 locator 与摘要字段，例如 run id、路径、授权、provider/model/agent、risk、stability、decision 和事件数。

删除 SQLite 文件不会删除控制证据。它可以根据 `control_run.json`、`preflight.json`、`stability.json`、`decision.json` 和 `events.jsonl` 重建。不要通过编辑 SQLite 修改决策；应通过 control workflow 更新事实源，再重建索引。

## 失败与证据边界

- Preflight 返回 `block` 或 `required_review` 时，`model` 执行会停止。
- Preflight-only run 会写出 `insufficient_evidence` attribution 与 stability，不会编造执行证据。
- Provider 与 adapter 错误会直接暴露；PromptControlLab 不会静默替换用户请求的模型。
- Prompt 哈希只能证明所记录输入的字节身份，不能证明 Prompt 质量。
- 事件标签只描述可观察行为，不描述隐藏模型状态或因果机制。

用 [benchmark](control_benchmark.zh.md)检查 analyzer contract，用[本地 UI](control_ui.zh.md)复核 run。PEOC、soft-hard、trajectory、Riccati 与 time-varying soft-control 只放在 Advanced Diagnostics 中，不是本闭环的必需步骤。
