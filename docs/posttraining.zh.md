# 后训练 Checkpoint 诊断

`pcl posttrain-gate` 会同时比较 baseline 与 candidate checkpoint 的性能、来源一致性、稳定性、部署边界、生成错配和 selective-risk 依据。

```bash
pcl posttrain-gate \
  --baseline runs/checkpoint-000 \
  --candidate runs/checkpoint-500 \
  --policy examples/posttrain.policy.yaml \
  --out runs/posttrain-gate
```

## 每个 checkpoint 目录需要什么

```text
manifest.json
metrics.json
stats.json
diagnostics/trajectory.json
diagnostics/soft_hard.json
diagnostics/generation_mismatch.json
diagnostics/selective_risk.json
```

candidate 的 `stats.json` 保存 baseline/candidate 匹配样本的 paired bootstrap 区间和 permutation
p-value。两侧 `metrics.json` 都要记录 `n`、`sample_hash`、平均生成 token 和 latency；paired 记录还会
绑定两侧 checkpoint ID、split hash、sample hash、`n_pairs` 和 `mean_delta`。字段不一致或置信区间
端点反向时，门禁会拒绝把它当作有效依据。

如果 SFT、DPO、PPO 或 GRPO checkpoint 并不部署 learned soft prompt，应明确写成“不适用”：

```json
{
  "applicability": "not_applicable",
  "reason": "This checkpoint does not deploy a learned soft prompt."
}
```

这比虚构一个 low projection risk 更准确。

## 四种决策

- `pass`：必需依据完整，而且所有检查满足 policy。
- `needs_review`：依据完整，但 slice 或不确定性检查需要人工复核。
- `hold`：分数、来源、稳定性、投影或生成检查中的 fail 级条件超出 policy。
- `insufficient_evidence`：缺少必需 artifact，门禁拒绝猜测。

输出包括 `posttrain_gate.json`、`checkpoint_comparison.json`、`mechanism_attribution.json` 和 `report.md/html`。

## 可以和不能说明什么

这项门禁可以辅助选择 checkpoint，并解释分数变化是否伴随 trajectory drift、generation mismatch、selective-risk 行为或部署 gap。它能服务 SFT、DPO、PPO、GRPO 流程，但不替代这些训练算法。受控的同源 checkpoint 对比比无关 Base/Instruct 模型对比更接近训练阶段归因，但没有受控干预时仍不能证明隐藏因果机制。

仓库还提供受保护的 SFT pilot 协议。它默认只生成计划；只有存在明确的资源批准记录并取得独占锁后才能启动 GPU 工作，避免因为“某张卡看起来空闲”而干扰服务器现有队列。

```bash
pcl posttrain-pilot \
  --model /local/cache/Qwen2.5-0.5B \
  --train pilot/train.jsonl --validation pilot/validation.jsonl \
  --withheld pilot/withheld.jsonl --format-fixture pilot/format.jsonl \
  --out runs/sft-pilot
```

这条命令只写出 `pilot_protocol.json`。写计划前，工具会同时按样本 ID 和规范化后的 prompt/answer
内容检查 train、validation、withheld、format fixture 是否重叠。真正开始训练还必须显式添加 `--execute --approval
<有过期时间的资源批准.json> --gpu <编号>`；脚本随后会再次检查 GPU 进程并取得独占 `flock`。

pilot 中的 `trajectory` 指最终 hidden layer 里相邻 prompt token 的表示漂移；generation mismatch
对 teacher-forced 与 free-generation 的答案使用同一套 canonical text exact-match 规则，避免评分口径
差异被误认为生成错配。
