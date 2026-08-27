# Control（闭环控制协议）

## 目的

`promptcontrollab.control` 定义面向 Prompt 和 AI Agent 的本地闭环协议。它记录版本化 `ControlRun`，接收有序生命周期事件，执行 Preflight 决策，分析归因与稳定性，并给出有边界的最终决策。

## 使用场景

- 启动只检查、Provider 范围或 Agent 范围的 Control Run。
- 在下游工作发生前对模型请求或工具执行进行 Gate。
- 重放 Agent 集成产生的有序事件，并避免重复写入。
- 解释哪些输入发生变化，以及运行表现为收敛、停滞、振荡还是发散。

## CLI 命令

```bash
pcl control --prompt "检查这个请求" --authorization inspect --out runs/control
pcl bridge serve --transport stdio
pcl harness replay --session session.jsonl --out runs/harness-replay
pcl harness finalize --runs runs --session session-id
```

## Python API

批准后的 canonical package 提供协议记录和工作流入口：

```python
from promptcontrollab.control import (
    ControlEvent,
    ControlRun,
    analyze_attribution,
    analyze_stability,
    run_control,
)
```

其他公共契约包括 `PreflightDecision`、`AttributionReport`、`StabilityReport`、`ControlDecision`、`ControlBridge` 和 `EventLog`。

## 输入与产物

- 输入：Prompt 或 Prompt 摘要、授权范围、Policy、Provider/模型元数据和有序生命周期事件。
- 输出：`control_run.json`、`events.jsonl`、`preflight.json`、`attribution.json`、`stability.json`、`decision.json`、`report.md` 和 `report.html`。
- Event ID 和序列号用于确定性重放与去重。

## 依赖

协议、事件日志、分析和 stdio bridge 使用默认零额外依赖运行环境，并依赖 `core` 与 `preflight`。Provider 和 Agent 实现通过 `integrations` 接入，Control 领域不直接反向依赖它们。

## 扩展点

- 在不改变已有事件语义的前提下增加版本化事件类型。
- 增加带显式证据和可信度的归因维度与稳定性信号。
- 增加把外部 Agent 事件转换为稳定 Control 协议的 adapter。

## 限制

- 归因表示基于证据的关联，不是严格因果识别。
- 稳定性标签是可观测事件的启发式汇总，也可能返回 `insufficient_evidence`。
- 自动 steering 和恢复必须显式启用，并受 Policy 约束。

## 测试与示例

可参考 Control Loop 指南、Benchmark fixture 和 DeepSeek Harness 集成测试。运行：

```bash
python -m pytest tests -k "control or bridge or attribution or stability"
```
