# Diagnostics（机制与稳定性诊断）

## 目的

`promptcontrollab.diagnostics` 分析 Prompt、checkpoint 和 Agent 行为背后的机制与稳定性信号，包括 Trajectory、Soft-to-Hard、Riccati、Time-varying Control、Terminal Sensitivity、Green Boundary 和 Posterior Certificate 诊断。

## 使用场景

- 测量隐藏状态漂移、尾部行为和类似 Turnpike 的衰减。
- 量化 Soft-to-Hard 投影差距和时变控制效应。
- 拟合低维 Riccati/DARE surrogate，并检查局部稳定性。
- 区分经验 Terminal Sensitivity、Surrogate 一致性和有前提支持的局部证书。

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
- Certificate 结果同时包含 `certificate_level` 和 `check_state`，从而区分证据强度与条件状态。

## 依赖

多数数值诊断需要 `research` extra（`numpy` 和 `scipy`）。标量 Posterior Check 不安装科学计算栈也可运行。该模块消费证据，但不执行模型训练。

## 扩展点

- 增加能够返回观察、解释、可信度、范围、结论边界和下一步行动的 Analyzer。
- 为受限数值格式增加安全 Artifact Reader。
- 在不改变诊断 JSON 事实来源的前提下增加 Renderer。

## 限制

- 观测到的 Trajectory 和拟合 surrogate 不能证明完整语言模型中的机制。
- `surrogate_consistent` 弱于 `certificate_verified`，且只适用于命名的有限维系统。
- 条件未满足不等于证明解或有用行为不存在。

## 测试与示例

可使用 `pcl research-demo`、控制证书指南和合成数值 fixture。运行：

```bash
python -m pytest tests -k "trajectory or soft_hard or riccati or tv_soft or certificate or research"
```
