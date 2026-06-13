# 产物说明

prompt_control_lab 的核心思路是：每次运行都应该留下可复查的文件，而不是只留下一个最终分数。

## `manifest.json`

记录工具版本、运行模式、方法名、metric、数据路径、prediction 路径、可选的模型身份信息，
以及可选的 prompt identity：`prompt_hash`、`prompt_id`、`prompt_file`、`prompt_version`。

说明什么问题：以后看到一个分数时，可以知道它是怎么来的，也能知道记录中的公开 model id 是什么。
Quick Mode 做成对 prompt 实验时，顶层 manifest 还可以包含 `baseline_prompt` 和
`candidate_prompt`；两个子 run 的 manifest 会分别保存自己的 `prompt` identity，供
`pcl validity` 检查 prompt-only 比较是否成立。

## `splits.json`

记录 train、validation、withheld 的样本 id、split hash、seed、数量和 leakage report。

说明什么问题：数据是否被干净隔离，切分是否可以复现。

## `predictions.jsonl`

每一行是一条样本的输出、期望答案、score、slice、method、错误信息，以及可选的模型来源信息。

说明什么问题：不是只看平均分，而是能回到每条样本检查失败原因。

## `pcl model-detect` 输出

记录 `provider`、`model_id`、`source`、`confidence`、可选的公开模型元数据、`request_id`、
`request_sha256`、`response_sha256`、`provider_log_reference`、`signed_receipt`、
`provenance_level`、`provenance_evidence`，以及 warning。

说明什么问题：这次运行是否留下了公开 model id 记录。它不能证明服务商隐藏的内部权重版本。
签名收据字段只记录引用；当前工具不会验证 provider 签名。

## `model_drift.json`

记录前后两次运行的 provider、model id、漂移风险等级和简短原因。

说明什么问题：这次比较是否还是干净的 prompt-only 对比，还是已经被模型变化影响。alias model id 会被当作复现风险。

## `audit_result.json`

记录 `pcl audit-diff` 的审计结果：改动文件、每个文件的新增/删除行数、source/test/docs/config 文件数量、
dependency / lockfile / workflow 改动、删除的测试、generated 文件、脱敏后的 secret finding、危险路径、
可能的 public API 改动、测试命令、测试状态、每条命令的 `test_results`（stdout/stderr 摘要和超时状态）、
预期路径检查，以及是否需要人工复核。

内置 secret scanner 会记录 `secret_scanner_scope: added_diff_lines`，表示只检查新增 diff 行。
可选的 `gitleaks` / `trufflehog` 会记录 `secret_scanner_scope: workspace`，因为它们扫描当前工作区，
可能报告不属于 `before` / `after` diff 的既有发现。

说明什么问题：AI 编程 agent 执行后到底改了什么。如果没有提供 `--expected-path`，`unnecessary_file_edits` 会是 `null`，因为工具不会假装知道原始任务意图。

## `audit_summary.md`

记录 `audit_result.json` 的可读摘要。

说明什么问题：哪些文件被改了，发现了哪些风险信号，reviewer 应该先看哪里。

## `history_index.json`

记录本地 run 目录索引，包括 manifest、模型身份、prompt 身份、metrics、gate 状态、风险类别和 artifact 路径。

说明什么问题：本地 `runs/` 目录里有哪些历史运行，每次运行留下了什么记录。

## `history_compare.json`

记录两个 run 目录之间的对比：prompt 身份是否一致、模型是否一致、metric delta、gate 状态变化、slice 退化、新增或消失的风险类别。

说明什么问题：新 run 相比旧 run 是否改了 prompt、模型、分数、门禁结果或风险画像。

## `comparison_validity.json` / `comparison_validity.md`

由 `pcl validity --baseline runs/baseline --candidate runs/candidate --out
runs/candidate/comparison_validity.json` 写出。

说明什么问题：当前 artifacts 是否支持一次干净的 prompt-only 比较。它会检查 prompt identity、
model identity、split hash、metric identity、成对统计证据和 slice 退化。`clean` 表示证据链较完整；
`needs_review` 表示证据有用但不完整或不确定；`invalid` 表示发现了模型、指标或切分不一致等阻断性混淆。

## `agent_run.json`

记录一个紧凑的 agent 执行 manifest：prompt identity、agent 名称、provider/model、policy、
gate decision、risk level、改动文件、测试、audit path、gate path，以及是否需要人工复核。

说明什么问题：把执行前检查、模型溯源、门禁结果和 diff 审计连接到同一次 AI 编程 agent 运行。

## `pr_summary.md` / `pr_summary.json`

基于 `audit_result.json`、`gate_result.json` 和可选的 `agent_run.json` 生成给 reviewer 看的 PR 摘要。

