# Codex 中的 prompt_control_lab

Codex 集成目前采用 Skill 与 Wrapper 模式。

仓库内置 Skill：

```text
plugins/codex/skills/prompt_control_lab/SKILL.md
```

在 Windows PowerShell 中安装：

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.codex\skills\prompt_control_lab"
Copy-Item -Recurse -Force .\plugins\codex\skills\prompt_control_lab\* "$env:USERPROFILE\.codex\skills\prompt_control_lab\"
```

复制完成后重启 Codex。

推荐用法：

```bash
pcl guard --prompt "Implement the feature" --profile coding --token-mode balanced
```

团队 Policy 模式：

```bash
pcl guard --prompt "Implement the feature" --profile coding --policy examples/guard.policy.yaml
```

Wrapper 模式：

```bash
echo "Implement the feature" | pcl guard --stdin --profile coding --policy examples/guard.policy.yaml --json
```

在 Codex Skill 中，可把 `pcl guard` 作为较长工作流的第一步。Guard 结果包含：

- 优化后的 Prompt；
- 估算 Token 成本；
- 风险等级；
- 判定原因；
- 建议动作。

核心逻辑继续由 `prompt_control_lab` 提供，避免不同 Agent 环境各自复制一套 Prompt 规则。

Policy 使用项目内置的无依赖解析器。示例采用扁平键，Skill 也可以使用 `pcl guard`
支持的最小 `rules:` 嵌套写法。
