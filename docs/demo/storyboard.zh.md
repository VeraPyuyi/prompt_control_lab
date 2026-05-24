# PromptControlLab 演示视频分镜（中文）

工作标题：PromptControlLab：面向 AI 编码 Agent 的预检、模型来源和可复现实验

目标时长：11:40。声音风格：冷静、技术型讲解。目标观众：使用 Claude Code、Cursor、Codex、shell wrapper 或 CI 运行 AI 编码 agent 的开发者。

定位边界：

- 先讲 agent prompt preflight、model provenance、reproducible prompt regression。
- `guard`、`gate` 和 `audit` 只提供本地证据和复核信号，不给出保证。
- 所有 artifact 都保留在本地，叙述只围绕工程证据展开。

## 场景 01 - 为什么需要 Preflight

时长：45 秒

画面：`docs/assets/tutorial_workflows.zh.png`

旁白：

PromptControlLab 放在 AI 编码 agent 的前后两侧。agent 执行前，它检查 prompt 是否清楚、范围是否收敛、是否符合本地 policy、token 成本是否可接受。agent 执行后，它记录模型身份、可复现实验证据、gate 状态、diff 审计信号和本地运行历史。它的目标不是证明 agent 一定安全，而是把一次性的主观感觉换成可检查的证据。

命令：

```bash
pcl start
```

画面决策：当 prompt 成本高、范围大、有风险，或需要留下可复现记录时，先使用 PromptControlLab。

## 场景 02 - 守护一个编码 Agent Prompt

时长：60 秒

画面：`docs/assets/tutorial_guard.zh.png`

旁白：

从开发者最容易直接发给 agent 的一句话开始：“修复这个 bug”。`guard` 命令会把这句模糊指令变成结构化 preflight 结果。它输出 action、risk level、原因、policy violation、是否需要复核、token 估算，以及改写后的 prompt。真正要做的决定是：直接发送、先修改，还是根据本地 policy 阻断。

命令：

```bash
pcl guard --prompt "修复这个 bug" --profile coding --policy examples/guard.policy.yaml --token-mode balanced --json
```

画面决策：`suggest` 表示先改写再发给 agent；`block` 表示本地 policy 要求停下来修改。

## 场景 03 - 在消耗 Token 前先 Improve

时长：55 秒

画面：`docs/assets/tutorial_guard.zh.png`

旁白：

`improve` 是更轻量的 preflight 路径。它用直接的语言改写 prompt，补上任务目标、输出格式、假设和稳定性要求，并估算 token 成本。如果连接到已有 run，它还可以结合诊断信息，例如退化的 slice 或失败样本。原始请求不危险、但太含糊时，这一步很适合放在昂贵 agent 任务之前。

命令：

```bash
pcl improve --prompt "回答下面的问题。"
pcl improve --prompt-file prompts/current.txt --run runs/quick --out runs/improve
```

画面决策：需要 policy 判断时用 `guard`；只需要直接改写时用 `improve`。

## 场景 04 - 本地 UI 工作流

时长：60 秒

画面：`docs/assets/tutorial_workflows.zh.png`

旁白：

本地 UI 把同一套流程放进可视化界面，不要求观众记住每条命令。工作流卡片从 guard 开始，接着是 quick report、gate、model drift、audit diff 和 history。这个 UI 是本地的：它读取当前工作树和 run 目录里的 artifact。它是检查证据的控制台，不是托管 dashboard。

命令：

```bash
pcl ui --run runs/quick
```

画面决策：当 reviewer 想先看同一份本地证据，而不是直接读 JSON 时，使用 UI。

## 场景 05 - Analyze：生成可复现 Run

时长：65 秒

画面：`docs/assets/tutorial_report.zh.png`

旁白：

`analyze` 是从样本数据到报告的最短路径。它生成可复现的 split，评测 baseline 和 candidate prediction，计算 metrics，做 paired statistics，写出 explanation，并生成 Markdown 和 HTML 报告。关键点是 prompt 变更会绑定输入文件、prediction 文件、split hash、metric 和输出 artifact。结果不再只是“感觉更好”。

命令：

```bash
pcl init --path demo
cd demo
pcl analyze --config promptcontrol.example.yaml --out runs/quick
```

画面决策：可复现 prompt 报告需要 data path、prediction path、split、metric、model identity 和 artifact path。

## 场景 06 - Gate 和 Report：把判断写清楚

时长：60 秒

画面：`docs/assets/tutorial_report.zh.png`

旁白：

分析完成后，report 给人看证据，gate 给自动化流程一个紧凑判断。gate policy 可以检查最低分数、最大退化、adjusted p-value、诊断风险和模型来源规则。gate 通过只表示配置的阈值通过了；它不证明 prompt 正确、安全或可以直接上线。如果置信区间跨过零，或者某个 slice 退化，判断里应该明确写出来。

命令：

```bash
pcl report --run runs/quick --title "Candidate Prompt Report"
pcl gate --run runs/quick --policy examples/gate.policy.yaml
```

