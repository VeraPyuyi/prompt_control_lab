# Checkpoint Change Review

这个可公开案例复用了真实三 seed SFT 试点的聚合证据，并把它送入统一 Change Review：

```text
聚合 Initial Checkpoint
  -> 聚合 Final Checkpoint
  -> 比较有效性
  -> 归因与稳定性
  -> Candidate Checkpoint Gate
  -> 面向 Reviewer 的决策
```

本地运行：

```bash
pcl review --baseline docs/case_studies/checkpoint_change_review/baseline --candidate docs/case_studies/checkpoint_change_review/candidate --out runs/checkpoint-review
pcl ui --runs runs/checkpoint-review --language zh
```

## 改了什么

预期变化是 checkpoint 身份从 `aggregate-initial` 变为 `aggregate-final`。公开聚合 manifest 记录的模型、评测 Prompt、split、metric 和 Agent 身份保持不变。

## 观察到了什么

| 观察项 | Initial | Final |
|---|---:|---:|
| 平均任务分数 | 0.0885 | 0.1944 |
| 生成阶段错配 | 0.5729 | 0.4670 |
| 选择性风险 AURC | 0.8712 | 0.6674 |
| 表示轨迹漂移 | 8.3955 | 8.8259 |

Final 分数提高，生成阶段错配和选择性风险朝更好方向变化；但表示轨迹漂移增加，格式遵循 slice 仍为零，而且来源 checkpoint gate 要求 `hold`。

## 为什么决策仍是 `hold`

Change Review 不会用一个分数覆盖来源门禁。Candidate 已记录的后训练 gate 因此被保留：在稳定性与生成/读出发现得到修复或合理解释前，暂不晋级。

## 证据边界

这个案例支持“在固定协议中，SFT 阶段与性能、效率、稳定性和风险画像共同变化”这一有边界的关联解释。它不能识别唯一因果机制，不能证明模型普遍改善，也不能证明部署安全。

## 可审计文件

- [`case_manifest.json`](case_manifest.json)：案例摘要。
- [`baseline/manifest.json`](baseline/manifest.json) 与 [`candidate/manifest.json`](candidate/manifest.json)：比较身份。
- [`review/change_review.json`](review/change_review.json)：顶层决策。
- [`review/comparison_validity.json`](review/comparison_validity.json)：身份与混杂因素检查。
- [`review/human_feedback.json`](review/human_feedback.json)：固定 reviewer 问题。
- [`review/decision_trace.json`](review/decision_trace.json)：产生决策的检查轨迹。

这里仅包含聚合证据，不保存 Prompt、逐样本生成、模型权重、凭据、隐藏推理或私有路径。
