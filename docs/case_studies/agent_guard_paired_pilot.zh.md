# 真实成对试点：Codex 本地 Guard Study

这是一个小规模的 **raw-agent vs guarded-agent 真实成对试点**。它使用本地 Codex
非交互执行，在隔离的临时 Python 仓库中运行，不会修改 `prompt_control_lab` 仓库本身。

这不是通用 benchmark。它的目的不是证明“所有任务都会提升”，而是验证：
`pcl guard` 生成的 guarded prompt 是否可以交给真实 coding agent 执行，并且能否和
raw prompt 在相同起点下做成对比较。

## 实验协议

- Agent：`codex-local-exec`
- 样本量：12 个成对任务
- 任务类型：隔离 Python `pytest` 修复任务，包括单文件和多文件场景
- 每个任务运行两次：
  - raw prompt
  - 经 `pcl guard --profile coding --policy examples/guard.policy.yaml` 改写后的 prompt
- 每一侧都从同一个干净 git 初始仓库开始
- 成功标准：agent 运行后，`python -m pytest -q` 通过
- 失败或不完整运行后，不提供人工纠偏轮次

## 结果

| 指标 | Raw agent | Guarded agent |
|---|---:|---:|
| 完成任务 | 12/12 | 12/12 |
| 测试通过 | 12/12 | 12/12 |
| 平均触碰文件数 | 1.25 | 1.0 |
| 非预期文件改动总数 | 3 | 0 |
| 人工纠偏轮次 | 0 | 0 |
| 平均估算 prompt token | 8.08 | 51.08 |
| 平均耗时秒数 | 173.74 | 119.97 |

![真实成对 Codex guard 试点可视化](../assets/agent_guard_paired_pilot.zh.svg)

## 如何解读

在这组 fixture 任务中，guarded prompt **没有提升成功率**，因为 raw Codex 也完成了
全部 12 个任务。更有价值的信号在别处：guard 输出被压缩后，guarded prompt 的 token
用量已经明显低于旧版长模板，但仍然高于 raw prompt；与此同时，本次 guarded runs
平均触碰文件更少、非预期文件改动为 0，并且平均耗时更短。

所以更诚实的结论是：

- guarded prompt 可以交给真实 coding agent 执行；
- 成对试点 harness 可以从相同起点比较 raw 和 guarded 两条路线；
- 这组样本不能证明通用任务成功率提升；
- 下一步应该使用更大的真实仓库任务和 PR 级 review 结果继续验证。

数据文件：

- [`agent_guard_paired_pilot.csv`](agent_guard_paired_pilot.csv)
- [`agent_guard_paired_pilot.summary.json`](agent_guard_paired_pilot.summary.json)
