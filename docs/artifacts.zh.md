# Artifact 说明

`prompt_control_lab` 的核心输出不是单个分数，而是一组可以复查的 artifact。
这份文档说明每个文件是什么、怎么得到、能说明什么问题。

## 快速阅读顺序

如果你只想快速判断一次 prompt 实验是否可靠，建议按这个顺序打开：

1. `evidence_audit_result.html`：外部工具导入后的总审计入口。
2. `bridge_summary.html`：外部工具提供了什么，PCL 又补了什么。
3. `research_bundle.zh.html` / `research_bundle.html`：中文 / 英文完整研究证据索引。
4. `evidence_card.html`：prompt optimization 证据卡片。
5. `claim_check.html`：当前证据最多能支持什么主张。
6. `research_gap_status.html`：还缺哪些论文诊断。
7. `research_bundle_verification.html`：证据包哈希是否仍然匹配。

如果是普通 quick run，可以先打开 `report.html` 和 `explanation.json`。

## `splits.json`

由 `pcl split` 或 `pcl analyze` 写出。

说明什么问题：任务样本是否被干净切成 train / validation / withheld。它会记录
split hash、各 split 的样本 id，以及是否存在重叠。这个文件用于降低 validation
overfitting 和 test leakage 的风险。

## `predictions.jsonl`

由 `pcl eval`、`pcl analyze` 或外部导入命令写出。

每一行通常包含样本 id、模型输出、期望答案、score、slice、method，以及可选的
provider / model / prompt identity。

说明什么问题：每条样本到底答对还是答错，错误集中在哪些 slice 上。

## `metrics.json`

由 `pcl eval` 或 `pcl analyze` 写出。

说明什么问题：一个 prompt 或方法在整体和每个 slice 上的表现。它适合快速看均值和
分组退化，但不能单独证明 candidate prompt 可靠提升。

## `stats.json`

由 `pcl stats` 或 `pcl analyze` 写出。

重要字段：

- `mean_delta`：candidate 相对 baseline 的平均差异。
- `bootstrap_ci`：bootstrap 置信区间。
- `permutation_p_value`：成对 permutation test 的 p-value。
- `holm_adjusted_p_value`：Holm correction 后的 p-value。

说明什么问题：candidate 的提升是否在成对统计意义下可靠。如果置信区间跨过 0，
即使均值更高，也应该谨慎解释。

## `comparison_validity.json` / `comparison_validity.md`

由 `pcl validity`、`pcl analyze` 或 `pcl compare-runs` 写出。

说明什么问题：baseline / candidate 是否真的是干净的 prompt-only 比较。它会检查
model、provider、metric、split hash、prompt identity 等混杂因素。如果发现模型不同，
这次结果就不能直接解释为“prompt 变好了”。

## `report.md` / `report.html`

由 `pcl report`、`pcl analyze` 或 `pcl compare-runs` 写出。

说明什么问题：把 metrics、stats、comparison validity、model provenance 和 gate 结果
合并成给人看的报告。HTML 适合给 reviewer 或团队成员直接打开。

## `explanation.json`

由 `pcl explain` 或 `pcl analyze` 写出。

说明什么问题：用更直白的语言解释本次 prompt 改动是否值得保留、证据强不强、
哪些 slice 退化、下一步应该检查什么。

## `gate_result.json`

由 `pcl gate` 写出。

说明什么问题：根据 policy 判断当前 run 是 `pass`、`needs_review` 还是 `fail`。
它可以检查分数阈值、退化幅度、统计证据、soft-hard 风险和模型溯源策略。

## `evidence_card.json` / `evidence_card.md` / `evidence_card.html`

由 `pcl evidence-card` 写出，也会由 `pcl research-demo`、`pcl diagnose`、
`pcl evidence-from` 和 `pcl evidence-audit` 间接生成。

说明什么问题：把一次 prompt optimization 实验压缩成一张证据卡片，集中展示协议、
成对统计、prompt-only 有效性、soft-hard gap、trajectory、Riccati、tv-soft 等证据。
它不是证明“prompt 全局最优”，而是说明当前 artifact 能支持什么程度的结论。

## `claim_check.json` / `claim_check.md` / `claim_check.html`

由 `pcl claim-check` 写出。

说明什么问题：当前证据最多能支持哪种主张。例如只支持 paired comparison，还是已经
达到 partial-research 或 full-research diagnostics。这个文件用于防止把普通 eval
结果夸大成完整论文诊断结论。

## `research_diagnostics.json` / `.md` / `.html`

由 `pcl diagnose` 或 `pcl research-demo` 写出。

说明什么问题：统一汇总论文里的核心诊断模块：

- soft-hard projection gap
- hidden-state trajectory / turnpike-like decay
- Riccati surrogate stability
- static / time-varying / shuffled / random soft-control comparison

缺少输入 artifact 时，报告会明确说明对应诊断没有运行，而不是伪造结果。

## `research_gap_plan.json` / `.md` / `.html`

由 `pcl diagnose` 或外部 evidence bridge 流程写出。

