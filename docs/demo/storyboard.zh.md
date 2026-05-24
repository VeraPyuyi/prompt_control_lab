# prompt_control_lab 中文演示视频分镜

工作标题：prompt_control_lab：AI 编码 Agent 的执行前门禁、模型溯源和可复现评测

目标时长：约 11 分 40 秒。声音风格：更自然的中文技术教程讲解，短句、轻停顿、少念稿感。

定位边界：

- 重点展示本地 agent preflight、model provenance、reproducible prompt regression 和 agent audit。
- `guard`、`gate` 和 `audit` 是启发式预检和治理信号，不是安全证明。
- 所有 artifact 留在本地，视频只围绕开源工具的工程使用展开。

## 场景 01 - 为什么需要 Preflight

时长：45 秒

画面：`docs/assets/tutorial_workflows.zh.png`

旁白：

先看这张工作台。PromptControlLab 放在 AI 编码 agent 的前后两侧。agent 动手前，先做预检：指令清不清楚，范围会不会太大，有没有触碰团队 policy，token 成本是否合理。agent 改完后，再留下证据：模型身份、评测结果、gate 状态、diff 审计和历史记录。它不是安全证明，而是把感觉变成可复核的记录。

命令：

```bash
pcl start
```

## 场景 02 - 守护一个编码 Agent Prompt

时长：60 秒

画面：`docs/assets/tutorial_guard.zh.png`

旁白：

我们从最常见的一句话开始：修复这个 bug。直接交给 agent，范围太宽。运行 guard 以后，工具会给出 action、risk level、policy violation、是否需要复核、token 估算，以及一版更可执行的 prompt。你要判断的是：现在可以发给 agent，还是先补充目标文件、失败现象和测试命令。

命令：

```bash
pcl guard --prompt "修复这个 bug" --profile coding --policy examples/guard.policy.yaml --token-mode balanced --json
```

## 场景 03 - 在消耗 Token 前先 Improve

时长：55 秒

画面：`docs/assets/tutorial_guard.zh.png`

旁白：

如果你只是想让 prompt 更清楚，就用 improve。它不调用大模型，也不做复杂搜索，只根据规则和已有报告改写指令。它会补上任务目标、输出格式、约束条件和稳定性提示。适合在真正花 token 之前，先把一句模糊的话整理成 agent 更容易执行的版本。

命令：

```bash
pcl improve --prompt "回答下面的问题。"
pcl improve --prompt-file prompts/current.txt --run runs/quick --out runs/improve
```

输出文件：

- `runs/improve/improved_prompt.txt`
- `runs/improve/prompt_improvement.json`
- `runs/improve/prompt_diff.md`

## 场景 04 - 本地 UI 工作流

时长：60 秒

画面：`docs/assets/tutorial_workflows.zh.png`

旁白：

本地 UI 把这些命令放进一个可视化工作台。左侧选择语言、runs 目录和 policy。中间的工作流卡片可以运行 guard、analyze、gate、audit diff、agent run 和 PR summary。所有文件都留在本地项目里。它不是托管服务，而是给团队 reviewer 用的本地控制台。

命令：

```bash
pcl ui --run runs/quick
```

## 场景 05 - Analyze：生成可复现 Run

时长：65 秒

画面：`docs/assets/tutorial_report.zh.png`

旁白：

接下来做一次可复现评测。analyze 会生成 split，读取 baseline 和 candidate prediction，计算 metrics，做 paired statistics，然后写出 explanation、report.md 和 report.html。重点不是只看一个分数，而是把数据路径、split hash、metric、模型信息和输出 artifact 一起记录下来。

命令：

```bash
pcl init --path demo
cd demo
pcl analyze --config promptcontrol.example.yaml --out runs/quick
```

输出文件：

- `runs/quick/splits.json`
- `runs/quick/stats.json`
- `runs/quick/explanation.json`
- `runs/quick/report.md`
- `runs/quick/report.html`

## 场景 06 - Gate 和 Report：把判断写清楚

时长：60 秒

画面：`docs/assets/tutorial_report.zh.png`

旁白：

report 给人看，gate 给自动化流程看。gate policy 可以检查最低分数、最大退化、adjusted p-value、诊断风险，以及模型来源规则。如果 gate 通过，只说明这套阈值通过了；它不等于 prompt 一定正确，也不等于可以不复核。这个边界要说清楚。

命令：

```bash
pcl report --run runs/quick --title "Candidate Prompt Report"
pcl gate --run runs/quick --policy examples/gate.policy.yaml
```

输出文件：

- `runs/quick/gate_result.json`
- `runs/quick/report.md`
- `runs/quick/report.html`

