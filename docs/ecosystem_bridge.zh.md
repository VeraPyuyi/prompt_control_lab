# Ecosystem Bridge：连接 Promptfoo、DeepEval、Langfuse 和 LangSmith

`prompt_control_lab` 不需要替代 Promptfoo、DeepEval、Langfuse 或 LangSmith。
更好的用法是：先让这些工具负责它们擅长的 eval、red-team、tracing、observability，
再把导出结果交给 PCL，补上 prompt optimization 的研究证据层。

## 一句话定位

外部工具回答“模型或应用表现如何”；PCL 继续追问：

- baseline / candidate 是否真的是同一批样本上的成对比较？
- model、provider、metric、split 或 prompt identity 是否变化？
- candidate 提升是否有成对统计证据？
- 当前证据最多能支持什么 prompt optimization claim？
- 要声称完整论文诊断，还缺哪些 soft-hard、trajectory、Riccati 或 tv-soft artifact？
- 分享出去的 research bundle 后来有没有被修改？

## 最快体验

使用仓库自带的外部工具样例：

```bash
pcl ecosystem-demo --examples examples/external --out runs/ecosystem-demo
```

得到什么：

- `runs/ecosystem-demo/ecosystem_scorecard.html`
- 每个工具目录里的 `bridge_summary.html`
- `research_bundle.html`
- `evidence_card.html`
- `claim_check.html`
- `research_gap_status.html`
- `research_bundle_verification.html`

说明什么问题：你可以看到 Promptfoo、DeepEval、Langfuse、LangSmith 风格导出分别提供了
什么证据，PCL 又补了哪些成对统计、prompt-only validity、claim check 和论文诊断缺口。

## 一条命令做完整外部证据审计

当你已经有外部工具导出的 baseline / candidate 结果时，运行：

```bash
pcl evidence-audit \
  --tool promptfoo \
  --baseline-input results.json \
  --candidate-input results.json \
  --baseline-prompt-id baseline \
  --candidate-prompt-id candidate \
  --provider openai:gpt-4o-mini-20260601 \
  --split-hash eval-split-2026-06 \
  --out runs/from-promptfoo-audit
```

得到什么：

- `evidence_audit_result.html` / `.md` / `.json`
- `bridge_summary.html` / `.md` / `.json`
- `research_bundle.html` / `.json`
- `source_input_verification.html` / `.md` / `.json`
- `research_bundle_verification.html` / `.md` / `.json`
- `research_gap_status.html` / `.md` / `.json`
- `evidence_card.html`
- `claim_check.html`
- `comparison/` 目录下的 stats、validity 和 report
- `imports/` 目录下的 baseline / candidate 导入快照

说明什么问题：这条命令把外部 eval / trace 导出转换成一个可审查的 PCL evidence bundle，
同时告诉你还缺哪些论文诊断、原始外部导出文件的哈希是否仍然匹配，以及当前证据包的
哈希验证是否通过。

人工审查建议先打开 `evidence_audit_result.html`；自动化流程读取
`evidence_audit_result.json`。

审计结果还会记录外部 baseline 和 candidate 导出文件的 source input provenance：
原始路径、路径类型、解析后的绝对路径、字节数、SHA-256 哈希、检测到的工具名和导入行数。
这样 reviewer 即使后续换了工作目录，也可以确认 PCL 证据包到底基于哪两个外部导出文件生成。
如果后续需要重新确认这些原始导出文件没有被替换或改动，可以运行：

```bash
pcl source-verify --run runs/from-promptfoo-audit
```

`pcl evidence-audit` 已经会写出 `source_input_verification.json`、`.md` 和 `.html`；
单独的 `source-verify` 命令用于后续刷新这项检查。它检查外部源文件本身；
`pcl research-bundle --verify` 检查由这些源文件生成的 PCL 证据 artifact。
当这项检查需要作为 CI 门禁时，使用 strict 模式：

```bash
pcl source-verify --run runs/from-promptfoo-audit --strict
```

strict 模式仍会写出同样的 JSON、Markdown 和 HTML 证据，但只要任何 source export 被改动、
缺失或无法检查，就会返回非零退出码。

## 更低层的桥接命令

如果你希望分步骤控制，可以先导入外部结果：

```bash
pcl import auto --input results.json --out runs/from-external --score-name exact_match
```

`pcl import` 是更直白的外部证据导入入口；`pcl ingest` 仍作为旧脚本兼容别名保留。

也可以使用明确的导入器：

```bash
pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate

pcl import langfuse --input langfuse-export.json --out runs/from-langfuse \
  --name candidate --score-name exact_match

pcl import langsmith --input langsmith-runs.csv --out runs/from-langsmith \
  --experiment candidate --score-name exact_match

pcl import deepeval --input deepeval-test-run.json --out runs/from-deepeval \
  --score-name exact_match
```

再把两个导入后的 run 比较成一个证据包：

```bash
pcl compare-runs \
  --baseline runs/from-promptfoo-baseline \
  --candidate runs/from-promptfoo-candidate \
  --out runs/from-promptfoo-comparison

pcl evidence-card \
  --run runs/from-promptfoo-comparison \
  --out runs/from-promptfoo-comparison/evidence_card.md

pcl claim-check \
  --run runs/from-promptfoo-comparison \
  --claim paired \
  --out runs/from-promptfoo-comparison/claim_check.json
```

## 每类工具的分工

| 工具 | 它擅长什么 | PCL 补什么 |
|---|---|---|
| Promptfoo | LLM eval、red-team、安全测试、CI、provider 覆盖。 | 成对统计、prompt-only validity、claim check、论文诊断缺口和可验证 evidence bundle。 |
| DeepEval | 本地 eval runner、metric、测试风格输出。 | 把测试结果升级为 prompt optimization 证据卡片和 claim 边界。 |
| Langfuse | tracing、prompt management、eval、成本追踪、自托管 observability。 | 对导出结果补 soft-hard、trajectory、Riccati、tv-soft 等研究诊断路径。 |
| LangSmith | agent tracing、experiment、dataset、online/offline eval。 | 检查实验导出是否能支持干净 prompt-only 比较和统计可靠结论。 |

## 打开哪个文件

- `evidence_audit_result.html`：完整一键审计摘要，建议人工审查先看。
- `bridge_summary.html`：外部工具和 PCL 的分工说明。
- `research_bundle.html`：证据包目录和 artifact 哈希索引。
- `evidence_card.html`：prompt optimization 证据卡片。
- `claim_check.html`：当前证据能安全支持的 claim。
- `research_gap_status.html`：论文诊断缺口是否已补齐。
- `research_bundle_verification.html`：证据包哈希是否仍然匹配。

如果要把 bundle 哈希验证作为 CI 或 reviewer gate，可以使用 strict 模式：

```bash
pcl research-bundle --run runs/ecosystem-demo --verify --strict
```

strict 模式仍会写出 `research_bundle_verification.json`、`.md` 和 `.html`，然后在证据文件
被改动、缺失或无法检查时返回非零退出码。

## 解读边界

示例文件通常很小，所以 evidence card 或 claim check 显示 `needs_review` 是正常的。
这不是失败，而是 PCL 的核心设计：把缺失证据暴露出来，避免把 smoke test 包装成
benchmark 或完整论文结论。

PCL 的目标不是更大、更全，而是更审慎、更可复现。它应该成为外部 eval /
observability 工具之后的研究证据层。
