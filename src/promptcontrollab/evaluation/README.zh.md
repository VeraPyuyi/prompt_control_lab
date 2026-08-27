# Evaluation（可复现评测）

## 目的

`promptcontrollab.evaluation` 提供可复现的 Prompt 与 checkpoint 比较，包括确定性数据切分、预测导入、指标、配对统计、有效性检查、解释、Policy Gate、报告和运行历史。

## 使用场景

- 在同一批样本上比较 baseline 与 candidate Prompt。
- 识别数据泄漏、slice 退化和统计上不确定的提升。
- 生成供 reviewer 阅读的 Markdown、HTML 和结构化 Gate artifact。
- 索引并比较一个目录中的历史 run。

## CLI 命令

```bash
pcl analyze --config promptcontrol.example.yaml --out runs/quick
pcl split --data examples/tasks.jsonl --out runs/split
pcl eval --data examples/tasks.jsonl --predictions examples/candidate.jsonl --out runs/candidate
pcl stats --baseline runs/baseline/predictions.jsonl --candidate runs/candidate/predictions.jsonl --out runs/stats.json
pcl explain --run runs/quick --level technical
pcl gate --run runs/quick --policy examples/gate.policy.yaml
pcl report --run runs/quick
pcl history index --runs runs --out runs/history_index.json
```

## Python API

批准后的 canonical package 提供编排和专项分析接口：

```python
from promptcontrollab.evaluation import (
    compare_prediction_files,
    generate_report,
    run_gate,
    run_import_eval,
    run_quick_analysis,
)
```

`ReportModel`、`SplitResult`、`ComparisonResult`、指标工具、History 函数和比较有效性检查可用于自定义流程。

## 输入与产物

- 输入：任务 JSONL、预测 JSONL、baseline/candidate run、指标、Policy，以及可选 Prompt/模型身份。
- 输出：`splits.json`、`predictions.jsonl`、`metrics.json`、`stats.json`、`explanation.json`、`gate_result.json`、`report.md`、`report.html` 和 History artifact。
- `export-report` 只打包已知 run artifact，不包含未声明的源码文件。

## 依赖

核心评测流程不需要额外依赖，使用 `core` 的 schema/文件工具和 `provenance` 的身份记录。统计函数使用确定性的 Python 实现，不强制安装科学计算栈。

## 扩展点

- 通过显式评分和汇总函数增加指标。
- 通过 `ReportModel` 增加报告字段，不从渲染后的 Markdown 反向解析。
- 将新的 Gate 检查表示为包含状态、影响、原因和下一步行动的结构化证据。

## 限制

- 统计显著性不能建立因果关系，也不能证明部署安全。
- 只有模型、数据和相关执行设置受控时，Prompt-only 比较才有效。
- 导入预测的可信范围取决于已记录的来源和校验信息。

## 测试与示例

可参考 `promptcontrol.example.yaml`、Quickstart 指南和 Evaluation 测试。运行：

```bash
python -m pytest tests -k "analyze or split or eval or stats or report or gate or history"
```
