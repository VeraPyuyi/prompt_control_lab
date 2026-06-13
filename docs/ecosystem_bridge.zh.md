# 生态桥接

Promptfoo、DeepEval、LangSmith 和 Langfuse 分别擅长 LLM 工程流程里的不同部分：

- Promptfoo：评测、红队测试、provider 矩阵、CI 和安全报告。
- DeepEval：本地 LLM test run、metric 分数、reason 和 CI 风格评测 artifact。
- LangSmith：trace、监控、在线评测、agent 轨迹调试和生产仪表盘。
- Langfuse：开源观测、prompt 管理、评测、成本跟踪和自托管部署。

`prompt_control_lab` 不应该替代它们。它更适合在这些工具的导出结果之上，增加一层论文式的 prompt optimization 证据审计。

## PCL 可以赢在哪里

最强路线不是做一个更大的 dashboard，而是做一个更窄、更深的证据层：

| 工具 | 最强能力 | PCL 的互补位置 |
|---|---|---|
| Promptfoo | LLM eval、红队 / 安全测试、provider 矩阵、CI 和安全报告。 | 导入 Promptfoo 评测结果之后，补上成对不确定性、prompt-only 有效性、evidence card、claim check 和论文诊断缺口闭环。 |
| DeepEval | 本地 LLM test run、metric 分数、reason 和 CI 风格评测 artifact。 | 导入 DeepEval TestRun JSON 之后，补上成对 prompt 证据、协议卫生、claim scope 检查和论文诊断缺口计划。 |
| LangSmith | Agent tracing、observability、在线 / 离线评测、部署和 sandbox。 | 把 LangSmith experiment export 变成 prompt optimization 证据包，区分 prompt 效果和 model、metric、split 等混杂因素。 |
| Langfuse | 开源 observability、prompt management、evaluation、成本跟踪和自托管 trace。 | 补上观测平台通常不覆盖的研究诊断：soft-hard gap、hidden-state trajectory、Riccati surrogate 和 time-varying control evidence。 |

实际集成路线是：

1. 继续用外部工具做它擅长的事：收集 trace、跑 eval、做 red-team 或管理 prompt version。
2. 导出 baseline / candidate 结果。
3. 用 `pcl evidence-from` 生成本地证据包。
4. 用 `pcl diagnose` 和 `pcl gap-status` 检查论文诊断证据哪些已有、哪些缺失、哪些已经补齐。
5. 用 `claim_check.md` 判断当前结果到底能支持多强的 prompt optimization 结论。

这样 PCL 的定位会更清楚：**prompt optimization 的研究级证据层**，不是又一个泛 LLMOps 平台。

## PCL 增加了什么

导入外部 baseline / candidate export 之后，PCL 会写出：

- `imports/baseline/` 和 `imports/candidate/`：把外部数据转换成 PCL scored run 的可复现快照。
- `comparison/stats.json`：成对 bootstrap CI、成对 permutation p-value 和 Holm-adjusted p-value。
- `comparison/comparison_validity.json`：检查 prompt identity、model identity、split hash、metric identity、统计证据和 slice regression。
- `evidence_card.md/json`：给 reviewer 快速阅读的证据卡。
- `claim_check.md/json`：直接说明当前 evidence tier 最多能支持哪一层 claim scope。
- `bridge_summary.md/json`：简短说明外部工具提供了什么、PCL 补了什么、还缺哪些证据。
- `report.html`：可以和本次 run 一起归档的本地报告。

这条桥接链路适合这些问题：

- baseline / candidate 是否按同一批样本成对比较？
- model、provider、metric 或 split 是否变化过？
- 观察到的提升在统计上是否可靠？
- 在声称 prompt 优化有效之前，还缺哪些证据？

## 一键示例

仓库已经在 `examples/external/` 放了这些文件。用
`pcl init --path demo` 创建的新 demo 项目也会在
`demo/examples/external/` 写出同样的样例，所以 wheel 或 `pipx`
用户不需要 clone 源码，也能直接试用这条桥接链路。

一次性运行多种外部工具的桥接示例：

```bash
pcl ecosystem-demo --examples examples/external --out runs/ecosystem-demo
```

这个命令会写出 `runs/ecosystem-demo/README.md`、`ecosystem_demo.json`、
`ecosystem_scorecard.html`、`ecosystem_scorecard.md`、`ecosystem_scorecard.json`、
`research_diagnostics.md`、`research_diagnostics.json`，并为每个外部工具生成一套
evidence bundle：

