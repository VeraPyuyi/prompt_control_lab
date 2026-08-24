# 真实服务器证据快照

这个可公开案例来自对现有 PEOC/A800 实验树的一次只读扫描。扫描器索引了七类 adapter 下的 911 个文件，再将其约简为聚合指标、解释角色、快照哈希和结论边界。

仓库中不包含模型权重、私有 Prompt、数据集样本、服务器绝对路径或隐藏推理。portable 来源身份不依赖服务器路径，快照哈希为 `sha256:f06e78767d7d399ed5d120de9671ea9ec2881c8e2c41a161ad6bfb716e914367`。

## 这份快照可以解释什么

- 机制：soft/hard 投影、time-varying 结构、容量对照与 Agent episode 结构。
- 稳定性：stationary 与 heterogeneous 轨迹衰减，以及拟合 Riccati/DARE surrogate。
- 适用边界：teacher-forced 与 free-generation pilot 及其停止规则。
- 不确定性：360 个 seed row 上的 selective-risk 行为。
- 决策：72 行冻结部署分析及其 fail-closed 原因。

这份快照**不能**证明 Prompt 普遍提升、严格因果关系、LLM 全局收敛或线上模型稳定性。`observed` 与 `inconclusive` 保留原始证据含义；二者都可以用于解释适用范围和决定下一项实验。

参见[完整说明](../../server_evidence.zh.md)，以及机器可读的[公开来源清单](public_source_manifest.json)、[证据矩阵](evidence_matrix.json)、[可解释性报告](interpretability_report.json)、[HTML 报告](interpretability_report.html)和[结论检查](claim_check.json)。adapter 校验发现 68 条 generation record 和 1 条 trajectory 侧 record 的 schema 不完整；它们仍计入来源数量，但不会被静默提升为已验证结论。

三 seed SFT checkpoint pilot 现在已经具备锁定版本并完成哈希校验的 Qwen2.5-0.5B-Instruct，以及确定性的 train/validation/withheld 输入。但 `2026-08-24T13:59:42Z` 的只读检查报告 4 个 running queue job、20 个 pending queue job，并且仍有 GPU 计算进程；独立依赖环境也尚未完整，因此 pilot 没有启动。这个资源门禁决定记录在 [sft_pilot_status.json](sft_pilot_status.json) 中；仓库不会声称已经得到 checkpoint 结果。