画面决策：gate 结果是 policy outcome：`pass`、`needs_review` 或 `fail`。

## 场景 07 - Model Detect 和 Drift

时长：60 秒

画面：`docs/assets/tutorial_model_drift.zh.png`

旁白：

模型来源很重要，因为只有模型足够稳定，prompt 实验才容易解释。`model-detect` 记录 provider、公开 model id、source、confidence 和 warning。`model-drift` 把当前 run 和历史 run 比较，标记结果是 prompt-only、因为缺少模型身份而不确定，还是已经被模型或 provider 变化污染。它记录公开身份证据，但不证明供应商内部隐藏权重版本。

命令：

```bash
pcl model-detect --predictions examples/predictions_candidate.jsonl
pcl model-drift --run runs/current --history runs/previous --out runs/current/model_drift.json
```

画面决策：如果模型变了，就把结果称为 model-plus-prompt comparison。

## 场景 08 - Agent 执行后的 Audit Diff

时长：55 秒

画面：`docs/assets/tutorial_audit.zh.png`

旁白：

agent 改完文件之后，用 `audit-diff` 总结到底发生了什么。它统计 source、test、docs、config、workflow、dependency 和 generated files，标记删除测试、危险路径、脱敏后的 secret finding、可能的 public API change、expected path mismatch，以及测试命令状态。这是 review triage，帮助人先看最关键的证据。

命令：

```bash
pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit
pcl audit-diff --before main --after HEAD --expected-path src/promptcontrollab --out runs/audit
```

画面决策：audit diff 解释 agent 改了什么；除非提供 expected path，它不会假装知道原始任务意图。

## 场景 09 - History：持续比较 Run

时长：55 秒

画面：`docs/assets/tutorial_history.zh.png`

旁白：

`history` 把分散的 run 目录变成本地索引。它记录 manifest、模型身份、prompt identity、metrics、gate status、risk categories 和 artifact path。compare 模式会说明新 run 是否改变了 prompt、模型、分数、gate 结果、slice 表现或风险轮廓。这样 prompt 工作会变成一串可复核的变更，而不是彼此断开的实验。

命令：

```bash
pcl history index --runs runs/ --out runs/history_index.json
pcl history compare --a runs/old --b runs/new --out runs/history_compare.json
```

画面决策：history 是 prompt identity、model provenance、gate status 和 run artifact 的本地账本。

## 场景 10 - Plugins、Skills 和 CI

时长：60 秒

画面：`docs/assets/tutorial_workflows.zh.png`

旁白：

PromptControlLab 可以放在 prompt 进入工作流的位置。Claude Code hook、Cursor rule 和 MCP-style tool、Codex skill、shell wrapper，以及 GitHub Action 模板，都可以调用同一组本地命令。适配器稳定读取的字段包括 action、risk level、token report、plain summary、gate status 和 audit summary。CI 可以运行 analyze，执行 gate，并把 audit 证据附到 pull request。

命令：

```bash
pcl install-plugin codex
pcl install-plugin cursor
pcl install-plugin claude-code
pcl install-plugin github-action
```

画面决策：adapter 应该读取结构化字段，同时保留给人看的 summary。

## 场景 11 - 研究诊断：Soft-Hard、Trajectory、Riccati、TV-Soft

时长：70 秒

画面：`docs/assets/tutorial_report.zh.png`

旁白：

高级命令面向 prompt optimization research。`soft-hard` 检查学到的 soft vector 是否能干净地投影到真实 token embedding。`trajectory` 总结 hidden-state drift 和类似稳定性的信号。`riccati` 拟合有限维 surrogate，并报告这个 surrogate 的 closed-loop stability，而不是完整语言模型的稳定性。`tv-soft` 比较 static、time-varying、shuffled 和 random control lane，用来判断收益是否更符合时序结构。

命令：

```bash
pcl soft-hard --soft soft_prompt.npz --vocab vocab_embeddings.npz --out runs/candidate/diagnostics
pcl trajectory --states hidden_states.npz --out runs/candidate/diagnostics
pcl riccati --trajectory hidden_states.npz --out runs/candidate/diagnostics
pcl tv-soft --predictions scored_methods.jsonl --out runs/candidate/diagnostics
```

画面决策：研究诊断是解释和后续实验的证据，不是部署保证。

## 场景 12 - 端到端复核循环

时长：55 秒

画面：`docs/assets/tutorial_workflows.zh.png`

旁白：

完整循环很直接：先 preflight prompt，必要时 improve，再运行 agent；之后 analyze prompt 变更，记录 model provenance，执行 gate，审计 diff，并和 history 比较。每一步都会产生别人可以检查的文件。最后回到项目定位：本地 agent preflight、model provenance 和 reproducible prompt evaluation。

命令：

```bash
pcl guard --prompt "修复这个 bug" --profile coding --policy examples/guard.policy.yaml --json
pcl analyze --config promptcontrol.example.yaml --out runs/quick
pcl gate --run runs/quick --policy examples/gate.policy.yaml
pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit
```

画面决策：交付 artifact package，而不只是交付一句结论。
