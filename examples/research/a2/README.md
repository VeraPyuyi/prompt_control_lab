# Research tools v2: synthetic examples and input contract

These examples contain **synthetic demonstration data only**. They contain no
private manuscript results or real model acceptance evidence. Run an example with
`pcl research readout --input examples/research/a2/readout.json --out <directory>`
(replace `readout` with `response`, `measurement-value`, `transfer`, or `replay`).
The Python entry point is `analyze_research(kind, document, out_dir)`.

Each run writes deterministic JSON, CSV, English/Chinese Markdown and HTML.
Calibration and budget curves also produce SVGs when applicable. These are local
diagnostics; no model calls, uploaded scripts, or pickle files are executed.

## Shared envelope

| Kind | Canonical `schema_version` |
| --- | --- |
| readout | `pcl.readout-sensitivity/v2` |
| response | `pcl.response-profile/v2` |
| measurement-value | `pcl.measurement-value/v2` |
| transfer | `pcl.control-transfer/v2` |
| replay | `pcl.research-replay/v2` |

The same names without the `pcl.` prefix are accepted as aliases. The selected
kind must match the schema. Legacy `/v1` documents retain their previous behavior.

Every v2 document requires:

- `synthetic`: explicit Boolean.
- `provenance`: object containing a nonempty `description`; preserve additional
  source, artifact, model, run, and import metadata in this object.
- `representation`: `raw_records` or `saved_summary`.
- Optional `evidence_status`: defaults to `historical_observation`.

`saved_summary` requires a nonempty `summaries` object or list. This path preserves
and hashes supplied summaries, labels `computation=saved_summary_only` and
`raw_recomputation=false`, and does not invent missing activations, timing traces,
labels, calibration data, confidence intervals, or raw-record recomputation.
This is the generic adapter contract for private supporting tables. Include
file names, original headings, units, cohort, and extraction method in provenance.

An `independent_confirmation` declaration requires the linked receipts accepted
by the existing evidence validator. Even internally valid receipt hashes and
dates do not authenticate temporal independence: `effective_claim` stays
`historical_observation`, and `temporal_independence_verified` stays false.
An importer must never upgrade a source label to independent confirmation.

For measurement-value v2 receipts, `lock.payload.policies_sha256` hashes the
ordered list of case projections with exactly `case_id`, `model`, `pair_id`,
`item_ids`, `budget_seconds`, and `policies`; canonical JSON hashing follows the
shared `digest` helper. Independent-confirmation cohort IDs must match the actual
`model:pair_id` set. The v1 receipt projection and `model:pair` cohort contract
remain unchanged. Response v2 verifies receipts against its original document
before projecting geometry inputs into the legacy computation helper.

Transfer v2 receipts use `transfer_v2_receipt_projection(document)` to produce
three ordered values: forecasts, calibration cohorts, and evaluation panels.
`lock.payload.forecasts_sha256` binds each panel's `panel_id`, `model`, `axes`
and nested pairs' `pair_id`, `prompt_ids`, `question_ids`, `predictions`.
`cohorts.calibration` contains the actual calibration `question_ids` and
`prompt_ids`; `cohorts.evaluation_panels` contains the same panel/pair projection
without predictions. These must match the analyzed data. Their digests belong
in `lock.payload.calibration_cohorts_sha256` and
`evaluation.evaluation_panels_sha256`, respectively. Seen-prompt or calibration-
question overlap is checked against each declared axis, not treated as independent
unseen-prompt transfer. These links still do not authenticate chronology.

## Readout

`conditions` is a nonempty list of:

- Unique `condition_id`; `parser={rule,version,posthoc}` with version
  `numeric/v2` or `choice/v2`, Boolean `posthoc`, rule `strict`, `leading`, or `terminal`.
- Positive `budget_tokens`, positive `batch_size`, nonempty `decoding` object,
  `stopping`, `precision`, `template_id` strings.
- `generation_mode`: `saved_full`, `stored_prefix`, or `real_short_generation`.
- `samples`: the same ordered, unique item panel in every condition.

Each sample has `item_id`, a strict parser-compatible `gold_answer` string,
`initial_answers={source:string,target:string}`, `source` and `target` endpoint
objects, and `scores={loss:number,...diagnostics}`. Gold answers and score names
must be identical across conditions. Score values or initial answer strings may
change in inference perturbations (for example, batch-size changes). Such results
remain computable, but `fixed_score_initial_answer_preserving_claim=failed`, with
separate preservation flags and score rank sensitivity. Only conditions that
preserve both, execution conditions and original output identities support a
readout-only classification. Results expose `execution_conditions_preserved`,
`execution_axes_changed` and `source_records_preserved`. A verified saved-prefix
view may change its reading budget without claiming a new generation. The initial answer record is a supplied
premise; the tool validates preservation, not the historical origin of that record.

