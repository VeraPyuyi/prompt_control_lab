# DeepSeek Harness 真实会话案例

这份可公开案例记录了一次真实、范围受限的 DeepSeek Harness 编码会话，并把生命周期事实、PromptControlLab 诊断和结论边界分开说明。

## 观察到了什么

- 原生 Cordis 插件针对 Harness `0.1.1-rc.2`、commit `b150a551...` 运行，并通过一个持久本地 stdio bridge 通信。
- 4 组匹配的模型请求/响应报告公开模型身份 `deepseek-official/deepseek-v4-flash`。
- 4 次终态工具结果包括 2 次文件读取、1 次有界文件写入和 1 次测试执行。
- 一次性仓库最终 3/3 测试通过。只有 `src/math_utils.py` 发生变化，增加 1 行、删除 1 行。
- 测试结果同时记录了 `is_error=false` 和明确的进程退出码 `0`；机器验收要求两个信号同时成立。
- 捕获的 Harness usage metadata 包含 13,401 个输入 token 和 619 个输出 token；没有对 cache token 或计费成本作出声明。
- 捕获的响应没有提供 provider 签发的 request ID。PromptControlLab 的本地 request identifier 不会被表述成 provider identifier。

## 这些诊断可以解释什么

较早的一次运行暴露了启发式 Guard 的上下文与否定作用域误判。加入针对性规则修复后，经过验证的真实模型运行得到 `low` preflight risk 和 `suggest` 决策。

后续审查发现，`is_error=false` 只能说明工具包装器正常结束，不能证明 shell 测试命令成功。脱敏协议现在只额外保留整数 `exitCode`，仍丢弃 stdout 和 stderr。缺少退出码时保持 `unknown`，非零为 `fail`，只有零才是 `pass`。新的真实运行明确记录退出码 `0`，因此可直接归类为 `converging`。最终 control decision 仍保守保持为 `suggest`。

## 凭据边界

凭据只临时提供给真实运行进程。凭据形态扫描在三个明确列出的本地范围内发现 0 个匹配：一次性任务工作区、PromptControlLab control artifacts 和 DeepSeek Harness session artifacts。这是有范围的观测，不是对未扫描外部系统的保证。

## 可复核的公开 Artifact

- [派生证据](live_session_evidence.json)保存脱敏后的生命周期、usage、诊断和扫描汇总。
- [状态文件](live_session_status.json)引用该证据并记录集成检查。

这个案例能证明一次真实、有界的生命周期经过了 preflight、模型请求、工具读取、文件修改和通过测试。它不能识别隐藏模型权重、证明语义安全、建立严格因果关系，也不能从一个任务推广出普遍性能结论。
