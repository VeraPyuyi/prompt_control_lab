# 真实成对试点：Codex 本地 Guard Study

这是一个小规模的 **raw-agent vs guarded-agent 真实成对试点**。它使用本地 Codex
非交互执行，在隔离的临时 Python 仓库中运行。

这不是通用 benchmark。它的目的不是证明“所有任务都会提升”，而是先验证：
`pcl guard` 生成的 guarded prompt 是否可以交给真实 coding agent 执行，并且能否和 raw prompt
在相同起点下做成对比较。

## 实验协议

- Agent：`codex-local-exec`
- 样本量：6 个成对任务
- 任务类型：隔离 Python `pytest` bugfix
- 每个任务运行两次：
  - raw prompt
  - 经过 `pcl guard --profile coding --policy examples/guard.policy.yaml` 改写后的 prompt
- 每一侧都从同一个干净 git 初始仓库开始。
- 成功标准：agent 运行后，`python -m pytest -q` 通过。
- 失败或不完整运行后，不提供人工纠偏轮次。

## 结果

| 指标 | Raw agent | Guarded agent |
|---|---:|---:|
| 完成任务 | 6/6 | 6/6 |
| 测试通过 | 6/6 | 6/6 |
| 平均触碰文件数 | 1.17 | 1.17 |
| 非预期文件改动总数 | 1 | 1 |
| 人工纠偏轮次 | 0 | 0 |
| 平均估算 prompt token | 5.17 | 83.17 |
| 平均耗时秒数 | 149.02 | 114.36 |

## 如何解读

在这组小型 fixture 任务中，guarded prompt **没有提升成功率**，因为 raw Codex 已经完成了全部
6 个任务。guarded prompt 在这次运行中的平均耗时更短，但 prompt token 用量明显更高。

所以更诚实的结论是：

- guarded prompt 可以交给真实 coding agent 执行；
- 成对试点 harness 可以从相同起点比较 raw 和 guarded 两条路线；
- 这组样本不能证明通用任务成功率提升；
- 后续需要更大、更接近真实 PR 的任务集，才能支持更强结论。

数据文件：

- [`agent_guard_paired_pilot.csv`](agent_guard_paired_pilot.csv)
- [`agent_guard_paired_pilot.summary.json`](agent_guard_paired_pilot.summary.json)