说明什么问题：为了补齐论文诊断，还缺什么输入、应该运行哪条命令、预期生成什么文件。

## `research_gap_status.json` / `.md` / `.html`

由 `pcl gap-status` 或 `pcl evidence-audit` 写出。

说明什么问题：检查 gap plan 中要求的 soft-hard、trajectory、Riccati、tv-soft 等
artifact 是否已经存在。它适合用来确认“证据缺口是否真的补上了”。

## `research_bundle.json` / `research_bundle.zh.html` / `research_bundle.html`

由 `pcl research-bundle`、`pcl research-demo`、`pcl diagnose` 或 `pcl evidence-audit` 写出。

说明什么问题：把一个 run 中的重要证据文件整理成浏览器优先的索引，并记录可见 artifact
的路径、大小和哈希。它是 reviewer 打开整个研究证据包的入口。

## `research_bundle_verification.json` / `.md` / `.html`

由 `pcl research-bundle --verify` 或 `pcl evidence-audit` 写出。

说明什么问题：验证 `research_bundle.json` 中记录的哈希是否仍然匹配当前文件。它不能防止
所有篡改，但可以让误改或分享后修改变得可见。
如果要把这项验证用作 CI 或 reviewer gate，可以运行
`pcl research-bundle --run <run> --verify --strict`。只要任何证据 artifact 被改动、
缺失或无法检查，命令就会返回非零退出码。

## `evidence_from_result.json`

由 `pcl evidence-from` 写出。

说明什么问题：记录外部工具导入、baseline/candidate 比较、PCL 证据补充和下一步建议。
它适合自动化读取；人工审查通常先看 `bridge_summary.html`。

重要字段：

- `source_inputs`：baseline 和 candidate 外部导出文件的原始路径、路径类型、解析后的绝对路径、
  字节数、SHA-256 哈希、检测到的工具名和导入行数。
- `baseline_import` / `candidate_import`：导入计数、均值和筛选条件。
- `comparison`：stats、comparison validity、evidence card 和 report 的路径。
- `bridge_summary`：推荐结论、evidence tier、claim scope、validity 和缺失证据。

## `evidence_audit_result.json` / `evidence_audit_result.md` / `evidence_audit_result.html`

由 `pcl evidence-audit` 写出。它会先运行和 `pcl evidence-from` 相同的导入与比较流程，
然后立刻运行 `pcl gap-status`、source-input verification、`pcl research-bundle --verify`
和 `pcl evidence-gate`。

重要字段：

- `detected_tools`：导入时识别到的外部工具来源。
- `source_inputs`：baseline 和 candidate 外部导出文件的原始路径、路径类型、解析后的绝对路径、
  字节数、SHA-256 哈希、检测到的工具名和导入行数。
- `claim_scope` / `evidence_tier` / `validity`：当前 prompt optimization 证据能支持的主张边界。
- `gap_status`：论文诊断是已经存在，还是仍有缺口。
- `source_verification`：原始外部导出文件是否仍然匹配记录哈希。
- `bundle_verification`：被链接的证据 artifact 是否仍然匹配已记录哈希。
- `source_input_verification_path`：原始导出哈希验证的浏览器报告路径。
- `evidence_gate`：source 和 bundle 证据的组合 reviewer/CI gate 状态。
- `evidence_gate_path`：组合 evidence gate 的浏览器报告路径。
- `html_path` / `markdown_path`：给人工审查使用的浏览器摘要和文本摘要。
- `next_actions`：建议 reviewer 下一步打开的文件。

说明什么问题：外部 eval / observability 导出是否已经被转换成可审查的 PCL 证据包，
还缺哪些研究诊断，以及当前链接的证据包是否通过了最新一次本地哈希验证。

人工审查时建议先打开 `evidence_audit_result.html`；自动化流程读取
`evidence_audit_result.json`。

## `source_input_verification.json` / `.md` / `.html`

由 `pcl evidence-audit` 自动写出；也可以用 `pcl source-verify --run <run>` 刷新。
如果要让 source verification 在 CI 或 reviewer gate 中阻断被改动、缺失或无法检查的
source input，可以使用 `pcl source-verify --run <run> --strict`。

说明什么问题：原始外部 baseline / candidate 导出文件是否仍然匹配
`pcl evidence-from` 或 `pcl evidence-audit` 记录在 `source_inputs` 里的 SHA-256 哈希。

重要字段：

- `status`：`pass`、`fail`、`needs_review` 或 `missing_source_inputs`。
- `source_artifact`：这次验证读取的是哪一个 PCL artifact 里的 `source_inputs`。
- `checked_count` / `ok_count` / `mismatch_count` / `missing_count` / `unchecked_count`。
- `results`：每个外部源文件的原始路径、实际解析路径，以及 expected / actual SHA-256 对比。

它和 `research_bundle_verification.*` 是互补关系。`source-verify` 验证原始 Promptfoo /
DeepEval / Langfuse / LangSmith 导出文件；`research-bundle --verify` 验证由这些导出生成的
PCL 证据 artifact。

