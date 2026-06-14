# prompt_control_lab

[![GitHub stars](https://img.shields.io/github/stars/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/forks)
[![GitHub watchers](https://img.shields.io/github/watchers/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/watchers)
[![License](https://img.shields.io/github/license/VeraPyuyi/prompt_control_lab)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

**面向 prompt 优化的控制论诊断与可复现证据工具。**

`prompt_control_lab` 把 prompt 优化实验变成可审计 artifact：干净切分、成对统计、prompt-only 有效性检查、soft-to-hard gap、hidden-state trajectory 诊断、Riccati surrogate 探针和 time-varying soft-control 对比。它也提供 agent prompt guard、模型溯源、diff audit、本地 UI、IDE/GitHub 模板。

Python 包名：`promptcontrollab`。仓库名：`prompt_control_lab`。英文文档：[README.md](README.md)。

## 快速开始

```bash
git clone https://github.com/VeraPyuyi/prompt_control_lab.git
cd prompt_control_lab
pip install -e ".[research,ui]"
pcl research-demo --out runs/research-demo
pcl diagnose --run runs/research-demo
pcl ui --runs runs/ --policy examples/guard.policy.yaml --port 8501
```

这会在本地生成研究证据包、诊断报告和交互式仪表盘。UI 只读取本地文件，不上传数据。

![prompt_control_lab 工作流](docs/assets/workflow.zh.svg)

## 它补上了什么

| 路径 | 得到什么 | 起步命令 |
|---|---|---|
| 论文流程 | tri-split 协议、soft-hard、trajectory、Riccati、tv-soft 诊断 | `pcl research-demo` |
| 证据桥接 | 面向 reviewer 的证据卡片和外部 eval 审计 | `pcl import`, `pcl evidence-audit` |
| Agent 应用层 | prompt 执行前检查、模型溯源、diff audit、历史视图 | `pcl guard`, `pcl audit-diff` |

论文功能映射：[Research From The Paper](docs/research_from_paper.zh.md)。生态对比：[Ecosystem Bridge](docs/ecosystem_bridge.zh.md)。

## 常用命令

```bash
pcl guard --prompt "Fix this bug" --profile coding --policy examples/guard.policy.yaml
pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate
pcl evidence-audit --tool promptfoo --baseline-input results.json --candidate-input results.json --out runs/audit
pcl model-detect --response response.json --provider openai
pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit
pcl export-report --run runs/quick --out runs/quick/report.zip
```

`pcl ingest` 仍作为 `pcl import` 的向后兼容别名保留。

## UI 和演示

本地 UI 包含 Research Overview、Tutorial、Workflows、Guard Prompt、Run Report、Model Drift、Agent Diff Audit 和 History。

![prompt_control_lab UI 工作流教程截图](docs/assets/tutorial_workflows.zh.png)

4K 实操演示：[中文 MP4](docs/assets/demo/prompt_control_lab_demo.zh.mp4) | [English MP4](docs/assets/demo/prompt_control_lab_demo.en.mp4)。

## 证据边界

- 模型溯源记录公开 model id 和证据等级，不证明服务商隐藏权重版本。见 [Decision Guide](docs/decision_guide.zh.md)。
- 本地 pilots 是透明小样本，不是通用 benchmark：[preflight pilot](docs/case_studies/agent_guard_pilot.zh.md)、[paired agent pilot](docs/case_studies/agent_guard_paired_pilot.zh.md)、[production pilot protocol](docs/production_pilot.zh.md)。
- `pcl guard` 和 `pcl audit-diff` 是启发式 preflight/governance 工具，能降低明显风险并产出审计 artifact，但不能证明 agent 行为一定安全。

## 文档

[背景](docs/background.zh.md) | [教程](docs/tutorial.zh.md) | [Artifacts](docs/artifacts.zh.md) | [创新点](docs/innovation.zh.md) | [对比](docs/comparison.zh.md) | [生态 scorecard](docs/assets/ecosystem_scorecard.zh.svg) | [证据矩阵](docs/assets/ecosystem_evidence_matrix.zh.svg) | [发布/安装](docs/release_install.zh.md) | [插件](plugins/)

Apache-2.0。见 [LICENSE](LICENSE)。
