# Evidence（证据接入与解释）

## 目的

`promptcontrollab.evidence` 负责导入、对齐和解释外部实验结果。它把评测、Prompt-Reach Adapter、后训练 checkpoint 和有边界的研究 artifact 连接到可审计的来源 manifest 与决策 Gate。

## 使用场景

- 扫描只读实验目录并生成确定性的来源 manifest。
- 导入 Promptfoo、Langfuse、LangSmith、DeepEval、Prompt Optimizer、PEOC 或服务器证据。
- 对齐本地与远程证据，同时不复制私有或大型来源资产。
- 使用 capability-aware Gate 比较与 SFT/DPO/PPO/GRPO 相关的 checkpoint。

## CLI 命令

```bash
pcl evidence scan --root /path/to/evidence --profile prompt-reach-v2 --out manifest.json
pcl evidence import --manifest manifest.json --out runs/evidence --portable
pcl evidence merge --primary local.json --secondary server.json --out runs/merged
pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate
pcl research-import peoc --bundle /path/to/read-only-bundle --out runs/peoc
pcl posttrain-gate --baseline runs/checkpoint-000 --candidate runs/checkpoint-500 --policy examples/posttrain.policy.yaml --out runs/posttrain-gate
```

## Python API

批准后的 canonical package 提供来源导入与后训练入口：

```python
from promptcontrollab.evidence import (
    EvidenceImportOptions,
    import_evidence_manifest,
    run_posttrain_gate,
    scan_evidence_root,
)
```

Adapter 覆盖 Prompt Reachability、Readout Alignment、Routing、Projection 和 Prompt Stability。Evidence Card、Gate、Pilot Plan 和 PEOC Import Option 支持专项流程。

## 输入与产物

- 输入：只读根目录、来源 manifest、外部工具导出、checkpoint run 目录、Policy 和 Adapter 专属 JSON/CSV 汇总。
- 输出：`server_evidence_manifest.json`、`source_manifest.json`、`evidence_matrix.json`、`source_gap_report.json`、`interpretability_report.json/html`、`claim_check.json` 和后训练 Gate artifact。
- Portable Import 只复制批准的派生文件；大型模型、私有 Prompt 和原始数据集保留在 Bundle 外部。

## 依赖

扫描和多数导入流程使用默认运行环境，并依赖 `core`、`provenance` 与 `evaluation`。受控后训练执行需要 `posttrain` extra；科学证据 Adapter 可能需要 `research`。

## 扩展点

- 注册具备确定性发现和规范化输出的 Evidence Profile 与 Adapter。
- 增加能够保留来源和结论边界的外部工具 Importer。
- 增加能够区分缺失、不适用和失败证据的 capability-aware Gate 检查。

## 限制

- 导入的历史证据可以解释已记录关联，但不能补出原实验缺失的对照。
- `mixed`、`inconclusive` 和 `requires_reanalysis` 不代表已证实提升。
- 后训练诊断用于辅助 checkpoint 选择，不替代训练，也不能证明因果机制。

## 测试与示例

可参考 `docs/case_studies/`、Evidence fixture 和后训练测试。运行：

```bash
python -m pytest tests -k "evidence or ingest or peoc or posttrain"
```
