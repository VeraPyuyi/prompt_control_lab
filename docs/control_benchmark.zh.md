# 控制基准

[English](control_benchmark.en.md) | [控制闭环](control_loop.zh.md) | [模型提供商](providers.zh.md) | [本地 UI](control_ui.zh.md)

PromptControlLab 提供一个开放且版本化的基准夹具，用于检查确定性的控制分析契约。它是合成回归测试，不是公开模型或 Agent 排行榜。

## 运行方式

```bash
python -m promptcontrollab.control_benchmark examples/control-benchmark/manifest.json
```

清单使用 `prompt_control_lab.control_benchmark_manifest.v1`；命令只打印一个 `prompt_control_lab.control_benchmark_result.v1` 对象。Fixture 使用 `prompt_control_lab.control_event.v1` 所检查的可观测事件形状，但这个命令不会写出 `ControlRun` 或 `ControlEvent` artifact。无需托管服务或私有评测器即可复核结果。

## 测量内容

夹具包含五类带标签轨迹：

| 标签 | 检查的契约 |
|---|---|
| `converging` | 误差在观测窗口内下降。 |
| `stalled` | 进展持续低于配置阈值。 |
| `oscillating` | 方向反复变化且未稳定收敛。 |
| `diverging` | 误差在观测步骤中增长。 |
| `insufficient_evidence` | 轨迹太短或不完整，无法形成受支持的判断。 |

`accuracy` 是确定性分析器复现夹具标签的比例。它适合发现分析器或事件协议回归；解读时应同时查看夹具清单、协议版本、配置和逐例输出，而不能把它当作独立质量分数。

## 解读边界

该基准**不**测量模型智能、Agent 任务性能、因果影响、生产可靠性或安全。通过它不能证明某个提示词、模型提供商或 Agent 更好，也不能建立启用控制所产生的因果效应。公开模型比较还需要独立记录模型标识、端点、参数、日期、原始产物，以及与主张匹配的评测设计。

该基准只回答一个窄问题：给定这些版本化的合成事件，当前 PromptControlLab 是否产生预期的控制分类？任何更宽的结论都应使用真实运行产物和明确的研究方案。
