# PromptControlLab Demo Pack

这份文档用于展示 `prompt_control_lab` 的三个最容易被用户理解的价值点：

1. 一个 2 分钟 demo 脚本。
2. 一个 Claude Code / Cursor 的真实接入案例。
3. 一个 before/after 数据表与可复现实验模板。

定位一句话：

> PromptControlLab 是给 AI 编程代理使用的轻量 prompt 预检与回归报告工具。

---

## 1. 两分钟 demo 脚本

### 标题

**PromptControlLab：给 AI 编程代理使用的 Prompt 预检层**

### 0:00--0:15 痛点

展示原始指令：

```text
Fix this bug.
```

旁白：

> 很多 AI 编程失败不是因为模型完全不会，而是因为输入太模糊。模型不知道该改哪个文件、该跑哪些测试、哪些内容不能动。

### 0:15--0:45 使用 `pcl guard`

```bash
pcl guard --prompt "Fix this bug" --profile coding --token-mode balanced
```

重点展示输出：

```text
Action: suggest
Risk: medium
Improved prompt: ...
Estimated token cost: ...
```

旁白：

> `pcl guard` 在 agent 执行前检查 prompt，给出风险等级、改写版本、原因和 token 估算。

### 0:45--1:10 给 IDE 或 agent 使用 JSON

```bash
echo "Refactor this module" | pcl guard --stdin --profile coding --json
```

旁白：

> JSON 输出可以接入 Claude Code hook、Cursor 规则、MCP-style server 或 shell wrapper。

### 1:10--1:40 生成回归报告

```bash
pcl init --path demo
cd demo
pcl analyze --config promptcontrol.example.yaml --out runs/quick
```

展示产物：

```text
runs/quick/report.md
runs/quick/report.html
runs/quick/stats.json
runs/quick/explanation.json
```

旁白：

> Prompt 改动不能只凭感觉。`pcl analyze` 会把 baseline 和 candidate 的结果变成可复查报告。

### 1:40--2:00 总结

```text
Before: vague prompt -> risky agent execution
After: guarded prompt -> clearer task and test focus
Report: prompt change -> reproducible evidence
```

---

## 2. Claude Code / Cursor 接入案例

### 使用场景

原始 prompt：

```text
Fix this bug.
```

问题：

- 没有目标文件。
- 没有失败现象。
- 没有测试要求。
- 没有修改边界。

接入后，先运行：

```bash
pcl guard --prompt "Fix this bug" --profile coding --token-mode balanced --json
```

然后把返回的 `improved_prompt` 交给 Claude Code、Cursor 或 Codex。

### Claude Code

仓库提供的 hook 文件：

```text
plugins/claude-code/hooks/prompt_guard.py
```

手动测试：

```powershell
'{"hook_event_name":"UserPromptSubmit","prompt":"Fix this bug"}' |
  python plugins\claude-code\hooks\prompt_guard.py --mode suggest --profile coding
```

预期结果：输出包含 `additionalContext`，用于把 prompt guard 建议注入到 Claude Code 上下文中。

### Cursor

项目级规则接入：

```powershell
New-Item -ItemType Directory -Force .cursor\rules
Copy-Item plugins\cursor\rules\prompt_control_lab.mdc .cursor\rules\prompt_control_lab.mdc
```

MCP-style server：

```bash
python plugins/cursor/mcp_server.py
```

预期结果：Cursor 可以调用 `guard_prompt`，读取 `plain_summary`、`risk_level`、`improved_prompt` 和 `token_report`。

### Before / After 示例

Before：

```text
Fix this bug.
```

After：

```text
Fix the reported bug with the smallest safe code change.

Before editing:
1. Identify the failing behavior and relevant files.
2. State the likely root cause.
3. List the tests you will run.

Constraints:
- Do not refactor unrelated code.
- Do not change public APIs unless necessary.
- Keep the patch minimal and explain every changed file.

After editing:
1. Run the relevant tests.
2. Summarize the fix.
3. Mention any remaining uncertainty.
```

