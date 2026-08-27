# prompt_control_lab 插件适配器

本目录包含面向 IDE 和 CLI Agent 的轻量适配器，用于在 Prompt 发送给模型前调用
`pcl guard`。

当前状态：

- `claude-code/`：可运行的 `UserPromptSubmit` Hook 原型。
- `cursor/`：Rules、命令式工作流和本地 MCP 风格服务器。
- `codex/`：Skill 与 CLI Wrapper 接入说明。
- `deepseek-harness/`：通过持久 stdio Bridge 接入 ControlRun 的原生 Cordis 插件。

稳定的核心接口是 CLI：

```bash
pcl guard --prompt "Fix this bug" --profile coding --token-mode balanced --json
```

团队可以让 CLI Wrapper 和 IDE Hook 透传同一份 Policy：

```bash
pcl guard --prompt "Fix this bug" --profile coding --policy examples/guard.policy.yaml --json
```

Hook 或 Wrapper 集成优先使用标准输入，避免把长 Prompt 拼进命令参数：

```bash
echo "Fix this bug" | pcl guard --stdin --profile coding --policy examples/guard.policy.yaml --json
```

各子目录 README 说明安装步骤、能力边界和对应的团队 Policy 用法。适配器只负责连接宿主，
Guard、Policy 和 Artifact 行为仍由 Python 核心实现。