## `evidence_gate_result.json` / `.md` / `.html`

由 `pcl evidence-gate --run <run>` 写出。如果希望 CI 或 reviewer 在必要证据检查不通过时失败，
可以使用 `pcl evidence-gate --run <run> --strict`。

说明什么问题：这个 run 当前的本地证据是否仍然可复核。必须检查项包括：已经记录 source input
时的 source-input verification，以及 research-bundle verification。gap status 和 claim-check
status 会作为 advisory check 记录，方便 reviewer 看到论文诊断缺口，但不会把缺少研究诊断和
source/bundle 篡改混为一谈。

重要字段：
- `status`：`pass`、`needs_review` 或 `fail`。
- `required_checks.source_inputs`：source-input hash 检查结果；如果这个 run 没有外部 source
  input，且没有使用 `--require-source`，则为 `skipped`。
- `required_checks.research_bundle`：research bundle hash verification 结果。
- `advisory_checks.gap_status` / `advisory_checks.claim_check`：非阻断性的研究证据上下文。
- `next_actions`：reviewer 下一步应该打开的文件或执行的动作。

## `bridge_summary.json` / `bridge_summary.md` / `bridge_summary.html`

由 `pcl evidence-from` 写出，并会被 `pcl evidence-audit` 刷新。

说明什么问题：外部工具和 PCL 的分工。它会记录哪个工具提供 eval 或 trace export，
PCL 补了哪些证据、主要成对统计、prompt-only 比较有效性、论文证据缺口诊断、缺失证据、
补齐命令、需要复查的项目和下一步动作。

当你要解释 PCL 为什么是 Promptfoo、DeepEval、Langfuse 或 LangSmith 的补充层，
而不是替代品时，建议先打开这个文件。

## `ecosystem_scorecard.json` / `.md` / `.html`

由 `pcl ecosystem-demo` 写出；也可以用 `pcl ecosystem-scorecard --run <run>` 单独刷新。

说明什么问题：Promptfoo、DeepEval、Langfuse 和 LangSmith 各自擅长什么，PCL 在其上补了
什么研究证据层，当前比较的 validity / evidence tier 是什么，还缺哪些论文诊断。
JSON 中的 `pcl_evidence_matrix` 会按工具列出 prompt-only validity、paired stats、证据卡、
主张检查、research bundle、bundle verification 和 gap status，方便 UI、CI 或 reviewer 直接读取。
JSON 中还包含 `market_readiness`：它会把扩展市场地图压缩成行动摘要，包括推荐定位、
优先用户、暂时不要做的方向，以及 P1/P2 下一步产品动作。这样 reviewer 不用读完整矩阵，
也能快速判断 PCL 应该从哪里切入。

## `prompt_assets.json` / `prompt_optimizer_gap_plan.json` / `eval_scaffold/`

由 `pcl import prompt-optimizer` 写出。

说明什么问题：prompt-optimizer 导出的是 prompt 候选、收藏或模板，不是已经成对打分的评测证据。
PCL 会记录 prompt 内容哈希，写出证据缺口计划，并生成 `eval_scaffold/`：
`tasks.template.jsonl`、`baseline_predictions.template.jsonl`、
`candidate_predictions.template.jsonl`、导入的 prompt 文本文件，以及
`promptcontrol.prompt_optimizer.example.yaml`。

这个 scaffold 本身不是证据。它的作用是把 prompt 资产推进到成对评测协议，
让用户知道下一步要补哪些任务、输出和模型信息，之后才能主张 prompt 真的变好。

评分前建议运行 `pcl scaffold-check --run <prompt-optimizer-import>`。它会写出
`eval_scaffold/scaffold_check.json`、`.md` 和 `.html`，检查缺失文件、模板占位符、
model/provider 空缺和成对 id 不一致；配合 `--strict` 可以作为 CI 检查。

## `model_identity.json` / `model_drift.json`

由 `pcl model-detect` 和 `pcl model-drift` 写出。

说明什么问题：当前 run 记录的公开 model id 是什么，baseline 和 candidate 是否使用同一
provider / model，是否存在 alias 或未知模型导致的复现风险。这里的模型追溯是公开 model id
层面的证据，不是服务商隐藏权重版本的证明。

## `audit_result.json` / `audit_summary.md` / 可选 `pcl.sarif`

由 `pcl audit-diff` 写出。

说明什么问题：coding agent 运行后改了哪些文件、增删多少行、是否触及 auth/payment/billing/
workflow/dependency/secret/test 删除等风险区域，是否需要人工复核。

## `agent_run.json`

由 `pcl agent-run build` 写出。

说明什么问题：把 prompt、policy、model、gate、audit 和 agent 执行结果合并成一个统一 manifest，
方便历史索引、PR summary 和 UI 读取。

## `history_index.json` / `history_compare.json`

由 `pcl history index` 和 `pcl history compare` 写出。

说明什么问题：跨多个 run 查看 score、model、prompt hash、gate status、risk level 和
review required 的变化趋势。
