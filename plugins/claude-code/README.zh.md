# Claude Code 中的 prompt_control_lab

这个原型通过 Claude Code 的 `UserPromptSubmit` Hook 接入 `prompt_control_lab`。

它会：

- 从标准输入读取 Claude Code Hook JSON 中的用户 Prompt；
- 调用本地 `prompt_control_lab` Guard；
- 通过 `additionalContext` 返回更清楚、成本更可控的 Prompt 建议；
- 在 `--mode gate` 检测到高风险时，可返回 `decision: block`。

## 安装

在仓库根目录，根据本地路径调整脚本和 Policy 路径，再把以下 Hook 配置加入 Claude Code
Settings：

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python \"D:/path/to/prompt_control_lab/plugins/claude-code/hooks/prompt_guard.py\" --mode suggest --profile coding --token-mode balanced --max-tokens 300 --policy \"D:/path/to/prompt_control_lab/examples/guard.policy.yaml\""
          }
        ]
      }
    ]
  }
}
```

## 模式

- `--mode suggest`：把 Prompt 建议加入额外上下文。
- `--mode auto`：在 Guard 结果中标记优化后的 Prompt 可以自动采用。
- `--mode gate`：当 Prompt 超出估算 Token 预算或风险较高时阻断。
- `--policy path/to/guard.policy.yaml`：使用与 `pcl guard` 相同的团队 Policy。

Policy 使用项目内置的无依赖解析器。示例文件采用扁平键，同时支持 CLI 能识别的最小
`rules:` 嵌套写法。

## 说明

Token 数量是离线估算值，并非特定模型 Tokenizer 的计费结果。Hook 是轻量适配层，核心
行为仍由 Python 包和 `pcl guard` 提供。