- `runs/ecosystem-demo/promptfoo/`
- `runs/ecosystem-demo/langfuse/`
- `runs/ecosystem-demo/langsmith/`
- `runs/ecosystem-demo/deepeval/`

如果要向团队解释定位，建议先打开根目录里的 `ecosystem_scorecard.html`。它会按工具列出：
外部工具擅长什么、PCL 补了什么、还缺哪些论文诊断。`ecosystem_scorecard.md` 仍适合
纯文本 review。然后再打开每个目录里的 `bridge_summary.md` 看工具级 provenance。
也可以用 `pcl ui --runs runs/ecosystem-demo` 打开根目录；Research Overview
会按外部工具逐行展示每套 evidence bundle。

如果后续修改了某个 bridge bundle，或者重新跑了诊断，可以不用重建整个 demo，直接刷新跨工具定位表：

```bash
pcl ecosystem-scorecard --run runs/ecosystem-demo
```

如果想把定位表另存给 reviewer，可以加 `--out <文件或目录>`。

demo 会自动按论文证据地图审计整套 bundle。如果之后手动改过 bundle，可以重新运行：

```bash
pcl diagnose --run runs/ecosystem-demo
```

这会在根目录写出 `research_diagnostics.json` 和 `research_diagnostics.md`。
对于外部工具导出，`diagnose` 会报告已有证据和缺失的研究诊断；它不会伪造
hidden-state、soft-hard、Riccati 或 time-varying-control 测量结果。
完成这一步后，`pcl ui --runs runs/ecosystem-demo` 的 Research Overview 也会显示
论文证据缺口表。报告还会给出一张补齐表，写明需要准备哪些输入、可以复制哪条
`pcl` 命令、会生成哪个 artifact，以及这个 artifact 能说明什么问题。需要交接给团队成员
时，可以直接打开 `research_gap_plan.md`；配套的 `research_gap_commands.ps1` 和 `.sh`
是 review-first 命令脚本。UI 会把同一份计划和脚本列表作为研究总览里的独立区域展示。

Promptfoo：

```bash
pcl evidence-from \
  --tool promptfoo \
  --baseline-input examples/external/promptfoo_results.json \
  --candidate-input examples/external/promptfoo_results.json \
  --baseline-prompt-id baseline \
  --candidate-prompt-id candidate \
  --provider openai:gpt-4o-mini-20260601 \
  --split-hash external-demo-split \
  --out runs/from-promptfoo-evidence
```

Langfuse：

```bash
pcl evidence-from \
  --tool langfuse \
  --baseline-input examples/external/langfuse_export.json \
  --candidate-input examples/external/langfuse_export.json \
  --baseline-name baseline \
  --candidate-name candidate \
  --score-name exact_match \
  --model gpt-4o-mini-20260601 \
  --provider openai \
  --split-hash external-demo-split \
  --out runs/from-langfuse-evidence
```

LangSmith：

```bash
pcl evidence-from \
  --tool langsmith \
  --baseline-input examples/external/langsmith_runs.csv \
  --candidate-input examples/external/langsmith_runs.csv \
  --baseline-experiment baseline \
  --candidate-experiment candidate \
  --score-name exact_match \
  --model gpt-4o-mini-20260601 \
  --provider openai \
  --split-hash external-demo-split \
  --out runs/from-langsmith-evidence
```

DeepEval：

```bash
pcl evidence-from \
  --tool deepeval \
  --baseline-input examples/external/deepeval_baseline.json \
  --candidate-input examples/external/deepeval_candidate.json \
  --score-name exact_match \
  --model gpt-4o-mini-20260601 \
  --provider openai \
  --split-hash external-demo-split \
  --out runs/from-deepeval-evidence
```

## 成对样本规则

成对统计必须依赖共享样本 ID。Promptfoo 导出通常可以通过 `testIdx` 配对。Langfuse 和 LangSmith 的 observation / run id 往往每次实验都不同，所以 PCL 会优先使用稳定样本字段，例如 `example_id`、`dataset_item_id`、`reference_example_id`、`case_id` 或 `sample_id`。

如果没有任何共享 ID，PCL 会拒绝计算成对统计，而不是静默输出一个无效比较。

## 解读边界

示例文件故意很小。生成的 evidence card 可能会显示 `needs_review`，因为 4 条样本不足以支撑强统计结论。这是预期行为：PCL 应该把缺失证据暴露出来，而不是把 smoke test 包装成 benchmark。

如果要向团队解释生态关系，建议先打开 `bridge_summary.md`；如果要判断当前结果能安全声称什么，打开 `claim_check.md`；如果要审查具体 prompt
优化证据，再打开 `evidence_card.md`。