## 场景 07 - Model Detect 和 Drift

时长：60 秒

画面：`docs/assets/tutorial_model_drift.zh.png`

旁白：

很多 prompt 问题，其实是模型变了。model detect 会记录 provider、公开 model id、来源和 warning。model drift 会比较当前 run 和历史 run：模型是否一致，provider 是否变化，是否使用 alias，比较是不是干净的 prompt-only comparison。这样排查问题时不用靠猜。

命令：

```bash
pcl model-detect --predictions examples/predictions_candidate.jsonl
pcl model-drift --run runs/current --history runs/previous --out runs/current/model_drift.json
```

输出文件：

- `runs/current/model_drift.json`

## 场景 08 - Agent 执行后的 Audit Diff

时长：55 秒

画面：`docs/assets/tutorial_audit.zh.png`

旁白：

agent 改完代码后，看 audit diff。它会统计 source、test、docs、config、workflow、dependency 和 generated file。还会标记危险路径、删除测试、疑似 secret、public API change、expected path mismatch 和测试结果。这个页面最适合做代码审查前的第一轮 triage。

命令：

```bash
pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit
pcl audit-diff --before main --after HEAD --expected-path src/promptcontrollab --out runs/audit
```

输出文件：

- `runs/audit/audit_result.json`
- `runs/audit/audit_summary.md`

## 场景 09 - History：持续比较 Run

时长：55 秒

画面：`docs/assets/tutorial_history.zh.png`

旁白：

单次报告解决一次问题，history 解决连续追踪。它把多个 run 目录整理成本地索引，记录 prompt identity、model identity、metrics、gate status、risk categories 和 artifact path。compare 模式会告诉你，新 run 到底是 prompt 变了、模型变了、分数变了，还是风险轮廓变了。

命令：

```bash
pcl history index --runs runs/ --out runs/history_index.json
pcl history compare --a runs/old --b runs/new --out runs/history_compare.json
```

输出文件：

- `runs/history_index.json`
- `runs/history_compare.json`

## 场景 10 - Plugins、Skills 和 CI

时长：60 秒

画面：`docs/assets/tutorial_workflows.zh.png`

旁白：

这个工具也可以接到日常工作流里。Claude Code hook、Cursor rule 和 MCP-style adapter、Codex skill、shell wrapper，以及 GitHub Action 模板，都围绕同一个 guard JSON 输出工作。也就是说，CLI、IDE 和 CI 看到的是同一套 action、risk、token report 和 audit summary。

命令：

```bash
pcl install-plugin codex
pcl install-plugin cursor
pcl install-plugin claude-code
pcl install-plugin github-action
```

输出文件：

- `.github/workflows/prompt-control-lab-gate.yml`

## 场景 11 - 研究诊断：Soft-Hard、Trajectory、Riccati、TV-Soft

时长：70 秒

画面：`docs/assets/tutorial_report.zh.png`

旁白：

高级研究命令放在后面。soft-hard 看 soft prompt 投影成真实 token 后损失多大。trajectory 看 hidden-state drift 和稳定性信号。riccati 只分析拟合出来的有限维 surrogate，不宣称证明完整语言模型稳定。tv-soft 用来比较 static、time-varying、shuffled 和 random control lane。

命令：

```bash
pcl soft-hard --soft soft_prompt.npz --vocab vocab_embeddings.npz --out runs/candidate/diagnostics
pcl trajectory --states hidden_states.npz --out runs/candidate/diagnostics
pcl riccati --trajectory hidden_states.npz --out runs/candidate/diagnostics
pcl tv-soft --predictions scored_methods.jsonl --out runs/candidate/diagnostics
```

输出文件：

- `runs/candidate/diagnostics/soft_hard.json`
- `runs/candidate/diagnostics/trajectory.json`
- `runs/candidate/diagnostics/riccati.json`
- `runs/candidate/diagnostics/tv_soft.json`

## 场景 12 - 端到端复核循环

时长：55 秒

画面：`docs/assets/tutorial_workflows.zh.png`

旁白：

最后把流程串起来：先 guard 或 improve prompt，再运行 agent。之后 analyze 评测变化，记录 model provenance，运行 gate，审计 diff，最后放进 history 比较。每一步都会产生别人能打开检查的文件。这就是 prompt_control_lab 的核心：执行前门禁、模型溯源、可复现评测和 agent 审计。

命令：

```bash
pcl guard --prompt "修复这个 bug" --profile coding --policy examples/guard.policy.yaml --json
pcl analyze --config promptcontrol.example.yaml --out runs/quick
pcl gate --run runs/quick --policy examples/gate.policy.yaml
pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit
```
