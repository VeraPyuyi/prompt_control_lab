# 开放控制事件基准

本目录提供一个确定性、无需联网的 PromptControlLab 控制协议基准。它使用五个小型合成事件会话，检查现有分析器的分类契约。运行时不需要 API 密钥或第三方依赖。

## 数据结构

`manifest.json` 使用 `prompt_control_lab.control_benchmark_manifest.v1`。顶层字段包括稳定标识 `benchmark_id`、用途 `description`、解释边界 `claim_boundary` 和有序用例列表 `cases`。

每个用例包含 `case_id`、相对 JSONL 路径 `fixture`、`expected_label`、简短的 `evidence_boundary` 以及稀疏的 `baseline_run`。每条事件严格包含 `sequence`、`event_type` 和 `payload`。夹具只保存合成的可观察元数据，不包含原始指令、凭据、私有推理轨迹或商业材料。

## 运行方式

在仓库根目录先安装当前检出版本，再运行模块：

```powershell
python -m pip install -e .
python -m promptcontrollab.control_benchmark examples/control-benchmark/manifest.json
```

Python API：

```python
from pathlib import Path

from promptcontrollab.control_benchmark import run_benchmark

result = run_benchmark(Path("examples/control-benchmark/manifest.json"))
```

## 输出

结果使用 `prompt_control_lab.control_benchmark_result.v1`。每个用例输出 `observed`、`expected`、`pass`、证据边界、完整稳定性报告和不计分的归因报告；汇总字段为 `passed_cases`、`total_cases` 和 `accuracy`。

稀疏的对照元数据会使归因结果保持为 `insufficient_evidence`。这保留了分析器仅描述关联的边界，准确率只计算稳定性标签是否匹配。

## 局限性

这些事件是为覆盖已记录阈值而构造的合成数据。该基准不评估真实智能体质量、提示效果、隐藏模型状态、因果效应、部署行为或普适安全性。通过仅表示当前确定性分析器符合这些夹具定义的契约。
