# Cursor 中的 prompt_control_lab

Cursor 集成包含两层：

- 轻量 Rules 与命令式使用模式；
- 无额外依赖的 MCP 风格 stdio Server，对外提供 `guard_prompt`。

当前适配器不宣称能够完整拦截 Cursor 的每次 Prompt。它提供可调用的 Guard 工具和可落地
的 Rules 工作流。

仓库内置规则文件：

```text
plugins/cursor/rules/prompt_control_lab.mdc
```

在 Cursor 项目中安装：

```powershell
New-Item -ItemType Directory -Force .cursor\rules
Copy-Item plugins\cursor\rules\prompt_control_lab.mdc .cursor\rules\prompt_control_lab.mdc
```

推荐用法：

1. 在 `.cursor/rules` 保存 Prompt 指引。
2. 在发送高成本或模糊 Prompt 前运行 `pcl guard`。
3. 自定义 Wrapper 优先展示 JSON 输出中的 `plain_summary`。
4. 团队工作流可先执行：

```bash
echo "Refactor this module" | pcl guard --stdin --profile coding --token-mode balanced --json
```

团队 Policy 模式：

```bash
echo "Refactor this module" | pcl guard --stdin --profile coding --policy examples/guard.policy.yaml --json
```

建议的 `.cursor/rules` 片段：

```text
Before acting on vague, broad, or expensive prompts, ask the user to run:
pcl guard --prompt "<their prompt>" --profile coding --policy examples/guard.policy.yaml

Prefer prompts that define scope, target files, expected output, tests, and verification.
```

## 更深集成方向

更深层的 Cursor 集成可采用以下任一方式：

- 在 Prompt 提交前调用 `pcl guard --json` 的 Cursor 扩展；
- 把 `guard_prompt` 暴露为工具的 MCP Server；
- 读取 Prompt、显示 `plain_summary`，再复制或转发优化 Prompt 的本地 Wrapper。

稳定的集成契约是 `pcl guard --json`，尤其包括 `plain_summary`、`action`、
`risk_level`、`improved_prompt` 和 `token_report`。

## 可选 MCP 风格服务器

启动本地 Server：

```bash
python plugins/cursor/mcp_server.py
```

如果 Cursor 配置支持本地 MCP Server，可将 Server 命令指向这个脚本。它提供一个工具：

```text
guard_prompt
```

工具参数示例：

```json
{
  "prompt": "Refactor this module",
  "profile": "coding",
  "token_mode": "balanced",
  "mode": "suggest",
  "policy": "examples/guard.policy.yaml"
}
```

工具返回含 `plain_summary`、`risk_level`、`improved_prompt`、`reasons` 和
`token_report` 的 JSON 文本，方便 Wrapper 在 Agent 消耗 Token 前展示可读建议。

Policy 使用项目内置的无依赖解析器。示例采用扁平键，同时支持 CLI 能识别的最小
`rules:` 嵌套写法。