Each endpoint requires `text` (empty is permitted). A stored prefix additionally
requires `prefix_tokens`, aligned `token_ids`/`token_texts`, `tokenizer_id`, and
`token_consistency={verified:true,decoder:string,token_ids_sha256:string,
decoded_text_sha256:string}`. Hashes use the canonical JSON `digest` helper on the
original token ID list and the full saved text string. Token pieces must exactly
reconstruct that text. These receipts check internal consistency, not independently
authenticated tokenizer behavior. A real short generation rejects prefix fields
and requires `generation_run_id`, `generated_tokens <= budget_tokens`, and
`finish_reason`. It is reported separately from a stored token prefix.

`strict` parses an entire numeric answer; `leading` parses its first numeric token;
`terminal` parses a numeric token ending the output, allowing final punctuation.
Decimal signs, decimal points, grouped thousands and scientific notation are
supported. Parse failure is null. The report separates parse-status switches,
parsed-answer changes, correctness changes, AUC per target and score, and AUC gaps
against loss. Score value preservation, rank preservation and Spearman correlation
are reported separately; changed ranks are retained as inference sensitivity.

`choice/v2` explicitly selects a fixed uppercase A-E vocabulary. Strict parsing
accepts a whole label such as `B`; leading parsing accepts the first standalone
label, such as `B. Because ...`; terminal parsing accepts the final standalone
label with optional closing parenthesis/bracket and sentence punctuation, such
as `Answer: (B).`. Embedded letters, lowercase labels and numeric labels are not
coerced into choices. `readout-choice.json` is a fully synthetic choice example.

## Response

Raw records require `metadata` with `readout_definition`, `calibration_source`,
`label_usage={calibration:string,measurement:string,evaluation:string}`, and
explicit unique `calibration_ids`, `measurement_ids`, `evaluation_ids` lists.
Calibration and evaluation question identities must be disjoint.

`records` use the existing v1 local geometry fields: unique `record_id`,
`loss_before`, `loss_after`, `control_before`, `control_after`, `response_before`,
`response_after`, `readout_gradient`, optional orthonormal `subspace_basis` and
optional `linear_response_matrix`. Only the supplied finite-dimensional response
gain, displacement, alignment, projection and linear approximation residual are
computed. These are not model-global certificates.

Optional `readouts` contain unique `readout_id`, `original_coefficients`,
`coefficients`, and `mode`. `fixed_coefficients` requires exact coefficient
preservation. `refit` requires nonempty `fit_question_ids` disjoint from evaluation
and a `fit_run_id`. Readout deltas are recomputed on the supplied response vectors;
rank correlation with the original readout is undefined for constant vectors.

Optional `calibration_curves` contain `readout_id`, `source=saved_summary`, and
`bins=[{count,mean_prediction,observed_rate}]`. Counts are positive integers and
rates lie in [0,1]. ECE is derived from saved bins only, with no raw calibration
recomputation claim.

Optional `selection_records` have `question_id`, `pair_id`, `fold` (0..4), binary
`label`, and numeric `scores` containing `loss`, `primary`, `activation`, `logit`.
Every question belongs to one fold across pairs; question/pair coordinates are
unique. All five folds and the same pair cohort in every fold are required.
Question identities must match `metadata.evaluation_ids`. AUC is computed within
each pair and fold, averaged over common valid pairs, then equally over all five
folds. If any fold has no defined AUC, the final mean stays null. Cross-fold scores
are never pooled for selection AUC. The report includes undefined pair counts,
activation/logit baselines, and within-fold per-pair rank sensitivity. Optional
`training_question_ids_by_fold={"0":[...],...,"4":[...]}` verifies each training
cohort is disjoint from its held-out fold; absence is reported as unverified.

## Measurement value

`cases` contain unique `case_id`, `model`, `pair_id`, unique `item_ids`, aligned
binary `labels`, measured `budget_seconds`, and optional `budget_grid_seconds`.
`policies` requires unique strategies including `direct`. Each policy contains:

- `strategy`, positive `actual_batch_size`, `timing_scope` of
  `measured_full_policy` or `primitive_operations`; the former requires `run_id`.
