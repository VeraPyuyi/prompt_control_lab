# 生产级试点协议

这份文档说明如何为 `prompt_control_lab` 收集一组小规模但可信的
`raw-agent vs guarded-agent` 生产风格试点数据。

目标不是证明“所有任务都会提升”。目标是在一个明确任务集上观察：
`pcl guard` 是否让团队得到更少的非预期改动、更清楚的测试证据、更少的人工纠偏、
更完整的审计记录，或更短的运行时间。

## 隐私边界

不要公开私有 prompt 或源码。公开 artifact 应只包含任务摘要、聚合指标、必要时脱敏的文件路径、
以及可复核的实验协议说明。完整 prompt、patch、日志和仓库快照应留在私有工作区，
除非它们已经明确可以发布。

## 推荐样本

- 从同一个仓库或同一个产品区域选择 20 到 50 个真实 coding 任务。
- 覆盖 bugfix、测试、文档、依赖变更、UI 修改、CI 修复和安全敏感请求。
- 不要只挑容易任务或成功任务。
- 如果排除某个任务，记录排除原因。

## 成对执行协议

每个任务都需要让 raw 和 guarded 两侧从完全相同的干净仓库状态开始。

1. 创建一个干净 worktree 或临时 clone。
2. 用原始 prompt 运行选定 agent。
3. 记录成功与否、测试是否通过、触碰文件、非预期改动、耗时和人工纠偏轮数。
4. 重置到同一个干净起始 commit。
5. 运行：

   ```bash
   pcl guard --prompt "<task prompt>" \
     --profile coding \
     --policy examples/guard.policy.yaml \
     --token-mode balanced \
     --json
   ```

6. 使用同一个 agent、provider、model 和 timeout 运行 guarded prompt。
7. 记录同一组指标。
8. 运行：

   ```bash
   pcl audit-diff --before <start-ref> --after <end-ref> --out runs/audit-<task-id>
   pcl agent-run build --run runs/quick --audit runs/audit-<task-id> --agent codex --out runs/agent_run-<task-id>.json
   ```

9. 公开 CSV 中只保留脱敏摘要。

## 建议记录字段

至少沿用当前 case study schema：

- `task_id`
- `agent`
- `task_type`
- `raw_prompt_summary`
- `guarded_prompt_summary`
- `raw_success`
- `guarded_success`
- `raw_touched_files`
- `guarded_touched_files`
- `raw_unnecessary_file_edits`
- `guarded_unnecessary_file_edits`
- `raw_tests_passed`
- `guarded_tests_passed`
- `raw_human_corrections`
- `guarded_human_corrections`
- `raw_prompt_tokens`
- `guarded_prompt_tokens`
- `raw_duration_seconds`
- `guarded_duration_seconds`
- `notes`

## 可以说明什么

可以谨慎说明：

- “在这组任务中，guarded prompt 的非预期改动更少。”
- “在这组任务中，guarded run 记录了更清楚的测试或审计证据。”
- “guard 增加了 prompt token，但平均运行时间更短。”
- “这次试点没有观察到成功率提升。”

不要这样说：

- “guarded prompt 总能提升 coding 成功率。”
- “guard 能证明 agent 行为安全。”
- “这个样本是通用 benchmark。”

## 发布汇总

收集 CSV 后，可以运行：

```bash
pcl history index --runs runs --out runs/history_index.json
pcl export-report --run runs/quick --out runs/quick/report.zip
```

公开聚合表、可视化、方法和限制。完整私有日志不要直接放进开源仓库，除非已经做过发布审查。
