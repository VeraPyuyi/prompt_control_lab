# Agent Guard 真实试点 Case Study

这份文档记录 `pcl guard` 的 Codex 本地成对试点。

## 当前状态

仓库目前还没有 20 条 `raw prompt` vs `pcl guard` 的成对任务记录。`D:\Vibe Research Projects`
下面确实有真实 agent 历史 transcript，但它们不是同一批 coding 任务分别用 raw prompt 和 guarded
prompt 各跑一次，因此不能直接用来计算成功率提升。

所以 README 现在不能发布“成功率提升”数字。

## 数据文件

试点数据会保存在：

```text
docs/case_studies/agent_guard_pilot.csv
```

每一行表示一个 Codex 本地 coding 任务，并且同一任务运行两次：

- 原始 prompt 直接交给 agent
- 使用 `pcl guard --profile coding --token-mode balanced` 得到 guarded prompt 后再交给 agent

公开 CSV 只保存摘要和指标，不公开完整私密 prompt。

## 指标口径

| 指标 | 定义 |
|---|---|
| `raw_success` / `guarded_success` | 任务完成且相关验证通过时为 `true` |
| `raw_tests_passed` / `guarded_tests_passed` | 预期测试或验收检查通过时为 `true` |
| `*_touched_files` | 本次运行修改的文件数量 |
| `*_unnecessary_file_edits` | 不属于任务、测试、文档或格式要求的误改文件数 |
| `*_human_corrections` | 人类为了限定范围、要求补测或撤回跑偏改动而追加的纠偏轮次 |
| `*_prompt_tokens` | 不依赖外部 tokenizer 的 prompt token 估算，不等同于模型计费 token |

## 发布规则

只有当 CSV 至少包含 20 条成对任务记录，并且 README 汇总表可以从 CSV 重新计算出来时，
才在 README 发布真实结果表。在此之前，README 只说明试点正在进行。

发布结果表时必须保留这句限制：

> 这是一个小样本 Codex 本地试点，不是通用 benchmark。它只说明 guard 在这批任务上的表现。
