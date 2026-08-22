# 真实 PEOC 导入：边界化案例

这个可公开快照生成于 2026-08-22。生成方式是对本地 PEOC NMI 复现包运行
`pcl research-import peoc --portable`。目录中只保留派生摘要和相对来源路径，
不包含本地绝对路径，也没有复制 NPZ 数组。

## 来源与完整性

- 证据来源：`real`
- 发现的来源文件：`14`
- 原始复现包清单：`sha256:8254ca7c122405739369d64e9629493c2fd6c66d9a367466fde1ef1d0375d72f`
- 生成的来源清单哈希：`sha256:cbedb26eb5722da4cdd1fb11644162167cb4a5c46f0db21cae45dba9bc7a8769`
- 可公开来源清单：`14/14` 条记录都包含相对路径和 SHA-256 哈希。
- 完整研究支持：`false`
- 主张检查：`fail`
- 证据建议：`not_supported`

## 证据状态

| 研究部分 | 状态 | 已记录结果 | 应该怎样解释 |
|---|---|---|---|
| hard evaluation | `available` | 72 条有效记录；3 个模型、4 个任务、6 种方法 | 是具体测量，不是通用排名。 |
| trajectory | `available` | 选中的平稳/异质轨迹对 | 只能支持有边界的拟合衰减对比。 |
| 阶段异质性 | `failed_validation` | 结论 `FAIL`；留出集 rho `-0.5429`，CI `[-1.0, 0.6364]` | 是负面证据，不能支持阶段控制选择器。 |
| 分段 soft evaluation | `unusable` | 没有样本数大于 0 的记录 | 不能支持正向 soft evaluation 主张。 |
| Riccati/DARE | `missing` | 没有发现合格来源 | 这个复现包不支持 Riccati 主张。 |
| soft-to-hard | `missing` | 没有发现投影诊断 | 不支持部署投影主张。 |

状态合计：`available=2`、`partial=0`、`failed_validation=1`、
`unusable=1`、`missing=2`。

## Hard 结果真正说明了什么

在 12 个“模型 × 任务”单元中，`tv_pmp` 相对 `static_autograd` 有 6 个更高、
6 个更低。各单元差值的未加权描述性平均值是 `+0.0063`，范围为
`-0.0566` 到 `+0.0449`；`tv_pmp` 只在 12 个单元中的 2 个取得最高均值。
这些是描述性汇总，不是显著性检验。结果明显依赖任务，不能说明某种优化器普遍更好。

## 选中的轨迹对

| 类型 | 模型 | Seed | 经验衰减率 | 平均 R2 | 轨迹数 |
|---|---|---:|---:|---:|---:|
| 平稳算术 | Qwen/Qwen2.5-7B-Instruct | 0 | `0.02471` | `0.6020` | 16 |
| 异质 GSM8K | Qwen/Qwen2.5-7B-Instruct | 0 | `0.001741` | `0.0880` | 32 |

选中的平稳摘要具有更强的拟合衰减信号。它只是轨迹诊断，不是完整语言模型全局稳定性的证明。

## 当前最强安全主张

这个案例只能报告导入的 PEOC 测量结果及其限制：hard-test 汇总给出了依赖任务、模型和
方法的具体结果；选中的平稳轨迹摘要比异质轨迹摘要具有更强的拟合衰减信号；阶段异质性
验证结果为 FAIL；分段 soft 汇总不能用于正向主张。它不是通用 benchmark，也不是完整
PEOC 验证。

机器可读证据：[research_case_study.json](research_case_study.json)。
导入教程：[research_import_peoc.zh.md](../../research_import_peoc.zh.md)。
