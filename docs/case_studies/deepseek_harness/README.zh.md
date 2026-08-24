# DeepSeek Harness 集成状态

这份可公开快照把“集成已就绪”和“真实模型 Agent 会话已完成”明确分开。

## 已观察到

- 原生 Cordis 插件可针对 Harness `0.1.1-rc.2`、commit `b150a551...` 构建。
- 27 项 TypeScript 契约测试通过。
- 活动 profile 能解析插件、启动持久本地 bridge，并创建脱敏 `ControlRun`。
- 外部启动失败后，可以显式收口为 `insufficient_evidence`，不会编造 preflight、模型、工具、文件或测试活动。
- 只有记录了匹配的模型请求/响应、文件读取、有界文件修改和成功测试，run 才能完成验收。

## 尚未观察到

记录检查时，本地环境中没有 `DEEPSEEK_API_KEY`，因此仓库不会声称已经发生真实模型请求、工具读取、受控修改或测试执行。Replay 和 fixture 不能替代真实会话验收。

机器可读状态见 [live_session_status.json](live_session_status.json)。下一次可验收运行必须在一次性仓库中捕获完整链路：policy preflight、公开 model identity、PromptControlLab request identity、provider 可提供时的 response identity、文件读取、有界修改、测试结果、稳定性状态和最终决策。本地 request id 不会被表述成 provider 签发的 request id。
