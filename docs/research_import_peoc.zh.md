# 导入真实 PEOC 研究证据

当你已经有 Prompt-Engineering-Optimal-Control（PEOC）复现包，并希望把它变成
可检查、可追溯的 `prompt_control_lab` run 时，使用这条流程。导入器不会重新运行
语言模型；它会校验、归一化并解释已有记录，而且不会把验证失败、不可用、部分可用
或缺失的内容包装成正向证据。

## 开始前

先安装研究与 UI 依赖，并确认复现包目录中包含清单和结果文件：

```bash
pip install -e ".[research,ui]"
pcl doctor
```

下面用 `<peoc-bundle>` 表示本地 `nmi_replication_bundle` 目录，导入结果写到
`runs/peoc-real`。

## 第 1 步：导入复现包

**怎么操作**

```bash
pcl research-import peoc \
  --bundle <peoc-bundle> \
  --out runs/peoc-real \
  --portable \
  --language zh
```

**会得到什么**

- `source_manifest.json`：来源文件、大小、用途和 SHA-256 哈希。
- `peoc_evidence.json`：归一化后的研究部分及其明确状态。
- `research_case_study.json`、`.md`、`.html`：带边界的案例报告。
- `evidence_card.*`、`claim_check.*`、`research_gap_plan.*`、
  `research_gap_status.*`、`research_bundle.*`：完整的下游证据链。

**这说明什么问题**

只有必要的结构化来源能够解析，而且导入过程中来源身份保持不变，导入才会成功。
`--portable` 会复制适合公开的小型 JSON/CSV 文件；较大的 NPZ 轨迹数组只保留带哈希的引用，
不会悄悄复制到 run 中。

**下一步**

先打开 `runs/peoc-real/research_case_study.html`，再判断任何结果能支持什么结论。

## 第 2 步：先看状态，再看分数

每个研究部分只会处于以下状态之一：

| 状态 | 含义 | 能支持正向主张吗？ |
|---|---|---|
| `available` | 真实来源可解析，并通过该部分检查。 | 只能在写明的限制内使用。 |
| `partial` | 必要证据不完整。 | 不能。 |
| `failed_validation` | 已记录的验证门禁没有通过。 | 不能；应保留为负面证据。 |
| `unusable` | 有真实来源，但数据不能支持这项分析。 | 不能。 |
| `missing` | 没有发现合格来源。 | 不能。 |

**怎么操作**

```bash
pcl claim-check --run runs/peoc-real --claim full-research
pcl gap-status --run runs/peoc-real
```

**会得到什么**

`claim_check.json/html` 会回答“当前证据是否支持指定主张”；
`research_gap_status.json/html` 会列出尚未完成的诊断。

**这说明什么问题**

完整研究主张检查失败并不是工具失败，而是一个有价值的结论。它能阻止用户把 hard-test
分数或一组轨迹对比写成“完整 PEOC 已验证”。

**下一步**

打开 `research_gap_plan.html`，决定缺失证据应该重新生成、从可信来源导入，还是明确排除在主张之外。

## 第 3 步：验证整条证据链

**怎么操作**

```bash
pcl research-bundle --run runs/peoc-real --verify --strict
```

**会得到什么**

`research_bundle_verification.json/html` 会记录每个索引 artifact 的预期哈希和实际哈希。

**这说明什么问题**

`pass` 只能证明当前本地文件与生成的 bundle 索引一致。它不能证明 API 服务商隐藏的模型权重，
也不能让有限任务上的实验自动代表所有任务。

**下一步**

归档整个 run，或者在共享 portable 小文件时同时保留来源清单和外部大文件引用。

## 第 4 步：在研究 UI 中检查

**怎么操作**

```bash
pcl ui --runs runs --language zh
```

选择 `peoc-real`，再打开“研究总览”。

**会得到什么**

首个区域会显示真实证据包标记、来源清单哈希、各状态数量、hard 方法表、选中的平稳/异质
轨迹对比、验证失败记录、缺失项和本地案例报告入口。

**这说明什么问题**

导入的既有实验摘要会和“当前 run 新执行的诊断”分开标注。UI 不会把 `partial`、
`failed_validation`、`unusable` 或 `missing` 计入“可用”。

**下一步**

只针对你真正拥有的输入运行新诊断：

```bash
pcl soft-hard --soft soft_prompt.npz --vocab vocab_embeddings.npz --out runs/peoc-real/diagnostics
pcl trajectory --states hidden_states.npz --out runs/peoc-real/diagnostics
pcl riccati --trajectory hidden_states.npz --out runs/peoc-real/diagnostics
pcl tv-soft --predictions method_predictions.jsonl --out runs/peoc-real/diagnostics
```

完成后重新运行 `gap-status`、`evidence-card`、`claim-check` 和
`research-bundle --verify --strict`。

## 覆盖来源、重新导入与安全边界

只有自动发现选错来源时，才使用 `--hard-summary`、可重复的 `--trajectory-file` 或
`--heterogeneity-summary`。重新导入已有 run 必须显式传入 `--overwrite`；导入器只替换
自己登记的生成文件。遇到无法确定结果的文件系统异常时，它会保留事务备份供人工恢复，
不会猜测性地覆盖文件。

## 科学解释边界

- hard-test 汇总依赖具体任务和模型，不是通用优化器排名。
- turnpike-like 衰减是轨迹诊断，不是完整语言模型全局稳定性证明。
- Riccati/DARE 结果只适用于拟合出的有限维 surrogate。
- 阶段异质性验证失败时，必须保留为负面证据。
- 来源哈希证明文件字节身份，不证明隐藏模型权重身份。
- 导入结果是已有记录，不是本工具刚刚重新运行的实验。

公开的边界化真实案例见
[`docs/case_studies/peoc_real/`](case_studies/peoc_real/README.zh.md)。
