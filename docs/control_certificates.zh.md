# 控制证书诊断

[English](control_certificates.en.md)

PromptControlLab 提供三项来自控制论敏感性与局部存在性思想的有边界检查。它们诊断用户指定的 artifact 或有限维 surrogate，不会把结果包装成对线上语言模型、全局最优性、隐藏推理或部署安全的证明。

矩阵诊断需要安装研究依赖：

```bash
python -m pip install -e ".[research]"
```

## 1. 终端敏感度

直接分析 terminal objective 或 readout 干预记录：

```bash
pcl terminal-sensitivity \
  --records examples/terminal_interventions.jsonl \
  --out runs/certificates/terminal
```

每条记录会计算：

```text
sensitivity = control_delta_norm / perturbation_norm
log(sensitivity) = intercept - decay_rate * (horizon - early_step)
```

结果包含衰减率、R-squared、bootstrap 区间、分组拟合和数值 floor 截断数量。即使拟合出正衰减，它也只是 `empirical_only`，不是时域一致的 Green estimate。

如需可复现的低维边值问题样例，可运行 `pcl research-demo --out runs/research-demo`。生成的 `inputs/terminal_surrogate.npz` 包含 `M`、`B0`、`BN`、`terminal_perturbations` 和 `control_readout`，可配合多个 `--horizon` 与 `--early-step` 使用。

## 2. Green 证书

```bash
pcl green-certificate \
  --surrogate runs/research-demo/inputs/green_surrogate.npz \
  --horizon 16 --horizon 32 --horizon 64 \
  --premises examples/green_premises.json \
  --out runs/certificates/green
```

命令检查稳定/不稳定 Schur 分解、单位圆谱间隙、缩放边界矩阵最小奇异值、逆范数、条件数和确定性系数恢复残差。NPZ 中存在 `graph_S` 时，会额外执行 terminal-only graph-boundary 检查；普通混合边界不会产生单边终端衰减结论。

使用估计前提的浮点检查最高只能得到 `surrogate_consistent`。只有完整且保守的 premise record 才能对其中明确命名的固定维 surrogate 和 horizon family 给出 `certificate_verified`，该等级不延伸到完整 Transformer。

## 3. 后验证书

```bash
pcl posterior-certificate \
  --input examples/posterior_bounds.json \
  --out runs/certificates/posterior
```

给定残差上界 `epsilon`、Jacobian 逆范数上界 `beta`、局部 Jacobian Lipschitz 上界 `L` 和有依据的邻域半径 `R`，命令计算：

```text
eta = beta * epsilon
K = beta * L
h = eta * K
```

工具检查 `h <= 1/2`，以及得到的局部存在半径是否位于 `R` 内；`L = 0` 时使用线性特例 `eta`。估计常数最高只能得到 `surrogate_consistent`，完整保守的 bound provenance 才能得到 `certificate_verified`。

## 等级与状态

| 字段 | 取值 | 含义 |
|---|---|---|
| `certificate_level` | `certificate_verified`、`surrogate_consistent`、`empirical_only`、`not_applicable`、`insufficient_evidence` | 记录证据的强度与适用性。 |
| `check_state` | `passed`、`conditions_not_met`、`missing`、`invalid` | 当前命名检查的结果。 |

`conditions_not_met` 只表示输入没有满足全部证书条件，不能据此证明解不存在。

## Diagnose、UI 与 Checkpoint Gate

将 artifact 放到 `<run>/diagnostics/` 后运行：

```bash
pcl diagnose --run runs/research-demo --language zh
pcl ui --runs runs --language zh
```

UI 按“观察到了什么 -> 可以解释什么 -> 不能证明什么 -> 下一步行动”展示结果。`pcl posttrain-gate` 会从 candidate checkpoint 的 diagnostics 中读取同样的三个文件；缺失时保持旧工作流兼容。如需强制要求，可在 policy 中加入：

```yaml
require_terminal_sensitivity: true
require_green_certificate: true
require_posterior_certificate: true
minimum_control_certificate_level: surrogate_consistent
```

统一最低等级会按每项诊断的天然上限解释。终端敏感度始终只到 `empirical_only`，因此上面的
配置要求它提供有效的经验 artifact，同时要求 Green 与后验证书至少达到
`surrogate_consistent`。实际采用的逐项最低等级会写入
`certificate_summary.effective_minimum_levels`。

已提供且为 `conditions_not_met` 的结果可以触发 `hold`；策略强制要求但证据缺失时返回 `insufficient_evidence`。证书通过也不会覆盖 score、slice、provenance 或其他 gate 失败。