- `costs`: seconds for `load`, `probe`, `score`, `sort`, `transfer`,
  `serialization`, `failed`. Missing/null costs remain unknown. Explicit zero is
  permitted only when that component is known to have zero cost.
- Ordered serial `batches` containing unique `batch_id`, `item_ids`,
  `elapsed_seconds` (null stays unknown), and explicit Boolean `completed`.

Costs are upfront non-overlapping overheads; recorded generation batch elapsed
time includes failed/incomplete generation. `failed` counts only failed work
outside those batches. Completed batches cannot count an item twice. A failed
attempt may be followed by a completed retry, paying both batch times. A batch
that crosses the budget gets no item credit. Incomplete batches pay elapsed time
but get no item credit. Unknown cost/timing leaves K, Y and delta Y unknown.
Decimal budget comparisons use exact rational arithmetic.

If a started batch crosses the budget, `observed_spend_within_cutoff_seconds`
includes its consumed time up to the cutoff. The full elapsed time through that
batch is `observed_elapsed_through_cutoff_batch_seconds`; its tail beyond the
budget is `measured_overrun_seconds`. The crossing batch earns no discovery
credit, and no later batch starts in that cutoff replay. An upfront cost overrun
is capped and reported in the same way. Unknown costs leave all three elapsed
fields unknown.

K is completed item count; Y is discovered changes. Delta Y versus direct is
reported only for measured full-policy traces on both sides. Primitive-operation
timings cannot become a full-policy claim. Optional top-level `primitive_timings`
rows contain `operation`, `elapsed_seconds`, and `model`; they are informational.
Budget curves replay supplied traces. No extrapolation to unobserved larger models
or unmeasured batch sizes is performed.

## Transfer

Requires nonempty unique `calibration_question_ids` and `calibration_prompt_ids`.
`panels` contain unique `panel_id`, `model`, and `axes={questions,prompts}`:
questions are `calibration_questions` or `new_questions`; prompts are
`seen_prompts` or `unseen_prompts`. Identity membership/disjointness is verified.
Missing cells of the 2x2 crossed panel are reported instead of invented.

Each panel has `pairs` with unique `pair_id`, two distinct `prompt_ids`, ordered
`question_ids`, aligned binary `labels`, scores containing `loss` and at least one
diagnostic, and `predictions={diagnostic:{full,cheap,group_mean,zero}}`. Zero is
exactly zero, and the group mean prediction is constant across a panel.
Pairs within a panel share ordered questions. Shared question axes preserve the
question panel; shared prompt axes preserve prompt pair identities/orientation.

For each diagnostic, per-pair AUC gain versus loss, descriptive group mean gain,
pair prediction MAE and MAE improvement versus the group mean are separate outputs.
Common valid pair counts and undefined pairs are explicit. There is no automatic
significance claim; formal intervals use the separate frozen bootstrap engine.
Optional `measurement_document` on a panel embeds a raw v2 measurement-value
document for additional measured policy value. Without it, additional control
value is `not_evaluated`; prediction accuracy is never substituted for paid value.

## Replay

`files`, `checks`, and `tolerances` use the v1 self-contained allowlisted replay
format: inline JSON/text plus optional canonical/exact SHA256; checks reference
embedded input/expected files and allowlisted research or local-certificate kinds.
No recursive replay or arbitrary command execution is allowed. V2 inputs in the
bundle dispatch to v2 implementations.

Four result channels are separate: `integrity`, `numerical_replay`, `protocol`,
and `theoretical_checks`. Expected output absent means numerical agreement is
`not_supplied`, even if recomputation ran. Protocol validates the chosen module's
local prerequisites and always reports chronological prediction lock as
`not_verified`. Local certificate checks never imply a whole-model theorem.

## 中文说明

这些示例全部是合成数据。v2 保留旧版行为，新增明确的原始记录与保存汇总两条输入路径。
解析、答案变化、正确性和排序分别报告；固定分数与初始答案未保留时会阻止相应结论，
但保留推理扰动的观察结果与排序变化；保存前缀与真实
短生成必须区分。响应诊断分别声明校准、测量、评估标签用途，五折选择统计只在每折内
按配对计算 AUC，再对配对及折等权平均，不混合跨折分数。成本缺失不能当作零，只有
预算内完成的整批次计入发现量。迁移面板分别表示新题目与未见提示，组均值、配对预测
和额外控制价值是三个不同目标。复算的完整性、数值一致性、协议前提和局部理论性质
彼此独立，哈希与来源标签不能证明独立确认，局部性质不能证明整个模型的性质。
