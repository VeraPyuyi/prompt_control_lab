# DeepSeek Harness 原生集成

English: [deepseek_harness.en.md](deepseek_harness.en.md)

DeepSeek Harness 是 PromptControlLab 0.2 alpha 框架方向中的旗舰 Agent 集成。它是原生 Cordis 插件，不是日志抓取器，也不是第二套 Agent loop。插件利用 Harness 在模型请求与工具执行前的拦截点，再通过一个持久本地 Python bridge 传递有界、脱敏的观察事件。

该集成由 PromptControlLab 社区维护。它的存在不代表 DeepSeek Harness 维护者已经背书、支持或收录。

## 兼容性锁

已测试 contract 被有意限制在一个明确版本：

- DeepSeek Harness version：`0.1.1-rc.2`
- DeepSeek Harness commit：`b150a551b8d465e31e418e1b2eaf5e79bbb7d28e`
- Node.js：`^22.19.0 || >=24.0.0`
- Bridge protocol：`prompt_control_lab.bridge.v1`
- Transport：一个持久 stdio 进程上的 line-delimited JSON-RPC 2.0

机器可读事实源是 [`plugins/deepseek-harness/compatibility.json`](../plugins/deepseek-harness/compatibility.json)。当前文档不声称兼容其他 Harness version 或 commit。Harness event signature 一旦变化，必须同步更新 lock、TypeScript wrapper、Python method 与 contract test。

锁定到该 commit 的 Harness 官方资料：