---

## 3. Before / After 表

### 3.1 内置示例项目 smoke result

运行：

```bash
pcl init --path demo
cd demo
pcl analyze --config promptcontrol.example.yaml --out runs/quick
```

内置示例结果：

| id | slice | expected | baseline output | candidate output | baseline correct | candidate correct |
|---|---|---:|---:|---:|---:|---:|
| arith-1 | arithmetic | 4 | 4 | 4 | yes | yes |
| arith-2 | arithmetic | 7 | 6 | 7 | no | yes |
| format-1 | format | POSITIVE | POSITIVE | POSITIVE | yes | yes |
| format-2 | format | NEGATIVE | negative | NEGATIVE | no | yes |

汇总：

| metric | baseline | candidate | delta |
|---|---:|---:|---:|
| exact match overall | 2/4 = 0.50 | 4/4 = 1.00 | +0.50 |
| arithmetic slice | 1/2 = 0.50 | 2/2 = 1.00 | +0.50 |
| format slice | 1/2 = 0.50 | 2/2 = 1.00 | +0.50 |
| fixed examples | - | arith-2, format-2 | 2 fixed |
| broken examples | - | none | 0 broken |

说明：这是 smoke test，不是大规模 benchmark。它证明工具链可以从数据、预测、统计到报告完整跑通。

### 3.2 真实 agent prompt guard pilot 表

建议收集 20--50 个真实 coding-agent prompt。每个任务跑两次：

- Before：原始 prompt 直接交给 agent。
- After：先用 `pcl guard --profile coding` 改写，再交给 agent。

记录模板：

| task id | prompt type | guard action | risk level | raw success | guarded success | raw touched files | guarded touched files | raw tests passed | guarded tests passed | note |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---|
| bug-001 | vague bug fix | suggest | medium | no | yes | 8 | 3 | no | yes | guard forced target-file and test plan |
| refactor-002 | broad refactor | review | high | no | review | 15 | - | no | - | scope too broad |
| test-003 | test generation | auto | low | yes | yes | 2 | 2 | yes | yes | small prompt change |

公开汇总时建议用：

| measurement | before raw prompts | after `pcl guard` | desired direction |
|---|---:|---:|---|
| task success rate | TBD | TBD | higher |
| average touched files | TBD | TBD | lower or more focused |
| tests passed | TBD | TBD | higher |
| prompts sent to review | 0 | TBD | nonzero for risky prompts |
| average prompt token estimate | TBD | TBD | controlled |
| human intervention count | TBD | TBD | lower |

谨慎表述：

> The built-in smoke test demonstrates the reproducible evaluation pipeline. The agent prompt-guard table is a pilot protocol for measuring real Claude Code/Cursor usage. We do not claim a universal success-rate improvement until a larger real-task benchmark is run.

---

## 4. README 推荐插入段落

英文 README：

```markdown
## Demo Pack

New to the project? Start with the demo pack:

- [2-minute demo script, agent integration case, and before/after table](docs/demo_pack.en.md)
- [中文 Demo Pack：2 分钟演示、真实接入案例与 Before/After 表](docs/demo_pack.zh.md)

The demo pack shows the intended product story: use `pcl guard` as a preflight layer before Claude Code/Cursor/Codex, then use `pcl analyze` to turn prompt changes into reproducible reports.
```

中文 README：

```markdown
## Demo Pack

第一次了解项目，可以先看 Demo Pack：

- [中文 Demo Pack：2 分钟演示、真实接入案例与 Before/After 表](docs/demo_pack.zh.md)
- [English demo pack: 2-minute script, agent integration case, and before/after table](docs/demo_pack.en.md)

Demo Pack 展示的是项目最容易被业界理解的产品故事：先用 `pcl guard` 作为 Claude Code / Cursor / Codex 前面的 prompt preflight 层，再用 `pcl analyze` 把 prompt 改动变成可复查报告。
```
