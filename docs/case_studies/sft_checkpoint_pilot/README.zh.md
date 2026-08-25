# 受控 SFT Checkpoint 试点

这个可公开案例记录了一次三 seed LoRA SFT 受控试点，使用锁定版本的 `Qwen/Qwen2.5-0.5B-Instruct`。它实际跑通了完整本地流程：

```text
产生 checkpoint -> 导出聚合证据 -> posttrain gate -> 有边界的解释 -> 决策
```

它是对完整工作流的小规模验收，不是通用模型 benchmark，也不声称 SFT 证明了唯一的隐藏因果机制。

![受控 Checkpoint 决策](checkpoint_decision.zh.svg)

## 实验协议

| 项目 | 记录值 |
|---|---|
| Seeds | `0, 1, 2` |
| Checkpoint 阶段 | `initial`、`mid`、`final` |
| Checkpoint run | 9 |
| Initial-to-candidate gate | 6 |
| Withheld 评测 | 128 条 GSM8K + 64 条格式遵循 fixture |
| 模型 revision | `7ae557604adf67be50417f59c2c2f167def9a775` |
| Split hash | `sha256:664cb24ac6d779378bf256c49f1369f910f49a788594d8813af51655af7bd4b4` |
| 保守决策 | `hold` |

LoRA 协议使用 320 条训练记录和 80 条验证记录。仓库只保存聚合行、决策、来源哈希和有边界的解释，不保存 Prompt、数据样本、逐样本预测、模型权重、adapter、trainer state、凭据、隐藏推理或私有路径。

## 观察到了什么

| 指标 | Initial | Mid | Final | 结果含义 |
|---|---:|---:|---:|---|
| 平均任务分数 | 0.0885 | 0.1788 | 0.1944 | withheld 聚合分数提高了 0.1059。 |
| GSM8K 分数 | 0.1328 | 0.2682 | 0.2917 | 固定 slice 上的最终数值准确率提高。 |
| 格式遵循分数 | 0.0000 | 0.0000 | 0.0000 | 格式 slice 没有改善。 |
| 平均生成 token | 147.34 | 106.34 | 107.34 | Final 相比 initial 减少 27.2%。 |
| 平均延迟（毫秒） | 8963.94 | 6389.04 | 6691.54 | Final 相比 initial 降低 25.4%。 |
| Generation mismatch | 0.5729 | 0.4826 | 0.4670 | 数值下降，但仍高于配置的 0.10 边界。 |
| Selective-risk AURC | 0.8712 | 0.7071 | 0.6674 | 风险排序改善，但仍高于配置的 0.40 复核边界。 |
| Trajectory drift | 8.3955 | 8.7674 | 8.8259 | 漂移增加 0.4304，触发稳定性 hold。 |

六个配对 gate 全部给出 `hold`。三个 seed 的 final 分数增量分别是 0.0990、0.0990 和 0.1198，配对 bootstrap 区间均高于 0。直接产生 hold 影响的是 trajectory/prompt stability 和 generation mismatch/readout alignment；selective risk 与 reachability 要求复核，routing 证据不足，格式 slice 保持不变则是独立观察。门禁没有否认分数改善，而是把“任务性能提高”和“是否可以晋级”分开判断。

## 如何解释这个决策

1. **观察到了什么：** 任务分数提高、输出更短、延迟降低，selective-risk 和 mismatch 指标朝更好方向变化。
2. **可以解释什么：** 在这套固定协议中，SFT 与性能、效率、表示和风险行为的共同变化有关联。
3. **不能证明什么：** 这些关联不能证明唯一因果机制、普遍提升，也不能证明它已经适合所有部署场景。
4. **下一步行动：** 修复格式 slice，区分解码预算饱和与模型失败，降低或解释 trajectory/readout drift，并在晋级前补充受控 routing 干预。

因此，`hold` 的准确含义是：**按照当前 policy，暂不晋级这个 checkpoint**。它不等于实验失败，也不等于没有观察到有用变化。

## 可审计文件

- [`checkpoint_metrics.csv`](checkpoint_metrics.csv)：9 行聚合 checkpoint 指标。
- [`gate_decisions.json`](gate_decisions.json)：6 个决策及触发检查。
- [`pilot_summary.json`](pilot_summary.json)：跨 seed 汇总。
- [`provenance.json`](provenance.json)：锁定模型、split、源码提交、wheel、运行环境和来源快照哈希。
- [`artifact_manifest.json`](artifact_manifest.json)：机器导出文件的 SHA-256。
- [`report.md`](report.md)：简洁的自动生成报告。

对另一个完整 run 生成同类聚合公开包：

```bash
pcl posttrain-pilot-export --run runs/sft-pilot-combined --out public/checkpoint-case
```

导出器会拒绝不完整的 run，只写入允许公开的聚合证据，并拒绝在持久化文件中出现来源绝对路径。