- [已测试 commit 的仓库](https://github.com/deepseek-ai/deepseek-harness/tree/b150a551b8d465e31e418e1b2eaf5e79bbb7d28e)
- [架构与 turn flow](https://github.com/deepseek-ai/deepseek-harness/blob/b150a551b8d465e31e418e1b2eaf5e79bbb7d28e/docs/architecture.md)
- [Cordis event system](https://github.com/deepseek-ai/deepseek-harness/blob/b150a551b8d465e31e418e1b2eaf5e79bbb7d28e/docs/user/develop/framework/events.md)
- [第一个 Harness plugin](https://github.com/deepseek-ai/deepseek-harness/blob/b150a551b8d465e31e418e1b2eaf5e79bbb7d28e/docs/user/develop/basic/index.md)
- [Event producer/consumer map](https://github.com/deepseek-ai/deepseek-harness/blob/b150a551b8d465e31e418e1b2eaf5e79bbb7d28e/docs/event-producer-consumer.md)
- [内置 repeat-tool reminder](https://github.com/deepseek-ai/deepseek-harness/blob/b150a551b8d465e31e418e1b2eaf5e79bbb7d28e/packages/guard/repeat-tool-reminder/README.md)

## 架构

```text
Harness Agent
  -> Cordis waterfall: agent/pre-step
  -> Cordis waterfall: tools/pre-execute
  -> PromptControlLab 原生插件
  -> 一个持久 `pcl bridge serve --transport stdio`
  -> 版本化本地 JSON/JSONL artifact
  -> attribution、stability、decision、report 与 history index
```

Cordis 插件负责 lifecycle listener 与有界 single-writer observation queue；Python bridge 负责持久化 control artifact 与分析。Harness 继续拥有 Agent loop、provider request、retry policy、工具执行、审批、session log、内置 guard 与取消信号。

## 安装与初始化

从锁定 commit 的 Harness checkout 开始，并把 PromptControlLab 安装在启动 Harness 的同一环境中。Harness 自己的 `pnpm` 环境以官方仓库说明为准。

先生成可复核的项目文件；这条命令不会自动修改正在使用的 Cordis composition：

```bash
pcl harness init --project .
```

它会写出：

- `.promptcontrol/deepseek-harness.json`
- `.promptcontrol/deepseek-harness.cordis.yml`
- `.promptcontrol/deepseek-harness.compatibility.json`

把原生插件安装到 Harness checkout 并构建：

```bash
pcl install-plugin deepseek-harness --target ./plugins/prompt-control-lab
cd plugins/prompt-control-lab
npm ci
npm run build
```

检查 `cordis.patch.yml`，再把其中的 row 合并到正在使用的 Harness profile。生成的安全默认配置是：

```yaml
- insert:
    - id: prompt-control-lab
      name: '@prompt-control-lab/deepseek-harness'
      config:
        mode: suggest
        policyPath: .promptcontrol/guard.policy.yaml
        capture: redacted
        feedback: summary
        autoRecover: false
        maxAutoRecoveries: 1
        bridgeFailure: warn
        runsRoot: .promptcontrol/runs
        feedbackMaxChars: 600
        observationQueueSize: 256
        exposeStatusTool: false
```

Harness 进程必须能 import PromptControlLab，并能执行 `pcl bridge serve --transport stdio`。插件会启动并复用这个 bridge；同一个 live session 不应再启动第二个 writer。

## Doctor

```bash
pcl harness doctor --project . --json
```

Doctor 完全离线。它检查本地 config schema、redacted capture、compatibility lock、Python bridge health、Node version 和 packaged plugin 文件。通过不代表 active Harness profile 已加载该 row，也不代表 provider credential 可用或 live session 已发出事件；这些状态需要用有界 Harness run 单独验证。

真实完成验收还要求 `session_origin=live_cordis`、持久 stdio transport、锁定的 Harness
版本/commit，以及带 bridge 来源序号和时间戳的生命周期事件。replay 数据和测试 fixture
直接追加的事件不能满足该验收。这些检查只能确认原生生命周期采集链路，仍不能证明 provider
隐藏权重身份，也不能证明每个 Agent 动作在语义上都安全。

## 精确 Event Mapping

Harness 会区分 live Cordis event 与 durable session event。`turn/*`、`step/*`、`tool/call`、`tool/result`、`compaction/*` 都通过 Cordis `session/event` listener 到达；它们不是同名 Cordis event。

| Harness 来源 | PromptControlLab bridge call | 持久化效果 |
|---|---|---|
| `agent/session-start` | `harness_session_start` | 创建或重试当前 `agent-scoped`、脱敏 control run，并校验 compatibility lock。已 finalize 的 session 再恢复时，会创建带 lineage metadata 的确定性 `-resume-N` 新 run。 |
| `agent/pre-step` | `harness_pre_step` | 在每个 `(turn, step)` 的模型请求前同步检查 downstream 最终 Prompt；只持久化哈希、发现与决策。 |
| `agent/request` | `harness_event`，event 为 `agent/request` | 记录 turn、step、retry attempt、公开 provider/model、max tokens 与 temperature。 |
| `agent/request-error` | `harness_event`，event 为 `agent/request-error` | 记录有界 failure kind/code/status/retryability；retry 仍由 Harness 所有。 |
| `tools/pre-execute` | `harness_tool_pre_execute` | 在派发前 gate 只含哈希的工具投影。 |
| `tools/post-execute` | `harness_event`，event 为 `tools/post-execute` | 在 downstream policy 之后观察归一化 result status。 |
| `tools/result` | `harness_event`，event 为 `tools/result` | 观察不可变 result 投影。 |
| `session/event` | `harness_event`，event 为 `session/<event.type>` | 记录脱敏 durable session metadata，但跳过 `assistant/chunk`。 |
| `session/event` 中的 `turn/end` | 先 `harness_event`，再 `harness_turn_end` | 持久化 event，并计算有界 turn assessment。 |
| `agent/turn-stopping` | `harness_turn_end` | 只有显式启用 `autoRecover` 时才请求 recovery recommendation。 |
| `agent/disposed` | `harness_finalize` | Flush 关键 lifecycle work，并 finalize 本地报告。 |
| 可选 `pcl_status` tool | `harness_status` | 只读状态，不改变 state；仅在 `exposeStatusTool: true` 时注册。 |

七个版本化 bridge method 是 `harness_session_start`、`harness_pre_step`、`harness_tool_pre_execute`、`harness_event`、`harness_turn_end`、`harness_status`、`harness_finalize`。

## Suggest 与 Gate 语义

### Prompt gate：`agent/pre-step`

插件会先等待 downstream pre-step listener，再检查它们最终准备发送的准确 message batch。

- `suggest` 中，PromptControlLab 的所有 decision 都继续 delegate；如果有 feedback，可以追加一条有 source attribution、长度受限的 user message。Bridge 不可用时记录本地 warning 并继续，即 suggest 失败时继续（fail open）。
- `gate` 中，`deny` 会在模型请求前返回 `{ kind: "reject" }`。Bridge failure 同样 reject，即 gate 失败时关闭（fail closed）。没有 Prompt 时会 reject，只有 step 1 之后 Harness 明确发起的空 continuation 例外。
- Downstream listener 已经 reject 时，PromptControlLab 保留该 reject。
- Harness abort signal 会取消等待；PromptControlLab 不创建另一套 retry loop。
- 第一个非空 pre-step 绑定稳定的 run-level Prompt identity。后续 coordinate 写入脱敏的 `preflight.turn-N.step-N.json` artifact；同一 coordinate 的完全相同 retry 保持幂等，而同一 coordinate 换用不同内容会被拒绝。

### Tool gate：`tools/pre-execute`

- `suggest` 中，`allow`、`ask`、`deny` 都 delegate 给下一个 Harness listener。
- `gate` 中，`deny` 阻止派发，`ask` 交给 Harness approval，`allow` 正常 delegate。
- Bridge 在 `gate` 中不可用时，工具会带有界 reason 被 deny。Harness signal 已 abort 时，工具按 cancelled deny。

`bridgeFailure` 在 `suggest` 中会归一化为 `warn`，在 `gate` 中会归一化为 `block`；配置不能把 gate 改成 fail open。

## 隐私默认值

原生参考集成只支持 `capture: redacted`。

| 输入 | 持久化表示 |
|---|---|
| 原始 Prompt | 只为同步 `harness_pre_step` 穿过本地 stdio；持久化为 SHA-256 identity、发现与决策，不保存原始 prompt 正文。 |
| 工具参数 | 稳定投影的 SHA-256 与排序后的顶层 argument key。 |
| 工具结果 | Error flag、Harness 可提供时的整数 shell 退出码、有界 error name/code、是否结束 turn和 content block 数；不保留原始 stdout/stderr。 |
| Assistant 内容 | 不复制到 PromptControlLab event；跳过 `assistant/chunk`。 |
| 隐藏推理 | Hidden reasoning、chain-of-thought、thinking field 与 reasoning content 都不持久化。 |
| API keys | 已识别的凭据字段和 credential-shaped value 会在持久化前被丢弃。公开证据仍需执行有明确范围的 artifact 扫描；这不代表对未扫描外部系统作出保证。 |
| 路径 | Replay sanitization 会哈希 workspace/repository path，而不是保留原路径。 |

脱敏会减少保留内容，但不保证任意用户元数据都无害。共享前仍应检查 policy 与 artifact。

## 有界 Feedback 与 Observation

- `feedbackMaxChars` 默认 `600`；Prompt suggestion、tool reason 和 recovery recommendation 都截断到该上限。
- `observationQueueSize` 默认 `256`；一个 worker 串行写入异步 observation。
- Queue overflow 会丢弃新的非关键 observation、增加计数并输出 warning。缺失 observation 必须按缺失证据处理。
- `autoRecover` 默认 `false`，并会传给 bridge。自动 steering 必须同时满足三项条件：配置为 `autoRecover: true`、所选 policy 包含 `harness_auto_recover: true`（或 `harness.auto_recover: true`），且 `maxAutoRecoveries > 0`；否则 bridge 返回 `recover: false`。
- `maxAutoRecoveries` 默认是一。插件会在每个 control run 内计数，自动 steering 不会超过该配置上限；即使两项 opt-in 都为 true，设为 `0` 也会禁用 recovery。
- Turn-end 与 finalization 使用关键 lifecycle path，并在 plugin teardown 时 flush。

## 与 Harness 内置 Guard 协作

插件不会替换或复刻 Harness 的 `repeat-tool-reminder`、timeout policy、approval system、retry policy 或 tool guard；这些能力继续由 Harness 决定。

当 source plugin 标识出 `repeat-tool-reminder` 时，PromptControlLab 记录 `repeat_tool_reminder` signal；当可见 error code 或 event 含 timeout 时，记录 `tool_timeout` signal。这些信号用于本地跨 run stability 视图，不代表 PromptControlLab 检出了全部循环或 timeout，也不会覆盖内置 guard 决策。

## Replay 与 Report

把已有 Harness JSONL session replay 成新的脱敏 control run：

```bash
pcl harness replay --session <session.jsonl> --out runs/harness-replay --json
```

Replay 至少需要一条 user Prompt，才能执行诚实的 preflight。它会哈希 content，从持久 event 中删除隐藏推理与原始内容，记录 source-session hash，但不会重新运行 Agent。

如果外部 Harness 进程在插件 teardown 运行前退出，可显式收口本地 run：

```bash
pcl harness finalize --runs .promptcontrol/runs --session <session-or-run-id> --outcome failed --exit-code 1 --json
```

该命令不会编造缺失活动。如果没有观察到 preflight，它会把这次运行记录为 `insufficient_evidence`，并明确说明没有证据证明发生过模型请求、工具执行或代码修改。

按 Harness session id 或 PromptControlLab run id 查找本地报告：

```bash
pcl harness report --runs .promptcontrol/runs --session <session-or-run-id> --json
```

结果返回本地已有 `report.md`、`report.html` 与 `decision.json` 的路径。准备给上游维护者审阅的问题见 [GitHub Discussion draft](github_discussion_deepseek_harness.md)。
