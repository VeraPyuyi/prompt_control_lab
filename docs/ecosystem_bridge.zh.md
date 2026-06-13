# 生态桥接

Promptfoo、LangSmith 和 Langfuse 分别擅长 LLM 工程流程里的不同部分：

- Promptfoo：评测、红队测试、provider 矩阵、CI 和安全报告。
- LangSmith：trace、监控、在线评测、agent 轨迹调试和生产仪表盘。
- Langfuse：开源观测、prompt 管理、评测、成本跟踪和自托管部署。

`prompt_control_lab` 不应该替代它们。它更适合在这些工具的导出结果之上，增加一层论文式的 prompt optimization 证据审计。

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

## 成对样本规则

成对统计必须依赖共享样本 ID。Promptfoo 导出通常可以通过 `testIdx` 配对。Langfuse 和 LangSmith 的 observation / run id 往往每次实验都不同，所以 PCL 会优先使用稳定样本字段，例如 `example_id`、`dataset_item_id`、`reference_example_id`、`case_id` 或 `sample_id`。

如果没有任何共享 ID，PCL 会拒绝计算成对统计，而不是静默输出一个无效比较。

## 解读边界

示例文件故意很小。生成的 evidence card 可能会显示 `needs_review`，因为 4 条样本不足以支撑强统计结论。这是预期行为：PCL 应该把缺失证据暴露出来，而不是把 smoke test 包装成 benchmark。

如果要向团队解释生态关系，建议先打开 `bridge_summary.md`；如果要判断当前结果能安全声称什么，打开 `claim_check.md`；如果要审查具体 prompt
优化证据，再打开 `evidence_card.md`。
