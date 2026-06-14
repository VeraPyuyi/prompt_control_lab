# prompt_control_lab

[![GitHub stars](https://img.shields.io/github/stars/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/forks)
[![GitHub watchers](https://img.shields.io/github/watchers/VeraPyuyi/prompt_control_lab?style=social)](https://github.com/VeraPyuyi/prompt_control_lab/watchers)
[![License](https://img.shields.io/github/license/VeraPyuyi/prompt_control_lab)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

**面向 prompt 优化的控制论诊断与可复现证据工具。**

`prompt_control_lab` 把 prompt 实验变成可审计证据：干净切分、成对统计、prompt-only 有效性检查、soft-to-hard gap、hidden-state trajectory 诊断、Riccati surrogate 探针和 time-varying soft-control 对比。它也提供围绕证据层的 policy guard、模型溯源、diff audit、本地 UI、IDE/GitHub 模板。

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

![prompt_control_lab 工作流](docs/assets/workflow.zh.svg)

## 它补上了什么

| 层级 | 用来做什么 | 命令 |
|---|---|---|
| 研究协议 | 干净对比 prompt，并给出不确定性 | `pcl split`, `pcl analyze`, `pcl stats`, `pcl validity` |
| 论文诊断 | soft-hard、trajectory、Riccati、tv-soft 检查 | `pcl research-demo`, `pcl diagnose`, `pcl soft-hard`, `pcl trajectory`, `pcl riccati`, `pcl tv-soft` |
| 证据包 | claim 边界和 reviewer-facing artifact | `pcl evidence-card`, `pcl evidence-gate`, `pcl claim-check` |
| 生态桥接 | 给外部 eval 导出补证据层 | `pcl import`, `pcl evidence-from`, `pcl evidence-audit` |
| Agent 应用层 | preflight、模型溯源、diff audit、历史记录 | `pcl guard`, `pcl model-detect`, `pcl audit-diff`, `pcl history` |

论文功能完整映射：[论文功能映射](docs/research_from_paper.zh.md)。

## 常用命令

```bash
pcl research-demo --out runs/research-demo
pcl diagnose --run runs/research-demo
pcl import promptfoo --input results.json --out runs/from-promptfoo --prompt-id candidate
pcl import prompt-optimizer --input favorites.json --out runs/from-prompt-optimizer
pcl evidence-audit --tool promptfoo --baseline-input results.json --candidate-input results.json --out runs/from-promptfoo-audit
pcl guard --prompt "Fix this bug" --profile coding --policy examples/guard.policy.yaml
pcl model-detect --response response.json --provider openai
pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit
pcl export-report --run runs/quick --out runs/quick/report.zip
```

`pcl ingest` 仍作为 `pcl import` 的向后兼容别名保留。

## UI 和演示

页面：Research Overview、Tutorial、Workflows、Guard Prompt、Run Report、Model Drift、Agent Diff Audit 和 History。

![prompt_control_lab UI 工作流教程截图](docs/assets/tutorial_workflows.zh.png)

4K 实操演示：[中文 MP4](docs/assets/demo/prompt_control_lab_demo.zh.mp4) | [English MP4](docs/assets/demo/prompt_control_lab_demo.en.mp4)。

## 证据边界

- 模型溯源记录公开 model id 和证据等级，不证明服务商隐藏权重版本。见 [决策指南](docs/decision_guide.zh.md)。
- 本地 paired pilots 是透明小样本，不是通用 benchmark：[preflight pilot](docs/case_studies/agent_guard_pilot.zh.md)、[paired agent pilot](docs/case_studies/agent_guard_paired_pilot.zh.md)、[生产级试点协议](docs/production_pilot.zh.md)。
- `pcl guard` 和 `pcl audit-diff` 是启发式 preflight / governance 工具。它们能减少明显风险并产出审计 artifact，但不能证明 agent 行为一定安全。

## 更多文档

生态说明：[生态桥接](docs/ecosystem_bridge.zh.md)、[对比说明](docs/comparison.zh.md)、[生态 scorecard](docs/assets/ecosystem_scorecard.zh.svg)、[PCL 补充证据矩阵](docs/assets/ecosystem_evidence_matrix.zh.svg)。
使用文档：[使用背景](docs/background.zh.md)、[面向用户](docs/users.zh.md)、[教程](docs/tutorial.zh.md)、[Artifact 说明](docs/artifacts.zh.md)、[创新点](docs/innovation.zh.md)、[发布和安装验证](docs/release_install.zh.md)、[插件模板](plugins/)。

Apache-2.0。见 [LICENSE](LICENSE)。
