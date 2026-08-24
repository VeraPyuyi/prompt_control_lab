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
diagnostics/prompt_reachability.json
diagnostics/readout_alignment.json
diagnostics/prompt_routing.json
diagnostics/prompt_projection.json
diagnostics/prompt_stability.json
```

五类 Prompt 诊断分别回答不同的问题：

| 诊断 | 观察什么 | 决策边界 |
|---|---|---|
| Prompt 可达性 | 相对 initial checkpoint 的表示变化 | 变化过大时可要求复核，但不能据此证明 Prompt 导致了分数变化。 |
| 读出对齐 | hidden representation 与答案/readout 证据之间的 gap | 能力可用且 gap 过大时，可按 policy 暂停 candidate。 |
| Prompt 路由 | 是否真的比较了不同 Prompt/控制路径 | 没有干预证据时是 `insufficient_evidence`，不是模型失败。 |
| Prompt 投影 | soft-to-hard 部署 gap | 普通 LoRA checkpoint 应标记为 `not_applicable`。 |
| Prompt 稳定性 | 漂移或重复运行之间的变化 | 漂移增大时可按 policy 暂停 candidate。 |

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

仓库还提供受保护的 SFT pilot 协议。先从锁定版本的 GSM8K 和自动生成的格式 fixture 准备确定性输入：

```bash
pcl posttrain-pilot-prepare \
  --out /root/prompt_control_lab_runtime/pilot-data
```

这条命令会写出 320 条训练、80 条验证、128 条 withheld GSM8K，以及 64 条 withheld 格式任务；选择过程是确定性的，并记录在 `dataset_provenance.json`。离线环境可以通过 `--gsm8k-train-jsonl` 和 `--gsm8k-test-jsonl` 使用预先准备的数据。

pilot 默认只生成计划；只有存在明确的资源批准记录并取得独占锁后才能启动 GPU 工作，避免因为“某张卡看起来空闲”而干扰服务器现有队列。

先把锁定版本的模型快照哈希写入独立 runtime，不修改共享模型缓存：

```bash
pcl posttrain-model-provenance \
  --model /root/prompt_control_lab_runtime/models/Qwen2.5-0.5B-Instruct \
  --model-id Qwen/Qwen2.5-0.5B-Instruct --revision PINNED_40_OR_64_HEX_COMMIT \
  --out /root/prompt_control_lab_runtime/provenance/qwen-0.5b.json
```

```bash
pcl posttrain-pilot \
  --runtime-root /root/prompt_control_lab_runtime \
  --model /root/prompt_control_lab_runtime/models/Qwen2.5-0.5B-Instruct \
  --model-provenance /root/prompt_control_lab_runtime/provenance/qwen-0.5b.json \
  --train /root/prompt_control_lab_runtime/pilot-data/train.jsonl \
  --validation /root/prompt_control_lab_runtime/pilot-data/validation.jsonl \
  --withheld /root/prompt_control_lab_runtime/pilot-data/withheld.jsonl \
  --format-fixture /root/prompt_control_lab_runtime/pilot-data/format_fixture.jsonl \
  --out /root/prompt_control_lab_runtime/runs/sft-pilot
```

这条命令只写出 `pilot_protocol.json`。写计划前，工具会同时按样本 ID 和规范化后的 prompt/answer
内容检查 train、validation、withheld、format fixture 是否重叠。真正开始训练还必须显式添加 `--execute --approval
<有过期时间的资源批准.json> --gpu <编号>`；脚本随后会再次检查 GPU 进程并取得独占 `flock`。
使用 `--execute` 时，模型、provenance、split、审批记录、锁文件和输出都必须解析到
`--runtime-root` 内；工具会在创建任何锁或输出文件之前完成该检查。
审批记录必须指向同一 runtime 内真实且非符号链接的 JSON `queue_source`。进入执行锁后，
PromptControlLab 会重新读取该文件，核对精确 SHA-256，并要求它的 `checked_at` 与审批记录一致且
不超过 90 秒。默认 `global_queue` 范围仍要求 pending/running job 都为零。如果资源所有者明确分配
指定 GPU，也可以使用范围更窄的 `selected_gpu` 审批：审批记录和快照必须同时记录选中/获准 GPU、
明确授权、单卡预留，以及已验证“避开外来计算进程”的外部调度策略 SHA-256。该模式不会跳过最后
两次 GPU 空闲检查或独占锁。指定 GPU 审批可以显式记录不超过 4096 MiB 的空闲显存上限；默认值仍为
1024 MiB。审批记录不能替代新鲜的资源快照。

pilot 中的 `trajectory` 指最终 hidden layer 里相邻 prompt token 的表示漂移。generation mismatch
会对 teacher-forced 与 free-generation 使用同一套任务评分器：GSM8K 提取最终数值答案，格式任务
执行区分大小写的严格字符串匹配。如果输出用满 generation budget 仍没有 EOS，工具会记录 saturation；
默认 policy 会把任何 saturation 视为评分依据不足，而不会把解码预算限制静默算成 checkpoint 失败。

受控协议固定 seeds `0,1,2` 和 `initial/mid/final` 三个 checkpoint 阶段。完整运行会生成九个 checkpoint 目录、六个 initial-to-mid/final 门禁、保守的跨 seed `pilot_summary.json/html` 和 `decision_trace.json`。在这些 artifact 真正出现前，资源预检只能说明准备状态，不能写成 checkpoint 性能证据。
