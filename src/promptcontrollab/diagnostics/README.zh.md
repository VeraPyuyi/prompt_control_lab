# Diagnostics（稳定性与可信度诊断）

## 目的

`promptcontrollab.diagnostics` 帮助用户理解 Prompt、Checkpoint 和 Agent 变更为何有效、何时不稳定，以及当前结论可以相信到什么范围。内部仍保留稳定英文 ID，中文界面优先显示功能名称：

| 稳定 ID | 中文功能名称 | 它回答的问题 |
|---|---|---|
| `terminal_sensitivity` | 最终目标影响 | 最终奖励或目标改变后，对前面决策的影响是否会随任务变长而减弱？ |
| `green_certificate` | 局部稳定边界 | 当前低维近似中的稳定方向是否清楚分离，边界约束是否足够稳健？ |
| `posterior_certificate` | 局部解可信范围 | 当前数值结果附近是否存在可检查的解，它的可信范围有多大？ |

Terminal Sensitivity、Green Certificate 和 Posterior Certificate 只在“技术细节”中作为学术名称显示。

## 使用场景

- 查看模型内部表示是否持续漂移、在任务中段趋于稳定，或在尾部再次变化。
- 判断连续 Prompt 方案转成离散 Token 后是否产生明显损失，以及变化是否来自真正的时序结构。
- 用低维近似检查局部动态是否稳定，同时明确它不能代表完整模型。
- 区分“只观察到趋势”“低维近似一致”和“限定前提已核验”，避免把证据等级混在一起。

## CLI 命令

```bash
pcl diagnose --run runs/research
pcl research-demo --out runs/research-demo
pcl soft-hard --soft soft.npz --vocab vocab.npz --out runs/soft-hard
pcl trajectory --states states.npz --out runs/trajectory
pcl riccati --matrices matrices.npz --trajectory states.npz --out runs/riccati
pcl tv-soft --predictions scored_predictions.jsonl --out runs/tv-soft
pcl terminal-sensitivity --records terminal_interventions.jsonl --out runs/certificates
pcl green-certificate --surrogate green_surrogate.npz --horizon 16 --horizon 32 --horizon 64 --premises green_premises.json --out runs/certificates
pcl posterior-certificate --input posterior_bounds.json --out runs/certificates
```

## Python API

批准后的 canonical package 提供专项分析接口：

```python
from promptcontrollab.diagnostics import (
    analyze_green_certificate,
    analyze_posterior_certificate,
    analyze_terminal_sensitivity,
    analyze_trajectory,
)
```

其他 API 包括 `analyze_soft_hard`、`analyze_riccati`、`summarize_tv_soft`、`run_research_diagnostics` 和 Research Bundle Renderer。

## 输入与产物

- 输入：Hidden State、Transition Sample、Soft Control、Vocabulary Embedding、Intervention JSONL、受限 NPZ surrogate 和 Premise/Bound JSON。
- 输出：诊断 JSON、CSV、SVG/HTML 汇总、Research Bundle Index 和 Certificate artifact。
- 三项可信度检查同时包含 `certificate_level` 和 `check_state`，从而区分证据强度与条件状态。

## 依赖

多数数值诊断需要 `research` extra（`numpy` 和 `scipy`）。标量 Posterior Check 不安装科学计算栈也可运行。该模块消费证据，但不执行模型训练。

## 扩展点

- 增加能够返回“观察、解释、可信度、适用范围、不能证明什么、下一步行动”的 Analyzer。
- 为受限数值格式增加安全 Artifact Reader。
- 在不改变诊断 JSON 事实来源的前提下增加 Renderer。

## 限制

- 观测到的 Trajectory 和拟合 surrogate 不能证明完整语言模型中的机制。
- “低维近似结果一致”弱于“限定条件已核验”，且只适用于命名的有限维系统。
- 条件未满足不等于证明解或有用行为不存在。

## 测试与示例

可使用 `pcl research-demo`、控制证书指南和合成数值 fixture。运行：

```bash
python -m pytest tests -k "trajectory or soft_hard or riccati or tv_soft or certificate or research"
```
