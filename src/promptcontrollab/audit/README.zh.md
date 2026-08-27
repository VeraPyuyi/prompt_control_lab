# Audit（Agent 执行审计）

## 目的

`promptcontrollab.audit` 用于解释 AI 编程任务执行后究竟改了什么。它汇总 Git diff、测试、敏感路径、依赖、Workflow、疑似 Secret 新增、Agent manifest、PR 审查覆盖范围和结论边界。

## 使用场景

- 审查两个 Git revision 之间的文件变化和增删行数。
- 识别意外路径、公共 API 变化、测试删除或安全敏感修改。
- 构建一个连接 Prompt、Policy、模型、Gate、Diff 和测试的 `agent_run.json`。
- 生成 PR Summary、GitHub Check 信号、Markdown 审查或 SARIF 报告。

## CLI 命令

```bash
pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit --sarif runs/audit/pcl.sarif
pcl agent-run build --run runs/quick --audit runs/audit --agent codex --out runs/agent_run.json
pcl pr-summary --audit runs/audit/audit_result.json --gate runs/quick/gate_result.json --out pr_summary.md
pcl github-app serve --host 0.0.0.0 --port 8080
pcl claim-check --run runs/quick
```

## Python API

批准后的 canonical package 提供审计与评审构建接口：

```python
from promptcontrollab.audit import (
    build_agent_run_manifest,
    build_pr_summary,
    run_audit_diff,
    run_claim_check,
)
```

GitHub 集成通过 integrations 层使用 `verify_webhook_signature`、`summarize_pull_files` 和 `handle_pull_request_payload`。

## 输入与产物

- 输入：Git revision、预期路径、测试记录、Audit/Gate artifact、Policy 路径和 PR 文件元数据。
- 输出：`audit_result.json`、`audit_summary.md`、可选 `pcl.sarif`、`agent_run.json`、`pr_summary.json`、`pr_summary.md` 和 Claim Check 报告。
- 疑似 Secret 发现会在持久化前脱敏。

## 依赖

本地 Diff 审计使用 Git、标准库和 `core`。外部 Secret Scanner 是可选可执行程序。自托管 GitHub App 需要安装 `bot` extra。

## 扩展点

- 增加带稳定 Rule ID 的文件分类器和结构化 finding。
- 在保留内置 fallback 的同时增加可选外部 Scanner。
- 基于同一份结构化 Summary Model 增加 PR Renderer 或 Annotation。

## 限制

- Diff 分类和公共 API 检测属于启发式分析，不是完整语义分析。
- 内置 Secret 匹配不能替代专门的 Secret Scanner。
- 缺少测试记录表示工具未观察到测试，不等于一定没有运行测试。

## 测试与示例

测试使用临时 Git 仓库和 Fake GitHub Client。运行：

```bash
python -m pytest tests -k "audit_diff or agent_run or pr_summary or github_app or claim_check"
```