说明什么问题：PR 应该通过、失败还是进入人工复核；同时列出建议标签，例如
`prompt-control-lab:needs-review`、危险路径、缺少测试、workflow/dependency 改动或 secret finding。

## `pcl doctor` 输出

记录或打印本地安装检查：Python 版本、包导入、CLI parser、可选的 `OPENAI_API_KEY`、guard policy 解析、Claude Code hook、Cursor MCP server、demo report 生成和可选研究依赖。

说明什么问题：本地环境是否已经能正常使用 CLI 和插件；如果安装失败，应该先检查哪里。

## `metrics.json`

记录总体样本数、平均分和每个 slice 的平均分。

说明什么问题：新 prompt 是否只在某些 slice 上变好，是否在另一些 slice 上退化。

## `stats.json`

记录 baseline 和 candidate 的 paired comparison，包括 mean delta、bootstrap CI、permutation p-value 和 Holm-adjusted p-value。

说明什么问题：观察到的提升是否可靠，还是样本波动导致的不确定结果。

## `explanation.json`

记录本次运行的直白或技术解释，包括总体结论、证据强度、数据隔离、slice 变化、样本变化、部署风险、下一步建议、`plain_summary` 和 `deployment_recommendation`。

说明什么问题：不用逐个阅读所有 JSON 文件，也能知道这次 prompt 改动说明了什么。

## `gate_result.json`

记录策略阈值判断结果。

说明什么问题：这次运行是 `pass`、`needs_review` 还是 `fail`，以及触发原因是什么。它也会包含 `plain_summary`，方便插件和报告直接展示直白结论。配置模型策略后，它还会记录模型来源检查，例如模型未知、baseline/candidate 模型不同、alias model、provider 白名单和 verified 要求。如果存在 `comparison_validity.json`，gate 也会消费它：`invalid` 会变成硬失败，`needs_review` 会进入人工复核，`clean` 才通过比较有效性检查。

## `pcl guard --json` 输出

记录 hook、rules 或 shell wrapper 使用的输入层 prompt 守护结果。

重要字段：

- `plain_summary`：给普通用户看的直白建议，例如“补充目标文件和验收标准”。
- `action`：`suggest`、`auto` 或 `block`。
- `risk_level`：`low`、`medium` 或 `high`。
- `improved_prompt`：建议继续发送给 AI 工具的守护版 prompt。
- `risk_categories`：例如 `destructive_change`、`security`、`production_path`、`broad_refactor`、`token_budget` 或团队策略类别。
- `policy_violations`：具体命中的内置规则或团队策略。
- `required_review`：是否需要人工复核。

说明什么问题：这条 prompt 是否已经足够清晰，发送前还应该补什么。

## `improved_prompt.txt`

记录 `pcl improve` 生成的优化 prompt。

说明什么问题：工具推荐用户使用哪一个更直白、更稳定的 prompt。

## `prompt_improvement.json`

记录原始 prompt、优化 prompt、识别语言、优化目标、风格、改写原因和报告上下文提示。它还包含 `token_report`，用不依赖外部 tokenizer 的方式估算原始 prompt 和优化 prompt 的 token 数、token 模式、可选预算以及是否满足预算。

说明什么问题：工具为什么这样改 prompt，是否使用了已有诊断报告，以及这次改写对估算 prompt-token 成本有什么影响。`plain_summary` 会用一句直白的话解释结果，方便插件或简单 wrapper 直接展示给普通用户。

## `prompt_diff.md`

记录原始 prompt、优化 prompt、可读的改动列表和 estimated token 成本。

说明什么问题：不用看 JSON，也能知道 prompt 具体改了什么。

## `diagnostics/soft_hard.json`

记录 soft prompt 向 nearest token embedding 投影的 token index 和距离。

说明什么问题：soft prompt 转成 hard prompt 的部署风险。

## `diagnostics/trajectory.json`

记录 hidden-state trajectory 的 drift、log-decay slope、fit quality 和 turnpike-like signal。

说明什么问题：prompt 或任务是否让内部轨迹更稳定，还是更漂移。

## `diagnostics/riccati.json`

记录 surrogate 的 closed-loop spectral radius、theory decay rate 和稳定性标签。

说明什么问题：拟合出的有限维控制论 surrogate 是否自洽稳定。

## `diagnostics/tv_soft.json`

记录 static、time-varying、shuffled、random 等方法的均值和相对 baseline 的差异。

说明什么问题：time-varying prompt 的收益是否更像来自时序结构。

## `report.md` / `report.html`

把 split、metrics、stats 和 diagnostics 汇总成可读报告。

说明什么问题：这次 prompt 改动是否值得保留，以及下一步应该检查哪里。
