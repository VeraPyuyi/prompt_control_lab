# Preflight（执行前检查）

## 目的

`promptcontrollab.preflight` 在 AI Agent 或模型消耗 Token、修改文件之前检查并改进 Prompt。它把启发式风险识别、团队 Policy、Prompt 改写、Token 预算、脚手架检查和工作流选择放在同一层。

## 使用场景

- 识别模糊、破坏性、安全敏感或范围过宽的指令。
- 在 Agent 执行前应用团队维护的 Guard Policy。
- 生成目标更清楚、输出边界和验证要求更明确的 Prompt。
- 估算 Prompt Token，并推荐合适的 PromptControlLab 工作流。

## CLI 命令

```bash
pcl guard --prompt "修复这个问题" --profile coding --policy examples/guard.policy.yaml
pcl improve --prompt "回答这个问题" --token-mode balanced
pcl start --choice guard --prompt "修复这个问题"
pcl choose --need "在 Agent 执行前检查 Prompt"
pcl scaffold-check --scaffold runs/scaffold
```

## Python API

批准后的 canonical package 提供以下主要入口：

```python
from promptcontrollab.preflight import (
    choose_tool_for_need,
    guard_prompt,
    improve_prompt,
    load_guard_policy,
)
```

辅助类型包括 `PromptGuardResult`、`PromptImprovement`、`PromptContext`、`GuardPolicy` 和 `GuardViolation`。

## 输入与产物

- 输入：Prompt 字符串或文件、profile、mode、Policy 文件、Token 模式、可选 run 上下文和语言。
- 输出：`guard_result.json`、`improved_prompt.txt`、`prompt_improvement.json`、`prompt_diff.md`，以及按需生成的脚手架检查报告。
- JSON 输出为 CLI、Hook、MCP 和 Skill 使用者保留稳定字段。

## 依赖

默认 Preflight 流程完全本地运行且不需要额外依赖。它依赖 `core` 读取配置和文件，也可以将已有 run artifact 作为受限上下文。

## 扩展点

- 在不改变稳定结果 schema 的前提下增加 Guard profile 和 Policy rule。
- 增加多语言建议和风险类别。
- 增加输出确定的工具选择通道或 Prompt 上下文提取器。

## 限制

- Guard 决策是启发式治理信号，不是 Agent 操作安全性的证明。
- Token 数量是估算值，可能与 Provider 的计费 tokenizer 不同。
- 离线改写不会调用模型，也不保证修改后的 Prompt 一定表现更好。

## 测试与示例

示例位于 `examples/guard.policy.yaml`、插件文档和 Preflight 测试中。可运行：

```bash
python -m pytest tests -k "guard or improve or policy or scaffold or tool_choice"
```
