# Agent Guard 本地试点 Case Study

这份文档记录 `pcl guard` 的第一版本地成对试点。

## 当前状态

仓库现在已经包含 20 条 **preflight** 成对记录，保存在：

```text
docs/case_studies/agent_guard_pilot.csv
```

每一行都包含一个原始 coding prompt，以及通过下面命令得到的 guarded prompt：

```bash
pcl guard --profile coding --policy examples/guard.policy.yaml --token-mode balanced
```

这还不是 raw-agent vs guarded-agent 的真实成功率 benchmark。因为本批次没有让同一个 agent
对同一任务分别执行 raw prompt 和 guarded prompt，所以 `*_success`、`*_tests_passed`、
`*_touched_files` 和人工纠偏字段都标记为 `not_run`。

这批数据能说明的是：`pcl guard` 如何改写 prompt、估算 token、标注风险类别和策略违规。

## 数据文件

公开 CSV 只保存摘要和指标，不公开完整私密 prompt。

```text
docs/case_studies/agent_guard_pilot.csv
```

## 指标口径

| 指标 | 定义 |
|---|---|
| `raw_success` / `guarded_success` | 本批 preflight 试点中为 `not_run`，留给未来真实 agent 双跑 |
| `raw_tests_passed` / `guarded_tests_passed` | 本批 preflight 试点中为 `not_run` |
| `*_touched_files` | 只有真实 agent 修改仓库后才记录 |
| `*_unnecessary_file_edits` | 只有真实 agent 双跑后才记录 |
| `*_human_corrections` | 只有真实 agent 双跑后才记录 |
| `*_prompt_tokens` | 不依赖外部 tokenizer 的估算 prompt token，不等于模型计费 token |
| `notes` | guard action、风险等级、风险类别和策略违规数量 |

## 发布规则

README 可以发布 preflight pilot 表，因为它可以从 20 条 CSV 重新计算。
但在同一批任务完成 raw prompt 和 guarded prompt 的真实 agent 双跑前，README 不能发布“任务成功率提升”数字。

> 这是一个小样本本地 preflight 试点，不是通用 benchmark。它说明 `pcl guard`
> 在这批任务上如何改写和分类 prompt，不证明 agent 任务成功率一定提升。
