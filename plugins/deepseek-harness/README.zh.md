# PromptControlLab 的 DeepSeek Harness 原生插件

这是一个原生 Cordis 插件：它在模型请求和工具执行前调用 PromptControlLab 门禁，并把脱敏后的
Agent 生命周期证据通过一个常驻本地 Python bridge 传给 PromptControlLab。

## 它怎样工作

1. `agent/pre-step` 检查待发送 prompt。`gate` 模式返回 `{ kind: "reject" }` 时，Harness 不会调用模型。
2. `tools/pre-execute` 只发送工具参数哈希等元数据。`gate` 模式的 `deny` 会阻止工具执行，`ask` 交给
   Harness 的审批机制。
3. 模型、工具、session 和 turn 的观察事件进入有界单写入队列，不会为每个事件重复启动 Python。
4. PromptControlLab 在本地生成归因、稳定性、历史和报告 artifacts。

Guard 和稳定性判断属于启发式治理与诊断，不是“Agent 一定安全”的证明。

## 安装到 Harness 项目

```bash
pcl install-plugin deepseek-harness --target ./plugins/prompt-control-lab
cd plugins/prompt-control-lab
npm ci
npm run build
```

然后把 `cordis.patch.yml` 中的配置行加入正在使用的 Harness profile。Harness 进程所在环境必须能运行
`pcl bridge serve --transport stdio`。

## 安全默认配置

```yaml
- id: prompt-control-lab
  name: '@prompt-control-lab/deepseek-harness'
  config:
    mode: suggest
    policyPath: .promptcontrol/guard.policy.yaml
    capture: redacted
    feedback: summary
    autoRecover: false
    bridgeFailure: warn
    runsRoot: .promptcontrol/runs
    feedbackMaxChars: 600
    observationQueueSize: 256
    exposeStatusTool: false
```

`suggest` 模式在 bridge 故障时放行并显示警告；`gate` 模式固定为故障关闭。自动 steer 默认关闭，显式
开启时仍受 `maxAutoRecoveries` 次数上限约束。

## 隐私边界

- 原始 prompt 只通过 stdio 做同步检查，Python bridge 必须只持久化 prompt 哈希、发现和决策。
- 工具参数只记录 SHA-256 和顶层字段名。
- 不复制 assistant 原文、隐藏推理、思维链、API key 或工具原始输出。
- 可选 `pcl_status` 工具只读，并且仅在 `exposeStatusTool: true` 时注册。

精确 bridge 字段和锁定的 Harness 版本见 [COMPATIBILITY.md](COMPATIBILITY.md)。
