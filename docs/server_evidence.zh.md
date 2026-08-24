# 导入分散的服务器实验依据

`pcl evidence` 可以把分散在不同目录中的 trajectory、Riccati、soft-hard、部署门禁、generation-aware、selective-risk 和 Agent episode 结果，整理成带哈希的证据清单和以解释为主的本地报告。

## 第 1 步：只读扫描，不修改服务器实验树

**怎么操作**

```bash
pcl evidence scan \
  --root /path/to/experiments \
  --profile peoc-server \
  --out server_evidence_manifest.json
```

**会得到什么：** `server_evidence_manifest.json`。每个命中的文件都有稳定排序、字节数、SHA-256、adapter、角色、媒体类型和读取策略。

**这说明什么问题：** 清单明确记录当前到底有哪些依据。`.pt` 默认只记录元数据和哈希，`.npz` 默认只做哈希校验；扫描不会启动模型，也不会改动来源目录。

**下一步：** 检查 `adapter_counts` 和 warning。缺失的 adapter 会保留为缺失依据，不会被自动补数。

## 第 2 步：验证并统一解释

**怎么操作**

```bash
pcl evidence import \
  --manifest server_evidence_manifest.json \
  --out runs/server-evidence
```

需要分享结果时可加 `--portable`。它只生成不含原始路径的 `portable/` 派生包，包括公开来源清单、证据矩阵、可解释性报告和 claim check；不会复制原始 JSON/CSV、权重或数组。

**会得到什么**

| 文件 | 记录什么 | 可以说明什么问题 |
|---|---|---|
| `source_manifest.json` | 已验证的来源身份和哈希 | 扫描后依据有没有变化 |
| `evidence_matrix.json` | 输入、状态、置信度、解释角色和缺失项 | 当前能回答哪些诊断问题 |
| `interpretability_report.json/html` | 观察、解释、范围、边界和下一步 | 如何在不隐藏不确定性的前提下解读结果 |
| `claim_check.json` | 允许和不允许表达的结论 | 是否支持普遍性或因果性表述 |

**这说明什么问题：** 每项结果会归入 `mechanism`（机制）、`boundary`（适用边界）、`stability`（稳定性）、`uncertainty`（不确定性）或 `decision`（决策）。原始 p-value、区间和 `CONFIRMATORY_FAIL_CLOSED` 等状态不会被改写。

**下一步：** 打开 `interpretability_report.html`，或在 `pcl ui --runs runs` 中选择该 run。

## 七类内置 adapter

- `turnpike_a800`：轨迹衰减、漂移和任务异质性。
- `riccati_ass_hyp`：拟合有限维 DARE surrogate 的局部自洽性。
- `soft_hard_tv`：时序结构、容量、QAT 和投影 gap 归因。
- `deployment_gate`：为什么通过、需要复核或保持 fail-closed。
- `generation_aware`：teacher-forced/free-generation 错配和 pilot 边界。
- `selective_risk`：AURC、固定 coverage accuracy 和可信样本选择。
- `agent_episode`：连接 Prompt、工具、测试、验证器和逐轮行为。

## 结论边界

这套流程提供有范围的、基于观测的可解释性。它不能证明 Prompt 或 checkpoint 普遍提升、隐藏权重身份、LLM 全局稳定性，或在没有受控干预时证明严格因果关系。公开的[服务器案例](case_studies/server_evidence/README.zh.md)展示了一份真实快照保留下来的聚合依据。
